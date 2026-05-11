from dataclasses import dataclass
from typing import Optional
from ..objetos_valor.cargo import Cargo


@dataclass
class Funcionario:
    matricula: str
    nome: str
    cpf: str
    cargo: Cargo
    email: Optional[str] = None

    def __post_init__(self):
        if not self.matricula:
            raise ValueError("Matrícula é obrigatória")
        if not self.nome:
            raise ValueError("Nome é obrigatório")
        if not self.cpf:
            raise ValueError("CPF é obrigatório")
