# -*- coding: utf-8 -*-
"""
Visualizador CVC IAM — servidor local que torna o index.html FUNCIONAL e
IGUALZINHO ao BI, lendo direto do SQLite (sem Parquet), por queries.

Conceito (validado por numeros == Parquet do BI, 6963 linhas):
  - bi_divergencias  = TABELA ESTATICA (snapshot do cenario do BI)
        Fonte 1: validacao_acessos (tipo = status, acao = label)
        Fonte 2: divergencias onde tipo = ACESSO_SEM_VINCULO_RH (acao = 'Usuário Não Encontrado')
        Reproduz src/aplicacao/casos_de_uso/gerar_saidas.py
  - quarentena       = TABELA GRAVAVEL (acao write-back)
  - Le bi_divergencias (+ LEFT JOIN rh_ativos = LOOKUPVALUE do BI)
  - Injeta os dados vivos no `const DB = {...}` do index.html (HTML intacto)
  - Mesmo modelo do POC (validado na maquina do cliente): config.xml,
    auto-encerrar, sem terminal, log. SQLite em WAL + read-only p/ leitura.

config.xml (ao lado do exe):
  <config>
    <banco caminho="..\\DADOS\\BANCO\\iam_analytics.db" />
    <sistema valor="SYSTUR" />          <!-- escopo dos KPIs/usuarios; vazio=todos -->
    <quarentena duracao_dias="30" />
  </config>
"""
import sys, os, io, json, time, socket, sqlite3, threading, webbrowser, getpass, zipfile
import base64
import subprocess
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST, PORT = "127.0.0.1", 8800

# Este exe (launcher_visualizador.exe) mora em EXECUTAVEIS\launcher\.
# BASE_EXE = pasta do exe; BASE_APP = pai dela (EXECUTAVEIS\).
# CONFIG, REPORT e DADOS sao referenciados a partir de BASE_APP.
if getattr(sys, "frozen", False):
    BASE_EXE = os.path.dirname(sys.executable)
else:
    BASE_EXE = os.path.dirname(os.path.abspath(__file__))
BASE_APP = os.path.dirname(BASE_EXE)          # EXECUTAVEIS\
RAIZ_APP = os.path.dirname(BASE_APP)          # CVC_IAM_ANALYTICS\
REPORT_DIR = os.path.join(BASE_APP, "REPORT")
DADOS_DIR = os.path.join(BASE_APP, "DADOS")
BANCO_LOCAL = os.path.join(DADOS_DIR, "BANCO", "iam_analytics.db")
LOG_PATH = os.path.join(DADOS_DIR, "LOGS", "visualizador.log")
INDEX_PATH = os.path.join(REPORT_DIR, "index.html")
CONFIG_PATH = os.path.join(BASE_APP, "CONFIG", "config.xml")
# Jira: arquivo PROPRIO (CONFIG/jira.xml), preenchido pela infra e NAO
# versionado — carrega o token. O caminho e' resolvido em tempo de execucao
# por _jira_xml_path(), que prefere a REDE ao local.
JIRA_XML_LOCAL = os.path.join(BASE_APP, "CONFIG", "jira.xml")
# Alias historico — algumas funcoes mais abaixo ainda usam BASE.
BASE = BASE_APP

# Garante a estrutura DADOS\LOGS\ e DADOS\BANCO\ antes de qualquer escrita
for _p in (os.path.dirname(LOG_PATH), os.path.dirname(BANCO_LOCAL)):
    try:
        os.makedirs(_p, exist_ok=True)
    except Exception:
        pass


class _Tee:
    # Warnings cosmeticos do bootloader PyInstaller --onefile, emitidos no
    # exit do processo. Acontecem quando o Windows ainda tem DLLs do _MEI
    # temporario mapeadas; nao afeta funcionalidade alguma (o Windows limpa
    # o temp sozinho depois). Filtramos pra nao confundir o usuario.
    _FILTROS_BOOTLOADER = (
        "Failed to remove temporary directory",
        "Failed to remove old temporary directory",
    )

    def __init__(self, p):
        self._f = open(p, "a", encoding="utf-8", errors="replace")
        self._o = sys.__stdout__

    def _filtrar(self, s):
        return any(f in s for f in self._FILTROS_BOOTLOADER)

    def write(self, s):
        if self._filtrar(s):
            return
        try: self._f.write(s); self._f.flush()
        except Exception: pass
        if self._o:
            try: self._o.write(s); self._o.flush()
            except Exception: pass

    def flush(self):
        try: self._f.flush()
        except Exception: pass


try:
    _t = _Tee(LOG_PATH); sys.stdout = _t; sys.stderr = _t
except Exception:
    pass

USUARIO = getpass.getuser()
MAQUINA = socket.gethostname()

TIPO_LABEL = {
    "SEM_ACESSO": "Sem Acesso", "DIVERGENTE": "Divergente",
    "EM_ANALISE": "Em Análise", "ACESSO_SEM_VINCULO_RH": "Sem Vínculo RH",
    "ACESSO_DESLIGADO": "Acesso Desligado", "PERFIL_INVALIDO": "Perfil Inválido",
    "OK": "Aderente",
}

# tipo_vinculo (rh_ativos) -> rótulo da coluna "Categoria" no painel.
# FUNCIONARIO = CLT; TERCEIRO = prestador de fornecedor (base de terceiros do
# RH); FRANQUEADO/PRESTADOR = identidades do diretório (AD), que existem para
# dar dono aos acessos órfãos. Default FUNCIONARIO cobre banco antigo (coluna
# ausente) — por isso o mapa tem fallback em vez de KeyError.
VINCULO_LABEL = {
    "FUNCIONARIO": "Funcionário", "TERCEIRO": "Terceiro",
    "FRANQUEADO": "Franqueado", "PRESTADOR": "Prestador",
}
VINCULO_PADRAO = "Funcionário"


def rotulo_vinculo(tv) -> str:
    """Rótulo de categoria a partir do tipo_vinculo cru. Valor desconhecido cai
    no padrão (nunca quebra a grid por causa de um vínculo novo no RH)."""
    return VINCULO_LABEL.get((tv or "").strip().upper(), VINCULO_PADRAO)


# origem_matriz -> rótulo da coluna "Origem"
# MATRIZ = matrizes de perfis dos sistemas; CCO = matriz CCO; vazio = nenhuma
ORIGEM_LABEL = {"MATRIZ": "Sistema", "CCO": "Base CCO"}

SRV = None
_last_seen = time.time()
_armed = False
_OCIOSO = 300   # watchdog tolerante: aba em 2o plano (heartbeat estrangulado) nao mata o servidor
_enc_em = None  # timestamp de um encerramento agendado (None = nenhum pendente)
_GRACE = 5      # carencia: F5/Ctrl+F5 recarrega e re-arma a aba dentro desse prazo
_sessao = None  # id da aba ativa; um beacon de encerrar so vale vindo dela
_BASE = None   # cache da parte cara do DB (bi_divergencias + JOIN); 1x por execução
_SEM_BANCO = False   # True quando o banco da rede ainda nao existe (mostra aviso)

# Pagina mostrada quando o banco ainda nao foi gerado (em vez de travar
# "importando"). O visualizador NAO roda o Processador — quem roda e' o
# responsavel, manualmente. O ping mantem o watchdog coerente (cai ao fechar).
_PAGINA_SEM_BANCO = """<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">
<title>CVC IAM — Banco nao gerado</title><style>
*{box-sizing:border-box}
body{font-family:-apple-system,"Segoe UI",Arial,sans-serif;margin:0;min-height:100vh;
  display:flex;align-items:center;justify-content:center;
  background:linear-gradient(180deg,#f5f6fa,#e7ebf2)}
.card{background:#fff;border-radius:14px;padding:40px 48px;max-width:520px;text-align:center;
  box-shadow:0 8px 28px rgba(31,45,92,.12)}
.brand{color:#1F2D5C;font:700 11.5px Arial;letter-spacing:.1em;margin-bottom:8px}
h1{color:#1F2D5C;margin:0 0 12px;font:700 21px Arial}
p{color:#3A3F4C;font:400 14px/1.6 Arial;margin:6px 0}
.b{color:#1F2D5C;font-weight:700}
</style></head><body>
<div class="card">
  <div class="brand">CVC IAM ANALYTICS</div>
  <h1>Banco ainda nao gerado</h1>
  <p>Ainda nao ha dados processados na rede.</p>
  <p><span class="b">Pe&ccedil;a para o respons&aacute;vel rodar o Processador</span> &mdash;
     ele gera o banco. Depois, feche e abra este painel novamente.</p>
</div>
<script>setInterval(()=>{fetch('/api/ping?s=semb').catch(()=>{})},4000);</script>
</body></html>"""


def _enc(motivo):
    print(f"  [ENCERRANDO] {motivo}")
    if SRV is not None:
        threading.Thread(target=SRV.shutdown, daemon=True).start()


def agendar_encerramento(sessao, motivo):
    """Agenda o encerramento p/ daqui a _GRACE s, em vez de matar na hora.
    Um F5/Ctrl+F5 recarrega a aba: a pagina nova manda /api/ping e cancela
    este pedido. Beacon atrasado de uma aba ja substituida e ignorado."""
    global _enc_em
    if _sessao is not None and sessao and sessao != _sessao:
        print("  [encerrar ignorado] beacon de sessao antiga (F5)")
        return
    _enc_em = time.time()
    print(f"  [encerrar agendado +{_GRACE}s] {motivo}")


def _watchdog():
    while True:
        time.sleep(1)
        if _enc_em is not None and (time.time() - _enc_em) > _GRACE:
            _enc("aba fechada (sem retorno apos carencia)")
            return
        if _armed and (time.time() - _last_seen) > _OCIOSO:
            _enc(f"aba inativa (sem heartbeat >{_OCIOSO}s)")
            return


def carregar_config():
    """Le o config unificado (EXECUTAVEIS\\CONFIG\\config.xml).
    Devolve (rede_raiz, banco_sub, sistema, quarentena_dias, origem)."""
    rede_raiz = ""
    banco_sub = os.path.join("DADOS", "BANCO", "iam_analytics.db")
    sistema = "SYSTUR"
    duracao = 90
    meta_desl = None   # meta (KRI) de desligados com acesso; None = sem selo
    origem = "padrao"
    if os.path.exists(CONFIG_PATH):
        try:
            root = ET.parse(CONFIG_PATH).getroot()
            rede_raiz = (root.findtext("rede/raiz") or "").strip()
            v = (root.findtext("rede/banco_dados") or "").strip()
            if v:
                banco_sub = v
            # <sistema> presente mas VAZIO = todos os sistemas ativos (filtro
            # desligado). Elemento AUSENTE mantem o default legado "SYSTUR".
            node_s = root.find("visualizador/sistema")
            if node_s is not None:
                sistema = (node_s.text or "").strip()
            q = (root.findtext("visualizador/quarentena_dias") or "").strip()
            if q:
                duracao = int(q)
            # Meta de risco (opcional): limite tolerado de desligados com acesso
            # ativo. Ausente/vazio/invalido = None (KPI sem selo de meta).
            md = (root.findtext("metas/acessos_desligado_meta") or "").strip()
            if md != "":
                try:
                    meta_desl = int(md)
                except ValueError:
                    meta_desl = None
            origem = "config.xml"
        except Exception as e:
            origem = f"config.xml invalido ({e!r}) -> padrao"
    return rede_raiz, banco_sub, sistema, duracao, meta_desl, origem


REDE_RAIZ, BANCO_SUB, SISTEMA, QUAR_DIAS, META_ACESSOS_DESLIG, CONFIG_SRC = carregar_config()


def _jira_xml_path():
    """Caminho do jira.xml. PREFERE A REDE ao local.

    Ler da rede (e nao da copia local que o auto-update traz) e' deliberado: o
    auto-update so copia quando a <versao> muda, entao um token trocado ficaria
    parado na rede ate a proxima release — toda rotacao viraria pedido de
    publicacao. Lendo direto, a infra troca o token e vale para todos os
    analistas na proxima abertura do painel. De quebra, o token nao se replica
    no disco de cada maquina.

    Sem <rede><raiz> (modo local / dev), cai no arquivo ao lado do config.
    """
    if REDE_RAIZ:
        try:
            sub = (ET.parse(CONFIG_PATH).getroot().findtext("rede/executaveis")
                   or "EXECUTAVEIS") if os.path.exists(CONFIG_PATH) else "EXECUTAVEIS"
            rede = os.path.join(REDE_RAIZ, sub, "CONFIG", "jira.xml")
            if os.path.exists(rede):
                return rede, "rede"
        except Exception:
            pass
    if os.path.exists(JIRA_XML_LOCAL):
        return JIRA_XML_LOCAL, "local"
    return None, "ausente"


def carregar_config_jira():
    """Le CONFIG/jira.xml — TODOS os parametros do Jira, inclusive credencial.

    Arquivo proprio, preenchido pela infra, fora do config.xml: aquele e'
    versionado, e um token nele seria commitado. Este esta no .gitignore.
    Modelo em CONFIG/jira.xml.exemplo.
    """
    cfg = {"ativo": False, "url": "", "service_desk_id": "",
           "request_type_id": "", "campo_tipo": "customfield_11936",
           "tipo_solicitacao": "", "prefixo_titulo": "Sanitização",
           "timeout_s": 30, "usuario": "", "token": "", "origem": "ausente"}
    caminho, origem = _jira_xml_path()
    cfg["origem"] = origem
    if not caminho:
        return cfg
    try:
        r = ET.parse(caminho).getroot()
        for k in ("url", "service_desk_id", "request_type_id", "campo_tipo",
                  "tipo_solicitacao", "prefixo_titulo", "usuario", "token"):
            v = (r.findtext(k) or "").strip()
            if v:
                cfg[k] = v
        cfg["ativo"] = (r.findtext("ativo", "false") or "").strip().lower() == "true"
        t = (r.findtext("timeout_s") or "").strip()
        if t.isdigit():
            cfg["timeout_s"] = int(t)
    except Exception as e:
        cfg["origem"] = f"{origem} (invalido: {e!r})"
    return cfg


def jira_diagnostico() -> str:
    """Uma linha dizendo em que pe' esta a integracao. Vai para o log de
    inicializacao: sem tela de teste, um valor errado no jira.xml falharia em
    silencio — este e' o unico ponto em que isso fica visivel."""
    if JIRA["origem"] == "ausente":
        return "Jira     : nao configurado (sem CONFIG/jira.xml)"
    if "invalido" in JIRA["origem"]:
        return f"Jira     : ERRO ao ler jira.xml — {JIRA['origem']}"
    if not JIRA["ativo"]:
        return f"Jira     : desligado (<ativo>false</ativo>, {JIRA['origem']})"
    faltando = [k for k in ("usuario", "token", "url", "service_desk_id",
                            "request_type_id") if not JIRA[k]]
    if faltando:
        return (f"Jira     : INCOMPLETO ({JIRA['origem']}) — falta "
                + ", ".join(faltando))
    return (f"Jira     : ativo ({JIRA['origem']}) — {JIRA['usuario']} "
            f"-> portal {JIRA['service_desk_id']} / tipo {JIRA['request_type_id']}")


JIRA = carregar_config_jira()


def jira_habilitado():
    """So habilita com <ativo>true</ativo> E credencial presente. Sem isso o
    botao do painel fica desabilitado, como esta hoje — botao habilitado que nao
    abre chamado e' armadilha (mesmo principio do _btnJira no index.html)."""
    return bool(JIRA["ativo"] and JIRA["usuario"] and JIRA["token"]
                and JIRA["url"] and JIRA["service_desk_id"]
                and JIRA["request_type_id"])


class JiraErro(Exception):
    """Falha ao abrir chamado. A mensagem vai INTEIRA para a tela: o analista
    precisa saber se pode tentar de novo ou se tem de abrir na mao."""


# Limite do campo Resumo no Jira. Truncar aqui e' melhor do que levar 400 do
# outro lado com o chamado nao criado.
_JIRA_MAX_SUMMARY = 255


def _data_br(valor) -> str:
    """'2025-06-30' / '2025-06-30 00:00:00' -> '30/06/2025'. O chamado e' lido
    por pessoa, nao por maquina. Formato desconhecido volta como veio."""
    s = str(valor or "").strip()[:10]
    try:
        a, m, d = s.split("-")
        return f"{d}/{m}/{a}"
    except ValueError:
        return str(valor or "").strip()


def jira_titulo(sistema: str, nome: str) -> str:
    """'Sanitizacao - SYSTUR - AGATHA DIAS'. Titulo GERADO, nao o motivo: e' o
    que distingue um chamado do outro na fila do Service Desk sem abrir."""
    t = f"{JIRA['prefixo_titulo']} - {sistema or '?'} - {nome or '?'}"
    return t[:_JIRA_MAX_SUMMARY]


def jira_descricao(linhas, contexto: str = "", parecer: str = "") -> str:
    """Corpo do chamado. `linhas` = [(nome, login, perfil), ...] — uma por
    perfil revogado; `contexto` = a linha propria do fluxo ("Desligamento: ..."
    no desligado, "Motivo: ..." na pendencia); `parecer` = o texto do analista.

    TABELA EM TEXTO SEPARADO POR '|': a descricao vai como texto puro e o Jira
    Cloud guarda descricao em ADF, entao markup de tabela provavelmente NAO e'
    interpretado e alinhamento por espaco nao segura em fonte proporcional. O
    separador visivel sobrevive aos dois casos. Confirmar no 1o chamado real.
    """
    corpo = ["Prezados,", "Revogar o usuario abaixo:", "",
             "NOME | LOGIN | PERFIL"]
    for nome, login, perfil in linhas:
        corpo.append(f"{nome or '—'} | {login or '—'} | {perfil or '—'}")
    if contexto:
        corpo += ["", contexto]
    if parecer:
        corpo += ["", "Parecer do analista:", parecer.strip()]
    return "\n".join(corpo)


def jira_abrir_chamado(titulo: str, descricao: str):
    """POST em /rest/servicedeskapi/request. Devolve (ticket, url).

    urllib da stdlib de proposito: o painel e' standalone e o spec nao empacota
    dependencia. A descricao vai como STRING — este endpoint aceita texto puro,
    diferente da API generica de issues, que exigiria montar ADF.

    Levanta JiraErro em qualquer falha. Quem chama TEM de tratar: se o POST
    falhou, nenhum chamado existe; se deu certo mas a gravacao seguinte falhar,
    o numero precisa chegar na tela de qualquer jeito.
    """
    if not jira_habilitado():
        raise JiraErro("Integracao com o Jira desabilitada ou sem credencial "
                       "(ver <jira> no config.xml).")
    payload = {
        "serviceDeskId": str(JIRA["service_desk_id"]),
        "requestTypeId": str(JIRA["request_type_id"]),
        "requestFieldValues": {
            "summary": titulo,
            "description": descricao,
            JIRA["campo_tipo"]: JIRA["tipo_solicitacao"],
        },
    }
    auth = base64.b64encode(
        f"{JIRA['usuario']}:{JIRA['token']}".encode()).decode()
    req = urllib.request.Request(
        JIRA["url"].rstrip("/") + "/rest/servicedeskapi/request",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Basic {auth}",
                 "Content-Type": "application/json",
                 "Accept": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=JIRA["timeout_s"]) as r:
            dados = json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        detalhe = e.read().decode("utf-8", "replace")[:300]
        raise JiraErro(f"Jira respondeu {e.code}: {detalhe}")
    except Exception as e:
        raise JiraErro(f"Falha de rede ao abrir chamado: {type(e).__name__}: {e}")

    ticket = (dados.get("issueKey") or "").strip()
    url = ((dados.get("_links") or {}).get("web") or "").strip()
    if not ticket:
        raise JiraErro("Jira aceitou a requisicao mas nao devolveu o numero do "
                       "chamado. Confira no portal antes de tentar de novo.")
    return ticket, url


# Limite maximo de dias que uma quarentena pode receber no formulario (regra de
# negocio; o front tambem bloqueia). Acima disso, enviar_quarentena rejeita.
QUAR_MAX_DIAS = 90

MOTIVOS_RES_PATH = os.path.join(os.path.dirname(CONFIG_PATH), "motivos_resolucao.xml")


def listar_motivos_resolucao():
    """Motivos do combobox obrigatorio de 'Resolver pendencia', lidos do XML
    em CONFIG/motivos_resolucao.xml (versionado/auto-atualizado com o sistema).
    Ordem do arquivo = ordem no combobox. Fallback minimo se faltar/invalido."""
    try:
        root = ET.parse(MOTIVOS_RES_PATH).getroot()
        motivos = [(m.text or "").strip() for m in root.findall("motivo")]
        motivos = [m for m in motivos if m]
        if motivos:
            return motivos
    except Exception as e:
        print(f"  [motivos] falha lendo {MOTIVOS_RES_PATH}: {e!r}")
    return ["Resolvido", "Outro"]

# Visão Geral: janela movel (dias) dos blocos de FLUXO (Chamados, Movimentação).
# Fixo por enquanto; tornar parametrizavel e' item do docs/ROADMAP_VISAO_GERAL.md.
VG_JANELA_DIAS = 30


def _precisa_sincronizar(rede_db: str, local_db: str) -> bool:
    """True se o cache local esta defasado em relacao ao da rede.

    Heuristica (rapida, sem ler o conteudo do arquivo):
      - sem cache local            -> precisa copiar
      - tamanhos diferentes        -> precisa copiar (o Processador re-escreveu)
      - rede modificada apos cache -> precisa copiar
      - caso contrario             -> cache em dia, pula a copia."""
    if not os.path.exists(local_db):
        return True
    try:
        if os.path.getsize(rede_db) != os.path.getsize(local_db):
            return True
        # Em WAL, escritas recentes do Processador podem estar no .db-wal e
        # ainda nao refletidas no .db (mtime/size do .db nao mudam). Por isso
        # consideramos tambem o mtime do -wal da rede. (O Processador faz
        # checkpoint ao fim, mas isto cobre a janela ate o checkpoint.)
        def _mtime_max(p):
            m = os.path.getmtime(p)
            w = p + "-wal"
            if os.path.exists(w):
                m = max(m, os.path.getmtime(w))
            return m
        return _mtime_max(rede_db) > os.path.getmtime(local_db)
    except OSError:
        return True


def sincronizar_banco():
    """Modo rede: copia o iam_analytics.db da rede para um cache local
    (backup SQLite consistente) so se houver diferenca de tamanho/mtime — caso
    contrario reusa o cache anterior. Le sempre do cache local. Sem
    <rede><raiz>, le o banco local direto, sem copia."""
    raiz = REDE_RAIZ if REDE_RAIZ else RAIZ_APP
    rede_db = (BANCO_SUB if os.path.isabs(BANCO_SUB)
               else os.path.join(raiz, BANCO_SUB))
    rede_db = os.path.abspath(rede_db)
    if not REDE_RAIZ:
        return rede_db                        # modo local: le direto
    local_db = BANCO_LOCAL                    # BASE\DADOS\BANCO\iam_analytics.db
    if os.path.exists(rede_db):
        if not _precisa_sincronizar(rede_db, local_db):
            print(f"  [banco] cache local em dia (rede inalterada): {local_db}")
            return local_db
        try:
            src = sqlite3.connect(f"file:{rede_db}?mode=ro", uri=True, timeout=15)
            dst = sqlite3.connect(local_db, timeout=15)
            with dst:
                src.backup(dst)
            dst.close()
            src.close()
            print(f"  [banco] sincronizado da rede: {rede_db}")
            return local_db
        except Exception as e:
            print(f"  [banco] falha ao sincronizar da rede ({e!r})")
    if os.path.exists(local_db):
        print("  [banco] rede indisponivel — usando copia local anterior")
        return local_db
    print("  [banco] rede indisponivel e sem copia local")
    return local_db


DB_PATH = sincronizar_banco()


# ───────────── Interacoes multiusuario (.jsonl na rede) ─────────────
def caminho_interacoes():
    """Pasta de interacoes: <rede><raiz>/<rede><interacoes> em modo rede;
    RAIZ_APP/<rede><interacoes> em modo local (raiz vazia)."""
    try:
        sub = (ET.parse(CONFIG_PATH).getroot().findtext("rede/interacoes")
               or "INTERACOES").strip()
    except Exception:
        sub = "INTERACOES"
    base = REDE_RAIZ if REDE_RAIZ else RAIZ_APP
    return os.path.join(base, sub)


PASTA_INTERACOES = caminho_interacoes()


def _interacao_arquivo(usuario):
    nome = "".join(ch if (ch.isalnum() or ch in "._-") else "_"
                   for ch in (usuario or "anon"))
    return os.path.join(PASTA_INTERACOES, f"interacao_{nome}.jsonl")


def _interacao_gravar(interacao):
    """Anexa uma interacao (dict) ao .jsonl do USUARIO atual na rede."""
    if not PASTA_INTERACOES:
        raise RuntimeError("pasta de interacoes nao configurada")
    os.makedirs(PASTA_INTERACOES, exist_ok=True)
    with open(_interacao_arquivo(USUARIO), "a", encoding="utf-8") as f:
        f.write(json.dumps(interacao, ensure_ascii=False) + "\n")


def _interacoes_ler():
    """Le todas as interacoes de todos os .jsonl da pasta da rede.
    Tolerante a linha final incompleta (ignora)."""
    todas = []
    if not PASTA_INTERACOES or not os.path.isdir(PASTA_INTERACOES):
        return todas
    for nome in os.listdir(PASTA_INTERACOES):
        if not nome.lower().endswith(".jsonl"):
            continue
        try:
            with open(os.path.join(PASTA_INTERACOES, nome),
                      "r", encoding="utf-8") as f:
                for linha in f:
                    linha = linha.strip()
                    if linha:
                        try:
                            todas.append(json.loads(linha))
                        except Exception:
                            pass
        except Exception:
            pass
    return todas


def _quarentena_viva(interacoes=None):
    """Estado vivo {registro_id: interacao mais recente} do tipo QUARENTENA.
    Aceita uma lista de interacoes ja lida (coalesce: evita reler a pasta da
    rede no mesmo request); se None, le da rede."""
    atual = {}
    for it in (interacoes if interacoes is not None else _interacoes_ler()):
        if it.get("tipo_interacao") != "QUARENTENA":
            continue
        rid = it.get("registro_id")
        if not rid:
            continue
        ant = atual.get(rid)
        if ant is None or str(it.get("data_acao", "")) >= str(ant.get("data_acao", "")):
            atual[rid] = it
    return atual


def _meta_divergencia(rid):
    """(nome_usuario, sistema, matricula) de bi_divergencias para um registro_id."""
    c = conn_ro()
    try:
        row = c.execute(
            "SELECT nome_usuario, sistema, matricula FROM bi_divergencias "
            "WHERE usuario=? LIMIT 1", [rid]).fetchone()
    finally:
        c.close()
    if row:
        return (row["nome_usuario"] or rid, row["sistema"] or "",
                row["matricula"] or "")
    return rid, "", ""


def _resolucao_viva(interacoes=None):
    """Estado vivo {registro_id: interacao} das interacoes RESOLUCAO da rede.
    Aceita interacoes ja lidas (coalesce de leitura no mesmo request)."""
    atual = {}
    for it in (interacoes if interacoes is not None else _interacoes_ler()):
        if it.get("tipo_interacao") != "RESOLUCAO":
            continue
        rid = it.get("registro_id")
        if not rid:
            continue
        ant = atual.get(rid)
        if ant is None or str(it.get("data_acao", "")) >= str(ant.get("data_acao", "")):
            atual[rid] = it
    return atual


def _tratamento_desligado_vivo(interacoes=None):
    """Estado vivo {registro_id: interacao} do tipo TRATAMENTO_DESLIGADO da rede.
    Mesmo padrao da RESOLUCAO: a interacao de data_acao mais recente vence."""
    atual = {}
    for it in (interacoes if interacoes is not None else _interacoes_ler()):
        if it.get("tipo_interacao") != "TRATAMENTO_DESLIGADO":
            continue
        rid = it.get("registro_id")
        if not rid:
            continue
        ant = atual.get(rid)
        if ant is None or str(it.get("data_acao", "")) >= str(ant.get("data_acao", "")):
            atual[rid] = it
    return atual


def chamados_abertos(interacoes=None):
    """{registro_id: {ticket, ticket_url, por, em}} — chamados JA abertos pelo
    painel. Mesmo padrao mesclado dos tratamentos: banco dobrado + interacoes
    vivas da rede.

    LE DE TODOS OS .jsonl DA REDE, nao so' do usuario atual: dois analistas em
    maquinas diferentes podem estar com a mesma linha aberta, e quem abriu o
    chamado pode nao ser quem esta tentando abrir agora. Essa e' justamente a
    duplicata que precisamos impedir.

    O primeiro a abrir VENCE (nao o mais recente, como nos tratamentos): o
    chamado ja existe no Service Desk e nao ha' o que sobrepor.
    """
    out = {}
    # Lado dobrado. LE DA REDE, nao do cache local — e isto importa:
    #
    #   09:00 o painel abre e copia o banco para o cache (sem chamado nenhum)
    #   10:00 outro analista abre um chamado -> vai para o .jsonl da rede
    #   11:00 o Processador dobra no banco e APAGA a pasta de interacoes
    #   11:05 este painel, aberto desde as 09:00, olharia um .jsonl vazio e um
    #         cache velho — nao acharia o chamado e deixaria abrir o duplicado.
    #
    # A tabela e' pequena e a consulta e' pontual; nao justifica ressincronizar
    # o banco inteiro. Sem rede (modo local), cai no proprio DB_PATH.
    banco = _rede_db_path() if REDE_RAIZ else DB_PATH
    try:
        c = sqlite3.connect(f"file:{banco}?mode=ro", uri=True, timeout=10)
        c.row_factory = sqlite3.Row
        try:
            if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                         "AND name='chamados_abertos'").fetchone():
                for r in c.execute("SELECT registro_id,ticket,ticket_url,"
                                   "aberto_por,aberto_em FROM chamados_abertos"):
                    out[str(r["registro_id"])] = {
                        "ticket": r["ticket"] or "",
                        "ticket_url": r["ticket_url"] or "",
                        "por": r["aberto_por"] or "", "em": r["aberto_em"] or ""}
        finally:
            c.close()
    except Exception as e:
        # Nao engolir em silencio: sem esta leitura o painel deixaria abrir
        # chamado duplicado sem avisar ninguem.
        print(f"  [CHAMADO] aviso: nao foi possivel ler chamados_abertos ({e!r})")

    for it in (interacoes if interacoes is not None else _interacoes_ler()):
        if it.get("tipo_interacao") != "CHAMADO_ABERTO":
            continue
        rid = str(it.get("registro_id") or "")
        if not rid or not it.get("ticket"):
            continue
        # Normaliza ANTES de comparar: o envelope traz "2026-08-11T09:00:00" e o
        # que ja esta em `out` usa espaco. Comparar cru contra normalizado
        # inverte a ordem ('T' > ' ' em ASCII) e faria o MAIS RECENTE vencer —
        # o oposto da regra.
        em = (it.get("data_acao") or "").replace("T", " ")
        ant = out.get(rid)
        if ant is None or em < str(ant.get("em", "")):
            out[rid] = {"ticket": it.get("ticket") or "",
                        "ticket_url": it.get("ticket_url") or "",
                        "por": it.get("usuario") or "", "em": em}
    return out


def _tratamentos_desligado_db():
    """Tratamentos de desligado ja dobrados no banco {registro_id: dados}."""
    c = conn_ro()
    try:
        tem = c.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                        "AND name='tratamentos_desligado'").fetchone()
        if not tem:
            return {}
        out = {}
        for r in c.execute(
                "SELECT registro_id,ticket,ticket_url,descricao,motivo,acessos,"
                "cargo,centro_custo,nome,tratado_por,tratado_em "
                "FROM tratamentos_desligado"):
            try:
                acessos = json.loads(r["acessos"]) if r["acessos"] else []
            except Exception:
                acessos = []
            out[r["registro_id"]] = {
                "ticket": r["ticket"] or "", "ticket_url": r["ticket_url"] or "",
                "descricao": r["descricao"] or "", "motivo": r["motivo"] or "",
                "cargo": r["cargo"] or "", "centro_custo": r["centro_custo"] or "",
                "nome": r["nome"] or "",
                "por": r["tratado_por"] or "", "em": r["tratado_em"] or "",
                "acessos": acessos}
        return out
    except Exception:
        return {}
    finally:
        c.close()


def _tratamentos_desligado_mesclados(interacoes=None):
    """{registro_id: dados do tratamento} — banco dobrado + interacoes vivas da
    rede (a viva, mais recente, sobrepoe a dobrada)."""
    out = dict(_tratamentos_desligado_db())
    for rid, it in _tratamento_desligado_vivo(interacoes).items():
        out[str(rid)] = {
            "ticket": it.get("ticket") or "", "ticket_url": it.get("ticket_url") or "",
            "descricao": it.get("descricao") or "", "motivo": it.get("motivo") or "",
            "cargo": it.get("cargo") or "", "centro_custo": it.get("centro_custo") or "",
            "nome": it.get("nome") or "",
            "por": it.get("usuario") or "",
            "em": (it.get("data_acao") or "").replace("T", " "),
            "acessos": it.get("acessos") or []}
    return out


def _resolucoes_db():
    """Resolucoes ja dobradas no banco pelo Processador {registro_id: dados}."""
    c = conn_ro()
    try:
        tem = c.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                        "AND name='resolucoes'").fetchone()
        if not tem:
            return {}
        # base ainda nao dobrada com a coluna motivo -> nao quebra
        cols = {r[1] for r in c.execute("PRAGMA table_info(resolucoes)")}
        col_mot = "motivo" if "motivo" in cols else "'' AS motivo"
        out = {}
        for r in c.execute(
                f"SELECT registro_id,ticket,ticket_url,descricao,{col_mot},pendencias,"
                "cargo,centro_custo,nome,resolvido_por,resolvido_em "
                "FROM resolucoes"):
            try:
                pend = json.loads(r["pendencias"]) if r["pendencias"] else []
            except Exception:
                pend = []
            out[r["registro_id"]] = {
                "ticket": r["ticket"] or "", "ticket_url": r["ticket_url"] or "",
                "descricao": r["descricao"] or "", "motivo": r["motivo"] or "",
                "cargo": r["cargo"] or "", "centro_custo": r["centro_custo"] or "",
                "nome": r["nome"] or "",
                "por": r["resolvido_por"] or "", "em": r["resolvido_em"] or "",
                "pendencias": pend}
        return out
    except Exception:
        return {}                       # tabela antiga sem coluna pendencias
    finally:
        c.close()


def _resolucoes_mescladas(interacoes=None):
    """{registro_id: dados da resolucao} — banco dobrado + interacoes vivas da
    rede (a viva, mais recente, sobrepoe a dobrada). `interacoes` opcional
    para coalescer a leitura da rede no mesmo request."""
    out = dict(_resolucoes_db())
    for rid, it in _resolucao_viva(interacoes).items():
        out[rid] = {
            "ticket": it.get("ticket") or "",
            "ticket_url": it.get("ticket_url") or "",
            "descricao": it.get("descricao") or "",
            "motivo": it.get("motivo") or "",
            "cargo": it.get("cargo") or "",
            "centro_custo": it.get("centro_custo") or "",
            "nome": it.get("nome") or "",
            "por": it.get("usuario") or "",
            "em": it.get("data_acao") or "",
            "pendencias": it.get("pendencias") or [],
        }
    return out


def _dias_quar(it):
    """Prazo (dias) da interacao de envio; default QUAR_DIAS se ausente/invalido."""
    try:
        d = int(it.get("dias"))
        return d if d > 0 else QUAR_DIAS
    except (TypeError, ValueError):
        return QUAR_DIAS


def _partes_chave(rid):
    """Quebra a chave da interacao nos 3 niveis: (matricula, sistema, perfil).
    "M1" -> pessoa inteira; "M1##SYSTUR" -> sistema; "M1##SYSTUR##P_A" -> acesso."""
    p = str(rid or "").split("##")
    return (p[0] if p else "", p[1] if len(p) > 1 else "",
            p[2] if len(p) > 2 else "")


def _escopo_chave(rid):
    """Rotulo do alvo da quarentena/resolucao, para a tela nao mostrar a chave
    crua ("M1##SYSTUR##P_A") na coluna de usuario."""
    _, sis, perf = _partes_chave(rid)
    return "Acesso" if perf else "Sistema" if sis else "Pessoa"


def _sintetizar_ativa(rid, it):
    """Linha de quarentena ativa a partir de uma interacao ENVIAR viva.
    nome/sistema/prazo/ticket/titulo/motivo vem da propria interacao (gravados no envio).
    data_inicio mantem a HORA do envio; data_fim = dia do inicio + dias (prazo)."""
    inicio = (it.get("data_acao") or "").replace("T", " ")   # com hora
    dias = _dias_quar(it)
    try:
        df = (datetime.strptime(inicio[:10], "%Y-%m-%d")
              + timedelta(days=dias)).strftime("%Y-%m-%d")
    except Exception:
        df = inicio[:10]
    _mat, _sis, _perf = _partes_chave(rid)
    return {"id": rid, "usuario": rid,
            "nome_usuario": it.get("nome") or _mat,
            "sistema": it.get("sistema") or _sis,
            "perfil": it.get("perfil") or _perf,
            "escopo": _escopo_chave(rid),
            "origem": it.get("origem") or "Inclusão / Alteração",
            "data_inicio": inicio, "data_fim": df,
            "dias": dias, "ticket": it.get("ticket") or "",
            "titulo": it.get("titulo") or "", "motivo_entrada": it.get("motivo") or "",
            "criado_por": it.get("usuario") or ""}


def _sintetizar_historico(rid, it, anterior):
    """Linha de historico a partir de uma interacao RESOLVER viva (retirada manual).
    `anterior` traz os dados de ENTRADA (titulo/dias/ticket/motivo) — vem da linha
    ativa (DB) OU sintetizada do ENVIAR vivo. data_saida mantem a HORA da retirada."""
    ds = (it.get("data_acao") or "").replace("T", " ")       # com hora
    if anterior:
        base = dict(anterior)
    else:
        # a chave pode ser composta: o lookup do nome e' pela MATRICULA, e o
        # sistema/perfil vem da propria chave (mais especifico que o do banco)
        _mat, _sis, _perf = _partes_chave(rid)
        nome, sis, _ = _meta_divergencia(_mat)
        base = {"nome_usuario": nome, "sistema": _sis or sis, "perfil": _perf,
                "origem": "", "data_inicio": ds, "data_fim": ds[:10]}
    base.update({"id": rid, "usuario": rid, "data_saida": ds,
                 "motivo": (it.get("motivo") or "").strip() or "Retirado da quarentena",
                 "movido_em": (it.get("data_acao") or "").replace("T", " ") or ds,
                 "encerrado_por": it.get("usuario") or ""})
    return base

_SQL_BI = """
CREATE TABLE bi_divergencias AS
SELECT
  (v.matricula || '_' || v.sistema || '_' || COALESCE(v.perfil_esperado,'')) AS id,
  v.status AS tipo, v.sistema AS sistema, v.matricula AS usuario,
  v.nome AS nome_usuario, v.matricula AS matricula,
  COALESCE(v.perfil_atual,'')    AS perfil_encontrado,
  COALESCE(v.perfil_esperado,'') AS perfil_esperado,
  ''                             AS descricao,
  -- POR QUE a linha esta neste status, quando o status nao se explica sozinho.
  -- Nasceu do retorno da area (10/08/2026): a grid mostrava "Em Analise" com
  -- perfil esperado == encontrado e nao havia como saber que o motivo era o
  -- status da CONTA no extrato. O motivo e' decidido no motor (validacao), aqui
  -- so vira texto.
  CASE COALESCE(v.motivo_status,'')
    WHEN 'CONTA_INDEFINIDA' THEN
      'O perfil confere com o esperado, mas a conta esta com status pendente/'
      || 'indefinido no extrato do sistema — nao da para afirmar que o acesso '
      || 'esta ativo. Confirmar a situacao da conta no proprio sistema.'
    ELSE '' END                  AS motivo,
  COALESCE(v.dt_processamento,'') AS data_identificacao,
  0                              AS resolvida,
  CASE v.status WHEN 'SEM_ACESSO' THEN 'Incluir Acesso'
                WHEN 'DIVERGENTE' THEN 'Alterar Perfil'
                WHEN 'EM_ANALISE' THEN 'Em Análise'
                WHEN 'OK' THEN 'Aderente' ELSE '' END AS acao,
  COALESCE(v.origem_matriz,'') AS origem,
  -- login REAL do sistema (CD_LOGIN), trazido do acesso por (matricula, sistema).
  -- Vazio em SEM_ACESSO (a pessoa ainda nao tem login — a acao e' criar).
  COALESCE((SELECT a.usuario FROM acessos_sistemas a
            WHERE a.matricula_vinculada = v.matricula AND a.sistema = v.sistema
            LIMIT 1), '') AS login
FROM validacao_acessos v
UNION ALL
SELECT
  d.id, d.tipo, d.sistema, d.usuario,
  COALESCE(NULLIF(d.nome_usuario,''), d.usuario) AS nome_usuario,
  COALESCE(d.matricula,'') AS matricula,
  COALESCE(d.perfil_encontrado,'') AS perfil_encontrado,
  COALESCE(d.perfil_esperado,'')  AS perfil_esperado,
  COALESCE(d.descricao,'')        AS descricao,
  ''                              AS motivo,
  COALESCE(d.data_identificacao,'') AS data_identificacao,
  d.resolvida, 'Usuário Não Encontrado' AS acao, '' AS origem,
  d.usuario AS login
FROM divergencias d
WHERE d.tipo = 'ACESSO_SEM_VINCULO_RH'
"""

_IDX_BI = [
    "CREATE INDEX IF NOT EXISTS ix_bi_div_usuario  ON bi_divergencias(usuario)",
    "CREATE INDEX IF NOT EXISTS ix_bi_div_matricula ON bi_divergencias(matricula)",
    "CREATE INDEX IF NOT EXISTS ix_bi_div_sistema  ON bi_divergencias(sistema)",
    "CREATE INDEX IF NOT EXISTS ix_bi_div_tipo     ON bi_divergencias(tipo)",
]

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

# Log append-only: quem JA saiu da quarentena (retirada manual ou prazo vencido)
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

# Colunas do formulario de quarentena (migracao ADITIVA p/ bancos em HML).
_COLS_QUAR_FORM = [("dias", "INTEGER"), ("ticket", "TEXT"),
                   ("titulo", "TEXT"), ("motivo_entrada", "TEXT")]


def conn_rw():
    c = sqlite3.connect(DB_PATH, timeout=15)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=8000")
    return c


def conn_ro():
    uri = f"file:{DB_PATH}?mode=ro"
    c = sqlite3.connect(uri, uri=True, timeout=15)
    c.execute("PRAGMA busy_timeout=8000")
    c.row_factory = sqlite3.Row
    return c


def garantir_estrutura(force=False):
    """bi_divergencias = snapshot fixo (so cria se faltar, ou force).
    quarentena = sempre garante. Indices sempre garantidos.

    Recriar a bi_divergencias INVALIDA o cache `_BASE` — senao o painel (e os
    testes) continuariam servindo o snapshot anterior, de outro cenario."""
    global _BASE
    c = conn_rw()
    try:
        existe = c.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='bi_divergencias'"
        ).fetchone()
        # Banco gerado por Processador antigo pode nao ter `motivo_status` em
        # validacao_acessos — sem isso o CREATE do snapshot abaixo quebraria.
        try:
            _v_cols = [r[1] for r in c.execute("PRAGMA table_info(validacao_acessos)")]
            if _v_cols and "motivo_status" not in _v_cols:
                c.execute("ALTER TABLE validacao_acessos ADD COLUMN motivo_status TEXT")
                c.commit()
        except Exception:
            pass
        if existe and not force:
            cols = [r[1] for r in c.execute("PRAGMA table_info(bi_divergencias)")]
            if "origem" not in cols or "login" not in cols or "motivo" not in cols:
                force = True  # migração de schema: coluna 'origem'/'login'/'motivo'
        if force or not existe:
            c.execute("DROP TABLE IF EXISTS bi_divergencias")
            c.executescript(_SQL_BI)
            _BASE = None          # snapshot mudou: o cache tem de morrer junto
            print("  bi_divergencias (re)criada do cenario atual")
        for ix in _IDX_BI:
            c.execute(ix)
        try:
            c.execute("CREATE INDEX IF NOT EXISTS ix_rh_ativos_matricula "
                      "ON rh_ativos(matricula)")
        except Exception:
            pass
        # Defensivo: DB gerado por Processador antigo pode nao ter tipo_vinculo.
        # Sem isso, o LEFT JOIN rh_ativos com COALESCE(r.tipo_vinculo) quebraria.
        try:
            _rh_cols = [r[1] for r in c.execute("PRAGMA table_info(rh_ativos)")]
            if _rh_cols and "tipo_vinculo" not in _rh_cols:
                c.execute("ALTER TABLE rh_ativos ADD COLUMN tipo_vinculo TEXT DEFAULT 'FUNCIONARIO'")
        except Exception:
            pass
        c.executescript(_SQL_QUAR)
        c.executescript(_SQL_HIST)
        for _tab in ("quarentena", "quarentena_historico"):
            _cols = [r[1] for r in c.execute(f"PRAGMA table_info({_tab})")]
            if "origem" not in _cols:
                c.execute(f"ALTER TABLE {_tab} ADD COLUMN origem TEXT")
            c.execute(f"UPDATE {_tab} SET origem='Inclusão / Alteração' "
                      "WHERE origem IS NULL OR origem=''")
            # colunas do formulario de quarentena (aditivo, HML-safe)
            for _nome, _tipo in _COLS_QUAR_FORM:
                if _nome not in _cols:
                    c.execute(f"ALTER TABLE {_tab} ADD COLUMN {_nome} {_tipo}")
        c.commit()
        n = c.execute("SELECT COUNT(*) FROM bi_divergencias").fetchone()[0]
        print(f"  bi_divergencias: {n} linhas | quarentena: OK")
        return n
    finally:
        c.close()


def _dias(a, b):
    """Dias entre duas datas 'YYYY-MM-DD' (b - a)."""
    try:
        da = datetime.strptime((a or "")[:10], "%Y-%m-%d").date()
        db = datetime.strptime((b or "")[:10], "%Y-%m-%d").date()
        return (db - da).days
    except Exception:
        return 0


def sweep_expiradas(c=None):
    """Move ao historico as quarentenas cujo prazo (data_fim) ja venceu,
    com motivo 'Prazo vencido'. Idempotente."""
    own = c is None
    hoje = datetime.now().strftime("%Y-%m-%d")
    if own:
        # Pre-check barato em read-only: no caso comum (nada vencido) evita
        # abrir conexao de escrita (WAL) a cada /api/dados.
        cro = conn_ro()
        try:
            tem = cro.execute(
                "SELECT 1 FROM quarentena WHERE substr(data_fim,1,10) < ? "
                "LIMIT 1", [hoje]).fetchone()
        finally:
            cro.close()
        if not tem:
            return 0
        c = conn_rw()
    try:
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        venc = c.execute(
            "SELECT id,usuario,nome_usuario,sistema,matricula,origem,data_inicio,"
            "data_fim,dias,ticket,titulo,motivo_entrada,criado_por,criado_em "
            "FROM quarentena WHERE substr(data_fim,1,10) < ?", [hoje]).fetchall()
        for r in venc:
            c.execute(
                "INSERT INTO quarentena_historico (usuario,nome_usuario,sistema,"
                "matricula,origem,data_inicio,data_fim,data_saida,motivo,"
                "dias,ticket,titulo,motivo_entrada,"
                "criado_por,criado_em,encerrado_por,movido_em) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[7],
                 "Prazo vencido", r[8], r[9], r[10], r[11], r[12], r[13], None, agora])
            c.execute("DELETE FROM quarentena WHERE id=?", [r[0]])
        if venc:
            c.commit()
            print(f"  [QUARENTENA] {len(venc)} expirada(s) -> historico")
        return len(venc)
    finally:
        if own:
            c.close()


_MESES = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
          "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]


def _mes_ref(dt):
    """'YYYY-MM-...' -> 'Maio / 2026'."""
    try:
        return f"{_MESES[int(dt[5:7])]} / {dt[:4]}"
    except Exception:
        return "—"


def _fmt_dt(dt):
    """'YYYY-MM-DD HH:MM:SS' -> 'DD/MM/YYYY HH:MM'."""
    d = (dt or "")[:10].split("-")
    if len(d) != 3:
        return "—"
    hm = dt[11:16] if len(dt) > 10 else ""
    return f"{d[2]}/{d[1]}/{d[0]}" + (f" {hm}" if hm else "")


def _col_letra(n):
    """1 -> A, 27 -> AA."""
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _xml_esc(v):
    return (str(v).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def gerar_xlsx(colunas, linhas, niveis=None, formatos=None):
    """Gera um .xlsx (stdlib puro: zipfile + XML) com cabecalho destacado,
    colunas dimensionadas, linha de cabecalho congelada e autofiltro."""
    n_col = max(1, len(colunas))

    def cel(ci, ri, valor, estilo=0):
        ref = f"{_col_letra(ci + 1)}{ri + 1}"
        s = f' s="{estilo}"' if estilo else ""
        if isinstance(valor, bool):
            valor = str(valor)
        if isinstance(valor, (int, float)):
            return f'<c r="{ref}"{s}><v>{valor}</v></c>'
        return (f'<c r="{ref}"{s} t="inlineStr"><is>'
                f'<t xml:space="preserve">{_xml_esc(valor)}</t></is></c>')

    rows_xml = ['<row r="1">' +
                "".join(cel(ci, 0, c, 1) for ci, c in enumerate(colunas)) +
                '</row>']
    for ri, linha in enumerate(linhas, start=1):
        nv = niveis[ri - 1] if niveis and ri - 1 < len(niveis) else 0
        prox = niveis[ri] if niveis and ri < len(niveis) else 0
        # Outline de profundidade livre (pessoa 0 > sistema 1 > perfil 2...): o
        # nivel vira outlineLevel e toda linha que abre um grupo sai recolhida.
        ol = f' outlineLevel="{nv}" hidden="1"' if nv else ""
        if prox > nv:
            ol += ' collapsed="1"'                 # linha-pai de um grupo recolhido
        rows_xml.append(f'<row r="{ri + 1}"{ol}>' +
                        "".join(cel(ci, ri, v) for ci, v in enumerate(linha)) +
                        '</row>')

    larg = []
    for ci in range(len(colunas)):
        m = len(str(colunas[ci]))
        for linha in linhas:
            if ci < len(linha):
                m = max(m, len(str(linha[ci])))
        larg.append(min(70, max(10, m + 3)))
    cols_xml = ("<cols>" + "".join(
        f'<col min="{i+1}" max="{i+1}" width="{w}" customWidth="1"/>'
        for i, w in enumerate(larg)) + "</cols>") if larg else ""

    ref = f"A1:{_col_letra(n_col)}{len(linhas) + 1}"
    # Formatacao condicional (replica as cores dos badges do grid)
    dxfs, cf_xml, _prio = [], "", 1
    for fmt in (formatos or []):
        cl = _col_letra(fmt.get("col", 0) + 1)
        regras = ""
        for reg in fmt.get("regras", []):
            fundo = str(reg.get("fundo") or "FFFFFF").lstrip("#").upper()
            texto = str(reg.get("texto") or "000000").lstrip("#").upper()
            dxfs.append(
                f'<dxf><font><color rgb="FF{texto}"/></font>'
                f'<fill><patternFill><bgColor rgb="FF{fundo}"/></patternFill>'
                f'</fill></dxf>')
            regras += (
                f'<cfRule type="cellIs" dxfId="{len(dxfs) - 1}" '
                f'priority="{_prio}" operator="equal">'
                f'<formula>"{_xml_esc(reg.get("quando", ""))}"</formula></cfRule>')
            _prio += 1
        if regras:
            cf_xml += (f'<conditionalFormatting sqref="{cl}2:{cl}{len(linhas) + 1}">'
                       + regras + '</conditionalFormatting>')
    dxfs_xml = f'<dxfs count="{len(dxfs)}">' + "".join(dxfs) + '</dxfs>'

    agrupado = bool(niveis) and any(niveis)
    prof = max(niveis) if agrupado else 0
    sheet_pr = '<sheetPr><outlinePr summaryBelow="0"/></sheetPr>' if agrupado else ''
    fmt_pr = (f'<sheetFormatPr defaultRowHeight="15" outlineLevelRow="{prof}"/>'
              if agrupado else '')
    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        + sheet_pr +
        '<sheetViews><sheetView tabSelected="1" workbookViewId="0">'
        '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
        '</sheetView></sheetViews>'
        + fmt_pr + cols_xml +
        '<sheetData>' + "".join(rows_xml) + '</sheetData>'
        f'<autoFilter ref="{ref}"/>' + cf_xml + '</worksheet>')

    ctypes = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '</Types>')
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>')
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Dados" sheetId="1" r:id="rId1"/></sheets></workbook>')
    wb_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        '</Relationships>')
    styles = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="2">'
        '<font><sz val="11"/><name val="Calibri"/></font>'
        '<font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>'
        '</fonts>'
        '<fills count="3">'
        '<fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="gray125"/></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FF1F2D5C"/></patternFill></fill>'
        '</fills>'
        '<borders count="1"><border/></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="2">'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/>'
        '</cellXfs>'
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        + dxfs_xml +
        '</styleSheet>')

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ctypes)
        z.writestr("_rels/.rels", rels)
        z.writestr("xl/workbook.xml", workbook)
        z.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        z.writestr("xl/styles.xml", styles)
        z.writestr("xl/worksheets/sheet1.xml", sheet)
    return buf.getvalue()


def gerar_xlsx_vg(secoes, titulo="Visão Geral"):
    """XLSX de UMA aba com TODAS as seções (gráficos) empilhadas, cada uma com
    título + tabela dos dados que a alimentam (espelha o painel). stdlib puro.
    secoes = [{'titulo': str, 'colunas': [..], 'linhas': [[..], ..]}]."""
    def cel(ci, r, valor, estilo=0):
        ref = f"{_col_letra(ci + 1)}{r + 1}"
        s = f' s="{estilo}"' if estilo else ""
        if isinstance(valor, bool):
            valor = str(valor)
        if isinstance(valor, (int, float)):
            return f'<c r="{ref}"{s}><v>{valor}</v></c>'
        return (f'<c r="{ref}"{s} t="inlineStr"><is>'
                f'<t xml:space="preserve">{_xml_esc(valor)}</t></is></c>')
    SHEET = "Visão Geral"
    rows_xml, ri, ncols, charts = [], 0, 1, []
    rows_xml.append(f'<row r="{ri + 1}">' + cel(0, ri, titulo, 1) + '</row>'); ri += 2
    for sec in (secoes or []):
        cols = sec.get("colunas") or []
        linhas = sec.get("linhas") or []
        ncols = max(ncols, len(cols))
        t0 = ri
        rows_xml.append(f'<row r="{ri + 1}">' + cel(0, ri, sec.get("titulo") or "", 2) + '</row>'); ri += 1
        rows_xml.append(f'<row r="{ri + 1}">'
                        + "".join(cel(ci, ri, c, 1) for ci, c in enumerate(cols)) + '</row>'); ri += 1
        for linha in linhas:
            rows_xml.append(f'<row r="{ri + 1}">'
                            + "".join(cel(ci, ri, v) for ci, v in enumerate(linha)) + '</row>'); ri += 1
        ch = sec.get("chart")
        if ch and linhas:
            cc, vc = ch.get("cat", 0), ch.get("val", 1)
            f1, l1 = t0 + 3, t0 + 2 + len(linhas)   # 1-based: 1a e ultima linha de dados
            cL, vL = _col_letra(cc + 1), _col_letra(vc + 1)
            charts.append({
                "tipo": ch.get("tipo", "bar"), "titulo": sec.get("titulo") or "",
                "cat": f"'{SHEET}'!${cL}${f1}:${cL}${l1}",
                "val": f"'{SHEET}'!${vL}${f1}:${vL}${l1}",
                "fc": 3, "fr": t0, "tc": 12, "tr": t0 + 15})
            ri = t0 + 17          # reserva espaço vertical p/ o gráfico
        else:
            ri += 1               # linha em branco entre seções
    larg = []
    for ci in range(ncols):
        m = 12
        for sec in (secoes or []):
            cols = sec.get("colunas") or []
            if ci < len(cols):
                m = max(m, len(str(cols[ci])))
            for linha in (sec.get("linhas") or []):
                if ci < len(linha):
                    m = max(m, len(str(linha[ci])))
        larg.append(min(70, max(14, m + 3)))
    cols_xml = ("<cols>" + "".join(
        f'<col min="{i+1}" max="{i+1}" width="{w}" customWidth="1"/>'
        for i, w in enumerate(larg)) + "</cols>") if larg else ""
    draw_ref = '<drawing r:id="rId1"/>' if charts else ''
    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheetViews><sheetView tabSelected="1" workbookViewId="0">'
        '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
        '</sheetView></sheetViews>'
        + cols_xml +
        '<sheetData>' + "".join(rows_xml) + '</sheetData>' + draw_ref + '</worksheet>')
    chart_ov = ""
    if charts:
        chart_ov = ('<Override PartName="/xl/drawings/drawing1.xml" '
                    'ContentType="application/vnd.openxmlformats-officedocument.drawing+xml"/>')
        for _i in range(len(charts)):
            chart_ov += (f'<Override PartName="/xl/charts/chart{_i+1}.xml" '
                         'ContentType="application/vnd.openxmlformats-officedocument.drawingml.chart+xml"/>')
    ctypes = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        + chart_ov +
        '</Types>')
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>')
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Visão Geral" sheetId="1" r:id="rId1"/></sheets></workbook>')
    wb_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        '</Relationships>')
    styles = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="3">'
        '<font><sz val="11"/><name val="Calibri"/></font>'
        '<font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>'
        '<font><b/><sz val="12"/><color rgb="FF1F2D5C"/><name val="Calibri"/></font>'
        '</fonts>'
        '<fills count="4">'
        '<fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="gray125"/></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FF1F2D5C"/></patternFill></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FFF5E9C8"/></patternFill></fill>'
        '</fills>'
        '<borders count="1"><border/></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="3">'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/>'
        '<xf numFmtId="0" fontId="2" fillId="3" borderId="0" xfId="0" applyFont="1" applyFill="1"/>'
        '</cellXfs>'
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        '</styleSheet>')

    # ── Gráficos nativos (OOXML): 1 chart por seção com 'chart', à direita da tabela ──
    chart_parts, drawing, draw_rels, sheet_rels = [], None, None, None
    if charts:
        def _chart_xml(c):
            ser = ('<c:ser><c:idx val="0"/><c:order val="0"/>'
                   '<c:cat><c:strRef><c:f>' + _xml_esc(c["cat"]) + '</c:f></c:strRef></c:cat>'
                   '<c:val><c:numRef><c:f>' + _xml_esc(c["val"]) + '</c:f></c:numRef></c:val></c:ser>')
            t = c["tipo"]
            if t in ("doughnut", "pie"):
                plot = (('<c:doughnutChart><c:varyColors val="1"/>' + ser + '<c:holeSize val="55"/></c:doughnutChart>')
                        if t == "doughnut" else
                        ('<c:pieChart><c:varyColors val="1"/>' + ser + '</c:pieChart>'))
            else:
                bd = "bar" if t == "bar" else "col"
                cap, vap = ("l", "b") if bd == "bar" else ("b", "l")
                plot = (
                    '<c:barChart><c:barDir val="' + bd + '"/><c:grouping val="clustered"/>'
                    + ser + '<c:axId val="111"/><c:axId val="222"/></c:barChart>'
                    '<c:catAx><c:axId val="111"/><c:scaling><c:orientation val="minMax"/></c:scaling>'
                    '<c:delete val="0"/><c:axPos val="' + cap + '"/><c:crossAx val="222"/></c:catAx>'
                    '<c:valAx><c:axId val="222"/><c:scaling><c:orientation val="minMax"/></c:scaling>'
                    '<c:delete val="0"/><c:axPos val="' + vap + '"/><c:crossAx val="111"/></c:valAx>')
            return (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<c:chartSpace xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" '
                'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><c:chart>'
                '<c:title><c:tx><c:rich><a:bodyPr/><a:lstStyle/><a:p><a:r><a:t>'
                + _xml_esc(c["titulo"]) + '</a:t></a:r></a:p></c:rich></c:tx><c:overlay val="0"/></c:title>'
                '<c:autoTitleDeleted val="0"/><c:plotArea><c:layout/>' + plot + '</c:plotArea>'
                '<c:legend><c:legendPos val="r"/><c:overlay val="0"/></c:legend>'
                '<c:plotVisOnly val="1"/></c:chart></c:chartSpace>')
        anchors = ""
        draw_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                     '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">')
        for i, c in enumerate(charts):
            chart_parts.append((f"xl/charts/chart{i+1}.xml", _chart_xml(c)))
            draw_rels += (f'<Relationship Id="rId{i+1}" '
                          'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart" '
                          f'Target="../charts/chart{i+1}.xml"/>')
            anchors += (
                '<xdr:twoCellAnchor>'
                f'<xdr:from><xdr:col>{c["fc"]}</xdr:col><xdr:colOff>0</xdr:colOff>'
                f'<xdr:row>{c["fr"]}</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:from>'
                f'<xdr:to><xdr:col>{c["tc"]}</xdr:col><xdr:colOff>0</xdr:colOff>'
                f'<xdr:row>{c["tr"]}</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:to>'
                '<xdr:graphicFrame macro="">'
                f'<xdr:nvGraphicFramePr><xdr:cNvPr id="{i+2}" name="Chart {i+1}"/>'
                '<xdr:cNvGraphicFramePr/></xdr:nvGraphicFramePr>'
                '<xdr:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/></xdr:xfrm>'
                '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/chart">'
                '<c:chart xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
                f'r:id="rId{i+1}"/></a:graphicData></a:graphic></xdr:graphicFrame>'
                '<xdr:clientData/></xdr:twoCellAnchor>')
        draw_rels += '</Relationships>'
        drawing = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing" '
                   'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">' + anchors + '</xdr:wsDr>')
        sheet_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                      '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                      '<Relationship Id="rId1" '
                      'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing" '
                      'Target="../drawings/drawing1.xml"/></Relationships>')

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ctypes)
        z.writestr("_rels/.rels", rels)
        z.writestr("xl/workbook.xml", workbook)
        z.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        z.writestr("xl/styles.xml", styles)
        z.writestr("xl/worksheets/sheet1.xml", sheet)
        if charts:
            z.writestr("xl/worksheets/_rels/sheet1.xml.rels", sheet_rels)
            z.writestr("xl/drawings/drawing1.xml", drawing)
            z.writestr("xl/drawings/_rels/drawing1.xml.rels", draw_rels)
            for path, xml in chart_parts:
                z.writestr(path, xml)
    return buf.getvalue()


def _vg_chart_xml(c):
    """XML de UM gráfico OOXML (doughnut/pie/bar/col) ligado a ranges da aba."""
    ser = ('<c:ser><c:idx val="0"/><c:order val="0"/>'
           '<c:cat><c:strRef><c:f>' + _xml_esc(c["cat"]) + '</c:f></c:strRef></c:cat>'
           '<c:val><c:numRef><c:f>' + _xml_esc(c["val"]) + '</c:f></c:numRef></c:val></c:ser>')
    t = c["tipo"]
    if t in ("doughnut", "pie"):
        plot = (('<c:doughnutChart><c:varyColors val="1"/>' + ser + '<c:holeSize val="55"/></c:doughnutChart>')
                if t == "doughnut" else
                ('<c:pieChart><c:varyColors val="1"/>' + ser + '</c:pieChart>'))
    else:
        bd = "bar" if t == "bar" else "col"
        cap, vap = ("l", "b") if bd == "bar" else ("b", "l")
        plot = (
            '<c:barChart><c:barDir val="' + bd + '"/><c:grouping val="clustered"/>'
            + ser + '<c:axId val="111"/><c:axId val="222"/></c:barChart>'
            '<c:catAx><c:axId val="111"/><c:scaling><c:orientation val="minMax"/></c:scaling>'
            '<c:delete val="0"/><c:axPos val="' + cap + '"/><c:crossAx val="222"/></c:catAx>'
            '<c:valAx><c:axId val="222"/><c:scaling><c:orientation val="minMax"/></c:scaling>'
            '<c:delete val="0"/><c:axPos val="' + vap + '"/><c:crossAx val="111"/></c:valAx>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<c:chartSpace xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<c:roundedCorners val="1"/><c:chart>'
        '<c:title><c:tx><c:rich><a:bodyPr/><a:lstStyle/><a:p>'
        '<a:pPr><a:defRPr sz="1200" b="1"><a:solidFill><a:srgbClr val="1F2D5C"/></a:solidFill></a:defRPr></a:pPr>'
        '<a:r><a:rPr lang="pt-BR" sz="1200" b="1"><a:solidFill><a:srgbClr val="1F2D5C"/></a:solidFill></a:rPr><a:t>'
        + _xml_esc(c["titulo"]) + '</a:t></a:r></a:p></c:rich></c:tx><c:overlay val="0"/></c:title>'
        '<c:autoTitleDeleted val="0"/><c:plotArea><c:layout/>' + plot + '</c:plotArea>'
        '<c:legend><c:legendPos val="r"/><c:overlay val="0"/></c:legend>'
        '<c:plotVisOnly val="0"/></c:chart>'
        '<c:spPr><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill>'
        '<a:ln w="9525"><a:solidFill><a:srgbClr val="E7EBF2"/></a:solidFill></a:ln></c:spPr>'
        '</c:chartSpace>')


def _vg_chart_pack(charts):
    """(chart_parts, drawing.xml, drawing.rels, sheet1.rels) para os gráficos."""
    chart_parts = []
    anchors = ""
    draw_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">')
    for i, c in enumerate(charts):
        chart_parts.append((f"xl/charts/chart{i+1}.xml", _vg_chart_xml(c)))
        draw_rels += (f'<Relationship Id="rId{i+1}" '
                      'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart" '
                      f'Target="../charts/chart{i+1}.xml"/>')
        anchors += (
            '<xdr:twoCellAnchor>'
            f'<xdr:from><xdr:col>{c["fc"]}</xdr:col><xdr:colOff>0</xdr:colOff>'
            f'<xdr:row>{c["fr"]}</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:from>'
            f'<xdr:to><xdr:col>{c["tc"]}</xdr:col><xdr:colOff>0</xdr:colOff>'
            f'<xdr:row>{c["tr"]}</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:to>'
            '<xdr:graphicFrame macro="">'
            f'<xdr:nvGraphicFramePr><xdr:cNvPr id="{i+2}" name="Chart {i+1}"/>'
            '<xdr:cNvGraphicFramePr/></xdr:nvGraphicFramePr>'
            '<xdr:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/></xdr:xfrm>'
            '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/chart">'
            '<c:chart xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
            f'r:id="rId{i+1}"/></a:graphicData></a:graphic></xdr:graphicFrame>'
            '<xdr:clientData/></xdr:twoCellAnchor>')
    draw_rels += '</Relationships>'
    drawing = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
               '<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing" '
               'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">' + anchors + '</xdr:wsDr>')
    sheet1_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" '
                   'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing" '
                   'Target="../drawings/drawing1.xml"/></Relationships>')
    return chart_parts, drawing, draw_rels, sheet1_rels


# Paleta dos cards KPI da Visão Geral (fill claro, texto colorido) — espelha o painel.
_VG_CARD_CORES = [
    ("FFF7E0", "1F2D5C"), ("EBF5FB", "2980B9"), ("E8F8F5", "16A085"),
    ("E8EEF7", "1F2D5C"), ("EDE9F7", "5B47A8"), ("FBEAEA", "B33A3A"),
]
# Cor da barrinha lateral (accent) de cada card — como o inset box-shadow do painel.
_VG_CARD_BAR = ["F5B800", "2980B9", "16A085", "1F2D5C", "5B47A8", "B33A3A"]


def _vg_styles_xml():
    """styles.xml com: 0=normal, 1=header(navy), 2=título-seção(gold), 3=título-grande,
    e 2 estilos por card (valor grande + rótulo), índice 4 + k*2 / 5 + k*2."""
    fonts = [
        '<font><sz val="11"/><name val="Calibri"/></font>',
        '<font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>',
        '<font><b/><sz val="12"/><color rgb="FF1F2D5C"/><name val="Calibri"/></font>',
        '<font><b/><sz val="15"/><color rgb="FF1F2D5C"/><name val="Calibri"/></font>',
    ]
    fills = [
        '<fill><patternFill patternType="none"/></fill>',
        '<fill><patternFill patternType="gray125"/></fill>',
        '<fill><patternFill patternType="solid"><fgColor rgb="FF1F2D5C"/></patternFill></fill>',
        '<fill><patternFill patternType="solid"><fgColor rgb="FFF5E9C8"/></patternFill></fill>',
    ]
    xfs = [
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>',
        '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/>',
        '<xf numFmtId="0" fontId="2" fillId="3" borderId="0" xfId="0" applyFont="1" applyFill="1"/>',
        '<xf numFmtId="0" fontId="3" fillId="0" borderId="0" xfId="0" applyFont="1"/>',
    ]
    for fill, txt in _VG_CARD_CORES:
        fi = len(fills)
        fills.append(f'<fill><patternFill patternType="solid"><fgColor rgb="FF{fill}"/></patternFill></fill>')
        fvi = len(fonts); fonts.append(f'<font><b/><sz val="20"/><color rgb="FF{txt}"/><name val="Calibri"/></font>')
        fli = len(fonts); fonts.append(f'<font><b/><sz val="10"/><color rgb="FF{txt}"/><name val="Calibri"/></font>')
        xfs.append(f'<xf numFmtId="0" fontId="{fvi}" fillId="{fi}" borderId="0" xfId="0" '
                   'applyFont="1" applyFill="1" applyAlignment="1">'
                   '<alignment horizontal="center" vertical="center"/></xf>')
        xfs.append(f'<xf numFmtId="0" fontId="{fli}" fillId="{fi}" borderId="0" xfId="0" '
                   'applyFont="1" applyFill="1" applyAlignment="1">'
                   '<alignment horizontal="center" vertical="center"/></xf>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<fonts count="{len(fonts)}">' + "".join(fonts) + '</fonts>'
        f'<fills count="{len(fills)}">' + "".join(fills) + '</fills>'
        '<borders count="1"><border/></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        f'<cellXfs count="{len(xfs)}">' + "".join(xfs) + '</cellXfs>'
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        '</styleSheet>')


def gerar_xlsx_painel(dash_secoes, analiticos, titulo="Visão Geral"):
    """Workbook multi-aba: aba 'Visão Geral' (réplica do painel, com gráficos) +
    uma aba ANALÍTICA por fonte de dados (o detalhe que gerou cada gráfico)."""
    SH1 = "Visão Geral"

    def cel(ci, r, v, s=0):
        ref = f"{_col_letra(ci + 1)}{r + 1}"
        st = f' s="{s}"' if s else ""
        if isinstance(v, bool):
            v = str(v)
        if isinstance(v, (int, float)):
            return f'<c r="{ref}"{st}><v>{v}</v></c>'
        return (f'<c r="{ref}"{st} t="inlineStr"><is>'
                f'<t xml:space="preserve">{_xml_esc(v)}</t></is></c>')

    def fcel(ci, r, formula, s=0):
        ref = f"{_col_letra(ci + 1)}{r + 1}"
        st = f' s="{s}"' if s else ""
        return f'<c r="{ref}"{st}><f>{_xml_esc(formula)}</f></c>'

    def cols_xml(pares):
        nc = max([1] + [len(cc) for cc, _ in pares])
        larg = []
        for ci in range(nc):
            m = 12
            for cc, ll in pares:
                if ci < len(cc):
                    m = max(m, len(str(cc[ci])))
                for row in ll:
                    if ci < len(row):
                        m = max(m, len(str(row[ci])))
            larg.append(min(70, max(12, m + 2)))
        return ("<cols>" + "".join(
            f'<col min="{i+1}" max="{i+1}" width="{w}" customWidth="1"/>'
            for i, w in enumerate(larg)) + "</cols>")

    # ---- aba 1: ESPELHO do painel (formas flutuantes posicionadas em px) ----
    from collections import defaultdict
    kpis = next((s for s in dash_secoes if s.get("kind") == "kpis"), None)
    tempo = next((s for s in dash_secoes if s.get("kind") == "tempo"), None)
    mov = next((s for s in dash_secoes if s.get("kind") == "mov"), None)
    acao = next((s for s in dash_secoes if s.get("kind") == "acao"), None)
    chart_secs = [s for s in dash_secoes if s.get("chart")]
    # Dados-fonte dos gráficos vão em células ESCONDIDAS (cols U+); o visual é
    # 100% desenho flutuante (espelho do painel).
    cells = {}
    def put(r, c, v, s=0):
        cells[(r, c)] = (v, s)
    # posições (px do painel) de cada gráfico
    _POS = {"Chamados": (14, 190, 610, 196), "Divergências": (14, 402, 610, 224),
            "Motivos": (636, 402, 610, 224), "Concentração": (1258, 402, 610, 224),
            "Aging": (14, 638, 738, 200)}
    def _slot(t):
        for k, v in _POS.items():
            if t.startswith(k):
                return v
        return None
    HCOL, hr, charts = 20, 1, []
    for sec in chart_secs:
        cols = sec.get("colunas") or []
        linhas = sec.get("linhas") or []
        ch = sec.get("chart"); cc, vc = ch.get("cat", 0), ch.get("val", 1)
        put(hr + 1, HCOL + cc, cols[cc] if cc < len(cols) else "Categoria", 1)
        put(hr + 1, HCOL + vc, cols[vc] if vc < len(cols) else "Qtd", 1)
        for j, row in enumerate(linhas):
            for kk, val in enumerate(row):
                put(hr + 2 + j, HCOL + kk, val)
        f1, l1 = hr + 3, hr + 2 + len(linhas)
        cL, vL = _col_letra(HCOL + cc + 1), _col_letra(HCOL + vc + 1)
        pos = _slot(sec.get("titulo") or "")
        if pos and linhas:
            charts.append({"tipo": ch.get("tipo", "bar"), "titulo": sec.get("titulo") or "",
                           "cat": f"'{SH1}'!${cL}${f1}:${cL}${l1}",
                           "val": f"'{SH1}'!${vL}${f1}:${vL}${l1}", "px": pos})
        hr += len(linhas) + 3
    rowmap = defaultdict(list)
    for (r, c), (v, s) in cells.items():
        rowmap[r].append((c, v, s))
    rows1 = [f'<row r="{r + 1}">' + "".join(cel(c, r, v, s) for c, v, s in sorted(rowmap[r])) + '</row>'
             for r in sorted(rowmap)]
    draw_ref = '<drawing r:id="rId1"/>' if charts else ''
    sheet1 = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheetViews><sheetView tabSelected="1" showGridLines="0" showRowColHeaders="0" '
        'workbookViewId="0"/></sheetViews>'
        '<cols><col min="21" max="90" hidden="1"/></cols>'
        '<sheetData>' + "".join(rows1) + '</sheetData>'
        '<sheetProtection sheet="1" objects="1" scenarios="1" '
        'selectLockedCells="1" selectUnlockedCells="1"/>'
        + draw_ref + '</worksheet>')

    # ---- abas analíticas (tabela por fonte) + coluna-auxiliar de visibilidade ----
    # Cada aba ganha 2 colunas ocultas: 'n' (=1, sempre preenchida) e 'vis'
    # (=SUBTOTAL(103, n) → 1 se a linha está VISÍVEL no autoFilter, 0 se filtrada).
    # É o que faz os gráficos da aba 'Análise Interativa' responderem aos filtros.
    ana_sheets = []
    ana_meta = {}

    def _cats(linhas, ci, faixa=False):
        seen, s = [], set()
        for row in linhas:
            v = str(row[ci]) if ci < len(row) else ""
            if v and v not in s:
                s.add(v); seen.append(v)
        if faixa:
            ordem = {"0-7": 0, "8-30": 1, "31-90": 2, "90+": 3}
            seen.sort(key=lambda x: ordem.get(x, 9))
        return seen

    for a in (analiticos or []):
        cols = a.get("colunas") or []
        linhas = a.get("linhas") or []
        nd = max(1, len(cols))
        n_ci, vis_ci = nd, nd + 1
        hdr = "".join(cel(ci, 0, c, 1) for ci, c in enumerate(cols))
        hdr += cel(n_ci, 0, "n", 1) + cel(vis_ci, 0, "vis", 1)
        rws = ['<row r="1">' + hdr + '</row>']
        for i, row in enumerate(linhas, start=1):
            body = "".join(cel(ci, i, v) for ci, v in enumerate(row))
            body += cel(n_ci, i, 1)
            body += fcel(vis_ci, i, f"SUBTOTAL(103,{_col_letra(n_ci + 1)}{i + 1})")
            rws.append(f'<row r="{i + 1}">' + body + '</row>')
        ref = f"A1:{_col_letra(nd)}{len(linhas) + 1}"
        cols_block = cols_xml([(cols, linhas)])[:-len("</cols>")] + \
            f'<col min="{n_ci + 1}" max="{vis_ci + 1}" hidden="1"/></cols>'
        xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetViews><sheetView workbookViewId="0">'
            '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
            '</sheetView></sheetViews>'
            + cols_block + '<sheetData>' + "".join(rws) + '</sheetData>'
            + f'<autoFilter ref="{ref}"/></worksheet>')
        nome = a.get("nome") or "Dados"
        ana_sheets.append((nome, xml))
        ana_meta[nome] = {"nrows": len(linhas), "helper_letra": _col_letra(vis_ci + 1),
                          "linhas": linhas}

    # ---- aba 'Análise Interativa': gráficos por fórmula (SUMPRODUCT + SUBTOTAL)
    #      que recalculam ao FILTRAR as abas analíticas (nível registro/auditável) ----
    SH2 = "Análise Interativa"
    INTER = [
        {"titulo": "Divergências por Tipo (registros)", "tipo": "doughnut",
         "aba": "Divergências (analítico)", "cat_ci": 4, "px": (14, 128, 610, 250)},
        {"titulo": "Concentração por Sistema (registros)", "tipo": "bar",
         "aba": "Divergências (analítico)", "cat_ci": 3, "px": (636, 128, 610, 250)},
        {"titulo": "Aging das Pendências (registros)", "tipo": "col",
         "aba": "Aging (analítico)", "cat_ci": 7, "px": (14, 396, 610, 250)},
        {"titulo": "Motivos das Resoluções — Pendências (registros)", "tipo": "doughnut",
         "aba": "Motivos (analítico)", "cat_ci": 2, "px": (636, 396, 610, 250)},
    ]
    icells = {}

    def iput(r, c, v, s=0):
        icells[(r, c)] = ("v", v, s)

    def iputf(r, c, f, s=0):
        icells[(r, c)] = ("f", f, s)

    HCOL2, hr2, inter_charts = 20, 1, []
    for cfg in INTER:
        meta = ana_meta.get(cfg["aba"])
        if not meta or meta["nrows"] == 0:
            continue
        last = meta["nrows"] + 1
        catL = _col_letra(cfg["cat_ci"] + 1)
        hlpL = meta["helper_letra"]
        aba = cfg["aba"]
        cats = _cats(meta["linhas"], cfg["cat_ci"],
                     faixa=(cfg["cat_ci"] == 7 and "Aging" in aba))
        if not cats:
            continue
        iput(hr2 + 1, HCOL2, "Categoria", 1)
        iput(hr2 + 1, HCOL2 + 1, "Qtd", 1)
        for j, cat in enumerate(cats):
            rr = hr2 + 2 + j
            iput(rr, HCOL2, cat)
            catref = f"{_col_letra(HCOL2 + 1)}{rr + 1}"
            iputf(rr, HCOL2 + 1,
                  f"SUMPRODUCT(('{aba}'!${catL}$2:${catL}${last}={catref})"
                  f"*('{aba}'!${hlpL}$2:${hlpL}${last}))")
        f1, l1 = hr2 + 3, hr2 + 2 + len(cats)
        cL, vL = _col_letra(HCOL2 + 1), _col_letra(HCOL2 + 2)
        inter_charts.append({"tipo": cfg["tipo"], "titulo": cfg["titulo"],
                             "cat": f"'{SH2}'!${cL}${f1}:${cL}${l1}",
                             "val": f"'{SH2}'!${vL}${f1}:${vL}${l1}", "px": cfg["px"]})
        hr2 += len(cats) + 3
    irowmap = defaultdict(list)
    for (r, c), (kind, v, s) in icells.items():
        irowmap[r].append((c, kind, v, s))

    def _icell(c, r, kind, v, s):
        return fcel(c, r, v, s) if kind == "f" else cel(c, r, v, s)

    rows2 = [f'<row r="{r + 1}">' + "".join(_icell(c, r, kind, v, s)
             for c, kind, v, s in sorted(irowmap[r])) + '</row>'
             for r in sorted(irowmap)]
    draw2_ref = '<drawing r:id="rId1"/>' if inter_charts else ''
    sheet2 = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheetViews><sheetView showGridLines="0" showRowColHeaders="0" '
        'workbookViewId="0"/></sheetViews>'
        '<cols><col min="21" max="90" hidden="1"/></cols>'
        '<sheetData>' + "".join(rows2) + '</sheetData>'
        '<sheetProtection sheet="1" objects="1" scenarios="1" '
        'selectLockedCells="1" selectUnlockedCells="1"/>'
        + draw2_ref + '</worksheet>')

    sheets_all = [(SH1, sheet1), (SH2, sheet2)] + ana_sheets
    n = len(sheets_all)
    sheets_tag = "".join(
        f'<sheet name="{_xml_esc(nm[:31])}" sheetId="{i+1}" r:id="rId{i+1}"/>'
        for i, (nm, _) in enumerate(sheets_all))
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets>' + sheets_tag + '</sheets>'
        '<calcPr calcId="0" fullCalcOnLoad="1"/></workbook>')
    wb_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
               '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">')
    for i in range(n):
        wb_rels += (f'<Relationship Id="rId{i+1}" '
                    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                    f'Target="worksheets/sheet{i+1}.xml"/>')
    wb_rels += (f'<Relationship Id="rId{n+1}" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
                'Target="styles.xml"/></Relationships>')

    # ---- DESENHOS FLUTUANTES (factory: 1 desenho por aba com gráficos) ----
    _E = lambda px: int(round(px * 9525))
    chart_parts = []
    _chart_seq = [0]

    def _anchor(x, y, w, h, inner):
        return ('<xdr:absoluteAnchor>'
                f'<xdr:pos x="{_E(x)}" y="{_E(y)}"/>'
                f'<xdr:ext cx="{_E(w)}" cy="{_E(h)}"/>' + inner
                + '<xdr:clientData/></xdr:absoluteAnchor>')

    def _build_drawing(fill_fn):
        objs, drels, idc = [], [], [1]

        def sp(x, y, w, h, fill, line, texts, radius=True):
            idc[0] += 1
            body = "".join(
                f'<a:p><a:pPr algn="{algn}"/><a:r><a:rPr lang="pt-BR" sz="{sz}" b="{1 if b else 0}">'
                f'<a:solidFill><a:srgbClr val="{col}"/></a:solidFill></a:rPr>'
                f'<a:t>{_xml_esc(str(t))}</a:t></a:r></a:p>'
                for (t, sz, b, col, algn) in texts) or '<a:p><a:endParaRPr lang="pt-BR"/></a:p>'
            geom = ('<a:prstGeom prst="roundRect"><a:avLst><a:gd name="adj" fmla="val 7000"/></a:avLst></a:prstGeom>'
                    if radius else '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>')
            ln = (f'<a:ln><a:solidFill><a:srgbClr val="{line}"/></a:solidFill></a:ln>'
                  if line else '<a:ln><a:noFill/></a:ln>')
            inner = ('<xdr:sp macro="" textlink="">'
                     f'<xdr:nvSpPr><xdr:cNvPr id="{idc[0]}" name="sp{idc[0]}"/><xdr:cNvSpPr/></xdr:nvSpPr>'
                     f'<xdr:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{_E(w)}" cy="{_E(h)}"/></a:xfrm>'
                     + geom + f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>' + ln + '</xdr:spPr>'
                     '<xdr:txBody><a:bodyPr anchor="ctr" wrap="square" '
                     'lIns="54000" tIns="36000" rIns="54000" bIns="36000"/><a:lstStyle/>'
                     + body + '</xdr:txBody></xdr:sp>')
            objs.append(_anchor(x, y, w, h, inner))

        def chart(x, y, w, h, spec):
            idc[0] += 1
            _chart_seq[0] += 1
            k = _chart_seq[0]
            chart_parts.append((f"xl/charts/chart{k}.xml", _vg_chart_xml(spec)))
            rid = len(drels) + 1
            drels.append(f'<Relationship Id="rId{rid}" '
                         'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart" '
                         f'Target="../charts/chart{k}.xml"/>')
            inner = ('<xdr:graphicFrame macro="">'
                     f'<xdr:nvGraphicFramePr><xdr:cNvPr id="{idc[0]}" name="Chart{idc[0]}"/>'
                     '<xdr:cNvGraphicFramePr/></xdr:nvGraphicFramePr>'
                     f'<xdr:xfrm><a:off x="0" y="0"/><a:ext cx="{_E(w)}" cy="{_E(h)}"/></xdr:xfrm>'
                     '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/chart">'
                     '<c:chart xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" '
                     'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
                     f'r:id="rId{rid}"/></a:graphicData></a:graphic></xdr:graphicFrame>')
            objs.append(_anchor(x, y, w, h, inner))

        fill_fn(sp, chart)
        if not objs:
            return None, None
        dxml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing" '
                'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
                + "".join(objs) + '</xdr:wsDr>')
        rxml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                + "".join(drels) + '</Relationships>')
        return dxml, rxml

    def _sheet_draw_rels(fn):
        return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing" '
                f'Target="../drawings/{fn}"/></Relationships>')

    # desenho 1 — ESPELHO do painel (sheet1)
    def _draw_vg(_sp, _chart):
        if not charts:
            return
        _sp(0, 0, 1880, 72, "1F2D5C", "", [(titulo, 1500, True, "FFFFFF", "l")], radius=False)
        if kpis:
            for k, row in enumerate(kpis.get("linhas", [])[:6]):
                lbl, val = (list(row) + ["", ""])[:2]
                cx = 14 + k * 310
                fill, txt = _VG_CARD_CORES[k % len(_VG_CARD_CORES)]
                bar = _VG_CARD_BAR[k % len(_VG_CARD_BAR)]
                _sp(cx, 88, 298, 84, fill, "D5DCEA",
                    [(val, 2000, True, txt, "ctr"), (lbl, 1000, True, txt, "ctr")])
                _sp(cx + 1, 94, 6, 72, bar, "", [], radius=False)
        if tempo:
            tx = [(tempo.get("titulo") or "Tempo de Tratamento", 1100, True, "1F2D5C", "l")]
            for row in tempo.get("linhas", []):
                a, b = (list(row) + ["", ""])[:2]
                tx.append((f"{a}:  {b}", 1000, False, "3A3F4C", "l"))
            _sp(636, 190, 610, 196, "FFFFFF", "E7EBF2", tx)
        mtx = [((mov.get("titulo") if mov else None) or "Movimentação RH (últimos 30 dias)",
                1100, True, "1F2D5C", "l")]
        for row in (mov.get("linhas", []) if mov else []):
            a, b = (list(row) + ["", ""])[:2]
            vazio = str(b) == ""
            mtx.append((str(a) if vazio else f"{a}:  {b}", 1000, False,
                        ("8A9099" if vazio else "3A3F4C"), "l"))
        _sp(1258, 190, 610, 196, "FFFFFF", "E7EBF2", mtx)
        atx = [((acao.get("titulo") if acao else None) or "Ação Imediata — Recém-desligados com Acesso",
                1100, True, "1F2D5C", "l")]
        for row in (acao.get("linhas", []) if acao else []):
            parts = [str(x) for x in row if str(x) != ""]
            if not parts:
                continue
            vazio = len(parts) == 1 and parts[0].lower().startswith("sem desligados")
            atx.append((" · ".join(parts), 1000, False, ("8A9099" if vazio else "3A3F4C"), "l"))
        _sp(766, 638, 1102, 200, "FFFFFF", "E7EBF2", atx)
        for spec in charts:
            x, y, w, h = spec["px"]
            _chart(x, y, w, h, spec)

    # desenho 2 — ANÁLISE INTERATIVA (sheet2): responde aos filtros das analíticas
    def _draw_inter(_sp, _chart):
        if not inter_charts:
            return
        _sp(0, 0, 1260, 60, "1F2D5C", "",
            [("Análise Interativa — filtre as abas analíticas para atualizar",
              1300, True, "FFFFFF", "l")], radius=False)
        _sp(14, 72, 1232, 44, "EEF3FB", "D5DCEA",
            [("Estes gráficos contam REGISTROS e recalculam conforme os filtros das "
              "abas analíticas. Os números do painel 'Visão Geral' são fixos "
              "(usuários distintos).", 900, False, "3A3F4C", "l")])
        for spec in inter_charts:
            x, y, w, h = spec["px"]
            _chart(x, y, w, h, spec)

    drawing1, draw1_rels = _build_drawing(_draw_vg)
    drawing2, draw2_rels = _build_drawing(_draw_inter)
    # (sheet_index, arquivo, drawing_xml, rels_xml) para cada desenho existente
    draw_files = []
    if drawing1:
        draw_files.append((1, "drawing1.xml", drawing1, draw1_rels))
    if drawing2:
        draw_files.append((2, "drawing2.xml", drawing2, draw2_rels))

    ct_sheets = "".join(
        f'<Override PartName="/xl/worksheets/sheet{i+1}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for i in range(n))
    chart_ov = ""
    for _si, _fn, _dx, _rx in draw_files:
        chart_ov += (f'<Override PartName="/xl/drawings/{_fn}" '
                     'ContentType="application/vnd.openxmlformats-officedocument.drawing+xml"/>')
    for _i in range(len(chart_parts)):
        chart_ov += (f'<Override PartName="/xl/charts/chart{_i+1}.xml" '
                     'ContentType="application/vnd.openxmlformats-officedocument.drawingml.chart+xml"/>')
    ctypes = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        + ct_sheets + chart_ov + '</Types>')
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>')

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ctypes)
        z.writestr("_rels/.rels", rels)
        z.writestr("xl/workbook.xml", workbook)
        z.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        z.writestr("xl/styles.xml", _vg_styles_xml())
        for i, (nm, xml) in enumerate(sheets_all):
            z.writestr(f"xl/worksheets/sheet{i+1}.xml", xml)
        for si, fn, dxml, rxml in draw_files:
            z.writestr(f"xl/worksheets/_rels/sheet{si}.xml.rels", _sheet_draw_rels(fn))
            z.writestr(f"xl/drawings/{fn}", dxml)
            z.writestr(f"xl/drawings/_rels/{fn}.rels", rxml)
        for path, xml in chart_parts:
            z.writestr(path, xml)
    return buf.getvalue()


def _perfil_div(d):
    """Identidade do ACESSO dentro do (usuario, sistema): o perfil que a grid
    mostra na sub-linha — o ENCONTRADO quando existe, senao o ESPERADO. As
    varias linhas de "Em Analise" (1 por perfil candidato) compartilham o mesmo
    perfil encontrado, entao caem na MESMA chave — igual ao que a tela agrupa."""
    return (d.get("pe") or d.get("pp") or "").strip()


def construir_db():
    """DB para o index.html. A parte cara (bi_divergencias + JOIN rh_ativos) e
    calculada 1x e cacheada; so o filtro de quarentena re-roda a cada request
    (barato: a tabela quarentena e pequena)."""
    global _BASE
    sweep_expiradas()
    if _BASE is None:
        _BASE = _montar_base()
    cro = conn_ro()
    try:
        em_quar = {r[0] for r in cro.execute("SELECT usuario FROM quarentena")}
    finally:
        cro.close()
    # Le as interacoes da rede UMA vez por request e reaproveita nos dois
    # estados vivos abaixo (antes eram 2 varreduras completas da pasta SMB).
    _interacoes = _interacoes_ler()
    # sobrepoe as interacoes vivas da rede (ENVIAR entra, RESOLVER sai)
    for rid, it in _quarentena_viva(_interacoes).items():
        if it.get("acao") == "ENVIAR":
            em_quar.add(rid)  # noqa: E501  (chave pode ser composta — ver abaixo)
        elif it.get("acao") == "RESOLVER":
            em_quar.discard(rid)
    # sobrepoe as resolucoes (banco dobrado + interacoes vivas): o funcionario
    # resolvido ganha u.resolvido + u.resolucao e todas as divs viram Resolvido.
    resolvidos = _resolucoes_mescladas(_interacoes)
    # Granularidade da acao (retorno Bruna, 3 niveis) — a chave da interacao
    # carrega o alvo, sem mudar schema:
    #   "usuario"                    -> a PESSOA inteira
    #   "usuario##sistema"           -> so aquele SISTEMA
    #   "usuario##sistema##perfil"   -> so aquele ACESSO (perfil)
    em_quar_all = {k for k in em_quar if "##" not in k}
    em_quar_sis = {}      # usuario -> {sistema}
    em_quar_perf = {}     # usuario -> {(sistema, perfil)}
    for k in em_quar:
        if "##" not in k:
            continue
        partes = k.split("##")
        if len(partes) >= 3 and partes[2]:
            em_quar_perf.setdefault(partes[0], set()).add((partes[1], partes[2]))
        else:
            em_quar_sis.setdefault(partes[0], set()).add(partes[1])
    users = []
    for u in _BASE["users"]:
        if u["u"] in em_quar_all:
            continue                            # pessoa inteira em quarentena
        _qsis = em_quar_sis.get(u["u"])
        _qperf = em_quar_perf.get(u["u"])
        if _qsis or _qperf:
            _divs = [d for d in u["divs"]
                     if d.get("sis") not in (_qsis or ())
                     and (d.get("sis"), _perfil_div(d)) not in (_qperf or ())]
            if not _divs:
                continue                        # tudo em quarentena
            u = dict(u, divs=_divs)             # segue sem o que foi quarentenado
        r_all = resolvidos.get(u["u"])          # resolucao da PESSOA inteira
        # resolucoes por SISTEMA e por ACESSO (perfil) desta pessoa
        r_sis, r_perf = {}, {}
        _pre = u["u"] + "##"
        for k, v in resolvidos.items():
            if not k.startswith(_pre):
                continue
            partes = k.split("##")
            if len(partes) >= 3 and partes[2]:
                r_perf[(partes[1], partes[2])] = v
            else:
                r_sis[partes[1]] = v
        if r_all or r_sis or r_perf:
            uc = dict(u)
            # Cada div vira Resolvido se a pessoa foi resolvida inteira, OU o
            # SISTEMA da div foi resolvido, OU aquele ACESSO (perfil) foi
            # resolvido. Linha JA Aderente (OK) vence -> Aderente.
            def _st(d):
                if d.get("t") == "OK":
                    return "Aderente"
                if r_all or (d.get("sis") in r_sis) \
                        or ((d.get("sis"), _perfil_div(d)) in r_perf):
                    return "Resolvido"
                return d.get("s")
            uc["divs"] = [dict(d, s=_st(d)) for d in u["divs"]]
            # resolvido (lupa/estado da PESSOA) = resolucao da pessoa inteira. A
            # resolucao POR SISTEMA nao "resolve a pessoa" — aparece nos divs
            # (sub-linha do sistema vira Resolvido), e a pessoa segue com o botao
            # de resolver os demais sistemas.
            uc["resolvido"] = bool(r_all)
            uc["resolucao"] = (r_all or next(iter(r_sis.values()), None)
                               or next(iter(r_perf.values()), None))
            uc["resolucao_sis"] = r_sis          # {sistema: dados} p/ lupa por sistema
            # {"sistema||perfil": dados} — lupa do acesso individual (o JSON nao
            # aceita tupla como chave)
            uc["resolucao_perfil"] = {f"{s}||{p}": v for (s, p), v in r_perf.items()}
            users.append(uc)
        else:
            users.append(u)
    # Visão Geral: copia o vg estatico e injeta os campos DINAMICOS.
    vg = dict(_BASE.get("vg", {}))
    vg["quarentena_ativa"] = len(em_quar)
    # Resolvidos recalculados AO VIVO (dobrado + interacoes da rede), nao o
    # snapshot cacheado em _BASE — assim a VG atualiza assim que algo e'
    # resolvido, sem reiniciar. Mesma janela movel de N dias do _calcular_visao_geral.
    _corte = (datetime.now() - timedelta(days=VG_JANELA_DIAS)).strftime("%Y-%m-%d")
    n_resolv = sum(1 for r in resolvidos.values()
                   if str(r.get("em", ""))[:10] >= _corte)
    ch = dict(vg.get("chamados") or
              {"identificados": 0, "resolvidos": 0, "tempo_medio_dias": 0})
    ch["resolvidos"] = n_resolv
    vg["chamados"] = ch
    return {"kpis": _BASE["kpis"], "acao_dist": _BASE["acao_dist"],
            "sis_dist": _BASE["sis_dist"], "meta": _BASE["meta"],
            "users": users, "vg": vg, "aderentes": _BASE.get("aderentes", [])}


def _montar_base():
    """Parte estatica do DB (bi_divergencias + JOIN), sem o filtro de quarentena."""
    c = conn_ro()
    try:
        whereS = "WHERE sistema = ?" if SISTEMA else ""
        argS = [SISTEMA] if SISTEMA else []

        sis_dist = {r["sistema"]: r["n"] for r in c.execute(
            "SELECT sistema, COUNT(*) n FROM bi_divergencias GROUP BY sistema")}

        # REGRA: todo card conta USUARIOS distintos (qualitativo), nao acessos
        # (quantitativo). Um usuario pode ter varios acessos do mesmo tipo — Em
        # Analise com N perfis candidatos, ou varios acessos sem vinculo — mas no
        # card conta como 1 pessoa. (Bate com o nivel superior da grid: 1 linha
        # por usuario.) Antes contava linhas e inflava (ex.: Em Analise 523 op. de
        # 154 pessoas; Nao Mapeado 5540 acessos de 5036 pessoas).
        def cont(t):
            return c.execute(
                f"SELECT COUNT(DISTINCT usuario) FROM bi_divergencias {whereS} "
                f"{'AND' if whereS else 'WHERE'} tipo=?", argS + [t]).fetchone()[0]

        kpis = {
            "sem_acesso": cont("SEM_ACESSO"),
            "divergente": cont("DIVERGENTE"),
            "em_analise": cont("EM_ANALISE"),
            "nao_mapeado": cont("ACESSO_SEM_VINCULO_RH"),
            "ok": cont("OK"),                       # conforme — nao e' pendencia
        }
        # total de PENDENCIAS = PESSOAS distintas a tratar (resolvida=0). Exclui OK
        # (aderente) E SEM_ACESSO — este ultimo deixou de ser pendencia (retorno
        # Bruna): "sem acesso" e' informativo (so na Consulta), nao entra na
        # contagem de pendencias. NAO e' a soma dos cards (multi-sistema conta 1x).
        kpis["total"] = c.execute(
            f"SELECT COUNT(DISTINCT usuario) FROM bi_divergencias {whereS} "
            f"{'AND' if whereS else 'WHERE'} resolvida=0 AND tipo<>'OK' "
            f"AND tipo<>'SEM_ACESSO'",
            argS).fetchone()[0]
        acao_dist = {r["acao"]: r["n"] for r in c.execute(
            f"SELECT acao, COUNT(DISTINCT usuario) n FROM bi_divergencias {whereS} "
            f"GROUP BY acao ORDER BY n DESC", argS)}

        # Usuarios de TODA a base; o filtro de quarentena e aplicado por
        # request em construir_db (a tabela quarentena e pequena/barata).
        cond, a2 = [], []
        if SISTEMA:
            cond.append("b.sistema = ?"); a2.append(SISTEMA)
        wsql = ("WHERE " + " AND ".join(cond)) if cond else ""

        rows = c.execute(
            f"""SELECT b.usuario, b.nome_usuario, b.matricula, b.tipo, b.acao,
                       b.perfil_encontrado, b.perfil_esperado, b.data_identificacao,
                       b.resolvida, b.origem, b.sistema, b.login,
                       COALESCE(b.motivo,'') motivo,
                       COALESCE(r.cargo_descricao,'') cargo,
                       COALESCE(r.departamento,'')   depto,
                       COALESCE(r.centro_custo_codigo,'') cc_cod,
                       COALESCE(r.centro_custo_nome,'')   cc_nome,
                       COALESCE(r.cpf,'')   cpf,
                       COALESCE(r.email,'') email,
                       COALESCE(r.gestor,'') gestor,
                       COALESCE(r.tipo_vinculo,'FUNCIONARIO') tipo_vinc
                FROM bi_divergencias b
                LEFT JOIN rh_ativos r ON r.matricula = b.matricula
                {wsql}
                ORDER BY b.usuario""", a2).fetchall()

        users = {}
        for r in rows:
            u = users.get(r["usuario"])
            if u is None:
                u = {"u": r["usuario"], "n": r["nome_usuario"] or r["usuario"],
                     "m": r["matricula"] or "", "c": r["cargo"], "d": r["depto"],
                     "cc": (r["cc_cod"] + " - " + r["cc_nome"]).strip(" -"),
                     "cpf": r["cpf"] or "", "email": r["email"] or "",
                     "gestor": r["gestor"] or "",
                     # categoria (Funcionário/Terceiro/Franqueado/Prestador) —
                     # mesma p/ toda a pessoa
                     "vinc": rotulo_vinculo(r["tipo_vinc"]),
                     "divs": []}
                users[r["usuario"]] = u
            tp = r["tipo"]
            u["divs"].append({
                "t": tp, "tl": TIPO_LABEL.get(tp, tp), "a": r["acao"],
                "sis": r["sistema"] or "",
                "login": r["login"] or "",   # login do sistema (CD_LOGIN) desta linha
                "pe": r["perfil_encontrado"], "pp": r["perfil_esperado"],
                # motivo do status, quando o status nao se explica sozinho
                # (hoje: conta pendente/indefinida no extrato) — a grid mostra
                # como aviso na linha. Vazio na esmagadora maioria das linhas.
                "mot": r["motivo"] or "",
                "dt": r["data_identificacao"] or "",
                "s": ("Aderente" if tp == "OK"
                      else "Resolvido" if r["resolvida"] else "Pendente"),
                # categoria lida do rh_ativos (tipo_vinculo): Funcionário (CLT),
                # Terceiro (fornecedor) ou Franqueado/Prestador (diretório AD).
                "vinc": rotulo_vinculo(r["tipo_vinc"]),
                "o": ("Matriz " + (r["sistema"] or "")) if r["origem"] == "MATRIZ"
                     else ("Matriz CCO" if r["origem"] == "CCO" else "—"),
            })
        # Login do usuario = logins distintos dos seus acessos (96% tem 1).
        # Vazio quando so ha SEM_ACESSO (ainda nao tem login no sistema).
        # Deduplica IGNORANDO caixa: o mesmo login em sistemas diferentes pode
        # vir em caixas distintas (INTADM527 no SYSTUR, intadm527 no SIGOT) — e'
        # o mesmo login, mostra uma vez so. Logins realmente distintos (ex.:
        # mariliadavid no SIG) continuam aparecendo.
        for _u in users.values():
            _por_caixa = {}
            for d in _u["divs"]:
                lg = d.get("login")
                if lg and lg.strip().lower() not in _por_caixa:
                    _por_caixa[lg.strip().lower()] = lg
            _u["login"] = ", ".join(sorted(_por_caixa.values()))
        maxdt = c.execute(
            "SELECT MAX(data_identificacao) FROM bi_divergencias "
            "WHERE data_identificacao <> ''").fetchone()[0] or ""
        meta = {"referencia": _mes_ref(maxdt), "atualizacao": _fmt_dt(maxdt)}

        # ── Visão Geral (campos adicionais para a aba pg-vg) ──────────────
        # Filtra por SISTEMA do config (mesmo escopo da grid de Inclusão).
        # Resiliente a drift de schema: se a VG falhar (ex.: banco antigo sem
        # alguma coluna/tabela), o painel principal segue de pe com vg vazio.
        try:
            vg = _calcular_visao_geral(c, sistema=SISTEMA)
        except Exception as e:
            print(f"  [vg] falha ao calcular Visão Geral: {e!r} — vg vazio")
            vg = {}

        # ── Conformidade (aba Aderentes): quem está conforme + a trilha/datas ─
        # REGRA (mesma das pendencias): conta USUARIOS, nao acessos. 1 linha por
        # matricula — se a pessoa for aderente em +de um sistema, mantemos a
        # aderencia mais recente (ORDER BY dt_aderente DESC -> primeira vista).
        aderentes = []
        try:
            cond_a, par_a = "WHERE dt_aderente IS NOT NULL", []
            if SISTEMA:
                cond_a += " AND sistema = ?"
                par_a.append(SISTEMA)
            # SEM dedup por matricula: traz TODAS as linhas (matricula, sistema)
            # aderentes — uma pessoa aderente em 6 sistemas vem em 6 linhas. O
            # painel agrupa por pessoa (accordion), mostrando todos os sistemas em
            # que ela aderiu (antes o dedup escondia todos menos o mais recente).
            for r in c.execute(
                "SELECT cv.matricula,cv.nome,cv.login,cv.cargo,cv.sistema,cv.perfil,"
                "       cv.dt_aderente,cv.dt_pendencia,cv.dt_resolvido,cv.ticket,"
                "       COALESCE(rh.gestor,'') gestor,"
                "       COALESCE(rh.tipo_vinculo,'FUNCIONARIO') tipo_vinc "
                "FROM ciclo_vida_acesso cv "
                "LEFT JOIN rh_ativos rh ON rh.matricula = cv.matricula "
                + cond_a.replace("dt_aderente", "cv.dt_aderente").replace("sistema =", "cv.sistema =")
                + " ORDER BY cv.dt_aderente DESC", par_a):
                aderentes.append({
                    "m": r["matricula"], "n": r["nome"] or "", "login": r["login"] or "",
                    "cargo": r["cargo"] or "", "sis": r["sistema"] or "",
                    "perfil": r["perfil"] or "", "dt": r["dt_aderente"] or "",
                    "dt_pend": r["dt_pendencia"] or "", "dt_resol": r["dt_resolvido"] or "",
                    "ticket": r["ticket"] or "",
                    "gestor": r["gestor"] or "",
                    "vinc": rotulo_vinculo(r["tipo_vinc"]),
                })
        except Exception as e:
            print(f"  [conf] falha ao montar aderentes: {e!r}")

        # ── Enriquecimento: Nº de ciclos por (matricula, sistema) do log de
        # eventos (ciclo_eventos_acesso) — habilita o selo "reaberta / Nº ciclos"
        # nas abas Pendencias e Aderentes. Ciclo > 1 = a pessoa ja passou por
        # reabertura(s) naquele sistema. Blindado: banco antigo sem a tabela ->
        # nenhum selo (segue normal).
        try:
            ciclo_max = {}
            for r in c.execute("SELECT matricula, sistema, MAX(ciclo) mc "
                               "FROM ciclo_eventos_acesso GROUP BY matricula, sistema"):
                ciclo_max[(r["matricula"], r["sistema"])] = r["mc"] or 1
            if ciclo_max:
                for u in users.values():
                    for d in u["divs"]:
                        mc = ciclo_max.get((u["m"], d.get("sis")))
                        if mc and mc > 1:
                            d["ciclos"] = mc
                            # pendencia atual num sistema com ciclo>1 = reaberta
                            d["reab"] = (d.get("s") == "Pendente")
                # trilha (marcos por ciclo) SÓ dos (matricula,sistema) multi-ciclo,
                # para o selo "N ciclos" da aba Aderentes poder expandir os ciclos.
                # Payload enxuto: ignora quem tem 1 ciclo só.
                ciclo_ev = {}
                for r in c.execute(
                    "SELECT matricula, sistema, ciclo, tipo_evento, data_evento, ticket "
                    "FROM ciclo_eventos_acesso ORDER BY matricula, sistema, ciclo, "
                    "CASE tipo_evento WHEN 'PENDENCIA' THEN 0 WHEN 'RESOLVIDO' THEN 1 ELSE 2 END"):
                    k = (r["matricula"], r["sistema"])
                    if (ciclo_max.get(k) or 1) > 1:
                        ciclo_ev.setdefault(k, []).append({
                            "ciclo": r["ciclo"], "tipo": r["tipo_evento"],
                            "data": r["data_evento"], "ticket": r["ticket"] or ""})
                for a in aderentes:
                    mc = ciclo_max.get((a["m"], a["sis"]))
                    if mc and mc > 1:
                        a["ciclos"] = mc
                        a["eventos"] = ciclo_ev.get((a["m"], a["sis"]), [])
        except Exception as e:
            print(f"  [ciclos] enriquecimento de selos falhou: {e!r}")

        return {"kpis": kpis, "acao_dist": acao_dist, "sis_dist": sis_dist,
                "users": list(users.values()), "meta": meta, "vg": vg,
                "aderentes": aderentes}
    finally:
        c.close()


def _fmt_duracao(seg):
    """Segundos -> 'Xd Yh Zmin' (dias/horas/minutos). None/negativo -> '—'."""
    if seg is None or seg < 0:
        return "—"
    seg = int(seg)
    d, h, m = seg // 86400, (seg % 86400) // 3600, (seg % 3600) // 60
    partes = []
    if d:
        partes.append(f"{d}d")
    if h:
        partes.append(f"{h}h")
    if m:
        partes.append(f"{m}min")
    if not partes:
        partes.append("0min")   # menos de 1 minuto
    return " ".join(partes)


def _calcular_visao_geral(c, sistema=""):
    """Coleta os blocos da aba Visão Geral.

    Tudo em SQL simples sobre o banco do Processador. Quando `sistema` for
    informado, os KPIs e contagens filtram pelo mesmo escopo da aba Inclusão
    (para os números baterem).
    """
    import datetime
    out = {}
    # Filtro de sistema (mesmo escopo da grid de Inclusão / Alteração)
    whereS = " AND sistema = ?" if sistema else ""
    argS = (sistema,) if sistema else ()

    # KPIs principais — todos filtrados por `sistema` (primeira entrega = SYSTUR)
    # "Pendências Abertas" — TOTAL exibido na aba Inclusão / Alteração.
    # Fonte: bi_divergencias (validacao_acessos com ação + ACESSO_SEM_VINCULO_RH).
    # REGRA: conta USUARIOS distintos (nao acessos), igual aos cards do topo.
    try:
        # "Incluir Acesso" (SEM_ACESSO) NAO e' pendencia: fica FORA de "Pendencias
        # Abertas" e ganha contagem propria (out["incluir"]).
        out["pendentes"] = c.execute(
            f"SELECT COUNT(DISTINCT usuario) FROM bi_divergencias "
            f"WHERE resolvida=0 AND tipo<>'OK' AND tipo<>'SEM_ACESSO'{whereS}",
            argS).fetchone()[0]
        out["incluir"] = c.execute(
            f"SELECT COUNT(DISTINCT usuario) FROM bi_divergencias WHERE tipo='SEM_ACESSO'{whereS}",
            argS).fetchone()[0]
        out["ok"] = c.execute(
            f"SELECT COUNT(DISTINCT usuario) FROM bi_divergencias WHERE tipo='OK'{whereS}",
            argS).fetchone()[0]
    except Exception:
        # Fallback para banco sem `bi_divergencias`. Ele TAMBEM precisa ser
        # blindado: num banco antigo de mais (sem `validacao_acessos`) a
        # excecao vazava e derrubava a Visao Geral inteira, em vez de a tela
        # degradar mostrando zero. Achado em teste de schema aditivo.
        try:
            out["pendentes"] = c.execute(
                "SELECT COUNT(DISTINCT matricula) FROM validacao_acessos "
                "WHERE situacao_acao='PENDENTE'").fetchone()[0]
        except Exception:
            out["pendentes"] = 0
        out.setdefault("incluir", 0)
        out.setdefault("ok", 0)
    # Acessos de desligado: le da SAIDA do motor (divergencias ACESSO_DESLIGADO),
    # que ja aplica uniao matricula/CPF + filtro de status (so conta ativa). Conta
    # PESSOAS distintas (nao linhas — o SIG e' matricial e inflaria a contagem).
    # Limita ao sistema do escopo. Coerente com RegraAcessoDesligado.
    out["acessos_deslig"] = c.execute(
        f"SELECT COUNT(DISTINCT matricula) FROM divergencias "
        f"WHERE tipo='ACESSO_DESLIGADO'" + (" AND sistema = ?" if sistema else ""),
        argS).fetchone()[0]
    # Meta (KRI) do config — habilita o selo de risco no KPI. None = sem selo.
    out["acessos_desligado_meta"] = META_ACESSOS_DESLIG
    # Cobertura RH: também só do sistema do escopo. Defensivo: um banco de
    # schema antigo (pre-freeze, sem metodo_vinculacao) NAO pode zerar a Visao
    # Geral inteira — degrada so este bloco e loga (visivel no visualizador.log).
    try:
        wsis_simples = "WHERE sistema = ?" if sistema else ""
        total = c.execute(
            f"SELECT COUNT(*) FROM acessos_sistemas {wsis_simples}",
            argS).fetchone()[0]
        vinc = c.execute(
            f"SELECT COUNT(*) FROM acessos_sistemas "
            f"WHERE matricula_vinculada IS NOT NULL "
            f"AND metodo_vinculacao NOT IN ('NAO_VINCULADO','FUZZY','')"
            + (" AND sistema = ?" if sistema else ""),
            argS).fetchone()[0]
        out["cobertura_pct"] = round(100 * vinc / total, 1) if total else 0
        out["acessos_vinc"] = vinc
        out["total_acessos"] = total
    except Exception as e:
        print(f"  [vg] cobertura indisponivel ({e!r}) — banco de schema antigo?")
        out["cobertura_pct"] = 0
        out["acessos_vinc"] = 0
        out["total_acessos"] = 0
    # quarentena_ativa: preenchido no construir_db (depende do set em_quar)

    # Universo RH (banner) — RH é global (sem filtro de sistema)
    out["rh_ativos"] = c.execute("SELECT COUNT(*) FROM rh_ativos").fetchone()[0]
    out["rh_desligados"] = c.execute("SELECT COUNT(*) FROM rh_desligados").fetchone()[0]

    # Divergências por tipo (do sistema do escopo) — USUARIOS distintos por tipo,
    # da fonte unificada (bi_divergencias), excluindo OK (aderente nao e' divergencia).
    # Defensivo: banco sem bi_divergencias (ex.: chamada direta em teste) degrada
    # so este bloco, sem derrubar a Visao Geral inteira.
    try:
        out["div_tipos"] = {r[0]: r[1] for r in c.execute(
            "SELECT tipo, COUNT(DISTINCT usuario) FROM bi_divergencias "
            "WHERE tipo<>'OK'" + (" AND sistema = ?" if sistema else "")
            + " GROUP BY tipo", argS)}
    except Exception:
        out["div_tipos"] = {}
    # Concentração por sistema. RESPEITA o escopo configurado (visualizador/sistema):
    # com escopo SYSTUR mostra SO SYSTUR (requisito da 1a entrega = nada alem de
    # SYSTUR); com escopo vazio (multi-sistema futuro) mostra TODOS. O painel
    # continua multi-sistema-ready — quem manda e' o escopo, nao um filtro fixo.
    try:
        out["div_sistemas"] = {r[0]: r[1] for r in c.execute(
            "SELECT sistema, COUNT(DISTINCT usuario) FROM bi_divergencias "
            "WHERE tipo<>'OK'" + (" AND sistema = ?" if sistema else "")
            + " GROUP BY sistema ORDER BY 2 DESC", argS)}
    except Exception:
        out["div_sistemas"] = {}

    # Card 24 — TRANSFERIDOS na Visao Geral (espelha o que ja existe p/ desligados).
    # Pessoas com acesso a revisar (saida do motor) + o numero acionavel do Card 23:
    # acessos que so faziam sentido na funcao/equipe anterior.
    out["transf_pessoas"] = 0
    out["transf_sobrou"] = 0
    out["transf_movimentos"] = 0
    try:
        out["transf_pessoas"] = c.execute(
            "SELECT COUNT(DISTINCT matricula) FROM divergencias "
            "WHERE tipo='ACESSO_TRANSFERIDO'" + (" AND sistema = ?" if sistema else ""),
            argS).fetchone()[0] or 0
    except Exception:
        pass
    for tabela, chave, sql in (
            ("revalidacao_transferido", "transf_sobrou",
             "SELECT COUNT(*) FROM revalidacao_transferido WHERE situacao='SOBROU'"
             + (" AND sistema = ?" if sistema else "")),
            ("transferidos", "transf_movimentos",
             "SELECT COUNT(*) FROM transferidos")):
        try:
            if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                         (tabela,)).fetchone():
                arg = argS if ("?" in sql) else []
                out[chave] = c.execute(sql, arg).fetchone()[0] or 0
        except Exception:
            pass

    # Top 10 desligados recentes ainda com acesso ativo NO SISTEMA do escopo.
    # Fonte = saida do motor (divergencias ACESSO_DESLIGADO): ja e' uniao
    # matricula/CPF + so conta ativa. 'perfis' = nº de acessos ativos flagados.
    hoje = datetime.date.today()
    top = []
    wsis_top = "AND x.sistema = ?" if sistema else ""
    # Blindado como os demais blocos: banco de schema anterior (sem alguma das
    # colunas do JOIN) fazia esta consulta levantar e derrubar a Visao Geral
    # INTEIRA, em vez de o bloco vir vazio. Achado em teste de schema aditivo.
    try:
        linhas_top = c.execute(f"""
            SELECT d.nome, d.data_desligamento, d.cargo_descricao,
                   COUNT(DISTINCT x.sistema) AS sistemas, COUNT(*) AS perfis
            FROM rh_desligados d
            JOIN divergencias x ON x.matricula = d.matricula AND x.tipo='ACESSO_DESLIGADO'
            WHERE d.data_desligamento IS NOT NULL {wsis_top}
            GROUP BY d.matricula
            ORDER BY d.data_desligamento DESC LIMIT 10
        """, argS).fetchall()
    except Exception as e:
        print(f"  [vg] top de desligados indisponivel ({e!r}) — banco de schema antigo?")
        linhas_top = []
    for r in linhas_top:
        try:
            dias = (hoje - datetime.date.fromisoformat(r[1])).days
        except Exception:
            dias = None
        top.append({"nome": r[0], "data": r[1], "dias": dias,
                    "cargo": r[2], "sistemas": r[3], "perfis": r[4]})
    out["top_urgentes"] = top

    # Aging: faixa etária das pendências por USUARIO (nao por acesso). Cada
    # pessoa entra uma vez, classificada pela sua pendência MAIS ANTIGA — assim a
    # soma do aging bate com o nº de usuários pendentes (consistente com os cards).
    _pend_idade = {}  # matricula -> maior idade (dias) entre suas pendências
    for mat, dtp in c.execute("""
        SELECT matricula, dt_processamento FROM validacao_acessos
        WHERE situacao_acao='PENDENTE' AND dt_processamento IS NOT NULL
    """):
        try:
            dt = datetime.datetime.fromisoformat(str(dtp)[:19]).date()
            dias = (hoje - dt).days
        except Exception:
            continue
        if mat not in _pend_idade or dias > _pend_idade[mat]:
            _pend_idade[mat] = dias
    aging = {"0-7": 0, "8-30": 0, "31-90": 0, "90+": 0}
    for dias in _pend_idade.values():
        if dias <= 7: aging["0-7"] += 1
        elif dias <= 30: aging["8-30"] += 1
        elif dias <= 90: aging["31-90"] += 1
        else: aging["90+"] += 1
    out["aging"] = aging

    # Movimentação RH (CDC últimos 30 dias). Sem CDC = zeros (placeholder).
    mov = {"admissoes": 0, "alteracoes": 0, "desligamentos": 0}
    try:
        d_corte = (hoje - datetime.timedelta(days=30)).isoformat()
        rows = c.execute("""
            SELECT entidade, tipo_mudanca, COUNT(*)
            FROM historico
            WHERE date(data_snapshot) >= ?
            GROUP BY entidade, tipo_mudanca
        """, (d_corte,)).fetchall()
        for ent, tipo, n in rows:
            if ent == "RH_ATIVO" and tipo == "NOVO":
                mov["admissoes"] += n
            elif ent == "RH_ATIVO" and tipo == "ALTERADO":
                mov["alteracoes"] += n
            elif ent == "RH_DESLIGADO" and tipo == "NOVO":
                mov["desligamentos"] += n
    except Exception:
        pass  # tabela historico pode nem existir em banco antigo
    out["mov_rh"] = mov

    # Chamados — janela movel de ULTIMOS N dias (VG_JANELA_DIAS), nao
    # mes-calendario: na virada do mes (dia 1) o calendario zerava e a tela
    # vinha vazia. 30 dias terminando hoje sempre mostra o recente. (Mesma
    # janela da Movimentação RH.) Parametrizar a janela: ver docs/ROADMAP_VISAO_GERAL.
    # Chamados contam USUARIOS distintos a tratar (nao acessos): o que importa e'
    # quantas pessoas preciso tratar, nao quantos acessos cada uma tem.
    chamados = {"identificados": 0, "resolvidos": 0, "aderentes": 0, "tempo_medio_dias": 0}
    corte = (hoje - datetime.timedelta(days=VG_JANELA_DIAS)).isoformat()
    try:
        chamados["identificados"] = c.execute(
            "SELECT COUNT(DISTINCT matricula) FROM validacao_acessos "
            "WHERE situacao_acao='PENDENTE' AND date(dt_processamento) >= ?", (corte,)
        ).fetchone()[0]
    except Exception:
        pass
    try:
        chamados["resolvidos"] = c.execute(
            "SELECT COUNT(DISTINCT registro_id) FROM resolucoes "
            "WHERE date(resolvido_em) >= ?", (corte,)
        ).fetchone()[0]
    except Exception:
        pass  # tabela resolucoes ainda nao existe em banco virgem
    try:
        # Aderentes: viraram conforme na janela (3o estagio do ciclo). Inclui
        # quem foi liberado FORA do sistema (P->A direto, sem ticket).
        chamados["aderentes"] = c.execute(
            "SELECT COUNT(DISTINCT matricula) FROM ciclo_vida_acesso "
            "WHERE dt_aderente IS NOT NULL AND date(dt_aderente) >= ?", (corte,)
        ).fetchone()[0]
    except Exception:
        pass  # tabela ciclo_vida_acesso pode nao existir em banco antigo
    out["chamados"] = chamados

    # Tempo de tratamento (ciclo de vida).
    # TOTAL = pendencia -> aderencia (liberacao do acesso), contando TAMBEM os
    # casos resolvidos FORA do sistema (P->A direto, sem ticket): nao podemos
    # perder esse tempo. SEGMENTOS (P->R e R->A) so existem p/ ciclos resolvidos
    # PELO sistema (com ticket) — alimentam a barra segmentada quando houver.
    filtro_sis = " AND sistema = ?" if sistema else ""
    par_sis = (sistema,) if sistema else ()
    # Cada etapa e' medida INDEPENDENTE, na sua propria populacao — nao exigimos
    # o ciclo completo (P->R->A). Assim um RESOLVIDO que ainda nao virou aderente
    # aparece em P->R (antes caia num limbo: nem no total P->A, nem nos segmentos),
    # e o P->A (total) e' um item proprio (inclui o P->A direto, sem ticket).
    tempos = {"total": "—", "pend_resolv": "—", "resolv_ader": "—",
              "seg_pr": 0, "seg_ra": 0, "seg_pa": 0, "n": 0, "n_pr": 0, "n_ra": 0}
    try:
        # Usa o log de eventos SÓ se ele tiver dados (banco antigo/virgem cai no
        # fallback do ciclo_vida). Blindado contra a tabela nao existir.
        try:
            _tem_ev = c.execute("SELECT 1 FROM ciclo_eventos_acesso LIMIT 1").fetchone()
        except Exception:
            _tem_ev = None
        if _tem_ev:
            # Tempos por CICLO a partir do LOG DE EVENTOS: pendencia->resolvido->
            # aderente DENTRO de cada (matricula, sistema, ciclo). Reflete
            # REABERTURAS (cada ciclo mede o proprio tempo) e nao depende do
            # first-wins de ciclo_vida (onde, num reprocesso unico, a linha tem so
            # 1 carimbo — pendencia OU aderente — e nunca fecha um ciclo).
            wsis = " WHERE sistema = ?" if sistema else ""
            row = c.execute(
                "WITH ev AS ("
                " SELECT matricula, sistema, ciclo,"
                "  MAX(CASE WHEN tipo_evento='PENDENCIA' THEN data_evento END) dp,"
                "  MAX(CASE WHEN tipo_evento='RESOLVIDO' THEN data_evento END) dr,"
                "  MAX(CASE WHEN tipo_evento='ADERENTE'  THEN data_evento END) da"
                " FROM ciclo_eventos_acesso" + wsis +
                " GROUP BY matricula, sistema, ciclo)"
                " SELECT"
                "  AVG(CASE WHEN dp IS NOT NULL AND da IS NOT NULL AND da>=dp THEN (julianday(da)-julianday(dp))*86400.0 END),"
                "  SUM(CASE WHEN dp IS NOT NULL AND da IS NOT NULL AND da>=dp THEN 1 ELSE 0 END),"
                "  AVG(CASE WHEN dp IS NOT NULL AND dr IS NOT NULL AND dr>=dp THEN (julianday(dr)-julianday(dp))*86400.0 END),"
                "  SUM(CASE WHEN dp IS NOT NULL AND dr IS NOT NULL AND dr>=dp THEN 1 ELSE 0 END),"
                "  AVG(CASE WHEN dr IS NOT NULL AND da IS NOT NULL AND da>=dr THEN (julianday(da)-julianday(dr))*86400.0 END),"
                "  SUM(CASE WHEN dr IS NOT NULL AND da IS NOT NULL AND da>=dr THEN 1 ELSE 0 END)"
                " FROM ev", par_sis).fetchone()
            seg_pa, n_pa = (row[0] or 0), (row[1] or 0)
            seg_pr, n_pr = (row[2] or 0), (row[3] or 0)
            seg_ra, n_ra = (row[4] or 0), (row[5] or 0)
        else:
            # fallback (banco antigo sem o log): ciclo_vida_acesso (1 ciclo)
            rpa = c.execute(
                "SELECT AVG((julianday(dt_aderente)-julianday(dt_pendencia))*86400.0), COUNT(*) "
                "FROM ciclo_vida_acesso "
                "WHERE dt_pendencia IS NOT NULL AND dt_aderente IS NOT NULL "
                "  AND dt_aderente >= dt_pendencia" + filtro_sis, par_sis).fetchone()
            seg_pa, n_pa = (rpa[0] or 0), (rpa[1] or 0)
            rpr = c.execute(
                "SELECT AVG((julianday(dt_resolvido)-julianday(dt_pendencia))*86400.0), COUNT(*) "
                "FROM ciclo_vida_acesso "
                "WHERE dt_pendencia IS NOT NULL AND dt_resolvido IS NOT NULL "
                "  AND dt_resolvido >= dt_pendencia" + filtro_sis, par_sis).fetchone()
            seg_pr, n_pr = (rpr[0] or 0), (rpr[1] or 0)
            rra = c.execute(
                "SELECT AVG((julianday(dt_aderente)-julianday(dt_resolvido))*86400.0), COUNT(*) "
                "FROM ciclo_vida_acesso "
                "WHERE dt_resolvido IS NOT NULL AND dt_aderente IS NOT NULL "
                "  AND dt_aderente >= dt_resolvido" + filtro_sis, par_sis).fetchone()
            seg_ra, n_ra = (rra[0] or 0), (rra[1] or 0)
        tempos.update({
            "seg_pr": seg_pr, "seg_ra": seg_ra, "seg_pa": seg_pa,
            "n": n_pa, "n_pr": n_pr, "n_ra": n_ra,
            "pend_resolv": _fmt_duracao(seg_pr) if n_pr else "—",
            "resolv_ader": _fmt_duracao(seg_ra) if n_ra else "—",
            "total": _fmt_duracao(seg_pa) if n_pa else "—",
        })
    except Exception:
        pass
    out["tempos"] = tempos

    return out


def enviar_quarentena(usuarios, origem="Inclusão / Alteração",
                      dias=None, ticket="", titulo="", motivo=""):
    """Grava uma interacao ENVIAR (QUARENTENA) na rede para cada usuario novo,
    com o prazo (dias) e os dados do formulario. data_fim = inicio + dias.
    Nao escreve na tabela local — a tabela e' snapshot do Processador."""
    try:
        dias = int(dias)
    except (TypeError, ValueError):
        dias = 0
    if dias <= 0:
        return {"erro": "Informe a quantidade de dias (maior que zero)."}
    if dias > QUAR_MAX_DIAS:
        return {"erro": f"O limite da quarentena é {QUAR_MAX_DIAS} dias."}
    titulo = str(titulo or "").strip()
    if not titulo:
        return {"erro": "O título/descrição é obrigatório."}
    ticket = str(ticket or "").strip()
    motivo = str(motivo or "").strip()
    agora = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    fim = (datetime.now() + timedelta(days=dias)).strftime("%Y-%m-%d")
    # ja em quarentena: snapshot do DB local + interacoes vivas da rede
    c = conn_ro()
    try:
        ja = {r[0] for r in c.execute("SELECT usuario FROM quarentena")}
    finally:
        c.close()
    for rid, it in _quarentena_viva().items():
        if it.get("acao") == "ENVIAR":
            ja.add(rid)
        elif it.get("acao") == "RESOLVER":
            ja.discard(rid)
    novos = 0
    for u in usuarios:
        if u in ja:
            continue
        # chave composta (retorno Bruna): "usuario##sistema" = so aquele sistema;
        # "usuario##sistema##perfil" = so aquele ACESSO. Sem ## = pessoa inteira.
        _p = u.split("##")
        usr_real = _p[0]
        sis_alvo = _p[1] if len(_p) > 1 else ""
        perf_alvo = _p[2] if len(_p) > 2 else ""
        nome, sis, _ = _meta_divergencia(usr_real)
        _interacao_gravar({
            "tipo_interacao": "QUARENTENA", "registro_id": u, "acao": "ENVIAR",
            "usuario": USUARIO, "data_acao": agora, "origem": origem,
            "nome": nome, "sistema": sis_alvo or sis, "perfil": perf_alvo,
            "dias": dias, "ticket": ticket, "titulo": titulo, "motivo": motivo,
        })
        ja.add(u)
        novos += 1
    print(f"  [QUARENTENA] +{novos} ENVIAR por {USUARIO} "
          f"({dias}d, ticket='{ticket}') (ignorados {len(usuarios)-novos} ja ativos)")
    return {"novos": novos, "total": len(ja), "data_fim": fim}


def listar_desligados():
    """Aba Desligados: uma linha por PESSOA desligada, com o veredito de acesso.

    Duas situacoes (pedido da area):
      - "Tratar" — ainda tem acesso ativo em algum sistema (precisa revogar);
      - "OK"     — nenhum acesso ativo (situacao correta pos-desligamento).

    Fonte do acesso = SAIDA do motor (`divergencias` tipo ACESSO_DESLIGADO), a
    mesma da Visao Geral. NAO recalcula a regra aqui: o motor ja aplica a uniao
    matricula/CPF e o filtro de status (so conta conta ATIVA). Duas leituras da
    mesma pergunta divergiriam com o tempo.

    Respeita o SISTEMA do escopo (config), como as demais grids.
    """
    c = conn_ro()
    try:
        arg = [SISTEMA] if SISTEMA else []
        # Acessos vivos por matricula desligada (pode haver varios sistemas).
        por_mat = {}
        try:
            for r in c.execute(
                    "SELECT matricula, sistema, usuario, perfil_encontrado, "
                    "       data_identificacao, resolvida "
                    "FROM divergencias WHERE tipo='ACESSO_DESLIGADO'"
                    + (" AND sistema = ?" if SISTEMA else ""), arg):
                por_mat.setdefault(r["matricula"] or "", []).append({
                    "sis": r["sistema"] or "",
                    "login": r["usuario"] or "",
                    "perfil": r["perfil_encontrado"] or "",
                    # data crua (ISO): quem formata é o fmtDH do painel
                    "dt": r["data_identificacao"] or "",
                    "resolvida": bool(r["resolvida"]),
                })
        except Exception as e:
            print(f"  [deslig] divergencias indisponivel: {e!r}")

        out = []
        try:
            for r in c.execute(
                    "SELECT matricula, nome, cpf, cargo_descricao, departamento, "
                    "       COALESCE(centro_custo_codigo,'') cc_cod, "
                    "       COALESCE(centro_custo_nome,'')   cc_nome, "
                    "       data_desligamento, email, empresa "
                    "FROM rh_desligados ORDER BY data_desligamento DESC"):
                mat = r["matricula"] or ""
                acessos = por_mat.pop(mat, [])
                out.append({
                    "m": mat, "n": r["nome"] or "", "cpf": r["cpf"] or "",
                    "cargo": r["cargo_descricao"] or "", "depto": r["departamento"] or "",
                    "cc": (r["cc_cod"] + " - " + r["cc_nome"]).strip(" -"),
                    "dt_deslig": r["data_desligamento"] or "",
                    "email": r["email"] or "", "empresa": r["empresa"] or "",
                    "acessos": acessos,
                    "sit": "Tratar" if acessos else "OK",
                })
        except Exception as e:
            print(f"  [deslig] rh_desligados indisponivel: {e!r}")

        # Sobra do motor: acesso marcado como de desligado cuja matricula nao
        # esta (mais) no rh_desligados — a pessoa sumiu da base de RH mas o
        # acesso segue vivo. Nao pode ser engolido: e' justamente o caso de
        # risco. Entra como "Tratar" com os campos de RH vazios.
        for mat, acessos in por_mat.items():
            out.append({
                "m": mat, "n": (acessos[0].get("login") or ""), "cpf": "",
                "cargo": "", "depto": "", "cc": "", "dt_deslig": "",
                "email": "", "empresa": "", "acessos": acessos,
                "sit": "Tratar", "sem_rh": True,
            })
    finally:
        c.close()

    # Tratamentos sob ticket (mesmo padrao da resolucao de pendencia): quem foi
    # tratado ganha `tratado`+`tratamento` e some do "Tratar" pendente. O acesso
    # segue existindo ate o proximo reprocesso revogar — mas ja foi encaminhado.
    tratamentos = _tratamentos_desligado_mesclados()
    for d in out:
        t = tratamentos.get(str(d["m"]))
        if t and d["sit"] == "Tratar":
            d["tratado"] = True
            d["tratamento"] = {"ticket": t["ticket"], "ticket_url": t["ticket_url"],
                               "descricao": t["descricao"], "motivo": t["motivo"],
                               "por": t["por"], "em": t["em"]}

    # Chamado JA aberto e tratativa ainda NAO concluida: o analista foi
    # interrompido entre uma coisa e outra. A linha precisa dizer isso — sem
    # isto ela volta a parecer intocada e o proximo abre um segundo chamado
    # para o mesmo caso. O formulario usa `chamado` para travar a abertura.
    abertos = chamados_abertos()
    for d in out:
        ch = abertos.get(str(d["m"]))
        if ch and not d.get("tratado"):
            d["chamado"] = ch

    # KPIs: "Tratar" = com acesso e AINDA nao tratado; "tratado" e' categoria a
    # parte (encaminhado). "OK" segue = sem acesso.
    tratar = sum(1 for d in out if d["sit"] == "Tratar" and not d.get("tratado"))
    tratados = sum(1 for d in out if d.get("tratado"))
    ok = sum(1 for d in out if d["sit"] == "OK")
    # `jira` diz a tela se o botao "Abrir chamado" pode habilitar. Vem do
    # servidor porque so ele sabe se ha credencial — o front nunca ve o token.
    return {"lista": out, "kpis": {"tratar": tratar, "tratados": tratados,
                                   "ok": ok, "total": len(out)},
            "jira": jira_habilitado()}


import re as _re_transf
_RE_CAMPOS = _re_transf.compile(r"Mudança de (.+?) —")


def _transferidos_depara(c, matriculas):
    """Le a tabela `transferidos` (de/para do movimento) para as matriculas dadas.

    Devolve {matricula: {"campos": str, "dt": str, "pares": [{"campo","de","para"}]}}.
    So entram os campos que REALMENTE mudaram — o motor congela o par inteiro, mas
    mostrar "cargo: X -> X" seria ruido. Banco sem a tabela (Processador anterior
    a esta versao) devolve {} e a aba segue funcionando sem o par."""
    if not matriculas:
        return {}
    try:
        tem = c.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                        "AND name='transferidos'").fetchone()
        if not tem:
            return {}
    except Exception:
        return {}
    campos = (("cargo", "cargo_anterior", "cargo_atual"),
              ("departamento", "departamento_anterior", "departamento_atual"),
              ("centro de custo", "centro_custo_anterior", "centro_custo_atual"),
              ("gestor", "gestor_anterior", "gestor_atual"))
    out = {}
    try:
        qm = ",".join("?" * len(matriculas))
        for r in c.execute(
                "SELECT matricula, campos_mudados, data_transferencia, "
                "cargo_anterior, cargo_atual, departamento_anterior, departamento_atual, "
                "centro_custo_anterior, centro_custo_atual, gestor_anterior, gestor_atual "
                f"FROM transferidos WHERE matricula IN ({qm})", list(matriculas)):
            pares = []
            for rotulo, col_ant, col_atu in campos:
                de, para = (r[col_ant] or ""), (r[col_atu] or "")
                if de != para:
                    pares.append({"campo": rotulo, "de": de, "para": para})
            out[r["matricula"]] = {
                "campos": r["campos_mudados"] or "",
                "dt": r["data_transferencia"] or "",
                "pares": pares,
            }
    except Exception as e:
        print(f"  [transf] de/para indisponivel: {e!r}")
    return out


def _revalidacao_transferidos(c, matriculas):
    """Card 23 — leitura da `revalidacao_transferido` (o veredito por acesso).

    Devolve {matricula: {"resumo": {...}, "sobrou": [...], "falta": [...],
                         "pares": (antes, depois)}}.

    SOBROU e' o sinal novo — nenhuma outra regra o enxerga. FALTA e' CONTEXTO:
    a inclusao ja aparece na aba de pendencias pela regra geral (e la ela passa
    pelo filtro B1 de adesao, que aqui nao se aplica); repetir como pendencia
    inflaria a fila, que foi exatamente a reclamacao da area.
    """
    if not matriculas:
        return {}
    try:
        tem = c.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                        "AND name='revalidacao_transferido'").fetchone()
        if not tem:
            return {}
        qm = ",".join("?" * len(matriculas))
        linhas = c.execute(
            "SELECT matricula, sistema, perfil, situacao, origem, pares_antes,"
            " pares_depois FROM revalidacao_transferido "
            f"WHERE matricula IN ({qm})"
            + (" AND sistema = ?" if SISTEMA else ""),
            list(matriculas) + ([SISTEMA] if SISTEMA else [])).fetchall()
    except Exception as e:
        print(f"  [transf] revalidacao indisponivel: {e!r}")
        return {}
    out = {}
    for r in linhas:
        d = out.setdefault(r["matricula"], {
            "resumo": {"MANTEM": 0, "SOBROU": 0, "EXCESSO": 0, "FALTA": 0},
            "sobrou": [], "falta": [], "pares": None})
        sit = r["situacao"]
        d["resumo"][sit] = d["resumo"].get(sit, 0) + 1
        if sit in ("SOBROU", "FALTA"):
            d[sit.lower()].append({"sis": r["sistema"], "perfil": r["perfil"],
                                   "origem": r["origem"] or ""})
        if r["pares_antes"] is not None and d["pares"] is None:
            d["pares"] = [r["pares_antes"], r["pares_depois"]]
    return out


def listar_transferidos():
    """Aba Transferidos: pessoas que MUDARAM cargo/CC/departamento/gestor (detectado
    do historico do RH) e cujos acessos precisam de REVISÃO. Fonte = saida do motor
    (`divergencias` tipo ACESSO_TRANSFERIDO), a mesma da regra — NÃO recalcula aqui.

    Situações: "Revisar" (acesso pendente de revisão) × "Tratado" (revisado sob
    ticket). Sem janela: fica em Revisar até tratar. Respeita o SISTEMA do escopo.
    """
    c = conn_ro()
    try:
        arg = [SISTEMA] if SISTEMA else []
        por_mat = {}
        campos_por_mat = {}
        try:
            for r in c.execute(
                    "SELECT matricula, sistema, usuario, perfil_encontrado, "
                    "       data_identificacao, descricao "
                    "FROM divergencias WHERE tipo='ACESSO_TRANSFERIDO'"
                    + (" AND sistema = ?" if SISTEMA else ""), arg):
                mat = r["matricula"] or ""
                por_mat.setdefault(mat, []).append({
                    "sis": r["sistema"] or "", "login": r["usuario"] or "",
                    "perfil": r["perfil_encontrado"] or "",
                    "dt": r["data_identificacao"] or "",
                })
                # "Mudança de cargo, gestor — ..." -> extrai os campos que mudaram
                if mat not in campos_por_mat:
                    m = _RE_CAMPOS.search(r["descricao"] or "")
                    campos_por_mat[mat] = m.group(1) if m else ""
        except Exception as e:
            print(f"  [transf] divergencias indisponivel: {e!r}")

        out = []
        # dados de RH (ativos) por matricula p/ enriquecer nome/cargo/CC/gestor
        rh = {}
        if por_mat:
            try:
                qm = ",".join("?" * len(por_mat))
                for r in c.execute(
                        "SELECT matricula, nome, cargo_descricao, departamento, "
                        "COALESCE(centro_custo_codigo,'') cc, COALESCE(gestor,'') gestor "
                        f"FROM rh_ativos WHERE matricula IN ({qm})", list(por_mat)):
                    rh[r["matricula"]] = r
            except Exception:
                pass
        # de -> para do movimento (tabela `transferidos`, gravada pelo motor).
        # Banco de Processador antigo nao tem a tabela: o painel so nao mostra o
        # par, o resto da aba segue igual.
        depara = _transferidos_depara(c, list(por_mat))
        reval = _revalidacao_transferidos(c, list(por_mat))
        for mat, acessos in por_mat.items():
            info = rh.get(mat)
            dp = depara.get(mat) or {}
            rv = reval.get(mat) or {}
            out.append({
                "reval": rv.get("resumo"),
                "sobrou": rv.get("sobrou", []),
                "falta": rv.get("falta", []),
                "pares": rv.get("pares"),
                "m": mat,
                "n": (info["nome"] if info else "") or (acessos[0].get("login") or ""),
                "cargo": (info["cargo_descricao"] if info else "") or "",
                "depto": (info["departamento"] if info else "") or "",
                "cc": (info["cc"] if info else "") or "",
                "gestor": (info["gestor"] if info else "") or "",
                "campos": campos_por_mat.get(mat, "") or dp.get("campos", ""),
                "de_para": dp.get("pares", []),
                "dt_mov": dp.get("dt", ""),
                "acessos": acessos,
                "sit": "Revisar",
                # explicito nas DUAS origens de linha: quem consome a lista nao
                # precisa saber de onde ela veio para saber o formato
                "sem_acesso": False,
            })
    finally:
        c.close()

    # Quem se MOVEU mas nao tem acesso em sistema nenhum: nao gera divergencia
    # (nao ha o que revisar) e, ate aqui, sumia do painel inteiro — a pessoa
    # mudou de cargo/gestor e ninguem via. Entra com sit="Sem acesso", fora dos
    # KPIs de revisao: e' movimentacao para conhecimento, nao fila de trabalho.
    out += _transferidos_sem_acesso(por_mat)

    tratamentos = _tratamentos_transferido_mesclados()
    for d in out:
        t = tratamentos.get(str(d["m"]))
        if t:
            d["tratado"] = True
            d["tratamento"] = {"ticket": t["ticket"], "ticket_url": t["ticket_url"],
                               "descricao": t["descricao"], "motivo": t["motivo"],
                               "por": t["por"], "em": t["em"]}
    com_acesso = [d for d in out if not d.get("sem_acesso")]
    revisar = sum(1 for d in com_acesso if not d.get("tratado"))
    tratados = sum(1 for d in com_acesso if d.get("tratado"))
    # Card 23: quantos acessos sobraram da funcao anterior (o sinal acionavel)
    sobrou = sum(len(d.get("sobrou") or []) for d in out)
    pessoas_sobrou = sum(1 for d in out if d.get("sobrou"))
    return {"lista": out,
            "kpis": {"revisar": revisar, "tratados": tratados,
                     "total": len(com_acesso),
                     "sem_acesso": len(out) - len(com_acesso),
                     "sobrou": sobrou, "pessoas_sobrou": pessoas_sobrou}}


def _transferidos_sem_acesso(ja_listados):
    """Movimentos gravados em `transferidos` que NAO viraram linha da aba porque
    a pessoa nao tem acesso em sistema nenhum. Respeita o escopo por sistema:
    com <visualizador><sistema> definido, a aba e' daquele sistema — listar quem
    nao tem acesso nenhum ali seria ruido."""
    if SISTEMA:
        return []
    c = conn_ro()
    try:
        tem = c.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                        "AND name='transferidos'").fetchone()
        if not tem:
            return []
        linhas = c.execute(
            "SELECT matricula, nome, campos_mudados, data_transferencia, "
            "cargo_atual, centro_custo_atual, gestor_atual FROM transferidos").fetchall()
        mats = [r["matricula"] for r in linhas if r["matricula"] not in ja_listados]
        depara = _transferidos_depara(c, mats)
        # Estas pessoas nao tem acesso, mas PODEM ter FALTA (o que a funcao nova
        # espera e elas nao tem). Sem isto a linha sairia com formato diferente
        # das outras — e a informacao mais util sobre elas se perderia.
        reval = _revalidacao_transferidos(c, mats)
    except Exception as e:
        print(f"  [transf] sem-acesso indisponivel: {e!r}")
        return []
    finally:
        c.close()
    out = []
    for r in linhas:
        mat = r["matricula"]
        if mat in ja_listados:
            continue
        dp = depara.get(mat) or {}
        rv = reval.get(mat) or {}
        out.append({
            "m": mat, "n": r["nome"] or mat,
            "cargo": r["cargo_atual"] or "", "depto": "",
            "cc": r["centro_custo_atual"] or "", "gestor": r["gestor_atual"] or "",
            "campos": r["campos_mudados"] or "",
            "de_para": dp.get("pares", []),
            "dt_mov": r["data_transferencia"] or "",
            # mesmo formato das demais linhas da aba
            "reval": rv.get("resumo"), "sobrou": rv.get("sobrou", []),
            "falta": rv.get("falta", []), "pares": rv.get("pares"),
            "acessos": [], "sit": "Sem acesso", "sem_acesso": True,
        })
    return out


def _tratamento_transferido_vivo(interacoes=None):
    atual = {}
    for it in (interacoes if interacoes is not None else _interacoes_ler()):
        if it.get("tipo_interacao") != "TRATAMENTO_TRANSFERIDO":
            continue
        rid = it.get("registro_id")
        if not rid:
            continue
        ant = atual.get(rid)
        if ant is None or str(it.get("data_acao", "")) >= str(ant.get("data_acao", "")):
            atual[rid] = it
    return atual


def _tratamentos_transferido_db():
    c = conn_ro()
    try:
        tem = c.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                        "AND name='tratamentos_transferido'").fetchone()
        if not tem:
            return {}
        out = {}
        for r in c.execute(
                "SELECT registro_id,ticket,ticket_url,descricao,motivo,"
                "tratado_por,tratado_em FROM tratamentos_transferido"):
            out[r["registro_id"]] = {
                "ticket": r["ticket"] or "", "ticket_url": r["ticket_url"] or "",
                "descricao": r["descricao"] or "", "motivo": r["motivo"] or "",
                "por": r["tratado_por"] or "", "em": r["tratado_em"] or ""}
        return out
    except Exception:
        return {}
    finally:
        c.close()


def _tratamentos_transferido_mesclados(interacoes=None):
    out = dict(_tratamentos_transferido_db())
    for rid, it in _tratamento_transferido_vivo(interacoes).items():
        out[str(rid)] = {
            "ticket": it.get("ticket") or "", "ticket_url": it.get("ticket_url") or "",
            "descricao": it.get("descricao") or "", "motivo": it.get("motivo") or "",
            "por": it.get("usuario") or "",
            "em": (it.get("data_acao") or "").replace("T", " ")}
    return out


def tratar_transferido(registro_id, ticket, ticket_url="", descricao="", motivo=""):
    """Grava interacao TRATAMENTO_TRANSFERIDO (mesmo padrao do desligado): registra
    a revisao de acesso pos-mudanca. Ticket OPCIONAL desde 05/08 — ver
    `_validar_tratativa`. registro_id = matricula."""
    rid = str(registro_id or "").strip()
    tk = str(ticket or "").strip()
    motivo = str(motivo or "").strip()
    if not rid or not str(descricao or "").strip():
        return 0
    nome = ""
    try:
        c = conn_ro()
        try:
            r = c.execute("SELECT nome FROM rh_ativos WHERE matricula=?", [rid]).fetchone()
            nome = (r["nome"] if r else "") or ""
        finally:
            c.close()
    except Exception:
        pass
    _interacao_gravar({
        "tipo_interacao": "TRATAMENTO_TRANSFERIDO", "registro_id": rid, "acao": "TRATAR",
        "ticket": tk, "ticket_url": str(ticket_url or "").strip(),
        "descricao": str(descricao or "").strip(), "motivo": motivo,
        "nome": nome, "usuario": USUARIO,
        "data_acao": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    })
    print(f"  [TRAT_TRANSF] {rid} ticket={tk} por {USUARIO}")
    return 1


def listar_quarentena():
    """{ativas, historico}: snapshot do DB local sobreposto pelas interacoes
    vivas da rede (ENVIAR entra em ativas, RESOLVER move para historico)."""
    sweep_expiradas()
    hoje = datetime.now().strftime("%Y-%m-%d")
    c = conn_ro()
    try:
        ativas = {r["usuario"]: dict(r) for r in c.execute(
            "SELECT id,usuario,nome_usuario,sistema,origem,data_inicio,"
            "data_fim,dias,ticket,titulo,motivo_entrada,criado_por "
            "FROM quarentena ORDER BY data_fim")}
        historico = [dict(r) for r in c.execute(
            "SELECT id,usuario,nome_usuario,sistema,origem,data_inicio,"
            "data_fim,data_saida,motivo,dias,ticket,titulo,motivo_entrada,"
            "encerrado_por,movido_em "
            "FROM quarentena_historico ORDER BY movido_em DESC")]
    finally:
        c.close()

    # Le as interacoes 1x: estado vivo (ultima acao por rid) + o ENVIAR mais
    # recente por rid (traz os dados de ENTRADA — necessario p/ o historico de
    # uma quarentena que entrou e saiu antes de o Processador dobrar).
    _inter = _interacoes_ler()
    _envios = {}
    for it in _inter:
        if it.get("tipo_interacao") == "QUARENTENA" and it.get("acao") == "ENVIAR":
            erid = it.get("registro_id")
            if erid and (erid not in _envios or
                         str(it.get("data_acao", "")) >= str(_envios[erid].get("data_acao", ""))):
                _envios[erid] = it
    for rid, it in _quarentena_viva(_inter).items():
        acao = it.get("acao")
        if acao == "ENVIAR":
            if rid not in ativas:
                ativas[rid] = _sintetizar_ativa(rid, it)
        elif acao == "RESOLVER":
            anterior = ativas.pop(rid, None)
            if anterior is None and rid in _envios:
                anterior = _sintetizar_ativa(rid, _envios[rid])   # carrega entrada
            historico.insert(0, _sintetizar_historico(rid, it, anterior))

    lista = list(ativas.values())
    for r in lista:
        r["id"] = r["usuario"]                       # id uniforme = registro_id
        r["dias_restantes"] = max(0, _dias(hoje, r.get("data_fim", "")))
    for r in historico:
        r["periodo_dias"] = _dias(r.get("data_inicio", ""), r.get("data_saida", ""))

    # A chave pode ser composta (usuario##sistema##perfil): a tela mostra a
    # MATRICULA na coluna de usuario + o escopo/perfil do que foi quarentenado.
    # Sem isso a coluna sairia com a chave crua e o vinculo nao casaria no RH.
    for r in lista + historico:
        _mat, _sis, _perf = _partes_chave(r.get("usuario") or r.get("id") or "")
        r["id"] = r.get("id") or r.get("usuario")
        r["usuario"] = _mat
        r["sistema"] = r.get("sistema") or _sis
        r["perfil"] = r.get("perfil") or _perf
        r["escopo"] = _escopo_chave(r["id"])

    # Vinculo (Funcionario/Terceiro) por usuario (matricula) — lookup em rh_ativos
    _mats = {r["usuario"] for r in lista} | {r["usuario"] for r in historico}
    _vinc = {}
    if _mats:
        cv = conn_ro()
        try:
            qm = ",".join("?" * len(_mats))
            for row in cv.execute(
                "SELECT matricula, COALESCE(tipo_vinculo,'FUNCIONARIO') tv "
                f"FROM rh_ativos WHERE matricula IN ({qm})", list(_mats)):
                _vinc[row["matricula"]] = rotulo_vinculo(row["tv"])
        except Exception:
            pass
        finally:
            cv.close()
    for r in lista:
        r["vinc"] = _vinc.get(r["usuario"], VINCULO_PADRAO)
    for r in historico:
        r["vinc"] = _vinc.get(r["usuario"], VINCULO_PADRAO)
    return {"ativas": lista, "historico": historico}


# tipo (em log_importacoes) -> (grupo, rotulo amigavel) para o painel "Bases"
_BASES_GRUPOS = ["RH", "Diretório (AD)", "Matrizes", "Extratos dos Sistemas"]
_BASES_LABEL = {
    "RH_ATIVOS":              ("RH", "Funcionários Ativos"),
    "RH_DESLIGADOS":          ("RH", "Funcionários Desligados"),
    # AD: sem estas linhas, uma entrega SEM os exports do diretorio e' invisivel
    # — a tela segue mostrando as identidades da carga anterior e nada avisa.
    # Sao elas que dao dono aos acessos orfaos e achem desligado pelo login.
    "AD_FRANQUEADOS":         ("Diretório (AD)", "Franqueados"),
    "AD_PRESTADORES":         ("Diretório (AD)", "Prestadores"),
    "AD_DESLIGADOS":          ("Diretório (AD)", "Desligados (AD)"),
    "MATRIZ_PERFIS":          ("Matrizes", "Matriz de Perfis de Acesso"),
    "MATRIZ_CCO":             ("Matrizes", "Mapeamento CCO_CSC"),
    "SYSTUR":                 ("Extratos dos Sistemas", "SYSTUR"),
    "IC_INTEGRADOR_CONTABIL": ("Extratos dos Sistemas", "IC — Integrador Contábil"),
    "SICA_RA":                ("Extratos dos Sistemas", "SICA RA"),
    "SICA_ESFERA":            ("Extratos dos Sistemas", "SICA Esfera"),
    "SIGOT":                  ("Extratos dos Sistemas", "SIGOT"),
    "SIG":                    ("Extratos dos Sistemas", "SIG"),
    "ORACLE_EBS":             ("Extratos dos Sistemas", "Oracle EBS"),
}


def listar_bases():
    """Catalogo das bases: por tipo, SO a ULTIMA importacao bem-sucedida —
    nome do arquivo e a data do PROPRIO arquivo (disponibilizacao). Agrupado
    em RH / Matrizes / Extratos dos Sistemas. Fonte: log_importacoes (o SQLite
    devolve o arquivo/dt_arquivo da linha de maior dt_importacao por tipo)."""
    c = conn_ro()
    try:
        # DOIS casos que davam a MESMA tela vazia (achado 06/08: a base aparecia
        # numa maquina e nao na outra, com o MESMO pacote):
        #   a) tabela ausente  -> banco ainda nao processado. Vazio e' a verdade.
        #   b) erro de leitura -> o dado pode existir; o que falhou foi a
        #      consulta. Antes o `except: rows = []` engolia isto e a tela dizia
        #      "Nenhuma importacao registrada" — mentindo, e sem deixar rastro
        #      para diagnosticar. Agora propaga: a rota devolve 500 e o painel
        #      mostra o motivo.
        cols = [r["name"] for r in c.execute("PRAGMA table_info(log_importacoes)")]
        if not cols:
            return []                      # (a) nunca processou: vazio de verdade
        col_dt = "dt_arquivo" if "dt_arquivo" in cols else "'' AS dt_arquivo"
        rows = c.execute(
            f"SELECT tipo, arquivo, {col_dt}, total_registros, MAX(dt_importacao) AS dt_imp "
            "FROM log_importacoes WHERE status='SUCESSO' "
            "GROUP BY tipo").fetchall()     # (b) qualquer erro sobe
    finally:
        c.close()

    def _item(tipo, rotulo, r):
        return {"tipo": tipo, "base": rotulo, "arquivo": r["arquivo"] or "",
                "dt_arquivo": r["dt_arquivo"] or "", "dt_importacao": r["dt_imp"] or "",
                "registros": r["total_registros"] if r["total_registros"] is not None else ""}

    por_tipo = {r["tipo"]: r for r in rows}
    grupos = {g: [] for g in _BASES_GRUPOS}
    for tipo, (grupo, rotulo) in _BASES_LABEL.items():
        r = por_tipo.get(tipo)
        if r:
            grupos[grupo].append(_item(tipo, rotulo, r))
    # tipos sem rotulo conhecido caem em "Extratos dos Sistemas" com o tipo cru
    for tipo, r in por_tipo.items():
        if tipo not in _BASES_LABEL:
            grupos["Extratos dos Sistemas"].append(_item(tipo, tipo, r))
    return [{"grupo": g, "itens": grupos[g]} for g in _BASES_GRUPOS if grupos[g]]


def retirar_quarentena(registro_id, motivo=""):
    """Grava uma interacao RESOLVER (QUARENTENA) na rede com o MOTIVO da retirada
    (obrigatorio). Devolve 1 se gravou, 0 se invalido."""
    rid = str(registro_id or "").strip()
    motivo = str(motivo or "").strip()
    if not rid or not motivo:
        return 0
    _interacao_gravar({
        "tipo_interacao": "QUARENTENA", "registro_id": rid, "acao": "RESOLVER",
        "usuario": USUARIO, "motivo": motivo,
        "data_acao": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    })
    print(f"  [QUARENTENA] RESOLVER ({rid}) por {USUARIO} — motivo: {motivo}")
    return 1


def _validar_tratativa(rid, motivo, parecer, exige_motivo=True):
    """Regra da TRATATIVA INTERNA (05/08/2026). Devolve o JSON do erro ou None.

    O ticket do Jira ERA obrigatorio. Com a regra nova — "Resolver" (o analista
    trata internamente) separado de "Abrir chamado no Jira" — exigir o ticket
    impediria justamente o caminho novo: nao daria para registrar uma tratativa
    sem antes existir chamado. O obrigatorio passou a ser o que PROVA a
    tratativa: o PARECER do analista. Ticket e link ficam opcionais.

    O MOTIVO (lista fechada do XML) so vale na PENDENCIA — `exige_motivo`
    (06/08). A lista responde "por que este acesso divergente da matriz vai
    ficar assim?", pergunta que nao cabe nos outros dois fluxos: no desligado o
    desfecho e' sempre revogar (obrigatorio de resposta unica e' atrito, nao
    dado) e no transferido "Transferencia de Area" so repete o rotulo da aba.
    """
    if not rid:
        return '{"ok":false,"erro":"registro obrigatorio"}'
    if exige_motivo and not motivo:
        return '{"ok":false,"erro":"Selecione o motivo da tratativa."}'
    if not str(parecer or "").strip():
        return ('{"ok":false,"erro":"Descreva o parecer da tratativa '
                '(o que foi verificado e decidido)."}')
    return None


def resolver_pendencia(registro_id, ticket, ticket_url="", descricao="", motivo="",
                       sistema="", perfil=""):
    """Grava uma interacao RESOLUCAO na rede — registra a TRATATIVA do analista
    (motivo + parecer), com o ticket do Jira OPCIONAL. Devolve 1 se gravou, 0 se
    invalido.

    O ticket ERA obrigatorio aqui tambem (regra antiga). Ficou opcional em
    05/08 junto com a separacao "Resolver" x "Abrir chamado no Jira": exigir o
    ticket impediria registrar a tratativa interna, que e' o caminho novo. O
    obrigatorio agora e' o que prova a tratativa — ver `_validar_tratativa`.

    Alvo (retorno Bruna, 3 niveis):
      - so `registro_id`            -> a PESSOA inteira (compat);
      - + `sistema`                 -> so aquele SISTEMA  (`usuario##sistema`);
      - + `sistema` e `perfil`      -> so aquele ACESSO   (`usuario##sistema##perfil`).
    O snapshot de auditoria segue o mesmo recorte do alvo."""
    rid = str(registro_id or "").strip()
    sis_alvo = str(sistema or "").strip()
    perf_alvo = str(perfil or "").strip() if sis_alvo else ""
    tk = str(ticket or "").strip()
    motivo = str(motivo or "").strip()
    # a PENDENCIA mantem o motivo obrigatorio (e' o unico fluxo com a lista
    # fechada, e e' dela que sai o grafico "Motivos das Resolucoes")
    if not rid or not motivo or not str(descricao or "").strip():
        return 0
    nome, _, _ = _meta_divergencia(rid)
    # chave da resolucao: composta quando por sistema/acesso (nao muda schema)
    chave = rid
    if sis_alvo:
        chave += f"##{sis_alvo}" + (f"##{perf_alvo}" if perf_alvo else "")
    # Snapshot completo para auditoria — cargo, centro de custo e as pendencias
    # como estavam no momento da resolucao, mesmo que a base mude depois.
    # "Em Analise" vem como varias linhas (1 por perfil candidato) em
    # bi_divergencias — colapsamos numa pendencia so, com a lista de opcoes.
    cargo = centro_custo = ""
    pend = []
    try:
        c = conn_ro()
        try:
            rh = c.execute(
                "SELECT cargo_descricao, centro_custo_codigo, centro_custo_nome "
                "FROM rh_ativos WHERE matricula=?", [rid]).fetchone()
            cargo = (rh["cargo_descricao"] if rh else "") or ""
            cc_cod = (rh["centro_custo_codigo"] if rh else "") or ""
            cc_nome = (rh["centro_custo_nome"] if rh else "") or ""
            centro_custo = (cc_cod + " - " + cc_nome).strip(" -")
            analise = {}     # sistema -> pendencia "Em Analise" agrupada
            # snapshot: todas as pendencias da pessoa, ou so as do sistema alvo
            _sql = ("SELECT tipo, acao, sistema, perfil_encontrado, "
                    "perfil_esperado, origem FROM bi_divergencias WHERE usuario=?"
                    + (" AND sistema=?" if sis_alvo else "")
                    # acesso individual: a linha e' identificada pelo perfil
                    # ENCONTRADO (ou pelo ESPERADO quando nao ha encontrado),
                    # o mesmo criterio de _perfil_div/da grid
                    + (" AND COALESCE(NULLIF(TRIM(COALESCE(perfil_encontrado,'')),''),"
                       "TRIM(COALESCE(perfil_esperado,'')))=?" if perf_alvo else ""))
            _args = [rid] + ([sis_alvo] if sis_alvo else []) \
                + ([perf_alvo] if perf_alvo else [])
            for r in c.execute(_sql, _args):
                tp = r["tipo"] or ""
                sis = r["sistema"] or ""
                org = r["origem"] or ""
                origem = ("Matriz " + sis if org == "MATRIZ"
                          else "Matriz CCO" if org == "CCO" else "—")
                if tp == "EM_ANALISE":
                    ea = analise.get(sis)
                    if ea is None:
                        ea = {"tipo": TIPO_LABEL["EM_ANALISE"],
                              "acao": r["acao"] or "Em Análise",
                              "sistema": sis, "origem": origem,
                              "pe": r["perfil_encontrado"] or "",
                              "pp": "", "opcoes": []}
                        analise[sis] = ea
                        pend.append(ea)
                    pp = r["perfil_esperado"] or ""
                    if pp and pp not in ea["opcoes"]:
                        ea["opcoes"].append(pp)
                else:
                    pend.append({
                        "tipo": TIPO_LABEL.get(tp, tp), "acao": r["acao"] or "",
                        "sistema": sis, "origem": origem,
                        "pe": r["perfil_encontrado"] or "",
                        "pp": r["perfil_esperado"] or "", "opcoes": []})
        finally:
            c.close()
    except Exception as e:
        print(f"  [RESOLUCAO] aviso: snapshot incompleto ({e!r})")
    _interacao_gravar({
        "tipo_interacao": "RESOLUCAO", "registro_id": chave, "acao": "RESOLVER",
        "ticket": tk,
        "ticket_url": str(ticket_url or "").strip(),
        "descricao": str(descricao or "").strip(),
        "motivo": motivo,
        "cargo": cargo, "centro_custo": centro_custo,
        "sistema": sis_alvo, "perfil": perf_alvo,
        "pendencias": pend,
        "nome": nome, "usuario": USUARIO,
        "data_acao": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    })
    print(f"  [RESOLUCAO] {chave} ticket={tk} ({len(pend)} pend.) por {USUARIO}")
    return 1


def tratar_desligado(registro_id, ticket, ticket_url="", descricao="", motivo=""):
    """Grava uma interacao TRATAMENTO_DESLIGADO na rede — registra o tratamento do
    acesso de um desligado (mesmo padrao da resolucao de pendencia). Ticket
    OPCIONAL desde 05/08 — ver `_validar_tratativa`. `registro_id` = matricula
    do desligado. Devolve 1 se gravou."""
    rid = str(registro_id or "").strip()
    tk = str(ticket or "").strip()
    motivo = str(motivo or "").strip()
    if not rid or not str(descricao or "").strip():
        return 0
    # Snapshot p/ auditoria: dados do desligado + acessos ainda ativos no momento.
    nome = cargo = centro_custo = ""
    acessos = []
    try:
        c = conn_ro()
        try:
            rh = c.execute(
                "SELECT nome, cargo_descricao, centro_custo_codigo, centro_custo_nome "
                "FROM rh_desligados WHERE matricula=?", [rid]).fetchone()
            if rh:
                nome = rh["nome"] or ""
                cargo = rh["cargo_descricao"] or ""
                centro_custo = ((rh["centro_custo_codigo"] or "") + " - "
                                + (rh["centro_custo_nome"] or "")).strip(" -")
            for r in c.execute(
                    "SELECT sistema, usuario, perfil_encontrado "
                    "FROM divergencias WHERE tipo='ACESSO_DESLIGADO' AND matricula=?",
                    [rid]):
                acessos.append({"sistema": r["sistema"] or "",
                                "login": r["usuario"] or "",
                                "perfil": r["perfil_encontrado"] or ""})
        finally:
            c.close()
    except Exception as e:
        print(f"  [TRAT_DESLIG] aviso: snapshot incompleto ({e!r})")
    _interacao_gravar({
        "tipo_interacao": "TRATAMENTO_DESLIGADO", "registro_id": rid, "acao": "TRATAR",
        "ticket": tk,
        "ticket_url": str(ticket_url or "").strip(),
        "descricao": str(descricao or "").strip(),
        "motivo": motivo,
        "cargo": cargo, "centro_custo": centro_custo,
        "acessos": acessos,
        "nome": nome, "usuario": USUARIO,
        "data_acao": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    })
    print(f"  [TRAT_DESLIG] {rid} ticket={tk} ({len(acessos)} acesso(s)) por {USUARIO}")
    return 1


def abrir_chamado_desligado(registro_id, parecer):
    """Abre o chamado de revogacao de um DESLIGADO e registra a abertura.

    Devolve (ticket, url). Levanta JiraErro se o chamado nao foi criado.

    POR QUE GRAVA AQUI, e nao so' no Resolver: entre criar o chamado no Jira e o
    analista concluir a tratativa nao ha' nada persistido. Se ele fechar o modal
    no meio, o chamado existe no Service Desk e o painel nao sabe — a pendencia
    segue aberta e o proximo analista abre um segundo chamado para a mesma coisa.
    Gravando na resposta do POST, o painel passa a saber, e o estado "aguardando
    chamado" cai de graca: e' a pendencia que tem ticket e ainda nao tem parecer.

    A ORDEM IMPORTA: cria primeiro, grava depois. Se a gravacao falhar (rede,
    share fora), o chamado JA existe — por isso o erro devolve o numero junto,
    para a tela exibi-lo e o analista nao perder o dado.
    """
    rid = str(registro_id or "").strip()
    if not rid:
        raise JiraErro("Registro nao informado.")
    parecer = str(parecer or "").strip()
    if not parecer:
        raise JiraErro("Descreva o parecer antes de abrir o chamado.")

    # Ja existe chamado para este registro? A checagem e' AQUI, no servidor, e
    # nao so' na tela: a tela de um analista nao sabe do clique do outro, e o
    # painel roda em varias maquinas contra a mesma pasta de interacoes.
    ja = chamados_abertos().get(rid)
    if ja:
        raise JiraErro(
            f"Ja existe o chamado {ja['ticket']} para este registro, aberto por "
            f"{ja['por'] or '?'} em {ja['em'] or '?'}. Conclua a tratativa em vez "
            f"de abrir outro.")

    nome, desligamento = "", ""
    acessos = []
    try:
        c = conn_ro()
        try:
            rh = c.execute(
                "SELECT nome, data_desligamento FROM rh_desligados WHERE matricula=?",
                [rid]).fetchone()
            if rh:
                nome = rh["nome"] or ""
                desligamento = rh["data_desligamento"] or ""
            for r in c.execute(
                    "SELECT sistema, usuario, perfil_encontrado "
                    "FROM divergencias WHERE tipo='ACESSO_DESLIGADO' AND matricula=?",
                    [rid]):
                acessos.append({"sistema": r["sistema"] or "",
                                "login": r["usuario"] or "",
                                "perfil": r["perfil_encontrado"] or ""})
        finally:
            c.close()
    except Exception as e:
        # Sem os acessos nao da' para dizer O QUE revogar — abrir um chamado
        # vazio seria pior do que nao abrir.
        raise JiraErro(f"Nao foi possivel ler os dados do desligado: {e}")

    if not acessos:
        raise JiraErro("Nenhum acesso ativo encontrado para este desligado.")

    # Um chamado por (usuario, SISTEMA): o titulo carrega um sistema so. Com
    # acesso em mais de um sistema, o primeiro define o titulo e os demais vao
    # na tabela — a area confirmou um chamado por pessoa/sistema, e hoje o
    # escopo do painel e' de um sistema so'.
    sistema = acessos[0]["sistema"]
    titulo = jira_titulo(sistema, nome)
    contexto = (f"Desligamento: {_data_br(desligamento)}"
                if desligamento else "")
    descricao = jira_descricao(
        [(nome, a["login"], a["perfil"]) for a in acessos], contexto, parecer)

    ticket, url = jira_abrir_chamado(titulo, descricao)   # pode levantar JiraErro

    try:
        _interacao_gravar({
            "schema_version": 1,
            "tipo_interacao": "CHAMADO_ABERTO", "registro_id": rid,
            "acao": "ABRIR_CHAMADO", "fluxo": "DESLIGADO",
            "ticket": ticket, "ticket_url": url,
            "nome": nome, "sistema": sistema, "acessos": acessos,
            "usuario": USUARIO,
            "data_acao": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        })
    except Exception as e:
        raise JiraErro(
            f"Chamado {ticket} foi ABERTO no Jira, mas nao foi possivel "
            f"registrar no painel ({e}). Anote o numero e informe no campo "
            f"'N do ticket' antes de resolver.")

    print(f"  [CHAMADO] {ticket} aberto para desligado {rid} por {USUARIO}")
    return ticket, url


def listar_historico_rh():
    """Trilha de pendências: cada resolução gera o par "Pendência identificada"
    / "Pendência resolvida". Lista plana, ordenada por data decrescente; a tela
    agrupa por funcionário. Movimentações cadastrais de RH (admissão, alteração
    de cargo) NÃO entram aqui — o foco é o ciclo de vida da pendência."""
    out = []
    # resolucoes de pendencia: cada uma gera 2 linhas para rastreabilidade —
    # quando a pendencia foi identificada e quando foi resolvida.
    resolvidos = _resolucoes_mescladas()
    if resolvidos:
        cr = conn_ro()
        try:
            for rid, rdat in resolvidos.items():
                nome = rdat.get("nome") or ""
                if not nome:
                    row = cr.execute(
                        "SELECT nome_usuario FROM bi_divergencias "
                        "WHERE usuario=? LIMIT 1", [rid]).fetchone()
                    nome = (row[0] if row and row[0] else "") or rid
                row = cr.execute(
                    "SELECT MIN(data_identificacao) FROM bi_divergencias "
                    "WHERE usuario=? AND data_identificacao<>''", [rid]).fetchone()
                dt_pend = (str(row[0]) if row and row[0] else "")
                # A "identificada" nunca pode ser DEPOIS da "resolvida". Se a
                # pessoa ja virou Aderente/OK, o bi so guarda a linha OK com a
                # data do reprocesso (data_identificacao > em) -> limita pela
                # propria data de resolucao para nao inverter a cronologia.
                _em = str(rdat.get("em") or "")
                if _em and (not dt_pend or dt_pend > _em):
                    dt_pend = _em
                # dados do encerramento, comuns às 2 linhas (p/ o modal de detalhe)
                tk = {
                    "ticket": rdat.get("ticket") or "",
                    "ticket_url": rdat.get("ticket_url") or "",
                    "descricao": rdat.get("descricao") or "",
                    "motivo": rdat.get("motivo") or "",
                    "cargo": rdat.get("cargo") or "",
                    "centro_custo": rdat.get("centro_custo") or "",
                    "por": rdat.get("por") or "",
                    "em": rdat.get("em") or "",
                    "pendencias": rdat.get("pendencias") or [],
                }
                # linha 1 — pendencia identificada
                out.append(dict(tk, **{
                    "tipo": "PENDENCIA", "data": dt_pend, "_ord": dt_pend,
                    "matricula": rid, "nome": nome,
                    "movimentacao": "Pendência identificada", "campos": "",
                }))
                # linha 2 — pendencia resolvida (sob ticket). _ord usa a
                # data_acao completa (com hora) p/ ficar acima da identificada.
                out.append(dict(tk, **{
                    "tipo": "RESOLUCAO", "data": str(rdat.get("em") or ""),
                    "_ord": str(rdat.get("em") or ""),
                    "matricula": rid, "nome": nome,
                    "movimentacao": "Pendência resolvida",
                    "campos": rdat.get("ticket") or "",
                }))
        finally:
            cr.close()

    # Ciclo de vida POR (matricula, sistema) — log de eventos append-only
    # `ciclo_eventos_acesso`: marcos Pendencia -> Resolvido -> Aderente AGRUPADOS
    # EM CICLOS. Cada evento carrega o proprio sistema e o numero do ciclo, entao
    # o Historico abre por sistema (sem achatar por pessoa) e mostra REABERTURA
    # (ciclo >= 2). Para matriculas com resolucao rica (montada acima), pulamos
    # PENDENCIA/RESOLVIDO do CICLO 1 pra nao duplicar; ADERENTE e reaberturas
    # sempre entram. Banco antigo sem a tabela -> fallback na projecao `historico`.
    mats_resol = set((resolvidos or {}).keys())
    _MOVS = {"PENDENCIA": ("PENDENCIA", "Pendência identificada"),
             "RESOLVIDO": ("RESOLUCAO", "Pendência resolvida"),
             "ADERENTE":  ("ADERENTE",  "Aderente")}
    _LBL = {"PENDENCIA": "Pendência", "RESOLVIDO": "Resolvido", "ADERENTE": "Aderente"}
    ch = conn_ro()
    try:
        _tem_ev = ch.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='ciclo_eventos_acesso'").fetchone()
        if _tem_ev:
            for row in ch.execute(
                "SELECT matricula, sistema, ciclo, tipo_evento, data_evento, "
                "perfil, nome, cargo, ticket FROM ciclo_eventos_acesso"
            ):
                mat, _sis, _ciclo, tm = row[0], row[1] or "", row[2] or 1, row[3]
                if tm in ("PENDENCIA", "RESOLVIDO") and _ciclo == 1 and mat in mats_resol:
                    continue  # ciclo 1 ja coberto pelas linhas ricas da resolucao
                tipo, mov = _MOVS.get(tm, (tm, tm))
                dt = str(row[4] or "")
                _perf = row[5] or ""
                _tk = row[8] or ""
                _reab = (tm == "PENDENCIA" and _ciclo > 1)
                _mov = "Pendência reaberta" if _reab else mov
                _lbl = _LBL.get(tm, tm)
                _pend = ([{"tipo": _lbl, "acao": "", "sistema": _sis, "origem": "—",
                           "pe": (_perf if tm == "ADERENTE" else ""),
                           "pp": _perf, "opcoes": []}]
                         if (_sis or _perf) else [])
                out.append({
                    "tipo": tipo, "data": dt, "_ord": dt,
                    "matricula": mat, "nome": row[6] or mat,
                    "movimentacao": _mov, "campos": _tk,
                    "sistema": _sis, "perfil": _perf,
                    "ciclo": _ciclo, "reaberta": _reab,
                    "cargo": row[7] or "", "ticket": _tk,
                    "ticket_url": "", "descricao": "", "por": "", "em": "",
                    "centro_custo": "",
                    "pendencias": _pend,
                })
        else:
            # fallback: banco antigo sem o log de eventos -> projecao `historico`
            for row in ch.execute(
                "SELECT matricula, tipo_mudanca, data_snapshot, dados_novo FROM historico "
                "WHERE entidade='ACESSO_SISTEMA' AND tipo_mudanca IN "
                "('PENDENCIA','RESOLVIDO','ADERENTE')"
            ):
                mat, tm = row[0], row[1]
                if tm in ("PENDENCIA", "RESOLVIDO") and mat in mats_resol:
                    continue
                tipo, mov = _MOVS.get(tm, (tm, tm))
                try:
                    d = json.loads(row[3] or "{}")
                except Exception:
                    d = {}
                dt = d.get("data") or str(row[2] or "")
                _sis = d.get("sistema") or ""
                _perf = d.get("perfil") or ""
                _lbl = _LBL.get(tm, tm)
                _pend = ([{"tipo": _lbl, "acao": "", "sistema": _sis, "origem": "—",
                           "pe": (_perf if tm == "ADERENTE" else ""),
                           "pp": _perf, "opcoes": []}]
                         if (_sis or _perf) else [])
                out.append({
                    "tipo": tipo, "data": dt, "_ord": dt,
                    "matricula": mat, "nome": d.get("nome") or mat,
                    "movimentacao": mov, "campos": d.get("ticket") or "",
                    "sistema": _sis, "perfil": _perf,
                    "cargo": d.get("cargo") or "", "ticket": d.get("ticket") or "",
                    "ticket_url": "", "descricao": "", "por": "", "em": "",
                    "centro_custo": "",
                    "pendencias": _pend,
                })
    except Exception:
        pass  # tabela historico/eventos pode nao existir em banco antigo
    finally:
        ch.close()

    # vinculo (Funcionario/Terceiro) por matricula — lookup em rh_ativos
    _mats = {e.get("matricula") for e in out if e.get("matricula")}
    if _mats:
        cvh = conn_ro()
        _vm, _ccm, _gm = {}, {}, {}
        try:
            qm = ",".join("?" * len(_mats))
            for r in cvh.execute(
                    "SELECT matricula, COALESCE(tipo_vinculo,'FUNCIONARIO'), "
                    "COALESCE(centro_custo_codigo,''), COALESCE(centro_custo_nome,''), "
                    "COALESCE(gestor,'') "
                    f"FROM rh_ativos WHERE matricula IN ({qm})", list(_mats)):
                _vm[r[0]] = rotulo_vinculo(r[1])
                _ccm[r[0]] = (str(r[2]) + " - " + str(r[3])).strip(" -")
                _gm[r[0]] = r[4] or ""
        except Exception:
            pass
        finally:
            cvh.close()
        for e in out:
            e["vinc"] = _vm.get(e.get("matricula"), VINCULO_PADRAO)
            e["gestor"] = _gm.get(e.get("matricula"), "")
            if not e.get("centro_custo"):
                e["centro_custo"] = _ccm.get(e.get("matricula"), "")

    out.sort(key=lambda x: x.get("_ord") or "", reverse=True)
    return out


def motivos_tratados(de="", ate=""):
    """Distribuição dos MOTIVOS dos casos tratados no período + 'Sem motivo'
    para as ADERÊNCIAS que ocorreram sem resolução no sistema (viraram conformes
    por reprocesso, sem ticket). Conta USUÁRIOS (matrícula) distintos.
    de/ate: 'YYYY-MM-DD' inclusivo; vazio = sem limite. Período por data da
    resolução (tratados) e por data da aderência (sem motivo)."""
    def _conds(col):
        cs, args = [], []
        if de:  cs.append(f"substr({col},1,10) >= ?"); args.append(de)
        if ate: cs.append(f"substr({col},1,10) <= ?"); args.append(ate)
        return cs, args
    out = {}
    tratados_mats = set()
    c = conn_ro()
    try:
        def _tem(t):
            return c.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                             "AND name=?", [t]).fetchone() is not None
        # ── Tratados: por motivo (tabela resolucoes) ──────────────────────
        if _tem("resolucoes"):
            cols = [r[1] for r in c.execute("PRAGMA table_info(resolucoes)")]
            mot = "COALESCE(NULLIF(TRIM(motivo),''),'(motivo não informado)')" \
                  if "motivo" in cols else "'(motivo não informado)'"
            cs, args = _conds("resolvido_em")
            where = (" WHERE " + " AND ".join(cs)) if cs else ""
            for r in c.execute(
                    f"SELECT {mot} m, COUNT(DISTINCT registro_id) n "
                    f"FROM resolucoes{where} GROUP BY m", args):
                out[r[0]] = out.get(r[0], 0) + (r[1] or 0)
            for r in c.execute("SELECT DISTINCT registro_id FROM resolucoes"):
                if r[0]:
                    tratados_mats.add(str(r[0]))
        # ── Sem motivo: aderências sem resolução (ciclo_vida_acesso) ──────
        if _tem("ciclo_vida_acesso"):
            cs, args = _conds("dt_aderente")
            cond = ["dt_aderente IS NOT NULL"] + cs
            for r in c.execute(
                    "SELECT DISTINCT matricula FROM ciclo_vida_acesso WHERE "
                    + " AND ".join(cond), args):
                m = str(r[0] or "")
                if m and m not in tratados_mats:
                    out["Sem motivo"] = out.get("Sem motivo", 0) + 1
    finally:
        c.close()
    itens = sorted(out.items(), key=lambda x: (x[0] == "Sem motivo", -x[1]))
    return {"total": sum(out.values()),
            "itens": [{"motivo": k, "n": v} for k, v in itens]}


def _vg_secoes(de="", ate=""):
    """Monta as seções da Visão Geral para o Excel (uma tabela por gráfico,
    com a fonte de dados). Motivos respeita o período de/ate."""
    vg = construir_db().get("vg", {}) or {}
    mot = motivos_tratados(de, ate)
    TL = {'ACESSO_SEM_VINCULO_RH': 'Sem Vínculo RH', 'DIVERGENTE': 'Alterar Perfil',
          'EM_ANALISE': 'Em Análise', 'SEM_ACESSO': 'Incluir Acesso',
          'ACESSO_DESLIGADO': 'Acesso de Desligado', 'PERFIL_INVALIDO': 'Perfil Inválido'}
    SL = {'IC_INTEGRADOR_CONTABIL': 'IC', 'SICA_RA': 'SICA RA', 'SICA_ESFERA': 'SICA Esfera',
          'ORACLE_EBS': 'Oracle EBS', 'OPERA_OPERACIONAL': 'Opera'}
    pct = lambda n, t: (round(100 * n / t, 1) if t else 0)
    ch = vg.get("chamados") or {}
    tp = vg.get("tempos") or {}
    dt = vg.get("div_tipos") or {}
    ds = vg.get("div_sistemas") or {}
    ag = vg.get("aging") or {}
    tot_dt, tot_m = sum(dt.values()), mot.get("total", 0)
    secoes = [
        {"titulo": "Indicadores", "kind": "kpis", "colunas": ["Indicador", "Valor"], "linhas": [
            ["Pendências Abertas", vg.get("pendentes", 0)],
            ["Incluir Acesso", vg.get("incluir", 0)],
            ["Aderentes", vg.get("ok", 0)],
            ["Cobertura RH (%)", vg.get("cobertura_pct", 0)],
            ["Em Quarentena", vg.get("quarentena_ativa", 0)],
            ["Acessos de Desligado", vg.get("acessos_deslig", 0)],
            ["RH Ativos", vg.get("rh_ativos", 0)]]},
        {"titulo": "Tempo de Tratamento (ciclo)", "kind": "tempo", "colunas": ["Etapa", "Tempo"], "linhas": [
            ["Pendência → Aderente (médio)", tp.get("total") or "—"],
            ["Pendência → Resolvido", tp.get("pend_resolv") or "—"],
            ["Resolvido → Aderente", tp.get("resolv_ader") or "—"]]},
        {"titulo": "Chamados (últimos 30 dias)", "chart": {"tipo": "bar"}, "colunas": ["Categoria", "Qtd"], "linhas": [
            ["Identificados", ch.get("identificados", 0)],
            ["Resolvidos", ch.get("resolvidos", 0)],
            ["Aderentes", ch.get("aderentes", 0)]]},
        {"titulo": "Divergências por Tipo", "chart": {"tipo": "doughnut"}, "colunas": ["Tipo", "Qtd", "%"],
         "linhas": [[TL.get(k, k), v, pct(v, tot_dt)]
                    for k, v in sorted(dt.items(), key=lambda x: -x[1])]},
        {"titulo": "Concentração por Sistema", "chart": {"tipo": "bar"}, "colunas": ["Sistema", "Qtd"],
         "linhas": [[SL.get(k, k), v] for k, v in sorted(ds.items(), key=lambda x: -x[1])]},
        {"titulo": "Aging das Pendências", "chart": {"tipo": "col"}, "colunas": ["Faixa (dias)", "Qtd"],
         "linhas": [[k, v] for k, v in ag.items()]},
        {"titulo": "Motivos das Resoluções — Pendências"
                   + (f" ({de} a {ate})" if (de or ate) else " (todo o período)"),
         "chart": {"tipo": "doughnut"}, "colunas": ["Motivo", "Qtd", "%"],
         "linhas": [[it["motivo"], it["n"], pct(it["n"], tot_m)] for it in mot.get("itens", [])]},
    ]
    # Movimentação RH (painel do dashboard) — data-driven
    mv = vg.get("movimentacao")
    _MOVLBL = {"admissoes": "Admissões", "alteracoes": "Alterações",
               "desligamentos": "Desligamentos"}
    if isinstance(mv, dict) and mv:
        mov_linhas = [[_MOVLBL.get(k, str(k)), v] for k, v in mv.items()]
    else:
        mov_linhas = [["(sem dados de movimentação no período)", ""]]
    secoes.append({"titulo": "Movimentação RH (últimos 30 dias)", "kind": "mov",
                   "colunas": ["Tipo", "Qtd"], "linhas": mov_linhas})
    # Ação Imediata — recém-desligados ainda com acesso (Top 10) — data-driven
    tu = vg.get("top_urgentes") or []
    if tu and isinstance(tu[0], dict):
        acao_linhas = [[t.get("nome", ""), t.get("cargo", ""),
                        t.get("sistemas", 0), t.get("perfis", 0)] for t in tu[:8]]
    else:
        acao_linhas = [["Sem desligados com acesso ativo", "", "", ""]]
    secoes.append({"titulo": "Ação Imediata — Recém-desligados com Acesso", "kind": "acao",
                   "colunas": ["Nome", "Cargo", "Sistemas", "Perfis"], "linhas": acao_linhas})
    return secoes


def _vg_analiticos(de="", ate=""):
    """Abas ANALÍTICAS: o detalhe (registros) que gerou cada gráfico, pro cliente
    auditar quais informações foram usadas. Uma aba por fonte de dados."""
    TL = {'ACESSO_SEM_VINCULO_RH': 'Sem Vínculo RH', 'DIVERGENTE': 'Alterar Perfil',
          'EM_ANALISE': 'Em Análise', 'SEM_ACESSO': 'Incluir Acesso', 'OK': 'Aderente',
          'ACESSO_DESLIGADO': 'Acesso de Desligado', 'PERFIL_INVALIDO': 'Perfil Inválido'}
    SL = {'IC_INTEGRADOR_CONTABIL': 'IC', 'SICA_RA': 'SICA RA', 'SICA_ESFERA': 'SICA Esfera',
          'ORACLE_EBS': 'Oracle EBS', 'OPERA_OPERACIONAL': 'Opera'}
    d19 = lambda s: (str(s) if s else "")[:19]
    from datetime import datetime as _dt
    hoje = _dt.now()
    out = []
    c = conn_ro()
    try:
        def _tem(t):
            return c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                             [t]).fetchone() is not None
        # Escopo = mesmo do painel (config visualizador/sistema; vazio = todos).
        # Mantém as abas analíticas/interativas no mesmo recorte da Visão Geral.
        whereW = " WHERE sistema = ?" if SISTEMA else ""
        whereAnd = " AND sistema = ?" if SISTEMA else ""
        argS = (SISTEMA,) if SISTEMA else ()
        # 1) Divergências → 'Divergências por Tipo' + 'Concentração por Sistema'
        L = [[r["usuario"] or "", r["nome_usuario"] or "", r["matricula"] or "",
              SL.get(r["sistema"], r["sistema"] or ""), TL.get(r["tipo"], r["tipo"] or ""),
              r["acao"] or "", r["perfil_encontrado"] or "", r["perfil_esperado"] or "",
              r["origem"] or "", d19(r["data_identificacao"])]
             for r in c.execute(
                "SELECT usuario,nome_usuario,matricula,sistema,tipo,acao,perfil_encontrado,"
                "perfil_esperado,origem,data_identificacao FROM bi_divergencias"
                + whereW + " ORDER BY sistema,tipo", argS)]
        out.append({"nome": "Divergências (analítico)",
                    "colunas": ["Usuário/Login", "Nome", "Matrícula", "Sistema", "Tipo", "Ação",
                                "Perfil Encontrado", "Perfil Esperado", "Origem", "Data"],
                    "linhas": L})
        # 2) Aging → 'Aging das Pendências'
        A = []
        for r in c.execute("SELECT usuario,nome_usuario,sistema,tipo,acao,data_identificacao "
                           "FROM bi_divergencias WHERE resolvida=0 AND tipo<>'OK' "
                           "AND data_identificacao<>''" + whereAnd, argS):
            try:
                dias = (hoje - _dt.fromisoformat(str(r["data_identificacao"])[:19])).days
            except Exception:
                dias = ""
            fa = ("" if dias == "" else "0-7" if dias <= 7 else "8-30" if dias <= 30
                  else "31-90" if dias <= 90 else "90+")
            A.append([r["usuario"] or "", r["nome_usuario"] or "", SL.get(r["sistema"], r["sistema"] or ""),
                      TL.get(r["tipo"], r["tipo"] or ""), r["acao"] or "",
                      d19(r["data_identificacao"]), dias, fa])
        out.append({"nome": "Aging (analítico)",
                    "colunas": ["Usuário/Login", "Nome", "Sistema", "Tipo", "Ação",
                                "Data Identificação", "Dias", "Faixa"],
                    "linhas": A})
        # 3) Ciclo de vida → 'Chamados' + 'Tempo de Tratamento'
        if _tem("ciclo_vida_acesso"):
            CV = [[r["matricula"] or "", r["nome"] or "", SL.get(r["sistema"], r["sistema"] or ""),
                   r["perfil"] or "", d19(r["dt_pendencia"]), d19(r["dt_resolvido"]),
                   r["ticket"] or "", d19(r["dt_aderente"])]
                  for r in c.execute(
                    "SELECT matricula,nome,sistema,perfil,dt_pendencia,dt_resolvido,ticket,"
                    "dt_aderente FROM ciclo_vida_acesso" + whereW + " ORDER BY dt_pendencia", argS)]
            out.append({"nome": "Ciclo de Vida (analítico)",
                        "colunas": ["Matrícula", "Nome", "Sistema", "Perfil", "Pendência",
                                    "Resolvido", "Ticket", "Aderente"],
                        "linhas": CV})
        # 4) Motivos → donut 'Motivos dos Tratamentos'
        M, tratados = [], set()
        if _tem("resolucoes"):
            cr = {r[1] for r in c.execute("PRAGMA table_info(resolucoes)")}
            mc = "motivo" if "motivo" in cr else "'' AS motivo"
            for r in c.execute(f"SELECT registro_id,nome,{mc},ticket,resolvido_em FROM resolucoes"):
                dd = d19(r["resolvido_em"])
                if (de and dd[:10] < de) or (ate and dd[:10] > ate):
                    continue
                tratados.add(str(r["registro_id"]))
                M.append([r["registro_id"] or "", r["nome"] or "",
                          (r["motivo"] or "(não informado)"), r["ticket"] or "", dd, ""])
        if _tem("ciclo_vida_acesso"):
            # 1 linha por USUÁRIO (distinto) — bate com o donut (conta usuários)
            for r in c.execute("SELECT matricula, MAX(nome) nome, MAX(sistema) sistema, "
                               "MAX(dt_aderente) dt_aderente FROM ciclo_vida_acesso "
                               "WHERE dt_aderente IS NOT NULL GROUP BY matricula"):
                m = str(r["matricula"] or "")
                dd = d19(r["dt_aderente"])
                if (de and dd[:10] < de) or (ate and dd[:10] > ate):
                    continue
                if m and m not in tratados:
                    M.append([m, r["nome"] or "", "Sem motivo", "", dd,
                              SL.get(r["sistema"], r["sistema"] or "")])
        out.append({"nome": "Motivos (analítico)",
                    "colunas": ["Matrícula", "Nome", "Motivo", "Ticket", "Data", "Sistema"],
                    "linhas": M})
    finally:
        c.close()
    return out


_PAGINA_CACHE = {"chave": None, "html": None}


def _chave_cache_pagina():
    """Assinatura do estado que muda a pagina: mtime/tamanho do banco + mtime do
    index.html. Enquanto nao muda, reusa a pagina montada (evita reconstruir o
    DB de ~7MB e re-serializar a cada F5)."""
    try:
        sb = os.stat(DB_PATH)
        si = os.stat(INDEX_PATH)
        return (sb.st_mtime_ns, sb.st_size, si.st_mtime_ns)
    except OSError:
        return None


def html_injetado():
    # Cache: so remonta quando o banco (reprocesso) ou o index.html mudam.
    chave = _chave_cache_pagina()
    if chave is not None and _PAGINA_CACHE["chave"] == chave and _PAGINA_CACHE["html"]:
        return _PAGINA_CACHE["html"]
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        linhas = f.read().split("\n")
    js = "const DB = " + json.dumps(construir_db(), ensure_ascii=False) + ";"
    for i, ln in enumerate(linhas):
        if ln.lstrip().startswith("const DB ="):
            linhas[i] = js
            break
    else:
        raise RuntimeError("linha 'const DB =' nao encontrada no index.html")
    html = "\n".join(linhas)
    if chave is not None:
        _PAGINA_CACHE["chave"], _PAGINA_CACHE["html"] = chave, html
    return html


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        b = body.encode("utf-8") if isinstance(body, str) else body
        # Compressao gzip: a pagina embute ~7MB de JSON e cai ~92% gzipada —
        # decisivo na REDE (transfere ~0,6MB em vez de ~7MB). So comprime se o
        # navegador aceitar (Accept-Encoding) e se valer a pena (>1KB).
        comprimir = (len(b) > 1024 and
                     "gzip" in (self.headers.get("Accept-Encoding") or "").lower())
        if comprimir:
            import gzip as _gzip
            b = _gzip.compress(b, 5)
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        # NAO CACHEAR (06/08). O painel mora sempre no mesmo endereco
        # (127.0.0.1:8800), entao a versao NOVA de um pacote chega na mesma URL
        # da anterior. Sem nenhum cabecalho de cache o navegador decide sozinho
        # e pode servir a pagina do pacote antigo: aconteceu no teste — o painel
        # mostrava os dados certos (vem da API a cada abertura) mas a tela era a
        # velha, e o popup de arquivos importados vinha vazio. So se resolveu
        # limpando o cache do navegador, o que nao da para pedir a cada entrega.
        # Aqui nada e' estatico o bastante para valer cache: o HTML e' gerado e
        # as respostas mudam a cada tratativa.
        self.send_header("Cache-Control", "no-store, must-revalidate")
        if comprimir:
            self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, *a):
        print("  [http] " + (a[0] % a[1:]))

    def do_GET(self):
        global _last_seen, _armed, _enc_em, _sessao
        try:
            if self.path in ("/", "/index.html"):
                if _SEM_BANCO:
                    self._send(200, _PAGINA_SEM_BANCO, "text/html; charset=utf-8")
                else:
                    self._send(200, html_injetado(), "text/html; charset=utf-8")
            elif self.path == "/api/dados":
                self._send(200, json.dumps(construir_db(), ensure_ascii=False),
                           "application/json; charset=utf-8")
            elif self.path == "/api/quarentena":
                self._send(200, json.dumps(listar_quarentena(), ensure_ascii=False),
                           "application/json; charset=utf-8")
            elif self.path == "/api/historico":
                self._send(200, json.dumps(listar_historico_rh(), ensure_ascii=False),
                           "application/json; charset=utf-8")
            elif self.path == "/api/desligados":
                self._send(200, json.dumps(listar_desligados(), ensure_ascii=False),
                           "application/json; charset=utf-8")
            elif self.path == "/api/transferidos":
                self._send(200, json.dumps(listar_transferidos(), ensure_ascii=False),
                           "application/json; charset=utf-8")
            elif self.path == "/api/bases":
                self._send(200, json.dumps(listar_bases(), ensure_ascii=False),
                           "application/json; charset=utf-8")
            elif self.path.startswith("/api/exportar-vg"):
                from urllib.parse import urlparse, parse_qs
                q = parse_qs(urlparse(self.path).query)
                de = (q.get("de", [""])[0] or "").strip()
                ate = (q.get("ate", [""])[0] or "").strip()
                xlsx = gerar_xlsx_painel(_vg_secoes(de, ate), _vg_analiticos(de, ate),
                                         "Visão Geral — CVC IAM Analytics")
                self.send_response(200)
                self.send_header("Content-Type", "application/vnd.openxmlformats-"
                                 "officedocument.spreadsheetml.sheet")
                self.send_header("Content-Disposition",
                                 'attachment; filename="Visao_Geral.xlsx"')
                self.send_header("Content-Length", str(len(xlsx)))
                self.end_headers()
                self.wfile.write(xlsx)
                print(f"  [EXPORT] Visao_Geral.xlsx ({len(xlsx)} bytes)")
                return
            elif self.path.startswith("/api/motivos-tratados"):
                from urllib.parse import urlparse, parse_qs
                q = parse_qs(urlparse(self.path).query)
                de = (q.get("de", [""])[0] or "").strip()
                ate = (q.get("ate", [""])[0] or "").strip()
                self._send(200, json.dumps(motivos_tratados(de, ate), ensure_ascii=False),
                           "application/json")
            elif self.path == "/api/motivos-resolucao":
                self._send(200, json.dumps(listar_motivos_resolucao(), ensure_ascii=False),
                           "application/json; charset=utf-8")
            elif self.path.split("?")[0] == "/api/atalhos":
                # ?origem=incl|consulta — filtra; sem origem lista de todas as abas
                origem = ""
                if "?" in self.path:
                    for par in self.path.split("?", 1)[1].split("&"):
                        if par.startswith("origem="):
                            origem = par[7:].strip()
                self._send(200, json.dumps(
                    {"usuario": USUARIO,
                     "limite": LIMITE_ATALHOS_POR_ABA,
                     "atalhos": listar_atalhos(USUARIO, origem)},
                    ensure_ascii=False), "application/json; charset=utf-8")
            elif self.path.split("?")[0] == "/api/ping":
                _last_seen = time.time(); _armed = True; _enc_em = None
                if "?" in self.path:
                    for par in self.path.split("?", 1)[1].split("&"):
                        if par.startswith("s="):
                            _sessao = par[2:]
                self._send(200, '{"ok":true}', "application/json")
            elif self.path == "/api/encerrar":
                self._send(200, '{"ok":true}', "application/json")
                _enc("pedido da pagina (GET)")
            elif self.path == "/chart.umd.min.js":
                p = os.path.join(REPORT_DIR, "chart.umd.min.js")
                if os.path.exists(p):
                    with open(p, "rb") as f:
                        self._send(200, f.read(),
                                   "application/javascript; charset=utf-8")
                else:
                    self._send(404, '{"erro":"chart.umd.min.js ausente"}',
                               "application/json")
            else:
                self._send(404, '{"erro":"rota"}', "application/json")
        except Exception as e:
            print(f"  [ERRO GET {self.path}] {e!r}")
            self._send(500, json.dumps({"erro": repr(e)}), "application/json")

    def do_POST(self):
        try:
            if self.path == "/api/encerrar":
                n = int(self.headers.get("Content-Length", 0))
                sessao = self.rfile.read(n).decode("utf-8").strip() if n else ""
                self._send(200, '{"ok":true}', "application/json")
                agendar_encerramento(sessao, "aba fechada/recarregada (sendBeacon)")
                return
            if self.path == "/api/quarentena":
                n = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
                us = payload.get("usuarios") or (
                    [payload["usuario"]] if payload.get("usuario") else [])
                us = [str(x).strip() for x in us if str(x).strip()]
                origem = (payload.get("origem") or "Inclusão / Alteração").strip()
                if not us:
                    self._send(400, '{"ok":false,"erro":"sem usuarios"}',
                               "application/json")
                    return
                res = enviar_quarentena(
                    us, origem, dias=payload.get("dias"),
                    ticket=payload.get("ticket"), titulo=payload.get("titulo"),
                    motivo=payload.get("motivo"))
                if res.get("erro"):
                    self._send(200, json.dumps(
                        {"ok": False, "erro": res["erro"]}, ensure_ascii=False),
                        "application/json; charset=utf-8")
                    return
                self._send(200, json.dumps(
                    {"ok": True, "resultado": res,
                     "quarentena": listar_quarentena()}, ensure_ascii=False),
                    "application/json; charset=utf-8")
                return
            if self.path == "/api/quarentena/retirar":
                n = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
                qid = payload.get("id")
                motivo = str(payload.get("motivo") or "").strip()
                if qid is None:
                    self._send(400, '{"ok":false,"erro":"sem id"}',
                               "application/json")
                    return
                if not motivo:
                    self._send(200, '{"ok":false,"erro":"O motivo da retirada é obrigatório."}',
                               "application/json; charset=utf-8")
                    return
                linhas = retirar_quarentena(qid, motivo)
                self._send(200, json.dumps(
                    {"ok": linhas > 0,
                     "erro": None if linhas > 0 else "quarentena nao encontrada",
                     "quarentena": listar_quarentena()}, ensure_ascii=False),
                    "application/json; charset=utf-8")
                return
            if self.path == "/api/resolver":
                n = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
                rid = str(payload.get("id") or "").strip()
                ticket = str(payload.get("ticket") or "").strip()
                motivo = str(payload.get("motivo") or "").strip()
                erro = _validar_tratativa(rid, motivo, payload.get("descricao"))
                if erro:
                    self._send(400, erro, "application/json; charset=utf-8")
                    return
                linhas = resolver_pendencia(rid, ticket, payload.get("ticket_url"),
                                            payload.get("descricao"), motivo,
                                            sistema=payload.get("sistema") or "",
                                            perfil=payload.get("perfil") or "")
                self._send(200, json.dumps(
                    {"ok": linhas > 0,
                     "erro": None if linhas > 0 else "falha ao resolver",
                     "dados": construir_db()}, ensure_ascii=False),
                    "application/json; charset=utf-8")
                return
            if self.path == "/api/tratar-desligado":
                n = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
                rid = str(payload.get("id") or "").strip()
                ticket = str(payload.get("ticket") or "").strip()
                motivo = str(payload.get("motivo") or "").strip()
                erro = _validar_tratativa(rid, motivo, payload.get("descricao"),
                                          exige_motivo=False)
                if erro:
                    self._send(400, erro, "application/json; charset=utf-8")
                    return
                linhas = tratar_desligado(rid, ticket, payload.get("ticket_url"),
                                          payload.get("descricao"), motivo)
                self._send(200, json.dumps(
                    {"ok": linhas > 0,
                     "erro": None if linhas > 0 else "falha ao tratar",
                     "desligados": listar_desligados()}, ensure_ascii=False),
                    "application/json; charset=utf-8")
                return
            if self.path == "/api/abrir-chamado":
                n = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
                fluxo = str(payload.get("fluxo") or "desligado").strip().lower()
                if fluxo != "desligado":
                    # Escopo atual: so' revogacao de desligado. Pendencia e
                    # transferido seguem em alinhamento com a area.
                    self._send(400, json.dumps(
                        {"ok": False, "erro": "Abertura automatica disponivel "
                                              "apenas para desligados."},
                        ensure_ascii=False),
                        "application/json; charset=utf-8")
                    return
                try:
                    ticket, url = abrir_chamado_desligado(
                        payload.get("id"), payload.get("descricao"))
                except JiraErro as e:
                    # 409: o chamado PODE ter sido criado (ver abrir_chamado_
                    # desligado). A mensagem carrega o numero quando existe, e a
                    # tela precisa mostra-la inteira.
                    self._send(409, json.dumps(
                        {"ok": False, "erro": str(e)}, ensure_ascii=False),
                        "application/json; charset=utf-8")
                    return
                self._send(200, json.dumps(
                    {"ok": True, "ticket": ticket, "ticket_url": url},
                    ensure_ascii=False), "application/json; charset=utf-8")
                return
            if self.path == "/api/tratar-transferido":
                n = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
                rid = str(payload.get("id") or "").strip()
                ticket = str(payload.get("ticket") or "").strip()
                motivo = str(payload.get("motivo") or "").strip()
                erro = _validar_tratativa(rid, motivo, payload.get("descricao"),
                                          exige_motivo=False)
                if erro:
                    self._send(400, erro, "application/json; charset=utf-8")
                    return
                linhas = tratar_transferido(rid, ticket, payload.get("ticket_url"),
                                            payload.get("descricao"), motivo)
                self._send(200, json.dumps(
                    {"ok": linhas > 0,
                     "erro": None if linhas > 0 else "falha ao tratar",
                     "transferidos": listar_transferidos()}, ensure_ascii=False),
                    "application/json; charset=utf-8")
                return
            if self.path == "/api/atalho":
                n = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
                ok, msg, atalho = criar_atalho(
                    USUARIO,
                    payload.get("nome"),
                    payload.get("origem"),
                    payload.get("filtros") or [],
                )
                self._send(200 if ok else 422, json.dumps(
                    {"ok": ok, "erro": None if ok else msg, "atalho": atalho,
                     "atalhos": listar_atalhos(USUARIO, payload.get("origem") or "")},
                    ensure_ascii=False), "application/json; charset=utf-8")
                return
            if self.path == "/api/atalho/excluir":
                n = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
                ok, msg = excluir_atalho(USUARIO, payload.get("id"))
                origem = payload.get("origem") or ""
                self._send(200 if ok else 404, json.dumps(
                    {"ok": ok, "erro": None if ok else msg,
                     "atalhos": listar_atalhos(USUARIO, origem)},
                    ensure_ascii=False), "application/json; charset=utf-8")
                return
            if self.path == "/api/exportar":
                n = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
                nome = str(payload.get("arquivo") or "export").strip() or "export"
                cols = payload.get("colunas") or []
                rows = payload.get("linhas") or []
                xlsx = gerar_xlsx(cols, rows, payload.get("niveis"),
                                  payload.get("formatos"))
                self.send_response(200)
                self.send_header(
                    "Content-Type", "application/vnd.openxmlformats-"
                    "officedocument.spreadsheetml.sheet")
                self.send_header("Content-Disposition",
                                 f'attachment; filename="{nome}.xlsx"')
                self.send_header("Content-Length", str(len(xlsx)))
                self.end_headers()
                self.wfile.write(xlsx)
                print(f"  [EXPORT] {nome}.xlsx ({len(rows)} linhas)")
                return
            self._send(404, '{"erro":"rota"}', "application/json")
        except Exception as e:
            print(f"  [ERRO POST {self.path}] {e!r}")
            self._send(500, json.dumps({"erro": repr(e)}), "application/json")


# ── Atalhos personalizados (mesmo padrão de quarentena/resolução) ──────
LIMITE_ATALHOS_POR_ABA = 9


def _atalhos_db():
    """Lista de atalhos consolidados na tabela 'atalhos' (banco dobrado).
    Retorna [] se a tabela ainda nao existe (banco pre-1a dobra)."""
    out = []
    try:
        c = conn_ro()
        try:
            for r in c.execute("SELECT id, nome, origem, filtros, criado_por, "
                               "criado_em FROM atalhos"):
                try:
                    filtros = json.loads(r["filtros"] or "[]")
                except Exception:
                    filtros = []
                out.append({
                    "id": r["id"], "nome": r["nome"], "origem": r["origem"] or "",
                    "filtros": filtros, "criado_por": r["criado_por"] or "",
                    "criado_em": r["criado_em"] or "",
                })
        finally:
            c.close()
    except Exception:
        pass
    return out


def _atalhos_vivos():
    """Estado vivo {id: ultima_interacao} do tipo ATALHO. CRIAR e EXCLUIR
    competem por id — vence a interacao de data_acao mais recente."""
    atual = {}
    for it in _interacoes_ler():
        if it.get("tipo_interacao") != "ATALHO":
            continue
        rid = it.get("registro_id")
        if not rid:
            continue
        ant = atual.get(rid)
        if ant is None or str(it.get("data_acao", "")) >= str(ant.get("data_acao", "")):
            atual[rid] = it
    return atual


def listar_atalhos(usuario, origem=""):
    """Lista atalhos visiveis pro `usuario` na aba `origem` (incl|consulta).
    Mescla tabela dobrada + interacoes vivas da rede (vivas sobrepoem)."""
    final = {}
    for a in _atalhos_db():
        if a["criado_por"] == usuario and (not origem or a["origem"] == origem):
            final[a["id"]] = a
    for rid, it in _atalhos_vivos().items():
        # so do usuario atual
        if (it.get("usuario") or "") != usuario:
            continue
        ex = it.get("extras") or {}
        if origem and ex.get("origem") != origem:
            continue
        if it.get("acao") == "EXCLUIR":
            final.pop(rid, None)
        else:  # CRIAR
            final[rid] = {
                "id": rid, "nome": ex.get("nome") or rid,
                "origem": ex.get("origem") or "",
                "filtros": ex.get("filtros") or [],
                "criado_por": it.get("usuario") or "",
                "criado_em": it.get("data_acao") or "",
            }
    return sorted(final.values(), key=lambda a: a.get("criado_em") or "")


def _normalizar_filtros(filtros):
    """Devolve tupla ordenada de pares (fid, valor) — para comparar como
    CONJUNTO (ordem dos pares e ordem dos valores dentro nao importam)."""
    if not filtros:
        return tuple()
    return tuple(sorted((str(f), str(v)) for f, v in filtros))


def criar_atalho(usuario, nome, origem, filtros):
    """Grava interacao ATALHO/CRIAR no JSONL do usuario.
    Aplica:
      - limite de LIMITE_ATALHOS_POR_ABA por (usuario, origem)
      - validacao de duplicacao: rejeita se ja existe filtro do usuario com
        os mesmos criterios (mesmo conjunto de filtros)
    Retorna (ok: bool, mensagem: str, atalho: dict|None)."""
    nome = (nome or "").strip()
    origem = (origem or "").strip()
    if not nome:
        return False, "nome obrigatório", None
    if origem not in ("incl", "hist", "consulta", "conf"):
        return False, "origem inválida (use 'incl', 'hist', 'consulta' ou 'conf')", None
    if not isinstance(filtros, list):
        return False, "filtros precisa ser lista", None
    atuais = listar_atalhos(usuario, origem)
    # Validacao 1: limite
    if len(atuais) >= LIMITE_ATALHOS_POR_ABA:
        return False, (f"limite de {LIMITE_ATALHOS_POR_ABA} filtros nesta "
                       f"aba atingido — exclua algum antes"), None
    # Validacao 2: duplicacao de criterios
    chave_nova = _normalizar_filtros(filtros)
    for a in atuais:
        if _normalizar_filtros(a.get("filtros") or []) == chave_nova:
            return False, (f"Já existe um filtro salvo com esses mesmos "
                           f"critérios: \"{a['nome']}\". "
                           f"Abra 'Meus filtros' para ver/usar."), None
    rid = f"atl_{int(time.time()*1000)}"
    interacao = {
        "schema_version": 1,
        "tipo_interacao": "ATALHO",
        "registro_id": rid,
        "acao": "CRIAR",
        "usuario": usuario,
        "data_acao": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "extras": {"nome": nome, "origem": origem, "filtros": filtros},
    }
    try:
        _interacao_gravar(interacao)
    except Exception as e:
        return False, f"falha ao gravar: {e!r}", None
    return True, "ok", {
        "id": rid, "nome": nome, "origem": origem, "filtros": filtros,
        "criado_por": usuario, "criado_em": interacao["data_acao"],
    }


def excluir_atalho(usuario, atalho_id):
    """Grava interacao ATALHO/EXCLUIR no JSONL do usuario. So permite excluir
    atalho do PROPRIO usuario (autoridade local)."""
    rid = str(atalho_id or "").strip()
    if not rid:
        return False, "id obrigatório"
    # Confere que o atalho existe e e' do usuario (evita EXCLUIR alheio)
    visiveis = {a["id"] for a in listar_atalhos(usuario)}
    if rid not in visiveis:
        return False, "atalho não encontrado para este usuário"
    interacao = {
        "schema_version": 1,
        "tipo_interacao": "ATALHO",
        "registro_id": rid,
        "acao": "EXCLUIR",
        "usuario": usuario,
        "data_acao": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "extras": {},
    }
    try:
        _interacao_gravar(interacao)
    except Exception as e:
        return False, f"falha ao gravar: {e!r}"
    return True, "ok"


def banner():
    print("=" * 64)
    print(" VISUALIZADOR CVC IAM — servidor (SQLite ao vivo)")
    print("=" * 64)
    print(f"  Pasta exe : {BASE}")
    print(f"  Config    : {CONFIG_SRC}")
    print(f"  Banco     : {DB_PATH}")
    print(f"  Escopo    : {SISTEMA or '(todos)'} | quarentena {QUAR_DIAS} dias")
    # Sem tela de teste, um valor errado no jira.xml so' apareceria quando um
    # chamado falhasse. Aqui ele aparece na abertura.
    print(f"  {jira_diagnostico()}")
    print(f"  Endereco  : http://{HOST}:{PORT}/")
    print("=" * 64)


def _rede_db_path():
    """Caminho do banco NA REDE (modo rede) ou local (modo local)."""
    raiz = REDE_RAIZ if REDE_RAIZ else RAIZ_APP
    p = BANCO_SUB if os.path.isabs(BANCO_SUB) else os.path.join(raiz, BANCO_SUB)
    return os.path.abspath(p)


def _banco_disponivel():
    """True se o banco DA REDE ja existe.

    O visualizador NAO dispara mais o Processador — quem roda e' o responsavel,
    manualmente (na maquina que tem o motor). Se faltar banco, main() sobe a
    pagina _PAGINA_SEM_BANCO em vez de travar 'importando'. O auto-update (copiar
    a versao da rede pro local) e' independente disto e segue funcionando."""
    return os.path.exists(_rede_db_path())


def main():
    global SRV, _SEM_BANCO
    # Auto-update agora e' responsabilidade do principal (visualizador.exe no
    # top level) e do launcher_atualizador.exe. Este core so SERVE o painel.
    banner()
    # Se o banco da rede ainda nao existe, NAO disparamos o Processador (o
    # responsavel roda ele manualmente). Subimos o servidor mostrando uma
    # pagina clara — assim a aba do auto-update cai nela, sem girar "importando".
    _SEM_BANCO = not _banco_disponivel()
    if _SEM_BANCO:
        print(f"  [sem-banco] {_rede_db_path()} ausente — servindo aviso "
              f"'rode o Processador' (visualizador nao dispara o Processador).")
    else:
        try:
            garantir_estrutura(force=("refresh" in [a.lower() for a in sys.argv[1:]]))
        except Exception as e:
            print(f"  [FALHA] estrutura: {e!r}")
            time.sleep(8)
            return 1
        if len(sys.argv) > 1 and sys.argv[1].lower() == "selftest":
            db = construir_db()
            print("  KPIs :", db["kpis"])
            print("  Acao :", db["acao_dist"])
            print("  Sist :", db["sis_dist"])
            print("  Users:", len(db["users"]))
            return 0
        if not os.path.exists(INDEX_PATH):
            print(f"  [FALHA] index.html nao encontrado: {INDEX_PATH}")
            return 1
    try:
        srv = ThreadingHTTPServer((HOST, PORT), H)
    except OSError as e:
        print(f"  [FALHA] nao abriu {HOST}:{PORT} -> {e!r}")
        time.sleep(8)
        return 1
    SRV = srv
    threading.Thread(target=_watchdog, daemon=True).start()
    url = f"http://{HOST}:{PORT}/"
    print(f"  No ar. Abrindo {url} (encerra ao fechar a pagina).")
    if os.environ.get("VISUALIZADOR_NOBROWSER") != "1":
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
