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
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

_CREATE_NO_WINDOW = 0x08000000   # taskkill/tasklist sem piscar console


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


def _contar_instancias(img: str) -> int:
    """Quantas instancias do processo `img` existem AGORA (via tasklist).
    Retorna 0 se nenhuma, >0 se ha, -1 se nao deu pra verificar."""
    try:
        r = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {img}", "/NH"],
            capture_output=True, text=True, creationflags=_CREATE_NO_WINDOW)
    except Exception:
        return -1
    # com processos: cada linha contem o nome da imagem; sem: "INFO: No tasks..."
    return (r.stdout or "").lower().count(img.lower())


def _matar_processos_anteriores(alvo: str) -> None:
    """Garante que NAO sobre NENHUMA instancia do core (launcher_<alvo>.exe)
    antes de subir uma nova — evita visualizador duplicado (porta 8800 presa)
    ou processador travado/zumbi. Pode haver VARIOS processos abertos.

    Fluxo que de fato VERIFICA o resultado:
      1. conta instancias com `tasklist`;
      2. se 0 -> pronto (confirmado);
      3. se >0 -> `taskkill /F /T /IM` (mata TODAS as instancias do nome + filhos),
         espera o SO liberar e CONFERE de novo; repete ate zerar (ou avisar).

    Mata so o alvo sendo aberto: abrir o processador NAO derruba o visualizador
    (e vice-versa). Nao mata a si mesmo (o exe de topo tem outro nome)."""
    if sys.platform != "win32":
        return
    img = f"launcher_{alvo}.exe"
    for _ in range(8):
        n = _contar_instancias(img)
        if n == 0:
            return                      # VERIFICADO: zero instancias
        try:
            subprocess.run(["taskkill", "/F", "/T", "/IM", img],
                           capture_output=True, creationflags=_CREATE_NO_WINDOW)
        except Exception as e:
            print(f"[principal] aviso ao encerrar '{img}': {e!r}")
            return
        if n < 0:
            return                      # tasklist indisponivel: matou best-effort
        time.sleep(0.3)                 # da tempo do SO encerrar e liberar a porta
    # se chegou aqui, ainda havia algo apos 8 tentativas — registra
    if _contar_instancias(img) > 0:
        print(f"[principal] ATENCAO: ainda ha instancia(s) de '{img}' "
              f"apos varias tentativas de encerrar.")


def main() -> int:
    alvo = _alvo_pelo_nome()
    if not alvo:
        print(f"[principal] nao consegui detectar alvo a partir de "
              f"{sys.executable}")
        return 1

    # Antes de qualquer coisa: derruba instancias antigas do core deste alvo
    # (evita duplicata / porta presa / processo travado), como pedido.
    _matar_processos_anteriores(alvo)

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

    # Quando houve update, o ATUALIZADOR ja cuidou de subir o core:
    #   - visualizador: subiu logo apos copiar (NOBROWSER); o botao Fechar do
    #     atualizador navega a propria aba para o painel (8800).
    #   - processador: sobe no clique do Fechar (abre a propria janela de log).
    # Entao aqui NAO spawnamos nada — evita 2a aba / processo duplicado.
    if houve_update:
        return 0

    # Abertura normal (sem update): spawn do core, DETACHED, como sempre.
    if not core_local.exists():
        print(f"[principal] core ausente: {core_local}")
        return 1
    try:
        subprocess.Popen([str(core_local)], cwd=str(launcher_dir),
                         creationflags=_flags_detached(), close_fds=True)
    except Exception as e:
        print(f"[principal] falha ao spawnar core: {e!r}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
