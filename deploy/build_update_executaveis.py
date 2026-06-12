# -*- coding: utf-8 -*-
"""Empacota um UPDATE in-place — SOMENTE a pasta EXECUTAVEIS/.

Diferente de build_entrega_rede.py (instalacao nova com DADOS/BANCO vazio),
este pacote NAO traz ENTRADA/DADOS/INTERACOES — assim o cliente copia so os
executaveis por cima de Z:\\CVC\\CVC_IAM_ANALYTICS\\EXECUTAVEIS\\ sem risco de
apagar o banco nem as interacoes.

Grava no config do pacote: <versao>1.1.1</versao> e <rede><raiz>Z:\\...</raiz>.

Uso:  cd deploy && python build_update_executaveis.py
"""
import shutil
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

DEPLOY_DIR = Path(__file__).resolve().parent
RAIZ = DEPLOY_DIR.parent
EXECS = RAIZ / "CVC_IAM_ANALYTICS" / "EXECUTAVEIS"
ENTREGA = RAIZ / "ENTREGA"
STAGING = RAIZ / "_update_staging"

VERSAO = "1.3.4"
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
    if STAGING.exists():
        shutil.rmtree(STAGING, ignore_errors=True)
    destino_execs = STAGING / "EXECUTAVEIS"
    # copia a pasta EXECUTAVEIS inteira (exes + launcher + REPORT + CONFIG + py)
    shutil.copytree(EXECS, destino_execs)
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
