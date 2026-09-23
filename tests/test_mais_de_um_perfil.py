# -*- coding: utf-8 -*-
"""MAIS DE UM PERFIL no mesmo sistema vira pendencia.

Retorno da area (22/09/2026, "Aplicacao_2_09.pdf", textual): "Mais de um perfil
nao pode ficar nada como aderente, ele precisa vir como pendencia para analise".

NAO e' o PERFIL EXCESSIVO de 28/08 (`test_perfil_excessivo.py`). Sao perguntas
diferentes:
  excessivo          -> "a matriz preve este acesso?"  (sobra em relacao a matriz)
  mais de um perfil  -> "quantos perfis ela tem?"      (o limite e' um, e ponto)
Uma pessoa com DOIS perfis que a matriz preve nao tem excesso nenhum e, ate
22/09, saia Aderente — e' exatamente o caso que a area levantou (print da
THAIANE, matricula 14510, SYSTUR).

ESCOPO: todos os sistemas (decisao do usuario em 22/09, ciente do volume). A
regra nasceu no SYSTUR em 17/09 ("usuarios do systur nao podem ter mais de um
perfil"), so' como aviso de tela. Medido em 22/09 na base de 15/09: 419 linhas
hoje Aderentes viram pendencia (SIG 197, ORACLE_EBS 164, SYSTUR 58); as
pendencias vao de 826 para 1.245.

O config (`validacao/mais_de_um_perfil/`) tem `gera_pendencia` e `sistemas`
para a area recuar sem rebuild — mesmo desenho do perfil excessivo.
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
import visualizador.main as vm  # noqa: F401  (usado em NoPainel)

SYS = "SYSTUR"
IC = "IC_INTEGRADOR_CONTABIL"


def _cenario(esperados, tem, sistema=SYS, ligado=True, escopo=None, fora=None):
    """Uma pessoa com `esperados` na matriz e `tem` no extrato."""
    tmp = tempfile.mkdtemp(prefix="cvc_multi_")
    cx = ConexaoBancoDados(os.path.join(tmp, "d.db"))
    cx.inicializar()
    s = cx.sessao()
    s.add(RhAtivo(matricula="M1", nome="THAIANE", cpf="11111111111",
                  cargo_codigo="CG", cargo_descricao="ANALISTA",
                  centro_custo_codigo="100", situacao="ATIVO"))
    for p in esperados:
        s.add(PerfilEsperadoModel(cargo_codigo="100", cargo_descricao="ANALISTA",
                                  sistema=sistema, perfil=p))
    for p in tem:
        s.add(AcessoSistema(sistema=sistema, usuario="u1", perfil=p,
                            matricula_vinculada="M1", situacao="ATIVO"))
    s.commit(); s.close()
    ValidarAcessosSistema(cx, multi_perfil_gera_pendencia=ligado,
                          multi_perfil_sistemas=escopo,
                          multi_perfil_sistemas_fora=fora).executar()
    s = cx.sessao()
    rows = [(r.status, r.motivo_status, r.perfil_esperado, r.perfil_atual)
            for r in s.query(ValidacaoAcessoModel).filter_by(matricula="M1").all()]
    s.close()
    return rows


class DoisPerfisViramPendencia(unittest.TestCase):

    def test_o_caso_da_area(self):
        """Os DOIS perfis estao na matriz: nao ha excesso, e mesmo assim a
        linha nao pode ficar Aderente."""
        r = _cenario(["P1", "P2"], ["P1", "P2"])
        self.assertEqual(len(r), 1)
        status, mot, esp, atual = r[0]
        self.assertEqual(status, "EM_ANALISE")
        self.assertEqual(mot, "MAIS_DE_UM_PERFIL")
        self.assertEqual(atual, "P1, P2", "a tela precisa mostrar os dois")

    def test_um_perfil_segue_aderente(self):
        """Nao-regressao: a esmagadora maioria das linhas OK cai aqui."""
        self.assertEqual(_cenario(["P1"], ["P1"]), [("OK", None, "P1", "P1")])

    def test_preserva_o_motivo_anterior(self):
        """A linha ja' podia carregar um porque (aqui, PERFIL_EXCESSIVO). Perder
        esse achado seria trocar um diagnostico por outro."""
        r = _cenario(["P1"], ["P1", "SOBRA"])
        self.assertEqual(r[0][0], "EM_ANALISE")
        self.assertEqual(r[0][1], "MAIS_DE_UM_PERFIL | PERFIL_EXCESSIVO")

    def test_grafia_dupla_nao_inventa_pendencia(self):
        """Mesmo cuidado do dedup dos esperados (retorno de 10/08): 'IC CONSULTA'
        e 'IC_CONSULTA' sao o MESMO perfil. Contar os dois criaria pendencia do
        nada — no IC o casamento aproxima '_' e espaco."""
        r = _cenario(["IC CONSULTA"], ["IC_CONSULTA"], sistema=IC)
        self.assertEqual(r[0][0], "OK", f"grafia dupla virou pendencia: {r[0]}")


class EscopoEDesligamento(unittest.TestCase):

    def test_flag_desligada_mantem_o_comportamento_antigo(self):
        r = _cenario(["P1", "P2"], ["P1", "P2"], ligado=False)
        self.assertEqual(r[0][0], "OK")
        self.assertIsNone(r[0][1])

    def test_escopo_limita_aos_sistemas_listados(self):
        """A area pode recuar para um subconjunto sem rebuild."""
        r = _cenario(["P1", "P2"], ["P1", "P2"], escopo=["SIG"])
        self.assertEqual(r[0][0], "OK", "SYSTUR fora do escopo configurado")
        r = _cenario(["P1", "P2"], ["P1", "P2"], escopo=["SYSTUR"])
        self.assertEqual(r[0][0], "EM_ANALISE")

    def test_escopo_vazio_e_todos(self):
        self.assertEqual(_cenario(["P1", "P2"], ["P1", "P2"], escopo=[])[0][0],
                         "EM_ANALISE")

    def test_default_do_construtor_e_off(self):
        """Quem constroi o caso de uso sem a flag mantem o comportamento antigo;
        em producao quem manda e' o config, e la' o default e' true."""
        import inspect
        p = inspect.signature(ValidarAcessosSistema.__init__).parameters
        self.assertIs(p["multi_perfil_gera_pendencia"].default, False)


class SistemasDeFora(unittest.TestCase):
    """Sistemas em que ter varios perfis e' NORMAL ficam de fora da regra.

    ORACLE_EBS entrou em 23/09/2026. Palavras da area: "para oracle nao, a
    pessoa pode ter mais de um perfil no oracle; cada perfil e' um acesso
    especifico ao sistema". Sem isso, quem tem exatamente os perfis da funcao
    dela virava pendencia — medido na PRISCILA 90001455, com os 4 perfis
    Oracle da funcao "Atendimento a fornecedores CVC e VISUAL"."""

    def test_sistema_de_fora_nao_vira_pendencia(self):
        r = _cenario(["P1", "P2"], ["P1", "P2"], sistema="ORACLE_EBS",
                     fora=["ORACLE_EBS"])
        self.assertEqual(r[0][0], "OK")
        self.assertIsNone(r[0][1])

    def test_os_demais_continuam_valendo(self):
        r = _cenario(["P1", "P2"], ["P1", "P2"], fora=["ORACLE_EBS"])
        self.assertEqual(r[0][0], "EM_ANALISE")
        self.assertEqual(r[0][1], "MAIS_DE_UM_PERFIL")

    def test_config_do_projeto_tira_so_o_oracle(self):
        """SO' o Oracle. Em 23/09/2026 eu acrescentei o SIG por conta propria,
        com o argumento de que os perfis dele tambem se somam (47% das pessoas
        tem mais de um, media 18,7). O usuario recusou: o pedido era validar o
        ORACLE contra o SYSTUR — e' o que a coluna PERFIL SYSTUR da matriz do
        Oracle diz —, nao mexer no SIG. Este teste existe para o SIG nao
        reaparecer aqui sem alguem pedir."""
        from infraestrutura.configuracao.leitor_config import LeitorConfig
        raiz = Path(__file__).resolve().parent.parent
        cfg = LeitorConfig(str(
            raiz / "CVC_IAM_ANALYTICS/EXECUTAVEIS/CONFIG/config.xml")).carregar()
        self.assertEqual(cfg.validacao_multi_perfil_sistemas_fora, ["ORACLE_EBS"])


class ConfigEhAFonte(unittest.TestCase):

    def test_config_do_projeto_liga_para_todos(self):
        from infraestrutura.configuracao.leitor_config import LeitorConfig
        raiz = Path(__file__).resolve().parent.parent
        cfg = LeitorConfig(str(
            raiz / "CVC_IAM_ANALYTICS/EXECUTAVEIS/CONFIG/config.xml")).carregar()
        self.assertTrue(cfg.validacao_multi_perfil_gera_pendencia)
        self.assertEqual(cfg.validacao_multi_perfil_sistemas, [],
                         "vazio = todos os sistemas")

    def test_ausencia_da_chave_nao_quebra(self):
        """Config antigo (sem o bloco) tem de continuar carregando. O default do
        leitor e' true: o pacote novo passa a cobrar mesmo com config velho."""
        from infraestrutura.configuracao.leitor_config import LeitorConfig
        tmp = Path(tempfile.mkdtemp(prefix="cvc_cfg_")) / "config.xml"
        tmp.write_text(
            "<configuracao><versao>1.0.0</versao><validacao>"
            "<perfil_excessivo><gera_pendencia>false</gera_pendencia>"
            "</perfil_excessivo></validacao></configuracao>", encoding="utf-8")
        cfg = LeitorConfig(str(tmp)).carregar()
        self.assertTrue(cfg.validacao_multi_perfil_gera_pendencia)
        self.assertEqual(cfg.validacao_multi_perfil_sistemas, [])


class NoPainel(unittest.TestCase):
    """O snapshot que a tela le (`bi_divergencias`) precisa trazer as DUAS
    coisas: a frase (para o analista ler) e o CODIGO (para a tela decidir o
    rotulo). O encadeamento de motivos e' o caso que quebrava: ate 22/09 o
    CASE do snapshot casava por igualdade exata e a linha encadeada ficava sem
    texto nenhum."""

    def setUp(self):
        import sqlite3
        import visualizador.main as vm
        self.vm = vm
        self.tmp = tempfile.mkdtemp(prefix="cvc_bi_")
        self.db = os.path.join(self.tmp, "iam.db")
        ConexaoBancoDados(self.db).inicializar()
        self._orig = (vm.DB_PATH, vm.SISTEMA)
        vm.DB_PATH, vm.SISTEMA, vm._BASE = self.db, "", None
        c = sqlite3.connect(self.db)
        try:
            cols = [r[1] for r in c.execute("PRAGMA table_info(validacao_acessos)")]
            def ins(mat, sistema, status, motivo, atual):
                vals = {"matricula": mat, "nome": "PESSOA " + mat,
                        "cpf": mat.rjust(11, "0"), "sistema": sistema,
                        "perfil_esperado": "P1", "perfil_atual": atual,
                        "status": status, "situacao_acao": "PENDENTE",
                        "motivo_status": motivo,
                        "dt_processamento": "2026-09-22 10:00:00"}
                usar = [k for k in vals if k in cols]
                c.execute("INSERT INTO validacao_acessos (" + ",".join(usar) + ") "
                          "VALUES (" + ",".join("?" * len(usar)) + ")",
                          [vals[k] for k in usar])
            ins("1", "SYSTUR", "EM_ANALISE", "MAIS_DE_UM_PERFIL", "P1, P2")
            ins("2", "SYSTUR", "EM_ANALISE",
                "MAIS_DE_UM_PERFIL | PERFIL_EXCESSIVO", "P1, P2, SOBRA")
            ins("3", "SYSTUR", "OK", None, "P1")
            c.commit()
        finally:
            c.close()
        vm.garantir_estrutura(force=True)

    def tearDown(self):
        self.vm.DB_PATH, self.vm.SISTEMA = self._orig
        self.vm._BASE = None

    def _div(self, matricula):
        db = self.vm.construir_db()
        u = [x for x in db["users"] if x["m"] == matricula][0]
        return u["divs"][0]

    def test_frase_chega_a_tela(self):
        d = self._div("1")
        self.assertIn("mais de um perfil", d["mot"].lower())
        self.assertIn("um perfil por pessoa por sistema", d["mot"])

    def test_codigo_chega_a_tela(self):
        self.assertEqual(self._div("1")["motc"], "MAIS_DE_UM_PERFIL")

    def test_motivo_encadeado_nao_fica_sem_texto(self):
        """⭐ O caso que o CASE por igualdade perdia — 134 das 419 linhas
        medidas em 22/09/2026."""
        d = self._div("2")
        self.assertTrue(d["mot"], "linha encadeada ficou sem motivo na tela")
        self.assertIn("mais de um perfil", d["mot"].lower())
        self.assertIn("MAIS_DE_UM_PERFIL", d["motc"])
        self.assertIn("PERFIL_EXCESSIVO", d["motc"], "o achado anterior segue la")

    def test_aderente_nao_ganha_motivo(self):
        """Nao-regressao: quem tem um perfil so' continua limpo."""
        d = self._div("3")
        self.assertEqual(d["mot"], "")
        self.assertEqual(d["motc"], "")

    def test_snapshot_antigo_e_refeito(self):
        """Banco que a area ja' tem: o snapshot sem `motivo_cod` precisa ser
        recriado sozinho, senao a tela fica sem o rotulo ate alguem reprocessar
        (mesmo cuidado tomado com `funcao` em 18/09)."""
        import sqlite3
        c = sqlite3.connect(self.db)
        try:
            c.execute("DROP TABLE bi_divergencias")
            c.execute("CREATE TABLE bi_divergencias (usuario TEXT, tipo TEXT, "
                      "acao TEXT, motivo TEXT, data_identificacao TEXT)")
            c.commit()
        finally:
            c.close()
        self.vm._BASE = None
        self.vm.garantir_estrutura()
        c = sqlite3.connect(self.db)
        try:
            cols = [r[1] for r in c.execute("PRAGMA table_info(bi_divergencias)")]
        finally:
            c.close()
        self.assertIn("motivo_cod", cols)


if __name__ == "__main__":
    unittest.main()
