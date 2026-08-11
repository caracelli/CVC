# -*- coding: utf-8 -*-
"""RECONTRATADO — a regra que a area definiu (Bruna, 10/08/2026), textual:

    "se tiver ativo e for o mesmo login pode considerar ok
     agora se ele for um ativo com o login diferente precisa apontar"

Contexto (Pontos_aplicacao_2.docx, prints 1-2): pessoas apareciam como
desligadas estando ativas. A mesma pessoa tem matricula antiga (desligada) e
nova (ativa) — re-matriculacao — e o motor casava pelo CPF/login da antiga,
marcando como irregular a conta que ela USA HOJE.

Entao o eixo da decisao e' o LOGIN, nao o vinculo nem o CPF: pessoa ativa com o
mesmo login sai da lista; pessoa ativa com login DIFERENTE e' apontada — e'
identidade antiga que sobrou viva. Medido: dos 1.794 pares desligado x ativo,
1.790 (99,8%) mantiveram o mesmo login; 4 voltaram com login diferente.
"""
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dominio.entidades.funcionario_ativo import FuncionarioAtivo
from dominio.entidades.funcionario_desligado import FuncionarioDesligado
from dominio.entidades.perfil_acesso import PerfilAcesso
from dominio.objetos_valor.cargo import Cargo
from dominio.objetos_valor.sistema import Sistema
from dominio.regras.regra_acesso_desligado import RegraAcessoDesligado


def _cargo():
    return Cargo(codigo="CG", descricao="ANALISTA", departamento="TI",
                 centro_custo="100")


def _ativo(matricula, cpf, nome="FULANO", tipo_vinculo="FUNCIONARIO"):
    return FuncionarioAtivo(matricula=matricula, nome=nome, cpf=cpf,
                            cargo=_cargo(), situacao="ATIVO",
                            tipo_vinculo=tipo_vinculo)


def _deslig(matricula, cpf, nome="FULANO"):
    return FuncionarioDesligado(matricula=matricula, nome=nome, cpf=cpf,
                                cargo=_cargo(),
                                data_desligamento=date(2025, 6, 30))


def _acesso(usuario, matricula_vinculada=None, cpf="", sistema=Sistema.SYSTUR,
            situacao="ATIVO"):
    return PerfilAcesso(
        sistema=sistema, usuario=usuario, perfil="PERFIL_X",
        nome_usuario="FULANO", cpf=cpf, situacao=situacao,
        matricula_vinculada=matricula_vinculada,
    )


class TestRecontratadoMesmoLogin(unittest.TestCase):
    """'se tiver ativo e for o MESMO LOGIN pode considerar ok'"""

    def setUp(self):
        self.regra = RegraAcessoDesligado()

    def test_casos_reais_do_print_somem(self):
        """HUGO, DANIELE e GIRLAISON: matricula nova ATIVA, antiga desligada, e
        a conta ja vinculada a matricula NOVA (como esta na base real)."""
        casos = [
            ("90000568", "34531584", "76789420444", "HUGO LEONARDO FELIX DA SILVA"),
            ("90000994", "34531099", "40053815882", "DANIELE MARIA DA SILVA"),
            ("90001174", "34532317", "73418692168", "GIRLAISON RIBEIRO MACEDO"),
        ]
        ativos = [_ativo(nova, cpf, nome) for nova, _, cpf, nome in casos]
        desligados = [_deslig(velha, cpf, nome) for _, velha, cpf, nome in casos]
        acessos = [_acesso(f"CORPC{nova}", matricula_vinculada=nova, cpf=cpf)
                   for nova, _, cpf, _ in casos]

        divs = self.regra.verificar(acessos, desligados, ativos)

        self.assertEqual(divs, [], "mesmo login de quem esta ativo = ok")
        self.assertEqual(self.regra.recontratados_suprimidos, 3)

    def test_mesmo_login_sem_vinculo_na_conta_tambem_sai(self):
        """A conta nao foi vinculada, mas o login e' o que a pessoa ativa usa
        (veio do diretorio AD dela)."""
        cpf = "76789420444"
        a = _ativo("90000568", cpf); a.login = "hsilva"
        desligados = [_deslig("34531584", cpf)]
        acessos = [_acesso("hsilva", cpf=cpf)]

        divs = self.regra.verificar(acessos, desligados, [a])

        self.assertEqual(divs, [])
        self.assertEqual(self.regra.recontratados_suprimidos, 1)

    def test_login_com_caixa_diferente_e_o_mesmo_login(self):
        """'CORPC90000568' e 'corpc90000568' sao a mesma conta."""
        cpf = "76789420444"
        ativos = [_ativo("90000568", cpf)]
        desligados = [_deslig("34531584", cpf)]
        acessos = [_acesso("CORPC90000568", matricula_vinculada="90000568"),
                   _acesso("corpc90000568", cpf=cpf)]

        divs = self.regra.verificar(acessos, desligados, ativos)

        self.assertEqual(divs, [])

    def test_volta_como_terceiro_com_mesmo_login_tambem_sai(self):
        """A regra fala de ATIVO — nao restringe o vinculo sob o qual voltou."""
        cpf = "76789420444"
        ativos = [_ativo("TERC-76789420444", cpf, tipo_vinculo="TERCEIRO")]
        desligados = [_deslig("34531584", cpf)]
        acessos = [_acesso("L1", matricula_vinculada="TERC-76789420444")]

        divs = self.regra.verificar(acessos, desligados, ativos)

        self.assertEqual(divs, [])


class TestRecontratadoLoginDiferente(unittest.TestCase):
    """'agora se ele for um ativo com o LOGIN DIFERENTE precisa apontar'"""

    def setUp(self):
        self.regra = RegraAcessoDesligado()

    def test_conta_antiga_com_outro_login_e_APONTADA(self):
        """O caso NATALIA da base real: usa 'nmatos' hoje e deixou 'njmatos'
        preso a identidade antiga. Tem de aparecer."""
        cpf = "76789420444"
        ativos = [_ativo("90000568", cpf, "NATALIA")]
        desligados = [_deslig("34531584", cpf, "NATALIA")]
        acessos = [
            _acesso("nmatos",  matricula_vinculada="90000568"),   # a de hoje
            _acesso("njmatos", matricula_vinculada="34531584"),   # a antiga
        ]

        divs = self.regra.verificar(acessos, desligados, ativos)

        self.assertEqual(len(divs), 1, "login diferente precisa apontar")
        self.assertEqual(divs[0].usuario, "njmatos")
        self.assertEqual(self.regra.login_diferente_apontado, 1)
        # 'nmatos' nem chega a casar como desligado (a matricula dela e' ativa e
        # o login nao e' de nenhum desligado), entao nao entra como "perdoado" —
        # o contador mede so o que casaria e foi considerado ok.
        self.assertEqual(self.regra.recontratados_suprimidos, 0)

    def test_login_diferente_SEM_vinculo_na_conta_tambem_aponta(self):
        """Era o furo do critério anterior: a conta sem vinculo, com CPF de
        alguem ativo, sumia mesmo tendo outro login. A area quer ver."""
        cpf = "76789420444"
        ativos = [_ativo("90000568", cpf)]
        desligados = [_deslig("34531584", cpf)]
        acessos = [
            _acesso("CORPC90000568", matricula_vinculada="90000568"),  # a de hoje
            _acesso("LOGIN_ANTIGO_SOLTO", cpf=cpf),                    # outro login
        ]

        divs = self.regra.verificar(acessos, desligados, ativos)

        self.assertEqual(len(divs), 1)
        self.assertEqual(divs[0].usuario, "LOGIN_ANTIGO_SOLTO")
        self.assertEqual(self.regra.login_diferente_apontado, 1)

    def test_volta_como_franqueado_com_outro_login_aponta(self):
        """O caso CARLA da base real: voltou franqueada com 'grus2226' e deixou
        'carsantos' vivo no SIG."""
        cpf = "76789420444"
        a = _ativo("FRANQ-grus2226", cpf, "CARLA", tipo_vinculo="FRANQUEADO")
        a.login = "grus2226"
        desligados = [_deslig("34531584", cpf, "CARLA")]
        acessos = [_acesso("carsantos", matricula_vinculada="34531584",
                           sistema=Sistema.SIG)]

        divs = self.regra.verificar(acessos, desligados, [a])

        self.assertEqual(len(divs), 1)
        self.assertEqual(divs[0].usuario, "carsantos")



class TestDesligadoDeVerdade(unittest.TestCase):
    """Quem NAO esta ativo segue pelo matching normal — nada disso pode sumir."""

    def setUp(self):
        self.regra = RegraAcessoDesligado()

    def test_desligado_de_verdade_continua_aparecendo(self):
        """Ninguem ativo com esse CPF/matricula: segue sendo divergencia."""
        ativos = [_ativo("90000568", "76789420444")]
        desligados = [_deslig("34531584", "11144477735")]
        acessos = [_acesso("LOGIN1", matricula_vinculada="34531584",
                           cpf="11144477735")]

        divs = self.regra.verificar(acessos, desligados, ativos)

        self.assertEqual(len(divs), 1)
        self.assertEqual(self.regra.recontratados_suprimidos, 0)

    def test_conta_do_AD_por_login_continua_aparecendo(self):
        """Desligado do diretorio AD casa so por LOGIN (sem matricula/CPF na
        conta) — a chave que fecha a lacuna nao pode ser afetada."""
        ativos = [_ativo("90000568", "76789420444")]
        d = _deslig("34531584", "11144477735")
        d.login = "hsilva"
        acessos = [_acesso("hsilva")]

        divs = self.regra.verificar(acessos, [d], ativos)

        self.assertEqual(len(divs), 1)

    def test_cpf_invalido_nao_colide(self):
        """CPF '000...' nao pode servir de de-para (colidiria em massa)."""
        ativos = [_ativo("90000568", "00000000000")]
        desligados = [_deslig("34531584", "00000000000")]
        acessos = [_acesso("LOGIN1", cpf="00000000000")]

        divs = self.regra.verificar(acessos, desligados, ativos)

        self.assertEqual(self.regra.recontratados_suprimidos, 0)

    def test_cpf_com_zero_a_esquerda_casa(self):
        """CPF salvo como numero perde o zero; o zfill precisa reconciliar."""
        a = _ativo("90000568", "12345678")          # CPF sem os zeros
        a.login = "mesmologin"
        desligados = [_deslig("34531584", "00012345678")]   # com zeros
        acessos = [_acesso("mesmologin", cpf="00012345678")]

        divs = self.regra.verificar(acessos, desligados, [a])

        self.assertEqual(divs, [], "o zfill precisa reconciliar os dois CPFs")
        self.assertEqual(self.regra.recontratados_suprimidos, 1)

    def test_conta_bloqueada_continua_fora(self):
        """Regra anterior preservada: conta ja revogada nao e' divergencia."""
        desligados = [_deslig("34531584", "11144477735")]
        acessos = [_acesso("L1", matricula_vinculada="34531584",
                           situacao="BLOQUEADO")]

        divs = self.regra.verificar(acessos, desligados, [])

        self.assertEqual(divs, [])

    def test_sem_ativos_mantem_comportamento_antigo(self):
        """Chamada sem `ativos` (compatibilidade) nao suprime nada."""
        desligados = [_deslig("34531584", "76789420444")]
        acessos = [_acesso("LOGIN1", matricula_vinculada="34531584")]

        divs = self.regra.verificar(acessos, desligados)

        self.assertEqual(len(divs), 1)
        self.assertEqual(self.regra.recontratados_suprimidos, 0)


if __name__ == "__main__":
    unittest.main()
