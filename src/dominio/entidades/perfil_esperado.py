from dataclasses import dataclass
from ..objetos_valor.sistema import Sistema


@dataclass(frozen=True)
class PerfilEsperado:
    cargo_codigo: str        # código do centro de custo
    sistema: Sistema
    perfil: str
    descricao: str = ""
    cargo_descricao: str = ""   # descritivo do cargo / função
    acesso_manual: bool = False  # flag ACESSO MANUAL da matriz SYSTUR
