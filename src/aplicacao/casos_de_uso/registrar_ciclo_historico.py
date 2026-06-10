# -*- coding: utf-8 -*-
"""Projeta o CICLO DE VIDA (ciclo_vida_acesso) na trilha de auditoria
`historico`, como entidade ACESSO_SISTEMA — UMA linha por marco atingido:

  dt_pendencia -> PENDENCIA  ("Pendência identificada")
  dt_resolvido -> RESOLVIDO  ("Pendência resolvida")  [com ticket]
  dt_aderente  -> ADERENTE   ("Aderente")

O historico armazena MODIFICACOES: a cada reprocesso grava as linhas que ainda
NAO existem (idempotente por matricula+marco), montando a sequencia em ordem.
Cobre tanto a transicao MANUAL (resolucao por ticket, ja dobrada em dt_resolvido)
quanto a do PROCESSADOR (pendencia/aderencia pela validacao). Quem e' lido
aderente direto (sem dt_pendencia) NAO ganha linha de pendencia — so a Aderente.
Tudo ADITIVO e BLINDADO (qualquer erro so e' logado).
"""
import json
from datetime import datetime

from loguru import logger
from sqlalchemy import text

# ordem cronologica dos marcos do ciclo
_MARCOS = (
    ("dt_pendencia", "PENDENCIA"),
    ("dt_resolvido", "RESOLVIDO"),
    ("dt_aderente",  "ADERENTE"),
)


class RegistrarCicloHistorico:

    def __init__(self, conexao):
        self._conexao = conexao

    def executar(self, agora: str = None) -> int:
        try:
            return self._executar(agora)
        except Exception as e:  # blindagem: nunca derruba o processamento
            logger.warning(f"Ciclo no historico nao registrado (ignorado): {e}")
            return 0

    def _executar(self, agora: str = None) -> int:
        agora = agora or datetime.now().isoformat(sep=" ", timespec="seconds")
        with self._conexao.sessao() as sessao:
            if not self._tabela(sessao, "ciclo_vida_acesso"):
                return 0
            rows = sessao.execute(text("""
                SELECT matricula, sistema, perfil, nome, login, cargo,
                       dt_pendencia, dt_resolvido, ticket, dt_aderente
                FROM ciclo_vida_acesso
                ORDER BY dt_pendencia, dt_resolvido, dt_aderente
            """)).fetchall()

            n = 0
            vistos = set()  # (matricula, tipo) tratados neste lote (1 linha/pessoa)
            for r in rows:
                for campo, tipo in _MARCOS:
                    data = getattr(r, campo)
                    if not data or (r.matricula, tipo) in vistos:
                        continue
                    vistos.add((r.matricula, tipo))
                    if self._existe(sessao, r.matricula, tipo):
                        continue  # idempotente: a linha desse marco ja existe
                    dados = {
                        "sistema": r.sistema or "", "perfil": r.perfil or "",
                        "nome": r.nome or "", "login": r.login or "",
                        "cargo": r.cargo or "", "data": data,
                    }
                    if tipo == "RESOLVIDO":
                        dados["ticket"] = r.ticket or ""
                    sessao.execute(text("""
                        INSERT INTO historico
                            (data_snapshot, entidade, chave_entidade, tipo_mudanca,
                             dados_novo, dt_registro, matricula)
                        VALUES
                            (:ds, 'ACESSO_SISTEMA', :mat, :tipo, :dados, :agora, :mat)
                    """), {
                        "ds": str(data)[:10], "mat": r.matricula, "tipo": tipo,
                        "dados": json.dumps(dados, ensure_ascii=False, sort_keys=True),
                        "agora": agora,
                    })
                    n += 1
            sessao.commit()
        logger.success(f"Ciclo projetado no historico: {n} linha(s) nova(s).")
        return n

    @staticmethod
    def _existe(sessao, matricula: str, tipo: str) -> bool:
        return sessao.execute(text(
            "SELECT 1 FROM historico WHERE entidade='ACESSO_SISTEMA' "
            "AND tipo_mudanca=:t AND chave_entidade=:m LIMIT 1"
        ), {"t": tipo, "m": matricula}).fetchone() is not None

    @staticmethod
    def _tabela(sessao, nome: str) -> bool:
        return sessao.execute(text(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=:n"
        ), {"n": nome}).fetchone() is not None
