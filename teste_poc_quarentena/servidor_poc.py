# -*- coding: utf-8 -*-
"""
POC Quarentena — servidor local de teste.
Só biblioteca padrão (http.server + sqlite3). Sem dependência externa.

Objetivo do teste na máquina do cliente:
  1. Um .exe não-assinado consegue EXECUTAR (AppLocker/EDR/SmartScreen)?
  2. Consegue ABRIR socket loopback 127.0.0.1?
  3. Tem PERMISSÃO DE ESCRITA do SQLite na pasta onde está?
  4. O navegador ABRE a página local?

Prova objetiva via git: grava `teste.db` (SQLite) e `registros.txt` (texto,
diff legível) na MESMA pasta do executável.

Uso:
  ServidorPOC.exe            -> sobe servidor + abre navegador
  ServidorPOC.exe selftest   -> autoteste headless (grava 1 registro e sai)
"""
import sys, os, json, time, socket, sqlite3, threading, webbrowser, getpass
import xml.etree.ElementTree as ET
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = "127.0.0.1"
PORT = 8799

if getattr(sys, "frozen", False):
    BASE = os.path.dirname(sys.executable)          # rodando como .exe
else:
    BASE = os.path.dirname(os.path.abspath(__file__))  # rodando como .py


class _Tee:
    """Espelha prints para arquivo de log (vale com --noconsole, sem janela)."""
    def __init__(self, caminho):
        self._f = open(caminho, "a", encoding="utf-8", errors="replace")
        self._orig = sys.__stdout__
    def write(self, s):
        try:
            self._f.write(s); self._f.flush()
        except Exception:
            pass
        if self._orig:
            try:
                self._orig.write(s); self._orig.flush()
            except Exception:
                pass
    def flush(self):
        try:
            self._f.flush()
        except Exception:
            pass


LOG_PATH = os.path.join(BASE, "poc_log.txt")
try:
    _tee = _Tee(LOG_PATH)
    sys.stdout = _tee
    sys.stderr = _tee
except Exception:
    pass

CONFIG_PATH = os.path.join(BASE, "config.xml")


def carregar_config():
    """Le config.xml (ao lado do exe). <banco caminho='...'>.
    Caminho relativo -> resolve na pasta do exe. Absoluto/UNC -> usa direto.
    Sem config ou erro -> padrao 'teste.db' na pasta do exe."""
    padrao = os.path.join(BASE, "teste.db")
    origem = "padrao (sem config.xml)"
    caminho = padrao
    if os.path.exists(CONFIG_PATH):
        try:
            root = ET.parse(CONFIG_PATH).getroot()
            el = root.find("banco")
            val = None
            if el is not None:
                val = el.get("caminho") or (el.text or "").strip() or None
            if val:
                caminho = val if os.path.isabs(val) else os.path.join(BASE, val)
                origem = f"config.xml ({val})"
            else:
                origem = "config.xml sem <banco caminho> -> padrao"
        except Exception as e:
            origem = f"config.xml invalido ({e!r}) -> padrao"
            caminho = padrao
    caminho = os.path.abspath(caminho)
    db_dir = os.path.dirname(caminho)
    erro_dir = ""
    try:
        os.makedirs(db_dir, exist_ok=True)
    except Exception as e:
        erro_dir = f"nao criou pasta {db_dir}: {e!r}"
    txt = os.path.join(db_dir, "registros.txt")
    return caminho, txt, origem, erro_dir


DB_PATH, TXT_PATH, CONFIG_SRC, CONFIG_ERR = carregar_config()
USUARIO = getpass.getuser()
MAQUINA = socket.gethostname()

# --- ciclo de vida: pagina fecha -> servidor encerra ---
SRV = None                 # instancia do servidor (preenchida no main)
_last_seen = time.time()   # ultimo heartbeat recebido
_armed = False             # watchdog so liga apos o 1o ping da pagina
_ocioso_seg = 15           # sem heartbeat por X seg -> encerra


def _encerrar(motivo: str):
    print(f"  [ENCERRANDO] {motivo}")
    if SRV is not None:
        threading.Thread(target=SRV.shutdown, daemon=True).start()


def _watchdog():
    while True:
        time.sleep(3)
        if _armed and (time.time() - _last_seen) > _ocioso_seg:
            _encerrar(f"pagina fechada (sem heartbeat ha >{_ocioso_seg}s)")
            return


def agora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_db():
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "CREATE TABLE IF NOT EXISTS registros ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "conteudo TEXT NOT NULL, "
        "criado_em TEXT NOT NULL, "
        "maquina TEXT NOT NULL, "
        "usuario TEXT NOT NULL)"
    )
    con.commit()
    con.close()


def gravar(conteudo: str) -> dict:
    ts = agora()
    con = sqlite3.connect(DB_PATH)
    cur = con.execute(
        "INSERT INTO registros (conteudo, criado_em, maquina, usuario) "
        "VALUES (?, ?, ?, ?)",
        (conteudo, ts, MAQUINA, USUARIO),
    )
    con.commit()
    novo_id = cur.lastrowid
    con.close()
    with open(TXT_PATH, "a", encoding="utf-8") as f:
        f.write(f"{ts} | {MAQUINA} | {USUARIO} | #{novo_id} | {conteudo}\n")
    return {"id": novo_id, "criado_em": ts}


def listar() -> list:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT id, conteudo, criado_em, maquina, usuario "
        "FROM registros ORDER BY id DESC LIMIT 50"
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def teste_escrita() -> str:
    try:
        p = os.path.join(os.path.dirname(DB_PATH), ".escrita_ok.tmp")
        with open(p, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(p)
        return "OK (pasta gravável)"
    except Exception as e:
        return f"FALHOU: {e!r}"


HTML = '''<!DOCTYPE html>
<html lang='pt-BR'>
<head>
<meta charset='UTF-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>POC Quarentena — Teste de Gravação</title>
<style>
  * { box-sizing: border-box; font-family: 'Segoe UI', Arial, sans-serif; }
  body { margin: 0; background: #F2F4F7; color: #1F2D5C; }
  header { background: #1F2D5C; color: #fff; padding: 16px 28px; border-bottom: 4px solid #F5B800; }
  header h1 { margin: 0; font-size: 18px; }
  header small { color: #C9D2E3; }
  .wrap { max-width: 880px; margin: 22px auto; padding: 0 18px; }
  .card { background: #fff; border: 1px solid #E2E8F0; border-radius: 8px; padding: 18px 20px; margin-bottom: 18px; box-shadow: 0 1px 3px rgba(31,45,92,.08); }
  .card h2 { margin: 0 0 12px; font-size: 14px; text-transform: uppercase; letter-spacing: .5px; color: #1F2D5C; }
  .diag { display: grid; grid-template-columns: 150px 1fr; gap: 6px 14px; font-size: 13px; }
  .diag b { color: #555; font-weight: 600; }
  .ok { color: #1E8449; font-weight: 700; }
  .bad { color: #C0392B; font-weight: 700; }
  .row { display: flex; gap: 10px; }
  input[type=text] { flex: 1; padding: 11px 12px; font-size: 15px; border: 1px solid #B8C2D0; border-radius: 6px; }
  input[type=text]:focus { outline: 2px solid #F5B800; border-color: #F5B800; }
  button { background: #1F2D5C; color: #fff; border: 0; padding: 11px 22px; font-size: 15px; font-weight: 700; border-radius: 6px; cursor: pointer; }
  button:hover { background: #2c3f7e; }
  button:disabled { background: #9AA0A6; cursor: not-allowed; }
  #msg { margin-top: 10px; font-size: 14px; min-height: 20px; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 6px; }
  th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid #EDF1F6; }
  th { background: #F5B800; color: #1F2D5C; }
  tr:nth-child(even) td { background: #FAFBFD; }
  .empty { color: #888; padding: 14px 0; font-style: italic; }
</style>
</head>
<body>
<header>
  <h1>POC Quarentena — Teste de Gravação no Banco</h1>
  <small>Servidor Python local · SQLite · prova via git (teste.db + registros.txt)</small>
</header>
<div class='wrap'>

  <div class='card'>
    <h2>Diagnóstico do ambiente</h2>
    <div class='diag' id='diag'>carregando…</div>
  </div>

  <div class='card'>
    <h2>Enviar texto para o banco</h2>
    <div class='row'>
      <input type='text' id='txt' placeholder='Digite qualquer texto e clique Enviar' autocomplete='off'>
      <button id='btn'>Enviar</button>
    </div>
    <div id='msg'></div>
  </div>

  <div class='card'>
    <h2>Registros gravados (SQLite)</h2>
    <table>
      <thead><tr><th>#</th><th>Conteúdo</th><th>Criado em</th><th>Máquina</th><th>Usuário</th></tr></thead>
      <tbody id='tb'><tr><td colspan='5' class='empty'>—</td></tr></tbody>
    </table>
  </div>

</div>
<script>
const $ = s => document.querySelector(s);

function pinta(d) {
  const esc = d.escrita.startsWith('OK') ? 'ok' : 'bad';
  $('#diag').innerHTML =
    "<b>Banco SQLite</b><span>" + d.db_path + "</span>" +
    "<b>Texto prova</b><span>" + d.txt_path + "</span>" +
    "<b>Origem config</b><span>" + d.origem_config + "</span>" +
    "<b>Permissao escrita</b><span class='" + esc + "'>" + d.escrita + "</span>" +
    "<b>Maquina</b><span>" + d.maquina + "</span>" +
    "<b>Usuario</b><span>" + d.usuario + "</span>" +
    "<b>Hora servidor</b><span>" + d.hora_servidor + "</span>";
  const tb = $('#tb');
  if (!d.registros.length) { tb.innerHTML = "<tr><td colspan='5' class='empty'>Nenhum registro ainda.</td></tr>"; return; }
  tb.innerHTML = d.registros.map(r =>
    "<tr><td>" + r.id + "</td><td>" + r.conteudo + "</td><td>" + r.criado_em +
    "</td><td>" + r.maquina + "</td><td>" + r.usuario + "</td></tr>").join('');
}

async function carregar() {
  try {
    const r = await fetch('/api/registros');
    pinta(await r.json());
  } catch (e) {
    $('#diag').innerHTML = "<span class='bad'>Servidor nao respondeu: " + e + "</span>";
  }
}

async function enviar() {
  const v = $('#txt').value.trim();
  if (!v) { $('#msg').innerHTML = "<span class='bad'>Digite algo antes de enviar.</span>"; return; }
  $('#btn').disabled = true;
  $('#msg').textContent = 'Enviando...';
  try {
    const r = await fetch('/api/enviar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ texto: v })
    });
    const j = await r.json();
    if (j.ok) {
      $('#msg').innerHTML = "<span class='ok'>Gravado no banco: registro #" + j.gravado.id + " (" + j.gravado.criado_em + ")</span>";
      $('#txt').value = '';
      pinta(await (await fetch('/api/registros')).json());
    } else {
      $('#msg').innerHTML = "<span class='bad'>Erro: " + (j.erro || '?') + "</span>";
    }
  } catch (e) {
    $('#msg').innerHTML = "<span class='bad'>Falha de conexao: " + e + "</span>";
  } finally {
    $('#btn').disabled = false;
  }
}

async function ping() { try { await fetch('/api/ping'); } catch (e) {} }
window.addEventListener('pagehide', () => {
  try { navigator.sendBeacon('/api/encerrar'); } catch (e) {}
});

$('#btn').addEventListener('click', enviar);
$('#txt').addEventListener('keydown', e => { if (e.key === 'Enter') enviar(); });
carregar();
ping();
setInterval(carregar, 8000);
setInterval(ping, 5000);
</script>
</body>
</html>'''


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        print("  [http] " + (fmt % args))

    def do_GET(self):
        global _last_seen, _armed
        if self.path in ("/", "/index.html"):
            self._send(200, HTML, "text/html; charset=utf-8")
        elif self.path == "/api/ping":
            _last_seen = time.time()
            _armed = True
            self._send(200, json.dumps({"ok": True}))
        elif self.path == "/api/encerrar":
            self._send(200, json.dumps({"ok": True}))
            _encerrar("pedido explicito da pagina (GET)")
        elif self.path == "/api/registros":
            self._send(200, json.dumps({
                "ok": True,
                "db_path": DB_PATH,
                "txt_path": TXT_PATH,
                "origem_config": CONFIG_SRC + (f" | {CONFIG_ERR}" if CONFIG_ERR else ""),
                "maquina": MAQUINA,
                "usuario": USUARIO,
                "escrita": teste_escrita(),
                "hora_servidor": agora(),
                "registros": listar(),
            }, ensure_ascii=False))
        else:
            self._send(404, json.dumps({"ok": False, "erro": "rota"}))

    def do_POST(self):
        if self.path == "/api/encerrar":          # navigator.sendBeacon (pagehide)
            self._send(200, json.dumps({"ok": True}))
            _encerrar("pagina fechada (sendBeacon)")
            return
        if self.path != "/api/enviar":
            self._send(404, json.dumps({"ok": False, "erro": "rota"}))
            return
        try:
            n = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            texto = (payload.get("texto") or "").strip()
            if not texto:
                self._send(400, json.dumps({"ok": False, "erro": "texto vazio"}))
                return
            res = gravar(texto)
            print(f"  [GRAVADO] #{res['id']} '{texto}' -> {DB_PATH}")
            self._send(200, json.dumps({
                "ok": True, "gravado": res, "registros": listar()
            }, ensure_ascii=False))
        except Exception as e:
            print(f"  [ERRO] {e!r}")
            self._send(500, json.dumps({"ok": False, "erro": repr(e)}))


def banner():
    print("=" * 64)
    print(" POC QUARENTENA — servidor de teste")
    print("=" * 64)
    print(f"  Pasta base   : {BASE}")
    print(f"  Config       : {CONFIG_SRC}")
    if CONFIG_ERR:
        print(f"  [ALERTA dir] : {CONFIG_ERR}")
    print(f"  Banco SQLite : {DB_PATH}")
    print(f"  Texto prova  : {TXT_PATH}")
    print(f"  Maquina      : {MAQUINA}")
    print(f"  Usuario      : {USUARIO}")
    print(f"  Escrita      : {teste_escrita()}")
    print(f"  Endereco     : http://{HOST}:{PORT}/")
    print("=" * 64)


def main():
    if len(sys.argv) > 1 and sys.argv[1].lower() == "selftest":
        banner()
        init_db()
        r = gravar("[SELFTEST] gerado automaticamente")
        print(f"  SELFTEST OK -> registro #{r['id']} em {r['criado_em']}")
        print("  (db e registros.txt criados na pasta acima)")
        return 0

    banner()
    init_db()
    try:
        srv = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError as e:
        print(f"  [FALHA] nao consegui abrir {HOST}:{PORT} -> {e!r}")
        print("  (porta ocupada ou bloqueio de socket). Encerrando.")
        print(f"  Detalhes registrados em: {LOG_PATH}")
        try:
            if sys.stdin and sys.stdin.isatty():
                input("  Pressione ENTER para fechar...")
            else:
                time.sleep(8)
        except Exception:
            time.sleep(8)
        return 1

    global SRV
    SRV = srv
    threading.Thread(target=_watchdog, daemon=True).start()

    url = f"http://{HOST}:{PORT}/"
    print(f"  Servidor no ar. Abrindo {url} no navegador...")
    print(f"  Encerra sozinho ao FECHAR A PAGINA (ou {_ocioso_seg}s sem ela).")
    print("  Tambem pode: fechar esta janela ou Ctrl+C.")
    if os.environ.get("POC_NOBROWSER") != "1":
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    else:
        print("  [POC_NOBROWSER] nao abrindo navegador (modo teste)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  Encerrado pelo usuario.")
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
