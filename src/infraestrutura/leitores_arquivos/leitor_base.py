import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import chardet
from loguru import logger

EXTENSOES_SUPORTADAS = {".csv", ".xlsx", ".xls"}


class LeitorArquivoBase:

    def __init__(
        self,
        pasta_processados: Optional[str] = None,
        pasta_erros: Optional[str] = None,
    ):
        self._pasta_processados = Path(pasta_processados) if pasta_processados else None
        self._pasta_erros = Path(pasta_erros) if pasta_erros else None

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
        destino = self._pasta_processados if self._pasta_processados else arquivo.parent / "PROCESSADOS"
        destino.mkdir(parents=True, exist_ok=True)
        sufixo = datetime.now().strftime("%Y%m%d_%H%M%S")
        novo_nome = f"{arquivo.stem}_{sufixo}{arquivo.suffix}"
        shutil.move(str(arquivo), str(destino / novo_nome))
        logger.info(f"Movido para processados: {arquivo.name}")

    def mover_para_erros(self, arquivo: Path, erro: str):
        destino = self._pasta_erros if self._pasta_erros else arquivo.parent / "ERROS"
        destino.mkdir(parents=True, exist_ok=True)
        sufixo = datetime.now().strftime("%Y%m%d_%H%M%S")
        novo_nome = f"{arquivo.stem}_{sufixo}{arquivo.suffix}"
        shutil.move(str(arquivo), str(destino / novo_nome))
        logger.error(f"Movido para erros: {arquivo.name} — {erro}")

    def detectar_encoding(self, arquivo: Path) -> str:
        with open(arquivo, "rb") as f:
            raw = f.read(50_000)
        resultado = chardet.detect(raw)
        encoding = resultado.get("encoding") or "utf-8"
        logger.debug(f"Encoding detectado ({arquivo.name}): {encoding}")
        return encoding
