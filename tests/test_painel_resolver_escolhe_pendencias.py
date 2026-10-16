# -*- coding: utf-8 -*-
"""Resolver pendência: escolher QUAIS (Bruna, 16/10/2026).

"Quando tem mais de um sistema, se clica no primeiro ele acaba resolvendo as
duas pendências. Quando tiver duas pendências na tela de pendência, tem como
deixar claro qual pendência está sendo tratada, ou selecionar qual pendência
vai ser tratada?"

O botão da linha da PESSOA (e o "todo o sistema") resolvia tudo sem mostrar o
quê. Agora o modal lista cada pendência com uma caixa — nenhuma marcada — e:
  - nada marcado: não resolve;
  - todas marcadas: UMA chamada no escopo do botão, igual a antes;
  - parte: uma chamada por acesso marcado, com a mesma tratativa.
"""
import json
import re
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_transferidos_tres_blocos import _funcao, _node  # noqa: E402

NODE = shutil.which("node")
INDEX = (Path(__file__).resolve().parent.parent / "CVC_IAM_ANALYTICS" / "EXECUTAVEIS"
         / "REPORT" / "index.html").read_text(encoding="utf-8")

# Pessoa do print: pendência no SYSTUR e no SIG (o SIG com um "Em Análise" de
# duas opções, que é UM acesso só).
USER = {"u": "90000266", "n": "ALEXANDRA", "divs": [
    {"sis": "SYSTUR", "pe": "B2B_PROJETOS", "pp": "", "a": "Alterar Perfil"},
    {"sis": "SIG", "pe": "PERFIL_X", "pp": "OPC1", "a": "Em Análise"},
    {"sis": "SIG", "pe": "PERFIL_X", "pp": "OPC2", "a": "Em Análise"},
    {"sis": "IC_INTEGRADOR_CONTABIL", "pe": "IC_CONSULTA", "pp": "", "a": "Aderente"},
]}

_STUBS = r"""
const esc = s => String(s == null ? '' : s);
let _JIRA_ATIVO = false;
const DB = {users: [__USER__]};
let MODAL = '';
function _modal(h){ MODAL = h; }
function _campoTratativa(){ return '<div id="campos"></div>'; }
function _btnJira(){ return ''; }
function _preencherMotivos(){} function _ligarBtnJiraPendencia(){}
function setTimeout(){}
const CAMPOS = {'res-ticket': {value: 'IAM-9'}, 'res-url': {value: ''},
                'res-desc': {value: 'parecer'}, 'res-motivo': {value: 'Acesso Indevido'},
                'res-err': {textContent: ''}};
let CHKS = [];
const document = {
  getElementById: id => CAMPOS[id] || null,
  querySelectorAll: sel => sel === '.res-chk' ? CHKS : [],
};
function _montarChks(marcados){
  const n = (MODAL.match(/class="res-chk"/g) || []).length;
  CHKS = Array.from({length: n}, (_, i) => ({value: String(i), checked: marcados.includes(i)}));
}
function _validarTratativa(){ return true; }
function fecharModal(){} async function proc(){}
function invalidarCacheAPI(){} function renderMatrix(){} function aplicarKPIs(){}
async function refreshDB(){}
let ALERTA = ''; function alert(m){ ALERTA = m; }
const ENVIOS = [];
async function fetch(url, op){ ENVIOS.push(JSON.parse(op.body));
  return {json: async () => ({ok: true})}; }
let _resAlvo = null, _resSistema = '', _resPerfil = '', _resItens = [];
"""


@unittest.skipUnless(NODE, "Node não disponível nesta máquina")
class EscolherPendencias(unittest.TestCase):

    def _rodar(self, corpo):
        fns = "\n".join(_funcao(n) for n in (
            "_perfChave", "abrirResolver", "_resRotuloPerfis", "_resMarcarTodas",
            "_resAlvosMarcados"))
        # o extrator pega a partir de "function": o async fica de fora
        fns += "\nasync " + _funcao("confirmarResolucao")
        # as variaveis globais do painel (let _resAlvo etc.) ficam nos stubs
        js = _STUBS.replace("__USER__", json.dumps(USER)) + fns + "\n(async () => {\n" \
            + corpo + "\n})();"
        return _node(js)

    def test_pessoa_com_duas_pendencias_lista_as_duas_sem_marcar(self):
        """⭐ O print: SYSTUR e SIG. O modal mostra as duas, nenhuma marcada.
        O "Em Análise" de duas opções é UM acesso; o aderente não entra."""
        out = self._rodar("abrirResolver('90000266'); console.log(MODAL);")
        self.assertEqual(out.count('class="res-chk"'), 2)
        self.assertIn("SYSTUR</b> · B2B_PROJETOS", out)
        self.assertIn("SIG</b> · PERFIL_X", out)
        self.assertNotIn("IC_CONSULTA", out)
        self.assertNotIn("checked", out)
        self.assertIn("escolha quais resolver", out)

    def test_nada_marcado_nao_resolve(self):
        out = self._rodar("abrirResolver('90000266'); _montarChks([]);"
                          "await confirmarResolucao();"
                          "console.log(JSON.stringify({n: ENVIOS.length, e: CAMPOS['res-err'].textContent}));")
        r = json.loads(out)
        self.assertEqual(r["n"], 0)
        self.assertIn("Marque", r["e"])

    def test_so_uma_marcada_resolve_so_ela(self):
        out = self._rodar("abrirResolver('90000266'); _montarChks([1]);"
                          "await confirmarResolucao(); console.log(JSON.stringify(ENVIOS));")
        env = json.loads(out)
        self.assertEqual([(e["sistema"], e["perfil"]) for e in env], [("SIG", "PERFIL_X")])

    def test_todas_marcadas_e_uma_chamada_so_como_antes(self):
        out = self._rodar("abrirResolver('90000266'); _montarChks([0, 1]);"
                          "await confirmarResolucao(); console.log(JSON.stringify(ENVIOS));")
        env = json.loads(out)
        self.assertEqual(len(env), 1)
        self.assertEqual((env[0]["sistema"], env[0]["perfil"]), ("", ""),
                         "todas = o escopo do botão (pessoa inteira), o registro de sempre")

    def test_marcar_todas_alterna(self):
        out = self._rodar("abrirResolver('90000266'); _montarChks([0]); _resMarcarTodas();"
                          "const a = CHKS.map(c => c.checked); _resMarcarTodas();"
                          "console.log(JSON.stringify([a, CHKS.map(c => c.checked)]));")
        self.assertEqual(json.loads(out), [[True, True], [False, False]])

    def test_uma_pendencia_so_nao_pede_escolha(self):
        """Com uma pendência não há o que escolher: o modal diz qual é."""
        out = self._rodar("abrirResolver('90000266', 'SYSTUR'); console.log(MODAL);")
        self.assertNotIn('class="res-chk"', out)
        self.assertIn("B2B_PROJETOS", out)

    def test_acesso_da_sub_linha_continua_direto(self):
        out = self._rodar("abrirResolver('90000266', 'SIG', 'PERFIL_X'); _montarChks([]);"
                          "await confirmarResolucao(); console.log(JSON.stringify(ENVIOS));")
        env = json.loads(out)
        self.assertEqual([(e["sistema"], e["perfil"]) for e in env], [("SIG", "PERFIL_X")])

    def test_lista_longa_de_perfis_fica_curta(self):
        """SIG com dezenas de perfis numa linha (FERNANDA 30804): o rotulo mostra
        os dois primeiros e quantos faltam."""
        out = self._rodar("console.log(_resRotuloPerfis('A, B, C, D'), '|', _resRotuloPerfis('X'));")
        self.assertEqual(out.strip(), "A, B +2 perfis | X")

    def test_jira_segue_a_escolha(self):
        corpo = _funcao("abrirChamadoJiraPendencia")
        self.assertIn("res-chk", corpo)
        self.assertIn("marque uma pendência ou todas", corpo)


if __name__ == "__main__":
    unittest.main()
