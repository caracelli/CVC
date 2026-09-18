# -*- coding: utf-8 -*-
"""Retorno da área de 17/09/2026, itens 2 e 3 do "Aplicação_17_09.docx".

ITEM 3 — "Esses casos onde não tiver mapeamento nas matriz, trazer um status:
sem perfis mapeados e não como aderente." O print do documento (PAULO HENRIQUE)
mostra a linha com "7 sem mapeamento" e o pino verde "Aderente".
Por que estava assim: o pino nasceu com "Aderente" como `else` (o mesmo defeito
que a área apontou em 25/08 no BRCVCSRVSYSINT, corrigido para "Resolvido"), e o
NAO_MAPEADO entrou junto com OK no status da linha (10/09) para não virar
"Pendente". Aderência no motor SEMPRE foi POR SISTEMA ("REGRA OK (por sistema)"),
então quem não tem um único acesso aderente não pode herdar o rótulo.

ITEM 2 — "todos colaboradores do systur que tiver mais de um perfil deve vir com
alerta: Usuário com mais de um acesso. Obs.: usuários do systur não podem ter
mais de um perfil." Segue a decisão de 28/08 sobre perfil excessivo: VER sempre,
COBRAR só com a flag do config — o alerta é informativo e NÃO cria pendência.
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


def _node(js):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                     encoding="utf-8") as f:
        f.write(js)
        caminho = f.name
    try:
        r = subprocess.run([NODE, caminho], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        if r.returncode:
            raise AssertionError(r.stderr)
        return r.stdout
    finally:
        os.unlink(caminho)


class StatusNoServidor(unittest.TestCase):
    """O status da LINHA sai do servidor — se ele disser "Aderente", a tela
    inteira (grid, pino e export) repete."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cvc_status_")
        self.db = os.path.join(self.tmp, "iam.db")
        ConexaoBancoDados(self.db).inicializar()
        self._orig = (vm.DB_PATH, vm.SISTEMA)
        vm.DB_PATH, vm.SISTEMA, vm._BASE = self.db, "", None
        c = sqlite3.connect(self.db)
        try:
            cols = [r[1] for r in c.execute("PRAGMA table_info(validacao_acessos)")]
            def ins(mat, nome, sistema, status, motivo=None):
                vals = {"matricula": mat, "nome": nome, "cpf": mat.rjust(11, "0"),
                        "sistema": sistema, "perfil_esperado": "", "perfil_atual": "",
                        "status": status, "situacao_acao": "OK",
                        "motivo_status": motivo,
                        "dt_processamento": "2026-09-18 10:00:00"}
                usar = [k for k in vals if k in cols]
                c.execute(f"INSERT INTO validacao_acessos ({','.join(usar)}) "
                          f"VALUES ({','.join('?' * len(usar))})", [vals[k] for k in usar])
            ins("1", "SEM MAPEAMENTO", "", "NAO_MAPEADO", "SEM_EXPECTATIVA_RELEVANTE")
            ins("2", "CONFORME", "SYSTUR", "OK")
            c.commit()
        finally:
            c.close()
        vm.garantir_estrutura(force=True)

    def tearDown(self):
        vm.DB_PATH, vm.SISTEMA = self._orig
        vm._BASE = None

    def _status(self, matricula):
        db = vm.construir_db()
        u = [x for x in db["users"] if x["m"] == matricula][0]
        return [d["s"] for d in u["divs"]]

    def test_nao_mapeado_nao_e_aderente(self):
        self.assertEqual(self._status("1"), ["Sem perfis mapeados"])

    def test_quem_tem_acesso_aderente_continua_aderente(self):
        self.assertEqual(self._status("2"), ["Aderente"])

    def test_nao_mapeado_nunca_vira_pendente(self):
        """A correção de 10/09 não pode ser desfeita: informativo, não pendência."""
        self.assertNotIn("Pendente", self._status("1"))


@unittest.skipUnless(NODE, "Node não disponível nesta máquina")
class PinoEColunaStatus(unittest.TestCase):

    def _pino(self, divs):
        return json.loads(_node(f"{_funcao('_csPino')}\n"
                                f"console.log(JSON.stringify(_csPino({{divs:{json.dumps(divs)}}})));"))

    def _coluna(self, divs):
        return _node(f"{_funcao('_csDisp')}\n"
                     f"console.log(_csDisp(14, {{divs:{json.dumps(divs)}}}));").strip()

    NM = {"a": "Não Mapeado", "s": "Sem perfis mapeados", "sis": ""}
    OK = {"a": "Aderente", "s": "Aderente", "sis": "SYSTUR"}
    INC = {"a": "Incluir Acesso", "s": "Aderente", "sis": "SIG"}
    PEND = {"a": "Alterar Perfil", "s": "Pendente", "sis": "SIG"}

    def test_so_sem_mapeamento_nao_e_aderente(self):
        self.assertEqual(self._pino([self.NM])["lbl"], "Sem perfis mapeados")
        self.assertEqual(self._coluna([self.NM]), "Sem perfis mapeados")

    def test_aderente_em_um_sistema_segue_aderente(self):
        """Aderência é POR SISTEMA: um OK basta, mesmo sem mapeamento nos outros
        (é o caso do print da PRISCILA: 2 encontrados, 3 sem mapeamento)."""
        self.assertEqual(self._pino([self.OK, self.NM])["lbl"], "Aderente")
        self.assertEqual(self._coluna([self.OK, self.NM]), "Aderente")

    def test_pendencia_e_inclusao_continuam_na_frente(self):
        self.assertEqual(self._pino([self.PEND, self.NM])["lbl"], "1 pendente")
        self.assertEqual(self._pino([self.INC, self.NM])["lbl"], "Incluir acessos")

    def test_pino_e_coluna_dizem_a_mesma_coisa(self):
        """Se divergirem, o funil oferece valor que a coluna não mostra."""
        for divs in ([self.NM], [self.OK, self.NM], [self.PEND], [self.INC]):
            p, c = self._pino(divs)["lbl"], self._coluna(divs)
            if p.endswith("pendente") or p.endswith("pendentes"):
                p = "Pendente"
            self.assertEqual(p, c, divs)


@unittest.skipUnless(NODE, "Node não disponível nesta máquina")
class AlertaDeMaisDeUmPerfilNoSystur(unittest.TestCase):

    def _txt(self, d):
        js = ("const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;')"
              ".replace(/>/g,'&gt;').replace(/\"/g,'&quot;');\n"
              f"{_funcao('_csListaPerfis')}\n{_funcao('_csDelta')}\n"
              f"{_funcao('_csPerfilTxt')}\n"
              f"console.log(_csPerfilTxt({json.dumps(d)}));")
        return _node(js)

    def test_systur_com_dois_perfis_alerta(self):
        html = self._txt({"sis": "SYSTUR", "pe": "P_UM, P_DOIS", "pp": "P_UM"})
        self.assertIn("mais de um acesso", html)

    def test_systur_com_um_perfil_nao_alerta(self):
        self.assertNotIn("mais de um acesso",
                         self._txt({"sis": "SYSTUR", "pe": "P_UM", "pp": "P_UM"}))

    def test_outro_sistema_nao_alerta(self):
        """A regra é do SYSTUR (área, 17/09). No SIG ter vários perfis é normal —
        medido em 18/09: 1.048 pessoas."""
        self.assertNotIn("mais de um acesso",
                         self._txt({"sis": "SIG", "pe": "P_UM, P_DOIS", "pp": "P_UM"}))

    def test_o_alerta_nao_inventa_pendencia(self):
        """Informativo, como o perfil excessivo desde 28/08: o texto diz isso."""
        html = self._txt({"sis": "SYSTUR", "pe": "P_UM, P_DOIS", "pp": "P_UM"})
        self.assertIn("não vira pendência", html)


if __name__ == "__main__":
    unittest.main()
