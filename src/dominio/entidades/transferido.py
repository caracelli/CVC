from dataclasses import dataclass
from datetime import date
from typing import Optional
from .funcionario_ativo import FuncionarioAtivo
from ..objetos_valor.cargo import Cargo


@dataclass
class Transferido:
    funcionario: FuncionarioAtivo
    cargo_anterior: Cargo
    data_transferencia: date
    motivo: Optional[str] = None

    @property
    def precisa_revisao_acessos(self) -> bool:
        return self.funcionario.cargo.departamento != self.cargo_anterior.departamento
