# -*- coding: utf-8 -*-
"""Auto-atualizacao dos executaveis (versao local x rede).

Ao iniciar a partir de uma COPIA LOCAL, compara a <versao> do config.xml local
com a do config.xml na rede (<rede><base>\\EXECUTAVEIS\\CONFIG\\config.xml).
Se diferirem, copia a pasta EXECUTAVEIS da rede por cima da local e re-executa
o proprio exe.

- Modo desenvolvimento (script .py, nao congelado): no-op.
- Rede indisponivel: apenas avisa e segue. O bloqueio "rede fora = nao roda"
  e' aplicado junto da base de dados na rede, em fase posterior.
"""
import os
import shutil
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

_IGNORAR = ("*.old", "*.log", "visualizador_log.txt", "__pycache__",
            "*.db", "*.db-shm", "*.db-wal")


def _texto(caminho: Path, tag: str) -> str:
    """Le um elemento de texto de um config.xml. '' se nao der para ler."""
    try:
        return (ET.parse(caminho).getroot().findtext(tag) or "").strip()
    except Exception:
        return ""


def _retry_io(fn, tentativas: int = 5, delay: float = 0.4) -> bool:
    """Retenta uma operacao de IO algumas vezes — antivirus/Defender pode segurar
    arquivos por alguns ms apos copia/extracao. Devolve True se OK."""
    for i in range(tentativas):
        try:
            fn()
            return True
        except Exception:
            if i == tentativas - 1:
                return False
            time.sleep(delay)
    return False


def _limpar_old(diretorio: Path, log, silencioso: bool = False) -> None:
    """Remove .old residuais de updates anteriores. Roda sempre, mesmo sem
    update pendente. Tentativa rapida — use _agendar_limpeza_old() pra
    retentar em background apos o startup."""
    try:
        for antigo in diretorio.glob("*.old"):
            if _retry_io(antigo.unlink, tentativas=3, delay=0.3):
                if not silencioso:
                    log(f"[auto-update] removido .old anterior: {antigo.name}")
    except Exception:
        pass


def _agendar_limpeza_old(diretorio: Path, log, duracao_s: int = 60) -> None:
    """Retenta a remocao de .old por ate `duracao_s` em background."""
    def _worker():
        fim = time.time() + duracao_s
        while time.time() < fim:
            time.sleep(2.0)
            try:
                remanescentes = list(diretorio.glob("*.old"))
                if not remanescentes:
                    return
                for f in remanescentes:
                    try:
                        f.unlink()
                        log(f"[auto-update] removido .old (background): {f.name}")
                    except Exception:
                        pass
            except Exception:
                pass
    threading.Thread(target=_worker, daemon=True).start()


def verificar_atualizacao(log=print) -> None:
    """Checa versao local x rede; se diferir, atualiza e re-executa o exe."""
    if not getattr(sys, "frozen", False):
        return  # dev: sem exe para atualizar

    exe = Path(sys.executable)
    exe_dir = exe.parent                           # ...\EXECUTAVEIS
    cfg_local = exe_dir / "CONFIG" / "config.xml"
    if not cfg_local.exists():
        log(f"[auto-update] config local ausente ({cfg_local}) - sem checar")
        return
    _limpar_old(exe_dir, log)              # tentativa rapida no startup
    _agendar_limpeza_old(exe_dir, log, 60) # background: ate 60s

    base = _texto(cfg_local, "rede/raiz")
    if not base:
        log("[auto-update] <rede><raiz> nao definido - sem checar")
        return

    sub = _texto(cfg_local, "rede/executaveis") or "EXECUTAVEIS"
    rede_exec = Path(base) / sub
    cfg_rede = rede_exec / "CONFIG" / "config.xml"
    if not cfg_rede.exists():
        log(f"[auto-update] rede indisponivel ({cfg_rede}) - seguindo sem atualizar")
        return

    v_local = _texto(cfg_local, "versao")
    v_rede = _texto(cfg_rede, "versao")
    if not v_rede or v_local == v_rede:
        log(f"[auto-update] em dia (versao {v_local})")
        return

    # rodando direto da pasta de rede? nao ha o que copiar
    if os.path.normcase(str(exe_dir)).startswith(os.path.normcase(str(rede_exec))):
        log("[auto-update] executando direto da rede - sem copia")
        return

    log(f"[auto-update] atualizando {v_local} -> {v_rede}")
    _aplicar(exe, exe_dir, rede_exec, log)


def _aplicar(exe: Path, exe_dir: Path, rede_exec: Path, log) -> None:
    _limpar_old(exe_dir, log, silencioso=True)

    # o exe em execucao nao pode ser sobrescrito: renomeia para .old com
    # timestamp pra nao conflitar com .old residual de update anterior.
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    exe_old = exe.with_name(exe.name + "." + stamp + ".old")
    if not _retry_io(lambda: exe.rename(exe_old), tentativas=6, delay=0.5):
        log("[auto-update] nao foi possivel liberar o exe (WinError 32?) - update abortado")
        return

    def _copiar():
        shutil.copytree(rede_exec, exe_dir, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns(*_IGNORAR))
    if not _retry_io(_copiar, tentativas=3, delay=0.5):
        log("[auto-update] falha ao copiar da rede - restaurando")
        if not exe.exists():
            _retry_io(lambda: exe_old.rename(exe), tentativas=3, delay=0.3)
        return

    if not exe.exists():
        log("[auto-update] exe novo ausente apos copia - restaurando")
        try:
            exe_old.rename(exe)
        except Exception:
            pass
        return

    log("[auto-update] concluido - reiniciando")
    # Pequena pausa pra file system assentar (AV/indexer pode estar segurando)
    import time
    time.sleep(0.5)
    try:
        # DETACHED_PROCESS: o novo exe nao herda handles do pai — evita o
        # "failed to delete temp" do bootloader PyInstaller ao sair.
        flags = 0
        if sys.platform == "win32":
            DETACHED_PROCESS = 0x00000008
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        subprocess.Popen([str(exe)] + sys.argv[1:], cwd=str(exe_dir),
                         creationflags=flags, close_fds=True)
    except Exception as e:
        log(f"[auto-update] falha ao reiniciar ({e!r})")
        return
    sys.exit(0)
