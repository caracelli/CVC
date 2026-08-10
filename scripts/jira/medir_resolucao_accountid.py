"""Mede quantas pessoas da base resolvem accountId no Jira (Cards 25-26).

O campo 'Usuario Afetado' e' OBRIGATORIO no formulario 8819 e exige accountId.
Este script aplica a regra de dois niveis sobre `validacao_acessos` e reporta a
cobertura por status — o numero que diz para quantos casos o botao "Abrir
chamado no Jira" consegue funcionar sozinho.

REGRA (conjuntiva — os dois criterios juntos):
  nivel 1  e-mail exato          -> aceita
  nivel 2  nome completo IDENTICO e resultado UNICO -> aceita
  senao    falha explicita (nao chutar)

O nivel 2 nao pode afrouxar: buscar "DANIELA LOPES" devolve 50 contas e nenhuma
e' a pessoa. Homonimo aprovado aqui vira chamado aberto contra o usuario errado.

Somente GET. Grava parcial a cada 50 — execucao longa (~15 min por 900 pessoas)
tem que ser observavel enquanto roda.

Credencial: igual ao testar_credencial.py (JIRA_USER/JIRA_TOKEN, JIRA_CRED ou
.jira_cred na raiz).

Uso:
    python scripts/jira/medir_resolucao_accountid.py [--limite N] [--offset N]
"""
import argparse
import base64
import json
import os
import re
import sqlite3
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

HOST = "https://cvccorp.atlassian.net"
PORTAL = 9
FIELD_CONFIG_ID = 11659
CAMPO_USUARIO = "customfield_11358"

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BANCO_PADRAO = os.path.join(RAIZ, "CVC_IAM_ANALYTICS", "DADOS", "BANCO",
                            "iam_analytics.db")


def ler_credencial():
    u, t = os.environ.get("JIRA_USER"), os.environ.get("JIRA_TOKEN")
    if u and t:
        return u, t
    caminho = os.environ.get("JIRA_CRED") or os.path.join(RAIZ, ".jira_cred")
    if not os.path.exists(caminho):
        sys.exit(f"[X] sem credencial (JIRA_USER/JIRA_TOKEN ou {caminho}).")
    linhas = [x.strip() for x in
              open(caminho, encoding="utf-8").read().splitlines() if x.strip()]
    return linhas[0], linhas[1]


EMAIL, TOKEN = ler_credencial()
AUTH = base64.b64encode(f"{EMAIL}:{TOKEN}".encode()).decode()


def norm(s):
    """Normaliza p/ comparar nome: sem acento, sem caixa, espacos colapsados."""
    s = unicodedata.normalize("NFKD", (s or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().upper()


def buscar(termo, tentativas=3):
    q = urllib.parse.urlencode({"fieldConfigId": FIELD_CONFIG_ID,
                                "fieldName": CAMPO_USUARIO, "query": termo})
    req = urllib.request.Request(
        f"{HOST}/rest/servicedesk/1/customer/portal/{PORTAL}/user-search?{q}",
        headers={"Authorization": f"Basic {AUTH}", "Accept": "application/json"})
    for _ in range(tentativas):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception:
            time.sleep(1.5)
    return None


def resolver(nome, email):
    """Devolve (nivel, accountId|None, candidatos). nivel: 1, 2 ou 0 (falha)."""
    res = buscar(email)
    if res is None:
        return None, None, []
    for a in res:
        if (a.get("emailAddress") or "").strip().lower() == email:
            return 1, a.get("accountId"), res
    res2 = buscar(nome)
    if res2 is None:
        return None, None, []
    iguais = [a for a in res2 if norm(a.get("displayName")) == norm(nome)]
    if len(iguais) == 1:
        return 2, iguais[0].get("accountId"), res2
    return 0, None, iguais            # 0 ou 2+ identicos => ambiguo/ausente


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--banco", default=BANCO_PADRAO)
    ap.add_argument("--limite", type=int, default=900)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--saida", default=os.path.join(RAIZ, "medicao_accountid.json"))
    a = ap.parse_args()

    if not os.path.exists(a.banco):
        sys.exit(f"[X] banco nao encontrado: {a.banco}")

    con = sqlite3.connect(a.banco)
    con.row_factory = sqlite3.Row
    pessoas = con.execute("""
        SELECT email, nome,
               MIN(CASE status WHEN 'DIVERGENTE' THEN 1 WHEN 'EM_ANALISE' THEN 2
                               WHEN 'SEM_ACESSO' THEN 3 ELSE 4 END) ord
        FROM validacao_acessos
        WHERE email LIKE '%@%' AND nome IS NOT NULL
        GROUP BY lower(email), nome
        ORDER BY lower(email) LIMIT ? OFFSET ?""",
        (a.limite, a.offset)).fetchall()

    ROT = {1: "DIVERGENTE", 2: "EM_ANALISE", 3: "SEM_ACESSO", 4: "OK"}
    agg = {v: {"n": 0, "n1": 0, "n2": 0, "falha": 0} for v in ROT.values()}
    falhas, erros = [], 0

    print(f">> {len(pessoas)} pessoas (offset {a.offset})", flush=True)
    t0 = time.time()
    for i, p in enumerate(pessoas, 1):
        st = ROT[p["ord"]]
        em = (p["email"] or "").strip().lower()
        agg[st]["n"] += 1
        nivel, _acc, cands = resolver(p["nome"], em)
        if nivel is None:
            erros += 1
        elif nivel == 1:
            agg[st]["n1"] += 1
        elif nivel == 2:
            agg[st]["n2"] += 1
        else:
            agg[st]["falha"] += 1
            falhas.append({"nome": p["nome"], "email": em, "status": st,
                           "tipo": "ambiguo" if cands else "ausente",
                           "candidatos": [
                               {"displayName": c.get("displayName"),
                                "emailAddress": c.get("emailAddress"),
                                "accountId": c.get("accountId")} for c in cands]})
        if i % 50 == 0:
            ok = sum(x["n1"] + x["n2"] for x in agg.values())
            fa = sum(x["falha"] for x in agg.values())
            print(f"   {i}/{len(pessoas)}  ok={ok} falha={fa} "
                  f"({100 * ok / max(ok + fa, 1):.1f}%)  "
                  f"{time.time() - t0:.0f}s", flush=True)
            with open(a.saida, "w", encoding="utf-8") as f:
                json.dump({"parcial": True, "processados": i, "agg": agg,
                           "falhas": falhas}, f, ensure_ascii=False, indent=2)

    print(f"\n{'STATUS':12} {'n':>5} {'niv1':>6} {'niv2':>6} {'ok':>6} "
          f"{'falha':>6} {'%':>7}")
    print("-" * 52)
    tn = t1 = t2 = tf = 0
    for st in ("DIVERGENTE", "EM_ANALISE", "SEM_ACESSO", "OK"):
        x = agg[st]
        if not x["n"]:
            continue
        ok = x["n1"] + x["n2"]
        tn += x["n"]; t1 += x["n1"]; t2 += x["n2"]; tf += x["falha"]
        print(f"{st:12} {x['n']:5} {x['n1']:6} {x['n2']:6} {ok:6} "
              f"{x['falha']:6} {100 * ok / x['n']:6.1f}%")
    print("-" * 52)
    print(f"{'TOTAL':12} {tn:5} {t1:6} {t2:6} {t1 + t2:6} {tf:6} "
          f"{100 * (t1 + t2) / max(tn, 1):6.1f}%")
    print(f"\nerros de rede: {erros}")

    ambig = sum(1 for f in falhas if f["tipo"] == "ambiguo")
    print(f"falhas: {ambig} ambiguas (pessoa tem 2+ contas) / "
          f"{len(falhas) - ambig} ausentes (nenhuma conta)")

    with open(a.saida, "w", encoding="utf-8") as f:
        json.dump({"parcial": False, "agg": agg, "falhas": falhas},
                  f, ensure_ascii=False, indent=2)
    print(f">> salvo em {a.saida}")


if __name__ == "__main__":
    main()
