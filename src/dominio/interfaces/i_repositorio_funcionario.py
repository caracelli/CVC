from abc import ABC, abstractmethod
from typing import List, Optional
from ..entidades.funcionario_ativo import FuncionarioAtivo
from ..entidades.funcionario_desligado import FuncionarioDesligado


class IRepositorioFuncionario(ABC):

    @abstractmethod
    def obter_ativos(self) -> List[FuncionarioAtivo]: ...

    @abstractmethod
    def obter_desligados(self) -> List[FuncionarioDesligado]: ...

    @abstractmethod
    def buscar_por_matricula(self, matricula: str) -> Optional[FuncionarioAtivo]: ...

    @abstractmethod
    def buscar_por_cpf(self, cpf: str) -> Optional[FuncionarioAtivo]: ...
