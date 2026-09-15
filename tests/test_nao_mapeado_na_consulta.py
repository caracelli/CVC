# -*- coding: utf-8 -*-
"""Quem e' "Não Mapeado" tem de aparecer na Consulta.

Retorno da area (Bruna, 15/09/2026): 23 funcionarios ATIVOS "seguem nao vindo
na aplicacao". 20 deles tinham UMA linha so' no banco — a do NAO_MAPEADO, que
vem SEM sistema. O slicer de Sistema so' lista valores nao vazios
(`valoresFiltro`), entao '' nunca estava no Set e `divPassa` reprovava a linha
mesmo com todos os sistemas marcados: a pessoa sumia da Consulta inteira.

Na mesma rodada o rotulo mudou de "Sem Expectativa" para "Não Mapeado", com a
frase que a area usa ("Não tem mapeamento localizado para o centro de custo").
Decisao do usuario: um rotulo so' para os dois caminhos do motor (sem matriz, ou
com matriz mas cortado pelo limiar de 30%).
"""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
import visualizador.main as vm

INDEX = RAIZ / "CVC_IAM_ANALYTICS" / "EXECUTAVEIS" / "REPORT" / "index.html"
NODE = shutil.which("node")
ROTULO = "Não Mapeado"
FRASE = "Não tem mapeamento localizado para o centro de custo."


def _funcao(nome):
    html = INDEX.read_text(encoding="utf-8")
    i = html.index(f"function {nome}(")
    j, nivel = html.index("{", i), 0
    for k in range(j, len(html)):
        if html[k] == "{":
            nivel += 1
        elif html[k] == "}":
            nivel -= 1
            if nivel == 0:
                return html[i:k + 1]
    raise AssertionError(f"função {nome} não fecha")


@unittest.skipUnless(NODE, "Node não disponível nesta máquina")
class FiltroDeSistemaNaoEscondeLinhaSemSistema(unittest.TestCase):
    """Roda o `divPassa` REAL do index.html — o mesmo que a Consulta
    (`_csFiltrarUsers`) e a aba Pendencias usam."""

    UNIVERSO = ["SIG", "SYSTUR"]
    NAO_MAPEADO = {"a": ROTULO, "t": "NAO_MAPEADO", "tl": ROTULO,
                   "s": "Aderente", "sis": "", "vinc": "Funcionário"}

    def _passa(self, div, marcados):
        js = f"""
        const filtroSel = {{sistema: new Set({json.dumps(marcados)})}};
        const filtroVals = {{sistema: {json.dumps(self.UNIVERSO)}}};
        {_funcao('divPassa')}
        console.log(JSON.stringify(divPassa({json.dumps(div)})));
        """
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                         encoding="utf-8") as f:
            f.write(js)
            caminho = f.name
        try:
            r = subprocess.run([NODE, caminho], capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
            self.assertEqual(r.returncode, 0, r.stderr)
            return json.loads(r.stdout)
        finally:
            os.unlink(caminho)

    def test_todos_os_sistemas_marcados_a_pessoa_aparece(self):
        """O caso da Bruna: nenhum filtro mexido e a pessoa sumia."""
        self.assertTrue(self._passa(self.NAO_MAPEADO, self.UNIVERSO),
                        "linha sem sistema reprovada com o filtro de Sistema cheio")

    def test_isolando_um_sistema_quem_nao_tem_sistema_sai(self):
        self.assertFalse(self._passa(self.NAO_MAPEADO, ["SYSTUR"]))

    def test_linha_com_sistema_segue_a_regra_de_sempre(self):
        div = dict(self.NAO_MAPEADO, a="Aderente", t="OK", tl="Aderente", sis="SIG")
        self.assertTrue(self._passa(div, self.UNIVERSO))
        self.assertFalse(self._passa(div, ["SYSTUR"]))

    def test_a_consulta_filtra_pelo_divPassa(self):
        """Se a Consulta deixar de usar o divPassa, este arquivo tem de ser
        reapontado junto — senao passa verde testando a funcao errada."""
        self.assertIn("u.divs.some(divPassa)", _funcao("_csFiltrarUsers"))


class RotuloEFraseDaArea(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cvc_naomap_")
        self.db = os.path.join(self.tmp, "iam.db")
        ConexaoBancoDados(self.db).inicializar()
        self._orig = (vm.DB_PATH, vm.SISTEMA)
        vm.DB_PATH, vm.SISTEMA = self.db, ""
        vm._BASE = None
        c = sqlite3.connect(self.db)
        try:
            cols = [r[1] for r in c.execute("PRAGMA table_info(validacao_acessos)")]
            if "motivo_status" not in cols:
                c.execute("ALTER TABLE validacao_acessos ADD COLUMN motivo_status TEXT")
                cols.append("motivo_status")
            vals = {"matricula": "799", "nome": "FULANA", "cpf": "0" * 11,
                    "sistema": "", "perfil_esperado": "", "perfil_atual": "",
                    "status": "NAO_MAPEADO", "situacao_acao": "OK",
                    "motivo_status": "SEM_EXPECTATIVA_RELEVANTE",
                    "dt_processamento": "2026-09-15 12:43:28"}
            usar = [k for k in vals if k in cols]
            c.execute(f"INSERT INTO validacao_acessos ({','.join(usar)}) "
                      f"VALUES ({','.join('?' * len(usar))})", [vals[k] for k in usar])
            c.commit()
        finally:
            c.close()
        vm.garantir_estrutura(force=True)

    def tearDown(self):
        vm.DB_PATH, vm.SISTEMA = self._orig
        vm._BASE = None

    def _linha(self):
        c = sqlite3.connect(self.db)
        try:
            return c.execute("SELECT acao, motivo FROM bi_divergencias "
                             "WHERE tipo='NAO_MAPEADO'").fetchone()
        finally:
            c.close()

    def test_rotulo_e_frase(self):
        self.assertEqual(self._linha(), (ROTULO, FRASE))
        self.assertEqual(vm.TIPO_LABEL["NAO_MAPEADO"], ROTULO)

    def test_banco_com_rotulo_antigo_e_refeito_sem_o_processador(self):
        """O banco que a area ja' tem foi materializado com "Sem Expectativa".
        Sem reprocessar, abrir o painel novo tem de trocar o texto."""
        c = sqlite3.connect(self.db)
        try:
            c.execute("UPDATE bi_divergencias SET acao='Sem Expectativa', "
                      "motivo='texto antigo' WHERE tipo='NAO_MAPEADO'")
            c.commit()
        finally:
            c.close()
        vm.garantir_estrutura()                # sem force — como o .exe faz
        self.assertEqual(self._linha(), (ROTULO, FRASE))

    def test_o_painel_compara_com_o_mesmo_rotulo_do_servidor(self):
        """index.html decide "nao e' pendencia" comparando o TEXTO da acao. Se o
        servidor e a tela divergirem, a linha vira pendencia de mentira."""
        html = INDEX.read_text(encoding="utf-8")
        self.assertNotIn("'Sem Expectativa'", html)
        self.assertIn(f"a === '{ROTULO}'", _funcao("_csCatDe"))
        self.assertIn(f"d.a === '{ROTULO}'", _funcao("divPassa"))


if __name__ == "__main__":
    unittest.main()
