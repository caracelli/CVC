"""Roda o pipeline completo do Processador SEM a UI HTML (headless).

Util para validacao end-to-end via terminal. Reusa o _executar do main.
"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from processador.main import _executar, _caminho_config, configurar_log
from loguru import logger


def main():
    cfg_path = _caminho_config()
    t0 = time.time()
    rc = _executar(cfg_path)
    t1 = time.time()
    logger.success(f"Pipeline encerrado com rc={rc} em {t1-t0:.1f}s")
    return rc


if __name__ == "__main__":
    sys.exit(main())
