# -*- coding: utf-8 -*-
"""Monta UM zip so — CVC_IAM_ANALYTICS_LOCAL.zip — com o Visualizador E o
Processador prontos para rodar em QUALQUER pasta onde for extraido.

Diferenca para build_entrega.py (que gera dois zips, um por app): aqui os dois
apps vivem na mesma pasta CVC_IAM_ANALYTICS, compartilhando ENTRADA, DADOS e
INTERACOES — e' o ciclo completo (processar -> visualizar) numa maquina so.

Portabilidade: o config.xml vai com <rede><raiz> VAZIA. Nesse modo os caminhos
sao resolvidos a partir da pasta do proprio executavel, entao nao ha caminho
absoluto nem dependencia de drive de rede.

O banco embarcado e' o de DEMONSTRACAO (dados simulados, gerado por
scripts/gerar_db_demo.py): assim o Visualizador abre com conteudo no primeiro
clique. Para usar com dados REAIS, apague DADOS\\BANCO\\iam_analytics.db antes de
rodar o Processador — senao os dados reais entram sobre os simulados.

Pre-requisito: python deploy/build_all.py (gera os 5 exes).

Uso:
    cd deploy
    python build_zip_local.py
"""
import shutil
import sqlite3
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

DEPLOY_DIR = Path(__file__).resolve().parent
RAIZ = DEPLOY_DIR.parent
APP = RAIZ / "CVC_IAM_ANALYTICS"
EXECS = APP / "EXECUTAVEIS"
LAUNCHER = EXECS / "launcher"

SAIDA = RAIZ / "ENTREGA" / "CVC_IAM_ANALYTICS_LOCAL.zip"
STAGING = RAIZ / "_zip_local_staging"

EXES = [
    (EXECS / "visualizador.exe", "EXECUTAVEIS/visualizador.exe"),
    (EXECS / "Processador.exe", "EXECUTAVEIS/Processador.exe"),
    (LAUNCHER / "launcher_atualizador.exe", "EXECUTAVEIS/launcher/launcher_atualizador.exe"),
    (LAUNCHER / "launcher_visualizador.exe", "EXECUTAVEIS/launcher/launcher_visualizador.exe"),
    (LAUNCHER / "launcher_processador.exe", "EXECUTAVEIS/launcher/launcher_processador.exe"),
]

ENTRADA_SUBDIRS = [
    "RH/ATIVOS", "RH/DESLIGADOS",
    "SISTEMAS/SIGOT", "SISTEMAS/SICA_RA", "SISTEMAS/SICA_ESFERA",
    "SISTEMAS/SYSTUR", "SISTEMAS/IC", "SISTEMAS/SIG",
    "MATRIZES/ORGANIZACIONAL", "MATRIZES/PERFIS_SISTEMAS",
    "MATRIZES/PERFIS_SISTEMAS/SIG/DE_PARA",
]
DADOS_SUBDIRS = [
    "BANCO", "PROCESSADOS", "ERROS", "LOGS",
    "SAIDAS/DIVERGENCIAS", "SAIDAS/DESLIGADOS",
    "SAIDAS/TRANSFERIDOS", "SAIDAS/AUDITORIA",
]

LEIA_ME = """\
CVC IAM Analytics — pacote LOCAL (Visualizador + Processador)
=============================================================

Roda em QUALQUER pasta: extraia este zip onde quiser (Documentos, Desktop,
pen drive) e use. Nao precisa instalar nada, nao precisa de Python e nao
precisa de drive de rede.

O QUE FAZER
-----------
1. Extraia o zip.
2. Entre em CVC_IAM_ANALYTICS\\EXECUTAVEIS.
3. Clique em visualizador.exe — abre o painel no navegador
   (http://127.0.0.1:8800). Para fechar, feche a janela preta do programa.

O painel ja abre com dados: o banco que acompanha o pacote e' de
DEMONSTRACAO, com dados SIMULADOS (nenhum dado real de funcionario da CVC).

PARA PROCESSAR DADOS REAIS
--------------------------
1. APAGUE o arquivo DADOS\\BANCO\\iam_analytics.db (o banco de demonstracao).
   Se nao apagar, os dados reais entram POR CIMA dos simulados e o painel
   mostra os dois misturados.
2. Coloque os arquivos nas pastas de ENTRADA:
     ENTRADA\\RH\\ATIVOS               -> base de funcionarios ativos
     ENTRADA\\SISTEMAS\\<SISTEMA>      -> extrato de acesso de cada sistema
     ENTRADA\\MATRIZES\\PERFIS_SISTEMAS -> matrizes de perfil por cargo
     ENTRADA\\MATRIZES\\ORGANIZACIONAL  -> matriz organizacional
3. Clique em EXECUTAVEIS\\Processador.exe. Ele abre uma janela no navegador
   mostrando o progresso. Quando terminar, clique em "Fechar" nessa janela —
   e' esse clique que encerra o programa.
   O que ele faz: le a ENTRADA, cruza com as matrizes e grava o banco em
   DADOS\\BANCO. Cada arquivo lido e' movido para uma subpasta PROCESSADOS
   dentro da propria pasta de origem (ex.: ENTRADA\\RH\\ATIVOS\\PROCESSADOS);
   os rejeitados vao para DADOS\\ERROS. O log fica em DADOS\\LOGS.
4. Abra o visualizador.exe para ver o resultado.

RELATORIOS EM EXCEL
-------------------
Nao ha geracao automatica de Excel: a exportacao e' sob demanda, pelo botao
"Exportar Excel" de cada tela do painel (e "Exportar Visao Geral", na primeira
tela). O arquivo sai igual ao que esta na tela, respeitando os filtros.
Por isso a pasta DADOS\\SAIDAS comeca vazia.

ESTRUTURA
---------
CVC_IAM_ANALYTICS\\
  EXECUTAVEIS\\
    visualizador.exe        <- painel (clique aqui)
    Processador.exe         <- motor da analise (clique aqui)
    CONFIG\\config.xml       <- configuracao (raiz VAZIA = tudo local)
    REPORT\\index.html       <- pagina do painel
    launcher\\               <- motores internos (nao clique aqui)
  ENTRADA\\                  <- voce deposita os arquivos aqui
  DADOS\\
    BANCO\\iam_analytics.db  <- banco (vem com dados simulados)
    SAIDAS\\                 <- vazia (exportacao e' pelo painel, sob demanda)
    ERROS\\, LOGS\\           <- arquivos rejeitados e log de cada execucao
  INTERACOES\\               <- resolucoes/quarentena feitas no painel

OBSERVACOES
-----------
- Porta 8800: se ja estiver em uso, feche o outro programa que a ocupa.
- O Windows pode exibir aviso do SmartScreen na 1a execucao (exe sem
  assinatura digital): "Mais informacoes" > "Executar assim mesmo".
- Este pacote e' AUTONOMO: nao aponta para a rede e nao se auto-atualiza.
- Um mesmo pacote atende os dois usos: rodar o motor e ver o painel. Nao rode
  o Processador com o painel aberto — feche o visualizador antes.
"""


def checar_prerequisitos():
    faltando = [str(p) for p, _ in EXES if not p.exists()]
    for p in [EXECS / "CONFIG" / "config.xml", EXECS / "REPORT" / "index.html"]:
        if not p.exists():
            faltando.append(str(p))
    if faltando:
        print("FALHA — arquivos ausentes:")
        for f in faltando:
            print(f"  - {f}")
        print("\nRode 'python deploy/build_all.py' primeiro.")
        sys.exit(1)


def config_local(destino: Path):
    """config.xml com <rede><raiz> VAZIA: caminhos relativos ao proprio exe."""
    tree = ET.parse(EXECS / "CONFIG" / "config.xml")
    raiz_node = tree.getroot().find("rede/raiz")
    if raiz_node is not None:
        raiz_node.text = None
    destino.parent.mkdir(parents=True, exist_ok=True)
    tree.write(destino, encoding="UTF-8", xml_declaration=True)


def copiar_banco(destino: Path):
    """Backup pela API do SQLite — consistente mesmo com WAL aberto."""
    origem = APP / "DADOS" / "BANCO" / "iam_analytics.db"
    if not origem.exists():
        print("  ! sem banco em DADOS/BANCO — o pacote vai SEM banco "
              "(rode scripts/gerar_db_demo.py para embarcar o de demonstracao)")
        return False
    destino.parent.mkdir(parents=True, exist_ok=True)
    src, dst = sqlite3.connect(str(origem)), sqlite3.connect(str(destino))
    with dst:
        src.backup(dst)
    dst.close()
    src.close()
    return True


def montar():
    if STAGING.exists():
        shutil.rmtree(STAGING)
    base = STAGING / "CVC_IAM_ANALYTICS"

    for origem, rel in EXES:
        alvo = base / rel
        alvo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origem, alvo)

    shutil.copytree(EXECS / "REPORT", base / "EXECUTAVEIS" / "REPORT")
    config_local(base / "EXECUTAVEIS" / "CONFIG" / "config.xml")
    for extra in ["motivos_resolucao.xml"]:
        src = EXECS / "CONFIG" / extra
        if src.exists():
            shutil.copy2(src, base / "EXECUTAVEIS" / "CONFIG" / extra)
    if (EXECS / "LEIA-ME.md").exists():
        shutil.copy2(EXECS / "LEIA-ME.md", base / "EXECUTAVEIS" / "LEIA-ME.md")

    for sub in ENTRADA_SUBDIRS:
        (base / "ENTRADA" / sub).mkdir(parents=True, exist_ok=True)
    for sub in DADOS_SUBDIRS:
        (base / "DADOS" / sub).mkdir(parents=True, exist_ok=True)
    (base / "INTERACOES").mkdir(parents=True, exist_ok=True)

    com_banco = copiar_banco(base / "DADOS" / "BANCO" / "iam_analytics.db")
    (STAGING / "LEIA-ME.txt").write_text(LEIA_ME, encoding="utf-8")
    return com_banco


def zipar():
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    if SAIDA.exists():
        SAIDA.unlink()
    with zipfile.ZipFile(SAIDA, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(STAGING.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(STAGING))
            elif not any(p.iterdir()):       # pasta vazia entra como entrada propria
                z.writestr(str(p.relative_to(STAGING)).replace("\\", "/") + "/", "")


def main():
    checar_prerequisitos()
    com_banco = montar()
    zipar()
    shutil.rmtree(STAGING)
    print(f"OK -> {SAIDA}")
    print(f"  {SAIDA.stat().st_size / 1048576:.1f} MB"
          f" | banco de demonstracao: {'sim' if com_banco else 'NAO'}")


if __name__ == "__main__":
    main()
