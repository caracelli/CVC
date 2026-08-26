# -*- coding: utf-8 -*-
"""Empacota um UPDATE in-place para a maquina da BRUNA — so a pasta EXECUTAVEIS/.

POR QUE ESTE BUILD EXISTE (e nao reusamos build_entrega_bruna.py):

O build_entrega_bruna.py monta o pacote COMPLETO — ENTRADA populada com as bases
do cliente + banco pronto. Isso exige ter os arquivos do cliente na maquina de
build, e eles nao estao versionados: em 14/08/2026 faltavam 16 (SIGOT, SICA_RA,
SICA_ESFERA e SIG), porque o ENTRADA.zip disponivel era de outro ciclo.

So que a Bruna JA TEM tudo isso na maquina dela, do pacote de 07/08 (bfc9546:
4 grupos, 14 bases, Pendencias 421 / Consulta 3.042 / Aderentes 2.714). Reenviar
dado seria redundante — e' o CODIGO que mudou. Entao este build manda so os
executaveis, e a base dela fica onde esta.

DIFERENCAS PARA O build_update_executaveis.py (o de producao):

  - <raiz> VAZIA (modo local). O pacote dela nunca apontou para rede; escrever
    Z:\\ ou a UNC aqui faria o painel procurar dado num caminho que nao existe
    na maquina dela.
  - SEM launcher_atualizador.exe. Em modo local nao ha rede de onde atualizar —
    e' o exe que o Defender derruba, sem funcao nenhuma aqui. Mesmo motivo do
    build_entrega_bruna.py.

O QUE O UPDATE **NAO** TOCA: DADOS/ e INTERACOES/. As tratativas que ela ja
registrou sobrevivem, e o banco migra sozinho no proximo processamento (as
migracoes em conexao.py sao aditivas).

O QUE ELE ACRESCENTA EM ENTRADA/: um unico arquivo, o de-para de codigos do SIG
(tabela de REFERENCIA, ver DE_PARA_SIG_ORIGEM). Nenhum dado dela e' substituido.

DEPOIS DE APLICAR, ELA PRECISA RODAR O Processador.exe UMA VEZ. Sem isso os
numeros da tela continuam os antigos: os ajustes agem na fase de ANALISE, nao
na importacao. E' o reprocessamento que grava motivo_status (a conta BLOQUEADA
que aparecia como "sem acesso" mudo), traduz os codigos do SIG pelo de-para e,
na rodada anterior, fez os 762 desligados recontratados virarem 24.

Uso:  cd deploy && python build_update_bruna.py
"""
import shutil
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

DEPLOY_DIR = Path(__file__).resolve().parent
RAIZ = DEPLOY_DIR.parent
EXECS = RAIZ / "CVC_IAM_ANALYTICS" / "EXECUTAVEIS"
ENTREGA = RAIZ / "ENTREGA"
STAGING = RAIZ / "_update_bruna_staging"

# O pacote dela esta em 1.0.0 (numeracao propria, resetada na Fase 1 e distinta
# da linha de producao). Da 1.0.0 para ca mudaram os DOIS lados:
#   Processador  0->1: dobra/schema do chamados_abertos, regra do desligado
#                      recontratado (762 -> 24), motivo_status
#   Visualizador 0->1: os 6 ajustes do 2o retorno, abertura de chamado no Jira,
#                      as 4 leituras de tratativa que nao falham mais em silencio
# 1.1.1 -> 1.2.2 (26/08): a rodada do 3o retorno tocou os dois lados de novo.
#   Processador  1->2: de-para do SIG persiste no catalogo (perfil volta a ter
#                      NOME), motivo_status=CONTA_BLOQUEADA
#   Visualizador 1->2: categoria sem inventar vinculo, alerta de sistema sem
#                      extrato, snapshot que enxerga o reprocesso, pino da
#                      Consulta, coluna Origem, Excel de Transferidos/Desligados
# Em modo local a versao e' ROTULO (nao ha rede para o auto-update comparar) —
# serve para ela e nos sabermos o que esta instalado.
VERSAO = "1.2.2"
RAIZ_LOCAL = ""          # vazio = MODO LOCAL (nao toca rede nenhuma)

# jira.xml carrega o token e nunca entra num pacote. launcher_atualizador.exe
# nao tem funcao em modo local (ver docstring).
#
# Os artefatos de DEV nao podem viajar (achado em 26/08/2026 — o
# UPDATE_EXECUTAVEIS_v1.3.4 entregue levava os tres):
#   *.log / visualizador_log.txt -> logs da maquina de BUILD. O visualizador.log
#     daqui tinha 35 linhas com o caminho absoluto da nossa maquina; expor a
#     arvore de diretorios de quem constroi e' desleixo, e o log nao serve pra
#     nada na maquina do cliente.
#   launcher_dev/ -> copia ANTIGA do fonte do painel (main.py de 10/07). Mandar
#     codigo-fonte desatualizado junto do exe so' cria confusao.
IGNORAR = shutil.ignore_patterns("jira.xml", "launcher_atualizador.exe",
                                 "__pycache__", "*.log", "visualizador_log.txt",
                                 "launcher_dev")

# UNICO arquivo de dado que viaja com o update, e por necessidade:
# o de-para de codigos do SIG (ID -> nome do perfil) e' tabela de REFERENCIA,
# nao extrato diario. A ENTRADA dela nunca o trouxe, e por isso a tela mostra
# `100` / `55001` no lugar de ATD_HOTEIS_NACIONAIS / ACESSO_SISTEMA_BACKOFFICE —
# foi a regressao reportada no 3o retorno (25/08). A correcao do motor faz o
# catalogo PERSISTIR, mas nao ha o que persistir se o arquivo nunca chegar.
# Vai para ENTRADA/ (nao toca DADOS/ nem INTERACOES/) e e' lido no proximo
# processamento.
DE_PARA_SIG_ORIGEM = RAIZ / "Arquivos_origem" / "ID_x_Perfis_SIG 19.08.xlsx"
DE_PARA_SIG_DESTINO = "ENTRADA/MATRIZES/PERFIS_SISTEMAS/SIG/DE_PARA"


def grava_config(config_path: Path, versao: str, raiz_valor: str):
    tree = ET.parse(config_path)
    root = tree.getroot()
    n_v = root.find("versao")
    if n_v is not None:
        n_v.text = versao
    n_r = root.find("rede/raiz")
    if n_r is not None:
        n_r.text = raiz_valor
    tree.write(config_path, encoding="UTF-8", xml_declaration=True)


def main():
    print("=== Build UPDATE BRUNA (somente EXECUTAVEIS/, modo local) ===")
    if not EXECS.exists():
        print(f"FALHA: {EXECS} nao existe. Rode deploy/build_all.py antes.")
        return 1
    faltando = [n for n in ("visualizador.exe", "Processador.exe")
                if not (EXECS / n).exists()]
    faltando += [f"launcher/{n}" for n in ("launcher_visualizador.exe",
                                           "launcher_processador.exe")
                 if not (EXECS / "launcher" / n).exists()]
    if faltando:
        print("FALHA: exes ausentes -> " + ", ".join(faltando))
        print("       rode deploy/build_all.py primeiro.")
        return 1

    if STAGING.exists():
        shutil.rmtree(STAGING, ignore_errors=True)
    destino_execs = STAGING / "EXECUTAVEIS"
    shutil.copytree(EXECS, destino_execs, ignore=IGNORAR)
    for lixo in destino_execs.rglob("__pycache__"):
        shutil.rmtree(lixo, ignore_errors=True)

    # Conferencia explicita: um jira.xml vazado e' credencial na mao de terceiro,
    # e o custo de checar aqui e' zero perto do de descobrir depois.
    vazou = [str(p.relative_to(destino_execs))
             for p in destino_execs.rglob("jira.xml")]
    if vazou:
        print(f"FALHA: jira.xml entrou no pacote -> {vazou}")
        shutil.rmtree(STAGING, ignore_errors=True)
        return 1

    grava_config(destino_execs / "CONFIG" / "config.xml", VERSAO, RAIZ_LOCAL)

    ENTREGA.mkdir(parents=True, exist_ok=True)
    alvo = ENTREGA / f"UPDATE_BRUNA_v{VERSAO}.zip"
    if alvo.exists():
        alvo.unlink()
    with zipfile.ZipFile(alvo, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for p in destino_execs.rglob("*"):
            if p.is_file():
                arc = "EXECUTAVEIS/" + str(
                    p.relative_to(destino_execs)).replace("\\", "/")
                zf.write(p, arc)
        if not DE_PARA_SIG_ORIGEM.exists():
            print(f"FALHA: de-para do SIG nao encontrado -> {DE_PARA_SIG_ORIGEM}")
            print("       sem ele os perfis do SIG continuam aparecendo pelo codigo.")
            shutil.rmtree(STAGING, ignore_errors=True)
            alvo.unlink(missing_ok=True)
            return 1
        zf.write(DE_PARA_SIG_ORIGEM,
                 f"{DE_PARA_SIG_DESTINO}/{DE_PARA_SIG_ORIGEM.name}")

    n = len(zipfile.ZipFile(alvo).namelist())
    shutil.rmtree(STAGING, ignore_errors=True)
    print(f"  OK -> {alvo}  ({alvo.stat().st_size/1024/1024:.1f} MB, {n} arquivos)")
    print(f"  versao={VERSAO}  raiz=(vazia, modo local)")
    print()
    print("  INSTRUCAO PARA A BRUNA:")
    print("   1. Fechar o painel e o Processador, se estiverem abertos.")
    print("   2. Extrair o zip e copiar EXECUTAVEIS/ POR CIMA da pasta atual.")
    print("      NAO apagar nem mexer em DADOS/ e INTERACOES/.")
    print("   2b. Copiar tambem a pasta ENTRADA/ do zip por cima da atual —")
    print("       ela leva SO o de-para do SIG (ID_x_Perfis_SIG), que e' o que")
    print("       faz os perfis do SIG voltarem a aparecer pelo NOME.")
    print("       Nenhum outro dado dela e' tocado.")
    print("   3. Rodar o Processador.exe UMA VEZ (obrigatorio — e' ele que")
    print("      aplica as regras novas; sem isso os numeros ficam os antigos).")
    print("   4. Abrir o visualizador.exe.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
