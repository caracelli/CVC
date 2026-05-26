"""
Monta os dois pacotes de entrega em ENTREGA/:
  - Projeto CVC.zip      (visualizador + banco com cenario atual)
  - Processador CVC.zip  (motor + estrutura ENTRADA/DADOS vazia)

Ambos contem a pasta CVC_IAM_ANALYTICS espelhando a arquitetura v2.0+
(principal no top + 3 launchers em subpasta), com <rede><raiz> VAZIA —
funcionam em qualquer pasta onde forem extraidos.

Pre-requisito: rodar deploy/build_all.py antes (gera os 5 exes).

Uso:
    cd deploy
    python build_entrega.py
"""
import shutil
import sqlite3
import sys
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from pathlib import Path

DEPLOY_DIR = Path(__file__).resolve().parent
RAIZ = DEPLOY_DIR.parent
APP = RAIZ / "CVC_IAM_ANALYTICS"
EXECS = APP / "EXECUTAVEIS"
LAUNCHER_DIR = EXECS / "launcher"
ENTREGA = RAIZ / "ENTREGA"
STAGING = RAIZ / "_entrega_staging"

# Os 5 exes da nova arquitetura
PRINCIPAL_VISUALIZADOR = EXECS / "visualizador.exe"
PRINCIPAL_PROCESSADOR = EXECS / "Processador.exe"
LAUNCHER_ATUALIZADOR = LAUNCHER_DIR / "launcher_atualizador.exe"
LAUNCHER_VISUALIZADOR = LAUNCHER_DIR / "launcher_visualizador.exe"
LAUNCHER_PROCESSADOR = LAUNCHER_DIR / "launcher_processador.exe"

REPORT_DIR = EXECS / "REPORT"
CONFIG_SRC = EXECS / "CONFIG" / "config.xml"
LEIA_ME_EXECS = EXECS / "LEIA-ME.md"
BANCO_FONTE = APP / "DADOS" / "BANCO" / "iam_analytics.db"

ENTRADA_SUBDIRS = [
    "RH/ATIVOS", "RH/DESLIGADOS",
    "SISTEMAS/SIGOT", "SISTEMAS/SICA_RA", "SISTEMAS/SICA_ESFERA",
    "SISTEMAS/SYSTUR", "SISTEMAS/IC",
    "MATRIZES/ORGANIZACIONAL", "MATRIZES/PERFIS_SISTEMAS",
]
DADOS_SUBDIRS = [
    "BANCO", "PROCESSADOS", "ERROS", "LOGS",
    "SAIDAS/DIVERGENCIAS", "SAIDAS/DESLIGADOS",
    "SAIDAS/TRANSFERIDOS", "SAIDAS/AUDITORIA",
]


def checar_prerequisitos():
    faltando = [str(p) for p in [
        PRINCIPAL_VISUALIZADOR, PRINCIPAL_PROCESSADOR,
        LAUNCHER_ATUALIZADOR, LAUNCHER_VISUALIZADOR, LAUNCHER_PROCESSADOR,
        CONFIG_SRC, BANCO_FONTE, REPORT_DIR / "index.html",
    ] if not p.exists()]
    if faltando:
        print("FALHA — arquivos ausentes:")
        for f in faltando:
            print(f"  - {f}")
        print("\nRode 'python deploy/build_all.py' primeiro.")
        sys.exit(1)


def config_com_raiz_vazia(destino: Path):
    """Le o config.xml atual e grava no destino com <rede><raiz> vazia."""
    tree = ET.parse(CONFIG_SRC)
    root = tree.getroot()
    raiz_node = root.find("rede/raiz")
    if raiz_node is not None:
        raiz_node.text = None
    destino.parent.mkdir(parents=True, exist_ok=True)
    tree.write(destino, encoding="UTF-8", xml_declaration=True)


def copiar_banco_consistente(destino: Path):
    """Backup via SQLite API — copia consistente mesmo com WAL aberto."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(str(BANCO_FONTE))
    dst = sqlite3.connect(str(destino))
    with dst:
        src.backup(dst)
    dst.close()
    src.close()


def _montar_executaveis(execs_destino: Path, incluir_processador: bool,
                         incluir_visualizador: bool):
    """Monta EXECUTAVEIS/ com os exes solicitados + CONFIG + REPORT + launcher/."""
    execs_destino.mkdir(parents=True, exist_ok=True)
    (execs_destino / "launcher").mkdir(parents=True, exist_ok=True)

    # Top level principais
    if incluir_visualizador:
        shutil.copy2(PRINCIPAL_VISUALIZADOR, execs_destino / "visualizador.exe")
    if incluir_processador:
        shutil.copy2(PRINCIPAL_PROCESSADOR, execs_destino / "Processador.exe")
    shutil.copy2(LEIA_ME_EXECS, execs_destino / "LEIA-ME.md")
    shutil.copytree(REPORT_DIR, execs_destino / "REPORT", dirs_exist_ok=True)
    config_com_raiz_vazia(execs_destino / "CONFIG" / "config.xml")

    # Launchers em subpasta — sempre inclui o atualizador
    shutil.copy2(LAUNCHER_ATUALIZADOR,
                 execs_destino / "launcher" / "launcher_atualizador.exe")
    if incluir_visualizador:
        shutil.copy2(LAUNCHER_VISUALIZADOR,
                     execs_destino / "launcher" / "launcher_visualizador.exe")
    if incluir_processador:
        shutil.copy2(LAUNCHER_PROCESSADOR,
                     execs_destino / "launcher" / "launcher_processador.exe")


def montar_projeto_cvc(base: Path):
    """Visualizador + banco (com cenario atual). Para o cliente VER o painel."""
    raiz = base / "CVC_IAM_ANALYTICS"
    _montar_executaveis(raiz / "EXECUTAVEIS",
                        incluir_processador=False, incluir_visualizador=True)
    copiar_banco_consistente(raiz / "DADOS" / "BANCO" / "iam_analytics.db")
    (raiz / "INTERACOES").mkdir(parents=True, exist_ok=True)
    (base / "LEIA-ME.txt").write_text(LEIA_ME_PROJETO, encoding="utf-8")


def montar_processador_cvc(base: Path):
    """Motor + ENTRADA/DADOS vazios. Para o cliente RODAR o engine."""
    raiz = base / "CVC_IAM_ANALYTICS"
    _montar_executaveis(raiz / "EXECUTAVEIS",
                        incluir_processador=True, incluir_visualizador=False)
    for sub in ENTRADA_SUBDIRS:
        (raiz / "ENTRADA" / sub).mkdir(parents=True, exist_ok=True)
    for sub in DADOS_SUBDIRS:
        (raiz / "DADOS" / sub).mkdir(parents=True, exist_ok=True)
    (raiz / "INTERACOES").mkdir(parents=True, exist_ok=True)
    (base / "LEIA-ME.txt").write_text(LEIA_ME_PROCESSADOR, encoding="utf-8")


LEIA_ME_PROJETO = """\
Projeto CVC — Visualizador IAM Analytics
==========================================

Pacote de demonstracao do painel IAM Analytics. Ja vem com o banco
preparado (cenario atual): basta extrair e abrir o visualizador.

Como usar
---------
1. Extraia este zip onde quiser (ex.: Documentos\\Projeto CVC).
2. Entre na pasta CVC_IAM_ANALYTICS\\EXECUTAVEIS.
3. Execute visualizador.exe — o navegador abre em
   http://127.0.0.1:8800/ com o painel.
4. Para encerrar, basta fechar a aba do navegador.

Estrutura
---------
CVC_IAM_ANALYTICS\\
  EXECUTAVEIS\\
    visualizador.exe       <- entry point (clique aqui)
    CONFIG\\config.xml      <- configuracao (raiz vazia = pasta local)
    REPORT\\index.html      <- pagina do painel
    LEIA-ME.md             <- detalhes tecnicos
    launcher\\
      launcher_atualizador.exe   <- engine de update (so usado se houver rede)
      launcher_visualizador.exe  <- painel real (HTTP server em 8800)
  DADOS\\BANCO\\
    iam_analytics.db       <- banco com o cenario atual

Observacoes
-----------
- O config.xml vem com <raiz> vazia: nao precisa de drive de rede.
- O painel mora em launcher\\launcher_visualizador.exe; visualizador.exe
  no top level e' so o orquestrador que verifica update e dispara o painel.
"""

LEIA_ME_PROCESSADOR = """\
Processador CVC — Motor IAM Analytics
=======================================

Pacote do motor de processamento. Le os arquivos depositados em
ENTRADA, cruza com as matrizes e gera o banco iam_analytics.db.

Como usar
---------
1. Extraia este zip onde quiser (ex.: Documentos\\Processador CVC).
2. Deposite os arquivos do cliente nas pastas correspondentes em
   CVC_IAM_ANALYTICS\\ENTRADA\\ (RH, MATRIZES, SISTEMAS).
3. Execute CVC_IAM_ANALYTICS\\EXECUTAVEIS\\Processador.exe.
4. O banco gerado fica em CVC_IAM_ANALYTICS\\DADOS\\BANCO\\iam_analytics.db
   (saidas Excel em DADOS\\SAIDAS).

Estrutura
---------
CVC_IAM_ANALYTICS\\
  EXECUTAVEIS\\
    Processador.exe        <- entry point (clique aqui)
    CONFIG\\config.xml      <- configuracao (raiz vazia)
    LEIA-ME.md
    launcher\\
      launcher_atualizador.exe   <- engine de update
      launcher_processador.exe   <- motor real (com pandas/openpyxl)
  ENTRADA\\, DADOS\\, INTERACOES\\
"""


def zipar(base: Path, alvo_zip: Path):
    """Compacta `base` em `alvo_zip` mantendo a pasta-raiz `base.name/`."""
    alvo_zip.parent.mkdir(parents=True, exist_ok=True)
    if alvo_zip.exists():
        alvo_zip.unlink()
    with zipfile.ZipFile(alvo_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for p in base.rglob("*"):
            if p.is_file():
                arcname = base.name + "/" + str(p.relative_to(base)).replace("\\", "/")
                zf.write(p, arcname)
            elif p.is_dir() and not any(p.iterdir()):
                arcname = base.name + "/" + str(p.relative_to(base)).replace("\\", "/") + "/"
                zf.writestr(zipfile.ZipInfo(arcname), "")


def main():
    print("=== Build dos pacotes de ENTREGA (v2.0+) ===")
    checar_prerequisitos()

    if STAGING.exists():
        shutil.rmtree(STAGING)
    STAGING.mkdir(parents=True, exist_ok=True)
    ENTREGA.mkdir(parents=True, exist_ok=True)
    inicio = datetime.now()

    print("\n[1/2] Projeto CVC (visualizador + banco)")
    base_p = STAGING / "Projeto CVC"
    base_p.mkdir()
    montar_projeto_cvc(base_p)
    zip_p = ENTREGA / "Projeto CVC.zip"
    zipar(base_p, zip_p)
    print(f"  OK -> {zip_p}  ({zip_p.stat().st_size/1024/1024:.1f} MB)")

    print("\n[2/2] Processador CVC (motor)")
    base_pr = STAGING / "Processador CVC"
    base_pr.mkdir()
    montar_processador_cvc(base_pr)
    zip_pr = ENTREGA / "Processador CVC.zip"
    zipar(base_pr, zip_pr)
    print(f"  OK -> {zip_pr}  ({zip_pr.stat().st_size/1024/1024:.1f} MB)")

    shutil.rmtree(STAGING)
    dur = (datetime.now() - inicio).total_seconds()
    print(f"\nConcluido em {dur:.1f}s.")
    print(f"Saidas em: {ENTREGA}")


if __name__ == "__main__":
    main()
