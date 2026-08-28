# -*- coding: utf-8 -*-
"""Empacota um UPDATE in-place — SOMENTE a pasta EXECUTAVEIS/.

Diferente de build_entrega_rede.py (instalacao nova com DADOS/BANCO vazio),
este pacote NAO traz ENTRADA/DADOS/INTERACOES — assim o cliente copia so os
executaveis por cima de Z:\\CVC\\CVC_IAM_ANALYTICS\\EXECUTAVEIS\\ sem risco de
apagar o banco nem as interacoes.

Grava no config do pacote a VERSAO abaixo e <rede><raiz>Z:\\...</raiz>.

Uso:  cd deploy && python build_update_executaveis.py
"""
import shutil
import sys as _sys
from pathlib import Path as _Path
# roda tanto de dentro de deploy/ quanto da raiz do repo
_sys.path.insert(0, str(_Path(__file__).resolve().parent))
import _staging
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

DEPLOY_DIR = Path(__file__).resolve().parent
RAIZ = DEPLOY_DIR.parent
EXECS = RAIZ / "CVC_IAM_ANALYTICS" / "EXECUTAVEIS"
ENTREGA = RAIZ / "ENTREGA"
STAGING = RAIZ / "_update_staging"

# MAJOR.PROCESSADOR.VISUALIZADOR. Da 1.3.4 (entregue em 07/08) para ca mudaram
# OS DOIS lados, por isso os dois digitos sobem:
#   Processador  3->4: schema/dobra do chamados_abertos, migracao dobrado_em,
#                      regra do desligado recontratado, motivo_status
#   Visualizador 4->5: abertura de chamado no Jira, os 6 ajustes da Bruna,
#                      as 4 leituras de tratativa que nao falham mais em silencio
VERSAO = "1.4.5"
RAIZ_REDE = r"Z:\CVC\CVC_IAM_ANALYTICS"


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
    print("=== Build UPDATE (somente EXECUTAVEIS/) ===")
    _staging.limpar(STAGING)   # ver deploy/_staging.py — ignore_errors mentia
    destino_execs = STAGING / "EXECUTAVEIS"
    # copia a pasta EXECUTAVEIS inteira (exes + launcher + REPORT + CONFIG + py)
    #
    # jira.xml FICA DE FORA: ele carrega o token da conta de servico e vive na
    # pasta de rede, colocado uma vez pela infra. Se um jira.xml existir na
    # maquina de build, o copytree o embarcaria no pacote e a credencial se
    # espalharia para toda maquina que aplicasse o update. O .exemplo, esse sim,
    # vai junto — e' so' modelo.
    shutil.copytree(EXECS, destino_execs,
                    # jira.xml = credencial. Os demais sao artefatos de DEV
                    # da maquina de build: logs com o caminho local e uma copia
                    # antiga do fonte do painel. A v1.3.4 ENTREGUE levava os
                    # tres (achado em 26/08/2026).
                    ignore=shutil.ignore_patterns(
                        "jira.xml", "__pycache__", "*.log",
                        "visualizador_log.txt", "launcher_dev"))
    # remove caches do build, se vieram juntos
    for lixo in destino_execs.rglob("__pycache__"):
        shutil.rmtree(lixo, ignore_errors=True)
    # ajusta o config do PACOTE (nao toca no config de dev do repo)
    grava_config(destino_execs / "CONFIG" / "config.xml", VERSAO, RAIZ_REDE)

    ENTREGA.mkdir(parents=True, exist_ok=True)
    alvo = ENTREGA / f"UPDATE_EXECUTAVEIS_v{VERSAO}.zip"
    if alvo.exists():
        alvo.unlink()
    with zipfile.ZipFile(alvo, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for p in destino_execs.rglob("*"):
            if p.is_file():
                arc = "EXECUTAVEIS/" + str(p.relative_to(destino_execs)).replace("\\", "/")
                zf.write(p, arc)

    shutil.rmtree(STAGING, ignore_errors=True)
    print(f"  OK -> {alvo}  ({alvo.stat().st_size/1024/1024:.1f} MB)")
    print(f"  versao={VERSAO}  raiz={RAIZ_REDE}")
    print("  Cliente: extrair e copiar EXECUTAVEIS/ por cima de "
          "Z:\\CVC\\CVC_IAM_ANALYTICS\\EXECUTAVEIS\\ (NAO tocar em DADOS/ nem INTERACOES/).")


if __name__ == "__main__":
    main()
