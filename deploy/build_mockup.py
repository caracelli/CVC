"""
Monta um pacote MOCKUP completo para simulacao local em ENTREGA/Mockup CVC.zip.

Diferente dos pacotes de entrega:
- Tem PROCESSADOR + VISUALIZADOR juntos (cliente roda os dois)
- ENTRADA ja vem POPULADA com os arquivos reais de Arquivos_origem/
- DADOS/BANCO/ vem VAZIO (o 1o run do Processador gera tudo do zero)
- Config com <rede><raiz/> vazia: tudo resolvido em relacao a pasta extraida
- LEIA-ME com passo-a-passo de uso

Pre-requisito: rodar deploy/build_all.py antes (gera os 5 exes).

Uso:
    cd deploy
    python build_mockup.py
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
STAGING = RAIZ / "_mockup_staging"

PRINCIPAL_VISUALIZADOR = EXECS / "visualizador.exe"
PRINCIPAL_PROCESSADOR = EXECS / "Processador.exe"
LAUNCHER_ATUALIZADOR = LAUNCHER_DIR / "launcher_atualizador.exe"
LAUNCHER_VISUALIZADOR = LAUNCHER_DIR / "launcher_visualizador.exe"
LAUNCHER_PROCESSADOR = LAUNCHER_DIR / "launcher_processador.exe"

REPORT_DIR = EXECS / "REPORT"
CONFIG_SRC = EXECS / "CONFIG" / "config.xml"
LEIA_ME_EXECS = EXECS / "LEIA-ME.md"

# Pastas criadas, mesmo vazias
DADOS_SUBDIRS = [
    "BANCO", "PROCESSADOS", "ERROS", "LOGS",
    "SAIDAS/DIVERGENCIAS", "SAIDAS/DESLIGADOS",
    "SAIDAS/TRANSFERIDOS", "SAIDAS/AUDITORIA",
]

# Mapa: arquivo de Arquivos_origem -> destino dentro de ENTRADA/
# (caminho relativo a CVC_IAM_ANALYTICS/ENTRADA/)
ARQUIVOS_ENTRADA = [
    # RH
    ("PROJETOIAM (8).CSV",                              "RH/ATIVOS/PROJETOIAM.CSV"),
    ("PROJETOIAMDESLIGADOS (2).CSV",                    "RH/DESLIGADOS/PROJETOIAMDESLIGADOS.CSV"),
    # SISTEMAS
    ("relatorio systur 30.04.xlsx",                     "SISTEMAS/SYSTUR/relatorio systur 30.04.xlsx"),
    ("SIGOT_30_04.csv",                                 "SISTEMAS/SIGOT/SIGOT_30_04.csv"),
    ("SICA_RA_30_04.csv",                               "SISTEMAS/SICA_RA/SICA_RA_30_04.csv"),
    ("relatorio IC 30.04.xlsx",                         "SISTEMAS/IC/relatorio IC 30.04.xlsx"),
    ("SIG_18.05.26.xlsx",                               "SISTEMAS/SIG/SIG_18.05.26.xlsx"),
    # MATRIZES — perfis esperados por cargo
    ("MATRIZ DE PERFIL DE ACESSO SYSTUR.xlsx",          "MATRIZES/PERFIS_SISTEMAS/MATRIZ DE PERFIL DE ACESSO SYSTUR.xlsx"),
    ("MATRIZ DE PERFIL DE ACESSO - SIGOT.xlsx",         "MATRIZES/PERFIS_SISTEMAS/MATRIZ DE PERFIL DE ACESSO - SIGOT.xlsx"),
    ("MATRIZ DE PERFIL DE ACESSO SICA RA.xlsx",         "MATRIZES/PERFIS_SISTEMAS/MATRIZ DE PERFIL DE ACESSO SICA RA.xlsx"),
    ("MATRIZ DE PERFIL DE ACESSO SICA ESFERA.xlsx",     "MATRIZES/PERFIS_SISTEMAS/MATRIZ DE PERFIL DE ACESSO SICA ESFERA.xlsx"),
    ("Matriz de Perfil de Acessso - IC Integrador Contabil.xlsx",
                                                         "MATRIZES/PERFIS_SISTEMAS/Matriz de Perfil de Acessso - IC Integrador Contabil.xlsx"),
    # MATRIZES — SIG de-para de codigos
    ("ID_x_Perfis_SIG 19.08.xlsx",                      "MATRIZES/PERFIS_SISTEMAS/SIG/DE_PARA/ID_x_Perfis_SIG 19.08.xlsx"),
    # MATRIZES — organizacional (CCO_CSC)
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
    """Copia os arquivos reais de Arquivos_origem/ pra ENTRADA/."""
    for src_rel, dst_rel in ARQUIVOS_ENTRADA:
        src = ORIGEM / src_rel
        dst = raiz_app / "ENTRADA" / dst_rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def montar_estrutura_dados(raiz_app: Path):
    for sub in DADOS_SUBDIRS:
        (raiz_app / "DADOS" / sub).mkdir(parents=True, exist_ok=True)
    (raiz_app / "INTERACOES").mkdir(parents=True, exist_ok=True)


def montar_mockup(base: Path):
    """Monta a estrutura completa do mockup."""
    raiz_app = base / "CVC_IAM_ANALYTICS"
    montar_executaveis(raiz_app / "EXECUTAVEIS")
    popular_entrada(raiz_app)
    montar_estrutura_dados(raiz_app)
    (base / "LEIA-ME.txt").write_text(LEIA_ME_MOCKUP, encoding="utf-8")


LEIA_ME_MOCKUP = """\
Mockup CVC IAM Analytics — simulacao local end-to-end
=======================================================

Pacote para simulacao COMPLETA em maquina local (sem rede). Inclui:
- Processador.exe (motor) + visualizador.exe (painel)
- ENTRADA ja populada com os arquivos reais (RH, SISTEMAS, MATRIZES)
- DADOS/BANCO/ vazio — o 1o run do Processador gera tudo do zero

Como usar (3 passos)
---------------------
1. Extraia este zip em qualquer pasta (ex.: Documentos\\Mockup CVC).
2. Entre em CVC_IAM_ANALYTICS\\EXECUTAVEIS\\ e execute Processador.exe.
   - Uma janela HTML abre mostrando o progresso (RH -> Matrizes -> SYSTUR
     -> SIG -> Vinculacao -> Divergencias -> Excel). Demora ~1-2 minutos.
   - Ao terminar, o banco fica em DADOS\\BANCO\\iam_analytics.db e os
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
SISTEMAS/SYSTUR/relatorio systur 30.04.xlsx                7106 acessos
SISTEMAS/SIGOT/SIGOT_30_04.csv                              288 usuarios (CSV bruto)
SISTEMAS/SICA_RA/SICA_RA_30_04.csv                          135 usuarios (CPF mascarado!)
SISTEMAS/IC/relatorio IC 30.04.xlsx                          62 usuarios
SISTEMAS/SIG/SIG_18.05.26.xlsx                              523 usuarios x 399 perfis
MATRIZES/PERFIS_SISTEMAS/MATRIZ DE PERFIL DE ACESSO SYSTUR.xlsx
                                                  1934 perfis esperados
MATRIZES/PERFIS_SISTEMAS/SIG/DE_PARA/ID_x_Perfis_SIG 19.08.xlsx
                                                   399 codigos do SIG
MATRIZES/ORGANIZACIONAL/Mapeamento CCO_CSC (1).xlsx
                                                  1471 mapeamentos CC x Sistema x Perfil

O que esperar do 1o run (com esses dados)
------------------------------------------
- ~40k acessos importados (33k SIG despivotados + 7k SYSTUR)
- ~27k divergencias detectadas:
    18k+ ACESSO_DESLIGADO   (funcionario saiu, acesso continua ativo)
    8k+  ACESSO_SEM_VINCULO_RH (login sem matricula no RH = terceirizado)
    50+  PERFIL_INVALIDO    (perfil divergente da matriz por cargo)
- Excel de saida gerado em DADOS\\SAIDAS\\DIVERGENCIAS\\ com data/hora.

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
  ENTRADA\\               <- arquivos do cliente (ja populados)
  DADOS\\
    BANCO\\               <- iam_analytics.db (gerado no 1o run)
    PROCESSADOS\\         <- arquivos ja importados vao pra ca
    ERROS\\               <- arquivos rejeitados
    LOGS\\                <- processador_AAAA-MM-DD.log
    SAIDAS\\DIVERGENCIAS\\ <- Excel de divergencias
  INTERACOES\\            <- vazia (quarentena/resolucoes vao surgir aqui)
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
    print("=== Build do MOCKUP CVC (simulacao local end-to-end) ===")
    checar_prerequisitos()
    if STAGING.exists():
        shutil.rmtree(STAGING)
    STAGING.mkdir(parents=True, exist_ok=True)
    ENTREGA.mkdir(parents=True, exist_ok=True)
    inicio = datetime.now()

    base = STAGING / "Mockup CVC"
    base.mkdir()
    print("\n[1/2] Montando estrutura...")
    montar_mockup(base)
    n_arquivos = sum(1 for _ in base.rglob("*") if _.is_file())
    print(f"  OK -> {n_arquivos} arquivos preparados em {base}")

    print("\n[2/2] Compactando...")
    alvo = ENTREGA / "Mockup CVC.zip"
    zipar(base, alvo)
    print(f"  OK -> {alvo}  ({alvo.stat().st_size/1024/1024:.1f} MB)")

    shutil.rmtree(STAGING)
    dur = (datetime.now() - inicio).total_seconds()
    print(f"\nConcluido em {dur:.1f}s.")
    print(f"Saida: {alvo}")


if __name__ == "__main__":
    main()
