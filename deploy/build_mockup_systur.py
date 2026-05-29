"""
Monta um pacote MOCKUP FOCADO EM SYSTUR em ENTREGA/Mockup CVC - SYSTUR.zip.

Versao mais leve do mockup completo, contendo somente o que e' necessario
pra demonstrar a Fase 1 (SYSTUR):
- Processador.exe + visualizador.exe
- ENTRADA com APENAS: RH + SYSTUR + matriz SYSTUR + Mapeamento CCO_CSC
- SEM SIG, SEM SIGOT, SEM SICA_RA, SEM SICA_ESFERA, SEM IC
- DADOS/BANCO/ vazio (gera no 1o run)
- Config com <raiz/> vazia

Os outros sistemas continuam declarados no config.xml, mas como as pastas
ficam vazias o Processador apenas pula essas etapas (sem erro).

Pre-requisito: rodar deploy/build_all.py antes (gera os 5 exes).

Uso:
    cd deploy
    python build_mockup_systur.py
"""
import shutil
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
ORIGEM = RAIZ / "Arquivos_origem"
ENTREGA = RAIZ / "ENTREGA"
STAGING = RAIZ / "_mockup_systur_staging"

PRINCIPAL_VISUALIZADOR = EXECS / "visualizador.exe"
PRINCIPAL_PROCESSADOR = EXECS / "Processador.exe"
LAUNCHER_ATUALIZADOR = LAUNCHER_DIR / "launcher_atualizador.exe"
LAUNCHER_VISUALIZADOR = LAUNCHER_DIR / "launcher_visualizador.exe"
LAUNCHER_PROCESSADOR = LAUNCHER_DIR / "launcher_processador.exe"

REPORT_DIR = EXECS / "REPORT"
CONFIG_SRC = EXECS / "CONFIG" / "config.xml"
LEIA_ME_EXECS = EXECS / "LEIA-ME.md"

# Pastas DADOS (mesma estrutura do mockup completo)
DADOS_SUBDIRS = [
    "BANCO", "PROCESSADOS", "ERROS", "LOGS",
    "SAIDAS/DIVERGENCIAS", "SAIDAS/DESLIGADOS",
    "SAIDAS/TRANSFERIDOS", "SAIDAS/AUDITORIA",
]

# Subpastas ENTRADA criadas vazias (pros outros sistemas que existem
# no config.xml — Processador pula se vazio)
ENTRADA_SUBDIRS_VAZIAS = [
    "SISTEMAS/SIGOT", "SISTEMAS/SICA_RA", "SISTEMAS/SICA_ESFERA", "SISTEMAS/IC",
    "SISTEMAS/SIG",
    "MATRIZES/PERFIS_SISTEMAS/SIG/DE_PARA",
]

# Mapa: arquivo de Arquivos_origem -> destino dentro de ENTRADA/
# So o que importa pra SYSTUR.
ARQUIVOS_ENTRADA = [
    # RH (sempre necessario — cruzamento por CPF)
    ("PROJETOIAM (8).CSV",                              "RH/ATIVOS/PROJETOIAM.CSV"),
    ("PROJETOIAMDESLIGADOS (2).CSV",                    "RH/DESLIGADOS/PROJETOIAMDESLIGADOS.CSV"),
    # Sistema SYSTUR
    ("relatorio systur 30.04.xlsx",                     "SISTEMAS/SYSTUR/relatorio systur 30.04.xlsx"),
    # Matriz de perfil esperado por cargo (so a do SYSTUR)
    ("MATRIZ DE PERFIL DE ACESSO SYSTUR.xlsx",          "MATRIZES/PERFIS_SISTEMAS/MATRIZ DE PERFIL DE ACESSO SYSTUR.xlsx"),
    # Mapeamento organizacional (cobre todos os sistemas, inclusive SYSTUR)
    ("Mapeamento CCO_CSC (1).xlsx",                     "MATRIZES/ORGANIZACIONAL/Mapeamento CCO_CSC (1).xlsx"),
]


def checar_prerequisitos():
    faltando_exes = [str(p) for p in [
        PRINCIPAL_VISUALIZADOR, PRINCIPAL_PROCESSADOR,
        LAUNCHER_ATUALIZADOR, LAUNCHER_VISUALIZADOR, LAUNCHER_PROCESSADOR,
        CONFIG_SRC, REPORT_DIR / "index.html",
    ] if not p.exists()]
    if faltando_exes:
        print("FALHA — executaveis/recursos ausentes:")
        for f in faltando_exes:
            print(f"  - {f}")
        print("\nRode 'python deploy/build_all.py' primeiro.")
        sys.exit(1)
    faltando_arq = [src for src, _ in ARQUIVOS_ENTRADA if not (ORIGEM / src).exists()]
    if faltando_arq:
        print("FALHA — arquivos de Arquivos_origem/ ausentes:")
        for f in faltando_arq:
            print(f"  - {ORIGEM / f}")
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


def montar_executaveis(execs_destino: Path):
    """Top: visualizador.exe + Processador.exe. launcher/: os 3 launchers."""
    execs_destino.mkdir(parents=True, exist_ok=True)
    (execs_destino / "launcher").mkdir(parents=True, exist_ok=True)
    shutil.copy2(PRINCIPAL_VISUALIZADOR, execs_destino / "visualizador.exe")
    shutil.copy2(PRINCIPAL_PROCESSADOR, execs_destino / "Processador.exe")
    shutil.copy2(LEIA_ME_EXECS, execs_destino / "LEIA-ME.md")
    shutil.copytree(REPORT_DIR, execs_destino / "REPORT", dirs_exist_ok=True)
    config_com_raiz_vazia(execs_destino / "CONFIG" / "config.xml")
    shutil.copy2(LAUNCHER_ATUALIZADOR,
                 execs_destino / "launcher" / "launcher_atualizador.exe")
    shutil.copy2(LAUNCHER_VISUALIZADOR,
                 execs_destino / "launcher" / "launcher_visualizador.exe")
    shutil.copy2(LAUNCHER_PROCESSADOR,
                 execs_destino / "launcher" / "launcher_processador.exe")


def popular_entrada(raiz_app: Path):
    """Copia os arquivos do SYSTUR + RH + matriz SYSTUR + CCO."""
    for src_rel, dst_rel in ARQUIVOS_ENTRADA:
        src = ORIGEM / src_rel
        dst = raiz_app / "ENTRADA" / dst_rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    # Cria as subpastas vazias dos outros sistemas — o Processador pula
    # quando nao tem arquivos, e o cliente pode adicionar depois se quiser.
    for sub in ENTRADA_SUBDIRS_VAZIAS:
        (raiz_app / "ENTRADA" / sub).mkdir(parents=True, exist_ok=True)


def montar_estrutura_dados(raiz_app: Path):
    for sub in DADOS_SUBDIRS:
        (raiz_app / "DADOS" / sub).mkdir(parents=True, exist_ok=True)
    (raiz_app / "INTERACOES").mkdir(parents=True, exist_ok=True)


def montar_mockup(base: Path):
    raiz_app = base / "CVC_IAM_ANALYTICS"
    montar_executaveis(raiz_app / "EXECUTAVEIS")
    popular_entrada(raiz_app)
    montar_estrutura_dados(raiz_app)
    (base / "LEIA-ME.txt").write_text(LEIA_ME_MOCKUP_SYSTUR, encoding="utf-8")


LEIA_ME_MOCKUP_SYSTUR = """\
Mockup CVC IAM Analytics — versao SYSTUR (Fase 1)
==================================================

Pacote para simulacao local da Fase 1 do projeto (so SYSTUR). Inclui:
- Processador.exe (motor) + visualizador.exe (painel)
- ENTRADA ja populada com SYSTUR + RH + matriz SYSTUR + Mapeamento CCO_CSC
- DADOS/BANCO/ vazio — o 1o run do Processador gera tudo do zero

Outros sistemas (SIGOT, SICA_RA, SICA_ESFERA, IC, SIG) ficam declarados no
config mas com pastas vazias — o Processador apenas pula essas etapas, sem
erro. Para ativar um sistema, basta depositar o arquivo correspondente em
ENTRADA/SISTEMAS/<SISTEMA>/.

Como usar (3 passos)
---------------------
1. Extraia este zip em qualquer pasta (ex.: Documentos\\Mockup SYSTUR).
2. Entre em CVC_IAM_ANALYTICS\\EXECUTAVEIS\\ e execute Processador.exe.
   - Uma janela HTML abre mostrando o progresso (RH -> Matrizes -> SYSTUR
     -> Vinculacao -> Divergencias -> Excel). Demora ~30-60 segundos.
   - Ao terminar, o banco fica em DADOS\\BANCO\\iam_analytics.db e o
     Excel de saida em DADOS\\SAIDAS\\DIVERGENCIAS\\.
3. Ainda em EXECUTAVEIS\\, execute visualizador.exe.
   - O navegador abre em http://127.0.0.1:8800/ com o painel preenchido.
   - Para encerrar, feche a aba do navegador.

Voce pode rodar visualizador.exe quantas vezes quiser sem reprocessar.
Para reprocessar do zero: apague DADOS\\BANCO\\iam_analytics.db e rode
Processador.exe novamente.

Arquivos ja em ENTRADA
-----------------------
RH/ATIVOS/PROJETOIAM.CSV                   2207 ativos
RH/DESLIGADOS/PROJETOIAMDESLIGADOS.CSV     11290 desligados
SISTEMAS/SYSTUR/relatorio systur 30.04.xlsx        7106 acessos
MATRIZES/PERFIS_SISTEMAS/MATRIZ DE PERFIL DE ACESSO SYSTUR.xlsx
                                                  1934 perfis esperados
MATRIZES/ORGANIZACIONAL/Mapeamento CCO_CSC (1).xlsx
                                                  1471 mapeamentos CC x Sistema x Perfil

O que esperar do 1o run
------------------------
- 7106 acessos SYSTUR importados
- ~9-10k divergencias detectadas (a maioria ACESSO_DESLIGADO e SEM_VINCULO_RH)
- Excel de saida gerado em DADOS\\SAIDAS\\DIVERGENCIAS\\ com data/hora
- Painel mostra ~6800 itens de acao (Incluir Acesso, Alterar Perfil,
  Em Analise, Nao Mapeado)

Estrutura
---------
CVC_IAM_ANALYTICS\\
  EXECUTAVEIS\\
    Processador.exe      <- (1) rode primeiro
    visualizador.exe     <- (2) rode depois
    CONFIG\\config.xml    <- <raiz/> vazia (modo local)
    REPORT\\index.html    <- pagina do painel
    LEIA-ME.md
    launcher\\
      launcher_atualizador.exe
      launcher_processador.exe
      launcher_visualizador.exe
  ENTRADA\\               <- so SYSTUR populado; demais sistemas vazios
  DADOS\\
    BANCO\\               <- iam_analytics.db (gerado no 1o run)
    PROCESSADOS\\         <- arquivos ja importados vao pra ca
    ERROS\\               <- arquivos rejeitados
    LOGS\\                <- processador_AAAA-MM-DD.log
    SAIDAS\\DIVERGENCIAS\\ <- Excel de divergencias
  INTERACOES\\            <- vazia (quarentena/resolucoes vao surgir aqui)

Para a versao COMPLETA (com SIG + outros sistemas), use Mockup CVC.zip.
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
    print("=== Build do MOCKUP CVC - SYSTUR (Fase 1) ===")
    checar_prerequisitos()
    if STAGING.exists():
        shutil.rmtree(STAGING)
    STAGING.mkdir(parents=True, exist_ok=True)
    ENTREGA.mkdir(parents=True, exist_ok=True)
    inicio = datetime.now()

    base = STAGING / "Mockup CVC - SYSTUR"
    base.mkdir()
    print("\n[1/2] Montando estrutura...")
    montar_mockup(base)
    n_arquivos = sum(1 for _ in base.rglob("*") if _.is_file())
    print(f"  OK -> {n_arquivos} arquivos preparados em {base}")

    print("\n[2/2] Compactando...")
    alvo = ENTREGA / "Mockup CVC - SYSTUR.zip"
    zipar(base, alvo)
    print(f"  OK -> {alvo}  ({alvo.stat().st_size/1024/1024:.1f} MB)")

    shutil.rmtree(STAGING)
    dur = (datetime.now() - inicio).total_seconds()
    print(f"\nConcluido em {dur:.1f}s.")
    print(f"Saida: {alvo}")


if __name__ == "__main__":
    main()
