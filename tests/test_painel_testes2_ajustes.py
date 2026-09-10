# -*- coding: utf-8 -*-
"""Ajustes do retorno de teste da area ("Testes 2.pdf", 09/09/2026).

1. Troca de aba "perde os dados" (principalmente Transferidos). Causa: o
   servidor devolve 500 com um JSON valido ({"erro": ...}) e o `fetchAPI`
   cacheava essa resposta como se fosse dado — a aba ficava vazia em toda volta
   ate o banco mudar de token. E a Transferidos engolia a falha e dizia
   "Nenhuma transferencia detectada".
2. SYSTUR na Consulta: o acesso ambiguo ("Em Analise" que casa com N perfis do
   cargo) aparecia como N linhas; na Pendencias ja' era UMA linha com as opcoes.
3. Botao "D" da Consulta: acendia para todo desligado, inclusive quem nao tem
   nada a remover ("ele filtra mas nao tem nada a remover").

Roda as funcoes reais extraidas do index.html no Node. Pula se nao houver Node.
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

INDEX = (Path(__file__).resolve().parent.parent
         / "CVC_IAM_ANALYTICS" / "EXECUTAVEIS" / "REPORT" / "index.html")
NODE = shutil.which("node")


def _funcao(nome):
    html = INDEX.read_text(encoding="utf-8")
    i = html.index(f"function {nome}(")
    if html[i - 6:i] == "async ":
        i -= 6
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
                           encoding="utf-8", timeout=60)
        if r.returncode != 0:
            raise AssertionError(r.stderr)
        return json.loads(r.stdout.strip().splitlines()[-1])
    finally:
        os.unlink(caminho)


@unittest.skipUnless(NODE, "Node não disponível nesta máquina")
class ErroDoServidorNaoEntraNoCache(unittest.TestCase):

    def _rodar(self, respostas, chamadas):
        js = f"""
        let _cacheAPI = new Map(), _tokenDB = 'T1', n = 0;
        const respostas = {json.dumps(respostas)};
        global.fetch = async () => {{
          const r = respostas[Math.min(n++, respostas.length - 1)];
          return {{ok: r.ok, status: r.status, text: async () => r.body}};
        }};
        {_funcao('fetchAPI')}
        (async () => {{
          const out = [];
          for (let i = 0; i < {chamadas}; i++) {{
            try {{ out.push({{ok: await fetchAPI('/api/transferidos')}}); }}
            catch (e) {{ out.push({{erro: e.message}}); }}
          }}
          console.log(JSON.stringify({{out, fetches: n}}));
        }})();
        """
        return _node(js)

    def test_500_vira_erro_e_a_volta_a_aba_busca_de_novo(self):
        """⭐ O bug: a 1a leitura falha (500) e a 2a, mesmo com o servidor ja'
        bom, devolvia o erro cacheado."""
        r = self._rodar([{"ok": False, "status": 500, "body": '{"erro": "db locked"}'},
                         {"ok": True, "status": 200, "body": '{"lista": [1, 2]}'}], 2)
        self.assertIn("500", r["out"][0]["erro"])
        self.assertIn("db locked", r["out"][0]["erro"])
        self.assertEqual(r["out"][1]["ok"], {"lista": [1, 2]})
        self.assertEqual(r["fetches"], 2, "o erro nao pode ter sido servido do cache")

    def test_resposta_boa_continua_no_cache(self):
        r = self._rodar([{"ok": True, "status": 200, "body": '{"lista": [7]}'}], 3)
        self.assertEqual([o["ok"] for o in r["out"]], [{"lista": [7]}] * 3)
        self.assertEqual(r["fetches"], 1, "o cache por token deixou de funcionar")

    def test_corpo_de_erro_nao_json_tambem_vira_erro(self):
        r = self._rodar([{"ok": False, "status": 502, "body": "<html>gateway</html>"}], 1)
        self.assertIn("502", r["out"][0]["erro"])


class TransferidosDizQueFalhou(unittest.TestCase):
    """Mesma trava que a Desligados ganhou em 25/08."""

    def test_carga_marca_a_falha(self):
        corpo = _funcao("renderTransferidos")
        self.assertIn("_transfFalhou = true", corpo)
        self.assertNotIn("catch(e){ _transfRecs = []; }", corpo,
                         "voltou a engolir o erro calado")

    def test_falha_nao_deixa_o_contador_da_carga_anterior(self):
        """Print do "Testes 2.pdf": "69 a revisar" em cima de uma grid vazia."""
        corpo = _funcao("renderTransferidos")
        i = corpo.index("_transfFalhou = true")
        self.assertIn("transf-count", corpo[i:], "o catch tem de limpar o contador")
        self.assertIn("números indisponíveis", corpo[i:])

    def test_grid_vazia_distingue_falha_de_base_vazia(self):
        corpo = _funcao("pintarTransferidos")
        self.assertIn("_transfFalhou", corpo)
        self.assertIn("Não foi possível carregar os transferidos", corpo)


@unittest.skipUnless(NODE, "Node não disponível nesta máquina")
class AmbiguoNaConsultaIgualPendencias(unittest.TestCase):

    DIVS = [
        {"a": "Em Análise", "s": "Pendente", "sis": "SYSTUR",
         "pe": "SYSTUR_VENDAS", "pp": f"SYSTUR_PERFIL_{i}"} for i in range(1, 6)
    ]

    def _consolidar_e_texto(self, divs):
        fns = "\n".join(_funcao(n) for n in (
            "esc", "_perfNome", "_perfDedup", "_csListaPerfis", "_csDelta",
            "_csPerfilTxt", "_divsDisplayA"))
        js = f"""
        {fns}
        const dd = _divsDisplayA({json.dumps(divs)});
        console.log(JSON.stringify({{n: dd.length, txt: dd.map(_csPerfilTxt)}}));
        """
        return _node(js)

    def test_cinco_candidatos_viram_um_acesso(self):
        r = self._consolidar_e_texto(self.DIVS)
        self.assertEqual(r["n"], 1, "a Consulta voltaria a mostrar 5 linhas")

    def test_texto_diz_uma_de_n_opcoes_e_nao_faltam_n(self):
        """⭐ No SYSTUR a pessoa so' pode ter UM perfil — "Faltam 5" e' falso."""
        txt = self._consolidar_e_texto(self.DIVS)["txt"][0]
        self.assertIn("1 de 5 opções", txt)
        self.assertIn("SYSTUR_VENDAS", txt, "o que ela tem hoje sumiu")
        self.assertNotIn("Falta", txt)

    def test_nao_ambiguo_nao_muda(self):
        um = [{"a": "Alterar Perfil", "s": "Pendente", "sis": "SIG",
               "pe": "A", "pp": "B"}]
        txt = self._consolidar_e_texto(um)["txt"][0]
        self.assertIn("Falta", txt)
        self.assertNotIn("opções", txt)

    def test_drawer_resumo_e_contador_usam_a_consolidacao(self):
        self.assertIn("_divsDisplayA(u.divs)", _funcao("csRenderDrawerBody"))
        self.assertIn("_divsDisplayA(u.divs)", _funcao("_csMontarSub"))
        self.assertIn("const nPend = _divsDisplayA(u.divs)", _funcao("renderConsulta"))


class BotaoDDizOCaso(unittest.TestCase):

    def test_situacao_do_desligado_e_carregada(self):
        corpo = _funcao("_carregarHistMats")
        self.assertIn("_deslSit = new Map(", corpo)
        self.assertIn("x.tratado ? 'Tratado' : x.sit", corpo)

    def test_botao_d_explica_e_apaga_no_ok(self):
        corpo = _funcao("renderConsulta")
        self.assertIn("nada a remover", corpo)
        self.assertIn("' ok'", corpo)
        self.assertIn(".cs-aba-btn.d.ok{", INDEX.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
