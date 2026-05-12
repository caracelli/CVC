from dataclasses import dataclass
from ..objetos_valor.sistema import Sistema


@dataclass(frozen=True)
class PerfilEsperado:
    cargo_codigo: str   # centro_custo code
    sistema: Sistema
    perfil: str
    descricao: str = ""
    cargo_descricao: str = ""   # cargo/function description from matrix CARGO column
