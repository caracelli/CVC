"""Valida uma credencial do Jira contra o portal 9 / tipo 8819 (Cards 25-26).

Somente GET — nao cria chamado, nao altera nada.

Responde, em ordem:
  1. o token autentica?
  2. da' para ler os metadados do formulario?
  3. o user-search do portal (o que resolve o accountId) aceita este token?
  4. a API publica de busca continua barrada? (controle — deve dar 403)

Usa `urllib` da stdlib de proposito: e' a mesma biblioteca que o Visualizador
usara, entao o que passa aqui passa la.

CREDENCIAL — nunca versionada. Ordem de busca:
  1. variaveis de ambiente JIRA_USER e JIRA_TOKEN
  2. arquivo apontado por JIRA_CRED
  3. .jira_cred na raiz do repositorio (esta no .gitignore)
O arquivo tem duas linhas: e-mail na primeira, token na segunda.

Uso:
    python scripts/jira/testar_credencial.py
"""
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

HOST = "https://cvccorp.atlassian.net"
PORTAL = 9
REQUEST_TYPE = 8819
FIELD_CONFIG_ID = 11659          # amarrado ao customfield_11358 no portal 9
CAMPO_USUARIO = "customfield_11358"

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def ler_credencial():
    u, t = os.environ.get("JIRA_USER"), os.environ.get("JIRA_TOKEN")
    if u and t:
        return u, t, "variaveis de ambiente"
    caminho = os.environ.get("JIRA_CRED") or os.path.join(RAIZ, ".jira_cred")
    if not os.path.exists(caminho):
        sys.exit(f"[X] sem credencial. Defina JIRA_USER/JIRA_TOKEN ou crie "
                 f"{caminho} com o e-mail na 1a linha e o token na 2a.")
    linhas = [x.strip() for x in
              open(caminho, encoding="utf-8").read().splitlines() if x.strip()]
    if len(linhas) < 2:
        sys.exit(f"[X] {caminho} precisa de 2 linhas: e-mail e token.")
    return linhas[0], linhas[1], caminho


EMAIL, TOKEN, ORIGEM = ler_credencial()
AUTH = base64.b64encode(f"{EMAIL}:{TOKEN}".encode()).decode()


def get(caminho, timeout=30):
    req = urllib.request.Request(
        HOST + caminho,
        headers={"Authorization": f"Basic {AUTH}", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:400]
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def buscar_usuario(termo):
    """A consulta que resolve o accountId. Endpoint INTERNO do portal
    (/rest/servicedesk/1/customer/...): nao e' documentado e pode mudar sem
    aviso. E' o unico caminho viavel — a API publica exige 'Browse users and
    groups', que uma conta cliente do JSM nao tem."""
    q = urllib.parse.urlencode({"fieldConfigId": FIELD_CONFIG_ID,
                                "fieldName": CAMPO_USUARIO, "query": termo})
    return get(f"/rest/servicedesk/1/customer/portal/{PORTAL}/user-search?{q}")


def main():
    print(f">> conta : {EMAIL}")
    print(f">> origem: {ORIGEM}\n")

    print("[1] autenticacao — GET /rest/api/3/myself")
    st, body = get("/rest/api/3/myself")
    print(f"    status={st}")
    if st != 200:
        print(f"    {body[:200]}")
        sys.exit("[X] o token nao autenticou; os demais testes nao valem.")
    m = json.loads(body)
    print(f"    {m.get('displayName')} | {m.get('emailAddress')} "
          f"| tipo={m.get('accountType')}")
    if m.get("accountType") != "customer":
        print("    NOTA: conta de servico definitiva sera 'customer'. O "
              "user-search e' endpoint do portal do cliente e deve valer "
              "igual, mas confirme com a credencial final.")

    print(f"\n[2] metadados — requesttype/{REQUEST_TYPE}/field")
    st, body = get(f"/rest/servicedeskapi/servicedesk/{PORTAL}"
                   f"/requesttype/{REQUEST_TYPE}/field")
    print(f"    status={st}")
    if st == 200:
        d = json.loads(body)
        print(f"    canRaiseOnBehalfOf={d.get('canRaiseOnBehalfOf')}")
        for c in d.get("requestTypeFields", []):
            js = c.get("jiraSchema", {})
            print(f"      - {c['fieldId']:22} obrigatorio={str(c.get('required')):5} "
                  f"tipo={js.get('type')}")
    else:
        print(f"    {body[:200]}")

    print("\n[3] user-search do portal aceita este token?")
    for termo in (EMAIL, "naoexiste_zzz99"):
        st, body = buscar_usuario(termo)
        if st == 200:
            try:
                achados = json.loads(body)
                resumo = (", ".join(f"{a.get('displayName')} "
                                    f"<{a.get('emailAddress')}> {a.get('accountId')}"
                                    for a in achados[:2])
                          if achados else "0 (nenhum) — array vazio, sem erro")
            except Exception:
                resumo = f"corpo nao-JSON: {body[:120]}"
        else:
            resumo = body[:160]
        print(f"    {termo:34} status={st} {resumo}")

    print("\n[4] controle — a API publica deve continuar 403")
    st, _ = get("/rest/api/3/user/search?query=" + urllib.parse.quote(EMAIL))
    print(f"    /rest/api/3/user/search -> status={st}"
          + ("  (esperado)" if st == 403 else "  (INESPERADO — reavaliar)"))

    print("\n[5] chamado de teste")
    payload = _payload_teste()
    if "--criar-chamado" not in sys.argv:
        print("    (nao enviado — rode com --criar-chamado para abrir de verdade)")
        print("    Seria enviado:\n")
        for k, v in payload["requestFieldValues"].items():
            print(f"    {k}:")
            for linha in str(v).splitlines() or [""]:
                print(f"      {linha}")
            print()
        return
    _criar_chamado(payload)


def _payload_teste():
    """Payload com o FORMATO exato que o painel monta, mas com dados FALSOS.

    Nada de login ou perfil real aqui. O request type se chama "Catalogo para
    API de Revogacao Automatica de GA": se houver automacao consumindo esses
    chamados, um teste com dados reais dispararia uma revogacao de verdade —
    e cancelar o chamado depois nao desfaz o que ja foi executado. Com
    TESTE000000 nao ha o que revogar; a automacao, se existir, falha sem causar
    dano, e a propria falha vira informacao.

    Duas linhas na tabela de proposito: e' o que responde se ela renderiza.
    """
    titulo = "Sanitização - SYSTUR - TESTE INTEGRACAO IAM"
    descricao = "\n".join([
        "Prezados,", "Revogar o usuario abaixo:", "",
        "NOME | LOGIN | PERFIL",
        "TESTE INTEGRACAO IAM | TESTE000000 | PERFIL_TESTE_A",
        "TESTE INTEGRACAO IAM | TESTE000000 | PERFIL_TESTE_B",
        "", "Desligamento: 01/01/2000",
        "", "Parecer do analista:",
        "TESTE DE INTEGRACAO — validando o formato da descricao. NAO HA USUARIO "
        "REAL neste chamado; nenhum acesso deve ser revogado. Pode ser cancelado.",
    ])
    return {"serviceDeskId": str(PORTAL), "requestTypeId": str(REQUEST_TYPE),
            "requestFieldValues": {"summary": titulo, "description": descricao,
                                   "customfield_11936": "Revogação de acessos"}}


def _criar_chamado(payload):
    """POST real. So roda com --criar-chamado explicito."""
    req = urllib.request.Request(
        HOST + "/rest/servicedeskapi/request",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Basic {AUTH}",
                 "Content-Type": "application/json",
                 "Accept": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        print(f"    FALHOU {e.code}: {e.read().decode('utf-8','replace')[:400]}")
        return
    except Exception as e:
        print(f"    FALHOU: {type(e).__name__}: {e}")
        return
    print(f"    CRIADO: {d.get('issueKey')}")
    print(f"    link  : {(d.get('_links') or {}).get('web')}")
    print("    Abra o link e confira se a TABELA da descricao renderizou "
          "alinhada ou virou texto corrido.")


if __name__ == "__main__":
    main()
