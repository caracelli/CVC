"""
Gera o visualizador.exe na pasta CVC_IAM_ANALYTICS/MOCKUP/

O exe e onefile, sem janela de terminal (stdlib apenas — sem dependencias).
Deve ficar ao lado de index.html, config.xml e chart.umd.min.js: o servidor
resolve esses arquivos a partir da pasta do proprio exe.

Uso:
    cd deploy
    python build_mockup.py
"""
import subprocess
import sys
from pathlib import Path


def garantir_pyinstaller():
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("[INFO] PyInstaller nao encontrado. Instalando...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller", "-q"])
        print("[OK] PyInstaller instalado.")


DEPLOY_DIR = Path(__file__).resolve().parent
RAIZ = DEPLOY_DIR.parent
MOCKUP = RAIZ / "CVC_IAM_ANALYTICS" / "MOCKUP"
BUILD = DEPLOY_DIR / "_build_mockup"
FONTE = MOCKUP / "mockup_server.py"


def main():
    print("=== Build visualizador IAM Analytics ===")

    if not FONTE.exists():
        print(f"FALHA - fonte nao encontrada: {FONTE}")
        sys.exit(1)

    BUILD.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--noconsole",
        "--name", "visualizador",
        "--distpath", str(MOCKUP),
        "--workpath", str(BUILD),
        "--specpath", str(BUILD),
        "--noconfirm",
        str(FONTE),
    ]

    print(f"Executando: {' '.join(cmd)}\n")
    resultado = subprocess.run(cmd, cwd=str(DEPLOY_DIR))

    if resultado.returncode == 0:
        exe = MOCKUP / "visualizador.exe"
        print(f"\nOK - Executavel gerado: {exe}")
    else:
        print("\nFALHA - Build falhou. Verifique os erros acima.")
        sys.exit(1)


if __name__ == "__main__":
    garantir_pyinstaller()
    main()
