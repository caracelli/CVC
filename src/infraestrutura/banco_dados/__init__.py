from .conexao import ConexaoBancoDados
from .schema import (
    Base, RhAtivo, RhDesligado, SnapshotRh, Historico, HistoricoRh,
    LogImportacao, CatalogoPerfil,
)

__all__ = [
    "ConexaoBancoDados", "Base",
    "RhAtivo", "RhDesligado", "SnapshotRh",
    "Historico", "HistoricoRh",  # HistoricoRh = alias compat
    "LogImportacao", "CatalogoPerfil",
]
