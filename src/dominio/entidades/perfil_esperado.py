from dataclasses import dataclass
from ..objetos_valor.sistema import Sistema


@dataclass(frozen=True)
class PerfilEsperado:
    cargo_codigo: str
    sistema: Sistema
    perfil: str
    descricao: str
