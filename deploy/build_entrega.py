"""
Monta os dois pacotes de entrega em ENTREGA/:
  - Projeto CVC.zip      (visualizador + banco com cenario atual)
  - Processador CVC.zip  (motor + estrutura ENTRADA/DADOS vazia)

Ambos contem a pasta CVC_IAM_ANALYTICS espelhando a arquitetura atual,
com <rede><raiz> VAZIA — funcionam em qualquer pasta onde forem extraidos.

Pre-requisito: Processador.exe e visualizador.exe ja gerados em
CVC_IAM_ANALYTICS/EXECUTAVEIS/ (rodar build_processador.py e
build_visualizador.py antes).

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
ENTREGA = RAIZ / "ENTREGA"
STAGING = RAIZ / "_entrega_staging"

PROCESSADOR_EXE = EXECS / "Processador.exe"
VISUALIZADOR_EXE = EXECS / "visualizador.exe"
VISUALIZADOR_PY = EXECS / "visualizador.py"
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
    faltando = []
    for p in [PROCESSADOR_EXE, VISUALIZADOR_EXE, VISUALIZADOR_PY,
              CONFIG_SRC, BANCO_FONTE, REPORT_DIR / "index.html"]:
        if not p.exists():
            faltando.append(str(p))
    if faltando:
        print("FALHA — arquivos ausentes:")
        for f in faltando:
            print(f"  - {f}")
        sys.exit(1)


def config_com_raiz_vazia(destino: Path):
    """Le o config.xml atual e grava no destino com <rede><raiz> vazia."""
    tree = ET.parse(CONFIG_SRC)
    root = tree.getroot()
    raiz_node = root.find("rede/raiz")
    if raiz_node is not None:
        raiz_node.text = None  # zera a raiz -> modo "local pasta extraida"
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


def montar_projeto_cvc(base: Path):
    """Visualizador + banco (com cenario atual). Para o cliente VER o painel."""
    raiz = base / "CVC_IAM_ANALYTICS"
    # EXECUTAVEIS — somente o exe + config + REPORT + LEIA-ME (sem .py)
    execs = raiz / "EXECUTAVEIS"
    execs.mkdir(parents=True, exist_ok=True)
    shutil.copy2(VISUALIZADOR_EXE, execs / "visualizador.exe")
    shutil.copy2(LEIA_ME_EXECS, execs / "LEIA-ME.md")
    # REPORT
    shutil.copytree(REPORT_DIR, execs / "REPORT", dirs_exist_ok=True)
    # CONFIG com raiz vazia
    config_com_raiz_vazia(execs / "CONFIG" / "config.xml")
    # DADOS/BANCO (com banco copiado consistente)
    copiar_banco_consistente(raiz / "DADOS" / "BANCO" / "iam_analytics.db")
    # INTERACOES vazia (placeholder)
    (raiz / "INTERACOES").mkdir(parents=True, exist_ok=True)
    # LEIA-ME do pacote no topo
    (base / "LEIA-ME.txt").write_text(LEIA_ME_PROJETO, encoding="utf-8")


def montar_processador_cvc(base: Path):
    """Motor + ENTRADA/DADOS vazios. Para o cliente RODAR o engine."""
    raiz = base / "CVC_IAM_ANALYTICS"
    # EXECUTAVEIS
    execs = raiz / "EXECUTAVEIS"
    execs.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PROCESSADOR_EXE, execs / "Processador.exe")
    shutil.copy2(LEIA_ME_EXECS, execs / "LEIA-ME.md")
    config_com_raiz_vazia(execs / "CONFIG" / "config.xml")
    # ENTRADA — estrutura vazia (cliente deposita os arquivos)
    for sub in ENTRADA_SUBDIRS:
        (raiz / "ENTRADA" / sub).mkdir(parents=True, exist_ok=True)
    # DADOS — estrutura vazia
    for sub in DADOS_SUBDIRS:
        (raiz / "DADOS" / sub).mkdir(parents=True, exist_ok=True)
    # INTERACOES vazia
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
    visualizador.exe       <- aplicativo
    visualizador.py        <- codigo-fonte (auditoria)
    CONFIG\\config.xml      <- configuracao (raiz vazia = pasta local)
    REPORT\\index.html      <- pagina do painel
    LEIA-ME.md             <- detalhes tecnicos
  DADOS\\BANCO\\
    iam_analytics.db       <- banco com o cenario atual

Observacoes
-----------
- O config.xml ja vem com <raiz> vazia, ou seja, le os dados da
  pasta CVC_IAM_ANALYTICS extraida deste zip. Nao precisa configurar
  drive de rede para esta demonstracao.
- O visualizador faz uma copia local do banco no startup
  (mais rapido e sem ler durante uma eventual escrita do Processador).
"""

LEIA_ME_PROCESSADOR = """\
Processador CVC — Motor IAM Analytics
=======================================

Pacote do motor de processamento. Le os arquivos depositados em
ENTRADA, cruza com as matrizes e gera o banco iam_analytics.db.

Como usar
---------
1. Extraia este zip onde quiser (ex.: Documentos\\Processador CVC).
2. Deposite os arquivos do cliente nas pastas correspondentes:
     CVC_IAM_ANALYTICS\\ENTRADA\\RH\\ATIVOS\\
     CVC_IAM_ANALYTICS\\ENTRADA\\RH\\DESLIGADOS\\
     CVC_IAM_ANALYTICS\\ENTRADA\\MATRIZES\\ORGANIZACIONAL\\
     CVC_IAM_ANALYTICS\\ENTRADA\\MATRIZES\\PERFIS_SISTEMAS\\
     CVC_IAM_ANALYTICS\\ENTRADA\\SISTEMAS\\SYSTUR\\
     (idem para SIGOT, SICA_RA, SICA_ESFERA, IC quando houver)
3. Execute CVC_IAM_ANALYTICS\\EXECUTAVEIS\\Processador.exe.
4. O banco gerado fica em CVC_IAM_ANALYTICS\\DADOS\\BANCO\\iam_analytics.db
   (saidas Excel em DADOS\\SAIDAS).

Estrutura
---------
CVC_IAM_ANALYTICS\\
  EXECUTAVEIS\\
    Processador.exe        <- motor
    CONFIG\\config.xml      <- configuracao (raiz vazia = pasta local)
    LEIA-ME.md             <- detalhes tecnicos
  ENTRADA\\                  <- arquivos do cliente
    RH\\, MATRIZES\\, SISTEMAS\\
  DADOS\\                    <- saidas geradas
    BANCO\\, SAIDAS\\, PROCESSADOS\\, ERROS\\, LOGS\\
  INTERACOES\\               <- gravacoes do visualizador (multiusuario)

Observacoes
-----------
- O config.xml ja vem com <raiz> vazia, ou seja, todos os caminhos
  resolvem relativos a esta pasta extraida. Nao precisa de drive de
  rede para esta demonstracao.
- Para ver o resultado no painel, copie o banco gerado por cima do
  banco do pacote Projeto CVC, ou ajuste o config.xml para apontar
  ambos para a mesma raiz.
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
                # mantem diretorios vazios (cliente precisa do esqueleto de ENTRADA/DADOS)
                arcname = base.name + "/" + str(p.relative_to(base)).replace("\\", "/") + "/"
                zi = zipfile.ZipInfo(arcname)
                zf.writestr(zi, "")


def main():
    print("=== Build dos pacotes de ENTREGA ===")
    checar_prerequisitos()

    # Limpa staging
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

    # Limpa staging ao final
    shutil.rmtree(STAGING)

    dur = (datetime.now() - inicio).total_seconds()
    print(f"\nConcluido em {dur:.1f}s.")
    print(f"Saidas em: {ENTREGA}")


if __name__ == "__main__":
    main()
