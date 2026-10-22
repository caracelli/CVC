# -*- coding: utf-8 -*-
"""Tratativa do transferido com STATUS DO APONTAMENTO e STATUS POR SISTEMA
(Bruna, Aplicacao_21_10, mockup aprovado em 22/10/2026).

  "Criar um combo box de status: Em andamento / Pendente — ele nasce o
   apontamento com esse status / Resolvido. E precisamos criar um status para
   cada sistema: mantido, alterado, sem atuacao, excluido."

Os dois viajam na MESMA interacao TRATAMENTO_TRANSFERIDO e chegam ao banco na
dobra. Banco antigo (sem as colunas) ganha as colunas sozinho.
"""
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from aplicacao.casos_de_uso.dobrar_interacoes import DobrarInteracoes

INDEX = RAIZ / "CVC_IAM_ANALYTICS" / "EXECUTAVEIS" / "REPORT" / "index.html"


def _trat(rid, status, sistemas, data="2026-10-22T10:00:00"):
    return {"tipo_interacao": "TRATAMENTO_TRANSFERIDO", "registro_id": rid, "acao": "TRATAR",
            "ticket": "", "ticket_url": "", "descricao": "revisado", "motivo": "",
            "nome": "JULIA", "usuario": "op1", "data_acao": data,
            "status_apontamento": status, "status_sistemas": sistemas}


class DobraDaTratativa(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cvc_trat_status_")
        self.db = os.path.join(self.tmp, "iam.db")
        self.inter = os.path.join(self.tmp, "INTERACOES")
        os.makedirs(self.inter)

    def _gravar(self, *its):
        with open(os.path.join(self.inter, "op1.jsonl"), "a", encoding="utf-8") as f:
            for it in its:
                f.write(json.dumps(it, ensure_ascii=False) + "\n")

    def _linha(self, rid):
        c = sqlite3.connect(self.db)
        c.row_factory = sqlite3.Row
        try:
            return dict(c.execute("SELECT * FROM tratamentos_transferido WHERE registro_id=?",
                                  [rid]).fetchone())
        finally:
            c.close()

    def test_status_e_sistemas_chegam_ao_banco(self):
        self._gravar(_trat("90000321", "Em andamento", {"SYSTUR": "Mantido", "SIG": "Alterado"}))
        DobrarInteracoes(self.db, self.inter).executar()
        r = self._linha("90000321")
        self.assertEqual(r["status_apontamento"], "Em andamento")
        self.assertEqual(json.loads(r["status_sistemas"]), {"SYSTUR": "Mantido", "SIG": "Alterado"})

    def test_banco_antigo_ganha_as_colunas(self):
        c = sqlite3.connect(self.db)
        c.execute("CREATE TABLE tratamentos_transferido (registro_id TEXT PRIMARY KEY, "
                  "ticket TEXT NOT NULL, ticket_url TEXT, descricao TEXT, motivo TEXT, "
                  "nome TEXT, tratado_por TEXT, tratado_em TEXT, dobrado_em TEXT)")
        c.commit(); c.close()
        self._gravar(_trat("1", "Resolvido", {"IC_INTEGRADOR_CONTABIL": "Sem atuação"}))
        DobrarInteracoes(self.db, self.inter).executar()
        self.assertEqual(self._linha("1")["status_apontamento"], "Resolvido")


def _funcao(html, nome):
    i = html.index(f"function {nome}(")
    j, nivel = html.index("{", i), 0
    for k in range(j, len(html)):
        if html[k] == "{":
            nivel += 1
        elif html[k] == "}":
            nivel -= 1
            if nivel == 0:
                return html[i:k + 1]
    raise AssertionError(nome)


def _node(js):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js)
        caminho = f.name
    try:
        out = subprocess.run(["node", caminho], capture_output=True, text=True,
                             encoding="utf-8", timeout=60)
        if out.returncode:
            raise AssertionError(out.stderr)
        return json.loads(out.stdout.strip().splitlines()[-1])
    finally:
        os.unlink(caminho)


class AbaAcao(unittest.TestCase):
    """A simulacao de troca de funcao (caso do documento: RICARDO 34532244,
    Contas a Pagar I -> Adiantamento + Conciliacao bancaria)."""

    def test_incluir_excluir_manter(self):
        html = INDEX.read_text(encoding="utf-8-sig")
        js = (_funcao(html, "_acaoNrm") + "\n" + _funcao(html, "_acaoCalc") + "\n"
              + """
const eq = {
  'Contas a Pagar I': [['SYSTUR','CP_I'], ['SIGOT','CP_I'], ['ORACLE_EBS','AP Consulta'], ['ORACLE_EBS','AP Master']],
  'Adiantamento + Conciliação bancária': [['SYSTUR','ATD_CONC_BANC'], ['ORACLE_EBS','AP Consulta'], ['ORACLE_EBS','AP Pagamento']]
};
const tem = [['SYSTUR','CP_I'], ['ORACLE_EBS','AP Consulta'], ['ORACLE_EBS','AP Master'], ['IC_INTEGRADOR_CONTABIL','IC_CONSULTA']];
console.log(JSON.stringify(_acaoCalc(eq, 'Adiantamento + Conciliação bancária', tem)));
""")
        r = {x["sis"]: x for x in _node(js)}
        self.assertEqual(r["SYSTUR"]["inc"], ["ATD_CONC_BANC"])
        self.assertEqual(r["SYSTUR"]["exc"], ["CP_I"])
        self.assertEqual(r["ORACLE_EBS"]["man"], ["AP Consulta"])
        self.assertEqual(r["ORACLE_EBS"]["exc"], ["AP Master"])
        self.assertEqual(r["ORACLE_EBS"]["inc"], ["AP Pagamento"])
        self.assertNotIn("IC_INTEGRADOR_CONTABIL", r,
                         "sistema fora da CCO da equipe nao vira 'excluir'")


class QuarentenaEscolhe(unittest.TestCase):

    def test_parte_marcada_vira_um_alvo_por_acesso(self):
        html = INDEX.read_text(encoding="utf-8-sig")
        js = ("let _quarAlvo = 'U1', _quarItens = [{sis:'SYSTUR', pf:'TI'}, {sis:'IC', pf:'IC_APROVADOR'}];\n"
              "const _marc = [true, false];\n"
              "const document = {querySelectorAll: () => _marc.map((m, i) => ({checked: m, value: String(i)}))};\n"
              + _funcao(html, "_quarAlvos") + "\n"
              + "const parte = _quarAlvos(); _marc[1] = true; const todas = _quarAlvos();\n"
              + "console.log(JSON.stringify({parte, todas}));")
        r = _node(js)
        self.assertEqual(r["parte"], ["U1##SYSTUR##TI"])
        self.assertEqual(r["todas"], ["U1"], "todas marcadas = a pessoa inteira, como antes")

    def test_ferias_saiu_dos_motivos(self):
        html = INDEX.read_text(encoding="utf-8-sig")
        m = re.search(r"const QUAR_MOTIVOS = \[([^\]]*)\]", html)
        self.assertNotIn("Férias", m.group(1))


if __name__ == "__main__":
    unittest.main()
