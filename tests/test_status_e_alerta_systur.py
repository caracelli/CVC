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

    def _txt(self, d, fora=None):
        """`fora` = sistemas ISENTOS da regra, como o servidor os manda em
        DB.meta.multi_perfil_fora. None = sem DB nenhum, que e' como esta
        funcao roda isolada aqui — e como o painel pode chama-la antes de
        montar o DB."""
        db = ("" if fora is None else
              "const DB = {meta: {multi_perfil_fora: "
              + json.dumps(fora) + "}};\n")
        js = (db
              + "const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;')"
              ".replace(/>/g,'&gt;').replace(/\"/g,'&quot;');\n"
              f"{_funcao('_csListaPerfis')}\n{_funcao('_csDelta')}\n"
              f"{_funcao('_csPerfilTxt')}\n"
              f"console.log(_csPerfilTxt({json.dumps(d)}));")
        return _node(js)

    def test_sistema_isento_nao_recebe_o_alerta(self):
        """Achado na validacao visual de 23/09/2026: a PRISCILA (90001455),
        ADERENTE com exatamente os 4 perfis do Oracle que a funcao dela preve,
        levava um "⚠ Usuario com mais de um perfil (4)". O alerta contava
        perfis e nada mais, sem saber que o Oracle esta' FORA da regra — e o
        texto dele afirma "a regra da area e um perfil por pessoa por
        sistema", o oposto do que a area disse sobre o Oracle."""
        d = {"sis": "ORACLE_EBS", "pe": "P_UM, P_DOIS", "pp": "P_UM"}
        self.assertNotIn("mais de um perfil", self._txt(d, fora=["ORACLE_EBS"]))
        self.assertIn("mais de um perfil", self._txt(d, fora=["SIG"]),
                      "isento e' so' quem esta' na lista")

    def test_sem_DB_a_regra_vale_para_todos(self):
        """⭐ Esta funcao e' exercitada ISOLADA no node (os testes acima), e o
        painel pode chama-la antes de montar o DB. Ler `DB.meta` direto
        quebrou 25 testes com "DB is not defined" em 23/09 — e quebraria o
        painel no boot. Sem DB, vale o comportamento anterior."""
        self.assertIn("mais de um perfil",
                      self._txt({"sis": "ORACLE_EBS", "pe": "A, B", "pp": "A"}))

    def test_dois_perfis_alerta(self):
        html = self._txt({"sis": "SYSTUR", "pe": "P_UM, P_DOIS", "pp": "P_UM"})
        self.assertIn("mais de um perfil", html)
        self.assertIn("(2)", html, "o número de perfis entra no alerta")

    def test_um_perfil_nao_alerta(self):
        self.assertNotIn("mais de um perfil",
                         self._txt({"sis": "SYSTUR", "pe": "P_UM", "pp": "P_UM"}))

    def test_vale_para_todos_os_sistemas(self):
        """⭐ MUDANÇA DE ESCOPO (22/09/2026). Em 17/09 a regra era só do SYSTUR e
        este teste exigia o CONTRÁRIO: que o SIG não alertasse. A área fechou a
        decisão ("mais de um perfil não pode ficar nada como aderente") e o
        usuário estendeu a todos os sistemas, ciente do volume — medido em
        22/09: 419 linhas Aderentes viram pendência (SIG 197, ORACLE_EBS 164,
        SYSTUR 58)."""
        self.assertIn("mais de um perfil",
                      self._txt({"sis": "SIG", "pe": "P_UM, P_DOIS", "pp": "P_UM"}))

    def test_o_texto_segue_o_motor(self):
        """Tela e motor não podem dizer coisas diferentes. Quem cobra é o motor
        (motivo MAIS_DE_UM_PERFIL); o alerta só relata o que ele decidiu."""
        com = self._txt({"sis": "SYSTUR", "pe": "P_UM, P_DOIS", "pp": "P_UM",
                         "motc": "MAIS_DE_UM_PERFIL"})
        self.assertIn("entrou como pendência", com)
        self.assertNotIn("não vira pendência", com)
        # flag do config desligada: o motor não marca, e o aviso volta a ser
        # informativo (a decisão de 28/08, "VER sempre, COBRAR com a flag")
        sem = self._txt({"sis": "SYSTUR", "pe": "P_UM, P_DOIS", "pp": "P_UM"})
        self.assertIn("não vira pendência", sem)


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(NODE, "Node não disponível nesta máquina")
class RotuloNaFilaDePendencias(unittest.TestCase):
    """Área, 22/09: a linha entra em pendência "como usuário com mais de um
    perfil". Na fila, "Em Análise" sozinho não diz o que aconteceu — era
    justamente o que ela queria enxergar."""

    def _js(self, *funcoes):
        # esc simplificado: o que estes testes verificam e o ROTULO, nao o
        # escape (esse ja tem cobertura propria nos testes do painel).
        esc = 'const esc = s => String(s);'
        css = "const TIPO_CSS = {" + chr(39) + "EM_ANALISE" + chr(39) + ": "
        css += chr(39) + "b-em-analise" + chr(39) + "};"
        partes = [esc, css] + [_funcao(f) for f in funcoes]
        return chr(10).join(partes) + chr(10)

    def test_badge_nomeia_a_regra(self):
        js = self._js("motIcone", "tipoBadge")
        html = _node(js + "console.log(tipoBadge('EM_ANALISE','Em Análise','',"
                          "'MAIS_DE_UM_PERFIL'));")
        self.assertIn("Mais de um perfil", html)
        self.assertNotIn(">Em Análise<", html)
        self.assertIn("b-em-analise", html, "o tipo no dado continua EM_ANALISE")

    def test_outros_motivos_nao_mudam(self):
        """Não-regressão: o badge das outras pendências fica como estava."""
        js = self._js("motIcone", "tipoBadge")
        html = _node(js + "console.log(tipoBadge('EM_ANALISE','Em Análise','',"
                          "'CONTA_INDEFINIDA'));")
        self.assertIn(">Em Análise<", html)

    def test_badge_decide_pelo_codigo_e_nao_pela_frase(self):
        """⭐ O `mot` que chega à tela é a FRASE montada pelo servidor; o código
        cru vem em `motc`. Casar por frase quebraria no dia em que alguém
        melhorasse a redação do texto."""
        js = self._js("motIcone", "tipoBadge")
        # a frase no lugar do código: NÃO pode virar rótulo
        html = _node(js + "console.log(tipoBadge('EM_ANALISE','Em Análise',"
                          "'Usuario com mais de um perfil no MESMO sistema.',''));")
        self.assertIn(">Em Análise<", html)

    def test_motivo_encadeado_ainda_nomeia_a_regra(self):
        """O motor encadeia ("MAIS_DE_UM_PERFIL | PERFIL_EXCESSIVO") — medido em
        22/09: 134 das 419 linhas. O rótulo não pode se perder nelas."""
        js = self._js("motIcone", "tipoBadge")
        html = _node(js + "console.log(tipoBadge('EM_ANALISE','Em Análise','',"
                          "'MAIS_DE_UM_PERFIL | PERFIL_EXCESSIVO'));")
        self.assertIn("Mais de um perfil", html)
