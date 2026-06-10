"""
Monta o pacote ENTREGA_REDE.zip — teste end-to-end da arquitetura
multiusuario apontando para o caminho de rede Z:\\CVC\\CVC_IAM_ANALYTICS.

Conteudo:
  ENTREGA_REDE/
    LEIA-ME.txt
    REDE/                              -> vai para Z:\\CVC\\
      CVC_IAM_ANALYTICS/...            (exes + ENTRADA com arquivos prontos,
                                        DADOS/BANCO VAZIO — cliente roda o
                                        Processador para gerar o iam_analytics.db)
    CLIENTE/                           -> vai para C:\\CVC\\ de cada usuario
      CVC_VISUALIZADOR/
        visualizador.exe + visualizador.py + CONFIG/ + REPORT/ + LEIA-ME.md
    ATUALIZACAO/                       -> para demonstrar o auto-update
      CVC_IAM_ANALYTICS/EXECUTAVEIS/CONFIG/config.xml   (versao 1.0.1)

Pre-requisito: rodar build_processador.py e build_visualizador.py antes.

Uso:
    cd deploy
    python build_entrega_rede.py
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
STAGING = RAIZ / "_entrega_rede_staging"

# Os 5 exes da arquitetura v2.0+
LAUNCHER_DIR = EXECS / "launcher"
PRINCIPAL_VISUALIZADOR = EXECS / "visualizador.exe"
PRINCIPAL_PROCESSADOR = EXECS / "Processador.exe"
LAUNCHER_ATUALIZADOR = LAUNCHER_DIR / "launcher_atualizador.exe"
LAUNCHER_VISUALIZADOR = LAUNCHER_DIR / "launcher_visualizador.exe"
LAUNCHER_PROCESSADOR = LAUNCHER_DIR / "launcher_processador.exe"
REPORT_DIR = EXECS / "REPORT"
CONFIG_SRC = EXECS / "CONFIG" / "config.xml"
LEIA_ME_EXECS = EXECS / "LEIA-ME.md"
ARQUIVOS_ORIGEM = RAIZ / "Arquivos_origem"

# (origem em Arquivos_origem) -> (subpasta dentro de CVC_IAM_ANALYTICS/ENTRADA)
#
# ESCOPO FASE 1 = SYSTUR (inclusao/alteracao). A ENTRADA da entrega leva SO os
# 4 arquivos necessarios para esse fluxo: RH ativos + Mapeamento CCO/CSC +
# matriz SYSTUR + extrato SYSTUR. Qualquer outro arquivo (desligados, terceiros,
# outros sistemas) fica FORA do pacote — e o motor tambem os ignora por config
# (rh/desligados/processar=false, rh/ativos/processar_terceiros=false, e os
# sistemas fora de escopo com ativo=false). Para reativar numa proxima fase,
# descomentar a linha correspondente abaixo.
ENTRADA_ARQUIVOS = [
    ("PROJETOIAM (8).CSV",                                       "RH/ATIVOS"),
    ("Mapeamento CCO_CSC (1).xlsx",                              "MATRIZES/ORGANIZACIONAL"),
    ("MATRIZ DE PERFIL DE ACESSO SYSTUR.xlsx",                   "MATRIZES/PERFIS_SISTEMAS"),
    ("relatorio systur 30.04.xlsx",                              "SISTEMAS/SYSTUR"),
    # IC (Integrador Contabil) — em escopo: matriz + extrato. O perfil casa por
    # aproximacao (extrato usa '_', matriz usa espaco). Sistema ativo=true no config.
    ("Matriz de Perfil de Acessso - IC Integrador Contabil.xlsx", "MATRIZES/PERFIS_SISTEMAS"),
    ("relatorio IC 30.04.xlsx",                                  "SISTEMAS/IC"),
    # --- FORA de escopo (descomentar quando a fase respectiva entrar) ---
    # Terceiros (QuickReport): so quando a regra de espelho for definida.
    #   ("RH/ATIVOS/QuickReport_1780421571311.xlsx",            "RH/ATIVOS"),
    # Desligados: fluxo de revogacao, fase separada.
    #   ("PROJETOIAMDESLIGADOS (2).CSV",                         "RH/DESLIGADOS"),
    # Outros sistemas (matrizes + extratos): fora de escopo.
    #   ("MATRIZ DE PERFIL DE ACESSO - SIGOT.xlsx",              "MATRIZES/PERFIS_SISTEMAS"),
    #   ("MATRIZ DE PERFIL DE ACESSO SICA ESFERA.xlsx",          "MATRIZES/PERFIS_SISTEMAS"),
    #   ("MATRIZ DE PERFIL DE ACESSO SICA RA.xlsx",              "MATRIZES/PERFIS_SISTEMAS"),
    #   ("SIGOT_30_04.csv",                                      "SISTEMAS/SIGOT"),
    #   ("SICA_RA_30_04.csv",                                    "SISTEMAS/SICA_RA"),
]

RAIZ_REDE = r"Z:\CVC\CVC_IAM_ANALYTICS"
VERSAO_INICIAL = "1.1.1"     # MAJOR.PROCESSADOR.VISUALIZADOR (ciclo de vida + casamento por gestor + processados por pasta)
VERSAO_NOVA = "1.1.1"        # entrega: Processador (migracoes/ciclo/gestor) + Visualizador (painel)

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
    base = [PRINCIPAL_VISUALIZADOR, PRINCIPAL_PROCESSADOR,
            LAUNCHER_ATUALIZADOR, LAUNCHER_VISUALIZADOR, LAUNCHER_PROCESSADOR,
            CONFIG_SRC, REPORT_DIR / "index.html"]
    arq_orig = [ARQUIVOS_ORIGEM / nome for nome, _ in ENTRADA_ARQUIVOS]
    faltando = [str(p) for p in base + arq_orig if not p.exists()]
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
        n_r.text = raiz_valor
    destino.parent.mkdir(parents=True, exist_ok=True)
    tree.write(destino, encoding="UTF-8", xml_declaration=True)


def _montar_executaveis_servidor_sem_motor(execs_destino: Path, versao: str):
    """Monta EXECUTAVEIS/ do servidor MENOS o launcher_processador (motor
    grande, ~80 MB, vai num zip separado pra ficar < 100 MB do GitHub)."""
    execs_destino.mkdir(parents=True, exist_ok=True)
    launcher_d = execs_destino / "launcher"
    launcher_d.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PRINCIPAL_VISUALIZADOR, execs_destino / "visualizador.exe")
    shutil.copy2(PRINCIPAL_PROCESSADOR, execs_destino / "Processador.exe")
    shutil.copy2(LEIA_ME_EXECS, execs_destino / "LEIA-ME.md")
    shutil.copytree(REPORT_DIR, execs_destino / "REPORT", dirs_exist_ok=True)
    grava_config(execs_destino / "CONFIG" / "config.xml", versao, RAIZ_REDE)
    shutil.copy2(LAUNCHER_ATUALIZADOR, launcher_d / "launcher_atualizador.exe")
    shutil.copy2(LAUNCHER_VISUALIZADOR, launcher_d / "launcher_visualizador.exe")
    # launcher_processador.exe NAO entra aqui; vai no ENTREGA_REDE_motor.zip


def _montar_motor_separado(base: Path):
    """REDE/CVC_IAM_ANALYTICS/EXECUTAVEIS/launcher/launcher_processador.exe."""
    destino = (base / "CVC_IAM_ANALYTICS" / "EXECUTAVEIS"
               / "launcher" / "launcher_processador.exe")
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(LAUNCHER_PROCESSADOR, destino)


def _montar_executaveis_cliente(raiz: Path, versao: str):
    """Cliente: top + launcher/ (sem launcher_processador, que e' do servidor)."""
    raiz.mkdir(parents=True, exist_ok=True)
    launcher_d = raiz / "launcher"
    launcher_d.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PRINCIPAL_VISUALIZADOR, raiz / "visualizador.exe")
    shutil.copy2(LEIA_ME_EXECS, raiz / "LEIA-ME.md")
    shutil.copytree(REPORT_DIR, raiz / "REPORT", dirs_exist_ok=True)
    grava_config(raiz / "CONFIG" / "config.xml", versao, RAIZ_REDE)
    shutil.copy2(LAUNCHER_ATUALIZADOR, launcher_d / "launcher_atualizador.exe")
    shutil.copy2(LAUNCHER_VISUALIZADOR, launcher_d / "launcher_visualizador.exe")


def montar_rede(base: Path):
    """REDE/CVC_IAM_ANALYTICS/ — vai para o share.
    Banco vazio + arquivos de entrada prontos para o primeiro processamento.
    O launcher_processador.exe (motor, grande) vai num zip separado (motor)."""
    raiz = base / "CVC_IAM_ANALYTICS"
    _montar_executaveis_servidor_sem_motor(raiz / "EXECUTAVEIS", VERSAO_INICIAL)
    # ENTRADA com os arquivos prontos para o primeiro processamento
    for sub in ENTRADA_SUBDIRS:
        (raiz / "ENTRADA" / sub).mkdir(parents=True, exist_ok=True)
    for nome_origem, sub_destino in ENTRADA_ARQUIVOS:
        origem = ARQUIVOS_ORIGEM / nome_origem
        # nome_origem pode vir com subpasta (ex.: RH/ATIVOS/arquivo.xlsx);
        # no destino usamos so o nome do arquivo.
        destino = raiz / "ENTRADA" / sub_destino / Path(nome_origem).name
        shutil.copy2(origem, destino)
    # DADOS esqueleto, SEM banco (cliente roda o Processador para gera-lo)
    for sub in DADOS_SUBDIRS:
        (raiz / "DADOS" / sub).mkdir(parents=True, exist_ok=True)
    # INTERACOES vazia
    (raiz / "INTERACOES").mkdir(parents=True, exist_ok=True)


def montar_cliente(base: Path):
    """CLIENTE/CVC_VISUALIZADOR/ — vai para a maquina-usuario.
    Sem o motor (launcher_processador) — ele fica so na rede."""
    _montar_executaveis_cliente(base / "CVC_VISUALIZADOR", VERSAO_INICIAL)


def montar_atualizacao(base: Path):
    """ATUALIZACAO/ — config.xml com versao bumpada para demonstrar o auto-update."""
    raiz = base / "CVC_IAM_ANALYTICS" / "EXECUTAVEIS" / "CONFIG"
    raiz.mkdir(parents=True, exist_ok=True)
    grava_config(raiz / "config.xml", VERSAO_NOVA, RAIZ_REDE)


LEIA_ME = """\
ENTREGA_REDE — Teste end-to-end com pasta de rede
===================================================

Um zip unico (ENTREGA_REDE.zip) com duas pastas:

  REDE\\      -> copiar para Z:\\CVC\\CVC_IAM_ANALYTICS\\  (servidor, COM o motor)
  CLIENTE\\   -> copiar para cada maquina-usuario

Este pacote valida a arquitetura multiusuario: base na rede,
varios visualizadores escrevendo .jsonl por usuario em INTERACOES/,
Processador consolidando, auto-update por versao.

Caminho de rede assumido: Z:\\CVC\\CVC_IAM_ANALYTICS

------------------------------------------------------------
1. PRE-REQUISITO — Drive Z: mapeado
------------------------------------------------------------

OPCAO A: Z: e' um share de rede real
    Mapear o drive Z: na maquina/servidor que vai hospedar a base
    e em cada maquina-usuario. As permissoes devem ser R/W para
    todos os usuarios do teste.

OPCAO B: Simulacao local (uma maquina, uma "rede" fake)
    Criar uma pasta local e mapear Z: para ela com subst:
        mkdir C:\\CVC
        subst Z: C:\\CVC

    Para desfazer ao final: subst Z: /D

    O subst nao sobrevive a reboot — se rebootar, refaca.

------------------------------------------------------------
2. SUBIR A "REDE"
------------------------------------------------------------

Copie o conteudo da pasta REDE\\CVC_IAM_ANALYTICS\\ deste zip
para  Z:\\CVC\\CVC_IAM_ANALYTICS\\

A pasta REDE\\ ja vem com:
    EXECUTAVEIS\\  Processador.exe, visualizador.exe, CONFIG\\config.xml
                  (com <raiz>Z:\\CVC\\CVC_IAM_ANALYTICS</raiz>),
                  REPORT\\, visualizador.py, LEIA-ME.md
    ENTRADA\\      arquivos PRONTOS para o primeiro processamento:
                    RH\\ATIVOS\\PROJETOIAM (8).CSV
                    RH\\DESLIGADOS\\PROJETOIAMDESLIGADOS (2).CSV
                    MATRIZES\\ORGANIZACIONAL\\Mapeamento CCO_CSC (1).xlsx
                    MATRIZES\\PERFIS_SISTEMAS\\MATRIZ DE PERFIL DE ACESSO ...
                    SISTEMAS\\SYSTUR\\relatorio systur 30.04.xlsx
                    (SIGOT, SICA_RA, IC tambem ja estao no lugar
                     para quando entrarem em escopo)
    DADOS\\         estrutura vazia (Processador grava aqui o iam_analytics.db
                   e os Excel de saida)
    INTERACOES\\    vazia (escrita pelos visualizadores)

------------------------------------------------------------
3. INSTALAR CADA MAQUINA-USUARIO
------------------------------------------------------------

Em cada maquina onde alguem vai abrir o Visualizador:

    Copie a pasta CLIENTE\\CVC_VISUALIZADOR\\ deste zip para
    onde preferir (ex.: C:\\CVC\\VISUALIZADOR\\).

    Garanta que o drive Z: esta mapeado nessa maquina.

    Para abrir, basta dois cliques em visualizador.exe — ele:
      - Compara versao local x rede (auto-update);
      - Copia o iam_analytics.db da rede para um cache local;
      - Abre o painel em http://127.0.0.1:8800/

------------------------------------------------------------
4. PRIMEIRO PROCESSAMENTO (gera o iam_analytics.db)
------------------------------------------------------------

A base nasce VAZIA. Para gerar o iam_analytics.db inicial, execute
uma vez (de qualquer maquina com Z: mapeado):

    Z:\\CVC\\CVC_IAM_ANALYTICS\\EXECUTAVEIS\\Processador.exe

O log fica em Z:\\CVC\\CVC_IAM_ANALYTICS\\DADOS\\LOGS\\.
Esperado ao fim:
    - Z:\\CVC\\CVC_IAM_ANALYTICS\\DADOS\\BANCO\\iam_analytics.db criado
    - Excel de divergencias em DADOS\\SAIDAS\\DIVERGENCIAS\\
    - Arquivos lidos movidos para Z:\\CVC\\CVC_IAM_ANALYTICS\\DADOS\\PROCESSADOS\\
      (e SISTEMAS\\SYSTUR\\PROCESSADOS\\ para o arquivo do sistema)

A partir dai, abrir o visualizador.exe (em qualquer maquina-cliente)
ja mostra o cenario processado.

------------------------------------------------------------
5. TESTE MULTIUSUARIO
------------------------------------------------------------

CENARIO REAL (duas maquinas, dois usuarios):
    1. Em cada maquina, abrir visualizador.exe.
    2. Em cada uma, fazer uma acao diferente:
         - Maquina A: enviar funcionario X para quarentena.
         - Maquina B: resolver pendencia do funcionario Y sob ticket.
    3. Verificar que Z:\\CVC\\CVC_IAM_ANALYTICS\\INTERACOES\\ ficou
       com DOIS arquivos: interacao_<usuarioA>.jsonl, interacao_<usuarioB>.jsonl.
    4. Em uma das maquinas, rodar
       Z:\\CVC\\CVC_IAM_ANALYTICS\\EXECUTAVEIS\\Processador.exe.
       No log: "Dobra: N interacao(es) consolidada(s) de 'INTERACOES_processando'".
    5. INTERACOES\\ volta a ficar vazia. Atualizar (F5) o painel em
       cada maquina — ambas devem ver as duas acoes no Historico.

SIMULACAO LOCAL (uma maquina, dois usuarios sequenciais):
    Como o visualizador usa porta fixa 8800, rode um de cada vez.

    Terminal 1 (CMD ou PowerShell):
        set USERNAME=USUARIO_A         (CMD)
        $env:USERNAME="USUARIO_A"      (PowerShell)
        C:\\CVC\\VISUALIZADOR\\visualizador.exe

    Faca uma acao (ex.: enviar para quarentena), feche o navegador
    (encerra o visualizador).

    Mesmo terminal, agora como B:
        set USERNAME=USUARIO_B
        C:\\CVC\\VISUALIZADOR\\visualizador.exe

    Faca outra acao (ex.: resolver pendencia), feche.

    Conferir Z:\\CVC\\CVC_IAM_ANALYTICS\\INTERACOES\\:
      interacao_USUARIO_A.jsonl
      interacao_USUARIO_B.jsonl

    Rodar o Processador e validar como no cenario real.

------------------------------------------------------------
6. TESTE DO AUTO-UPDATE
------------------------------------------------------------

A pasta ATUALIZACAO\\ deste zip traz o mesmo config.xml com
<versao>1.0.1</versao> (a versao da rede vai estar a frente da
versao local de cada cliente).

    1. Copie ATUALIZACAO\\CVC_IAM_ANALYTICS\\EXECUTAVEIS\\CONFIG\\config.xml
       por cima de Z:\\CVC\\CVC_IAM_ANALYTICS\\EXECUTAVEIS\\CONFIG\\config.xml.
    2. Em uma maquina-usuario, abra C:\\CVC\\VISUALIZADOR\\visualizador.exe.
    3. No log (visualizador_log.txt, ao lado do exe):
         [auto-update] atualizando 1.0.0 -> 1.0.1
         [auto-update] concluido - reiniciando
    4. O visualizador.exe local foi renomeado para .exe.old, o novo
       foi copiado da rede, e o processo reiniciou sozinho.

------------------------------------------------------------
7. CHECAGENS DE BORDA (opcional, mas vale a pena)
------------------------------------------------------------

- Conflito: rodar o Processador exatamente enquanto um visualizador
  esta gravando em INTERACOES\\. Esperado: o rename do Processador
  e' atomico; visualizador segue gravando no novo INTERACOES\\.

- Crash no meio da dobra: matar o Processador durante a fase
  "Dobra:" e rodar de novo. Esperado: ele recupera a pasta orfa
  INTERACOES_processando\\ e a consome.

- Rede caida: desconectar Z: e abrir o visualizador. Esperado:
  log "[auto-update] rede indisponivel - seguindo sem atualizar"
  e o visualizador roda com o cache local (mas sem multiusuario).

------------------------------------------------------------
8. LIMPEZA APOS O TESTE
------------------------------------------------------------

- Visualizadores: matar a aba do navegador.
- subst (se foi simulacao local): subst Z: /D
- Apagar Z:\\CVC\\CVC_IAM_ANALYTICS\\ se nao for usar de novo.
"""


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


def main():
    """Gera UM zip unico (ENTREGA_REDE.zip) contendo a pasta CVC_IAM_ANALYTICS
    COMPLETA — sem subpastas REDE/CLIENTE. E' so extrair e copiar a pasta
    CVC_IAM_ANALYTICS para Z:\\CVC\\. Versionado via Git LFS (aguenta o tamanho).

    Conteudo do zip:
      CVC_IAM_ANALYTICS/
        EXECUTAVEIS/  (Processador.exe, visualizador.exe, launcher/ COM motor,
                       CONFIG/config.xml [raiz=Z:], REPORT/)
        ENTRADA/      (arquivos prontos para o 1o processamento)
        DADOS/        (vazio — o Processador gera o banco)
        INTERACOES/   (vazia)
        LEIA-ME.txt
    """
    print("=== Build ENTREGA (zip unico: CVC_IAM_ANALYTICS completo) ===")
    checar_prerequisitos()

    if STAGING.exists():
        shutil.rmtree(STAGING, ignore_errors=True)
    STAGING.mkdir(parents=True, exist_ok=True)
    ENTREGA.mkdir(parents=True, exist_ok=True)

    inicio = datetime.now()

    # Monta CVC_IAM_ANALYTICS completo: exes (sem motor) + ENTRADA + DADOS + INTERACOES...
    montar_rede(STAGING)
    # ...e adiciona o motor (launcher_processador.exe) no mesmo EXECUTAVEIS/launcher/
    _montar_motor_separado(STAGING)

    leia = (
        "ENTREGA - CVC IAM Analytics\n"
        "============================\n\n"
        "Este zip contem a pasta CVC_IAM_ANALYTICS (programa + dados).\n"
        "NADA roda da rede: cada usuario COPIA a pasta EXECUTAVEIS para o PC\n"
        "local e roda DE LA. A rede (Z:) guarda so os dados.\n\n"
        "NA REDE (uma vez):\n"
        "  1. Extraia o zip e copie a pasta CVC_IAM_ANALYTICS para Z:\\CVC\\\n"
        "     (fica Z:\\CVC\\CVC_IAM_ANALYTICS\\). Isso poe na rede os dados\n"
        "     (ENTRADA/DADOS/INTERACOES) e a pasta EXECUTAVEIS 'mestre'.\n"
        "     O config ja vem com <raiz>Z:\\CVC\\CVC_IAM_ANALYTICS</raiz>.\n\n"
        "EM CADA MAQUINA-USUARIO:\n"
        "  2. Copie a pasta EXECUTAVEIS (de Z:\\CVC\\CVC_IAM_ANALYTICS\\) para um\n"
        "     local, ex.: C:\\CVC\\EXECUTAVEIS, e rode o visualizador.exe DE LA.\n"
        "     - Le/grava os dados na rede (Z:), pelo <raiz> do config.\n"
        "     - Auto-atualiza: copia a versao nova de Z:\\...\\EXECUTAVEIS sozinho.\n\n"
        "PROCESSAR (responsavel):\n"
        "  3. Da SUA pasta EXECUTAVEIS local, rode o Processador.exe -> gera/\n"
        "     atualiza o banco na rede (Z:\\...\\DADOS\\BANCO\\iam_analytics.db).\n"
    )
    (STAGING / "CVC_IAM_ANALYTICS" / "LEIA-ME.txt").write_text(leia, encoding="utf-8")

    alvo = ENTREGA / "ENTREGA_REDE.zip"
    zipar(STAGING / "CVC_IAM_ANALYTICS", alvo)
    print(f"\n  OK -> {alvo}  ({alvo.stat().st_size/1024/1024:.1f} MB)")

    shutil.rmtree(STAGING, ignore_errors=True)
    print(f"Concluido em {(datetime.now()-inicio).total_seconds():.1f}s.")


LEIA_ME_MOTOR = """\
ENTREGA_REDE_motor — Motor do Processador
==========================================

Este zip contem APENAS o launcher_processador.exe (motor com pandas/openpyxl).
Foi separado do ENTREGA_REDE_servidor pra cada zip caber no limite de 100 MB
do GitHub.

Como instalar:
  Extrair em uma pasta temporaria, depois copiar:
    REDE/CVC_IAM_ANALYTICS/EXECUTAVEIS/launcher/launcher_processador.exe
  para o lugar correspondente na rede:
    Z:/CVC/CVC_IAM_ANALYTICS/EXECUTAVEIS/launcher/launcher_processador.exe

O ENTREGA_REDE_servidor.zip ja traz a estrutura ao redor (CONFIG, REPORT,
ENTRADA, os outros 4 exes); ele apenas nao tem este motor por causa do
tamanho.
"""


if __name__ == "__main__":
    main()
