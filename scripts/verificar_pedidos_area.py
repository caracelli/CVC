# -*- coding: utf-8 -*-
"""Verificacao ponta a ponta dos pedidos da area — contra o painel VIVO.

POR QUE ISTO EXISTE, se ja' ha 867 testes: a suite prova que o CODIGO faz o que
foi escrito. Isto prova outra coisa — que o PEDIDO da area chegou ao dado real e
a tela real. Sao perguntas diferentes, e o projeto ja' se queimou confundindo as
duas: em 26/08/2026 um teste passava chamando uma funcao MORTA, e o aviso que
ele "provava" nunca apareceu para a usuaria.

Cada item cita a FONTE (qual retorno, que data) e passa/falha com NUMERO medido.

COMO RODAR
    # 1. suba um painel apontando para a instalacao a conferir (porta 8800)
    # 2. so' o dado (rapido, sem browser):
    python scripts/verificar_pedidos_area.py --db <caminho do .db>
    # 3. dado + tela (precisa de playwright e do Edge instalados):
    python scripts/verificar_pedidos_area.py --db <caminho> --tela

DUAS ARMADILHAS QUE CUSTARAM TEMPO EM 28/08/2026
  * **Dois paineis na mesma porta.** Um servidor velho respondia e os totais da
    API nao batiam com `select count(*) from bi_divergencias`; ~20 min perdidos
    achando que o dado nao chegava a tela. Antes de medir:
        Get-NetTCPConnection -LocalPort 8800 -State Listen
  * **Escolher "o primeiro usuario que aparecer".** Para conferir o icone de
    motivo isso da FALSO NEGATIVO: o usuario de mais acessos pode nao ter
    motivo nenhum. Selecione pelo que quer provar — ver `verificar_tela`.
"""
import argparse
import collections
import io
import json
import os
import sqlite3
import sys
import urllib.request
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

RAIZ = Path(__file__).resolve().parent.parent
PADRAO_DB = RAIZ / "CVC_IAM_ANALYTICS" / "DADOS" / "BANCO" / "iam_analytics.db"
BASE_URL = "http://127.0.0.1:8800"
ABAS = ["consulta", "incl", "conf", "deslig", "transf", "hist", "quar", "vg"]

R = []


def check(fonte, item, ok, evid):
    """Registra um item. `evid` e' a PROVA — numero medido, nunca a palavra 'ok'."""
    R.append((fonte, item, bool(ok), evid))


def _api():
    return json.loads(urllib.request.urlopen(BASE_URL + "/api/dados", timeout=300).read())


# --------------------------------------------------------------------- DADO
def verificar_dado(db_path):
    api = _api()
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    u1 = lambda s: c.execute(s).fetchone()[0]
    divs = [d for u in api["users"] for d in u.get("divs", [])]

    # ---- 1o retorno (29/07/2026) ----
    n_sa = u1("SELECT COUNT(*) FROM bi_divergencias WHERE tipo='SEM_ACESSO'")
    check("1o 29/07", "'sem acesso' e' informativo, nao pendencia",
          n_sa > 0, f"{n_sa} linhas SEM_ACESSO fora da contagem de pendencias")

    acoes = sorted({d.get("a") for d in divs if d.get("a")})
    check("1o 29/07", "Consulta dividida por categoria",
          {"Aderente", "Incluir Acesso", "Em Análise"} <= set(acoes),
          f"acoes: {acoes}")

    comg = sum(1 for u in api["users"] if (u.get("gestor") or "").strip())
    check("1o 29/07", "coluna nome do GESTOR",
          comg > 0, f"{comg} de {len(api['users'])} usuarios com gestor")

    vincs = collections.Counter(u.get("vinc") or "(vazio)" for u in api["users"])
    check("1o 29/07", "terceiros/franqueados/prestadores identificados",
          len([k for k in vincs if k not in ("(vazio)", "Funcionário")]) >= 2,
          f"{dict(vincs)}")

    # ---- 2o retorno (10/08/2026) ----
    # A queixa foi "na consulta, se e a mesma pessoa por que tras separado".
    # Contar CPF repetido em rh_ativos e' a coisa ERRADA: os casos que existem
    # la' sao a MESMA pessoa com DUAS identidades de AD (FRANQ-x + FRANQ-y),
    # dado de origem legitimo. O que ela ve e' a CONSULTA.
    pc = collections.Counter((u.get("cpf") or "").strip()
                             for u in api["users"] if (u.get("cpf") or "").strip())
    dup_tela = sum(1 for v in pc.values() if v > 1)
    dup_base = u1("""SELECT COUNT(*) FROM (SELECT cpf FROM rh_ativos
                     WHERE COALESCE(cpf,'')<>'' GROUP BY cpf HAVING COUNT(*)>1)""")
    check("2o 10/08", "mesma pessoa NAO aparece 2x na Consulta",
          dup_tela == 0,
          f"{dup_tela} CPFs em mais de uma linha ({dup_base} tem 2 identidades "
          f"de AD na base, e o painel as une)")

    mudas = u1("""SELECT COUNT(*) FROM bi_divergencias
                  WHERE acao='Em Análise' AND TRIM(perfil_encontrado)=TRIM(perfil_esperado)
                    AND COALESCE(motivo,'')=''""")
    check("2o 10/08", "'Em Analise' com esperado==encontrado tem explicacao",
          mudas == 0, f"{mudas} linhas iguais e mudas (era o bug)")

    ccs = sum(1 for u in api["users"] if (u.get("cc") or "").strip())
    check("2o 10/08", "numero do centro de custo na tela",
          ccs > 0, f"{ccs} usuarios com CC")

    # ---- 3o retorno (25/08/2026) ----
    bloq = u1("SELECT COUNT(*) FROM bi_divergencias WHERE motivo LIKE 'A pessoa JA TEM conta%'")
    check("3o 25/08", "acesso existente vindo como 'sem acesso'",
          bloq > 0, f"{bloq} linhas explicadas por conta BLOQUEADA/INATIVA")

    check("3o 25/08", "alerta de sistema sem extrato (o caso SIGOT)",
          isinstance(api.get("sem_extrato"), list),
          f"sem_extrato = {api.get('sem_extrato') or '(nenhum)'}")

    sis = sorted({d["sis"] for d in divs if d.get("sis")})
    check("3o 25/08", "SIGOT presente (nao carregava)", "SIGOT" in sis, f"{sis}")

    # ---- 4o doc (SIG por nome, nao codigo) ----
    cod = u1("""SELECT COUNT(*) FROM bi_divergencias WHERE sistema='SIG'
                AND (perfil_encontrado GLOB '[0-9]*' OR perfil_esperado GLOB '[0-9]*')""")
    check("4o doc", "SIG mostra NOME do perfil, nao codigo cru",
          cod == 0, f"{cod} linhas do SIG com codigo numerico")

    # ---- Teams 28/08 ----
    exc = u1("SELECT COUNT(*) FROM bi_divergencias WHERE motivo LIKE 'A pessoa TEM o perfil%'")
    check("28/08", "perfil EXCESSIVO deixa de sumir",
          exc > 0, f"{exc} casos marcados")

    check("28/08", "token de mudanca chega ao cliente",
          "token" in api, f"{str(api.get('token'))[:40]}...")
    c.close()


# --------------------------------------------------------------------- TELA
def verificar_tela():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge")
        # 1366x768 = notebook comum. Se quebrar aqui, quebra na maquina dela.
        pg = b.new_page(viewport={"width": 1366, "height": 768})
        traf = {"dados": [0, 0], "versao": [0, 0]}

        def on_resp(r):
            for k in traf:
                if f"/api/{k}" in r.url:
                    traf[k][0] += 1
                    try:
                        traf[k][1] += len(r.body())
                    except Exception:
                        pass

        pg.on("response", on_resp)
        pg.goto(BASE_URL + "/", wait_until="domcontentloaded", timeout=180000)
        pg.wait_for_selector(".kpi-lbl", timeout=90000)
        pg.wait_for_timeout(6000)

        r = pg.evaluate("""() => {
          const tabs=[...document.querySelectorAll('.tab')];
          const tops=new Set(tabs.map(t=>Math.round(t.getBoundingClientRect().top)));
          return {n:tabs.length, linhas:tops.size};
        }""")
        check("27/08 Teams", "abas nao encavalam em 1366px",
              r["linhas"] == 1, f"{r['n']} abas em {r['linhas']} linha(s)")

        # O drawer vive dentro de .page — sem trocar de pagina, tudo mede 0.
        pg.evaluate("() => showPage('consulta')")
        pg.wait_for_timeout(2500)
        pg.evaluate("""() => {
          const u=(DB.users||[]).slice().sort((a,b)=>(b.divs||[]).length-(a.divs||[]).length)[0];
          csAbrirDrawer(u.u,'acessos');
        }""")
        pg.wait_for_timeout(2000)

        r = pg.evaluate("""() => {
          const bd=document.querySelector('#cs-drawer .cs-drawer-bd');
          const xs=[...bd.querySelectorAll('.cs-acc-v, .cs-sub-acc-v')]
                    .map(v=>Math.round(v.getBoundingClientRect().left));
          return {n:xs.length, distintos:[...new Set(xs)].length,
                  amp: xs.length?Math.max(...xs)-Math.min(...xs):-1};
        }""")
        check("28/08 Teams", "'coisas soltas' -> valores alinhados",
              r["distintos"] == 1 and r["amp"] == 0,
              f"{r['n']} linhas, amplitude {r['amp']}px (era 600)")

        r = pg.evaluate("""() => {
          const bd=document.querySelector('#cs-drawer .cs-drawer-bd');
          const o=[...bd.querySelectorAll('span[title]')].filter(s=>/outros/.test(s.textContent));
          return {alt:Math.round(bd.scrollHeight), n:o.length,
                  ex:o.length?o[0].textContent.trim():'-',
                  guardou:o.length?o[0].title.length:0};
        }""")
        check("28/08 Teams", "muita informacao -> teto por sistema",
              r["n"] > 0 and r["guardou"] > 0,
              f"drawer {r['alt']}px, '{r['ex']}', {r['guardou']} chars no title")

        r = pg.evaluate("""() => {
          const bd=document.querySelector('#cs-drawer .cs-drawer-bd');
          return /Sem mapeamento/.test(bd.innerText);
        }""")
        check("2o 10/08", "'por que ela nao tem o IC?' respondido",
              r, f"bloco 'Sem mapeamento' presente: {r}")

        r = pg.evaluate("""() => {
          const u=(DB.users||[]).slice().sort((a,b)=>(b.divs||[]).length-(a.divs||[]).length)[0];
          const h=_csMontarSub(u);
          return {resumo:/cs-sub-resumo/.test(h),
                  leva:/csAbrirDrawer/.test(h),
                  duplica:/_csDetalheCategorias/.test(_csMontarSub.toString())};
        }""")
        check("28/08 Teams", "detalhe mora em UM lugar (resumo -> drawer)",
              r["resumo"] and r["leva"] and not r["duplica"],
              f"resumo={r['resumo']} leva={r['leva']} duplica={r['duplica']}")

        # Escolhe um usuario POR TIPO de motivo. Pegar "o primeiro" daria falso
        # negativo — o de mais acessos pode nao ter motivo nenhum.
        for nome, marca in (("excesso", "alem dele outros"),
                            ("bloqueada", "JA TEM conta"),
                            ("indefinida", "status pendente")):
            uid = pg.evaluate("""(m) => {
              const u=(DB.users||[]).find(x=>(x.divs||[]).some(d=>(d.mot||'').includes(m)));
              return u?u.u:null;
            }""", marca)
            if uid is None:
                check("25-28/08", f"'?' do motivo — {nome}", True, "nenhum caso no dado")
                continue
            pg.evaluate("(u)=>csAbrirDrawer(u,'acessos')", uid)
            pg.wait_for_timeout(1600)
            n = pg.evaluate("() => document.querySelectorAll("
                            "'#cs-drawer .cs-drawer-bd .mot-info').length")
            check("25-28/08", f"'?' do motivo aparece — {nome}",
                  n > 0, f"user {uid}: {n} icone(s)")

        base = [traf["dados"][0], traf["dados"][1], traf["versao"][0], traf["versao"][1]]
        vazias = []
        for aba in ABAS:
            pg.evaluate("(a)=>showPage(a)", aba)
            # 2,5s e' o piso: a aba Desligados busca `/api/desligados`, que sao
            # 7,28 MB e ~0,6s no servidor, e so' enche por volta de 2s. Com
            # 1,1s ela media 0 linhas e o relatorio acusava falha que nao
            # existia. Se subir o payload, subir esta espera junto.
            pg.wait_for_timeout(2500)
            n = pg.evaluate("(a)=>{const p=document.getElementById('pg-'+a);"
                            "return p?p.querySelectorAll('tbody tr').length:-1}", aba)
            if n == 0:
                vazias.append(aba)
        mb = (traf["dados"][1] - base[1]) / 1048576
        check("28/08 Teams", "travamento: nao rebaixa tudo a cada aba",
              mb < 20,
              f"volta pelas 8 abas: {traf['dados'][0]-base[0]}x /api/dados = {mb:.2f} MB "
              f"(+{traf['versao'][0]-base[2]} token = "
              f"{(traf['versao'][1]-base[3])/1024:.2f} KB). Antes: 38,35 MB")
        check("28/08 Teams", "toda aba renderiza conteudo",
              not vazias, f"abas vazias: {vazias or 'nenhuma'}")
        b.close()


def relatorio():
    print("=" * 132)
    print("  VERIFICACAO DOS PEDIDOS DA AREA")
    print("=" * 132)
    print(f"{'FONTE':<13} {'ITEM':<54} {'':6} EVIDENCIA")
    print("-" * 132)
    ok = 0
    for fonte, item, passou, evid in R:
        ok += passou
        print(f"{fonte:<13} {item:<54} {'OK ' if passou else 'FALHA':6} {evid}")
    print("-" * 132)
    print(f"  {ok}/{len(R)} verificados")
    return ok == len(R)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(PADRAO_DB))
    ap.add_argument("--tela", action="store_true",
                    help="inclui a verificacao visual (playwright + Edge)")
    a = ap.parse_args()
    if not os.path.exists(a.db):
        print(f"FALHA: banco nao encontrado: {a.db}")
        return 2
    try:
        urllib.request.urlopen(BASE_URL + "/api/ping", timeout=10)
    except Exception:
        print(f"FALHA: nenhum painel em {BASE_URL} — suba o visualizador antes.")
        return 2
    verificar_dado(a.db)
    if a.tela:
        try:
            verificar_tela()
        except ImportError:
            print("  (parte visual pulada: playwright nao instalado)")
    return 0 if relatorio() else 1


if __name__ == "__main__":
    raise SystemExit(main())
