from abc import ABC, abstractmethod
from typing import List
from ..entidades.divergencia import Divergencia
from ..objetos_valor.tipo_divergencia import TipoDivergencia
from ..objetos_valor.sistema import Sistema


class IRepositorioDivergencia(ABC):

    @abstractmethod
    def salvar(self, divergencia: Divergencia) -> None: ...

    @abstractmethod
    def salvar_lote(self, divergencias: List[Divergencia]) -> None: ...

    @abstractmethod
    def obter_por_tipo(self, tipo: TipoDivergencia) -> List[Divergencia]: ...

    @abstractmethod
    def obter_por_sistema(self, sistema: Sistema) -> List[Divergencia]: ...

    @abstractmethod
    def obter_nao_resolvidas(self) -> List[Divergencia]: ...
