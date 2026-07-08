# -*- coding: utf-8 -*-
"""Dobra das interacoes multiusuario (.jsonl da rede) na base de dados.

Ao rodar o Processador, as interacoes acumuladas na pasta INTERACOES da rede
sao consolidadas nas tabelas do banco: `quarentena` / `quarentena_historico`
(tipo QUARENTENA) e `resolucoes` (tipo RESOLUCAO — resolucao de pendencia
sob ticket do Jira).

Envelope das interacoes: contrato v1 documentado em
`docs/INTERACOES_ENVELOPE_V1.md`. Este consumer e' tolerante a v0 (legado)
e v1 — quando schema_version sobir para 2, este arquivo precisa co-evoluir
para normalizar v1 -> v2 na leitura.

O reset da pasta usa rename atomico:
    INTERACOES\\  ->  INTERACOES_processando\\   (1 operacao, instantanea)
e em seguida cria uma INTERACOES\\ nova e vazia. A partir desse instante os
usuarios ja escrevem na pasta nova; as interacoes antigas ficam isoladas em
INTERACOES_processando\\ para a dobra. A pasta so e' removida apos o commit.

Se o Processador cair no meio, a pasta _processando sobrevive e e' recuperada
na proxima execucao — a dobra e' idempotente.
"""
import json
import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from loguru import logger

from infraestrutura.interacoes.repositorio_interacoes import ler_todas

_SQL_QUAR = """
CREATE TABLE IF NOT EXISTS quarentena (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  usuario TEXT NOT NULL, nome_usuario TEXT, sistema TEXT, matricula TEXT,
  origem TEXT,
  data_inicio TEXT NOT NULL, data_fim TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'Em quarentena',
  dias INTEGER, ticket TEXT, titulo TEXT, motivo_entrada TEXT,
  criado_por TEXT, criado_em TEXT NOT NULL
)
"""

_SQL_HIST = """
CREATE TABLE IF NOT EXISTS quarentena_historico (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  usuario TEXT NOT NULL, nome_usuario TEXT, sistema TEXT, matricula TEXT,
  origem TEXT,
  data_inicio TEXT NOT NULL, data_fim TEXT NOT NULL,
  data_saida TEXT NOT NULL, motivo TEXT NOT NULL,
  dias INTEGER, ticket TEXT, titulo TEXT, motivo_entrada TEXT,
  criado_por TEXT, criado_em TEXT, encerrado_por TEXT,
  movido_em TEXT NOT NULL
)
"""

# Colunas adicionadas depois (formulario de quarentena). Migração ADITIVA — bancos
# em HML ganham as colunas via ALTER, sem perder dados (ver _migrar_colunas_quar).
_COLS_QUAR_FORM = [("dias", "INTEGER"), ("ticket", "TEXT"),
                   ("titulo", "TEXT"), ("motivo_entrada", "TEXT")]


def _migrar_colunas_quar(c):
    """ALTER TABLE ADD COLUMN idempotente p/ quarentena e _historico (bancos antigos)."""
    for tab in ("quarentena", "quarentena_historico"):
        existentes = {r[1] for r in c.execute(f"PRAGMA table_info({tab})")}
        for nome, tipo in _COLS_QUAR_FORM:
            if nome not in existentes:
                c.execute(f"ALTER TABLE {tab} ADD COLUMN {nome} {tipo}")
    # resolucoes.motivo (combobox obrigatorio do XML) — aditivo p/ bases antigas
    existe_res = {r[1] for r in c.execute("PRAGMA table_info(resolucoes)")}
    if existe_res and "motivo" not in existe_res:
        c.execute("ALTER TABLE resolucoes ADD COLUMN motivo TEXT")

_SQL_RES = """
CREATE TABLE IF NOT EXISTS resolucoes (
  registro_id TEXT PRIMARY KEY,
  ticket TEXT NOT NULL,
  ticket_url TEXT,
  descricao TEXT,
  motivo TEXT,
  pendencias TEXT,
  cargo TEXT,
  centro_custo TEXT,
  nome TEXT,
  resolvido_por TEXT,
  resolvido_em TEXT,
  dobrado_em TEXT
)
"""

_SQL_ATALHOS = """
CREATE TABLE IF NOT EXISTS atalhos (
  id TEXT PRIMARY KEY,
  nome TEXT NOT NULL,
  origem TEXT,
  filtros TEXT NOT NULL,
  criado_por TEXT,
  criado_em TEXT,
  dobrado_em TEXT
)
"""


class DobrarInteracoes:
    """Consolida as interacoes da rede nas tabelas de quarentena do banco."""

    def __init__(self, caminho_banco: str, pasta_interacoes: str,
                 quarentena_dias: int = 90):
        self._banco = caminho_banco
        self._pasta = pasta_interacoes
        self._dias = quarentena_dias

    def executar(self) -> None:
        if not self._pasta:
            logger.info("Dobra de interacoes: pasta da rede nao configurada — pulando.")
            return
        base = Path(self._pasta)
        proc = base.with_name(base.name + "_processando")

        # 1. Recuperacao: pasta _processando orfa de uma execucao interrompida
        if proc.exists():
            logger.warning(
                f"Dobra: pasta orfa '{proc.name}' de execucao anterior — recuperando.")
            self._dobrar(proc)

        # 2-3. Rename atomico INTERACOES -> INTERACOES_processando + nova pasta vazia
        if not base.exists():
            logger.info("Dobra de interacoes: nenhuma pasta INTERACOES na rede — nada a dobrar.")
            return
        try:
            base.rename(proc)
        except Exception as e:
            logger.error(f"Dobra: falha ao renomear {base} -> {proc}: {e!r} — pulando.")
            return
        try:
            base.mkdir(exist_ok=True)
        except Exception as e:
            logger.warning(f"Dobra: falha ao recriar {base}: {e!r}")

        # 4-6. Dobra no banco + remove a pasta processada
        self._dobrar(proc)

    def _dobrar(self, proc: Path) -> None:
        interacoes = ler_todas(str(proc))
        if interacoes:
            self._aplicar(interacoes)
        try:
            shutil.rmtree(proc)
        except Exception as e:
            logger.warning(f"Dobra: nao foi possivel remover {proc}: {e!r}")
        logger.info(
            f"Dobra: {len(interacoes)} interacao(es) consolidada(s) de '{proc.name}'.")

    def _aplicar(self, interacoes: list) -> None:
        # QUARENTENA: agrupa todas as interacoes por registro
        por_reg: dict = {}
        for it in interacoes:
            if it.get("tipo_interacao") != "QUARENTENA":
                continue
            rid = it.get("registro_id")
            if rid:
                por_reg.setdefault(str(rid), []).append(it)
        # RESOLUCAO de pendencia: vence a interacao de data_acao mais recente
        res_reg: dict = {}
        for it in interacoes:
            if it.get("tipo_interacao") != "RESOLUCAO":
                continue
            rid = it.get("registro_id")
            if not rid:
                continue
            ant = res_reg.get(str(rid))
            if ant is None or str(it.get("data_acao", "")) >= str(
                    ant.get("data_acao", "")):
                res_reg[str(rid)] = it

        # ATALHO: para cada id, vence a interacao de data_acao mais recente
        # (acao=CRIAR ou EXCLUIR). Idempotente.
        atalho_reg: dict = {}
        for it in interacoes:
            if it.get("tipo_interacao") != "ATALHO":
                continue
            rid = it.get("registro_id")
            if not rid:
                continue
            ant = atalho_reg.get(str(rid))
            if ant is None or str(it.get("data_acao", "")) >= str(
                    ant.get("data_acao", "")):
                atalho_reg[str(rid)] = it

        c = sqlite3.connect(self._banco, timeout=15)
        try:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA busy_timeout=8000")
            c.executescript(_SQL_QUAR)
            c.executescript(_SQL_HIST)
            c.executescript(_SQL_RES)
            c.executescript(_SQL_ATALHOS)
            _migrar_colunas_quar(c)
            n_env = n_res = 0
            for rid, its in por_reg.items():
                its.sort(key=lambda x: str(x.get("data_acao", "")))
                ultima = its[-1]
                envios = [x for x in its if x.get("acao") == "ENVIAR"]
                env = envios[-1] if envios else None
                if ultima.get("acao") == "ENVIAR":
                    if self._ativar(c, rid, env or ultima):
                        n_env += 1
                elif ultima.get("acao") == "RESOLVER":
                    if self._resolver(c, rid, ultima, env):
                        n_res += 1
            n_resol = 0
            agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for rid, it in res_reg.items():
                c.execute(
                    "INSERT OR REPLACE INTO resolucoes (registro_id,ticket,"
                    "ticket_url,descricao,motivo,pendencias,cargo,centro_custo,nome,"
                    "resolvido_por,resolvido_em,dobrado_em) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    [rid, it.get("ticket") or "", it.get("ticket_url") or "",
                     it.get("descricao") or "", it.get("motivo") or "",
                     json.dumps(it.get("pendencias") or [], ensure_ascii=False),
                     it.get("cargo") or "", it.get("centro_custo") or "",
                     it.get("nome") or "", it.get("usuario") or "",
                     # normaliza ISO com 'T' -> espaco, para o formato de data ficar
                     # uniforme no banco (dt_resolvido entra em comparacoes de string
                     # com dt_pendencia/dt_aderente, que usam espaco).
                     (it.get("data_acao") or "").replace("T", " "), agora])
                n_resol += 1

            n_atalho_cri = n_atalho_exc = 0
            for rid, it in atalho_reg.items():
                ex = it.get("extras") or {}
                acao = it.get("acao", "")
                if acao == "EXCLUIR":
                    rc = c.execute("DELETE FROM atalhos WHERE id=?", [rid]).rowcount
                    if rc:
                        n_atalho_exc += 1
                else:  # CRIAR (default) — upsert
                    c.execute(
                        "INSERT OR REPLACE INTO atalhos (id,nome,origem,filtros,"
                        "criado_por,criado_em,dobrado_em) VALUES (?,?,?,?,?,?,?)",
                        [rid, ex.get("nome") or rid, ex.get("origem") or "",
                         json.dumps(ex.get("filtros") or [], ensure_ascii=False),
                         it.get("usuario") or "", it.get("data_acao") or "", agora])
                    n_atalho_cri += 1

            c.commit()
            logger.info(
                f"Dobra: {n_env} em quarentena, {n_res} resolvido(s), "
                f"{n_resol} resolucao(oes) de pendencia, "
                f"{n_atalho_cri} atalho(s) criado/atualizado, "
                f"{n_atalho_exc} atalho(s) excluido(s) aplicado(s) na base.")
        finally:
            c.close()

    def _dias_de(self, env: dict) -> int:
        """Prazo (dias) informado na interacao; cai no default se ausente/invalido."""
        try:
            d = int(env.get("dias"))
            return d if d > 0 else self._dias
        except (TypeError, ValueError):
            return self._dias

    def _data_fim(self, di: str, dias: int = None) -> str:
        # di pode vir com hora ("aaaa-mm-dd hh:mm:ss"); o prazo conta em dias.
        try:
            return (datetime.strptime((di or "")[:10], "%Y-%m-%d")
                    + timedelta(days=int(dias) if dias else self._dias)).strftime("%Y-%m-%d")
        except Exception:
            return (di or "")[:10]

    def _ativar(self, c, rid: str, env: dict) -> bool:
        """Insere o funcionario na quarentena. Idempotente (ja ativo = no-op)."""
        if c.execute("SELECT 1 FROM quarentena WHERE usuario=?", [rid]).fetchone():
            return False
        di = (env.get("data_acao") or "").replace("T", " ")   # data_inicio com hora
        dias = self._dias_de(env)
        c.execute(
            "INSERT INTO quarentena (usuario,nome_usuario,sistema,matricula,origem,"
            "data_inicio,data_fim,status,dias,ticket,titulo,motivo_entrada,"
            "criado_por,criado_em) "
            "VALUES (?,?,?,?,?,?,?, 'Em quarentena', ?,?,?,?, ?, ?)",
            [rid, env.get("nome") or rid, env.get("sistema") or "", rid,
             env.get("origem") or "Inclusão / Alteração", di, self._data_fim(di, dias),
             dias, env.get("ticket") or "", env.get("titulo") or "",
             env.get("motivo") or "",
             env.get("usuario") or "", env.get("data_acao") or di])
        return True

    def _resolver(self, c, rid: str, res: dict, env: dict) -> bool:
        """Move o funcionario para o historico. Idempotente (mesma saida = no-op)."""
        ds = (res.get("data_acao") or "").replace("T", " ")   # data_saida com hora
        if c.execute("SELECT 1 FROM quarentena_historico "
                     "WHERE usuario=? AND data_saida=?", [rid, ds]).fetchone():
            c.execute("DELETE FROM quarentena WHERE usuario=?", [rid])
            return False
        row = c.execute(
            "SELECT nome_usuario,sistema,matricula,origem,data_inicio,data_fim,"
            "dias,ticket,titulo,motivo_entrada,criado_por,criado_em "
            "FROM quarentena WHERE usuario=?", [rid]).fetchone()
        if row:
            nome, sis, mat, origem, di, df, dias, tk, titulo, motent, crp, cre = row
        elif env:
            di = (env.get("data_acao") or "").replace("T", " ")
            nome, sis, mat = env.get("nome") or rid, env.get("sistema") or "", rid
            dias = self._dias_de(env)
            origem, df = env.get("origem") or "", self._data_fim(di, dias)
            tk, titulo, motent = env.get("ticket") or "", env.get("titulo") or "", env.get("motivo") or ""
            crp, cre = env.get("usuario") or "", env.get("data_acao") or di
        else:
            nome, sis, mat, origem = rid, "", rid, ""
            di = df = cre = ds
            dias, tk, titulo, motent, crp = None, "", "", "", ""
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # motivo de SAIDA: vem da interacao (retirada manual exige motivo);
        # default p/ compat com interacoes antigas sem motivo.
        motivo_saida = (res.get("motivo") or "").strip() or "Retirado da quarentena"
        c.execute(
            "INSERT INTO quarentena_historico (usuario,nome_usuario,sistema,matricula,"
            "origem,data_inicio,data_fim,data_saida,motivo,dias,ticket,titulo,"
            "motivo_entrada,criado_por,criado_em,encerrado_por,movido_em) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [rid, nome, sis, mat, origem, di, df, ds, motivo_saida, dias, tk, titulo,
             motent, crp, cre, res.get("usuario") or "", agora])
        c.execute("DELETE FROM quarentena WHERE usuario=?", [rid])
        return True
