"""
Monta o pacote de PRODUCAO — ENTREGA_PRD_v<versao>.zip.

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
    python build_entrega_prd.py                 # versao padrao (VERSAO abaixo)
    python build_entrega_prd.py --versao 0.0.0  # go-live: o cliente ajusta depois
"""
import shutil
import sys as _sys
from pathlib import Path as _Path
# roda tanto de dentro de deploy/ quanto da raiz do repo
_sys.path.insert(0, str(_Path(__file__).resolve().parent))
import _staging
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

VERSAO = "1.3.1"   # padrao; --versao sobrescreve
# Producao usa o UNC real do cliente (o Z: era convencao de teste com subst).
RAIZ_REDE = r"\\intra.cvc\fscvc\Processos_Antlia\CVC\CVC_IAM\ANALYTICS"

LAUNCHER_DIR = EXECS / "launcher"
PRINCIPAL_VISUALIZADOR = EXECS / "visualizador.exe"
PRINCIPAL_PROCESSADOR = EXECS / "Processador.exe"
LAUNCHER_ATUALIZADOR = LAUNCHER_DIR / "launcher_atualizador.exe"
LAUNCHER_VISUALIZADOR = LAUNCHER_DIR / "launcher_visualizador.exe"
LAUNCHER_PROCESSADOR = LAUNCHER_DIR / "launcher_processador.exe"
REPORT_DIR = EXECS / "REPORT"
CONFIG_SRC = EXECS / "CONFIG" / "config.xml"
MOTIVOS_SRC = EXECS / "CONFIG" / "motivos_resolucao.xml"
LEIA_ME_EXECS = EXECS / "LEIA-ME.md"

ENTRADA_SUBDIRS = [
    "RH/ATIVOS", "RH/DESLIGADOS",
    # Diretorio AD (config <diretorio_ad>): franqueados, prestadores e
    # desligados. Faltavam aqui (05/10/2026) — o Processador as le.
    "RH/AD", "SISTEMAS/AD_FRANQUEADOS", "SISTEMAS/AD_PRESTADORES",
    "SISTEMAS/AD_DESLIGADOS",
    "SISTEMAS/SIGOT", "SISTEMAS/SICA_RA", "SISTEMAS/SICA_ESFERA",
    "SISTEMAS/SYSTUR", "SISTEMAS/IC", "SISTEMAS/SIG",
    "SISTEMAS/ORACLE_EBS",
    "MATRIZES/ORGANIZACIONAL", "MATRIZES/PERFIS_SISTEMAS",
    # de-para de codigos do SIG (ID -> nome do perfil). Sem esta pasta o
    # cliente nao tem onde depositar o arquivo, e os perfis do SIG aparecem
    # pelo codigo cru na tela — foi o retorno da area em 25/08/2026.
    "MATRIZES/PERFIS_SISTEMAS/SIG/DE_PARA",
]
# Arquivos de REFERENCIA que viajam com o pacote (matrizes, nao extratos) — os
# mesmos do pacote da Bruna (build_update_bruna.py): sem o de-para os perfis do
# SIG aparecem pelo codigo; sem a matriz de lojas a regra do franqueado fica
# inerte.
REFERENCIAS = [
    (RAIZ / "Arquivos_origem" / "ID_x_Perfis_SIG 19.08.xlsx",
     "ENTRADA/MATRIZES/PERFIS_SISTEMAS/SIG/DE_PARA"),
    (RAIZ / "Arquivos_origem" / "MATRIZ DE PERFIL DE ACESSO SYSTUR - LOJAS.xlsx",
     "ENTRADA/MATRIZES/PERFIS_SISTEMAS"),
]

DADOS_SUBDIRS = [
    "BANCO", "PROCESSADOS", "ERROS", "LOGS",
    "SAIDAS/DIVERGENCIAS", "SAIDAS/DESLIGADOS",
    "SAIDAS/TRANSFERIDOS", "SAIDAS/AUDITORIA",
]


def checar_prerequisitos():
    base = [PRINCIPAL_VISUALIZADOR, PRINCIPAL_PROCESSADOR,
            LAUNCHER_ATUALIZADOR, LAUNCHER_VISUALIZADOR, LAUNCHER_PROCESSADOR,
            CONFIG_SRC, MOTIVOS_SRC, REPORT_DIR / "index.html"]
    faltando = [str(p) for p in base + [o for o, _ in REFERENCIAS]
                if not p.exists()]
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
    CONFIG (versao do pacote, raiz UNC de producao)."""
    execs_destino.mkdir(parents=True, exist_ok=True)
    launcher_d = execs_destino / "launcher"
    launcher_d.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PRINCIPAL_VISUALIZADOR, execs_destino / "visualizador.exe")
    shutil.copy2(PRINCIPAL_PROCESSADOR, execs_destino / "Processador.exe")
    if LEIA_ME_EXECS.exists():
        shutil.copy2(LEIA_ME_EXECS, execs_destino / "LEIA-ME.md")
    shutil.copytree(REPORT_DIR, execs_destino / "REPORT", dirs_exist_ok=True)
    grava_config(execs_destino / "CONFIG" / "config.xml", VERSAO, RAIZ_REDE)
    # motivos_resolucao.xml — combobox obrigatorio de resolucao (Ajuste 2).
    # Sem isso o painel cai no fallback de 2 motivos.
    if MOTIVOS_SRC.exists():
        shutil.copy2(MOTIVOS_SRC, execs_destino / "CONFIG" / "motivos_resolucao.xml")
    # modelo do jira.xml (a infra copia para jira.xml na rede e preenche o
    # token). So' o MODELO: a credencial nunca viaja no pacote.
    jira_modelo = EXECS / "CONFIG" / "jira.xml.exemplo"
    if jira_modelo.exists():
        shutil.copy2(jira_modelo, execs_destino / "CONFIG" / "jira.xml.exemplo")
    shutil.copy2(LAUNCHER_ATUALIZADOR, launcher_d / "launcher_atualizador.exe")
    shutil.copy2(LAUNCHER_VISUALIZADOR, launcher_d / "launcher_visualizador.exe")
    shutil.copy2(LAUNCHER_PROCESSADOR, launcher_d / "launcher_processador.exe")


def montar(base: Path):
    raiz = base / "CVC_IAM_ANALYTICS"
    montar_executaveis(raiz / "EXECUTAVEIS")
    # ENTRADA: a estrutura, sem extratos — so as matrizes de referencia
    for sub in ENTRADA_SUBDIRS:
        (raiz / "ENTRADA" / sub).mkdir(parents=True, exist_ok=True)
    for origem, destino in REFERENCIAS:
        (raiz / destino).mkdir(parents=True, exist_ok=True)
        shutil.copy2(origem, raiz / destino / origem.name)
    # DADOS: esqueleto, SEM banco
    for sub in DADOS_SUBDIRS:
        (raiz / "DADOS" / sub).mkdir(parents=True, exist_ok=True)
    # INTERACOES vazia
    (raiz / "INTERACOES").mkdir(parents=True, exist_ok=True)
    (raiz / "LEIA-ME.txt").write_text(LEIA_ME.replace("{versao}", VERSAO),
                                      encoding="utf-8")


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
ENTREGA PRODUCAO - CVC IAM Analytics (v{versao})
==================================================

Pacote de PRODUCAO com a pasta CVC_IAM_ANALYTICS (programa + estrutura de
dados VAZIA). Nenhum dado, nenhum banco: o banco nasce no primeiro
processamento. A ENTRADA ja traz as duas matrizes de referencia (de-para do
SIG e matriz de lojas/franqueado).

Caminho de rede (config.xml <raiz>):
  \\\\intra.cvc\\fscvc\\Processos_Antlia\\CVC\\CVC_IAM\\ANALYTICS
(Nos passos abaixo, "a RAIZ de rede" = esse caminho.)

------------------------------------------------------------
1. SUBIR A REDE (uma vez)
------------------------------------------------------------
Extraia o zip e copie a pasta CVC_IAM_ANALYTICS para dentro da RAIZ de rede.
O config ja vem com a <raiz> UNC correta e <versao>{versao}</versao>.

------------------------------------------------------------
2. DEPOSITAR OS ARQUIVOS DE PRODUCAO
------------------------------------------------------------
Coloque os arquivos atuais nas pastas de ENTRADA (subpastas por mes, como
07-2026, sao aceitas):
  RH ativos              -> ENTRADA\\RH\\ATIVOS
  RH desligados          -> ENTRADA\\RH\\DESLIGADOS
  Mapeamento CCO         -> ENTRADA\\MATRIZES\\ORGANIZACIONAL
  Matrizes de perfil     -> ENTRADA\\MATRIZES\\PERFIS_SISTEMAS
                            (SIGOT, SICA RA, SICA ESFERA, SYSTUR, IC, ORACLE EBS)
  Extratos dos sistemas  -> ENTRADA\\SISTEMAS\\<SISTEMA>
                            (SIGOT, SICA_RA, SICA_ESFERA, SYSTUR, IC, SIG,
                             ORACLE_EBS)
  Diretorio AD           -> ENTRADA\\SISTEMAS\\AD_FRANQUEADOS, AD_PRESTADORES e
                            AD_DESLIGADOS
Os 7 sistemas estao ativos no config.

------------------------------------------------------------
3. PRIMEIRO PROCESSAMENTO (gera o banco)
------------------------------------------------------------
Rode uma vez (de uma maquina que enxergue a RAIZ de rede):
    <RAIZ>\\EXECUTAVEIS\\Processador.exe
Ao fim: <RAIZ>\\DADOS\\BANCO\\iam_analytics.db criado; arquivos lidos
movidos para PROCESSADOS. Log em DADOS\\LOGS\\. Com varios meses de arquivos
o primeiro processamento e' demorado (horas).

------------------------------------------------------------
4. AJUSTAR A VERSAO (depois do processamento)
------------------------------------------------------------
Em <RAIZ>\\EXECUTAVEIS\\CONFIG\\config.xml, troque <versao>{versao}</versao>
pela versao oficial. As maquinas-usuario comparam a versao local com a da
rede e se atualizam sozinhas quando ela muda.

------------------------------------------------------------
5. CADA MAQUINA-USUARIO
------------------------------------------------------------
Copie a pasta EXECUTAVEIS (de dentro da RAIZ de rede) para um local
(ex.: C:\\CVC\\EXECUTAVEIS) e rode o visualizador.exe DE LA. Ele auto-atualiza
da rede, copia o banco para um cache local e abre o painel em
http://127.0.0.1:8800/.
"""


LEIA_ME_ATUALIZACAO = """\
ATUALIZACAO PRODUCAO - CVC IAM Analytics (v{versao})
=====================================================

So' a pasta EXECUTAVEIS. Nao traz banco, ENTRADA nem INTERACOES: nada do que
ja esta na rede e' apagado.

Corrige o "database disk image is malformed" do painel (09/10): o banco da
rede passa a gravar no modo seguro para pasta de rede (sem WAL); o painel
confere a copia antes de usar e nao copia durante o processamento.

1. Feche o painel e o Processador em todas as maquinas.
2. Em <RAIZ>\\DADOS\\BANCO: se ainda existirem iam_analytics.db-wal e
   iam_analytics.db-shm, MOVA os dois para uma pasta _orfao_0910 (nao apague;
   nao mexa no iam_analytics.db). "Arquivo em uso" = algum painel aberto.
3. Copie a pasta EXECUTAVEIS do zip POR CIMA de <RAIZ>\\EXECUTAVEIS
   (aceite substituir). O CONFIG\\jira.xml da rede NAO e' tocado.
4. Rode <RAIZ>\\EXECUTAVEIS\\Processador.exe UMA vez, de UMA maquina so',
   com TODOS os paineis fechados, e espere "Processamento finalizado".
5. Abra o painel. As maquinas-usuario se atualizam sozinhas porque a
   <versao> mudou ({versao}) e descartam a copia local corrompida. Para usar
   outra versao, troque em CONFIG\\config.xml antes do passo 4.

IMPORTANTE: apague instalacoes ANTIGAS do programa que apontem para a rede.
"""


def main():
    global VERSAO
    if "--versao" in sys.argv:
        VERSAO = sys.argv[sys.argv.index("--versao") + 1]
    print("=== Build ENTREGA PRODUCAO (CVC_IAM_ANALYTICS limpo, v%s) ===" % VERSAO)
    checar_prerequisitos()
    _staging.limpar(STAGING)   # ver deploy/_staging.py — ignore_errors mentia
    STAGING.mkdir(parents=True, exist_ok=True)
    ENTREGA.mkdir(parents=True, exist_ok=True)

    inicio = datetime.now()
    if "--atualizacao" in sys.argv:
        # ATUALIZACAO da rede ja instalada (08/10/2026): SO' a pasta
        # EXECUTAVEIS — nao toca no banco, na ENTRADA nem nas INTERACOES.
        raiz = STAGING / "CVC_IAM_ANALYTICS"
        montar_executaveis(raiz / "EXECUTAVEIS")
        (raiz / "LEIA-ME_ATUALIZACAO.txt").write_text(
            LEIA_ME_ATUALIZACAO.replace("{versao}", VERSAO), encoding="utf-8")
        alvo = ENTREGA / f"ATUALIZACAO_PRD_v{VERSAO}.zip"
        zipar(raiz, alvo)
        print(f"  OK -> {alvo}  ({alvo.stat().st_size/1024/1024:.1f} MB)")
        print(f"  versao={VERSAO}  raiz={RAIZ_REDE}  SO' EXECUTAVEIS")
        shutil.rmtree(STAGING, ignore_errors=True)
        return
    montar(STAGING)

    alvo = ENTREGA / f"ENTREGA_PRD_v{VERSAO}.zip"
    zipar(STAGING / "CVC_IAM_ANALYTICS", alvo)
    print(f"\n  OK -> {alvo}  ({alvo.stat().st_size/1024/1024:.1f} MB)")
    print(f"  versao={VERSAO}  raiz={RAIZ_REDE}  ENTRADA=vazia  DADOS=sem banco")

    shutil.rmtree(STAGING, ignore_errors=True)
    print(f"Concluido em {(datetime.now()-inicio).total_seconds():.1f}s.")


if __name__ == "__main__":
    main()
