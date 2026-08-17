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
import re
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

# BASE que vai DENTRO do pacote — a mesma que foi processada aqui e entregue a
# ela em 07/08, recuperada do LFS (commit 346059a, de dentro do proprio zip
# entregue). Com ela o pacote e' AUTONOMO: extrair e abrir, sem copiar por cima,
# sem reprocessar, sem depender do que existe na maquina dela.
#
# OPCIONAL de proposito: se o arquivo nao estiver na maquina de build, o pacote
# sai sem base (o modo anterior) em vez de o build quebrar. Ver ORIGEM.txt ao
# lado do arquivo.
BANCO_ENTREGUE = (RAIZ / "Arquivos_origem" / "BANCO_ENTREGUE_BRUNA"
                  / "iam_analytics.db")

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
    # jira.xml.exemplo (modelo) + jira.xml COM a estrutura e SEM a credencial.
    exemplo = EXECS / "CONFIG" / "jira.xml.exemplo"
    if exemplo.exists():
        shutil.copy2(exemplo, execs_destino / "CONFIG" / "jira.xml.exemplo")
        gerar_jira_xml(execs_destino / "CONFIG" / "jira.xml")
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


# Os DOIS campos que nunca viajam preenchidos. O resto da estrutura vai
# completo, para quem for ativar so' precisar colar a credencial.
CREDENCIAL = ("usuario", "token")

CABECALHO_JIRA = """<!--
  ABERTURA DE CHAMADO NO JIRA — preencha os DOIS campos abaixo.

  Esta estrutura ja vem pronta: url, portal, tipo de formulario e campos foram
  apurados na API do Jira e so mudam se a CVC reconfigurar o portal. Falta a
  credencial, que NAO viaja em pacote nenhum — um token num zip e' um token
  vazado.

  FALTAM SO' DUAS LINHAS — todo o resto ja esta configurado:
      <usuario>  e-mail da conta de servico
      <token>    API token dessa conta

  Preencheu as duas, a abertura de chamado esta no ar. Enquanto estiverem
  vazias o botao fica desabilitado sozinho, sem erro na tela.

  A conta deve ser uma CONTA DE SERVICO cadastrada como CLIENTE do portal —
  nunca a conta pessoal de um analista (essa tem perfil de AGENTE). Ela so
  precisa abrir chamado; nao transiciona, nao fecha, nao le dado de outro
  projeto.

  ONDE ESTE ARQUIVO FICA: numa instalacao de rede, o painel le o jira.xml
  DIRETO DA REDE (<raiz>\\EXECUTAVEIS\\CONFIG\\jira.xml), nao da copia local.
  Trocar o token la vale para todos os analistas na proxima abertura do painel,
  sem republicar versao. Em modo local, vale este arquivo aqui.

  Ele e' colocado UMA VEZ e fica: nenhuma atualizacao de versao o sobrescreve.

  CONFERENCIA: abra o visualizador e olhe a linha "Jira" no inicio do log —
  ela diz de onde leu e o que falta.
-->"""


def gerar_jira_xml(destino: Path):
    """Escreve um CONFIG/jira.xml COM a estrutura e SEM a credencial.

    A estrutura sai do proprio .exemplo, que e' a fonte unica dos parametros
    apurados na API (portal 9, tipo 8819, customfield_11936). Redigitar esses
    valores aqui faria os dois divergirem no primeiro ajuste do Jira.

    <ativo> sai TRUE: o pacote e' a entrega final e tudo que da' para deixar
    pronto fica pronto. Nao ha risco nisso — jira_habilitado() exige ativo E
    usuario E token E os tres parametros do portal, entao com a credencial
    vazia o botao nasce desabilitado do mesmo jeito (validado nos 7 cenarios).
    Quem instalar preenche duas linhas e acabou.
    """
    texto = (EXECS / "CONFIG" / "jira.xml.exemplo").read_text(encoding="utf-8")
    # ORDEM IMPORTA: esvaziar os campos ANTES de inserir o cabecalho. O cabecalho
    # cita <usuario>/<token>/<ativo> como exemplo, e uma substituicao depois dele
    # casaria dentro do proprio comentario.
    # [^<]* em vez de .*? : ancora no conteudo da tag e nao atravessa markup —
    # com DOTALL, o casamento ia do exemplo no comentario ate a tag la embaixo,
    # engolindo o fecha-comentario e o <jira> no meio.
    for campo in CREDENCIAL:
        texto = re.sub(rf"<{campo}>[^<]*</{campo}>", f"<{campo}></{campo}>",
                       texto)
    texto = re.sub(r"<ativo>[^<]*</ativo>", "<ativo>true</ativo>", texto,
                   count=1)
    # lambda no replacement: o cabecalho tem barras invertidas, que o re
    # interpretaria como escape.
    texto = re.sub(r"<!--.*?-->", lambda _: CABECALHO_JIRA, texto,
                   count=1, flags=re.S)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(texto, encoding="utf-8")


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
    if BANCO_ENTREGUE.exists():
        shutil.copy2(BANCO_ENTREGUE, raiz / "DADOS" / "BANCO" / "iam_analytics.db")
        print(f"  base embutida: {BANCO_ENTREGUE.stat().st_size/1024/1024:.0f} MB")
    else:
        print(f"  AVISO: sem base ({BANCO_ENTREGUE} nao existe) — "
              f"pacote sai so' com os executaveis.")
    # roteiro de validacao junto do pacote (a usuaria nao tem o repo)
    if ROTEIRO.exists():
        shutil.copy2(ROTEIRO, raiz / "ROTEIRO_VALIDACAO.md")
    for doc in ROTEIRO_REGRAS:
        if doc.exists():
            shutil.copy2(doc, raiz / doc.name)
        else:
            print(f"  AVISO: roteiro de regras ausente, nao vai no pacote: {doc.name}")
    (raiz / "LEIA-ME.txt").write_text(LEIA_ME, encoding="utf-8")


BANCO_NO_PACOTE = "DADOS/BANCO/iam_analytics.db"


def conferir_conteudo(raiz: Path):
    """O que pode e o que nao pode viajar.

    O BANCO pode (e' o ponto do pacote autonomo). A ENTRADA nao: com os arquivos
    de entrada dentro, um clique no Processador reprocessaria e mudaria a base
    que ela esta validando — o oposto de entregar um estado congelado. Fora o
    banco, nada mais em DADOS/: relatorio ou log de outra rodada so' confunde.
    """
    achados = []
    for p in raiz.rglob("*"):
        if not p.is_file():
            continue
        rel = str(p.relative_to(raiz)).replace("\\", "/")
        if rel.startswith("ENTRADA/"):
            achados.append(f"{rel}  (ENTRADA tem de ir vazia)")
        elif rel.startswith("DADOS/") and rel != BANCO_NO_PACOTE:
            achados.append(f"{rel}  (so' o banco pode ir em DADOS/)")
    if achados:
        print("FALHA — o pacote levou o que nao devia:")
        for a in achados:
            print(f"  - {a}")
        shutil.rmtree(STAGING, ignore_errors=True)
        sys.exit(1)


# Sem estes, o painel nao consegue abrir chamado nenhum — sao o motivo de o
# arquivo viajar montado em vez de em branco.
CAMPOS_ESTRUTURA = ("url", "service_desk_id", "request_type_id", "campo_tipo",
                    "tipo_solicitacao", "prefixo_titulo", "timeout_s",
                    "cancelar_apos_abrir", "transicao_cancelamento")


def conferir_jira_sem_credencial(raiz: Path):
    """O jira.xml agora VIAJA — com a estrutura, sem a credencial.

    Confere as tres coisas que podem dar errado, e nesta ordem: o arquivo tem de
    ser XML VALIDO (a geracao mexe no texto com regex — um padrao que atravesse
    markup produz um arquivo que so' falharia na maquina do destinatario), a
    estrutura tem de estar completa (senao viaja um arquivo inutil) e a
    credencial tem de estar VAZIA (o build roda em maquina que pode ter um
    jira.xml preenchido; token em zip nao se recolhe depois de enviado).
    """
    for p in raiz.rglob("jira.xml"):
        rel = str(p.relative_to(raiz)).replace("\\", "/")
        try:
            r = ET.parse(p).getroot()
        except ET.ParseError as e:
            print(f"FALHA — {rel} nao e' XML valido: {e}")
            shutil.rmtree(STAGING, ignore_errors=True)
            sys.exit(1)
        vazios = [c for c in CAMPOS_ESTRUTURA if not (r.findtext(c) or "").strip()]
        if vazios:
            print(f"FALHA — {rel} saiu sem a estrutura: {', '.join(vazios)}")
            shutil.rmtree(STAGING, ignore_errors=True)
            sys.exit(1)
        if r.find("ativo") is None:
            print(f"FALHA — {rel} saiu sem a tag <ativo>.")
            shutil.rmtree(STAGING, ignore_errors=True)
            sys.exit(1)
        for campo in CREDENCIAL:
            if r.find(campo) is None:
                print(f"FALHA — {rel} saiu sem a tag <{campo}>.")
                shutil.rmtree(STAGING, ignore_errors=True)
                sys.exit(1)
            if (r.findtext(campo) or "").strip():
                print(f"FALHA — {rel} saiu com <{campo}> PREENCHIDO. "
                      "Credencial nao entra em pacote.")
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

O PACOTE JA VEM COM A BASE - a MESMA que voce recebeu em 07/08, com os mesmos
numeros. Nao precisa instalar por cima de nada, nao precisa processar, nao
precisa mexer na pasta que voce ja tem.

------------------------------------------------------------
COMO USAR - sao 2 passos
------------------------------------------------------------
1. Extraia a pasta CVC_IAM_ANALYTICS para qualquer lugar do seu PC
   (ex.: C:\\CVC_TESTE\\CVC_IAM_ANALYTICS).

2. Rode
       CVC_IAM_ANALYTICS\\EXECUTAVEIS\\visualizador.exe
   Ele abre http://127.0.0.1:8800/ no navegador. Pronto, e so isso.

NAO RODE O Processador.exe. A base ja vem pronta, e a pasta ENTRADA vem vazia
justamente para nao haver risco de um clique reprocessar e mudar os numeros
que voce esta conferindo.

Esta pasta e INDEPENDENTE: nao toca na versao anterior que voce tem, nao usa a
rede e nao interfere no ambiente do cliente. Se quiser, mantenha as duas e
compare.

------------------------------------------------------------
O QUE MUDOU EM RELACAO AO QUE VOCE JA VIU
------------------------------------------------------------
Os dados sao os mesmos de 07/08. O que mudou foi a TELA - quatro dos seis
pontos do seu retorno aparecem aqui: Consulta unificada por CPF, bloco "Sem
mapeamento", perfis esperados sem repeticao e a coluna Centro de Custo.

Os outros dois (desligado recontratado, que derruba a contagem de 762 para 24
pessoas, e o motivo do status no "?") sao calculados no processamento, nao na
tela - eles entram no proximo ciclo, quando as bases forem reprocessadas.

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
  O arquivo EXECUTAVEIS\\CONFIG\\jira.xml ja vem no pacote com a estrutura
  montada e ja LIGADA - falta so a credencial. Quem for ativar preenche duas
  linhas, <usuario> e <token>, e nada mais. O proprio arquivo explica.

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
    print("=== Build TESTE LOCAL BRUNA (modo local, autonomo, v%s) ===" % VERSAO)
    checar_prerequisitos()
    if STAGING.exists():
        shutil.rmtree(STAGING, ignore_errors=True)
    STAGING.mkdir(parents=True, exist_ok=True)
    ENTREGA.mkdir(parents=True, exist_ok=True)

    inicio = datetime.now()
    montar(STAGING)
    conferir_conteudo(STAGING / "CVC_IAM_ANALYTICS")
    conferir_jira_sem_credencial(STAGING / "CVC_IAM_ANALYTICS")

    alvo = ENTREGA / f"TESTE_LOCAL_BRUNA_v{VERSAO}.zip"
    zipar(STAGING / "CVC_IAM_ANALYTICS", alvo)
    n = len(zipfile.ZipFile(alvo).namelist())
    print(f"\n  OK -> {alvo}  ({alvo.stat().st_size/1024/1024:.1f} MB, {n} itens)")
    banco = "COM banco" if BANCO_ENTREGUE.exists() else "SEM banco"
    print(f"  versao={VERSAO}  raiz=<vazia/local>  {banco}  ENTRADA vazia  "
          f"Jira pronto (falta usuario/token)")
    print()
    print("  INSTRUCAO PARA A BRUNA:")
    print("   1. Extrair CVC_IAM_ANALYTICS/ para qualquer pasta do PC.")
    print("   2. Abrir EXECUTAVEIS/visualizador.exe. So' isso.")
    print("   Pacote AUTONOMO: base ja vem dentro, nao instala por cima de")
    print("   nada, nao roda Processador, nao toca no que ela ja tem.")

    shutil.rmtree(STAGING, ignore_errors=True)
    print(f"\nConcluido em {(datetime.now()-inicio).total_seconds():.1f}s.")


if __name__ == "__main__":
    main()
