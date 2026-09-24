# -*- coding: utf-8 -*-
"""OUTRAS FUNCOES QUE ELA PODE TER (usuario, 24/09/2026). So' CCO.

Caso da BRENDA (34530984): A_RECEBER_1 no SYSTUR; a gestora tem A Receber 1,
A Receber 1 Comissao, A Receber 2 + SIG e A Receber 3. So' a A Receber 1 e'
cobrada (regra de 23/09); as outras aparecem como o que ela PODE ter, sem
virar "incluir" nem pendencia. Sem perfil no SYSTUR o motor ja' cobra todas.
"""
import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import visualizador.main as vm


def _banco():
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE matriz_cco (cc, gestor, funcao, sistema, perfil)")
    c.execute("CREATE TABLE acessos_sistemas (matricula_vinculada, sistema, perfil, situacao)")
    for f, s, p in (("A Receber 1", "Systur", "A_RECEBER_1"),
                    ("A Receber 1", "Oracle EBS", "CVC AR BRASIL"),
                    ("A Receber 2 + SIG", "Systur", "A_RECEBER_2"),
                    ("A Receber 2 + SIG", "SIG", "OPERACIONAL"),
                    ("A Receber 2 + SIG", "Opera Operacional", "A_RECEBER_2"),
                    ("A Receber 3", "Oracle EBS", "CVC GL BRASIL")):
        c.execute("INSERT INTO matriz_cco VALUES (?,?,?,?,?)",
                  ("01.06.02.01", "FERNANDA DA SILVA AQUINO", f, s, p))
    c.execute("INSERT INTO acessos_sistemas VALUES ('M1','SYSTUR','A_RECEBER_1','ATIVO')")
    c.execute("INSERT INTO acessos_sistemas VALUES ('M1','SIG','OPERACIONAL','BLOQUEADO')")
    c.execute("INSERT INTO acessos_sistemas VALUES ('M1','ORACLE_EBS','CVC GL BRASIL','ATIVO')")
    return c


def _user(funcoes_cobradas, gestor="FERNANDA DA SILVA AQUINO"):
    return {"m": "M1", "gestor": gestor,
            "divs": [{"fun": f} for f in funcoes_cobradas]}


class OutrasFuncoesDaEquipe(unittest.TestCase):

    def _rodar(self, u, cc="01.06.02.01"):
        users = {"M1": u}
        vm._outras_funcoes_cco(_banco(), users, {"M1": cc})
        return u.get("fo")

    def test_a_brenda_ve_as_outras_da_gestora(self):
        """⭐ O pedido: as outras funcoes aparecem, a dela nao se repete."""
        fo = self._rodar(_user(["A Receber 1"]))
        self.assertEqual([x["f"] for x in fo], ["A Receber 2 + SIG", "A Receber 3"])

    def test_marca_o_que_ela_ja_tem(self):
        fo = {x["f"]: x["a"] for x in self._rodar(_user(["A Receber 1"]))}
        self.assertIn(["ORACLE_EBS", "CVC GL BRASIL", True], fo["A Receber 3"])

    def test_conta_bloqueada_nao_conta_como_tem(self):
        fo = {x["f"]: x["a"] for x in self._rodar(_user(["A Receber 1"]))}
        self.assertIn(["SIG", "OPERACIONAL", False], fo["A Receber 2 + SIG"])

    def test_opera_entra_na_lista(self):
        fo = {x["f"]: x["a"] for x in self._rodar(_user(["A Receber 1"]))}
        self.assertIn("OPERA_OPERACIONAL", [a[0] for a in fo["A Receber 2 + SIG"]])

    def test_sem_funcao_cobrada_nao_ha_o_que_separar(self):
        """Sem SYSTUR o motor ja' cobra todas — nada vai para 'outras'."""
        self.assertIsNone(self._rodar(_user([])))

    def test_quem_nao_e_da_cco_nao_ganha_o_bloco(self):
        self.assertIsNone(self._rodar(_user(["A Receber 1"], gestor="OUTRA PESSOA")))


class ATelaMostraOBloco(unittest.TestCase):

    def test_o_bloco_e_chamado_no_popup(self):
        html = (Path(__file__).resolve().parent.parent / "CVC_IAM_ANALYTICS"
                / "EXECUTAVEIS" / "REPORT" / "index.html").read_text(encoding="utf-8")
        self.assertIn("function _csOutrasFuncoes(u)", html)
        self.assertIn("+ _csOutrasFuncoes(u);", html)


if __name__ == "__main__":
    unittest.main()
