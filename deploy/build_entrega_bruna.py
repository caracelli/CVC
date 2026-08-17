"""
Monta o pacote de teste da Bruna — TESTE_LOCAL_BRUNA_v1.0.0.zip.

E' A ENTREGA DA FASE 1, NAO UM UPDATE (decidido em 17/08/2026). Por isso a
numeracao inicial, 1.0.0. O pacote leva os executaveis, a estrutura de pastas e
os roteiros de validacao.

SEM BASE, DE PROPOSITO. Nao traz banco nem arquivos de entrada: e' aplicado POR
CIMA da instalacao que ela ja tem (pacote de 07/08) e usa o banco e as bases que
ja estao la'. Ate 14/08 este build embutia um banco pronto, e o LEIA-ME dizia
"voce nao precisa rodar o Processador" — isso servia enquanto a premissa era que
ela so' usaria o Visualizador. O que muda agora esta' na fase de ANALISE, e
mandar banco pronto substituiria o trabalho que ela ja' registrou.

  - <raiz> VAZIA no config.xml -> MODO LOCAL: roda em qualquer pasta, NAO aponta
    para a rede, NAO auto-atualiza. Nao sobrepoe nem e' sobreposto pela versao
    que o cliente esta' testando na rede.
  - SEM banco e SEM ENTRADA populada. Os arquivos do cliente nao sao versionados
    (em 14/08 faltavam 16 nesta maquina) e ela ja' os tem.
  - DADOS/ e INTERACOES/ vao como pastas VAZIAS: numa copia por cima elas nao
    apagam nada, e numa instalacao nova criam a estrutura.

NAO USAR O build_update_bruna.py para esta entrega: aquele empacota a mesma
EXECUTAVEIS/ como update 1.1.1, sem os roteiros. Foi descartado em 17/08.

DEPOIS DE APLICAR, ELA PRECISA RODAR O Processador.exe UMA VEZ. Sem isso os
numeros da tela continuam os antigos: os 6 ajustes agem na fase de ANALISE, nao
na importacao. E' o reprocessamento que faz os 762 desligados recontratados
virarem 24.

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
ENTREGA = RAIZ / "ENTREGA"
STAGING = RAIZ / "_entrega_bruna_staging"

# 1.0.0 = a VERSAO INICIAL da Fase 1 (decidido em 17/08/2026). Este pacote nao
# e' um update: e' a entrega, com numeracao propria da Fase 1 e distinta da linha
# de producao (1.4.x). Em modo local nao ha auto-update, entao a versao e' rotulo
# — nenhum exe compara numero com a rede.
VERSAO = "1.0.0"
RAIZ_LOCAL = ""          # vazio = MODO LOCAL (nao toca a rede)
VERSAO_ROTEIRO = "1.0.0"  # o roteiro de REGRAS acompanha a numeracao do pacote

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

ROTEIRO = RAIZ / "docs" / "ROTEIRO_VALIDACAO_TRANSFERIDOS.md"
# Roteiro de REGRAS (docx + pdf): vai na raiz do pacote, junto do LEIA-ME. Ela
# recebe o zip por outro canal que nao o repo — se o documento nao viajar com o
# pacote, chega separado ou nao chega.
ROTEIRO_REGRAS = [
    ENTREGA / f"ROTEIRO_REGRAS_CVC_IAM_v{VERSAO_ROTEIRO}.docx",
    ENTREGA / f"ROTEIRO_REGRAS_CVC_IAM_v{VERSAO_ROTEIRO}.pdf",
]


def checar_prerequisitos():
    """So' os artefatos de BUILD. Este pacote nao leva dado, entao nao exige
    nenhum arquivo do cliente — era isso que travava o build nesta maquina."""
    # LAUNCHER_ATUALIZADOR NAO entra: ver a nota em montar_executaveis().
    base = [PRINCIPAL_VISUALIZADOR, PRINCIPAL_PROCESSADOR,
            LAUNCHER_VISUALIZADOR, LAUNCHER_PROCESSADOR,
            CONFIG_SRC, MOTIVOS_SRC, REPORT_DIR / "index.html"]
    faltando = [str(p) for p in base if not p.exists()]
    if faltando:
        print("FALHA — arquivos ausentes:")
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
    # jira.xml.exemplo viaja (e' modelo, nao credencial); jira.xml NUNCA.
    exemplo = EXECS / "CONFIG" / "jira.xml.exemplo"
    if exemplo.exists():
        shutil.copy2(exemplo, execs_destino / "CONFIG" / "jira.xml.exemplo")
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


def montar(base: Path):
    raiz = base / "CVC_IAM_ANALYTICS"
    montar_executaveis(raiz / "EXECUTAVEIS")
    # ENTRADA so' com a estrutura: o pacote nao leva dado, as bases dela ficam
    # onde estao. Pasta vazia numa copia por cima nao apaga arquivo nenhum.
    for sub in ENTRADA_SUBDIRS:
        (raiz / "ENTRADA" / sub).mkdir(parents=True, exist_ok=True)
    for sub in DADOS_SUBDIRS:
        (raiz / "DADOS" / sub).mkdir(parents=True, exist_ok=True)
    (raiz / "INTERACOES").mkdir(parents=True, exist_ok=True)
    # roteiro de validacao junto do pacote (a usuaria nao tem o repo)
    if ROTEIRO.exists():
        shutil.copy2(ROTEIRO, raiz / "ROTEIRO_VALIDACAO.md")
    for doc in ROTEIRO_REGRAS:
        if doc.exists():
            shutil.copy2(doc, raiz / doc.name)
        else:
            print(f"  AVISO: roteiro de regras ausente, nao vai no pacote: {doc.name}")
    (raiz / "LEIA-ME.txt").write_text(LEIA_ME, encoding="utf-8")


def conferir_sem_base(raiz: Path):
    """O pacote nao pode levar dado. Um banco ou uma base que escape substitui o
    trabalho que ela ja' registrou — e o erro so' apareceria na maquina dela."""
    achados = []
    for p in raiz.rglob("*"):
        if not p.is_file():
            continue
        rel = str(p.relative_to(raiz)).replace("\\", "/")
        if p.suffix.lower() == ".db" or rel.startswith("DADOS/"):
            achados.append(rel)
        elif rel.startswith("ENTRADA/"):
            achados.append(rel)
        elif p.name == "jira.xml":
            achados.append(rel)
    if achados:
        print("FALHA — o pacote deveria ir SEM base, mas levou:")
        for a in achados:
            print(f"  - {a}")
        shutil.rmtree(STAGING, ignore_errors=True)
        sys.exit(1)


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
CVC IAM Analytics - Fase 1 - v1.0.0 - pacote da Bruna
=====================================================

Este e o pacote de teste da Fase 1. Ele roda 100% LOCAL: NAO usa a rede e NAO
interfere na versao que o cliente esta testando (config.xml com <raiz> vazia =
modo local; os executaveis nao se auto-atualizam da rede).

ESTE PACOTE NAO TEM BASE. Ele nao traz banco nem arquivos de entrada, de
proposito: voce ja tem tudo isso na sua maquina, e o pacote e aplicado POR CIMA.
Assim o que voce ja tratou, resolveu ou mandou para quarentena CONTINUA LA.

------------------------------------------------------------
COMO INSTALAR - sao 4 passos
------------------------------------------------------------
1. FECHE o painel e o Processador, se estiverem abertos.

2. Extraia este zip e copie a pasta CVC_IAM_ANALYTICS POR CIMA da sua pasta
   atual, mandando SUBSTITUIR os arquivos repetidos.
   NAO apague nada. As pastas DADOS e INTERACOES vem vazias aqui - elas nao
   apagam nem substituem o que voce ja tem.

3. RODE O Processador.exe UMA VEZ. Este passo e OBRIGATORIO.
   As regras desta versao agem na hora da ANALISE, nao na importacao: sem
   reprocessar, a tela continua mostrando os numeros antigos.

4. Abra o visualizador.exe. Ele abre http://127.0.0.1:8800/ no navegador.

------------------------------------------------------------
OS NUMEROS VAO MUDAR - e e esperado
------------------------------------------------------------
A regra dos desligados recontratados muda a contagem por ordem de grandeza:
762 pessoas passam a 24. Consulta, dedup de perfis e as colunas da grid tambem
mudam. Se voce tiver roteiro, print ou planilha feitos sobre o pacote anterior,
eles ficam desatualizados.

------------------------------------------------------------
OS SEIS PONTOS DO SEU RETORNO - como ficaram
------------------------------------------------------------
A) DESLIGADO RECONTRATADO. Quem foi desligado e recontratado com o MESMO login
   nao e mais apontado; so aparece quem voltou com login DIFERENTE. E a regra
   que leva 762 pessoas para 24.
B) CONSULTA UNIFICADA POR CPF. A mesma pessoa com mais de um cadastro aparece
   uma vez so. As tratativas que voce ja registrou seguem ligadas ao acesso
   original.
C) BLOCO "SEM MAPEAMENTO" no detalhe da Consulta, separando o que nao tem
   correspondencia na matriz.
D) PERFIS ESPERADOS SEM REPETICAO, na grid e no Excel exportado.
E) MOTIVO DO STATUS: quando um acesso e rebaixado por status indefinido, o
   porque aparece no "?" ao lado do selo.
F) COLUNA CENTRO DE CUSTO na grid de Pendencias.

Mais dois pontos que valem saber:
- Os motivos do combobox nunca ficam em branco: se a lista nao puder ser lida,
  a tela usa a lista padrao e AVISA o motivo da falha (em vez de ficar vazia em
  silencio e travar a resolucao, por ser campo obrigatorio).
- O botao "Abrir chamado no Jira" aparece DESABILITADO. A abertura automatica
  ja esta pronta, mas depende de dois ajustes do lado do Jira que a CVC vai
  fazer; ate la o registro da tratativa continua manual, como hoje.

------------------------------------------------------------
POR ONDE COMECAR - o roteiro esta aqui nesta pasta
------------------------------------------------------------
   ROTEIRO_REGRAS_CVC_IAM_v1.0.0.docx   (o mesmo em .pdf)

Ele lista as 22 regras que decidem sozinhas alguma coisa no painel: o criterio
de cada uma (com os limiares), o filtro para conferir na tela e o numero que
deve aparecer. Cada regra tem uma linha para voce responder se ela esta certa.
As regras marcadas com estrela sao as que mais mudam volume de trabalho; se o
tempo for curto, comece por elas.

Os testes provam que o sistema faz o que foi programado. So voce prova que a
REGRA esta certa - e para isso que o roteiro existe.

Alguns numeros do roteiro podem nao bater com a tela por causa dos seis pontos
acima - em especial o dos desligados recontratados. Quando nao bater, e a regra
corrigida agindo, nao um erro do roteiro.

------------------------------------------------------------
O QUE VOCE PODE FAZER A VONTADE
------------------------------------------------------------
Tratar pendencias, resolver, enviar para quarentena, exportar as planilhas.
Tudo o que voce fizer fica gravado na sua copia local e NAO afeta ninguem - nem
a rede, nem a versao do cliente.

Sistemas ativos: SYSTUR, SIGOT, SICA_RA, SICA_ESFERA, IC, SIG, ORACLE_EBS
+ terceiros.
"""


def main():
    print("=== Build TESTE LOCAL BRUNA (modo local, SEM base, v%s) ===" % VERSAO)
    checar_prerequisitos()
    if STAGING.exists():
        shutil.rmtree(STAGING, ignore_errors=True)
    STAGING.mkdir(parents=True, exist_ok=True)
    ENTREGA.mkdir(parents=True, exist_ok=True)

    inicio = datetime.now()
    montar(STAGING)
    conferir_sem_base(STAGING / "CVC_IAM_ANALYTICS")

    alvo = ENTREGA / f"TESTE_LOCAL_BRUNA_v{VERSAO}.zip"
    zipar(STAGING / "CVC_IAM_ANALYTICS", alvo)
    n = len(zipfile.ZipFile(alvo).namelist())
    print(f"\n  OK -> {alvo}  ({alvo.stat().st_size/1024/1024:.1f} MB, {n} itens)")
    print(f"  versao={VERSAO}  raiz=<vazia/local>  SEM banco  SEM ENTRADA")
    print()
    print("  INSTRUCAO PARA A BRUNA:")
    print("   1. Fechar o painel e o Processador, se estiverem abertos.")
    print("   2. Extrair e copiar CVC_IAM_ANALYTICS/ POR CIMA da pasta atual,")
    print("      substituindo os repetidos. NAO apagar DADOS/ nem INTERACOES/.")
    print("   3. Rodar o Processador.exe UMA VEZ (obrigatorio — e' ele que")
    print("      aplica as regras novas; sem isso os numeros ficam os antigos).")
    print("   4. Abrir o visualizador.exe.")

    shutil.rmtree(STAGING, ignore_errors=True)
    print(f"\nConcluido em {(datetime.now()-inicio).total_seconds():.1f}s.")


if __name__ == "__main__":
    main()
