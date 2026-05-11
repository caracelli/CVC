from dataclasses import dataclass, field
from datetime import date
from typing import Optional
from .funcionario import Funcionario


@dataclass
class FuncionarioAtivo(Funcionario):
    data_admissao: Optional[date] = None
    situacao: str = "ATIVO"
