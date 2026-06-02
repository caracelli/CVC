# -*- coding: utf-8 -*-
"""
Visualizador CVC IAM — servidor local que torna o index.html FUNCIONAL e
IGUALZINHO ao BI, lendo direto do SQLite (sem Parquet), por queries.

Conceito (validado por numeros == Parquet do BI, 6963 linhas):
  - bi_divergencias  = TABELA ESTATICA (snapshot do cenario do BI)
        Fonte 1: validacao_acessos (tipo = status, acao = label)
        Fonte 2: divergencias onde tipo = ACESSO_SEM_VINCULO_RH (acao = 'Não Mapeado')
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
import subprocess
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
}

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
    origem = "padrao"
    if os.path.exists(CONFIG_PATH):
        try:
            root = ET.parse(CONFIG_PATH).getroot()
            rede_raiz = (root.findtext("rede/raiz") or "").strip()
            v = (root.findtext("rede/banco_dados") or "").strip()
            if v:
                banco_sub = v
            s = (root.findtext("visualizador/sistema") or "").strip()
            if s:
                sistema = s
            q = (root.findtext("visualizador/quarentena_dias") or "").strip()
            if q:
                duracao = int(q)
            origem = "config.xml"
        except Exception as e:
            origem = f"config.xml invalido ({e!r}) -> padrao"
    return rede_raiz, banco_sub, sistema, duracao, origem


REDE_RAIZ, BANCO_SUB, SISTEMA, QUAR_DIAS, CONFIG_SRC = carregar_config()

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
        return os.path.getmtime(rede_db) > os.path.getmtime(local_db)
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


def _resolucoes_db():
    """Resolucoes ja dobradas no banco pelo Processador {registro_id: dados}."""
    c = conn_ro()
    try:
        tem = c.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                        "AND name='resolucoes'").fetchone()
        if not tem:
            return {}
        out = {}
        for r in c.execute(
                "SELECT registro_id,ticket,ticket_url,descricao,pendencias,"
                "cargo,centro_custo,nome,resolvido_por,resolvido_em "
                "FROM resolucoes"):
            try:
                pend = json.loads(r["pendencias"]) if r["pendencias"] else []
            except Exception:
                pend = []
            out[r["registro_id"]] = {
                "ticket": r["ticket"] or "", "ticket_url": r["ticket_url"] or "",
                "descricao": r["descricao"] or "",
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
            "cargo": it.get("cargo") or "",
            "centro_custo": it.get("centro_custo") or "",
            "nome": it.get("nome") or "",
            "por": it.get("usuario") or "",
            "em": it.get("data_acao") or "",
            "pendencias": it.get("pendencias") or [],
        }
    return out


def _sintetizar_ativa(rid, it):
    """Linha de quarentena ativa a partir de uma interacao ENVIAR viva.
    nome/sistema vem da propria interacao (gravados no envio)."""
    di = (it.get("data_acao") or "")[:10]
    try:
        df = (datetime.strptime(di, "%Y-%m-%d")
              + timedelta(days=QUAR_DIAS)).strftime("%Y-%m-%d")
    except Exception:
        df = di
    return {"id": rid, "usuario": rid,
            "nome_usuario": it.get("nome") or rid,
            "sistema": it.get("sistema") or "",
            "origem": it.get("origem") or "Inclusão / Alteração",
            "data_inicio": di, "data_fim": df,
            "criado_por": it.get("usuario") or ""}


def _sintetizar_historico(rid, it, anterior):
    """Linha de historico a partir de uma interacao RESOLVER viva."""
    ds = (it.get("data_acao") or "")[:10]
    if anterior:
        base = dict(anterior)
    else:
        nome, sis, _ = _meta_divergencia(rid)
        base = {"nome_usuario": nome, "sistema": sis, "origem": "",
                "data_inicio": ds, "data_fim": ds}
    base.update({"id": rid, "usuario": rid, "data_saida": ds,
                 "motivo": "Resolvido", "movido_em": it.get("data_acao") or ds,
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
  COALESCE(v.dt_processamento,'') AS data_identificacao,
  0                              AS resolvida,
  CASE v.status WHEN 'SEM_ACESSO' THEN 'Incluir Acesso'
                WHEN 'DIVERGENTE' THEN 'Alterar Perfil'
                WHEN 'EM_ANALISE' THEN 'Em Análise' ELSE '' END AS acao,
  COALESCE(v.origem_matriz,'') AS origem
FROM validacao_acessos v
UNION ALL
SELECT
  d.id, d.tipo, d.sistema, d.usuario,
  COALESCE(NULLIF(d.nome_usuario,''), d.usuario) AS nome_usuario,
  COALESCE(d.matricula,'') AS matricula,
  COALESCE(d.perfil_encontrado,'') AS perfil_encontrado,
  COALESCE(d.perfil_esperado,'')  AS perfil_esperado,
  COALESCE(d.descricao,'')        AS descricao,
  COALESCE(d.data_identificacao,'') AS data_identificacao,
  d.resolvida, 'Não Mapeado' AS acao, '' AS origem
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
  criado_por TEXT, criado_em TEXT, encerrado_por TEXT,
  movido_em TEXT NOT NULL
)
"""


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
    quarentena = sempre garante. Indices sempre garantidos."""
    c = conn_rw()
    try:
        existe = c.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='bi_divergencias'"
        ).fetchone()
        if existe and not force:
            cols = [r[1] for r in c.execute("PRAGMA table_info(bi_divergencias)")]
            if "origem" not in cols:
                force = True  # migração de schema: coluna 'origem' nova
        if force or not existe:
            c.execute("DROP TABLE IF EXISTS bi_divergencias")
            c.executescript(_SQL_BI)
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
            "data_fim,criado_por,criado_em FROM quarentena "
            "WHERE substr(data_fim,1,10) < ?", [hoje]).fetchall()
        for r in venc:
            c.execute(
                "INSERT INTO quarentena_historico (usuario,nome_usuario,sistema,"
                "matricula,origem,data_inicio,data_fim,data_saida,motivo,"
                "criado_por,criado_em,encerrado_por,movido_em) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[7],
                 "Prazo vencido", r[8], r[9], None, agora])
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
        if nv:
            ol = ' outlineLevel="1" hidden="1"'   # detalhe: recolhido por padrao
        elif prox:
            ol = ' collapsed="1"'                  # linha-pai de um grupo recolhido
        else:
            ol = ""
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
    sheet_pr = '<sheetPr><outlinePr summaryBelow="0"/></sheetPr>' if agrupado else ''
    fmt_pr = '<sheetFormatPr defaultRowHeight="15" outlineLevelRow="1"/>' if agrupado else ''
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
            em_quar.add(rid)
        elif it.get("acao") == "RESOLVER":
            em_quar.discard(rid)
    # sobrepoe as resolucoes (banco dobrado + interacoes vivas): o funcionario
    # resolvido ganha u.resolvido + u.resolucao e todas as divs viram Resolvido.
    resolvidos = _resolucoes_mescladas(_interacoes)
    users = []
    for u in _BASE["users"]:
        if u["u"] in em_quar:
            continue
        r = resolvidos.get(u["u"])
        if r:
            uc = dict(u)
            uc["resolvido"] = True
            uc["resolucao"] = r
            uc["divs"] = [dict(d, s="Resolvido") for d in u["divs"]]
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
            "users": users, "vg": vg}


def _montar_base():
    """Parte estatica do DB (bi_divergencias + JOIN), sem o filtro de quarentena."""
    c = conn_ro()
    try:
        whereS = "WHERE sistema = ?" if SISTEMA else ""
        argS = [SISTEMA] if SISTEMA else []

        sis_dist = {r["sistema"]: r["n"] for r in c.execute(
            "SELECT sistema, COUNT(*) n FROM bi_divergencias GROUP BY sistema")}

        def cont(t):
            return c.execute(
                f"SELECT COUNT(*) FROM bi_divergencias {whereS} "
                f"{'AND' if whereS else 'WHERE'} tipo=?", argS + [t]).fetchone()[0]

        kpis = {
            "sem_acesso": cont("SEM_ACESSO"),
            "divergente": cont("DIVERGENTE"),
            "em_analise": cont("EM_ANALISE"),
            "nao_mapeado": cont("ACESSO_SEM_VINCULO_RH"),
            "total": c.execute(
                f"SELECT COUNT(*) FROM bi_divergencias {whereS}", argS).fetchone()[0],
        }
        acao_dist = {r["acao"]: r["n"] for r in c.execute(
            f"SELECT acao, COUNT(*) n FROM bi_divergencias {whereS} "
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
                       b.resolvida, b.origem, b.sistema,
                       COALESCE(r.cargo_descricao,'') cargo,
                       COALESCE(r.departamento,'')   depto,
                       COALESCE(r.centro_custo_codigo,'') cc_cod,
                       COALESCE(r.centro_custo_nome,'')   cc_nome,
                       COALESCE(r.cpf,'')   cpf,
                       COALESCE(r.email,'') email,
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
                     "divs": []}
                users[r["usuario"]] = u
            tp = r["tipo"]
            u["divs"].append({
                "t": tp, "tl": TIPO_LABEL.get(tp, tp), "a": r["acao"],
                "sis": r["sistema"] or "",
                "pe": r["perfil_encontrado"], "pp": r["perfil_esperado"],
                "dt": r["data_identificacao"] or "",
                "s": "Resolvido" if r["resolvida"] else "Pendente",
                # vinculo lido do rh_ativos (tipo_vinculo): Funcionário (CLT)
                # ou Terceiro (prestador de fornecedor).
                "vinc": "Terceiro" if r["tipo_vinc"] == "TERCEIRO" else "Funcionário",
                "o": ("Matriz " + (r["sistema"] or "")) if r["origem"] == "MATRIZ"
                     else ("Matriz CCO" if r["origem"] == "CCO" else "—"),
            })
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
        return {"kpis": kpis, "acao_dist": acao_dist, "sis_dist": sis_dist,
                "users": list(users.values()), "meta": meta, "vg": vg}
    finally:
        c.close()


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
    try:
        out["pendentes"] = c.execute(
            f"SELECT COUNT(*) FROM bi_divergencias WHERE resolvida=0{whereS}",
            argS).fetchone()[0]
    except Exception:
        out["pendentes"] = c.execute(
            "SELECT COUNT(*) FROM validacao_acessos "
            "WHERE situacao_acao='PENDENTE'").fetchone()[0]
    # Acessos de desligado: limita ao sistema do escopo
    wsis = "WHERE a.sistema = ?" if sistema else ""
    out["acessos_deslig"] = c.execute(
        f"SELECT COUNT(*) FROM acessos_sistemas a "
        f"JOIN rh_desligados d ON a.matricula_vinculada = d.matricula {wsis}",
        argS).fetchone()[0]
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

    # Divergências por tipo (do sistema do escopo)
    out["div_tipos"] = {r[0]: r[1] for r in c.execute(
        f"SELECT tipo, COUNT(*) FROM divergencias "
        + (" WHERE sistema = ?" if sistema else "") + " GROUP BY tipo",
        argS)}
    # Concentração por sistema. RESPEITA o escopo configurado (visualizador/sistema):
    # com escopo SYSTUR mostra SO SYSTUR (requisito da 1a entrega = nada alem de
    # SYSTUR); com escopo vazio (multi-sistema futuro) mostra TODOS. O painel
    # continua multi-sistema-ready — quem manda e' o escopo, nao um filtro fixo.
    out["div_sistemas"] = {r[0]: r[1] for r in c.execute(
        "SELECT sistema, COUNT(*) FROM divergencias "
        + ("WHERE sistema = ? " if sistema else "")
        + "GROUP BY sistema ORDER BY 2 DESC", argS)}

    # Top 10 desligados recentes ainda com acesso ativo NO SISTEMA do escopo
    hoje = datetime.date.today()
    top = []
    wsis_top = "AND a.sistema = ?" if sistema else ""
    for r in c.execute(f"""
        SELECT d.nome, d.data_desligamento, d.cargo_descricao,
               COUNT(DISTINCT a.sistema) AS sistemas, COUNT(*) AS perfis
        FROM rh_desligados d
        JOIN acessos_sistemas a ON a.matricula_vinculada = d.matricula
        WHERE d.data_desligamento IS NOT NULL {wsis_top}
        GROUP BY d.matricula
        ORDER BY d.data_desligamento DESC LIMIT 10
    """, argS):
        try:
            dias = (hoje - datetime.date.fromisoformat(r[1])).days
        except Exception:
            dias = None
        top.append({"nome": r[0], "data": r[1], "dias": dias,
                    "cargo": r[2], "sistemas": r[3], "perfis": r[4]})
    out["top_urgentes"] = top

    # Aging: agrupa validacao_acessos PENDENTE por faixa etária (dt_processamento)
    aging = {"0-7": 0, "8-30": 0, "31-90": 0, "90+": 0}
    for r in c.execute("""
        SELECT dt_processamento FROM validacao_acessos
        WHERE situacao_acao='PENDENTE' AND dt_processamento IS NOT NULL
    """):
        try:
            dt = datetime.datetime.fromisoformat(str(r[0])[:19]).date()
            dias = (hoje - dt).days
        except Exception:
            continue
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
    chamados = {"identificados": 0, "resolvidos": 0, "tempo_medio_dias": 0}
    corte = (hoje - datetime.timedelta(days=VG_JANELA_DIAS)).isoformat()
    try:
        chamados["identificados"] = c.execute(
            "SELECT COUNT(*) FROM validacao_acessos "
            "WHERE date(dt_processamento) >= ?", (corte,)
        ).fetchone()[0]
    except Exception:
        pass
    try:
        chamados["resolvidos"] = c.execute(
            "SELECT COUNT(*) FROM resolucoes "
            "WHERE date(resolvido_em) >= ?", (corte,)
        ).fetchone()[0]
    except Exception:
        pass  # tabela resolucoes ainda nao existe em banco virgem
    out["chamados"] = chamados

    return out


def enviar_quarentena(usuarios, origem="Inclusão / Alteração"):
    """Grava uma interacao ENVIAR (QUARENTENA) na rede para cada usuario novo.
    Nao escreve mais na tabela local — a tabela e' snapshot do Processador."""
    agora = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    fim = (datetime.now() + timedelta(days=QUAR_DIAS)).strftime("%Y-%m-%d")
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
        nome, sis, _ = _meta_divergencia(u)
        _interacao_gravar({
            "tipo_interacao": "QUARENTENA", "registro_id": u, "acao": "ENVIAR",
            "usuario": USUARIO, "data_acao": agora, "origem": origem,
            "nome": nome, "sistema": sis,
        })
        ja.add(u)
        novos += 1
    print(f"  [QUARENTENA] +{novos} ENVIAR por {USUARIO} "
          f"(ignorados {len(usuarios)-novos} ja ativos)")
    return {"novos": novos, "total": len(ja), "data_fim": fim}


def listar_quarentena():
    """{ativas, historico}: snapshot do DB local sobreposto pelas interacoes
    vivas da rede (ENVIAR entra em ativas, RESOLVER move para historico)."""
    sweep_expiradas()
    hoje = datetime.now().strftime("%Y-%m-%d")
    c = conn_ro()
    try:
        ativas = {r["usuario"]: dict(r) for r in c.execute(
            "SELECT id,usuario,nome_usuario,sistema,origem,data_inicio,"
            "data_fim,criado_por FROM quarentena ORDER BY data_fim")}
        historico = [dict(r) for r in c.execute(
            "SELECT id,usuario,nome_usuario,sistema,origem,data_inicio,"
            "data_fim,data_saida,motivo,encerrado_por,movido_em "
            "FROM quarentena_historico ORDER BY movido_em DESC")]
    finally:
        c.close()

    for rid, it in _quarentena_viva().items():
        acao = it.get("acao")
        if acao == "ENVIAR":
            if rid not in ativas:
                ativas[rid] = _sintetizar_ativa(rid, it)
        elif acao == "RESOLVER":
            anterior = ativas.pop(rid, None)
            historico.insert(0, _sintetizar_historico(rid, it, anterior))

    lista = list(ativas.values())
    for r in lista:
        r["id"] = r["usuario"]                       # id uniforme = registro_id
        r["dias_restantes"] = max(0, _dias(hoje, r.get("data_fim", "")))
    for r in historico:
        r["periodo_dias"] = _dias(r.get("data_inicio", ""), r.get("data_saida", ""))
    return {"ativas": lista, "historico": historico}


def retirar_quarentena(registro_id):
    """Grava uma interacao RESOLVER (QUARENTENA) na rede. Devolve 1 se gravou."""
    rid = str(registro_id or "").strip()
    if not rid:
        return 0
    _interacao_gravar({
        "tipo_interacao": "QUARENTENA", "registro_id": rid, "acao": "RESOLVER",
        "usuario": USUARIO,
        "data_acao": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    })
    print(f"  [QUARENTENA] RESOLVER ({rid}) por {USUARIO}")
    return 1


def resolver_pendencia(registro_id, ticket, ticket_url="", descricao=""):
    """Grava uma interacao RESOLUCAO na rede — marca o funcionario como
    resolvido sob um ticket do Jira. Devolve 1 se gravou."""
    rid = str(registro_id or "").strip()
    tk = str(ticket or "").strip()
    if not rid or not tk:
        return 0
    nome, _, _ = _meta_divergencia(rid)
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
            for r in c.execute(
                    "SELECT tipo, acao, sistema, perfil_encontrado, "
                    "perfil_esperado, origem FROM bi_divergencias "
                    "WHERE usuario=?", [rid]):
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
        "tipo_interacao": "RESOLUCAO", "registro_id": rid, "acao": "RESOLVER",
        "ticket": tk,
        "ticket_url": str(ticket_url or "").strip(),
        "descricao": str(descricao or "").strip(),
        "cargo": cargo, "centro_custo": centro_custo,
        "pendencias": pend,
        "nome": nome, "usuario": USUARIO,
        "data_acao": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    })
    print(f"  [RESOLUCAO] {rid} ticket={tk} ({len(pend)} pend.) por {USUARIO}")
    return 1


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
                # dados do encerramento, comuns às 2 linhas (p/ o modal de detalhe)
                tk = {
                    "ticket": rdat.get("ticket") or "",
                    "ticket_url": rdat.get("ticket_url") or "",
                    "descricao": rdat.get("descricao") or "",
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
    out.sort(key=lambda x: x.get("_ord") or "", reverse=True)
    return out


def html_injetado():
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        linhas = f.read().split("\n")
    js = "const DB = " + json.dumps(construir_db(), ensure_ascii=False) + ";"
    for i, ln in enumerate(linhas):
        if ln.lstrip().startswith("const DB ="):
            linhas[i] = js
            break
    else:
        raise RuntimeError("linha 'const DB =' nao encontrada no index.html")
    return "\n".join(linhas)


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        b = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
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
                res = enviar_quarentena(us, origem)
                self._send(200, json.dumps(
                    {"ok": True, "resultado": res,
                     "quarentena": listar_quarentena()}, ensure_ascii=False),
                    "application/json; charset=utf-8")
                return
            if self.path == "/api/quarentena/retirar":
                n = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
                qid = payload.get("id")
                if qid is None:
                    self._send(400, '{"ok":false,"erro":"sem id"}',
                               "application/json")
                    return
                linhas = retirar_quarentena(qid)
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
                if not rid or not ticket:
                    self._send(400, '{"ok":false,"erro":"id e ticket obrigatorios"}',
                               "application/json")
                    return
                linhas = resolver_pendencia(rid, ticket, payload.get("ticket_url"),
                                            payload.get("descricao"))
                self._send(200, json.dumps(
                    {"ok": linhas > 0,
                     "erro": None if linhas > 0 else "falha ao resolver",
                     "dados": construir_db()}, ensure_ascii=False),
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
    if origem not in ("incl", "hist", "consulta"):
        return False, "origem inválida (use 'incl', 'hist' ou 'consulta')", None
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
