# -*- coding: utf-8 -*-
"""Principal: entry point clicado pelo usuario para visualizador.exe ou
Processador.exe. Um exe FINO no top level de EXECUTAVEIS\\.

Fluxo:
  1. Identifica o alvo (visualizador ou processador) pelo proprio nome.
  2. Le <versao> local vs rede. Se houver diferenca:
     a. Pre-atualiza launcher_atualizador.exe (sai do paradoxo "atualizador
        nao consegue atualizar ele mesmo").
     b. Roda launcher_atualizador.exe --alvo <alvo> (BLOQUEANTE), que mostra
        splash HTML, copia o resto da rede e sai.
  3. Spawn launcher\\launcher_<alvo>.exe DETACHED.
  4. Sai imediatamente — o core e' quem sustenta a sessao.

Nenhuma lógica de servidor HTTP, nenhum self-update, nenhum import pesado.
Mantem o principal pequeno e estavel — raramente precisa mudar.
"""
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def _texto(caminho: Path, tag: str) -> str:
    try:
        return (ET.parse(caminho).getroot().findtext(tag) or "").strip()
    except Exception:
        return ""


def _alvo_pelo_nome() -> str:
    """Determina o alvo (visualizador|processador) pelo nome do proprio exe."""
    nome = Path(sys.executable if getattr(sys, "frozen", False)
                else __file__).stem.lower()
    if "visual" in nome:
        return "visualizador"
    if "process" in nome:
        return "processador"
    return ""


def _base() -> Path:
    """Pasta de execucao = EXECUTAVEIS\\."""
    return Path(sys.executable if getattr(sys, "frozen", False)
                else __file__).resolve().parent


def _flags_detached() -> int:
    if sys.platform != "win32":
        return 0
    DETACHED_PROCESS = 0x00000008
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    return DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP


def main() -> int:
    alvo = _alvo_pelo_nome()
    if not alvo:
        print(f"[principal] nao consegui detectar alvo a partir de "
              f"{sys.executable}")
        return 1

    base = _base()
    cfg_local = base / "CONFIG" / "config.xml"
    if not cfg_local.exists():
        print(f"[principal] config.xml local ausente: {cfg_local}")
        return 1

    launcher_dir = base / "launcher"
    atualizador_local = launcher_dir / "launcher_atualizador.exe"
    core_local = launcher_dir / f"launcher_{alvo}.exe"

    houve_update = False
    rede_raiz = _texto(cfg_local, "rede/raiz")
    if rede_raiz:
        rede_exec_sub = _texto(cfg_local, "rede/executaveis") or "EXECUTAVEIS"
        rede_exec = Path(rede_raiz) / rede_exec_sub
        cfg_rede = rede_exec / "CONFIG" / "config.xml"
        if cfg_rede.exists():
            v_local = _texto(cfg_local, "versao")
            v_rede = _texto(cfg_rede, "versao")
            if v_rede and v_local != v_rede:
                # Pre-atualiza o atualizador (ele mesmo pode ter mudado).
                # Como nao esta rodando aqui, podemos sobrescrever direto.
                try:
                    src_atualizador = rede_exec / "launcher" / "launcher_atualizador.exe"
                    if src_atualizador.exists():
                        atualizador_local.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src_atualizador, atualizador_local)
                except Exception as e:
                    print(f"[principal] aviso ao pre-atualizar atualizador: {e!r}")

                # Roda o atualizador (BLOCKING)
                if atualizador_local.exists():
                    try:
                        subprocess.run([str(atualizador_local),
                                        "--alvo", alvo],
                                       cwd=str(launcher_dir))
                        houve_update = True   # splash exibido: a aba dele vira o painel
                    except Exception as e:
                        print(f"[principal] falha ao rodar atualizador: {e!r}")
                else:
                    print(f"[principal] launcher_atualizador.exe ausente em "
                          f"{atualizador_local}")

    # Spawn o core (visualizador ou processador), DETACHED
    if not core_local.exists():
        print(f"[principal] core ausente: {core_local}")
        return 1
    # Apos atualizacao, o splash do atualizador ja redireciona a PROPRIA aba
    # para o painel (8800). Entao o visualizador NAO deve abrir uma 2a aba —
    # senao o usuario fica com o painel DUPLICADO. Em abertura normal (sem
    # update), o core abre o navegador como sempre.
    env = os.environ.copy()
    if houve_update and alvo == "visualizador":
        env["VISUALIZADOR_NOBROWSER"] = "1"
    try:
        subprocess.Popen([str(core_local)], cwd=str(launcher_dir),
                         creationflags=_flags_detached(), close_fds=True,
                         env=env)
    except Exception as e:
        print(f"[principal] falha ao spawnar core: {e!r}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
