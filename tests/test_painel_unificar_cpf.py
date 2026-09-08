# -*- coding: utf-8 -*-
"""Fusão de identidades por CPF na Consulta (`_csUnificarPorCpf`, 10/08/2026).

Retorno da área: "se é a mesma pessoa por que trás separado?" (prestador via
AD + terceiro via RH, mesmo CPF). A fusão existe desde `d4261a0`, mas nunca
tinha teste — e a auditoria de 08/09 achou o risco que faltava cobrir: nem
todo CPF duplicado é a MESMA pessoa. Medido na base real: de 681 CPFs com 2+
identidades em `rh_ativos`, 8 têm nomes SEM NENHUM token em comum (ex.:
"REYNALDO BLANCO" e "LUIS FERNANDO ESCAMILLA RUIZ" no mesmo CPF — código de
terceiro reaproveitado como CPF, não CPF de verdade). Fundir esses juntaria o
acesso de uma pessoa sob o nome/vínculo de outra — pior que a duplicidade
original. `_csAgruparPorNome` faz o corte: só funde quem, além do CPF, tem
pelo menos um token de nome em comum.

Roda as funções reais extraídas do index.html no Node. Pula se não houver Node.
"""
import json
import shutil
import subprocess
import tempfile
import os
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
INDEX = RAIZ / "CVC_IAM_ANALYTICS" / "EXECUTAVEIS" / "REPORT" / "index.html"
NODE = shutil.which("node")

_FUNCOES = ("_csNorm", "_csChaveCpf", "_csNomesCompativeis",
            "_csAgruparPorNome", "_csUnificarPorCpf")


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


def _u(u, n, cpf, vinc="Terceiro", divs=None, m=""):
    return {"u": u, "n": n, "cpf": cpf, "vinc": vinc, "m": m or u,
            "login": "", "c": "", "d": "", "cc": "", "gestor": "", "email": "",
            "divs": divs if divs is not None else [{"sis": "SYSTUR"}]}


@unittest.skipUnless(NODE, "Node não disponível nesta máquina")
class UnificarPorCpf(unittest.TestCase):

    def _rodar(self, users):
        # também precisa da definicao da constante _CS_NOME_STOP, que fica
        # junto de _csNomesCompativeis no arquivo — extraida junto abaixo.
        html = INDEX.read_text(encoding="utf-8")
        i = html.index("const _CS_NOME_STOP")
        j = html.index(";", i) + 1
        stop = html[i:j]
        corpo = "\n".join(_funcao(f) for f in _FUNCOES)
        js = f"""
        {stop}
        {corpo}
        console.log(JSON.stringify(_csUnificarPorCpf({json.dumps(users)})));
        """
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                         encoding="utf-8") as f:
            f.write(js)
            caminho = f.name
        try:
            r = subprocess.run([NODE, caminho], capture_output=True, text=True,
                               encoding="utf-8", timeout=60)
            self.assertEqual(r.returncode, 0, r.stderr)
            return json.loads(r.stdout.strip().splitlines()[-1])
        finally:
            os.unlink(caminho)

    def test_mesma_pessoa_prestador_e_terceiro_funde(self):
        """O caso real do retorno: Bruna Soler, mesmo CPF, 2 identidades."""
        out = self._rodar([
            _u("PREST-corpp138009", "BRUNA SOLER DOS SANTOS FERNANDES",
               "38251220858", vinc="Prestador"),
            _u("TERC-38251220858", "BRUNA SOLER DOS SANTOS FERNANDES",
               "38251220858", vinc="Terceiro"),
        ])
        self.assertEqual(len(out), 1, "tinha de virar 1 linha só")
        self.assertEqual(len(out[0]["divs"]), 2, "acessos das duas identidades somados")
        self.assertIn("Terceiro", out[0]["vinc"])
        self.assertIn("Prestador", out[0]["vinc"])

    def test_variante_de_nome_ainda_funde(self):
        """Nome incompleto/apelido (compartilha ao menos 1 token) continua
        sendo tratado como a mesma pessoa — não pode regredir."""
        out = self._rodar([
            _u("TERC-1", "JAQUELINE MOROSINI BARRETO", "36462314400"),
            _u("TERC-2", "JAQUELINE BARRETO", "36462314400"),
        ])
        self.assertEqual(len(out), 1)

    def test_cpf_ruim_com_pessoas_diferentes_NAO_funde(self):
        """Achado da auditoria de 08/09: mesmo CPF, nomes sem token em comum —
        são pessoas diferentes (CPF mascarado/placeholder reaproveitado).
        Fundir esconderia o acesso de uma pessoa atrás do nome da outra."""
        out = self._rodar([
            _u("TERC-1024524760", "REYNALDO BLANCO", "01024524760"),
            _u("TERC-01024524760", "LUIS FERNANDO ESCAMILLA RUIZ", "01024524760"),
        ])
        self.assertEqual(len(out), 2, "tinham de continuar separados")
        nomes = {o["n"] for o in out}
        self.assertEqual(nomes, {"REYNALDO BLANCO", "LUIS FERNANDO ESCAMILLA RUIZ"})

    def test_cpf_unico_nao_e_tocado(self):
        out = self._rodar([_u("TERC-1", "ALGUEM SOZINHO", "11122233396")])
        self.assertEqual(len(out), 1)
        self.assertNotIn("_ids", out[0])

    def test_cpf_vazio_ou_invalido_nao_agrupa(self):
        """CPF vazio ou com todos os dígitos iguais (000...00) não desambigua
        — cada identidade fica separada, mesmo que existam duas."""
        out = self._rodar([
            _u("TERC-1", "FULANO", ""),
            _u("TERC-2", "FULANO", "00000000000"),
        ])
        self.assertEqual(len(out), 2)

    def test_tres_identidades_mesma_pessoa(self):
        """O caso real mais comum na base: terceiro cadastrado 2x (com/sem
        zero à esquerda) + prestador, todos o mesmo CPF e nome."""
        out = self._rodar([
            _u("TERC-00000032089", "PEDRO GERETTO", "00000032089"),
            _u("TERC-032089", "PEDRO GERETTO", "00000032089"),
            _u("PREST-corpp132343", "PEDRO GERETTO", "00000032089"),
        ])
        self.assertEqual(len(out), 1)
        self.assertEqual(len(out[0]["_ids"]), 3)


if __name__ == "__main__":
    unittest.main()
