"""POC: cascata de matching multi-chave aplicada ao SICA_RA real (mascarado).

Mede a cobertura por nivel da cascata usando os dados reais:
- 135 registros SICA_RA com CPF mascarado (39328XXX)
- 2207 ativos do RH como universo (PROJETOIAM (8).CSV)

Saida esperada: contagem por metodo de vinculacao + lista de orfaos para
analise manual.

Roda solto:   python scripts/poc_matching_sica_ra.py
"""
import csv
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from dominio.servicos_dominio.servico_vinculacao_multi_chave import (
    FuncionarioRef, ServicoVinculacaoMultiChave,
    normalizar_cpf, normalizar_email, normalizar_nome,
)

RAIZ = Path(__file__).resolve().parent.parent
ORIGEM = RAIZ / "Arquivos_origem"


def carregar_universo_rh():
    """Le PROJETOIAM (8).CSV e devolve FuncionarioRef para cada ativo."""
    with open(ORIGEM / "PROJETOIAM (8).CSV", "r", encoding="latin-1", newline="") as f:
        rows = list(csv.reader(f, delimiter=";"))
    header = rows[0]
    idx_cpf = header.index("Numero do CPF")
    idx_mat = header.index("Matricula")
    idx_nome = header.index("Nome da Pessoa")
    # Email pode estar em "Email" ou "Email Pessoal"
    idx_email = None
    for cand in ("Email", "Email Pessoal"):
        if cand in header:
            idx_email = header.index(cand)
            break

    universo = []
    for r in rows[1:]:
        if len(r) <= idx_cpf:
            continue
        universo.append(FuncionarioRef(
            matricula=(r[idx_mat] or "").strip(),
            cpf=normalizar_cpf(r[idx_cpf]),
            email=normalizar_email(r[idx_email] if idx_email is not None and len(r) > idx_email else ""),
            nome=normalizar_nome(r[idx_nome]),
        ))
    return universo


def carregar_acessos_sica_ra():
    """Le SICA_RA_30_04.csv (skiprows=4). Devolve list de dicts com cpf
    mascarado, nome e email."""
    with open(ORIGEM / "SICA_RA_30_04.csv", "r", encoding="latin-1", newline="") as f:
        rows = list(csv.reader(f, delimiter=";"))
    rows = rows[4:]  # cabecalho de relatorio
    header = rows[0]
    idx = {col: i for i, col in enumerate(header)}
    out = []
    for r in rows[1:]:
        if len(r) <= idx["CPF"]:
            continue
        out.append({
            "usuario": (r[idx["Usuario"]] or "").strip(),
            "nome": (r[idx["Nome"]] or "").strip(),
            "cpf_mascarado": (r[idx["CPF"]] or "").strip(),
            "email": (r[idx["E-mail"]] or "").strip() if idx.get("E-mail") is not None else "",
        })
    return out


def main():
    print("=" * 70)
    print("POC — Cascata de matching multi-chave no SICA_RA mascarado real")
    print("=" * 70)

    universo = carregar_universo_rh()
    print(f"\nUniverso RH ativos: {len(universo)} funcionarios")

    acessos = carregar_acessos_sica_ra()
    print(f"Acessos SICA_RA:    {len(acessos)} registros")

    servico = ServicoVinculacaoMultiChave(universo)

    contagem = Counter()
    sem_vinculo = []
    fuzzy_revisao = []
    ambiguos = []

    for a in acessos:
        r = servico.vincular(
            cpf="",                     # CPF cheio nao temos (esta mascarado)
            email=a["email"],
            nome=a["nome"],
            cpf_mascarado=a["cpf_mascarado"],
        )
        contagem[r.metodo] += 1
        if r.metodo == "NAO_VINCULADO":
            sem_vinculo.append(a)
        elif r.metodo == "FUZZY":
            fuzzy_revisao.append((a, r.candidatos))
        elif r.candidatos and len(r.candidatos) > 1:
            ambiguos.append((a, r.candidatos))

    total = sum(contagem.values())
    print("\n" + "=" * 70)
    print("RESULTADO POR METODO")
    print("=" * 70)
    for metodo in ("CPF", "EMAIL", "CPF_PARCIAL_NOME", "NOME", "FUZZY", "NAO_VINCULADO"):
        qt = contagem.get(metodo, 0)
        pct = 100 * qt / total if total else 0
        marca = "OK" if metodo in ("CPF", "EMAIL", "CPF_PARCIAL_NOME") else \
                "REVISAR" if metodo in ("NOME", "FUZZY") else "ORFAO"
        print(f"  [{marca:7}] {metodo:<22} {qt:>4d} ({pct:5.1f}%)")

    vinculados = total - contagem.get("NAO_VINCULADO", 0) - contagem.get("FUZZY", 0)
    print(f"\nCOBERTURA EFETIVA (vincula automaticamente): {vinculados}/{total} "
          f"({100*vinculados/total:.1f}%)")
    print(f"Para revisao manual (FUZZY/ambiguos): "
          f"{contagem.get('FUZZY', 0) + len(ambiguos)}")

    if sem_vinculo:
        print(f"\n=== ORFAOS ({len(sem_vinculo)}) — primeiros 5 ===")
        for a in sem_vinculo[:5]:
            print(f"  user={a['usuario']!r}  nome={a['nome']!r}  "
                  f"cpf={a['cpf_mascarado']!r}  email={a['email']!r}")

    if fuzzy_revisao:
        print(f"\n=== FUZZY ({len(fuzzy_revisao)}) — primeiros 5 ===")
        for a, cands in fuzzy_revisao[:5]:
            print(f"  user={a['usuario']!r}  nome={a['nome']!r}  candidatos={cands}")

    if ambiguos:
        print(f"\n=== AMBIGUOS ({len(ambiguos)}) — primeiros 5 ===")
        for a, cands in ambiguos[:5]:
            print(f"  user={a['usuario']!r}  nome={a['nome']!r}  matriculas={cands}")


if __name__ == "__main__":
    main()
