"""
Monta o pacote de TESTE LOCAL para a Bruna — TESTE_LOCAL_BRUNA_v1.0.0.zip.

Igual ao build de producao, PORÉM:
  - <raiz> VAZIA no config.xml  -> MODO LOCAL: roda em qualquer pasta, NAO
    aponta para a rede, NAO auto-atualiza da rede. Assim NAO sobrepoe nem e'
    sobreposto pela versao que o cliente esta testando na rede.
  - <versao> 1.0.0 (RESET da numeracao para a entrega da Fase 1; o codigo e'
    o mais novo — retorno da Bruna aplicado), distinta da 1.3.1 do cliente.
  - ENTRADA JA POPULADA com os arquivos de entrada de TODOS os sistemas ativos
    hoje no config (SYSTUR, SIGOT, SICA_RA, SICA_ESFERA, IC, SIG, ORACLE_EBS +
    matrizes + CCO + RH ativos). A Bruna so roda o Processador.exe e o banco
    nasce localmente; depois abre o visualizador.exe.
  - SEM banco (DADOS/BANCO vazio) — o banco e' gerado no 1o processamento.

Pre-requisito: exes buildados com o CODIGO ATUAL (deploy/build_all.py).

Uso:
    cd deploy
    python build_entrega_bruna.py
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
ENTRADA_SRC = APP / "ENTRADA"
ORIGEM_SRC = RAIZ / "Arquivos_origem"   # bases que o cliente mandou fora da ENTRADA
ENTREGA = RAIZ / "ENTREGA"
STAGING = RAIZ / "_entrega_bruna_staging"

VERSAO = "1.0.0"
RAIZ_LOCAL = ""  # vazio = MODO LOCAL (nao toca a rede)

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
    "RH/ATIVOS", "RH/DESLIGADOS", "RH/AD",
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

# Arquivos de entrada a embutir: (origem sob ENTRADA_SRC) -> (destino sob ENTRADA staging).
# Pego a versao mais recente de cada base, ja SEM o sufixo _AAAAMMDD_HHMMSS que o
# Processador adiciona ao mover para PROCESSADOS (o Processador re-adiciona ao rodar).
ARQUIVOS_ENTRADA = [
    # RH ativos — FUNCIONARIOS CLT (base principal p/ vinculacao dos acessos).
    # PROJETOIAM tem CPF/Matricula/Nome/Email 100%. SEM ela, os acessos dos
    # sistemas nao acham funcionario e caem em "Usuario Nao Encontrado".
    ("RH/ATIVOS/PROCESSADOS/PROJETOIAM (8)_20260611_091052.CSV",
     "RH/ATIVOS/PROJETOIAM (8).CSV"),
    # RH ativos — TERCEIROS (processar_terceiros=true; validados por espelho).
    ("RH/ATIVOS/PROCESSADOS/QuickReport_1780421571311_20260624_124746.xlsx",
     "RH/ATIVOS/QuickReport_1780421571311.xlsx"),
    # Mapeamento organizacional (CCO/CSC)
    ("MATRIZES/ORGANIZACIONAL/PROCESSADOS/Mapeamento CCO_CSC (1)_20260617_173820.xlsx",
     "MATRIZES/ORGANIZACIONAL/Mapeamento CCO_CSC (1).xlsx"),
    # Matrizes de perfil por sistema
    ("MATRIZES/PERFIS_SISTEMAS/PROCESSADOS/MATRIZ DE PERFIL DE ACESSO - SIGOT_20260617_173818.xlsx",
     "MATRIZES/PERFIS_SISTEMAS/MATRIZ DE PERFIL DE ACESSO - SIGOT.xlsx"),
    ("MATRIZES/PERFIS_SISTEMAS/PROCESSADOS/MATRIZ DE PERFIL DE ACESSO ORACLE EBS_20260625_102527.xlsx",
     "MATRIZES/PERFIS_SISTEMAS/MATRIZ DE PERFIL DE ACESSO ORACLE EBS.xlsx"),
    ("MATRIZES/PERFIS_SISTEMAS/PROCESSADOS/MATRIZ DE PERFIL DE ACESSO SICA ESFERA_20260624_145358.xlsx",
     "MATRIZES/PERFIS_SISTEMAS/MATRIZ DE PERFIL DE ACESSO SICA ESFERA.xlsx"),
    ("MATRIZES/PERFIS_SISTEMAS/PROCESSADOS/MATRIZ DE PERFIL DE ACESSO SICA RA_20260617_173818.xlsx",
     "MATRIZES/PERFIS_SISTEMAS/MATRIZ DE PERFIL DE ACESSO SICA RA.xlsx"),
    ("MATRIZES/PERFIS_SISTEMAS/PROCESSADOS/MATRIZ DE PERFIL DE ACESSO SYSTUR_20260617_173819.xlsx",
     "MATRIZES/PERFIS_SISTEMAS/MATRIZ DE PERFIL DE ACESSO SYSTUR.xlsx"),
    ("MATRIZES/PERFIS_SISTEMAS/PROCESSADOS/Matriz de Perfil de Acessso - IC Integrador Contabil_20260617_173819.xlsx",
     "MATRIZES/PERFIS_SISTEMAS/Matriz de Perfil de Acessso - IC Integrador Contabil.xlsx"),
    # SIG de-para (sem timestamp — fica no lugar)
    ("MATRIZES/PERFIS_SISTEMAS/SIG/DE_PARA/ID_x_Perfis_SIG 19.08.xlsx",
     "MATRIZES/PERFIS_SISTEMAS/SIG/DE_PARA/ID_x_Perfis_SIG 19.08.xlsx"),
    # Extratos por sistema
    ("SISTEMAS/SIGOT/PROCESSADOS/SIGOT_30_04_20260617_173821.csv",
     "SISTEMAS/SIGOT/SIGOT_30_04.csv"),
    ("SISTEMAS/SICA_RA/PROCESSADOS/SICA_RA_30_04_20260617_173821.csv",
     "SISTEMAS/SICA_RA/SICA_RA_30_04.csv"),
    ("SISTEMAS/SICA_ESFERA/PROCESSADOS/SICA_ESFERA_24_06_20260624_145358.csv",
     "SISTEMAS/SICA_ESFERA/SICA_ESFERA_24_06.csv"),
    ("SISTEMAS/SYSTUR/PROCESSADOS/relatorio systur 30.04_20260617_173827.xlsx",
     "SISTEMAS/SYSTUR/relatorio systur 30.04.xlsx"),
    ("SISTEMAS/IC/PROCESSADOS/relatorio IC 30.04_20260617_173827.xlsx",
     "SISTEMAS/IC/relatorio IC 30.04.xlsx"),
    ("SISTEMAS/ORACLE_EBS/PROCESSADOS/EXTRACAO_USUARIOS_Oracle 09.06.2026 (1)_20260625_102537.xlsx",
     "SISTEMAS/ORACLE_EBS/EXTRACAO_USUARIOS_Oracle 09.06.2026 (1).xlsx"),
    ("SISTEMAS/SIG/PROCESSADOS/SIG_18.05.26_20260622_161322.xlsx",
     "SISTEMAS/SIG/SIG_18.05.26.xlsx"),
]

# Bases que nunca passaram pela ENTRADA de dev (chegaram via git em Arquivos_origem).
# O config de hoje EXIGE as duas: <rh><desligados><processar>true e
# <rh><diretorio_ad><processar>true. Sem elas o pacote roda, mas a aba Desligados
# nasce vazia e o AD grava "0 identidades" — a Bruna nao reproduziria esta rodada
# (orfaos com dono pelo login, desligados achados pelo AD, espelho franq/prest).
# Origem: (caminho sob Arquivos_origem) -> (destino sob ENTRADA staging).
ARQUIVOS_ORIGEM = [
    # RH desligados (motor de acesso de desligado)
    ("17072026/PROJETOIAMDESLIGADOS (1).CSV",
     "RH/DESLIGADOS/PROJETOIAMDESLIGADOS.CSV"),
    # Diretorio AD por OU — o nome do arquivo e' que roteia a populacao
    # (OU_Franq -> FRANQUEADO, OU_Prest -> PRESTADOR, OU_Desligados -> desligados).
    ("17072026/OU_Franq_Bruna.csv", "RH/AD/OU_Franq_Bruna.csv"),
    ("17072026/OU_Prest_Bruna.csv", "RH/AD/OU_Prest_Bruna.csv"),
    ("17072026/OU_Desligados_Bruna.csv", "RH/AD/OU_Desligados_Bruna.csv"),
]


def checar_prerequisitos():
    base = [PRINCIPAL_VISUALIZADOR, PRINCIPAL_PROCESSADOR,
            LAUNCHER_ATUALIZADOR, LAUNCHER_VISUALIZADOR, LAUNCHER_PROCESSADOR,
            CONFIG_SRC, MOTIVOS_SRC, REPORT_DIR / "index.html"]
    faltando = [str(p) for p in base if not p.exists()]
    # arquivos de entrada
    for origem, _ in ARQUIVOS_ENTRADA:
        p = ENTRADA_SRC / origem
        if not p.exists():
            faltando.append(str(p))
    for origem, _ in ARQUIVOS_ORIGEM:
        p = ORIGEM_SRC / origem
        if not p.exists():
            faltando.append(str(p))
    if faltando:
        print("FALHA — arquivos ausentes:")
        for f in faltando:
            print(f"  - {f}")
        print("\nRode 'python deploy/build_all.py' e confira os arquivos de ENTRADA.")
        sys.exit(1)


def grava_config(destino: Path, versao: str, raiz_valor: str):
    tree = ET.parse(CONFIG_SRC)
    root = tree.getroot()
    n_v = root.find("versao")
    if n_v is not None:
        n_v.text = versao
    n_r = root.find("rede/raiz")
    if n_r is not None:
        n_r.text = raiz_valor or None  # None -> <raiz /> (modo local)
    destino.parent.mkdir(parents=True, exist_ok=True)
    tree.write(destino, encoding="UTF-8", xml_declaration=True)


def montar_executaveis(execs_destino: Path):
    execs_destino.mkdir(parents=True, exist_ok=True)
    launcher_d = execs_destino / "launcher"
    launcher_d.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PRINCIPAL_VISUALIZADOR, execs_destino / "visualizador.exe")
    shutil.copy2(PRINCIPAL_PROCESSADOR, execs_destino / "Processador.exe")
    if LEIA_ME_EXECS.exists():
        shutil.copy2(LEIA_ME_EXECS, execs_destino / "LEIA-ME.md")
    shutil.copytree(REPORT_DIR, execs_destino / "REPORT", dirs_exist_ok=True)
    grava_config(execs_destino / "CONFIG" / "config.xml", VERSAO, RAIZ_LOCAL)
    if MOTIVOS_SRC.exists():
        shutil.copy2(MOTIVOS_SRC, execs_destino / "CONFIG" / "motivos_resolucao.xml")
    shutil.copy2(LAUNCHER_ATUALIZADOR, launcher_d / "launcher_atualizador.exe")
    shutil.copy2(LAUNCHER_VISUALIZADOR, launcher_d / "launcher_visualizador.exe")
    shutil.copy2(LAUNCHER_PROCESSADOR, launcher_d / "launcher_processador.exe")


def montar_entrada(raiz: Path):
    # estrutura completa (mesmo as vazias)
    for sub in ENTRADA_SUBDIRS:
        (raiz / "ENTRADA" / sub).mkdir(parents=True, exist_ok=True)
    # arquivos de entrada de-timestampados
    n = 0
    for base, lista in ((ENTRADA_SRC, ARQUIVOS_ENTRADA), (ORIGEM_SRC, ARQUIVOS_ORIGEM)):
        for origem, destino in lista:
            dst = raiz / "ENTRADA" / destino
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(base / origem, dst)
            n += 1
    return n


def montar(base: Path):
    raiz = base / "CVC_IAM_ANALYTICS"
    montar_executaveis(raiz / "EXECUTAVEIS")
    n = montar_entrada(raiz)
    for sub in DADOS_SUBDIRS:
        (raiz / "DADOS" / sub).mkdir(parents=True, exist_ok=True)
    (raiz / "INTERACOES").mkdir(parents=True, exist_ok=True)
    (raiz / "LEIA-ME.txt").write_text(LEIA_ME, encoding="utf-8")
    return n


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
TESTE LOCAL - CVC IAM Analytics (v1.0.0) - pacote da Bruna
==========================================================

Este pacote roda 100%% LOCAL. Ele NAO usa a rede e NAO interfere na versao
que o cliente esta testando (config.xml com <raiz> vazia = modo local; os
executaveis NAO se auto-atualizam da rede).

------------------------------------------------------------
COMO USAR
------------------------------------------------------------
1. Extraia a pasta CVC_IAM_ANALYTICS para qualquer lugar do seu PC
   (ex.: C:\\CVC_TESTE\\CVC_IAM_ANALYTICS). NAO precisa estar na rede.

2. Gere o banco (1a vez): rode
       CVC_IAM_ANALYTICS\\EXECUTAVEIS\\Processador.exe
   Os arquivos de entrada JA vem posicionados em ENTRADA\\. Ao terminar,
   o banco DADOS\\BANCO\\iam_analytics.db e' criado e os arquivos lidos
   vao para PROCESSADOS.

   >> REAPROVEITAR UMA BASE EXISTENTE (opcional):
      Se ja tiver um iam_analytics.db de um teste anterior, copie-o para
      CVC_IAM_ANALYTICS\\DADOS\\BANCO\\ ANTES de rodar o Processador. O
      Processador novo e' ADITIVO/NAO-DESTRUTIVO: ele apenas CRIA a nova
      tabela de eventos (ciclo_eventos_acesso) e a preenche a partir do
      historico ja existente — NAO apaga nem altera os dados anteriores
      (validacoes, ciclos, resolucoes e quarentenas ficam intactos).

3. Abra o painel: rode
       CVC_IAM_ANALYTICS\\EXECUTAVEIS\\visualizador.exe
   Ele abre http://127.0.0.1:8800/ no navegador, lendo o banco local.

------------------------------------------------------------
O QUE VEM DENTRO
------------------------------------------------------------
- Sistemas ativos: SYSTUR, SIGOT, SICA_RA, SICA_ESFERA, IC, SIG, ORACLE_EBS
  + terceiros (mesma configuracao de dev de hoje).
- Novidades desta versao (retorno da Bruna sobre o teste da Fase 1):
  * "SEM ACESSO" DEIXOU DE SER PENDENCIA. Quando a pessoa nao tem acesso
    num sistema, os perfis esperados do cargo NAO inflam mais a Pendencia
    (era o caso do SIGOT com 8 perfis e do SICA com +22). Eles aparecem
    como "esperado" na Consulta.
  * CONSULTA EM 4 BLOCOS: Acessos ENCONTRADOS (o que a pessoa de fato tem),
    ESPERADOS (o que o cargo preve e ela nao tem), NECESSITA ANALISE
    (perfil a mais / excesso) e NAO LOCALIZADOS (sistema fora da matriz).
  * TRATAMENTO GRANULAR: da para tratar e quarentenar POR SISTEMA e ate
    POR ACESSO (perfil) — nao e' mais tudo de uma vez. Os botoes agora vem
    ROTULADOS na sub-linha ("tratar <SISTEMA>", "tratar acesso",
    "quarentena"), e o filtro por sistema ISOLA de fato o sistema escolhido.
    A aba Quarentena mostra o ESCOPO de cada envio (pessoa / sistema / acesso).
  * COLUNA GESTOR nas grids e na Consulta.
  * DESLIGADOS e TRANSFERIDOS agrupam os acessos POR SISTEMA (antes vinham
    corridos — o caso dos 122 acessos numa linha so). O Excel exportado
    reproduz o mesmo agrupamento (+/-).
  * O STATUS DA CONTA MANDA: conta BLOQUEADA/INATIVA deixou de contar como
    acesso, e status vazio (ou "P" no IC) vai para "Em Analise" em vez de
    ser assumido como ativo. No nosso reprocesso de teste isso derrubou os
    "Usuario Nao Encontrado" de 2.631 para 99 e as pessoas com pendencia de
    792 para 461 — os numeros da sua base podem diferir.
  * IDENTIDADE: franqueados e prestadores do AD entram na base, e o acesso
    orfao agora mostra o perfil que veio do extrato.
  * Os filtros (funil) de cada coluna passaram a listar exatamente os
    valores que estao na grid — antes ofereciam valores de fora dela.
- SEM banco pronto: o banco nasce no 1o processamento (passo 2), ou
  reaproveite um banco anterior (ver passo 2).
"""


def main():
    print("=== Build TESTE LOCAL BRUNA (modo local, v%s) ===" % VERSAO)
    checar_prerequisitos()
    if STAGING.exists():
        shutil.rmtree(STAGING, ignore_errors=True)
    STAGING.mkdir(parents=True, exist_ok=True)
    ENTREGA.mkdir(parents=True, exist_ok=True)

    inicio = datetime.now()
    n = montar(STAGING)

    alvo = ENTREGA / f"TESTE_LOCAL_BRUNA_v{VERSAO}.zip"
    zipar(STAGING / "CVC_IAM_ANALYTICS", alvo)
    print(f"\n  OK -> {alvo}  ({alvo.stat().st_size/1024/1024:.1f} MB)")
    print(f"  versao={VERSAO}  raiz=<vazia/local>  ENTRADA={n} arquivos  DADOS=sem banco")

    shutil.rmtree(STAGING, ignore_errors=True)
    print(f"Concluido em {(datetime.now()-inicio).total_seconds():.1f}s.")


if __name__ == "__main__":
    main()
