# -*- coding: utf-8 -*-
"""Abrir a Consulta baixava 18,4 MB para usar 145 KB.

Retorno da area em 23/09/2026: "a troca de abas esta lenta" — e, perguntado
qual aba, "para mim a consulta ja demora".

MEDIDO na base de 15/09, ao abrir a Consulta:
    /api/historico    0,95 s   11,07 MB   12.084 registros
    /api/desligados   1,23 s    7,37 MB   30.247 registros
                      2,18 s   18,44 MB

E o painel jogava fora tudo menos as matriculas:
    _histMats = new Set(recs.map(x => x.matricula))
    _deslMats = new Set(d.lista.map(x => x.m))
    _deslSit  = new Map(d.lista.map(x => [x.m, x.tratado ? 'Tratado' : x.sit]))

O cache por token (fetchAPI) evitava REBUSCAR, mas a primeira abertura pagava
a conta inteira — e ela volta a cada carga nova do Processador, em cada aba e
para cada analista.

Agora ha' uma rota enxuta: 145 KB com gzip, e o custo de montar acontece uma
vez por carga (memo pelo token), nao uma vez por abertura.
"""
import os
import sys
import sqlite3
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import visualizador.main as vm  # noqa: E402

INDEX = RAIZ / "CVC_IAM_ANALYTICS" / "EXECUTAVEIS" / "REPORT" / "index.html"


class ARotaEnxutaExiste(unittest.TestCase):

    def test_o_servidor_atende_a_rota(self):
        fonte = (RAIZ / "src/visualizador/main.py").read_text(encoding="utf-8")
        self.assertIn('self.path == "/api/consulta-marcadores"', fonte)

    def test_a_consulta_usa_a_rota_enxuta(self):
        html = INDEX.read_text(encoding="utf-8")
        i = html.index("async function _carregarHistMats(")
        corpo = html[i:html.index("\n}", i)]
        self.assertIn("/api/consulta-marcadores", corpo)
        self.assertNotIn("/api/historico", corpo,
                         "11 MB para extrair matriculas")
        self.assertNotIn("/api/desligados", corpo,
                         "7,3 MB para extrair matriculas")

    def test_as_abas_proprias_continuam_com_o_dado_completo(self):
        """A rota enxuta NAO pode ter substituido as rotas completas: as abas
        Historico e Desligados mostram os registros, nao so' as matriculas."""
        html = INDEX.read_text(encoding="utf-8")
        self.assertIn("fetchAPI('/api/historico')", html)
        self.assertIn("fetchAPI('/api/desligados')", html)


class OFormatoDosMarcadores(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cvc_marc_"))
        db = self.tmp / "iam.db"
        from infraestrutura.banco_dados.conexao import ConexaoBancoDados
        ConexaoBancoDados(str(db)).inicializar()
        self._salvo = (vm.DB_PATH, vm.BANCO_LOCAL, vm.REDE_RAIZ,
                       vm.PASTA_INTERACOES, vm._MARCADORES)
        vm.DB_PATH = vm.BANCO_LOCAL = str(db)
        vm.REDE_RAIZ = ""
        vm.PASTA_INTERACOES = ""
        vm._MARCADORES = None
        c = sqlite3.connect(db)
        c.execute("INSERT INTO rh_desligados (matricula, nome, cpf) "
                  "VALUES ('123','FULANO','00000000123')")
        c.commit(); c.close()

    def tearDown(self):
        (vm.DB_PATH, vm.BANCO_LOCAL, vm.REDE_RAIZ, vm.PASTA_INTERACOES,
         vm._MARCADORES) = self._salvo

    def test_devolve_matriculas_e_situacao(self):
        d = vm.consulta_marcadores()
        self.assertIsInstance(d.get("hist"), list)
        self.assertIsInstance(d.get("desl"), dict)
        self.assertIn("123", d["desl"])

    def test_o_memo_e_por_versao_do_dado(self):
        """Montar custa ~2,5 s porque reusa as funcoes completas — de
        proposito, para nao existir uma segunda versao da regra que decide
        "Tratar"/"OK"/"Tratado". O memo faz esse custo acontecer uma vez por
        carga, e nao uma vez por abertura."""
        vm._MARCADORES = None
        a = vm.consulta_marcadores()
        self.assertIsNotNone(vm._MARCADORES)
        self.assertEqual(vm._MARCADORES[0], vm.token_mudanca())
        self.assertIs(vm.consulta_marcadores(), a, "a 2a chamada tem de reusar")

    def test_dado_novo_invalida_o_memo(self):
        """Sem isto o painel serviria marcadores da carga anterior — o defeito
        seria pior que a lentidao que ele veio curar."""
        vm.consulta_marcadores()
        vm._MARCADORES = ("token-de-outra-carga", {"hist": [], "desl": {}})
        d = vm.consulta_marcadores()
        self.assertIn("123", d["desl"], "token diferente tem de remontar")



class OOverlayNaoAtrasaATrocaDeAba(unittest.TestCase):
    """O overlay de "processando" era um PISO de 450 ms em toda troca de aba.

        const espera = Math.max(0, 450 - (Date.now() - _procT));

    A intencao era nao piscar; o efeito era segurar a tela de proposito depois
    que o trabalho ja' tinha acabado. Medido no Edge com o painel real
    (scratchpad/medir_abas2.py), a area sentia isso como "a troca de abas esta
    lenta". Invertido em 23/09/2026: o atraso passou a ser para APARECER.
    Medianas por aba depois da mudanca: 0,06 s a 0,40 s.
    """

    @classmethod
    def setUpClass(cls):
        cls.html = INDEX.read_text(encoding="utf-8")
        i = cls.html.index("function proc(on){")
        cls.corpo = cls.html[i:cls.html.index("\n}", i)]

    def test_o_piso_antigo_nao_voltou(self):
        self.assertNotIn("450 - (Date.now() - _procT)", self.corpo)

    def test_o_atraso_e_para_aparecer(self):
        self.assertIn("_PROC_ATRASO", self.corpo)
        self.assertIn("setTimeout", self.corpo)

    def test_trabalho_rapido_nao_mostra_overlay(self):
        """O ramo que faz a troca ser instantanea: se o overlay nem chegou a
        aparecer, nao ha' o que esperar."""
        self.assertIn("if(!_procVisivel)", self.corpo)

    def test_as_variaveis_sao_declaradas_antes_da_funcao(self):
        """⭐ `proc()` pode ser chamado antes de o script terminar de executar,
        e `let`/`const` lancam "Cannot access before initialization" ai'. Foi
        o que quebrou o painel na primeira versao desta mudanca — so' apareceu
        porque a medicao rodava num navegador de verdade."""
        decl = self.html.index("let _procTimer")
        uso = self.html.index("function proc(on){")
        self.assertLess(decl, uso,
                        "declarar ao lado da funcao quebra o painel no boot")

if __name__ == "__main__":
    unittest.main()
