# -*- coding: utf-8 -*-
"""
Mockup CVC IAM — servidor local que torna o index.html FUNCIONAL e
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
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST, PORT = "127.0.0.1", 8800

if getattr(sys, "frozen", False):
    BASE = os.path.dirname(sys.executable)
else:
    BASE = os.path.dirname(os.path.abspath(__file__))

LOG_PATH = os.path.join(BASE, "mockup_log.txt")
INDEX_PATH = os.path.join(BASE, "index.html")
CONFIG_PATH = os.path.join(BASE, "config.xml")


class _Tee:
    def __init__(self, p):
        self._f = open(p, "a", encoding="utf-8", errors="replace")
        self._o = sys.__stdout__
    def write(self, s):
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
_OCIOSO = 15
_BASE = None   # cache da parte cara do DB (bi_divergencias + JOIN); 1x por execução


def _enc(motivo):
    print(f"  [ENCERRANDO] {motivo}")
    if SRV is not None:
        threading.Thread(target=SRV.shutdown, daemon=True).start()


def _watchdog():
    while True:
        time.sleep(3)
        if _armed and (time.time() - _last_seen) > _OCIOSO:
            _enc(f"pagina fechada (sem heartbeat >{_OCIOSO}s)")
            return


def carregar_config():
    db = os.path.join(BASE, "..", "DADOS", "BANCO", "iam_analytics.db")
    sistema = "SYSTUR"
    duracao = 30
    origem = "padrao"
    if os.path.exists(CONFIG_PATH):
        try:
            root = ET.parse(CONFIG_PATH).getroot()
            b = root.find("banco")
            if b is not None:
                v = b.get("caminho") or (b.text or "").strip()
                if v:
                    db = v if os.path.isabs(v) else os.path.join(BASE, v)
            s = root.find("sistema")
            if s is not None:
                sistema = (s.get("valor") or (s.text or "")).strip()
            q = root.find("quarentena")
            if q is not None and q.get("duracao_dias"):
                duracao = int(q.get("duracao_dias"))
            origem = "config.xml"
        except Exception as e:
            origem = f"config.xml invalido ({e!r}) -> padrao"
    return os.path.abspath(db), sistema, duracao, origem


DB_PATH, SISTEMA, QUAR_DIAS, CONFIG_SRC = carregar_config()

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
    if own:
        c = conn_rw()
    try:
        hoje = datetime.now().strftime("%Y-%m-%d")
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
    return {"kpis": _BASE["kpis"], "acao_dist": _BASE["acao_dist"],
            "sis_dist": _BASE["sis_dist"], "meta": _BASE["meta"],
            "users": [u for u in _BASE["users"] if u["u"] not in em_quar]}


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
                       COALESCE(r.departamento,'')   depto
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
                     "divs": []}
                users[r["usuario"]] = u
            tp = r["tipo"]
            u["divs"].append({
                "t": tp, "tl": TIPO_LABEL.get(tp, tp), "a": r["acao"],
                "pe": r["perfil_encontrado"], "pp": r["perfil_esperado"],
                "dt": (r["data_identificacao"] or "")[:10],
                "s": "Resolvida" if r["resolvida"] else "Pendente",
                "o": ("Matriz " + (r["sistema"] or "")) if r["origem"] == "MATRIZ"
                     else ("Matriz CCO" if r["origem"] == "CCO" else "—"),
            })
        maxdt = c.execute(
            "SELECT MAX(data_identificacao) FROM bi_divergencias "
            "WHERE data_identificacao <> ''").fetchone()[0] or ""
        meta = {"referencia": _mes_ref(maxdt), "atualizacao": _fmt_dt(maxdt)}
        return {"kpis": kpis, "acao_dist": acao_dist, "sis_dist": sis_dist,
                "users": list(users.values()), "meta": meta}
    finally:
        c.close()


def enviar_quarentena(usuarios, origem="Inclusão / Alteração"):
    """Grava usuarios na tabela quarentena (data_fim = inicio + QUAR_DIAS)."""
    ini = datetime.now()
    fim = ini + timedelta(days=QUAR_DIAS)
    si, sf = ini.strftime("%Y-%m-%d %H:%M:%S"), fim.strftime("%Y-%m-%d %H:%M:%S")
    cro = conn_ro()
    try:
        meta = {}
        for u in usuarios:
            row = cro.execute(
                "SELECT nome_usuario, sistema, matricula FROM bi_divergencias "
                "WHERE usuario=? LIMIT 1", [u]).fetchone()
            meta[u] = (row["nome_usuario"] if row else u,
                       row["sistema"] if row else "",
                       row["matricula"] if row else "")
    finally:
        cro.close()
    c = conn_rw()
    try:
        ja = {r[0] for r in c.execute("SELECT usuario FROM quarentena")}
        novos = 0
        for u in usuarios:
            if u in ja:
                continue
            nome, sis, mat = meta.get(u, (u, "", ""))
            c.execute(
                "INSERT INTO quarentena (usuario,nome_usuario,sistema,matricula,"
                "origem,data_inicio,data_fim,status,criado_por,criado_em) "
                "VALUES (?,?,?,?,?,?,?, 'Em quarentena', ?, ?)",
                [u, nome, sis, mat, origem, si, sf, USUARIO, si])
            novos += 1
        c.commit()
        total = c.execute("SELECT COUNT(*) FROM quarentena").fetchone()[0]
        print(f"  [QUARENTENA] +{novos} (ignorados {len(usuarios)-novos} ja ativos) | total {total}")
        return {"novos": novos, "total": total, "data_fim": sf}
    finally:
        c.close()


def listar_quarentena():
    """Devolve {ativas, historico}: tabelas quarentena e quarentena_historico."""
    sweep_expiradas()
    hoje = datetime.now().strftime("%Y-%m-%d")
    c = conn_ro()
    try:
        ativas = [dict(r) for r in c.execute(
            "SELECT id,usuario,nome_usuario,sistema,origem,data_inicio,"
            "data_fim FROM quarentena ORDER BY data_fim")]
        historico = [dict(r) for r in c.execute(
            "SELECT id,usuario,nome_usuario,sistema,origem,data_inicio,"
            "data_fim,data_saida,motivo,movido_em "
            "FROM quarentena_historico ORDER BY movido_em DESC")]
    finally:
        c.close()
    for r in ativas:
        r["dias_restantes"] = max(0, _dias(hoje, r["data_fim"]))
    for r in historico:
        r["periodo_dias"] = _dias(r["data_inicio"], r["data_saida"])
    return {"ativas": ativas, "historico": historico}


def retirar_quarentena(qid):
    """Retira da quarentena: move o registro para o historico com motivo
    'Retirada manual'. Devolve 1 se moveu, 0 se nao encontrou."""
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c = conn_rw()
    try:
        r = c.execute(
            "SELECT usuario,nome_usuario,sistema,matricula,origem,data_inicio,"
            "data_fim,criado_por,criado_em FROM quarentena WHERE id=?",
            [qid]).fetchone()
        if not r:
            return 0
        c.execute(
            "INSERT INTO quarentena_historico (usuario,nome_usuario,sistema,"
            "matricula,origem,data_inicio,data_fim,data_saida,motivo,criado_por,"
            "criado_em,encerrado_por,movido_em) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [r[0], r[1], r[2], r[3], r[4], r[5], r[6], agora,
             "Retirada manual", r[7], r[8], USUARIO, agora])
        c.execute("DELETE FROM quarentena WHERE id=?", [qid])
        c.commit()
        print(f"  [QUARENTENA] retirada id={qid} ({r[0]}) -> historico")
        return 1
    finally:
        c.close()


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
        global _last_seen, _armed
        try:
            if self.path in ("/", "/index.html"):
                self._send(200, html_injetado(), "text/html; charset=utf-8")
            elif self.path == "/api/dados":
                self._send(200, json.dumps(construir_db(), ensure_ascii=False),
                           "application/json; charset=utf-8")
            elif self.path == "/api/quarentena":
                self._send(200, json.dumps(listar_quarentena(), ensure_ascii=False),
                           "application/json; charset=utf-8")
            elif self.path == "/api/ping":
                _last_seen = time.time(); _armed = True
                self._send(200, '{"ok":true}', "application/json")
            elif self.path == "/api/encerrar":
                self._send(200, '{"ok":true}', "application/json")
                _enc("pedido da pagina (GET)")
            elif self.path == "/chart.umd.min.js":
                p = os.path.join(BASE, "chart.umd.min.js")
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
                self._send(200, '{"ok":true}', "application/json")
                _enc("pagina fechada (sendBeacon)")
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
                linhas = retirar_quarentena(int(qid))
                self._send(200, json.dumps(
                    {"ok": linhas > 0,
                     "erro": None if linhas > 0 else "quarentena nao encontrada",
                     "quarentena": listar_quarentena()}, ensure_ascii=False),
                    "application/json; charset=utf-8")
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


def banner():
    print("=" * 64)
    print(" MOCKUP CVC IAM — servidor (SQLite ao vivo, igual ao BI)")
    print("=" * 64)
    print(f"  Pasta exe : {BASE}")
    print(f"  Config    : {CONFIG_SRC}")
    print(f"  Banco     : {DB_PATH}")
    print(f"  Escopo    : {SISTEMA or '(todos)'} | quarentena {QUAR_DIAS} dias")
    print(f"  Endereco  : http://{HOST}:{PORT}/")
    print("=" * 64)


def main():
    global SRV
    banner()
    if not os.path.exists(DB_PATH):
        print(f"  [FALHA] banco nao encontrado: {DB_PATH}")
        time.sleep(8)
        return 1
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
    if os.environ.get("MOCKUP_NOBROWSER") != "1":
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
