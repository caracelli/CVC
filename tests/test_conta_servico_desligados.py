# -*- coding: utf-8 -*-
"""CONTA DE SERVICO nos desligados — retorno da area (28 e 31/08/2026).

Bruna, no Teams de 28/08: "porque ta vindo uns usuarios sistemicos nos
desligados", com o caso SIST0230 ("Monitoramento roteiros / Usuario sistemico -
Pricing") aparecendo como acesso a revogar de uma pessoa desligada. A conta de
servico fora cadastrada com o e-mail de quem a criou; quando a pessoa saiu, o
robo virou "acesso de desligado".

A regra: acesso cujo LOGIN comeca com um dos prefixos do config vira
ACESSO_CONTA_SERVICO — tipo PROPRIO, nao ausencia de linha. Sai da lista de
revogacao (que so olha ACESSO_DESLIGADO) e continua consultavel, para que uma
classificacao errada apareca em vez de se esconder.

Medido em 31/08/2026 nas 432 linhas do E2E dos 7 sistemas: `SIST` pega 297
(69%), zero falso positivo e zero robo fora do prefixo.
"""
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dominio.objetos_valor.cargo import Cargo
from dominio.objetos_valor.sistema import Sistema
from dominio.objetos_valor.tipo_divergencia import TipoDivergencia
from dominio.entidades.perfil_acesso import PerfilAcesso
from dominio.entidades.funcionario_desligado import FuncionarioDesligado
from dominio.regras.regra_acesso_desligado import RegraAcessoDesligado
from dominio.servicos_dominio.servico_analise_divergencias import ServicoAnaliseDivergencias
from infraestrutura.configuracao.leitor_config import _conta_servico_prefixos

import xml.etree.ElementTree as ET


def _desligado(mat="900", cpf="52998224725"):
    return FuncionarioDesligado(
        matricula=mat, nome="KEITI ALEIXO GELMETTI", cpf=cpf,
        cargo=Cargo(codigo="CG", descricao="ESPECIALISTA PRICING",
                    departamento="TI", centro_custo="100"),
        data_desligamento=date(2026, 1, 1))


def _acesso(usuario, nome="N", vinc="900", perfil="P1"):
    return PerfilAcesso(usuario=usuario, nome_usuario=nome, sistema=Sistema.SYSTUR,
                        perfil=perfil, situacao="ATIVO", cpf="",
                        matricula_vinculada=vinc)


def _tipos(divs):
    return [d.tipo for d in divs]


# ───────────────────────── a regra em si ─────────────────────────
class TestContaServicoNaRegra(unittest.TestCase):

    def setUp(self):
        self.desligados = [_desligado()]

    def test_sem_prefixo_configurado_mantem_comportamento_anterior(self):
        """Config sem <conta_servico> (o caso da instalacao ja entregue) nao muda
        nada: o robo continua vindo como acesso de desligado."""
        divs = RegraAcessoDesligado().verificar(
            [_acesso("SIST0230", "USUARIO SISTEMICO MONITORAMENTO ROTEIROS")],
            self.desligados)
        self.assertEqual(_tipos(divs), [TipoDivergencia.ACESSO_DESLIGADO])

    def test_com_prefixo_o_robo_sai_da_revogacao(self):
        regra = RegraAcessoDesligado(["SIST"])
        divs = regra.verificar(
            [_acesso("SIST0230", "USUARIO SISTEMICO MONITORAMENTO ROTEIROS")],
            self.desligados)
        self.assertEqual(_tipos(divs), [TipoDivergencia.ACESSO_CONTA_SERVICO])
        self.assertEqual(regra.contas_servico, 1)
        # o que faz a linha sair da cobranca: a lista de revogacao le so' este tipo
        self.assertEqual(
            [d for d in divs if d.tipo == TipoDivergencia.ACESSO_DESLIGADO], [])

    def test_pessoa_de_verdade_continua_sendo_apontada(self):
        """O outro lado da regra: quem NAO tem o prefixo segue na revogacao.
        E' o que impede a regra de virar um filtro que esconde acesso real."""
        regra = RegraAcessoDesligado(["SIST"])
        divs = regra.verificar(
            [_acesso("corpc90000395", "RAFAELA RAZORI XIMENE")], self.desligados)
        self.assertEqual(_tipos(divs), [TipoDivergencia.ACESSO_DESLIGADO])
        self.assertEqual(regra.contas_servico, 0)

    def test_prefixo_ignora_caixa(self):
        """O extrato mistura `SIST0230` e `sist0230`; a classificacao nao pode
        depender disso."""
        regra = RegraAcessoDesligado(["sist"])
        divs = regra.verificar([_acesso("SIST00895", "PROJETO JENKINS")],
                               self.desligados)
        self.assertEqual(_tipos(divs), [TipoDivergencia.ACESSO_CONTA_SERVICO])

    def test_varios_prefixos(self):
        regra = RegraAcessoDesligado(["SIST", "BOT"])
        divs = regra.verificar(
            [_acesso("BOT0001", "ROBO NOVO"), _acesso("SIST0510", "ROBÔ AÉREO GRUPOS"),
             _acesso("mtzfin195", "LILIANE PRADO")],
            self.desligados)
        self.assertEqual(
            sorted(t.value for t in _tipos(divs)),
            ["ACESSO_CONTA_SERVICO", "ACESSO_CONTA_SERVICO", "ACESSO_DESLIGADO"])
        self.assertEqual(regra.contas_servico, 2)

    def test_descricao_diz_por_que_nao_revogar(self):
        """A linha precisa se explicar sozinha: quem abrir a tela em dezembro
        nao vai lembrar da conversa de agosto."""
        divs = RegraAcessoDesligado(["SIST"]).verificar(
            [_acesso("SIST0596", "ROBÔ REEMBOLSO AO CLIENTE")], self.desligados)
        d = divs[0].descricao.lower()
        self.assertIn("conta de serviço", d)
        self.assertIn("não revogar", d)

    def test_dados_do_acesso_preservados(self):
        """Reclassificar nao pode perder informacao: a tela mostra a quem o robo
        ficou vinculado e qual o login dele."""
        divs = RegraAcessoDesligado(["SIST"]).verificar(
            [_acesso("SIST0230", "USUARIO SISTEMICO MONITORAMENTO ROTEIROS",
                     perfil="RISCO_OPERACIONAL")], self.desligados)
        d = divs[0]
        self.assertEqual(d.usuario, "SIST0230")
        self.assertEqual(d.matricula, "900")
        self.assertEqual(d.perfil_encontrado, "RISCO_OPERACIONAL")
        self.assertEqual(d.sistema, Sistema.SYSTUR)


# ─────────────── conferencia da premissa (prefixo x nome) ───────────────
class TestConferenciaDaPremissa(unittest.TestCase):
    """O nome do robo NAO e' criterio — nao pega nada que o prefixo ja nao pegue
    (medido: 297/297 de concordancia). Serve para avisar que a premissa mudou."""

    def test_concordancia_nao_gera_aviso(self):
        regra = RegraAcessoDesligado(["SIST"])
        regra.verificar([_acesso("SIST00155", "ROBÔ MARÍTIMO")], [_desligado()])
        self.assertEqual(regra.divergiu_do_nome, 0)

    def test_robo_sem_o_prefixo_acende_o_aviso(self):
        """Robo com nome de robo e login sem `SIST`: a lista de prefixos ficou
        para tras. Ele SEGUE como desligado (nao adivinhamos por nome), mas o
        contador acusa para a area revisar o config."""
        regra = RegraAcessoDesligado(["SIST"])
        divs = regra.verificar([_acesso("AUTOM042", "ROBO FINANCEIRO NOVO")],
                               [_desligado()])
        self.assertEqual(_tipos(divs), [TipoDivergencia.ACESSO_DESLIGADO])
        self.assertEqual(regra.divergiu_do_nome, 1)
        self.assertEqual(regra.contas_servico, 0)

    def test_prefixo_com_nome_de_gente_acende_o_aviso(self):
        """O contrario: alguem criou uma conta PESSOAL com o prefixo. Ela sai da
        revogacao (o prefixo manda), mas o aviso pede revisao."""
        regra = RegraAcessoDesligado(["SIST"])
        divs = regra.verificar([_acesso("SIST9999", "MARIA DA SILVA")],
                               [_desligado()])
        self.assertEqual(_tipos(divs), [TipoDivergencia.ACESSO_CONTA_SERVICO])
        self.assertEqual(regra.divergiu_do_nome, 1)


# ─────────────────────────── leitura do config ───────────────────────────
class TestConfigContaServico(unittest.TestCase):

    def _root(self, xml):
        return ET.fromstring(xml)

    def test_bloco_ausente_desliga_a_regra(self):
        """O config que a Bruna tem instalado nao tem <conta_servico>. Precisa
        cair no comportamento anterior, nao quebrar."""
        self.assertEqual(
            _conta_servico_prefixos(self._root("<config><validacao/></config>")), [])

    def test_le_o_prefixo(self):
        r = self._root("<config><validacao><conta_servico>"
                       "<prefixos_login>SIST</prefixos_login>"
                       "</conta_servico></validacao></config>")
        self.assertEqual(_conta_servico_prefixos(r), ["SIST"])

    def test_lista_separada_por_virgula(self):
        r = self._root("<config><validacao><conta_servico>"
                       "<prefixos_login>SIST, BOT , RPA</prefixos_login>"
                       "</conta_servico></validacao></config>")
        self.assertEqual(_conta_servico_prefixos(r), ["SIST", "BOT", "RPA"])

    def test_flag_desliga_sem_apagar_a_lista(self):
        """A area precisa poder voltar atras sem perder o que configurou."""
        r = self._root("<config><validacao><conta_servico>"
                       "<prefixos_login>SIST</prefixos_login>"
                       "<excluir_de_desligados>false</excluir_de_desligados>"
                       "</conta_servico></validacao></config>")
        self.assertEqual(_conta_servico_prefixos(r), [])

    def test_config_real_do_projeto_tem_a_regra_ligada(self):
        cfg = (Path(__file__).resolve().parent.parent
               / "CVC_IAM_ANALYTICS" / "EXECUTAVEIS" / "CONFIG" / "config.xml")
        root = ET.parse(cfg).getroot()
        self.assertEqual(_conta_servico_prefixos(root), ["SIST"])


# ─────────────────────── integracao pelo servico ───────────────────────
class TestServicoRepassaOsPrefixos(unittest.TestCase):

    def test_servico_aplica_a_regra_e_expoe_o_contador(self):
        servico = ServicoAnaliseDivergencias([], prefixos_conta_servico=["SIST"])
        divs = servico.analisar(
            acessos=[_acesso("SIST0230", "USUARIO SISTEMICO MONITORAMENTO ROTEIROS")],
            ativos=[], desligados=[_desligado()], transferidos=[])
        deslig = [d for d in divs if d.tipo == TipoDivergencia.ACESSO_DESLIGADO]
        serv = [d for d in divs if d.tipo == TipoDivergencia.ACESSO_CONTA_SERVICO]
        self.assertEqual(deslig, [])
        self.assertEqual(len(serv), 1)
        self.assertEqual(servico.contas_servico, 1)

    def test_servico_sem_prefixo_mantem_o_comportamento_anterior(self):
        servico = ServicoAnaliseDivergencias([])
        divs = servico.analisar(
            acessos=[_acesso("SIST0230", "ROBÔ")], ativos=[],
            desligados=[_desligado()], transferidos=[])
        self.assertEqual(
            [d.tipo for d in divs if d.tipo == TipoDivergencia.ACESSO_DESLIGADO],
            [TipoDivergencia.ACESSO_DESLIGADO])


if __name__ == "__main__":
    unittest.main()
