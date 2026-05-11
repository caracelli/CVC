from typing import List
from ..entidades.divergencia import Divergencia
from ..entidades.perfil_acesso import PerfilAcesso
from ..entidades.perfil_esperado import PerfilEsperado
from ..entidades.funcionario_ativo import FuncionarioAtivo
from ..entidades.funcionario_desligado import FuncionarioDesligado
from ..entidades.transferido import Transferido
from ..regras.regra_acesso_desligado import RegraAcessoDesligado
from ..regras.regra_acesso_transferido import RegraAcessoTransferido
from ..regras.regra_perfil_invalido import RegraPerfilInvalido


class ServicoAnaliseDivergencias:

    def __init__(self, perfis_esperados: List[PerfilEsperado]):
        self._regra_desligado = RegraAcessoDesligado()
        self._regra_transferido = RegraAcessoTransferido()
        self._regra_perfil = RegraPerfilInvalido(perfis_esperados)

    def analisar(
        self,
        acessos: List[PerfilAcesso],
        ativos: List[FuncionarioAtivo],
        desligados: List[FuncionarioDesligado],
        transferidos: List[Transferido],
    ) -> List[Divergencia]:
        divergencias: List[Divergencia] = []
        divergencias.extend(self._regra_desligado.verificar(acessos, desligados))
        divergencias.extend(self._regra_transferido.verificar(acessos, transferidos))
        divergencias.extend(self._regra_perfil.verificar(acessos, ativos))
        return divergencias
