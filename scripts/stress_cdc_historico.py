"""Stress test do CDC de histórico RH — 30 iterações com valores variados.

Cada iteração simula um novo arquivo de RH (alguns alterados, alguns removidos,
alguns novos, o resto idêntico), roda RegistrarHistoricoRh contra o banco e
compara o resultado com um ORÁCULO independente (diff calculado por fora com a
mesma normalização). Reporta esperado vs obtido por iteração.
"""

import os
import sys
import random
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import RhAtivo
from infraestrutura.leitores_arquivos.leitor_base import LeitorArquivoBase
from infraestrutura.leitores_arquivos.leitor_rh import LeitorRh
from infraestrutura.repositorios.repositorio_funcionario_sqlite import RepositorioFuncionarioSqlite
from aplicacao.casos_de_uso.registrar_historico_rh import RegistrarHistoricoRh, _CAMPOS_ATIVO
from dominio.entidades.funcionario_ativo import FuncionarioAtivo
from dominio.objetos_valor.cargo import Cargo
from dominio.servicos_dominio.servico_padronizacao import ServicoPadronizacao
from loguru import logger

logger.remove()  # silencia o ruído de log durante o stress

RAIZ = os.path.join(os.path.dirname(__file__), "..")
ORIGINAL = os.path.join(RAIZ, "Arquivos_origem", "PROJETOIAM (8).CSV")
PAD = ServicoPadronizacao()
random.seed(42)  # reprodutível


def carregar_base():
    """Lê os 2207 ativos reais do CSV original."""
    leitor = LeitorRh()
    enc = LeitorArquivoBase().detectar_encoding  # noqa
    from pathlib import Path
    import pandas as pd
    arq = Path(ORIGINAL)
    e = LeitorArquivoBase().detectar_encoding(arq)
    df = pd.read_csv(arq, sep=";", dtype=str, encoding=e, on_bad_lines="skip")
    from infraestrutura.leitores_arquivos.leitor_rh import _resolver_coluna, _valor, _parse_data, _COLUNAS
    col = {k: _resolver_coluna(df, k) for k in _COLUNAS}
    base = []
    for _, row in df.iterrows():
        mat = _valor(row, col["matricula"])
        if not mat:
            continue
        base.append(FuncionarioAtivo(
            matricula=mat,
            nome=_valor(row, col["nome"]),
            cpf=_valor(row, col["cpf"]),
            cargo=Cargo(
                codigo=_valor(row, col["cargo_codigo"]),
                descricao=_valor(row, col["cargo_descricao"]),
                departamento=_valor(row, col["departamento"]),
                centro_custo=_valor(row, col["centro_custo_codigo"]),
            ),
            email=_valor(row, col["email"]) or None,
            data_admissao=_parse_data(_valor(row, col["data_admissao"])),
            situacao=_valor(row, col["situacao"]) or "ATIVO",
        ))
    # dedup por matrícula normalizada (igual ao merge)
    dedup = {}
    for f in base:
        dedup[PAD.normalizar_matricula(f.matricula)] = f
    return list(dedup.values())


def clonar(f: FuncionarioAtivo) -> FuncionarioAtivo:
    return FuncionarioAtivo(
        matricula=f.matricula, nome=f.nome, cpf=f.cpf,
        cargo=Cargo(f.cargo.codigo, f.cargo.descricao, f.cargo.departamento, f.cargo.centro_custo),
        email=f.email, data_admissao=f.data_admissao, situacao=f.situacao,
    )


def comparavel(f: FuncionarioAtivo) -> dict:
    """Mesma normalização que o CDC usa, para o oráculo."""
    bruto = {
        "nome": f.nome, "cpf": f.cpf,
        "cargo_codigo": f.cargo.codigo, "cargo_descricao": f.cargo.descricao,
        "centro_custo_codigo": f.cargo.centro_custo, "departamento": f.cargo.departamento,
        "data_admissao": str(f.data_admissao) if f.data_admissao else "",
        "email": f.email, "situacao": f.situacao,
    }
    out = {}
    for k in _CAMPOS_ATIVO:
        v = bruto.get(k)
        if k == "cpf":
            out[k] = PAD.normalizar_cpf(v)
        elif k == "nome":
            out[k] = PAD.normalizar_nome(v)
        elif k == "situacao":
            out[k] = PAD.normalizar_situacao(v)
        elif k == "data_admissao":
            out[k] = v or ""
        else:
            out[k] = (str(v).strip() if v is not None else "")
    return out


def oraculo(anterior_db: list, recebidos: list) -> dict:
    """Diff independente: como o CDC DEVERIA classificar."""
    ant = {PAD.normalizar_matricula(r.matricula): {
        "nome": r.nome, "cpf": r.cpf, "cargo_codigo": r.cargo_codigo,
        "cargo_descricao": r.cargo_descricao, "centro_custo_codigo": r.centro_custo_codigo,
        "departamento": r.departamento,
        "data_admissao": str(r.data_admissao) if r.data_admissao else "",
        "email": r.email, "situacao": r.situacao,
    } for r in anterior_db}

    def norm(d):
        o = {}
        for k in _CAMPOS_ATIVO:
            v = d.get(k)
            if k == "cpf":
                o[k] = PAD.normalizar_cpf(v)
            elif k == "nome":
                o[k] = PAD.normalizar_nome(v)
            elif k == "situacao":
                o[k] = PAD.normalizar_situacao(v)
            elif k == "data_admissao":
                o[k] = v or ""
            else:
                o[k] = (str(v).strip() if v is not None else "")
        return o

    ant = {m: norm(d) for m, d in ant.items()}
    nov = {PAD.normalizar_matricula(f.matricula): comparavel(f) for f in recebidos}
    novos = sum(1 for m in nov if m not in ant)
    alterados = sum(1 for m in nov if m in ant and ant[m] != nov[m])
    removidos = sum(1 for m in ant if m not in nov)
    return {"total": len(nov), "novos": novos, "alterados": alterados, "removidos": removidos}


def mutacionar(estado: list, idx_seq: int):
    """Gera o 'arquivo do dia': aplica remoções/alterações/novos aleatórios."""
    estado = [clonar(f) for f in estado]
    n = len(estado)
    n_rem = random.randint(0, max(1, n // 20))      # até ~5%
    n_alt = random.randint(0, max(1, n // 15))      # até ~7%
    n_new = random.randint(0, 40)

    random.shuffle(estado)
    removidos = estado[:n_rem]
    resto = estado[n_rem:]
    for f in resto[:n_alt]:
        f.cargo = Cargo(f"C{random.randint(1000,9999)}",
                        f"CARGO MUT {idx_seq}-{random.randint(1,999)}",
                        f.cargo.departamento,
                        f"{random.randint(10,99)}.{random.randint(10,99)}")
        if random.random() < 0.5:
            f.situacao = random.choice(["ATIVO", "BLOQUEADO", "INATIVO"])
    novos = []
    for k in range(n_new):
        novos.append(FuncionarioAtivo(
            matricula=f"SIM{idx_seq:02d}{k:03d}",
            nome=f"NOVO SIM {idx_seq}-{k}",
            cpf=str(70000000000 + idx_seq * 1000 + k).zfill(11),
            cargo=Cargo("C0001", "ESTAGIARIO", "TI", "10.10"),
            email=f"sim{idx_seq}_{k}@x.com", situacao="ATIVO",
        ))
    novo_arquivo = resto + novos
    random.shuffle(novo_arquivo)
    return novo_arquivo, {"esp_rem": n_rem, "esp_alt": n_alt, "esp_new": n_new}


def main():
    db = os.path.join(tempfile.gettempdir(), "stress_cdc.db")
    if os.path.exists(db):
        os.remove(db)
    cx = ConexaoBancoDados(db)
    cx.inicializar()
    repo = RepositorioFuncionarioSqlite(cx)
    cdc = RegistrarHistoricoRh(cx)

    base = carregar_base()
    print(f"Base real carregada: {len(base)} ativos\n")

    # Iteração 0 — baseline
    cdc.registrar_ativos(base)
    repo.salvar_ativos(base, "baseline")
    estado = [clonar(f) for f in base]

    print(f"{'it':>3} | {'arquivo':>7} | {'novos':>5} {'alt':>4} {'rem':>4} | "
          f"{'oráculo (n/a/r)':>16} | {'OK?':>4}")
    print("-" * 70)

    falhas = 0
    for it in range(1, 31):
        recebidos, esp = mutacionar(estado, it)

        with cx.sessao() as s:
            anterior_db = s.query(RhAtivo).all()
            anterior_db = [RhAtivo(
                matricula=r.matricula, nome=r.nome, cpf=r.cpf,
                cargo_codigo=r.cargo_codigo, cargo_descricao=r.cargo_descricao,
                centro_custo_codigo=r.centro_custo_codigo, departamento=r.departamento,
                data_admissao=r.data_admissao, email=r.email, situacao=r.situacao,
            ) for r in anterior_db]

        orc = oraculo(anterior_db, recebidos)
        res = cdc.registrar_ativos(recebidos)
        repo.salvar_ativos(recebidos, f"sim_{it}")

        ok = (res["novos"] == orc["novos"]
              and res["alterados"] == orc["alterados"]
              and res["removidos"] == orc["removidos"]
              and res["total"] == orc["total"])
        if not ok:
            falhas += 1
        print(f"{it:>3} | {len(recebidos):>7} | "
              f"{res['novos']:>5} {res['alterados']:>4} {res['removidos']:>4} | "
              f"{orc['novos']:>5}/{orc['alterados']:>3}/{orc['removidos']:>3}     | "
              f"{'OK' if ok else 'FALHA':>4}")

        # próximo 'estado' = o que o arquivo deste dia trouxe (vira a base do dia seguinte)
        estado = [clonar(f) for f in recebidos]

    print("-" * 70)
    with cx.sessao() as s:
        from infraestrutura.banco_dados.schema import HistoricoRh, SnapshotRh
        th = s.query(HistoricoRh).count()
        ts = s.query(SnapshotRh).count()
    print(f"Iterações: 30 | Falhas: {falhas} | "
          f"linhas na trilha: {th} | snapshots: {ts}")
    print("RESULTADO:", "TODOS OS 30 TESTES OK ✓" if falhas == 0 else f"{falhas} FALHA(S) ✗")
    os.remove(db)


if __name__ == "__main__":
    main()
