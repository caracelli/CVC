# -*- coding: utf-8 -*-
"""Retorno da area (Bruna) em 24/09/2026 — Arquivos_origem/Sistema_24_09 1.docx.

1. ROSELAINE (34532575), "tem mais de um acesso previsto na matriz": a matriz
   da' duas opcoes por sistema e ela tem uma. A tela dizia "Tem 1 / Falta 1".
   Regra: um perfil por sistema — tendo um mapeado, vem OK; as outras opcoes
   aparecem "estilo as funcoes do CCO" (bloco "Outros acessos previstos").
   Vale para todos os sistemas menos o Oracle (decisao do usuario).

2. DENISE (1562), "nao pode ter acesso e tem / ela tem acesso e nao veio o
   perfil": tem IC_CADASTRO no IC, e nem a matriz nem a CCO preveem IC para
   ela. A tela so' dizia "sem perfil previsto". Agora e' pendencia com o
   acesso nomeado (decisao do usuario). Medido na base de 15/09: 7 pessoas.
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
from infraestrutura.banco_dados.schema import (
    RhAtivo, AcessoSistema, PerfilEsperadoModel, ValidacaoAcessoModel)
from aplicacao.casos_de_uso.validar_acessos_sistema import ValidarAcessosSistema
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
    js = ("const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;')"
          ".replace(/>/g,'&gt;').replace(/\"/g,'&quot;');\n"
          "const DB = {meta: {multi_perfil_fora: ['ORACLE_EBS']}};\n" + js)
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


def _base_denise(situacao="PENDENTE", com_ic_na_matriz=False):
    tmp = tempfile.mkdtemp(prefix="cvc_2409_")
    cx = ConexaoBancoDados(os.path.join(tmp, "d.db"))
    cx.inicializar()
    s = cx.sessao()
    s.add(RhAtivo(matricula="1562", nome="DENISE", cpf="1", cargo_codigo="CG",
                  cargo_descricao="ANALISTA CONTABIL SR",
                  centro_custo_codigo="01.02.02.11", gestor="G",
                  situacao="ATIVO", tipo_vinculo="FUNCIONARIO"))
    s.add(PerfilEsperadoModel(cargo_codigo="01.02.02.11",
                              cargo_descricao="ANALISTA CONTABIL SR",
                              sistema="SIGOT", perfil="Contabil1"))
    if com_ic_na_matriz:
        s.add(PerfilEsperadoModel(cargo_codigo="01.02.02.11",
                                  cargo_descricao="ANALISTA CONTABIL SR",
                                  sistema="IC_INTEGRADOR_CONTABIL",
                                  perfil="IC_CADASTRO"))
    s.add(AcessoSistema(sistema="SIGOT", usuario="d", perfil="Contabil1",
                        matricula_vinculada="1562", situacao="ATIVO"))
    s.add(AcessoSistema(sistema="IC_INTEGRADOR_CONTABIL", usuario="d",
                        perfil="IC_CADASTRO", matricula_vinculada="1562",
                        situacao=situacao))
    s.commit(); s.close()
    return cx


def _ic(cx):
    ValidarAcessosSistema(cx).executar()
    s = cx.sessao()
    r = [(x.status, x.perfil_atual, x.motivo_status, x.situacao_acao)
         for x in s.query(ValidacaoAcessoModel)
         .filter_by(matricula="1562", sistema="IC_INTEGRADOR_CONTABIL").all()]
    s.close()
    return r


class NaoPodeTerETem(unittest.TestCase):

    def test_o_caso_da_denise(self):
        """⭐ Tem IC, a matriz nao preve: pendencia com o perfil."""
        self.assertEqual(_ic(_base_denise()), [
            ("EM_ANALISE", "IC_CADASTRO", "ACESSO_SEM_PREVISAO", "PENDENTE")])

    def test_conta_bloqueada_nao_e_acesso(self):
        self.assertEqual(_ic(_base_denise(situacao="BLOQUEADO")), [])

    def test_com_previsao_segue_o_caminho_normal(self):
        r = _ic(_base_denise(com_ic_na_matriz=True, situacao="ATIVO"))
        self.assertEqual([x[0] for x in r], ["OK"])

    def test_texto_no_painel(self):
        c = sqlite3.connect(os.path.join(tempfile.mkdtemp(), "i.db"))
        ConexaoBancoDados(c.execute("PRAGMA database_list").fetchone()[2]).inicializar()
        c.execute(
            "INSERT INTO validacao_acessos (matricula, nome, sistema, perfil_esperado,"
            " perfil_atual, status, motivo_status, dt_processamento)"
            " VALUES ('1562','DENISE','IC_INTEGRADOR_CONTABIL','','IC_CADASTRO',"
            "'EM_ANALISE','ACESSO_SEM_PREVISAO','2026-09-24 10:00:00')")
        c.commit()
        c.executescript(vm._SQL_BI)
        motivo = c.execute("SELECT motivo FROM bi_divergencias").fetchone()[0]
        c.close()
        self.assertTrue(motivo.startswith("Nao pode ter acesso e tem"))


@unittest.skipUnless(NODE, "Node não disponível nesta máquina")
class UmPerfilPorSistema(unittest.TestCase):
    ROSE_SYSTUR = {"a": "Aderente", "sis": "SYSTUR",
                   "pe": "CUSTOS", "pp": "CUSTOS, INTERCOMPANY"}
    ROSE_ORACLE = {"a": "Aderente", "sis": "ORACLE_EBS",
                   "pe": "CVC A", "pp": "CVC A, CVC B"}

    def _txt(self, d):
        return _node(f"{_funcao('_csListaPerfis')}\n{_funcao('_csDelta')}\n"
                     f"{_funcao('_csPerfilTxt')}\n"
                     f"console.log(_csPerfilTxt({json.dumps(d)}));")

    def _bloco(self, divs):
        return _node(f"{_funcao('_csOutrasOpcoes')}\n"
                     f"console.log(_csOutrasOpcoes({json.dumps(divs)}));")

    def test_aderente_nao_mostra_falta(self):
        """⭐ O caso da Roselaine: tem CUSTOS, era "Falta 1: INTERCOMPANY"."""
        h = self._txt(self.ROSE_SYSTUR)
        self.assertIn("CUSTOS", h)
        self.assertNotIn("Falta", h)

    def test_oracle_continua_mostrando_falta(self):
        """No Oracle cada perfil e' um acesso: la' a falta e' real."""
        self.assertIn("Falta", self._txt(self.ROSE_ORACLE))

    def test_as_outras_opcoes_vao_para_o_bloco(self):
        h = self._bloco([self.ROSE_SYSTUR, self.ROSE_ORACLE])
        self.assertIn("Outros acessos previstos (1)", h)
        self.assertIn("INTERCOMPANY", h)
        self.assertNotIn("CVC B", h)

    def test_so_um_mapeado_nao_gera_bloco(self):
        """VIVIANE (9326): IC so' com IC_CONSULTA, e ela tem — nada a listar."""
        self.assertEqual(self._bloco([{"a": "Aderente", "sis": "IC_INTEGRADOR_CONTABIL",
                                       "pe": "IC_CONSULTA", "pp": "IC_CONSULTA"}]).strip(), "")

    def test_o_bloco_nao_repete_o_que_ela_tem(self):
        """Validacao de 24/09: "tem X" no resumo repetia Acessos encontrados."""
        h = self._bloco([self.ROSE_SYSTUR])
        self.assertNotIn("tem CUSTOS", h)

    def test_poucas_opcoes_vem_direto_sem_expandir(self):
        """Validacao de 24/09: "se tem uma opcao so' acho desnecessario o +"."""
        h = self._bloco([self.ROSE_SYSTUR])
        self.assertNotIn("<details", h)
        self.assertIn("INTERCOMPANY", h)
        duas = {"a": "Aderente", "sis": "SIG", "pe": "A", "pp": "A, B, C"}
        self.assertIn("<details", self._bloco([duas]),
                      "mais de uma opcao fica recolhida")

    def test_em_analise_diz_o_lado(self):
        """⭐ DENISE: SYSTUR que falta e IC que sobra saiam iguais."""
        falta = self._txt({"a": "Em Análise", "sis": "SYSTUR", "pe": "", "pp": "INTEGRADOR_CONTABIL"})
        sobra = self._txt({"a": "Em Análise", "sis": "IC_INTEGRADOR_CONTABIL", "pe": "IC_CADASTRO", "pp": ""})
        self.assertIn("Deveria ter:", falta)
        self.assertIn("Tem hoje:", sobra)

    def test_o_bloco_e_chamado_no_popup(self):
        self.assertIn("+ _csOutrasOpcoes(u.divs)", INDEX.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
