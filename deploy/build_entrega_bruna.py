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

# A Bruna NAO roda o Processador: ela so usa o Visualizador (definido em
# 05/08). Entao o pacote leva o BANCO PRONTO e a ENTRADA vai VAZIA — so a
# estrutura de pastas. Sem isso ela abriria o painel num banco inexistente.
# Deixar a ENTRADA populada tambem seria risco: um clique no Processador
# reprocessaria e mudaria a base que ela esta validando.
BANCO_PRONTO = Path(
    r"C:\Users\user\AppData\Local\Temp\claude"
    r"\c--Users-user-OneDrive-Backup-Note-Projetos-Antlia-cvc-CVC"
    r"\34c299f2-b0ec-4b8f-baf4-db3c2f55ef38\scratchpad\bruto"
    r"\CVC_IAM_ANALYTICS\DADOS\BANCO\iam_analytics.db")

LAUNCHER_DIR = EXECS / "launcher"
PRINCIPAL_VISUALIZADOR = EXECS / "visualizador.exe"
PRINCIPAL_PROCESSADOR = EXECS / "Processador.exe"
# Sem LAUNCHER_ATUALIZADOR de proposito — este pacote nao o leva (ver
# montar_executaveis). Nao reintroduzir sem ler a nota de la'.
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
    # (RH ativos CLT: as DUAS cargas datadas vem de Arquivos_origem —
    #  ver ARQUIVOS_ORIGEM e ARQUIVOS_2A_CARGA abaixo.)
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
    # RH ativos CLT — 1a CARGA (17/06). A 2a (01/07) NAO entra na ENTRADA: ver
    # ARQUIVOS_2A_CARGA. Trocamos a antiga "PROJETOIAM (8)" (11/05) por esta
    # serie datada porque as duas cargas precisam ser COMPARAVEIS — (8) x 01/07
    # acusaria mudanca em meio mundo (vintages diferentes), o que e' ruido, nao
    # transferencia. Este par (17/06 -> 01/07) e' o provado: 31 alteracoes no
    # CDC -> 18 pessoas -> 10 com acesso a revisar.
    ("17072026/ENTRADA/RH/ATIVOS/PROCESSADOS/PROJETOIAM_20260617_114249_20260701_142343.CSV",
     "RH/ATIVOS/PROJETOIAM.CSV"),
    # RH desligados (motor de acesso de desligado)
    ("17072026/PROJETOIAMDESLIGADOS (1).CSV",
     "RH/DESLIGADOS/PROJETOIAMDESLIGADOS.CSV"),
    # Diretorio AD por OU — o nome do arquivo e' que roteia a populacao
    # (OU_Franq -> FRANQUEADO, OU_Prest -> PRESTADOR, OU_Desligados -> desligados).
    ("17072026/OU_Franq_Bruna.csv", "RH/AD/OU_Franq_Bruna.csv"),
    ("17072026/OU_Prest_Bruna.csv", "RH/AD/OU_Prest_Bruna.csv"),
    ("17072026/OU_Desligados_Bruna.csv", "RH/AD/OU_Desligados_Bruna.csv"),
]

# 2a CARGA de RH — vai FORA da ENTRADA, numa pasta que o Processador nao varre.
# Motivo (medido): ImportarRh le a pasta inteira e faz UM unico CDC sobre a
# UNIAO dos arquivos (leitor_rh.ler_ativos: `ativos.extend(novos)`). Com as duas
# cargas juntas na ENTRADA, o comparativo seria "uniao x banco vazio" = tudo
# NOVO, ZERO alteracao -> a aba Transferidos nasceria vazia de novo. A 2a carga
# tem de chegar DEPOIS da 1a execucao, exatamente como na operacao real (o
# cliente deposita um snapshot por dia). O LEIA-ME instrui os 2 passos.
PASTA_2A_CARGA = "2a_CARGA_RH"
ARQUIVOS_2A_CARGA = [
    ("17072026/ENTRADA/RH/ATIVOS/PROCESSADOS/PROJETOIAM_20260701_101549_20260701_142346.CSV",
     "PROJETOIAM.CSV"),
]


def checar_prerequisitos():
    # LAUNCHER_ATUALIZADOR NAO entra: ver a nota em montar_executaveis().
    base = [PRINCIPAL_VISUALIZADOR, PRINCIPAL_PROCESSADOR,
            LAUNCHER_VISUALIZADOR, LAUNCHER_PROCESSADOR,
            CONFIG_SRC, MOTIVOS_SRC, REPORT_DIR / "index.html"]
    faltando = [str(p) for p in base if not p.exists()]
    # arquivos de entrada
    for origem, _ in ARQUIVOS_ENTRADA:
        p = ENTRADA_SRC / origem
        if not p.exists():
            faltando.append(str(p))
    for origem, _ in ARQUIVOS_ORIGEM + ARQUIVOS_2A_CARGA:
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
    # launcher_atualizador.exe FICA DE FORA deste pacote, por dois motivos que
    # se somam:
    #
    # 1. E' INUTIL AQUI. Este pacote e' MODO LOCAL (<raiz> vazia): nao existe
    #    rede de onde se atualizar. O atualizador viajava sem funcao nenhuma.
    # 2. O DEFENDER O DERRUBA. Ele da' falso positivo neste exe e o apaga no
    #    meio do build — o zip saia TRUNCADO, e o erro so' aparecia na maquina
    #    do destinatario, na forma de um pacote que nao abre.
    #
    # O pacote de PRODUCAO (build_entrega_prd.py) continua levando o
    # atualizador: la' ele tem funcao, porque ha' rede e auto-update.
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


def montar_2a_carga(raiz: Path):
    """Pasta FORA da ENTRADA (o Processador nao a varre) com o snapshot de RH
    do dia seguinte. So depois da 1a execucao ela vai para a ENTRADA — e' esse
    intervalo que produz o CDC de onde saem os transferidos."""
    dst = raiz / PASTA_2A_CARGA
    dst.mkdir(parents=True, exist_ok=True)
    for origem, destino in ARQUIVOS_2A_CARGA:
        shutil.copy2(ORIGEM_SRC / origem, dst / destino)
    (dst / "LEIA-ME.txt").write_text(LEIA_ME_2A_CARGA, encoding="utf-8")
    return len(ARQUIVOS_2A_CARGA)


ROTEIRO = RAIZ / "docs" / "ROTEIRO_VALIDACAO_TRANSFERIDOS.md"
# Roteiro de REGRAS (docx + pdf): vai na raiz do pacote, junto do LEIA-ME. Ela
# recebe o zip por outro canal que nao o repo — se o documento nao viajar com o
# pacote, chega separado ou nao chega.
ROTEIRO_REGRAS = [
    ENTREGA / f"ROTEIRO_REGRAS_CVC_IAM_v{VERSAO}.docx",
    ENTREGA / f"ROTEIRO_REGRAS_CVC_IAM_v{VERSAO}.pdf",
]


def montar(base: Path):
    raiz = base / "CVC_IAM_ANALYTICS"
    montar_executaveis(raiz / "EXECUTAVEIS")
    # ENTRADA so com a estrutura (ela nao processa) — ver BANCO_PRONTO
    for sub in ENTRADA_SUBDIRS:
        (raiz / "ENTRADA" / sub).mkdir(parents=True, exist_ok=True)
    n = 0
    # roteiro de validacao junto do pacote (a usuaria nao tem o repo)
    if ROTEIRO.exists():
        shutil.copy2(ROTEIRO, raiz / "ROTEIRO_VALIDACAO.md")
    for doc in ROTEIRO_REGRAS:
        if doc.exists():
            shutil.copy2(doc, raiz / doc.name)
        else:
            print(f"  AVISO: roteiro de regras ausente, nao vai no pacote: {doc.name}")
    for sub in DADOS_SUBDIRS:
        (raiz / "DADOS" / sub).mkdir(parents=True, exist_ok=True)
    (raiz / "INTERACOES").mkdir(parents=True, exist_ok=True)
    # BANCO PRONTO — o painel abre direto nele
    if not BANCO_PRONTO.exists():
        print(f"FALHA — banco de entrega ausente:\n  {BANCO_PRONTO}")
        sys.exit(1)
    shutil.copy2(BANCO_PRONTO, raiz / "DADOS" / "BANCO" / "iam_analytics.db")
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


LEIA_ME_2A_CARGA = """\
SEGUNDA CARGA DE RH - para ver a aba TRANSFERIDOS
=================================================

Este PROJETOIAM.CSV e' o snapshot de RH do dia seguinte (01/07). Ele NAO esta
na ENTRADA de proposito.

POR QUE: o sistema descobre quem foi transferido COMPARANDO duas cargas de RH
(mudanca de cargo, centro de custo, departamento ou gestor). Se as duas cargas
entrarem juntas, nao ha "antes" e "depois" — o sistema le tudo como cadastro
novo e a aba Transferidos fica vazia.

COMO USAR (2 passos, e' assim que funciona no dia a dia):

  1. Rode o Processador.exe normalmente (a 1a carga ja esta na ENTRADA).
     Nesse momento a aba Transferidos ainda fica vazia — e' o esperado.

  2. COPIE o PROJETOIAM.CSV desta pasta para
         CVC_IAM_ANALYTICS\\ENTRADA\\RH\\ATIVOS\\
     e rode o Processador.exe DE NOVO.

     Agora a aba Transferidos mostra quem mudou, com o "de -> para" de cada
     movimento (ex.: gestor: FULANO -> CICLANO) e os acessos a revisar.
"""

LEIA_ME = """\
TESTE LOCAL - CVC IAM Analytics (v1.0.0) - pacote da Bruna
==========================================================

Este pacote roda 100%% LOCAL. Ele NAO usa a rede e NAO interfere na versao
que o cliente esta testando (config.xml com <raiz> vazia = modo local; os
executaveis NAO se auto-atualizam da rede).

------------------------------------------------------------
COMO USAR — sao 2 passos
------------------------------------------------------------
1. Extraia a pasta CVC_IAM_ANALYTICS para qualquer lugar do seu PC
   (ex.: C:\\CVC_TESTE\\CVC_IAM_ANALYTICS). NAO precisa estar na rede.

2. Rode
       CVC_IAM_ANALYTICS\\EXECUTAVEIS\\visualizador.exe
   Ele abre http://127.0.0.1:8800/ no navegador. Pronto, e' so isso.

------------------------------------------------------------
POR ONDE COMECAR — o roteiro esta aqui nesta pasta
------------------------------------------------------------
   ROTEIRO_REGRAS_CVC_IAM_v1.0.0.docx   (o mesmo em .pdf)

Ele lista as 22 regras que decidem sozinhas alguma coisa no painel: o criterio
de cada uma (com os limiares), o filtro para conferir na tela e o numero que
deve aparecer. Cada regra tem uma linha para voce responder se ela esta certa.

Os testes provam que o sistema faz o que foi programado. So voce prova que a
REGRA esta certa — e' para isso que o roteiro existe.
As regras marcadas com estrela sao as que mais mudam volume de trabalho; se o
tempo for curto, comece por elas.

VOCE NAO PRECISA RODAR O PROCESSADOR. O banco JA VEM PRONTO no pacote, com
dois meses de dados (junho, julho e agosto/2026) — inclusive o historico de
movimentacoes, que so existe porque varias cargas de RH foram comparadas ao
longo do periodo. E' esse banco que o painel abre.

A pasta ENTRADA vem VAZIA de proposito: nada para processar, e nenhum risco
de um clique no Processador alterar a base que voce esta validando.

O QUE VOCE PODE FAZER A VONTADE: tratar pendencias, resolver, enviar para
quarentena, exportar as planilhas. Tudo o que voce fizer fica gravado na sua
copia local e NAO afeta ninguem — nem a rede, nem a versao do cliente.

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
  * TRANSFERIDOS com "DE -> PARA": ao abrir uma pessoa transferida, a
    primeira linha mostra o que mudou no cadastro (ex.: gestor:
    ANDREIA RIBEIRO SANTOS -> NATHALIA MAQUEA DA SILVA), antes dos acessos
    a revisar — e' esse par que diz se o acesso antigo ainda faz sentido.
    O Excel exportado traz as colunas De/Para.
  * Na aba Aderentes, o selo "N aderencias" tambem abre/fecha os sistemas
    (antes so a coluna "N sistemas" respondia ao clique).
  * REVALIDACAO POS-TRANSFERENCIA: em vez de mandar revisar TODOS os acessos
    de quem foi transferido, o sistema aponta quais deixaram de fazer sentido.
    Cada acesso e' comparado com o que se espera da funcao/equipe NOVA e da
    ANTIGA, e a aba mostra:
       - "N sobraram da anterior" -> candidatos a REVOGAR (o numero acionavel)
       - quantos MANTEM, quantos estao fora do padrao e o que FALTA na nova
    Exemplo real do nosso teste: uma pessoa com 131 acessos no SIG teve 92
    mantidos e 21 apontados como sobra da equipe anterior — em vez de abrir
    os 131 um a um.
    Para os sistemas com matriz o criterio e' a matriz de cargo; para o SIG,
    que nao tem matriz, e' o padrao da EQUIPE (quem trabalha junto), por isso
    a troca de gestor muda o resultado.
  * VISAO GERAL: novo indicador "Acessos p/ Revogar", que leva direto para a
    aba Transferidos.
  * FORMULARIO DE TRATATIVA — regra nova. O nº do ticket do Jira NAO e' mais
    obrigatorio: agora o formulario separa a TRATATIVA DO ANALISTA (motivo e
    parecer, obrigatorios) do CHAMADO NO JIRA (ticket e link, opcionais).
    Assim da para registrar uma tratativa interna sem depender de chamado
    aberto. O botao "Abrir chamado no Jira" aparece DESABILITADO — a abertura
    automatica depende do formulario no Jira e vem depois.
    Na lupa, os dados do chamado aparecem em bloco proprio, somente leitura.
  * Os motivos do combobox nunca mais ficam em branco: se a lista nao puder ser
    lida, a tela usa a lista padrao e AVISA o motivo da falha (antes ficava
    vazia em silencio e travava a resolucao, por ser campo obrigatorio).
- BANCO PRONTO (nao precisa processar): 13.430 pessoas no RH ativo, 29.831
  desligados, 92.794 acessos nos 7 sistemas, 727 movimentacoes de cadastro
  detectadas no periodo e 13.773 acessos a revisar por transferencia.
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
    mb = BANCO_PRONTO.stat().st_size / 1024 / 1024
    print(f"  versao={VERSAO}  raiz=<vazia/local>  ENTRADA=vazia (nao processa)  "
          f"BANCO PRONTO={mb:.0f} MB")

    shutil.rmtree(STAGING, ignore_errors=True)
    print(f"Concluido em {(datetime.now()-inicio).total_seconds():.1f}s.")


if __name__ == "__main__":
    main()
