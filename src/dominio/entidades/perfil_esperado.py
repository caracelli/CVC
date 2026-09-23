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
    # Coluna PERFIL SYSTUR — hoje so' a matriz do Oracle EBS tem. Diz a QUAL
    # perfil do SYSTUR esta linha pertence: a pessoa so' pode ter este acesso
    # do Oracle se tiver aquele perfil no SYSTUR (regra da area, 23/09/2026).
    # Vazio nas demais matrizes = a linha nao depende do SYSTUR.
    perfil_systur: str = ""
