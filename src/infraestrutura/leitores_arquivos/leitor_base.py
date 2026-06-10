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

    # Subpastas ignoradas na varredura recursiva (saídas do próprio processo)
    _SUBPASTAS_IGNORADAS = {"processados", "erros"}

    def listar_arquivos(self, pasta: str) -> List[Path]:
        """Varre a pasta de forma RECURSIVA, ignorando PROCESSADOS/ e ERROS/."""
        p = Path(pasta)
        if not p.exists():
            logger.warning(f"Pasta não encontrada: {pasta}")
            return []
        arquivos = [
            f for f in p.rglob("*")
            if f.is_file()
            and f.suffix.lower() in EXTENSOES_SUPORTADAS
            and not any(
                parte.lower() in self._SUBPASTAS_IGNORADAS
                for parte in f.relative_to(p).parts[:-1]
            )
        ]
        logger.info(f"{len(arquivos)} arquivo(s) encontrado(s) em {p.name} (recursivo)")
        return sorted(arquivos)

    def mover_para_processados(self, arquivo: Path):
        # SEMPRE move para uma subpasta PROCESSADOS dentro da pasta do proprio
        # arquivo de origem (controle por pasta). A varredura recursiva ignora
        # "processados"/"erros" (_SUBPASTAS_IGNORADAS), entao nao reprocessa.
        destino = arquivo.parent / "PROCESSADOS"
        destino.mkdir(parents=True, exist_ok=True)
        sufixo = datetime.now().strftime("%Y%m%d_%H%M%S")
        novo_nome = f"{arquivo.stem}_{sufixo}{arquivo.suffix}"
        shutil.move(str(arquivo), str(destino / novo_nome))
        logger.info(f"Movido para processados: {destino}")

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
