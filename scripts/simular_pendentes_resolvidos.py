"""Fase 1 / SYSTUR — simulação de 30 cenários de inclusões e alterações
com ciclo PENDENTE → RESOLVIDO.

Pega as ações reais de SYSTUR (Incluir Acesso = SEM_ACESSO,
Alterar Perfil = DIVERGENTE, Em Análise = EM_ANALISE) da validacao_acessos
e, em 30 cenários, varia a fração resolvida por categoria, marcando cada
registro como RESOLVIDO/PENDENTE. Gera tabela no chat + parquet p/ Power BI.
"""

import os
import random
import sqlite3

import pandas as pd

RAIZ = os.path.join(os.path.dirname(__file__), "..", "CVC_IAM_ANALYTICS")
DB = os.path.join(RAIZ, "DADOS", "BANCO", "iam_analytics.db")
PARQUET_DIR = os.path.join(RAIZ, "DADOS", "PARQUET", "VALIDACAO")

LABEL = {
    "SEM_ACESSO": "Incluir Acesso",
    "DIVERGENTE": "Alterar Perfil",
    "EM_ANALISE": "Em Análise",
}
random.seed(42)


def carregar_acoes_systur():
    con = sqlite3.connect(DB)
    rows = con.execute(
        "SELECT status FROM validacao_acessos "
        "WHERE sistema='SYSTUR' AND status IN ('SEM_ACESSO','DIVERGENTE','EM_ANALISE')"
    ).fetchall()
    con.close()
    return [r[0] for r in rows]  # uma entrada por ação


def main():
    acoes = carregar_acoes_systur()
    por_cat = {k: acoes.count(k) for k in LABEL}
    total = len(acoes)
    print(f"Base real SYSTUR (Fase 1): {total} ações — "
          + ", ".join(f"{LABEL[k]}={v}" for k, v in por_cat.items()))
    print()

    linhas_parquet = []
    print(f"{'cen':>3} | {'fração resolv. alvo':^22} | "
          f"{'Incluir Acesso (P/R)':^22} | {'Alterar Perfil (P/R)':^22} | "
          f"{'Em Análise (P/R)':^20}")
    print("-" * 104)

    for cen in range(1, 31):
        # frações-alvo variando por cenário (alternando por categoria)
        f_incluir = round((cen / 30), 4)                       # 3%..100%
        f_alterar = round(min(1.0, ((31 - cen) / 30)), 4)      # decrescente (alterna)
        f_analise = round(abs(((cen % 10) / 10) - 0.5) * 2, 4)  # zig-zag 0..1

        alvo = {"SEM_ACESSO": f_incluir, "DIVERGENTE": f_alterar, "EM_ANALISE": f_analise}
        cont = {k: {"PENDENTE": 0, "RESOLVIDO": 0} for k in LABEL}

        for status in acoes:
            resolvido = random.random() < alvo[status]
            cont[status]["RESOLVIDO" if resolvido else "PENDENTE"] += 1

        for status in LABEL:
            for sit in ("PENDENTE", "RESOLVIDO"):
                linhas_parquet.append({
                    "cenario": cen,
                    "sistema": "SYSTUR",
                    "fase": "Fase 1",
                    "acao": LABEL[status],
                    "fracao_resolvido_alvo": round(alvo[status], 4),
                    "situacao_acao": sit,
                    "qtd": cont[status][sit],
                })

        def pr(k):
            return f"{cont[k]['PENDENTE']:>4} / {cont[k]['RESOLVIDO']:<4}"

        print(f"{cen:>3} | "
              f"inc={f_incluir:>.2f} alt={f_alterar:>.2f} ana={f_analise:>.2f} | "
              f"{pr('SEM_ACESSO'):^22} | {pr('DIVERGENTE'):^22} | {pr('EM_ANALISE'):^20}")

    print("-" * 104)

    df = pd.DataFrame(linhas_parquet)
    os.makedirs(PARQUET_DIR, exist_ok=True)
    destino = os.path.join(PARQUET_DIR, "simulacao_pendentes_resolvidos.parquet")
    df.to_parquet(destino, index=False)

    resumo = df.groupby(["acao", "situacao_acao"])["qtd"].sum().unstack(fill_value=0)
    print("Totais acumulados nos 30 cenários (por ação):")
    print(resumo.to_string())
    print()
    print(f"Parquet p/ Power BI: {os.path.relpath(destino, RAIZ)} "
          f"({len(df)} linhas: 30 cenários × 3 ações × 2 situações)")


if __name__ == "__main__":
    main()
