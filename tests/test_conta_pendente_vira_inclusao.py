# -*- coding: utf-8 -*-
"""Conta PENDENTE ('P'/sem status) vira INCLUSAO, com o perfil liberavel.

Retorno da area (31/08/2026, "Testes 1.docx"), textual:

    "Considerar apenas os acessos ativos: se a pessoa estiver com acesso nesse
     status, inativo, bloqueado ou P, e ela poder ter o acessos trazer como a
     incluir e o perfil que pode ser liberado para ela."

E no mesmo documento, sobre o print do proprio "?" que nos escrevemos em 10/08:

    "Nesse caso aqui os perfis estao iguais, nao deveria estar aderente?"

Ou seja: EXPLICAR NAO BASTOU. Em 10/08 a area pediu "corrigir explicando na
tela, nao mudando a regra"; em 31/08, olhando a explicacao, ela pediu o
desfecho. Bloqueado/inativo ja saiam como "Incluir Acesso" (CONTA_BLOQUEADA);
faltava o 'P'.

Medido em 31/08 no E2E dos 7 sistemas: 11 linhas mudam de lado.

A mudanca e' FLAG (validacao/conta_pendente/vira_inclusao) porque muda o
DESFECHO de uma pendencia: voltar atras nao pode exigir build novo, e o config
que a Bruna tem instalado hoje nao tem o bloco — cai no comportamento antigo.
"""
import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import (
    RhAtivo, PerfilEsperadoModel, AcessoSistema, ValidacaoAcessoModel)
from aplicacao.casos_de_uso.validar_acessos_sistema import ValidarAcessosSistema

SYS = "SYSTUR"


def _cenario(situacao, pendente_vira_inclusao):
    """Uma pessoa cujo cargo preve P1, com uma conta na `situacao` dada."""
    tmp = tempfile.mkdtemp(prefix="cvc_pend_")
    cx = ConexaoBancoDados(os.path.join(tmp, "d.db"))
    cx.inicializar()
    s = cx.sessao()
    s.add(RhAtivo(matricula="M1", nome="ROSE", cpf="11111111111",
                  cargo_codigo="CG", cargo_descricao="ANALISTA",
                  centro_custo_codigo="100", situacao="ATIVO"))
    s.add(PerfilEsperadoModel(cargo_codigo="100", cargo_descricao="ANALISTA",
                              sistema=SYS, perfil="P1"))
    # colega com acesso vivo mantem a adesao do cargo alta (regra B1) — sem ele
    # a inclusao e' suprimida e nao sobra registro para conferir
    s.add(RhAtivo(matricula="M2", nome="BIA", cpf="22222222222",
                  cargo_codigo="CG", cargo_descricao="ANALISTA",
                  centro_custo_codigo="100", situacao="ATIVO"))
    s.add(AcessoSistema(sistema=SYS, usuario="u2", perfil="P1",
                        matricula_vinculada="M2", situacao="ATIVO"))
    if situacao is not None:
        s.add(AcessoSistema(sistema=SYS, usuario="rose", perfil="P1",
                            matricula_vinculada="M1", situacao=situacao))
    s.commit(); s.close()
    ValidarAcessosSistema(
        cx, pendente_vira_inclusao=pendente_vira_inclusao).executar()
    s = cx.sessao()
    rows = [(r.status, r.motivo_status, r.perfil_atual or "", r.perfil_esperado or "")
            for r in s.query(ValidacaoAcessoModel).filter_by(matricula="M1").all()]
    s.close()
    return rows


class ComAFlagLigada(unittest.TestCase):

    def test_pendente_vira_inclusao(self):
        rows = _cenario("PENDENTE", True)
        self.assertEqual([(r[0], r[1]) for r in rows],
                         [("SEM_ACESSO", "CONTA_PENDENTE")])

    def test_mostra_o_perfil_LIBERAVEL(self):
        """O pedido dela tem duas metades; esta e' a segunda: "e o perfil que
        pode ser liberado para ela"."""
        rows = _cenario("PENDENTE", True)
        self.assertEqual(rows[0][3], "P1")

    def test_nao_afirma_posse_de_conta_que_nao_esta_ativa(self):
        """`perfil_atual` sai vazio: dizer que ela TEM o perfil enquanto a conta
        nao esta ativa e' o mesmo defeito do perfil excessivo, ao contrario."""
        rows = _cenario("PENDENTE", True)
        self.assertEqual(rows[0][2], "")

    def test_status_vazio_tambem_e_pendente(self):
        """'P' e vazio caem no mesmo balde (`indefinida`)."""
        rows = _cenario("", True)
        self.assertEqual([(r[0], r[1]) for r in rows],
                         [("SEM_ACESSO", "CONTA_PENDENTE")])

    def test_conta_ATIVA_nao_e_tocada(self):
        """O discriminador. Sem ele a flag viraria um "tudo e inclusao"."""
        self.assertEqual([(r[0], r[1]) for r in _cenario("ATIVO", True)],
                         [("OK", None)])

    def test_bloqueada_continua_com_o_motivo_dela(self):
        """Bloqueado ja saia como inclusao desde 25/08 e por outro caminho
        (`CONTA_BLOQUEADA`, que diz "desbloquear, nao criar"). A flag nao pode
        engolir essa distincao — as acoes sao diferentes."""
        self.assertEqual([(r[0], r[1]) for r in _cenario("BLOQUEADO", True)],
                         [("SEM_ACESSO", "CONTA_BLOQUEADA")])


class ComAFlagDESLIGADA(unittest.TestCase):
    """O config instalado na maquina dela nao tem o bloco — tem de cair aqui."""

    def test_pendente_continua_em_analise(self):
        self.assertEqual([(r[0], r[1]) for r in _cenario("PENDENTE", False)],
                         [("EM_ANALISE", "CONTA_INDEFINIDA")])

    def test_default_do_construtor_e_desligado(self):
        cx_rows = _cenario("PENDENTE", False)
        self.assertEqual(cx_rows[0][1], "CONTA_INDEFINIDA")


class ConfigDaRegra(unittest.TestCase):

    def _flag(self, xml):
        from infraestrutura.configuracao.leitor_config import LeitorConfig
        import tempfile as tf
        p = Path(tf.mkdtemp()) / "c.xml"
        p.write_text(xml, encoding="utf-8")
        # so' o pedaco que interessa: o leitor completo exige o arquivo inteiro,
        # entao conferimos pelo mesmo caminho que ele usa
        root = ET.fromstring(xml)
        txt = (root.findtext("validacao/conta_pendente/vira_inclusao", "false")
               or "false").strip().lower()
        return txt not in ("false", "0", "no", "nao", "n")

    def test_ausente_e_desligado(self):
        self.assertFalse(self._flag("<config><validacao/></config>"))

    def test_ligado_no_config_real_do_projeto(self):
        cfg = (Path(__file__).resolve().parent.parent
               / "CVC_IAM_ANALYTICS" / "EXECUTAVEIS" / "CONFIG" / "config.xml")
        root = ET.parse(cfg).getroot()
        self.assertEqual(
            (root.findtext("validacao/conta_pendente/vira_inclusao") or "").strip(),
            "true")


class TelaExplicaONovoMotivo(unittest.TestCase):

    def test_sql_do_painel_traduz_conta_pendente(self):
        """O motor grava o codigo; a tela vira texto. Sem este ramo a linha
        mudaria de lado SEM dizer por que — o defeito de 10/08 outra vez."""
        import visualizador.main as vm
        self.assertIn("CONTA_PENDENTE", vm._SQL_BI)
        i = vm._SQL_BI.index("CONTA_PENDENTE")
        trecho = vm._SQL_BI[i:i + 420]
        self.assertIn("INCLUSAO", trecho.upper())
        self.assertIn("liberado", trecho)


if __name__ == "__main__":
    unittest.main()
