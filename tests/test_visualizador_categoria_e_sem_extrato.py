# -*- coding: utf-8 -*-
"""Dois retornos da area de 25/08/2026, fixados como contrato.

1) CATEGORIA. Quem nao casa com identidade nenhuma vinha rotulado "Funcionário"
   — o painel afirmava um vinculo que ninguem apurou. Um login de franquia
   (AFLV0069), sem matricula e sem CPF, aparecia como CLT. O default passou a
   ser "Não identificado".

2) SISTEMA SEM EXTRATO. "Caso algum sistema nao carregue por completo, a
   aplicacao da algum alerta?" Nao dava — e o efeito e' pior que uma tela
   vazia: sem extrato, TODO usuario aparece como "sem mapeamento" naquele
   sistema, indistinguivel de "a matriz nao preve acesso". Foi o SIGOT.
"""
import io
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
import visualizador.main as vm


class CategoriaNaoInventaVinculo(unittest.TestCase):

    def test_vinculos_conhecidos(self):
        self.assertEqual(vm.rotulo_vinculo("FUNCIONARIO"), "Funcionário")
        self.assertEqual(vm.rotulo_vinculo("terceiro"), "Terceiro")
        self.assertEqual(vm.rotulo_vinculo(" Franqueado "), "Franqueado")
        self.assertEqual(vm.rotulo_vinculo("PRESTADOR"), "Prestador")

    def test_sem_vinculo_apurado_nao_vira_funcionario(self):
        """O caso do retorno: acesso orfao, sem vinculo nenhum."""
        for cru in (None, "", "   "):
            self.assertEqual(vm.rotulo_vinculo(cru), "Não identificado",
                             f"{cru!r} nao pode virar CLT")

    def test_vinculo_novo_no_rh_nao_vira_funcionario(self):
        """Vinculo que o painel ainda nao conhece: nao quebra, e tambem nao
        mente dizendo que e' CLT."""
        self.assertEqual(vm.rotulo_vinculo("ESTAGIARIO"), "Não identificado")


class AlertaDeSistemaSemExtrato(unittest.TestCase):

    CONFIG = """<?xml version='1.0' encoding='UTF-8'?>
<configuracao>
  <sistemas>
    <sistema id="SYSTUR"><nome>SYSTUR</nome><ativo>true</ativo></sistema>
    <sistema id="SIGOT"><nome>SIGOT</nome><ativo>true</ativo></sistema>
    <sistema id="OPERA"><nome>OPERA_OPERACIONAL</nome><ativo>false</ativo></sistema>
  </sistemas>
</configuracao>"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, "iam.db")
        ConexaoBancoDados(self.db).inicializar()
        self.cfg = os.path.join(self.tmp, "config.xml")
        with io.open(self.cfg, "w", encoding="utf-8") as f:
            f.write(self.CONFIG)
        self._db_orig, self._cfg_orig = vm.DB_PATH, vm.CONFIG_PATH
        vm.DB_PATH, vm.CONFIG_PATH = self.db, self.cfg

    def tearDown(self):
        vm.DB_PATH, vm.CONFIG_PATH = self._db_orig, self._cfg_orig

    def _acesso(self, sistema):
        c = sqlite3.connect(self.db)
        try:
            cols = [r[1] for r in c.execute("PRAGMA table_info(acessos_sistemas)")]
            valores = {"sistema": sistema, "usuario": "u1", "perfil": "P1"}
            usar = [k for k in valores if k in cols]
            c.execute(f"INSERT INTO acessos_sistemas ({','.join(usar)}) "
                      f"VALUES ({','.join('?' * len(usar))})",
                      [valores[k] for k in usar])
            c.commit()
        finally:
            c.close()

    def test_sistema_ligado_e_sem_acesso_e_apontado(self):
        self._acesso("SYSTUR")
        self.assertEqual(vm.sistemas_sem_extrato(), ["SIGOT"])

    def test_sistema_desligado_no_config_nao_alerta(self):
        """OPERA_OPERACIONAL esta com ativo=false: nao ter extrato e' o esperado."""
        self._acesso("SYSTUR")
        self._acesso("SIGOT")
        self.assertEqual(vm.sistemas_sem_extrato(), [])

    def test_base_sem_nenhum_acesso_aponta_todos_os_ativos(self):
        self.assertEqual(sorted(vm.sistemas_sem_extrato()), ["SIGOT", "SYSTUR"])

    def test_falha_de_leitura_nao_inventa_alerta(self):
        """Consulta quebrada nao pode virar 'todos os sistemas sem extrato' na
        tela — avisa no log e devolve vazio."""
        c = sqlite3.connect(self.db)
        try:
            c.execute("DROP TABLE IF EXISTS acessos_sistemas")
            c.execute("CREATE TABLE acessos_sistemas (outra_coisa TEXT)")
            c.commit()
        finally:
            c.close()
        buf = io.StringIO()
        with redirect_stdout(buf):
            r = vm.sistemas_sem_extrato()
        self.assertEqual(r, [])
        self.assertIn("[alerta]", buf.getvalue())

    def test_config_ilegivel_nao_derruba_o_painel(self):
        vm.CONFIG_PATH = os.path.join(self.tmp, "nao_existe.xml")
        buf = io.StringIO()
        with redirect_stdout(buf):
            r = vm.sistemas_sem_extrato()
        self.assertEqual(r, [])
        self.assertIn("[alerta]", buf.getvalue())


class CategoriaVemDoSqlSemInventar(unittest.TestCase):
    """O defeito real morava no SQL, nao na funcao de rotulo.

    `COALESCE(r.tipo_vinculo,'FUNCIONARIO')` sobre um LEFT JOIN nao distingue
    "linha existe no RH e a coluna esta nula" de "NAO HA linha no RH": nos dois
    casos devolve 'FUNCIONARIO'. Como o acesso orfao cai justamente no segundo
    caso, ele chegava na tela como CLT mesmo depois de a funcao de rotulo ser
    corrigida. Este teste passa pelo SQL de verdade."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, "iam.db")
        ConexaoBancoDados(self.db).inicializar()
        self._db_orig, self._sis_orig = vm.DB_PATH, vm.SISTEMA
        vm.DB_PATH, vm.SISTEMA = self.db, ""
        c = sqlite3.connect(self.db)
        try:
            # bi_divergencias e' materializada pelo painel a partir do banco do
            # Processador; aqui basta a forma que o SQL da Consulta le
            c.executescript(
                "CREATE TABLE IF NOT EXISTS bi_divergencias ("
                " id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT, sistema TEXT,"
                " usuario TEXT, nome_usuario TEXT, matricula TEXT,"
                " perfil_encontrado TEXT, perfil_esperado TEXT, descricao TEXT,"
                " motivo TEXT, data_identificacao TEXT, resolvida INTEGER,"
                " acao TEXT, origem TEXT, login TEXT);")
            # uma pessoa do RH e um acesso orfao (login de franquia, sem RH)
            cols = [r[1] for r in c.execute("PRAGMA table_info(rh_ativos)")]
            base = {"matricula": "34532779", "nome": "MICHELE COSTA",
                    "cpf": "38930677878", "cargo_descricao": "ESPECIALISTA",
                    "situacao": "ATIVO"}
            usar = [k for k in base if k in cols]
            c.execute(f"INSERT INTO rh_ativos ({','.join(usar)}) "
                      f"VALUES ({','.join('?' * len(usar))})", [base[k] for k in usar])
            for usuario, matricula in (("mcapolupo", "34532779"), ("AFLV0069", "")):
                c.execute(
                    "INSERT INTO bi_divergencias (tipo, sistema, usuario, nome_usuario, "
                    "matricula, perfil_encontrado, perfil_esperado, acao, resolvida, "
                    "data_identificacao) VALUES (?,?,?,?,?,?,?,?,0,?)",
                    ("OK", "SYSTUR", usuario, usuario, matricula, "P1", "P1",
                     "Aderente", "2026-08-25"))
            c.commit()
        finally:
            c.close()

    def tearDown(self):
        vm.DB_PATH, vm.SISTEMA = self._db_orig, self._sis_orig

    def _categorias(self):
        base = vm._montar_base()
        return {u["u"]: u["vinc"] for u in base["users"]}

    def test_acesso_com_dono_no_rh_segue_funcionario(self):
        self.assertEqual(self._categorias().get("mcapolupo"), "Funcionário")

    def test_acesso_orfao_nao_e_rotulado_como_clt(self):
        """AFLV0069: o print que a area mandou em 25/08."""
        self.assertEqual(self._categorias().get("AFLV0069"), "Não identificado")


class OrigemDizQualRegraValidou(unittest.TestCase):
    """"Qual regra afirma que o franqueado esta no perfil correto?" (25/08/2026)

    O dado sempre existiu — `origem_matriz` guarda ESPELHO_FRANQUEADO,
    ESPELHO_PRESTADOR, ESPELHO — mas a tela so' traduzia MATRIZ e CCO: todo o
    resto virava "—". Eram 2.088 linhas mudas na base de 05/08 (780 franqueado,
    709 prestador, 599 SIG)."""

    def test_matriz_e_cco_seguem_iguais(self):
        self.assertEqual(vm.rotulo_origem("MATRIZ", "SYSTUR"), "Matriz SYSTUR")
        self.assertEqual(vm.rotulo_origem("CCO"), "Matriz CCO")

    def test_espelho_diz_a_populacao(self):
        self.assertEqual(vm.rotulo_origem("ESPELHO_FRANQUEADO"),
                         "Espelho — franqueados")
        self.assertEqual(vm.rotulo_origem("ESPELHO_PRESTADOR"),
                         "Espelho — prestadores")
        self.assertEqual(vm.rotulo_origem("ESPELHO"), "Espelho — mesma área")

    def test_terceiro_usa_a_chave_que_o_motor_grava(self):
        """O motor escreve ESPELHO_TERC (não _TERCEIRO) — pegadinha real:
        com a chave 'errada' no mapa o rótulo sumia calado para terceiros."""
        self.assertEqual(vm.rotulo_origem("ESPELHO_TERC"), "Espelho — terceiros")
        self.assertEqual(vm.rotulo_origem("ESPELHO_TERCEIRO"), "Espelho — terceiros")

    def test_origem_desconhecida_continua_travessao(self):
        for org in ("", None, "COISA_NOVA"):
            self.assertEqual(vm.rotulo_origem(org), "—")


if __name__ == "__main__":
    unittest.main()
