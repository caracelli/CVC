from dataclasses import dataclass
from datetime import date
from typing import Optional
from .funcionario import Funcionario


@dataclass
class FuncionarioDesligado(Funcionario):
    data_desligamento: Optional[date] = None
    motivo_desligamento: Optional[str] = None
