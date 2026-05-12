"""
Gera o Processador.exe na pasta CVC_IAM_ANALYTICS/EXECUTAVEIS/

Pré-requisito: pip install pyinstaller

Uso:
    cd deploy
    python build_processador.py
"""
import subprocess
import sys
from pathlib import Path

DEPLOY_DIR = Path(__file__).resolve().parent
RAIZ = DEPLOY_DIR.parent
DIST = RAIZ / "CVC_IAM_ANALYTICS" / "EXECUTAVEIS"
BUILD = DEPLOY_DIR / "_build"
SPEC = DEPLOY_DIR / "processador.spec"


def main():
    print("=== Build Processador IAM Analytics ===")

    DIST.mkdir(parents=True, exist_ok=True)
    BUILD.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--distpath", str(DIST),
        "--workpath", str(BUILD),
        "--noconfirm",
        str(SPEC),
    ]

    print(f"Executando: {' '.join(cmd)}\n")
    resultado = subprocess.run(cmd, cwd=str(DEPLOY_DIR))

    if resultado.returncode == 0:
        exe = DIST / "Processador.exe"
        print(f"\nOK - Executavel gerado: {exe}")
    else:
        print("\nFALHA - Build falhou. Verifique os erros acima.")
        sys.exit(1)


if __name__ == "__main__":
    main()
