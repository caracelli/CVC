from dataclasses import dataclass
from datetime import date
from typing import Optional
from .funcionario import Funcionario


@dataclass
class FuncionarioAtivo(Funcionario):
    data_admissao: Optional[date] = None
    situacao: str = "ATIVO"
    # FUNCIONARIO (CLT proprio) | TERCEIRO (prestador de fornecedor)
    tipo_vinculo: str = "FUNCIONARIO"
    # Empresa fornecedora (preenchido para terceiros)
    empresa: Optional[str] = None
