"""
Monta o pacote de PRODUCAO — ENTREGA_PRD_v1.0.0.zip.

Pasta CVC_IAM_ANALYTICS/ completa e LIMPA para o go-live:
  - EXECUTAVEIS/  (visualizador.exe, Processador.exe, launcher/ COM motor,
                  CONFIG/config.xml [versao 1.0.0, raiz Z:], REPORT/)
  - ENTRADA/      VAZIA (so a estrutura de pastas — o cliente deposita os
                  arquivos de producao e roda o Processador)
  - DADOS/        VAZIO (sem banco — o Processador gera o iam_analytics.db)
  - INTERACOES/   vazia
  - LEIA-ME.txt

Base 100% limpa: nenhum dado de teste/dev, nenhum banco, nenhum arquivo de
entrada, nenhum __pycache__/parquet/wal. O staging e' montado do zero copiando
apenas os artefatos necessarios, entao o pacote e' limpo por construcao.

Pre-requisito: exes buildados (deploy/build_all.py). A versao e' lida do config
em runtime — nao precisa rebuildar so para mudar a versao.

Uso:
    cd deploy
    python build_entrega_prd.py
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
ENTREGA = RAIZ / "ENTREGA"
STAGING = RAIZ / "_entrega_prd_staging"

VERSAO = "1.0.0"
RAIZ_REDE = r"Z:\CVC\CVC_IAM_ANALYTICS"

LAUNCHER_DIR = EXECS / "launcher"
PRINCIPAL_VISUALIZADOR = EXECS / "visualizador.exe"
PRINCIPAL_PROCESSADOR = EXECS / "Processador.exe"
LAUNCHER_ATUALIZADOR = LAUNCHER_DIR / "launcher_atualizador.exe"
LAUNCHER_VISUALIZADOR = LAUNCHER_DIR / "launcher_visualizador.exe"
LAUNCHER_PROCESSADOR = LAUNCHER_DIR / "launcher_processador.exe"
REPORT_DIR = EXECS / "REPORT"
CONFIG_SRC = EXECS / "CONFIG" / "config.xml"
LEIA_ME_EXECS = EXECS / "LEIA-ME.md"

ENTRADA_SUBDIRS = [
    "RH/ATIVOS", "RH/DESLIGADOS",
    "SISTEMAS/SIGOT", "SISTEMAS/SICA_RA", "SISTEMAS/SICA_ESFERA",
    "SISTEMAS/SYSTUR", "SISTEMAS/IC", "SISTEMAS/SIG",
    "SISTEMAS/ORACLE_EBS", "SISTEMAS/OPERA_OPERACIONAL",
    "MATRIZES/ORGANIZACIONAL", "MATRIZES/PERFIS_SISTEMAS",
]
DADOS_SUBDIRS = [
    "BANCO", "PROCESSADOS", "ERROS", "LOGS",
    "SAIDAS/DIVERGENCIAS", "SAIDAS/DESLIGADOS",
    "SAIDAS/TRANSFERIDOS", "SAIDAS/AUDITORIA",
]


def checar_prerequisitos():
    base = [PRINCIPAL_VISUALIZADOR, PRINCIPAL_PROCESSADOR,
            LAUNCHER_ATUALIZADOR, LAUNCHER_VISUALIZADOR, LAUNCHER_PROCESSADOR,
            CONFIG_SRC, REPORT_DIR / "index.html"]
    faltando = [str(p) for p in base if not p.exists()]
    if faltando:
        print("FALHA — exes/arquivos ausentes:")
        for f in faltando:
            print(f"  - {f}")
        print("\nRode 'python deploy/build_all.py' primeiro.")
        sys.exit(1)


def grava_config(destino: Path, versao: str, raiz_valor: str):
    tree = ET.parse(CONFIG_SRC)
    root = tree.getroot()
    n_v = root.find("versao")
    if n_v is not None:
        n_v.text = versao
    n_r = root.find("rede/raiz")
    if n_r is not None:
        n_r.text = raiz_valor
    destino.parent.mkdir(parents=True, exist_ok=True)
    tree.write(destino, encoding="UTF-8", xml_declaration=True)


def montar_executaveis(execs_destino: Path):
    """EXECUTAVEIS/ completo: 2 principais + 3 launchers (com motor) + REPORT +
    CONFIG (versao 1.0.0, raiz Z:)."""
    execs_destino.mkdir(parents=True, exist_ok=True)
    launcher_d = execs_destino / "launcher"
    launcher_d.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PRINCIPAL_VISUALIZADOR, execs_destino / "visualizador.exe")
    shutil.copy2(PRINCIPAL_PROCESSADOR, execs_destino / "Processador.exe")
    if LEIA_ME_EXECS.exists():
        shutil.copy2(LEIA_ME_EXECS, execs_destino / "LEIA-ME.md")
    shutil.copytree(REPORT_DIR, execs_destino / "REPORT", dirs_exist_ok=True)
    grava_config(execs_destino / "CONFIG" / "config.xml", VERSAO, RAIZ_REDE)
    shutil.copy2(LAUNCHER_ATUALIZADOR, launcher_d / "launcher_atualizador.exe")
    shutil.copy2(LAUNCHER_VISUALIZADOR, launcher_d / "launcher_visualizador.exe")
    shutil.copy2(LAUNCHER_PROCESSADOR, launcher_d / "launcher_processador.exe")


def montar(base: Path):
    raiz = base / "CVC_IAM_ANALYTICS"
    montar_executaveis(raiz / "EXECUTAVEIS")
    # ENTRADA: so a estrutura, VAZIA
    for sub in ENTRADA_SUBDIRS:
        (raiz / "ENTRADA" / sub).mkdir(parents=True, exist_ok=True)
    # DADOS: esqueleto, SEM banco
    for sub in DADOS_SUBDIRS:
        (raiz / "DADOS" / sub).mkdir(parents=True, exist_ok=True)
    # INTERACOES vazia
    (raiz / "INTERACOES").mkdir(parents=True, exist_ok=True)
    (raiz / "LEIA-ME.txt").write_text(LEIA_ME, encoding="utf-8")


def zipar(base: Path, alvo_zip: Path):
    alvo_zip.parent.mkdir(parents=True, exist_ok=True)
    if alvo_zip.exists():
        alvo_zip.unlink()
    with zipfile.ZipFile(alvo_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for p in base.rglob("*"):
            if p.is_file():
                arcname = base.name + "/" + str(p.relative_to(base)).replace("\\", "/")
                zf.write(p, arcname)
            elif p.is_dir() and not any(p.iterdir()):
                arcname = base.name + "/" + str(p.relative_to(base)).replace("\\", "/") + "/"
                zf.writestr(zipfile.ZipInfo(arcname), "")


LEIA_ME = """\
ENTREGA PRODUCAO - CVC IAM Analytics (v1.0.0)
=============================================

Pacote de PRODUCAO com a pasta CVC_IAM_ANALYTICS (programa + estrutura de
dados VAZIA). Base limpa: nenhum dado, nenhum banco. O banco nasce no primeiro
processamento.

Caminho de rede assumido: Z:\\CVC\\CVC_IAM_ANALYTICS

------------------------------------------------------------
1. SUBIR A REDE (uma vez)
------------------------------------------------------------
Extraia o zip e copie a pasta CVC_IAM_ANALYTICS para Z:\\CVC\\
(fica Z:\\CVC\\CVC_IAM_ANALYTICS\\). O config ja vem com
<raiz>Z:\\CVC\\CVC_IAM_ANALYTICS</raiz> e <versao>1.0.0</versao>.

------------------------------------------------------------
2. DEPOSITAR OS ARQUIVOS DE PRODUCAO
------------------------------------------------------------
Coloque os arquivos atuais nas pastas de ENTRADA:
  RH ativos        -> ENTRADA\\RH\\ATIVOS
  Mapeamento CCO   -> ENTRADA\\MATRIZES\\ORGANIZACIONAL
  Matriz SYSTUR    -> ENTRADA\\MATRIZES\\PERFIS_SISTEMAS
  Extrato SYSTUR   -> ENTRADA\\SISTEMAS\\SYSTUR
(Escopo Fase 1 = SYSTUR. Demais sistemas/desligados/terceiros estao
 desativados no config e podem ser ligados nas proximas fases.)

------------------------------------------------------------
3. PRIMEIRO PROCESSAMENTO (gera o banco)
------------------------------------------------------------
Rode uma vez (de uma maquina com Z: mapeado):
    Z:\\CVC\\CVC_IAM_ANALYTICS\\EXECUTAVEIS\\Processador.exe
Ao fim: Z:\\...\\DADOS\\BANCO\\iam_analytics.db criado; arquivos lidos
movidos para PROCESSADOS. Log em DADOS\\LOGS\\.

------------------------------------------------------------
4. CADA MAQUINA-USUARIO
------------------------------------------------------------
Copie a pasta EXECUTAVEIS (de Z:\\CVC\\CVC_IAM_ANALYTICS\\) para um local
(ex.: C:\\CVC\\EXECUTAVEIS) e rode o visualizador.exe DE LA. Ele auto-atualiza
da rede, copia o banco para um cache local e abre o painel em
http://127.0.0.1:8800/.
"""


def main():
    print("=== Build ENTREGA PRODUCAO (CVC_IAM_ANALYTICS limpo, v%s) ===" % VERSAO)
    checar_prerequisitos()
    if STAGING.exists():
        shutil.rmtree(STAGING, ignore_errors=True)
    STAGING.mkdir(parents=True, exist_ok=True)
    ENTREGA.mkdir(parents=True, exist_ok=True)

    inicio = datetime.now()
    montar(STAGING)

    alvo = ENTREGA / f"ENTREGA_PRD_v{VERSAO}.zip"
    zipar(STAGING / "CVC_IAM_ANALYTICS", alvo)
    print(f"\n  OK -> {alvo}  ({alvo.stat().st_size/1024/1024:.1f} MB)")
    print(f"  versao={VERSAO}  raiz={RAIZ_REDE}  ENTRADA=vazia  DADOS=sem banco")

    shutil.rmtree(STAGING, ignore_errors=True)
    print(f"Concluido em {(datetime.now()-inicio).total_seconds():.1f}s.")


if __name__ == "__main__":
    main()
