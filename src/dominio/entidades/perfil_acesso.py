from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional
from ..objetos_valor.sistema import Sistema


@dataclass
class PerfilAcesso:
    usuario: str
    nome_usuario: str
    sistema: Sistema
    perfil: str
    situacao: str
    data_criacao: Optional[date] = None
    ultimo_acesso: Optional[datetime] = None
    matricula_vinculada: Optional[str] = None
    cpf: Optional[str] = None
