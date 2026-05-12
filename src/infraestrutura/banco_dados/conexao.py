from pathlib import Path
from sqlalchemy import create_engine, text
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
        self._migrar()
        logger.info("Banco de dados inicializado.")

    def _migrar(self):
        """Apply incremental schema changes to existing databases."""
        with self._engine.connect() as conn:
            # Add cargo_descricao to perfis_esperados if missing
            cols = {row[1] for row in conn.execute(text("PRAGMA table_info(perfis_esperados)"))}
            if "cargo_descricao" not in cols:
                conn.execute(text("ALTER TABLE perfis_esperados ADD COLUMN cargo_descricao TEXT"))
                conn.commit()
                logger.info("Migration: coluna cargo_descricao adicionada a perfis_esperados.")

    def sessao(self) -> Session:
        return self._SessionFactory()

    @property
    def engine(self):
        return self._engine
