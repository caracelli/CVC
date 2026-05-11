from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from loguru import logger
from .schema import Base


class ConexaoBancoDados:

    def __init__(self, caminho_db: str):
        Path(caminho_db).parent.mkdir(parents=True, exist_ok=True)
        self._engine = create_engine(f"sqlite:///{caminho_db}", echo=False)
        self._SessionFactory = sessionmaker(bind=self._engine)

    def inicializar(self):
        Base.metadata.create_all(self._engine)
        logger.info("Banco de dados inicializado.")

    def sessao(self) -> Session:
        return self._SessionFactory()

    @property
    def engine(self):
        return self._engine
