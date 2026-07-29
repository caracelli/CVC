from dataclasses import dataclass
from datetime import date
from typing import Optional
from .funcionario import Funcionario


@dataclass
class FuncionarioAtivo(Funcionario):
    data_admissao: Optional[date] = None
    situacao: str = "ATIVO"
    # FUNCIONARIO (CLT proprio) | TERCEIRO | FRANQUEADO | PRESTADOR
    tipo_vinculo: str = "FUNCIONARIO"
    # Login do diretorio (AD) — chave de vinculo p/ franqueado/prestador.
    login: Optional[str] = None
    # Empresa fornecedora (preenchido para terceiros/franqueado/prestador)
    empresa: Optional[str] = None
    # "Nome Gestor" do RH — chave do casamento com a CCO (cc + gestor)
    gestor: Optional[str] = None
