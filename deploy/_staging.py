# -*- coding: utf-8 -*-
r"""Limpeza da pasta de staging dos builds.

POR QUE ISTO EXISTE (28/08/2026):

Todo builder comecava com

    if STAGING.exists():
        shutil.rmtree(STAGING, ignore_errors=True)
    shutil.copytree(...)

e o `ignore_errors=True` engolia a falha. O repo vive dentro do OneDrive, que
marca diretorio como ReadOnly; o `rmtree` entao NAO apaga, segue calado, e o
`copytree` seguinte estoura com

    FileExistsError: [WinError 183] ... \_update_bruna_staging\EXECUTAVEIS

Foi exatamente o que travou o build de 28/08: sobras VAZIAS de 27/08, so'
diretorios, todos com o atributo ReadOnly. O erro aponta para o copytree e nao
diz a causa — custa tempo ate perceber que o culpado e' a linha anterior.

Aqui a limpeza tira o ReadOnly antes de apagar e, se ainda assim sobrar algo,
FALHA ALTO. Staging que nao morre e' bug de build, nao detalhe a ignorar: o
pacote sairia misturando arquivo velho com novo.
"""
import os
import shutil
import stat
from pathlib import Path


def _forcar_escrita(func, caminho, _exc):
    """onerror do rmtree: tira ReadOnly (heranca do OneDrive) e tenta de novo."""
    try:
        os.chmod(caminho, stat.S_IWRITE)
        func(caminho)
    except OSError:
        pass


def limpar(staging) -> None:
    """Apaga a pasta de staging. Levanta se ela sobreviver."""
    p = Path(staging)
    if not p.exists():
        return
    shutil.rmtree(p, onerror=_forcar_escrita)
    if p.exists():
        raise RuntimeError(
            f"nao consegui limpar o staging: {p}\n"
            "  Apague a mao e rode de novo. Seguir com sobra la' dentro faria o\n"
            "  pacote misturar arquivo velho com novo."
        )
