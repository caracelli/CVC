# -*- coding: utf-8 -*-
"""Atualizador: copia da rede para a instalacao local, com UI HTTP de progresso.

Chamado pelo principal (visualizador.exe / Processador.exe) somente quando
<versao> local != rede.

UX (substitui o antigo splash file:// que pollava o 8800 e as vezes "nao dava
em nada"):
  - FECHA (taskkill) os exes do app abertos ANTES de copiar, pra liberar os
    arquivos — era o que travava a copia quando a atualizacao partia do
    proprio Processador.exe (ele segurava o proprio .exe).
  - SERVE a propria pagina (HTTP local, porta ~8802) e mostra a LISTA de
    arquivos sendo copiados, marcando cada um quando termina, com barra de
    progresso.
  - Ao terminar a copia, habilita o botao "Fechar" (igual ao Processador).
    O usuario clica e SO entao segue pro destino — nada de auto-redirect.
  - O atualizador SOBE o core ele mesmo:
      * visualizador: sobe logo apos copiar (NOBROWSER) pra 8800 ficar pronto;
        o botao Fechar navega a aba pra http://127.0.0.1:8800/.
      * processador: sobe no clique do Fechar (o Processador abre a propria
        janela com log) e esta aba se fecha.
  - O principal, quando houve update, NAO sobe o core (o atualizador fez).

Copia da rede para o local, exceto:
  - launcher_atualizador.exe — estamos rodando agora; o principal e' quem
    atualiza isso na proxima rodada (pre-update).
  - DADOS\\ — dados locais nunca vem da rede.
  - *.db, *.db-shm, *.db-wal — cache local independente.
  - *.old, *.log, __pycache__ — residuais.

Mora em: EXECUTAVEIS\\launcher\\launcher_atualizador.exe.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

URL_PAINEL = "http://127.0.0.1:8800/"   # destino do visualizador
PORTA_BASE = 8802                        # 8800=painel, 8801=Processador
TIMEOUT_OCIOSO = 1800                    # 30 min: se o usuario nao clicar Fechar


_HTML_TEMPLATE = """<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">
<title>IAM Analytics - Atualizando</title><style>
*{box-sizing:border-box}
body{font-family:-apple-system,"Segoe UI",Arial,sans-serif;
  background:linear-gradient(180deg,#f5f6fa 0%,#e7ebf2 100%);
  margin:0;min-height:100vh;padding:30px 40px;display:flex;
  flex-direction:column;align-items:center}
.card{background:#fff;border-radius:14px;padding:26px 32px;
  box-shadow:0 8px 28px rgba(31,45,92,.12);width:min(720px,100%);
  display:flex;flex-direction:column;gap:14px}
.brand{color:#1F2D5C;font:700 11.5px Arial;letter-spacing:.1em}
h1{color:#1F2D5C;margin:0;font:700 22px Arial}
.row{display:flex;align-items:center;gap:12px;justify-content:space-between}
.ver{color:#7B8085;font:400 13px Arial;margin:2px 0 0}
.ver b{color:#1F2D5C;font-weight:700}
.status{display:flex;align-items:center;gap:10px;color:#3A3F4C;font:600 13px Arial}
.spinner{width:18px;height:18px;border:3px solid #E7EBF2;border-top-color:#1F2D5C;
  border-radius:50%;animation:spin .9s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.done .spinner{display:none}
.done .status{color:#2B7A2B}
.err .status{color:#B33A3A}
.bar{height:8px;background:#E7EBF2;border-radius:6px;overflow:hidden}
.bar>i{display:block;height:100%;width:0;background:#1F2D5C;
  border-radius:6px;transition:width .25s ease}
.done .bar>i{background:#2B7A2B}
.err .bar>i{background:#B33A3A}
.cont{color:#7B8085;font:600 11.5px Arial;text-align:right}
ul{list-style:none;margin:0;padding:12px 14px;background:#0F1320;border-radius:8px;
  height:46vh;overflow:auto;font:12.5px/1.7 "Consolas","Cascadia Code",monospace}
li{color:#9AA3B2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
li .nm{color:#D6DAE3}
li .sz{color:#6B7382}
li.ok::before{content:"\\2713 ";color:#5AA469;font-weight:700}
li.copiando::before{content:"\\21bb ";color:#E0A030}
li.erro::before{content:"\\2715 ";color:#E06A5A;font-weight:700}
li.erro .nm{color:#E06A5A}
.ft{display:flex;justify-content:flex-end;margin-top:2px}
button{border:none;border-radius:6px;padding:9px 18px;font:600 12px Arial;
  cursor:pointer;background:#1F2D5C;color:#fff}
button:disabled{opacity:.4;cursor:not-allowed}
</style></head><body>
<div class="card" id="card">
<div class="row">
  <div>
    <div class="brand">CVC · IAM ANALYTICS</div>
    <h1>Atualizando</h1>
    <p class="ver">Versão <b>__V_LOCAL__</b> &rarr; <b>__V_REDE__</b></p>
  </div>
  <div class="status"><div class="spinner"></div><span id="status">Iniciando...</span></div>
</div>
<div class="bar"><i id="prog"></i></div>
<div class="cont" id="cont">0 / 0 arquivos</div>
<ul id="lista"></ul>
<div class="ft">
  <button id="btn" disabled onclick="fechar()">Fechar</button>
</div>
</div>
<script>
const ALVO = "__ALVO__";
const URL_PAINEL = "__URL_PAINEL__";
const stEl = document.getElementById('status');
const card = document.getElementById('card');
const prog = document.getElementById('prog');
const cont = document.getElementById('cont');
const lista = document.getElementById('lista');
const btn = document.getElementById('btn');

let baseSt = 'Iniciando';
let dotN = 0;
setInterval(() => {
  if (card.classList.contains('done') || card.classList.contains('err')) return;
  dotN = (dotN % 6) + 1;
  stEl.textContent = baseSt + '.'.repeat(dotN);
}, 350);

function fmt(b){
  if (b >= 1048576) return (b/1048576).toFixed(1)+' MB';
  if (b >= 1024) return (b/1024).toFixed(0)+' KB';
  return b+' B';
}

function render(d){
  // re-renderiza a lista (poucos arquivos)
  lista.innerHTML = '';
  (d.arquivos||[]).forEach(a=>{
    const li = document.createElement('li');
    li.className = a.status;
    li.innerHTML = '<span class="nm">'+a.nome+'</span>'+
                   (a.tam ? ' <span class="sz">('+fmt(a.tam)+')</span>' : '');
    lista.appendChild(li);
  });
  lista.scrollTop = lista.scrollHeight;
  const tot = d.total||0, fei = d.copiados||0;
  cont.textContent = fei + ' / ' + tot + ' arquivos';
  prog.style.width = (tot ? Math.round(fei*100/tot) : 0) + '%';
  if (d.status) baseSt = d.status.replace(/\\.+$/, '');
}

function tick(){
  fetch('/progresso').then(r=>r.json()).then(d=>{
    render(d);
    if (d.done){
      card.classList.add(d.erro ? 'err' : 'done');
      btn.disabled = false;
      prog.style.width = '100%';
      stEl.textContent = d.erro
        ? 'Concluído com erros — clique em Fechar'
        : (ALVO === 'processador'
            ? 'Atualizado. Clique em Fechar para abrir o Processador.'
            : 'Atualizado. Clique em Fechar para abrir o painel.');
      return;
    }
    setTimeout(tick, 400);
  }).catch(()=> setTimeout(tick, 1000));
}
tick();

window.addEventListener('beforeunload', () => {
  try { navigator.sendBeacon('/encerrar'); } catch(e) {}
});

function fechar(){
  fetch('/encerrar', {method:'POST'}).catch(()=>{});
  if (ALVO === 'visualizador'){
    window.location.replace(URL_PAINEL);   // 8800 ja esta no ar
    return;
  }
  // processador: o servidor sobe o Processador (abre a propria janela);
  // aqui so fechamos esta aba.
  try { window.close(); } catch(e) {}
  setTimeout(() => { window.location.replace('about:blank'); }, 150);
}
</script></body></html>"""


# ---------------------------------------------------------------- estado

class _Estado:
    """Progresso thread-safe da copia."""

    def __init__(self):
        self._lock = threading.Lock()
        self._arquivos = []          # [{nome, tam, status}]
        self._total = 0
        self._done = False
        self._erro = False
        self._status = "Iniciando..."

    def definir_total(self, n):
        with self._lock:
            self._total = n

    def status(self, s):
        with self._lock:
            self._status = s

    def iniciar_arquivo(self, nome, tam):
        with self._lock:
            self._arquivos.append({"nome": nome, "tam": tam, "status": "copiando"})

    def terminar_arquivo(self, ok):
        with self._lock:
            if self._arquivos:
                self._arquivos[-1]["status"] = "ok" if ok else "erro"

    def concluir(self, erro=False):
        with self._lock:
            self._done = True
            self._erro = erro
            self._status = "Concluido com erro" if erro else "Concluido"

    def snapshot(self):
        with self._lock:
            copiados = sum(1 for a in self._arquivos if a["status"] in ("ok", "erro"))
            return {
                "arquivos": list(self._arquivos),
                "total": self._total,
                "copiados": copiados,
                "done": self._done,
                "erro": self._erro,
                "status": self._status,
            }


_ESTADO = _Estado()
_ENCERRAR = threading.Event()
_SRV = None
_HTML = ""


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a, **k):
        pass

    def do_GET(self):
        try:
            if self.path == "/" or self.path.startswith("/?"):
                self._send(200, _HTML, "text/html; charset=utf-8")
            elif self.path.startswith("/progresso"):
                self._send(200, json.dumps(_ESTADO.snapshot(), ensure_ascii=False),
                           "application/json; charset=utf-8")
            elif self.path == "/encerrar":
                _ENCERRAR.set()
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
        if self.path == "/encerrar":
            _ENCERRAR.set()
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
        try:
            self.wfile.write(body)
        except Exception:
            pass


# ---------------------------------------------------------------- util

def _texto(caminho: Path, tag: str) -> str:
    try:
        return (ET.parse(caminho).getroot().findtext(tag) or "").strip()
    except Exception:
        return ""


def _retry_io(fn, tentativas: int = 3, delay: float = 0.5) -> bool:
    """Retenta IO algumas vezes — AV/Defender pode segurar arquivos."""
    for i in range(tentativas):
        try:
            fn()
            return True
        except Exception:
            if i == tentativas - 1:
                return False
            time.sleep(delay)
    return False


def _flags_detached() -> int:
    if sys.platform != "win32":
        return 0
    DETACHED_PROCESS = 0x00000008
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    return DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP


def _matar_apps() -> None:
    """taskkill nos exes do app ANTES de copiar, pra garantir que ninguem
    esteja segurando os arquivos (foi o que travava a copia do Processador.exe
    quando a atualizacao era iniciada por ele mesmo).

    Mata os principais (Processador.exe / visualizador.exe) e os cores
    (launcher_processador.exe / launcher_visualizador.exe). NUNCA o
    launcher_atualizador.exe — somos nos.

    SEM /T de proposito: /T mataria os processos-filho, e o atualizador e'
    filho do principal que nos chamou; com /T cometeriamos suicidio. Matar
    so por nome de imagem nao afeta o atualizador (nome diferente).

    Em dev (.py) nao ha exes com esses nomes — e' no-op inofensivo.
    """
    if sys.platform != "win32":
        return
    nomes = ["Processador.exe", "visualizador.exe",
             "launcher_processador.exe", "launcher_visualizador.exe"]
    CREATE_NO_WINDOW = 0x08000000
    for nome in nomes:
        try:
            subprocess.run(["taskkill", "/F", "/IM", nome],
                           capture_output=True, creationflags=CREATE_NO_WINDOW)
        except Exception:
            pass
    time.sleep(0.7)  # da tempo dos handles de arquivo liberarem


def _spawn_core(base: Path, alvo: str, nobrowser: bool) -> bool:
    core = base / "launcher" / f"launcher_{alvo}.exe"
    if not core.exists():
        print(f"[atualizador] core ausente: {core}")
        return False
    env = os.environ.copy()
    if alvo == "visualizador" and nobrowser:
        env["VISUALIZADOR_NOBROWSER"] = "1"
    try:
        subprocess.Popen([str(core)], cwd=str(core.parent),
                         creationflags=_flags_detached(), close_fds=True, env=env)
        return True
    except Exception as e:
        print(f"[atualizador] falha ao spawnar core: {e!r}")
        return False


def _deve_ignorar(nome: str) -> bool:
    n = nome.lower()
    if n.endswith((".old", ".log", ".db", ".db-shm", ".db-wal")):
        return True
    if nome == "launcher_atualizador.exe":
        return True
    return False


def _coletar(rede_exec: Path):
    """Lista (src, rel, tamanho) dos arquivos a copiar, aplicando os ignores."""
    itens = []
    for raiz, dirs, arqs in os.walk(rede_exec):
        dirs[:] = [d for d in dirs if d not in ("DADOS", "__pycache__")]
        for a in arqs:
            if _deve_ignorar(a):
                continue
            src = Path(raiz) / a
            rel = src.relative_to(rede_exec)
            try:
                tam = src.stat().st_size
            except OSError:
                tam = 0
            itens.append((src, rel, tam))
    return itens


def _rodar_copia(base: Path, rede_exec: Path, alvo: str) -> None:
    """Thread de copia: copia arquivo a arquivo reportando progresso e, ao
    final, sobe o core do visualizador (pra 8800 estar pronto no Fechar)."""
    try:
        _ESTADO.status("Fechando aplicativos abertos")
        _matar_apps()
        _ESTADO.status("Calculando arquivos")
        itens = _coletar(rede_exec)
        _ESTADO.definir_total(len(itens))
        _ESTADO.status(f"Copiando {len(itens)} arquivo(s)")
        houve_erro = False
        for src, rel, tam in itens:
            _ESTADO.iniciar_arquivo(str(rel).replace("\\", "/"), tam)
            dst = base / rel

            def _copiar(_src=src, _dst=dst):
                _dst.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.copy2(_src, _dst)
                except (PermissionError, OSError):
                    # _dst em uso — tipicamente o proprio Processador.exe /
                    # visualizador.exe (o principal) que disparou ESTA
                    # atualizacao e segue rodando enquanto copiamos. No Windows
                    # da pra RENOMEAR um exe em execucao: movemos o antigo pra
                    # .old e copiamos o novo no lugar. O processo atual continua
                    # do .old; o novo vale no proximo start. (Sem precisar matar
                    # o processo.)
                    if not _dst.exists():
                        raise
                    antigo = _dst.with_suffix(_dst.suffix + ".old")
                    try:
                        if antigo.exists():
                            antigo.unlink()
                    except OSError:
                        pass
                    os.replace(_dst, antigo)
                    shutil.copy2(_src, _dst)

            ok = _retry_io(_copiar)
            _ESTADO.terminar_arquivo(ok)
            if not ok:
                houve_erro = True
        # visualizador: ja sobe o painel (sem abrir aba) pra 8800 ficar pronto
        if alvo == "visualizador":
            _ESTADO.status("Iniciando painel")
            _spawn_core(base, "visualizador", nobrowser=True)
        _ESTADO.concluir(erro=houve_erro)
    except Exception as e:
        print(f"[atualizador] erro na copia: {e!r}")
        _ESTADO.concluir(erro=True)


def _subir_servidor() -> str:
    global _SRV
    for porta in range(PORTA_BASE, PORTA_BASE + 10):
        try:
            _SRV = ThreadingHTTPServer(("127.0.0.1", porta), _Handler)
            threading.Thread(target=_SRV.serve_forever, daemon=True).start()
            return f"http://127.0.0.1:{porta}/"
        except OSError:
            continue
    raise RuntimeError("nenhuma porta livre para a UI do atualizador")


def main() -> int:
    global _HTML
    ap = argparse.ArgumentParser()
    ap.add_argument("--alvo", default="visualizador",
                    choices=["visualizador", "processador"])
    args = ap.parse_args()
    alvo = args.alvo

    # Estamos em EXECUTAVEIS\launcher\; a "base" do app e' o pai.
    base_self = Path(sys.executable if getattr(sys, "frozen", False)
                     else __file__).resolve().parent
    base = base_self.parent if base_self.name == "launcher" else base_self
    cfg_local = base / "CONFIG" / "config.xml"

    if not cfg_local.exists():
        print(f"[atualizador] config local ausente: {cfg_local}")
        return 1

    rede_raiz = _texto(cfg_local, "rede/raiz")
    if not rede_raiz:
        print("[atualizador] <rede><raiz> vazia - sem atualizacao")
        return 0
    rede_exec = Path(rede_raiz) / (_texto(cfg_local, "rede/executaveis") or "EXECUTAVEIS")
    cfg_rede = rede_exec / "CONFIG" / "config.xml"
    if not cfg_rede.exists():
        print(f"[atualizador] rede indisponivel: {cfg_rede}")
        return 0

    v_local = _texto(cfg_local, "versao")
    v_rede = _texto(cfg_rede, "versao")
    if not v_rede or v_local == v_rede:
        print(f"[atualizador] em dia (versao {v_local})")
        return 0

    print(f"[atualizador] atualizando {v_local} -> {v_rede} (alvo: {alvo})")
    _HTML = (_HTML_TEMPLATE
             .replace("__V_LOCAL__", v_local or "—")
             .replace("__V_REDE__", v_rede or "—")
             .replace("__ALVO__", alvo)
             .replace("__URL_PAINEL__", URL_PAINEL))

    try:
        url = _subir_servidor()
    except Exception as e:
        print(f"[atualizador] {e!r} - copiando sem UI")
        _rodar_copia(base, rede_exec, alvo)
        if alvo == "processador":
            _spawn_core(base, "processador", nobrowser=False)
        return 0

    threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    threading.Thread(target=_rodar_copia, args=(base, rede_exec, alvo),
                     daemon=True).start()

    # Bloqueia ate o usuario clicar Fechar (ou timeout). Para o visualizador,
    # o core ja foi spawnado ao fim da copia; aqui so seguramos a aba viva.
    _ENCERRAR.wait(timeout=TIMEOUT_OCIOSO)

    # No Fechar do processador, e' aqui que abrimos o Processador (janela propria).
    if alvo == "processador":
        _spawn_core(base, "processador", nobrowser=False)

    if _SRV is not None:
        try:
            _SRV.shutdown()
            _SRV.server_close()
        except Exception:
            pass
    print(f"[atualizador] concluido: {v_local} -> {v_rede}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
