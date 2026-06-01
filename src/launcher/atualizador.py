# -*- coding: utf-8 -*-
"""Atualizador: copia da rede para a instalacao local, com splash HTML.

Chamado pelo principal (visualizador.exe / Processador.exe) somente quando
<versao> local != rede. Recebe --alvo (visualizador|processador) — usado
apenas no texto do splash; a copia em si traz todos os arquivos relevantes.

NAO spawna o core — quem faz isso e' o principal apos esta execucao terminar.

Mora em: EXECUTAVEIS\\launcher\\launcher_atualizador.exe.
"""
import argparse
import shutil
import sys
import tempfile
import time
import webbrowser
import xml.etree.ElementTree as ET
from pathlib import Path


_SPLASH_HTML = """<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">
<title>IAM Analytics - Atualizando</title><style>
*{box-sizing:border-box}
body{font-family:-apple-system,"Segoe UI",Arial,sans-serif;
  background:linear-gradient(180deg,#f5f6fa 0%,#e7ebf2 100%);
  margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center}
.card{background:#fff;border-radius:14px;padding:44px 52px;
  box-shadow:0 8px 28px rgba(31,45,92,.12);text-align:center;max-width:480px}
.brand{color:#1F2D5C;font:700 11.5px Arial;letter-spacing:.1em;margin-bottom:6px}
h1{color:#1F2D5C;margin:0 0 6px;font:700 22px Arial}
.sub{color:#7B8085;font:400 13px Arial;margin:0}
.ver{color:#1F2D5C;font-weight:700}
.spinner{width:44px;height:44px;border:4px solid #E7EBF2;border-top-color:#1F2D5C;
  border-radius:50%;animation:spin .9s linear infinite;margin:28px auto 20px}
@keyframes spin{to{transform:rotate(360deg)}}
#status{color:#3A3F4C;font:600 14px Arial;margin:0 0 4px}
.small{color:#8A9099;font:400 11.5px Arial;margin-top:18px}
</style></head><body>
<div class="card">
<div class="brand">CVC IAM ANALYTICS</div>
<h1>Atualizando para nova versao</h1>
<p class="sub">Versao <span class="ver">__V_LOCAL__</span> -> <span class="ver">__V_REDE__</span></p>
<div class="spinner"></div>
<p id="status">Baixando da rede</p>
<p class="small">O painel abre automaticamente quando o processamento terminar
(no 1&ordm; uso pode levar alguns minutos).<br>
Se demorar muito, <a href="http://127.0.0.1:8800/" style="color:#1F2D5C;font-weight:600;text-decoration:underline">clique aqui</a>.</p>
</div>
<script>
const st=document.getElementById('status');
let baseSt='Baixando da rede';
let dn=0;
setInterval(()=>{dn=(dn%6)+1;st.textContent=baseSt+'.'.repeat(dn);},350);

// Estrategia 1: polla via <script src=...> — onload em alguns browsers
// nao dispara para cross-origin file:// -> http://localhost. Por isso o
// fallback abaixo.
// Polla o painel (8800) PACIENTEMENTE e so redireciona quando ele responde
// de fato (onload). No PRIMEIRO uso o visualizador roda o Processador antes
// de servir, o que pode levar alguns MINUTOS — por isso nada de fallback
// curto que jogue pra 8800 antes do painel existir (era a causa do
// "pagina nao encontrada").
let tentativas=0;
const MAX_TENT=1200;  // ~14 min a 700ms — paciencia pro 1o processamento
function tentar(){
  if(baseSt.indexOf('Aguardando')<0) baseSt='Aguardando o painel (1o uso pode levar minutos)';
  tentativas++;
  if(tentativas>MAX_TENT){
    window.location.replace('http://127.0.0.1:8800/');  // ultima tentativa
    return;
  }
  const s=document.createElement('script');
  s.onload=()=>window.location.replace('http://127.0.0.1:8800/');
  s.onerror=()=>{s.remove();setTimeout(tentar,700)};
  s.src='http://127.0.0.1:8800/chart.umd.min.js?_='+Date.now();
  document.head.appendChild(s);
}
setTimeout(tentar,4000);
</script></body></html>"""


def _texto(caminho: Path, tag: str) -> str:
    try:
        return (ET.parse(caminho).getroot().findtext(tag) or "").strip()
    except Exception:
        return ""


def _abrir_splash(v_local: str, v_rede: str) -> None:
    try:
        html = (_SPLASH_HTML.replace("__V_LOCAL__", v_local or "—")
                            .replace("__V_REDE__", v_rede or "—"))
        p = Path(tempfile.gettempdir()) / "cvc_iam_atualizando.html"
        p.write_text(html, encoding="utf-8")
        webbrowser.open("file:///" + str(p).replace("\\", "/"))
    except Exception as e:
        print(f"[atualizador] erro ao abrir splash: {e!r}")


def _retry_io(fn, tentativas: int = 5, delay: float = 0.4) -> bool:
    """Retenta IO ate algumas vezes — AV/Defender pode segurar arquivos."""
    for i in range(tentativas):
        try:
            fn()
            return True
        except Exception:
            if i == tentativas - 1:
                return False
            time.sleep(delay)
    return False


def _aplicar(base_local: Path, rede_exec: Path) -> bool:
    """Copia da rede para o local, exceto:
      - launcher_atualizador.exe — estamos rodando agora, o principal e' quem
        atualiza isso na proxima rodada (pre-update).
      - DADOS\\ — dados locais nunca vem da rede.
      - *.db, *.db-shm, *.db-wal — cache local independente.
      - *.old, *.log, __pycache__ — residuais."""
    def _ignore(diretorio, nomes):
        proibidos = set()
        for n in nomes:
            base_n = n.lower()
            if n == "DADOS":
                proibidos.add(n)
                continue
            if base_n.endswith(".old") or base_n.endswith(".log"):
                proibidos.add(n)
            elif n == "__pycache__":
                proibidos.add(n)
            elif base_n.endswith(".db") or base_n.endswith(".db-shm") or base_n.endswith(".db-wal"):
                proibidos.add(n)
            elif n == "launcher_atualizador.exe":
                proibidos.add(n)
        return proibidos

    def _copiar():
        shutil.copytree(str(rede_exec), str(base_local),
                        dirs_exist_ok=True, ignore=_ignore)
    return _retry_io(_copiar, tentativas=3, delay=0.5)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--alvo", default="visualizador",
                    choices=["visualizador", "processador"])
    args = ap.parse_args()

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

    print(f"[atualizador] atualizando {v_local} -> {v_rede} (alvo: {args.alvo})")
    _abrir_splash(v_local, v_rede)
    time.sleep(0.8)  # da tempo do browser pintar o splash

    if _aplicar(base, rede_exec):
        print(f"[atualizador] concluido: {v_local} -> {v_rede}")
        return 0
    print("[atualizador] falha na copia - abortado")
    return 1


if __name__ == "__main__":
    sys.exit(main())
