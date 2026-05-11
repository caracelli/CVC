from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from ..objetos_valor.sistema import Sistema
from ..objetos_valor.tipo_divergencia import TipoDivergencia


@dataclass
class Divergencia:
    id: str
    tipo: TipoDivergencia
    sistema: Sistema
    usuario: str
    nome_usuario: str
    descricao: str
    matricula: Optional[str] = None
    perfil_encontrado: Optional[str] = None
    perfil_esperado: Optional[str] = None
    data_identificacao: datetime = field(default_factory=datetime.now)
    resolvida: bool = False
