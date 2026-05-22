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
import xml.etree.ElementTree as ET
from pathlib import Path

_IGNORAR = ("*.old", "*.log", "visualizador_log.txt", "__pycache__",
            "*.db", "*.db-shm", "*.db-wal")


def _texto(caminho: Path, tag: str) -> str:
    """Le um elemento de texto de um config.xml. '' se nao der para ler."""
    try:
        return (ET.parse(caminho).getroot().findtext(tag) or "").strip()
    except Exception:
        return ""


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
    # limpa .old de updates anteriores
    for antigo in exe_dir.glob("*.old"):
        try:
            antigo.unlink()
        except Exception:
            pass

    # o exe em execucao nao pode ser sobrescrito: renomeia para .old
    exe_old = exe.with_name(exe.name + ".old")
    try:
        exe.rename(exe_old)
    except Exception as e:
        log(f"[auto-update] nao foi possivel liberar o exe ({e!r}) - update abortado")
        return

    try:
        shutil.copytree(rede_exec, exe_dir, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns(*_IGNORAR))
    except Exception as e:
        log(f"[auto-update] falha ao copiar da rede ({e!r}) - restaurando")
        if not exe.exists():
            try:
                exe_old.rename(exe)
            except Exception:
                pass
        return

    if not exe.exists():
        log("[auto-update] exe novo ausente apos copia - restaurando")
        try:
            exe_old.rename(exe)
        except Exception:
            pass
        return

    log("[auto-update] concluido - reiniciando")
    try:
        subprocess.Popen([str(exe)] + sys.argv[1:], cwd=str(exe_dir))
    except Exception as e:
        log(f"[auto-update] falha ao reiniciar ({e!r})")
        return
    sys.exit(0)
