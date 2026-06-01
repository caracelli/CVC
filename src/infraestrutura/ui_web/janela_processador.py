# -*- coding: utf-8 -*-
"""Janela HTML do Processador.

Substitui o terminal do Processador.exe (que e' --noconsole no PyInstaller)
por uma aba do navegador com textarea de log em tempo real.

Como funciona:
  - `iniciar()` sobe um servidor HTTP local em 127.0.0.1:<porta>
    (porta livre proxima de 8801) e abre o navegador na pagina.
  - A pagina faz polling em /log a cada 500ms; cada linha gravada
    via `escrever()` aparece na textarea.
  - Quando o processador termina, `concluir()` faz a pagina mostrar
    "Concluido" e ativa o botao "Fechar".
  - O usuario clica "Fechar" (ou fecha a aba) -> JS chama /encerrar ->
    sinaliza o evento de encerramento -> `aguardar_e_encerrar` retorna
    -> processo do Processador termina.
  - Fluxo "chamado pelo visualizador" (chamado_por='visualizador'):
    mensagem deixa explicito que ao fechar abre o painel.

Nao tem dependencias alem da stdlib.
"""
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Texto que sera renderizado no HTML — substituido em iniciar() conforme contexto
_MSG_CONCLUIDO_PADRAO = "Concluído. Clique em Fechar para encerrar."
_MSG_CONCLUIDO_VISUALIZADOR = ("Concluído. Clique em Fechar (ou feche esta aba) "
                                "para abrir o painel.")

# Evento sinalizado quando o usuario clica em Fechar / fecha a aba.
# aguardar_e_encerrar() bloqueia ate ele ser setado.
_ENCERRAR_PEDIDO = threading.Event()

_HTML_TEMPLATE = """<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">
<title>Processador IAM Analytics</title><style>
*{box-sizing:border-box}
body{font-family:-apple-system,"Segoe UI",Arial,sans-serif;
  background:linear-gradient(180deg,#f5f6fa 0%,#e7ebf2 100%);
  margin:0;min-height:100vh;padding:30px 40px;display:flex;
  flex-direction:column;align-items:center}
.card{background:#fff;border-radius:14px;padding:28px 34px;
  box-shadow:0 8px 28px rgba(31,45,92,.12);width:min(960px,100%);
  display:flex;flex-direction:column;gap:14px}
.brand{color:#1F2D5C;font:700 11.5px Arial;letter-spacing:.1em}
h1{color:#1F2D5C;margin:0;font:700 22px Arial}
.row{display:flex;align-items:center;gap:12px;justify-content:space-between}
.status{display:flex;align-items:center;gap:10px;color:#3A3F4C;font:600 13px Arial}
.spinner{width:18px;height:18px;border:3px solid #E7EBF2;border-top-color:#1F2D5C;
  border-radius:50%;animation:spin .9s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.done .spinner{display:none}
.done .status{color:#2B7A2B}
.err .status{color:#B33A3A}
pre{margin:0;padding:14px 16px;background:#0F1320;color:#D6DAE3;
  font:12.5px/1.5 "Consolas","Cascadia Code",monospace;
  border-radius:8px;height:60vh;overflow:auto;white-space:pre-wrap;
  word-break:break-word}
.ft{display:flex;justify-content:flex-end;gap:8px;margin-top:4px}
button{border:none;border-radius:6px;padding:8px 16px;font:600 12px Arial;
  cursor:pointer;background:#E7EBF2;color:#3A3F4C}
button.primary{background:#1F2D5C;color:#fff}
button:disabled{opacity:.45;cursor:not-allowed}
</style></head><body>
<div class="card" id="card">
<div class="row">
  <div>
    <div class="brand">CVC · IAM ANALYTICS</div>
    <h1>Processador</h1>
  </div>
  <div class="status"><div class="spinner"></div><span id="status">Iniciando...</span></div>
</div>
<pre id="log"></pre>
<div class="ft">
  <button id="btn-fechar" class="primary" disabled onclick="fechar()">Fechar</button>
</div>
</div>
<script>
let cursor = 0;
const log = document.getElementById('log');
const stEl = document.getElementById('status');
const card = document.getElementById('card');
const btn = document.getElementById('btn-fechar');

// Mensagem de conclusao injetada pelo servidor (varia por contexto)
const MSG_CONCLUIDO = __MSG_CONCLUIDO__;
// True quando o Processador foi disparado pelo Visualizador
const VAI_ABRIR_PAINEL = __VAI_ABRIR_PAINEL__;
// URL do painel (so usada se VAI_ABRIR_PAINEL=true)
const URL_PAINEL = __URL_PAINEL__;

let baseStatus = 'Iniciando';
let dotN = 0;
setInterval(() => {
  if (card.classList.contains('done') || card.classList.contains('err')) return;
  dotN = (dotN % 6) + 1;
  stEl.textContent = baseStatus + '.'.repeat(dotN);
}, 350);

function tick(){
  fetch('/log?since=' + cursor).then(r=>r.json()).then(d=>{
    if (d.lines && d.lines.length){
      log.textContent += d.lines.join('\\n') + '\\n';
      log.scrollTop = log.scrollHeight;
      cursor = d.cursor;
    }
    if (d.status) baseStatus = d.status.replace(/\\.+$/, '');
    if (d.done){
      card.classList.add(d.erro ? 'err' : 'done');
      btn.disabled = false;
      stEl.textContent = d.erro ? baseStatus : MSG_CONCLUIDO;
      return;
    }
    setTimeout(tick, 500);
  }).catch(()=> setTimeout(tick, 1200));
}
tick();

// Aviso de "fechar a aba" — sinaliza o servidor antes de sair.
// Usa sendBeacon: enfileira a request mesmo quando a pagina ja esta
// descarregando. /encerrar e' idempotente.
window.addEventListener('beforeunload', () => {
  try { navigator.sendBeacon('/encerrar'); } catch(e) {}
});

function fechar(){
  // 1. Sinaliza o servidor para encerrar (libera o aguardar_e_encerrar)
  // 2. Se chamado pelo visualizador, ja navega pra URL do painel — o
  //    visualizador ja esta no ar quando isso acontece (NOBROWSER=0 abriu
  //    o navegador na hora em que o subprocess do Processador terminou,
  //    mas como esta janela continua aberta, sobrescrevemos a URL aqui).
  // 3. Senao, fecha a aba (window.close() so funciona em janelas abertas
  //    por JS; em aba normal o navegador bloqueia. Fallback: about:blank).
  fetch('/encerrar', {method: 'POST'}).catch(()=>{});
  if (VAI_ABRIR_PAINEL && URL_PAINEL) {
    window.location.replace(URL_PAINEL);
    return;
  }
  try { window.close(); } catch(e) {}
  setTimeout(() => { window.location.replace('about:blank'); }, 100);
}
</script></body></html>"""


def _renderizar_html(chamado_por: str, url_painel: str) -> str:
    vai_abrir_painel = (chamado_por == "visualizador" and bool(url_painel))
    msg = _MSG_CONCLUIDO_VISUALIZADOR if vai_abrir_painel else _MSG_CONCLUIDO_PADRAO
    return (_HTML_TEMPLATE
            .replace("__MSG_CONCLUIDO__", json.dumps(msg, ensure_ascii=False))
            .replace("__VAI_ABRIR_PAINEL__", "true" if vai_abrir_painel else "false")
            .replace("__URL_PAINEL__", json.dumps(url_painel or "")))


class _Estado:
    """Buffer thread-safe das linhas de log + estado da execucao."""

    def __init__(self):
        self._lock = threading.Lock()
        self._linhas = []
        self._done = False
        self._erro = False
        self._status = "Iniciando..."

    def escrever(self, texto: str):
        with self._lock:
            for linha in str(texto).rstrip("\n").split("\n"):
                self._linhas.append(linha)

    def status(self, s: str):
        with self._lock:
            self._status = s

    def concluir(self, erro: bool = False):
        with self._lock:
            self._done = True
            self._erro = erro
            self._status = "Concluído com erro" if erro else "Concluído"

    def snapshot(self, desde: int):
        with self._lock:
            return {
                "lines": list(self._linhas[desde:]),
                "cursor": len(self._linhas),
                "done": self._done,
                "erro": self._erro,
                "status": self._status,
            }


_ESTADO = _Estado()
_SRV = None
_HTML_RENDERIZADO = ""    # gerado em iniciar() com contexto correto


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a, **k):
        pass  # silencioso

    def do_GET(self):
        try:
            if self.path == "/" or self.path.startswith("/?"):
                self._send(200, _HTML_RENDERIZADO, "text/html; charset=utf-8")
            elif self.path.startswith("/log"):
                desde = 0
                if "?" in self.path:
                    for par in self.path.split("?", 1)[1].split("&"):
                        if par.startswith("since="):
                            try:
                                desde = int(par[6:])
                            except Exception:
                                pass
                payload = json.dumps(_ESTADO.snapshot(desde), ensure_ascii=False)
                self._send(200, payload, "application/json; charset=utf-8")
            elif self.path == "/encerrar":
                _ENCERRAR_PEDIDO.set()
                self._send(200, b'{"ok":true}', "application/json")
            elif self.path == "/favicon.ico":
                self._send(204, b"")
            else:
                self._send(404, b"")
        except Exception:
            try:
                self._send(500, b"")
            except Exception:
                pass

    def do_POST(self):
        # /encerrar tambem aceita POST (usado pelo botao Fechar + sendBeacon)
        if self.path == "/encerrar":
            _ENCERRAR_PEDIDO.set()
            self._send(200, b'{"ok":true}', "application/json")
        else:
            self._send(404, b"")

    def _send(self, status, body, ct="text/plain"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def iniciar(porta_inicial: int = 8801, abrir_navegador: bool = True,
            chamado_por: str = "", url_painel: str = "") -> str:
    """Sobe o servidor da UI e abre o navegador. Devolve a URL final.

    chamado_por: 'visualizador' altera a mensagem de conclusao para
        deixar claro que ao fechar a aba o painel sera aberto.
    url_painel: URL do visualizador (so usada quando chamado_por='visualizador');
        o botao Fechar redireciona a aba pra essa URL apos sinalizar /encerrar.
    """
    global _SRV, _HTML_RENDERIZADO
    _ENCERRAR_PEDIDO.clear()
    _HTML_RENDERIZADO = _renderizar_html(chamado_por, url_painel)
    porta = None
    for tentativa in range(porta_inicial, porta_inicial + 10):
        try:
            _SRV = ThreadingHTTPServer(("127.0.0.1", tentativa), _Handler)
            porta = tentativa
            break
        except OSError:
            continue
    if _SRV is None:
        raise RuntimeError(
            f"nenhuma porta livre em {porta_inicial}..{porta_inicial+9}")
    threading.Thread(target=_SRV.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{porta}/"
    if abrir_navegador:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    return url


def escrever(texto: str) -> None:
    """Adiciona linhas ao log (chamado pelo sink do loguru)."""
    _ESTADO.escrever(texto)


def status(s: str) -> None:
    """Atualiza o rotulo de status do topo da pagina."""
    _ESTADO.status(s)


def concluir(erro: bool = False) -> None:
    """Marca a execucao como terminada (libera o botao Fechar)."""
    _ESTADO.concluir(erro=erro)


def aguardar_e_encerrar(timeout_segundos: int = 3600) -> None:
    """Bloqueia ate o usuario sinalizar encerramento (clicar Fechar ou fechar
    a aba) OU ate o timeout. Depois desliga o servidor.

    Timeout default de 1h evita o processo virar zumbi se o navegador
    nao conseguir disparar o beacon (ex.: aba ja fechada quando concluir
    foi chamado).
    """
    _ENCERRAR_PEDIDO.wait(timeout=timeout_segundos)
    encerrar()


def encerrar() -> None:
    """Para o servidor HTTP (a aba do navegador fica com 'Concluido')."""
    global _SRV
    if _SRV is not None:
        try:
            _SRV.shutdown()
            _SRV.server_close()
        except Exception:
            pass
        _SRV = None
