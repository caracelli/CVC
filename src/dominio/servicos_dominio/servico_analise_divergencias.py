from typing import List
from ..entidades.divergencia import Divergencia
from ..entidades.perfil_acesso import PerfilAcesso
from ..entidades.perfil_esperado import PerfilEsperado
from ..entidades.funcionario_ativo import FuncionarioAtivo
from ..entidades.funcionario_desligado import FuncionarioDesligado
from ..entidades.transferido import Transferido
from ..regras.regra_acesso_desligado import RegraAcessoDesligado
from ..regras.regra_acesso_transferido import RegraAcessoTransferido
from ..regras.regra_acesso_sem_vinculo import RegraAcessoSemVinculo
from ..regras.regra_perfil_invalido import RegraPerfilInvalido


class ServicoAnaliseDivergencias:

    def __init__(self, perfis_esperados: List[PerfilEsperado],
                 prefixos_conta_servico=None):
        # prefixos_conta_servico vem do config (validacao/conta_servico); vazio
        # mantem o comportamento anterior. Ver RegraAcessoDesligado.
        self._regra_desligado = RegraAcessoDesligado(prefixos_conta_servico)
        self._regra_transferido = RegraAcessoTransferido()
        self._regra_sem_vinculo = RegraAcessoSemVinculo()
        self._regra_perfil = RegraPerfilInvalido(perfis_esperados)

    def analisar(
        self,
        acessos: List[PerfilAcesso],
        ativos: List[FuncionarioAtivo],
        desligados: List[FuncionarioDesligado],
        transferidos: List[Transferido],
    ) -> List[Divergencia]:
        divergencias: List[Divergencia] = []
        # `ativos` entra na regra de desligado para suprimir o RECONTRATADO
        # (mesma pessoa, matricula nova ativa + matricula antiga desligada).
        divergencias.extend(
            self._regra_desligado.verificar(acessos, desligados, ativos))
        # repassa os contadores da regra para o caso de uso logar
        self.recontratados_suprimidos = self._regra_desligado.recontratados_suprimidos
        self.login_diferente_apontado = self._regra_desligado.login_diferente_apontado
        self.contas_servico = self._regra_desligado.contas_servico
        self.divergiu_do_nome = self._regra_desligado.divergiu_do_nome
        divergencias.extend(self._regra_transferido.verificar(acessos, transferidos))
        divergencias.extend(self._regra_sem_vinculo.verificar(acessos))
        divergencias.extend(self._regra_perfil.verificar(acessos, ativos))
        return divergencias
