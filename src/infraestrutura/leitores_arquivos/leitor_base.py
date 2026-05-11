import shutil
from datetime import datetime
from pathlib import Path
from typing import List

import chardet
from loguru import logger

EXTENSOES_SUPORTADAS = {".csv", ".xlsx", ".xls"}


class LeitorArquivoBase:

    def listar_arquivos(self, pasta: str) -> List[Path]:
        p = Path(pasta)
        if not p.exists():
            logger.warning(f"Pasta não encontrada: {pasta}")
            return []
        arquivos = [
            f for f in p.iterdir()
            if f.is_file() and f.suffix.lower() in EXTENSOES_SUPORTADAS
        ]
        logger.info(f"{len(arquivos)} arquivo(s) encontrado(s) em {p.name}")
        return sorted(arquivos)

    def mover_para_processados(self, arquivo: Path):
        destino = arquivo.parent / "PROCESSADOS"
        destino.mkdir(exist_ok=True)
        sufixo = datetime.now().strftime("%Y%m%d_%H%M%S")
        novo_nome = f"{arquivo.stem}_{sufixo}{arquivo.suffix}"
        shutil.move(str(arquivo), str(destino / novo_nome))
        logger.info(f"Movido para PROCESSADOS: {arquivo.name}")

    def mover_para_erros(self, arquivo: Path, erro: str):
        destino = arquivo.parent / "ERROS"
        destino.mkdir(exist_ok=True)
        sufixo = datetime.now().strftime("%Y%m%d_%H%M%S")
        novo_nome = f"{arquivo.stem}_{sufixo}{arquivo.suffix}"
        shutil.move(str(arquivo), str(destino / novo_nome))
        logger.error(f"Movido para ERROS: {arquivo.name} — {erro}")

    def detectar_encoding(self, arquivo: Path) -> str:
        with open(arquivo, "rb") as f:
            raw = f.read(50_000)
        resultado = chardet.detect(raw)
        encoding = resultado.get("encoding") or "utf-8"
        logger.debug(f"Encoding detectado ({arquivo.name}): {encoding}")
        return encoding
