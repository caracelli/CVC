# -*- coding: utf-8 -*-
"""O limiar de inclusao (regra B1) passou a ser parametro de configuracao.

CONTEXTO — por que ele foi desligado em 23/09/2026:

O limiar nasceu em 25/06 com UMA justificativa: nao inundar a fila de
pendencias com esperado irrelevante. Em 29/07 a area pediu que "sem acesso"
saisse das pendencias e ficasse so' na Consulta (commit 24aaf9f). A partir
daquele dia o limiar passou a cortar informacao que nao entra em fila
nenhuma — a premissa que o sustentava tinha sido revogada pela propria area.

Ela cobrou o efeito em 10/08 ("nao esta mapeado na matriz ou esta e ela nao
tem?"), em 25/08 ("se o usuario nao tiver acesso no sistema, mas na matriz
ele tiver mapeado, deve vir qual acesso que ele pode ter"), em 17/09 (o
documento chamado "Usuario que veio sem mapeamento mais tem acesso previsto
na matriz") e em 22/09. Em 23/09 ficou decidido: para os sistemas com matriz,
trazer 100% do que esta mapeado.

O QUE ESTE ARQUIVO TRAVA:
  - zero desliga a regra, e a inclusao aparece;
  - o valor historico (0,30) continua funcionando, para a area poder voltar
    atras sem rebuild;
  - config ANTIGO, sem a chave, NAO muda de comportamento sozinho;
  - o default do construtor segue 0,30 — e' o que os testes de B1 exercitam.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import (
    RhAtivo, PerfilEsperadoModel, AcessoSistema, ValidacaoAcessoModel)
from aplicacao.casos_de_uso.validar_acessos_sistema import ValidarAcessosSistema
from infraestrutura.configuracao.leitor_config import LeitorConfig

SYS = "SYSTUR"


def _cenario(limiar=None):
    """Cargo com adesao BAIXA: 1 de 4 pessoas tem o acesso (25% < 30%).

    A pessoa avaliada (M1) nao tem acesso e a matriz preve um perfil para ela.
    Com o limiar historico a inclusao e' suprimida; com zero, aparece.
    """
    tmp = tempfile.mkdtemp(prefix="cvc_limiar_")
    cx = ConexaoBancoDados(os.path.join(tmp, "d.db"))
    cx.inicializar()
    s = cx.sessao()
    for i in range(1, 5):
        s.add(RhAtivo(matricula=f"M{i}", nome=f"PESSOA {i}",
                      cpf=str(i).rjust(11, "0"), cargo_codigo="CG",
                      cargo_descricao="ANALISTA", centro_custo_codigo="100",
                      situacao="ATIVO"))
    s.add(PerfilEsperadoModel(cargo_codigo="100", cargo_descricao="ANALISTA",
                              sistema=SYS, perfil="P1"))
    # so' a M4 tem acesso -> adesao 1/4 = 25%
    s.add(AcessoSistema(sistema=SYS, usuario="u4", perfil="P1",
                        matricula_vinculada="M4", situacao="ATIVO"))
    s.commit(); s.close()
    ValidarAcessosSistema(cx, limiar_inclusao=limiar).executar()
    s = cx.sessao()
    linhas = [(r.sistema, r.status) for r in
              s.query(ValidacaoAcessoModel).filter_by(matricula="M1").all()]
    s.close()
    return linhas


class ZeroDesligaARegra(unittest.TestCase):

    def test_com_o_valor_historico_a_inclusao_some(self):
        """Era o comportamento ate 23/09: adesao 25% < 30% -> nada e' gravado,
        e a pessoa cai no 'Não Mapeado'."""
        self.assertEqual(_cenario(limiar=0.30), [("", "NAO_MAPEADO")])

    def test_com_zero_a_inclusao_aparece(self):
        self.assertEqual(_cenario(limiar=0.0), [(SYS, "SEM_ACESSO")])

    def test_default_do_construtor_e_o_historico(self):
        """Quem constroi sem passar o parametro mantem 0,30 — e' o que os
        testes de B1 (test_regras_validacao_simulada) exercitam."""
        self.assertEqual(_cenario(), [("", "NAO_MAPEADO")])


class OConfigEhAFonte(unittest.TestCase):

    def _cfg(self, xml):
        tmp = Path(tempfile.mkdtemp(prefix="cvc_cfg_")) / "config.xml"
        tmp.write_text(xml, encoding="utf-8")
        return LeitorConfig(str(tmp)).carregar().validacao_limiar_inclusao

    def test_config_do_projeto_esta_com_zero(self):
        raiz = Path(__file__).resolve().parent.parent
        cfg = LeitorConfig(str(
            raiz / "CVC_IAM_ANALYTICS/EXECUTAVEIS/CONFIG/config.xml")).carregar()
        self.assertEqual(cfg.validacao_limiar_inclusao, 0.0,
                         "a área pediu 100% do que a matriz mapeia (23/09)")

    def test_config_antigo_sem_a_chave_mantem_o_historico(self):
        self.assertEqual(
            self._cfg("<configuracao><versao>1.0.0</versao></configuracao>"),
            0.30)

    def test_valor_invalido_cai_no_historico(self):
        for v in ("abc", "1.5", "-0.2", ""):
            with self.subTest(valor=v):
                self.assertEqual(self._cfg(
                    "<configuracao><validacao><limiar_inclusao>"
                    f"<adesao_minima>{v}</adesao_minima>"
                    "</limiar_inclusao></validacao></configuracao>"), 0.30)

    def test_aceita_virgula_decimal(self):
        self.assertEqual(self._cfg(
            "<configuracao><validacao><limiar_inclusao>"
            "<adesao_minima>0,45</adesao_minima>"
            "</limiar_inclusao></validacao></configuracao>"), 0.45)


if __name__ == "__main__":
    unittest.main()
