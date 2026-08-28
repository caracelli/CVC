# -*- coding: utf-8 -*-
"""Perfil ALEM do esperado nao pode sumir da tela.

Pedido da area no 1o retorno (29/07/2026), item 2(c): "Acessos necessario
analise — acessos onde ele pode ter mais um perfil". `PERFIL_EXCESSIVO` ja'
existia no enum (`tipo_divergencia.py`) e no rotulo do Excel desde sempre, e
NUNCA era gerado.

O defeito nao era so' "faltar pendencia". `_gerar_registros_sistema` gravava
`perfil_atual = p_ok` — o perfil que casou, e mais nada. Quem tinha o esperado
MAIS outros aparecia como "Aderente / perfil X": a tela AFIRMAVA o que a pessoa
tem, e afirmava errado.

Duas coisas separadas de proposito:
  VER    (sempre) — o extra entra em `perfil_atual` + motivo_status.
  COBRAR (flag)   — so' com `excesso_gera_pendencia=True` vira EM_ANALISE.
                    Ligar muda o numero de pendencias; e' decisao da area.

⚠️ CORRECAO DE MEDIDA. Em 26/08 media-se "196 casos / 2.153 perfis extras".
Estava ERRADO: aquela consulta ad-hoc comparava cada acesso contra a UNICA
string `perfil_esperado` gravada na linha OK, e nao contra o conjunto esperado
inteiro. As matrizes do ORACLE_EBS sao largas — mat 1051 tem 39 perfis
previstos para o cargo, mat 1562 tem 50, mat 1590 tem 20 vindos da CCO — e
quase todo "extra" era, na verdade, previsto. Medido pelo motor real na mesma
ENTRADA de 05/08: **130 casos, 186 perfis extras** (ORACLE_EBS 96 · SYSTUR 33
· IC 1). O `test_ter_dois_esperados_nao_e_excesso` abaixo trava exatamente o
engano que produziu o 2.153.
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

SYS = "SYSTUR"
IC = "IC_INTEGRADOR_CONTABIL"


def _cenario(esperados, tem, flag=False, sistema=SYS):
    """Uma pessoa com `esperados` na matriz e `tem` no extrato."""
    tmp = tempfile.mkdtemp(prefix="cvc_exc_")
    cx = ConexaoBancoDados(os.path.join(tmp, "d.db"))
    cx.inicializar()
    s = cx.sessao()
    s.add(RhAtivo(matricula="M1", nome="ROSE", cpf="11111111111",
                  cargo_codigo="CG", cargo_descricao="ANALISTA",
                  centro_custo_codigo="100", situacao="ATIVO"))
    for p in esperados:
        s.add(PerfilEsperadoModel(cargo_codigo="100", cargo_descricao="ANALISTA",
                                  sistema=sistema, perfil=p))
    for i, p in enumerate(tem):
        s.add(AcessoSistema(sistema=sistema, usuario="u1", perfil=p,
                            matricula_vinculada="M1", situacao="ATIVO"))
    s.commit(); s.close()
    ValidarAcessosSistema(cx, excesso_gera_pendencia=flag).executar()
    s = cx.sessao()
    rows = [(r.status, r.motivo_status, r.perfil_esperado, r.perfil_atual)
            for r in s.query(ValidacaoAcessoModel).filter_by(matricula="M1").all()]
    s.close()
    return rows


class ExcessoAparece(unittest.TestCase):

    def test_extra_entra_no_perfil_atual(self):
        """O caso que a tela escondia."""
        r = _cenario(["P1"], ["P1", "EXTRA_A", "EXTRA_B"])
        self.assertEqual(len(r), 1)
        status, mot, esp, atual = r[0]
        self.assertEqual(status, "OK", "ver o excesso nao pode virar pendencia sozinho")
        self.assertEqual(mot, "PERFIL_EXCESSIVO")
        self.assertEqual(esp, "P1")
        self.assertEqual(atual, "P1, EXTRA_A, EXTRA_B",
                         "o esperado vem primeiro; a tela calcula a diferenca")

    def test_sem_extra_nada_muda(self):
        """Nao-regressao: 2.257 das 2.453 linhas OK caem aqui."""
        self.assertEqual(_cenario(["P1"], ["P1"]), [("OK", None, "P1", "P1")])

    def test_ter_dois_esperados_nao_e_excesso(self):
        """⭐ O engano que inflou a medida de 26/08 para 2.153.

        A pessoa tem DOIS perfis, e os dois estao na matriz. Isso e' aderencia,
        nao excesso. Se o calculo comparar contra a unica string gravada em
        `perfil_esperado`, P2 vira "extra" e o numero explode."""
        r = _cenario(["P1", "P2"], ["P1", "P2"])
        self.assertEqual(len(r), 1)
        self.assertIsNone(r[0][1], "perfil previsto pela matriz NAO e' excesso")
        self.assertEqual(r[0][3], "P1")

    def test_um_previsto_um_fora(self):
        r = _cenario(["P1", "P2"], ["P1", "P2", "SOBRA"])
        self.assertEqual(r[0][1], "PERFIL_EXCESSIVO")
        self.assertEqual(r[0][3], "P1, SOBRA", "so' o que a matriz nao explica")

    def test_grafia_diferente_nao_e_extra(self):
        """Retorno de 10/08: a matriz e o extrato grafam o mesmo perfil de dois
        jeitos. No IC o casamento aproxima '_' e espaco — sem o dedup, o mesmo
        acesso apareceria como perfil a mais."""
        r = _cenario(["IC CONSULTA"], ["IC_CONSULTA"], sistema=IC)
        self.assertIsNone(r[0][1], f"grafia dupla virou excesso: {r[0]}")


class CobrarEDecisaoDaArea(unittest.TestCase):

    def test_flag_off_e_o_padrao(self):
        import inspect
        p = inspect.signature(ValidarAcessosSistema.__init__).parameters
        self.assertIs(p["excesso_gera_pendencia"].default, False)

    def test_flag_on_vira_pendencia(self):
        r = _cenario(["P1"], ["P1", "EXTRA_A"], flag=True)
        self.assertEqual(r[0][0], "EM_ANALISE")
        self.assertEqual(r[0][1], "PERFIL_EXCESSIVO")

    def test_flag_on_nao_afeta_quem_nao_tem_excesso(self):
        self.assertEqual(_cenario(["P1"], ["P1"], flag=True)[0][0], "OK")


class TelaExplicaOExcesso(unittest.TestCase):

    def test_sql_do_painel_tem_o_motivo(self):
        """Sem este ramo, motivo_status='PERFIL_EXCESSIVO' nao vira texto e o
        '?' da grid nao aparece — o dado existe e a tela nao conta."""
        src = (Path(__file__).resolve().parent.parent
               / "src" / "visualizador" / "main.py").read_text(encoding="utf-8")
        self.assertIn("WHEN 'PERFIL_EXCESSIVO' THEN", src)

    def test_config_ausente_significa_desligado(self):
        """A instalacao da area tem config.xml ANTIGO, sem <validacao>. Se o
        default fosse true, o proximo processamento criaria pendencia sem
        ninguem ter pedido."""
        import xml.etree.ElementTree as ET
        from infraestrutura.configuracao.leitor_config import LeitorConfig
        cfg = (Path(__file__).resolve().parent.parent / "CVC_IAM_ANALYTICS"
               / "EXECUTAVEIS" / "CONFIG" / "config.xml")
        root = ET.parse(cfg).getroot()
        self.assertEqual(
            (root.findtext("validacao/perfil_excessivo/gera_pendencia") or "").strip(),
            "false", "o config versionado tem de sair desligado")
        # e sem o elemento nenhum tambem
        tmp = Path(tempfile.mkdtemp(prefix="cvc_cfgold_")) / "config.xml"
        t = cfg.read_text(encoding="utf-8")
        i, j = t.index("<validacao>"), t.index("</validacao>") + len("</validacao>")
        tmp.write_text(t[:i] + t[j:], encoding="utf-8")
        self.assertFalse(LeitorConfig(str(tmp)).carregar().validacao_excesso_gera_pendencia)


if __name__ == "__main__":
    unittest.main()
