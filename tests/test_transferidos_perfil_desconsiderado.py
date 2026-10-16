# -*- coding: utf-8 -*-
"""Perfil desconsiderado também nos Transferidos (Bruna, 16/10/2026).

"Esse perfil se colocou em padrão: CVC OIE BRASIL - Relatório de Despesas,
nos transferidos também?"

Desde 07/10 a validação normal tira os <perfis_isentos> de <ancora_systur> da
entrada dos sistemas ancorados (Oracle). A revalidação pós-transferência não
lia a lista: o perfil virava EXCESSO e a aba Transferidos o mostrava como
"fora do padrão das duas áreas (a regra geral trata)" — e a regra geral
justamente o ignora. Agora:
  - o Processador (RevalidarTransferidos) o desconsidera do mesmo jeito;
  - o painel marca o acesso como desconsiderado: sai do resumo, e o detalhe e
    o Excel dizem "desconsiderado (perfil padrão)" em vez de sumir calado.
"""
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import visualizador.main as vm
from aplicacao.casos_de_uso.revalidar_transferidos import RevalidarTransferidos
from dominio.objetos_valor.sistema import Sistema
from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import PerfilEsperadoModel
from test_regressao_profunda_transferidos import _Base, _acesso, _ativo, _mov
from test_transferidos_tres_blocos import _BASE_JS, _funcao, _node, REG

ORA = Sistema.ORACLE_EBS.value
SYS = Sistema.SYSTUR.value
OIE = "CVC OIE BRASIL - Relatório de Despesas"      # com acento, como no extrato
ISENTOS = ["CVC OIE BRASIL - RELATORIO DE DESPESAS"]   # como no config
NODE = shutil.which("node")


class Revalidacao(_Base):

    def _cenario(self, mat, sistema=ORA):
        self._seed(
            PerfilEsperadoModel(cargo_codigo="100", cargo_descricao="ANALISTA",
                                sistema=sistema, perfil="CVC AP CONSULTA",
                                acesso_manual=False),
            _ativo(mat), _acesso(mat, sistema, "CVC AP CONSULTA"),
            _acesso(mat, sistema, OIE), _mov(mat))

    def test_sem_a_lista_continua_como_antes(self):
        self._cenario("31")
        RevalidarTransferidos(self.con).executar()
        self.assertIn((OIE, "EXCESSO"), self._sit("31"))

    def test_com_a_lista_o_perfil_sai_da_revalidacao(self):
        """⭐ O pedido: no Oracle o perfil padrão não entra na conta."""
        self._cenario("32")
        RevalidarTransferidos(self.con, ancora_systur_sistemas=[ORA],
                              ancora_systur_isentos=ISENTOS).executar()
        sit = self._sit("32")
        self.assertNotIn(OIE, {p for p, _ in sit})
        self.assertIn(("CVC AP CONSULTA", "MANTEM"), sit, "o resto não muda")

    def test_so_nos_sistemas_ancorados(self):
        """Mesma regra da validação: fora dos ancorados o perfil é avaliado."""
        self._cenario("33", sistema=SYS)
        RevalidarTransferidos(self.con, ancora_systur_sistemas=[ORA],
                              ancora_systur_isentos=ISENTOS).executar()
        self.assertIn((OIE, "EXCESSO"), self._sit("33"))

    def test_processador_passa_as_chaves_do_config(self):
        src = (Path(__file__).resolve().parent.parent / "src" / "processador"
               / "main.py").read_text(encoding="utf-8")
        i = src.index("RevalidarTransferidos(")
        trecho = src[i:i + 300]
        self.assertIn("validacao_ancora_systur_sistemas", trecho)
        self.assertIn("validacao_ancora_systur_isentos", trecho)


class PainelMarcaOAcesso(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cvc_desc_")
        self.db = os.path.join(self.tmp, "iam.db")
        ConexaoBancoDados(self.db).inicializar()
        self.cfg = os.path.join(self.tmp, "config.xml")
        Path(self.cfg).write_text(
            "<config><validacao><ancora_systur><sistemas>ORACLE_EBS</sistemas>"
            "<perfis_isentos>CVC OIE BRASIL - RELATORIO DE DESPESAS</perfis_isentos>"
            "</ancora_systur></validacao></config>", encoding="utf-8")
        self._orig = (vm.DB_PATH, vm.SISTEMA, vm.CONFIG_PATH)
        vm.DB_PATH, vm.SISTEMA, vm.CONFIG_PATH = self.db, "", self.cfg
        c = sqlite3.connect(self.db)
        try:
            for i, (sis, perfil) in enumerate([(ORA, OIE), (ORA, "CVC AP CONSULTA"),
                                               (SYS, OIE)]):
                c.execute("INSERT INTO divergencias (id, tipo, sistema, usuario, "
                          "nome_usuario, matricula, perfil_encontrado, "
                          "data_identificacao, resolvida, descricao) VALUES "
                          "(?, 'ACESSO_TRANSFERIDO', ?, 'u1', 'F', 'M1', ?, "
                          "'2026-10-01', 0, 'Mudança de gestor — x')", (f"d{i}", sis, perfil))
            c.commit()
        finally:
            c.close()

    def tearDown(self):
        vm.DB_PATH, vm.SISTEMA, vm.CONFIG_PATH = self._orig

    def test_so_o_perfil_padrao_do_oracle_vem_marcado(self):
        acs = vm.listar_transferidos()["lista"][0]["acessos"]
        marc = {(a["sis"], a["perfil"]): bool(a.get("desconsiderado")) for a in acs}
        self.assertTrue(marc[(ORA, OIE)])
        self.assertFalse(marc[(ORA, "CVC AP CONSULTA")])
        self.assertFalse(marc[(SYS, OIE)], "fora dos ancorados não é desconsiderado")

    def test_sem_config_nada_e_marcado(self):
        vm.CONFIG_PATH = os.path.join(self.tmp, "nao_existe.xml")
        acs = vm.listar_transferidos()["lista"][0]["acessos"]
        self.assertFalse(any(a.get("desconsiderado") for a in acs))


@unittest.skipUnless(NODE, "Node não disponível nesta máquina")
class TelaEPlanilha(unittest.TestCase):

    REG = dict(REG,
               acessos=[{"sis": "ORACLE_EBS", "login": "c1", "perfil": OIE, "dt": "",
                         "desconsiderado": True}],
               mantem=[], sobrou=[], excesso=[], falta=[],
               reval={"MANTEM": 0, "SOBROU": 0, "EXCESSO": 0, "FALTA": 0})

    def _js(self, corpo):
        return (_BASE_JS + "const DB = {meta: {multi_perfil_fora: ['ORACLE_EBS']}};\n"
                + f"{_funcao('_acessosPorSistema')}\n{_funcao('_transfResumoSis')}\n"
                + f"{_funcao('_transfMultiFora')}\n{_funcao('_transfDetalhe')}\n"
                + f"const d = {json.dumps(self.REG)};\n" + corpo)

    def test_fica_fora_do_resumo(self):
        out = _node(self._js("console.log(JSON.stringify(_transfResumoSis(d, _sisTodos(), "
                             "_transfMultiFora()).find(x => x.s === 'ORACLE_EBS')));"))
        ora = json.loads(out)
        self.assertEqual(ora["tem"], [])
        self.assertEqual(ora["st"], "nada")
        self.assertEqual(ora["login"], "c1", "o login da conta não se perde")

    def test_detalhe_diz_desconsiderado(self):
        html = _node(self._js("console.log(_transfDetalhe(d, d.acessos, []));"))
        self.assertIn("desconsiderado (perfil padrão)", html)
        self.assertNotIn("fora do padrão das duas áreas", html)

    def test_planilha_diz_desconsiderado(self):
        js = (_BASE_JS + f"{_funcao('_acessosPorSistema')}\n{_funcao('_transfChave')}\n"
              + f"const _recs = [{json.dumps(self.REG)}];\n"
              + "function _transfFiltrados(){ return _recs; }\nlet cap = null;\n"
              + "function baixarExcel(n, cols, linhas){ cap = {cols, linhas}; }\n"
              + f"{_funcao('exportarTransferidos')}\nexportarTransferidos();\n"
              + "console.log(JSON.stringify(cap));")
        cap = json.loads(_node(js))
        ic = cap["cols"].index("Situação do acesso")
        self.assertIn("desconsiderado (perfil padrão)", [l[ic] for l in cap["linhas"]])


if __name__ == "__main__":
    unittest.main()
