# -*- coding: utf-8 -*-
"""Nenhuma aba pode rebaixar megabytes que ja' estao na mao.

Retorno da area (28/08/2026, Teams): "ele da umas travadas e so' fechando tudo
e abrindo de novo".

O refresh condicional (commit anterior) resolveu `/api/dados`, mas nao era o
unico peso — e o maior nem estava nele. Medido no painel dos 7 sistemas:
    /api/dados        5,48 MB
    /api/desligados   7,28 MB
    /api/historico    5,37 MB
`_carregarHistMats()` busca os DOIS ultimos e e' chamado ao abrir a CONSULTA,
a aba que ela mais usa: abrir a Consulta custava ~18 MB. A aba Desligados
custava 7,28 MB a cada visita.

MEDIDO, volta pelas 8 abas (todos os endpoints, nao so /api/dados):
    antes  — 69,14 MB  |  6,8s
    depois — 18,13 MB  |  2,2s        (-74% de trafego, -68% de tempo)
    Consulta 3.132ms -> 1.512ms · Desligados 1.337ms -> 103ms

Duas decisoes deste commit tem armadilha embutida, e os testes as travam:
  1. o cache guarda TEXTO, nao o objeto — o Historico MUTA o que recebe
     (`r._i = i` em cada registro);
  2. a rede de seguranca e' por TEMPO, nao por contagem — `showPage` chama
     refreshDB a cada troca de aba, entao contar ciclos disparava o download
     completo a cada 6 cliques, justo quando a pessoa navega rapido.
"""
import re
import unittest
from pathlib import Path

INDEX = (Path(__file__).resolve().parent.parent
         / "CVC_IAM_ANALYTICS" / "EXECUTAVEIS" / "REPORT" / "index.html")

PESADOS = ("/api/desligados", "/api/historico")


def _html():
    return INDEX.read_text(encoding="utf-8")


def _corpo(nome):
    html = _html()
    i = html.index(f"function {nome}(")
    j, nivel = html.index("{", i), 0
    for k in range(j, len(html)):
        if html[k] == "{":
            nivel += 1
        elif html[k] == "}":
            nivel -= 1
            if nivel == 0:
                return html[i:k + 1]
    raise AssertionError(f"{nome} nao fecha")


class EndpointPesadoPassaPeloCache(unittest.TestCase):

    def test_existe_o_fetch_com_cache(self):
        self.assertIn("async function fetchAPI(", _html())

    def test_nenhum_endpoint_pesado_e_buscado_cru(self):
        """Um `fetch('/api/desligados')` solto anula o ganho na hora."""
        html = _html()
        for ep in PESADOS:
            crus = re.findall(r"fetch\('" + re.escape(ep) + r"'\)", html)
            self.assertEqual(crus, [], f"{ep} buscado sem cache em {len(crus)} ponto(s)")

    def test_a_consulta_nao_puxa_12MB(self):
        """`_carregarHistMats` roda ao abrir a Consulta e busca os DOIS
        endpoints pesados — era o caminho mais caro do painel."""
        corpo = _corpo("_carregarHistMats")
        self.assertIn("fetchAPI('/api/historico')", corpo)
        self.assertIn("fetchAPI('/api/desligados')", corpo)

    def test_cache_e_chaveado_pelo_token(self):
        corpo = _corpo("fetchAPI")
        self.assertIn("_tokenDB", corpo,
                      "sem o token o cache serviria dado velho para sempre")

    def test_cache_guarda_TEXTO_e_nao_o_objeto(self):
        """⭐ O consumidor MUTA o que recebe: `renderHistorico` escreve
        `r._i = i` em cada registro. Entregar o mesmo objeto duas vezes
        obrigaria a auditar todo consumidor futuro."""
        corpo = _corpo("fetchAPI")
        self.assertIn(".text()", corpo)
        self.assertIn("JSON.parse", corpo)
        self.assertNotIn("await r.json()", corpo)

    def test_o_consumidor_realmente_muta(self):
        """Se um dia deixar de mutar, o teste acima vira dogma sem motivo —
        este aqui documenta que o motivo existe HOJE."""
        self.assertRegex(_html(), r"_histRecs\.forEach\(\(r,\s*i\)\s*=>\s*r\._i\s*=\s*i\)")


class RedeDeSegurancaPorTempo(unittest.TestCase):

    def test_nao_conta_ciclos(self):
        """Contar ciclos punia justamente quem navega rapido: `showPage` chama
        refreshDB a cada troca, entao 6 cliques = 5,48 MB baixados de novo.
        Medido antes da correcao: 2x /api/dados numa volta pelas 8 abas."""
        html = _html()
        self.assertNotIn("_FORCA_A_CADA", html)
        self.assertIn("_FORCA_APOS_MS", html)

    def test_a_janela_e_de_um_minuto(self):
        m = re.search(r"const _FORCA_APOS_MS = (\d+);", _html())
        self.assertTrue(m, "constante da rede de seguranca sumiu")
        self.assertLessEqual(int(m.group(1)), 300000,
                             "janela longa demais: dado velho demoraria a se corrigir")

    def test_refresh_usa_a_janela(self):
        corpo = _corpo("refreshDB")
        self.assertIn("_FORCA_APOS_MS", corpo)
        self.assertIn("_ultimoCheio", corpo)

    def test_marca_o_momento_do_download_completo(self):
        """Sem atualizar `_ultimoCheio`, a janela nunca fecha e o forcado
        dispara em toda troca de aba — o bug ao contrario."""
        corpo = _corpo("refreshDB")
        self.assertRegex(corpo, r"_ultimoCheio\s*=\s*Date\.now\(\)")


if __name__ == "__main__":
    unittest.main()
