from abc import ABC, abstractmethod
from typing import List
from ..entidades.perfil_acesso import PerfilAcesso
from ..objetos_valor.sistema import Sistema


class IRepositorioAcesso(ABC):

    @abstractmethod
    def obter_por_sistema(self, sistema: Sistema) -> List[PerfilAcesso]: ...

    @abstractmethod
    def obter_por_usuario(self, usuario: str) -> List[PerfilAcesso]: ...

    @abstractmethod
    def salvar(self, perfil: PerfilAcesso) -> None: ...

    @abstractmethod
    def salvar_lote(self, perfis: List[PerfilAcesso]) -> None: ...
