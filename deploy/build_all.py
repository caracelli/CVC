"""Build dos 5 exes do CVC IAM Analytics (v2.0.0+).

Layout final em CVC_IAM_ANALYTICS/EXECUTAVEIS/:
  visualizador.exe                    <- principal (top, clicavel)
  Processador.exe                     <- principal (top, clicavel)
  launcher/
    launcher_atualizador.exe          <- engine de update + splash HTML
    launcher_visualizador.exe         <- painel real
    launcher_processador.exe          <- motor real

Os principais sao pequenos (~10 MB cada), os launchers (visualizador/processador)
e' onde a logica de negocio vive.

Uso:
    cd deploy
    python build_all.py
"""
import subprocess
import shutil
import sys
from pathlib import Path

DEPLOY_DIR = Path(__file__).resolve().parent
RAIZ = DEPLOY_DIR.parent
EXECS = RAIZ / "CVC_IAM_ANALYTICS" / "EXECUTAVEIS"
LAUNCHER_DIR = EXECS / "launcher"


def garantir_pyinstaller():
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("[INFO] PyInstaller nao encontrado. Instalando...")
        subprocess.check_call([sys.executable, "-m", "pip", "install",
                               "pyinstaller", "-q"])


def _build(spec: str, destino: Path, work_subdir: str):
    work = DEPLOY_DIR / "_build" / work_subdir
    work.mkdir(parents=True, exist_ok=True)
    destino.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--distpath", str(destino),
        "--workpath", str(work),
        "--noconfirm",
        str(DEPLOY_DIR / spec),
    ]
    print(f"\n=== {spec} -> {destino} ===")
    rc = subprocess.run(cmd, cwd=str(DEPLOY_DIR)).returncode
    if rc != 0:
        print(f"FALHA no build de {spec}")
        sys.exit(1)


def main():
    garantir_pyinstaller()

    # 1-2. Principais (top level EXECUTAVEIS/)
    _build("principal_visualizador.spec", EXECS, "principal_v")
    _build("principal_processador.spec", EXECS, "principal_p")

    # 3-5. Launchers (subpasta EXECUTAVEIS/launcher/)
    _build("launcher_atualizador.spec", LAUNCHER_DIR, "atualizador")
    _build("launcher_visualizador.spec", LAUNCHER_DIR, "viz_core")
    _build("processador.spec", LAUNCHER_DIR, "proc_core")

    print("\n=== Resumo ===")
    for p in sorted(EXECS.iterdir()):
        if p.is_file() and p.suffix == ".exe":
            print(f"  {p.relative_to(RAIZ)}  ({p.stat().st_size/1024/1024:.1f} MB)")
    for p in sorted(LAUNCHER_DIR.iterdir()):
        if p.is_file() and p.suffix == ".exe":
            print(f"  {p.relative_to(RAIZ)}  ({p.stat().st_size/1024/1024:.1f} MB)")


if __name__ == "__main__":
    main()
