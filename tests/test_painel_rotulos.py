# -*- coding: utf-8 -*-
"""Rotulos do painel: um nome por conceito, e rotulo so quando distingue.

Retorno da area (28/08/2026, print do Teams):
    "Porque dois esperados: o perfil que tem ali e' o que e' esperado ou
     liberado?"

Ela estava certa. A varredura achou quatro problemas do mesmo tipo:

1. REDUNDANCIA. Dentro do bloco "● Acessos esperados (N) — nao tem, mas o
   cargo preve", cada linha repetia "Esperado:". O rotulo nao desambiguava
   nada: so' duplicava o cabecalho.

2. INCONSISTENCIA. No bloco "Acessos encontrados", quando encontrado ==
   esperado, a linha vinha em verde SEM rotulo. A mesma informacao aparecia
   ora rotulada, ora nao.

3. COLISAO SEMANTICA (a mais grave). "Encontrado" tinha DOIS sentidos na
   mesma tela: "Perfil Encontrado" = achado no EXTRATO (o que a pessoa tem);
   "Usuarios Nao Encontrados" = nao achado no RH (acesso sem dono).

4. QUATRO NOMES para o mesmo estado: "Usuario Nao Encontrado" (acao, 9x),
   "Usuarios Nao Encontrados" (card, 2x), "Acessos nao localizados"
   (categoria, 1x) e "Sem Vinculo RH" (tipo na grid, 8x).

O que NAO foi mexido, de proposito: o VALOR da acao (`d.a`), porque filtros e
atalhos salvos pela area guardam esse texto — renomear quebraria o que ela ja'
montou. E "Acessos nao localizados" ficou: e' a palavra dela, do 1o retorno
("Acessos que nao foram localizados").
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
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


@unittest.skipUnless(NODE, "Node não disponível nesta máquina")
class RotuloSoQuandoDistingue(unittest.TestCase):
    """UM valor na linha -> sem prefixo (o bloco que a contem ja diz o que e').
    DOIS valores -> os dois prefixos ficam, porque ai eles separam coisas."""

    def _txt(self, pe, pp):
        js = f"""
        const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;')
                                  .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
        {_funcao('_csListaPerfis')}
        {_funcao('_csDelta')}
        {_funcao('_csPerfilTxt')}
        console.log(_csPerfilTxt({json.dumps({"pe": pe, "pp": pp})}));
        """
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                         encoding="utf-8") as f:
            f.write(js)
            caminho = f.name
        try:
            r = subprocess.run([NODE, caminho], capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
            self.assertEqual(r.returncode, 0, r.stderr)
            return r.stdout.strip()
        finally:
            os.unlink(caminho)

    def test_so_esperado_nao_repete_o_bloco(self):
        """O caso do print dela: bloco 'Acessos esperados' + linha 'Esperado:'."""
        h = self._txt("", "ATD_LAZER, ATD_HOTEIS")
        self.assertNotIn("Esperado", h, "o bloco ja se chama 'Acessos esperados'")
        self.assertIn("ATD_LAZER", h)

    def test_so_encontrado_nao_repete_o_bloco(self):
        h = self._txt("ANT_OP_BKO_N2", "")
        self.assertNotIn("Encontrado", h)
        self.assertIn("ANT_OP_BKO_N2", h)

    def test_aderente_continua_sem_rotulo(self):
        h = self._txt("ATD_LAZER", "ATD_LAZER")
        self.assertNotIn("Esperado", h)
        self.assertNotIn("Encontrado", h)

    def test_dois_valores_MANTEM_os_rotulos(self):
        """Aqui o rotulo trabalha: separa coisas diferentes.

        Desde o ajuste de volume (28/08, ver test_painel_volume_perfis.py) o
        caso de dois lados mostra o DELTA — "Falta N" / "N a mais" — em vez das
        duas listas. Continuam sendo dois rotulos que distinguem, que e' o que
        esta regra cobra. O par "Tem hoje/Deveria ter" sobrou para a valvula
        de grafia, coberta la'."""
        h = self._txt("ATD_LAZER", "GERENCIA_GERAL")
        self.assertIn("Falta 1", h)
        self.assertIn("1 a mais", h)
        self.assertIn("GERENCIA_GERAL", h)
        self.assertIn("ATD_LAZER", h)

    def test_nao_usa_mais_a_palavra_ambigua(self):
        """'Encontrado' significava duas coisas na tela; some da linha."""
        for pe, pp in [("A", "B"), ("A", ""), ("", "B"), ("A", "A")]:
            self.assertNotIn("Encontrado:", self._txt(pe, pp))


class UmNomePorConceito(unittest.TestCase):

    def test_card_nao_usa_encontrado(self):
        """O card colidia com a coluna 'Perfil Encontrado'."""
        html = INDEX.read_text(encoding="utf-8")
        self.assertNotIn("Usuários Não Encontrados", html)
        self.assertIn("Usuários sem vínculo no RH", html)

    def test_rotulo_do_card_e_a_chave_do_KPI_MAP_batem(self):
        """ARMADILHA: `KPI_MAP[lbl.textContent]` — a chave E' o texto do rotulo.
        Renomear um sem o outro nao quebra nada visivelmente: o card so' para
        de receber valor, calado. Este teste amarra os dois."""
        html = INDEX.read_text(encoding="utf-8")
        m = re.search(r"const KPI_MAP = \{(.*?)\};", html, re.S)
        self.assertTrue(m, "KPI_MAP não encontrado")
        chaves = set(re.findall(r"'([^']+)'\s*:", m.group(1)))
        rotulos = {r.strip() for r in
                   re.findall(r'class="kpi-lbl"[^>]*>([^<]+)<', html)}
        orfas = chaves - rotulos
        self.assertEqual(orfas, set(),
                         "chave do KPI_MAP sem card com esse texto — o card "
                         f"nao recebe valor e ninguem percebe: {orfas}")


if __name__ == "__main__":
    unittest.main()
