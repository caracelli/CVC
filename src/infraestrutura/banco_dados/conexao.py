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
            # perfis_esperados: cargo_descricao
            cols = {row[1] for row in conn.execute(text("PRAGMA table_info(perfis_esperados)"))}
            if "cargo_descricao" not in cols:
                conn.execute(text("ALTER TABLE perfis_esperados ADD COLUMN cargo_descricao TEXT"))
                conn.commit()
                logger.info("Migration: coluna cargo_descricao adicionada a perfis_esperados.")

            # perfis_esperados: acesso_manual
            if "acesso_manual" not in cols:
                conn.execute(text("ALTER TABLE perfis_esperados ADD COLUMN acesso_manual INTEGER DEFAULT 0"))
                conn.commit()
                logger.info("Migration: coluna acesso_manual adicionada a perfis_esperados.")

            # snapshots_rh: colunas de CDC (novos / alterados / removidos)
            cols_snap = {row[1] for row in conn.execute(text("PRAGMA table_info(snapshots_rh)"))}
            for coluna in ("novos", "alterados", "removidos"):
                if coluna not in cols_snap:
                    conn.execute(text(f"ALTER TABLE snapshots_rh ADD COLUMN {coluna} INTEGER DEFAULT 0"))
                    conn.commit()
                    logger.info(f"Migration: coluna {coluna} adicionada a snapshots_rh.")

            # validacao_acessos: ciclo PENDENTE/RESOLVIDO da ação
            cols_val = {row[1] for row in conn.execute(text("PRAGMA table_info(validacao_acessos)"))}
            if "situacao_acao" not in cols_val:
                conn.execute(text("ALTER TABLE validacao_acessos ADD COLUMN situacao_acao TEXT DEFAULT 'PENDENTE'"))
                conn.commit()
                logger.info("Migration: coluna situacao_acao adicionada a validacao_acessos.")

            # matriz_organizacional → substituída por matriz_cco; remover tabela antiga se existir
            tabelas = {row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
            if "matriz_organizacional" in tabelas and "matriz_cco" not in tabelas:
                conn.execute(text("DROP TABLE matriz_organizacional"))
                conn.commit()
                logger.info("Migration: tabela matriz_organizacional removida (substituída por matriz_cco).")

    def sessao(self) -> Session:
        return self._SessionFactory()

    @property
    def engine(self):
        return self._engine
