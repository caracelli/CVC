from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional
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
    email: Optional[str] = None
    # Resultado da cascata de matching multi-chave. Preenchidos pelo
    # ServicoVinculacaoMultiChave; default = ainda nao tentou vincular.
    metodo_vinculacao: Optional[str] = None     # CPF / EMAIL / CPF_PARCIAL_NOME / NOME / FUZZY / NAO_VINCULADO
    score_vinculacao: Optional[float] = None    # 1.0 (CPF) ... 0.5 (fuzzy) ... 0.0 (nao vinculado)
    candidatos_matricula: Optional[List[str]] = None  # matriculas candidatas quando ambiguo
