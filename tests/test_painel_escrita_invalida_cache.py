# -*- coding: utf-8 -*-
"""Depois de agir, a usuaria TEM de ver a propria acao.

Este e' o risco do cache por token (commit 1f5284a). Se o cache servir conteudo
velho logo apos ela resolver uma pendencia ou mandar para quarentena, ela nao ve
o que acabou de fazer — e isso e' PIOR que a lentidao que o cache corrigiu.

O mecanismo que protege: a acao grava um `.jsonl` em INTERACOES/, o
`token_mudanca()` do servidor enxerga o arquivo maior, o token muda, e o cache
do `fetchAPI` erra por token diferente e rebusca. A corrente so' funciona se o
fluxo de escrita chamar `refreshDB()` DEPOIS de gravar — e' isso que os testes
abaixo cobram.

PROVADO AO VIVO em 28/08/2026, quarentena feita PELA INTERFACE (modal
preenchido e confirmado), no painel dos 7 sistemas:
    token       antes `interacao_user.jsonl:3587` -> depois `:3952`  (mudou)
    quarData.ativas  0 -> 1, contendo o alvo (matricula 10039)
    a linha renderizou na aba Quarentena SEM recarregar a pagina
A pasta INTERACOES/ foi restaurada ao original depois do teste (3587 bytes).

⚠️ Naquele teste a primeira assertiva deu FALHA por engano meu: eu procurava o
TITULO da quarentena no texto da grid, e a grid nao tem coluna de titulo. O dado
estava certo o tempo todo. Assertiva ruim produz falso negativo tao facilmente
quanto teste fraco produz falso positivo.
"""
import re
import unittest
from pathlib import Path

INDEX = (Path(__file__).resolve().parent.parent
         / "CVC_IAM_ANALYTICS" / "EXECUTAVEIS" / "REPORT" / "index.html")

# Fluxos que ESCREVEM e depois precisam mostrar o resultado na tela.
# ⚠️ Sao os `confirmar*`. `retirarQuarentena` NAO entra: ela so' abre o modal —
# quem faz o POST e' `confirmarRetirada`. Errei essa lista na primeira versao e
# o teste acusou uma falha que nao existia no codigo, so' no nome que escolhi.
ESCRITA = ("confirmarQuarentena", "confirmarRetirada", "confirmarResolucao")


def _corpo(nome):
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
    raise AssertionError(f"{nome} nao fecha")


class EscritaRefrescaAntesDeRedesenhar(unittest.TestCase):

    def test_todo_fluxo_de_escrita_invalida_o_cache(self):
        """⭐ Achado de 28/08: `confirmarResolucao` tem uma via rapida em que o
        servidor devolve `j.dados` e o cliente atualiza o DB DIRETO, sem passar
        por refreshDB. Nessa via o `_tokenDB` fica velho e o cache do fetchAPI
        segue entregando o conteudo de ANTES da acao dela — ela resolveria uma
        pendencia e o Historico continuaria sem a resolucao."""
        for f in ESCRITA:
            corpo = _corpo(f)
            self.assertIn("invalidarCacheAPI()", corpo,
                          f"{f} grava e nao joga o cache fora")

    def test_o_invalidador_existe_e_limpa_mesmo(self):
        corpo = _corpo("invalidarCacheAPI")
        self.assertIn("_cacheAPI.clear()", corpo)

    def test_a_via_rapida_da_resolucao_continua_coberta(self):
        """Se a via rapida voltar a existir sem a invalidacao, o bug volta —
        e volta CALADO, porque a tela mostra dado plausivel, so' que velho."""
        corpo = _corpo("confirmarResolucao")
        i = corpo.index("invalidarCacheAPI()")
        j = corpo.index("if(j.dados)")
        self.assertLess(i, j, "a invalidacao tem de vir ANTES da via rapida")


class CorrenteDoTokenIntacta(unittest.TestCase):
    """As tres pecas que fazem a acao dela aparecer. Quebrar qualquer uma
    devolve o bug — e calado."""

    def test_1_o_servidor_assina_as_interacoes(self):
        src = (Path(__file__).resolve().parent.parent / "src" / "visualizador"
               / "main.py").read_text(encoding="utf-8-sig")
        i = src.index("def token_mudanca(")
        corpo = src[i:i + 2600]
        self.assertIn("PASTA_INTERACOES", corpo)
        self.assertIn("st_size", corpo,
                      "sem o TAMANHO, um append no .jsonl que ja' existe passa batido")

    def test_2_o_cliente_guarda_o_token_do_que_recebeu(self):
        self.assertIn("_tokenDB = d.token", _corpo("refreshDB"))

    def test_3_o_cache_erra_quando_o_token_muda(self):
        corpo = _corpo("fetchAPI")
        self.assertRegex(corpo, r"c\.token\s*===\s*_tokenDB")


if __name__ == "__main__":
    unittest.main()
