# -*- coding: utf-8 -*-
"""Ordem CRONOLOGICA de importacao dos snapshots do AD.

O merge e' por login: quando chegam varios snapshots da mesma populacao, o
ULTIMO processado prevalece. Logo o ultimo tem de ser o MAIS RECENTE.

Ordenar pelo caminho (alfabetico) funciona por acaso dentro do mesmo ano
(07-2026 < 08-2026) e QUEBRA na virada: "01-2027" < "07-2026", entao o snapshot
de dezembro venceria o de janeiro — o dado mais VELHO ganharia. A pasta vira
numero (MM-AAAA -> AAAAMM) e a data do nome (DD_MM_AAAA_HH-MM -> AAAAMMDDHHMM)
manda, porque e' precisa ate a hora.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from aplicacao.casos_de_uso.importar_diretorio_ad import (
    _chave_cronologica, _mes_da_pasta)
from infraestrutura.leitores_arquivos.leitor_sistema import chave_data_arquivo

BASE = Path("C:/app/ENTRADA/SISTEMAS/AD_PRESTADORES")


def _p(mes, nome):
    return BASE / mes / nome


def _ordenar(*arquivos):
    return [a.name for a in sorted(arquivos, key=_chave_cronologica)]


class TestPastaViraNumero(unittest.TestCase):

    def test_mm_aaaa_vira_aaaamm(self):
        self.assertEqual(_mes_da_pasta(_p("07-2026", "x.csv")), 202607)
        self.assertEqual(_mes_da_pasta(_p("08-2026", "x.csv")), 202608)
        self.assertEqual(_mes_da_pasta(_p("01-2027", "x.csv")), 202701)

    def test_janeiro_do_ano_seguinte_e_MAIOR_que_dezembro(self):
        self.assertGreater(_mes_da_pasta(_p("01-2027", "x.csv")),
                           _mes_da_pasta(_p("12-2026", "x.csv")))

    def test_pasta_sem_padrao_nao_atrapalha(self):
        self.assertEqual(_mes_da_pasta(BASE / "x.csv"), 0)
        self.assertEqual(_mes_da_pasta(BASE / "qualquer" / "x.csv"), 0)


class TestDataDoNome(unittest.TestCase):
    """Reaproveita a MESMA funcao dos extratos de sistema — nao duplica regra."""

    def test_nome_completo(self):
        self.assertEqual(chave_data_arquivo("ou_prestadores_03_08_2026_16-50.csv"),
                         (2026, 8, 3, 16, 50))

    def test_hora_ordena_o_mesmo_dia(self):
        a = chave_data_arquivo("ou_prestadores_29_07_2026_18-25.csv")
        b = chave_data_arquivo("ou_prestadores_29_07_2026_19-20.csv")
        self.assertLess(a, b)

    def test_nome_sem_data(self):
        self.assertEqual(chave_data_arquivo("OU_Prest_Bruna.csv"), (0, 0, 0, 0, 0))

    def test_pasta_completa_o_ano_quando_o_nome_so_tem_dia_e_mes(self):
        # nome curto "20_12" nao diz o ano: sem a pasta, dezembro/2026 e
        # dezembro/2027 empatariam
        dez26 = BASE / "12-2026" / "ou_prestadores_20_12.csv"
        jan27 = BASE / "01-2027" / "ou_prestadores_05_01.csv"
        self.assertEqual(_ordenar(jan27, dez26)[-1], jan27.name)


class TestOrdemDeImportacao(unittest.TestCase):

    def test_virada_de_ano(self):
        dez = _p("12-2026", "ou_prestadores_20_12_2026_10-00.csv")
        jan = _p("01-2027", "ou_prestadores_05_01_2027_09-00.csv")
        self.assertEqual(_ordenar(jan, dez)[-1], jan.name,
                         "o de janeiro/2027 tem de ser o ULTIMO (mais recente)")

    def test_os_cinco_snapshots_reais_da_entrega(self):
        arqs = [
            _p("07-2026", "ou_prestadores_29_07_2026_18-25.csv"),
            _p("07-2026", "ou_prestadores_29_07_2026_19-20.csv"),
            _p("07-2026", "ou_prestadores_30_07_2026_10-44.csv"),
            _p("07-2026", "ou_prestadores_30_07_2026_10-50.csv"),
            _p("08-2026", "ou_prestadores_03_08_2026_16-50.csv"),
        ]
        ordem = _ordenar(*reversed(arqs))     # embaralhado de proposito
        self.assertEqual(ordem, [a.name for a in arqs])
        self.assertEqual(ordem[-1], "ou_prestadores_03_08_2026_16-50.csv",
                         "o mais recente tem de prevalecer")

    def test_arquivo_sem_data_cede_lugar_ao_datado(self):
        antigo = BASE / "OU_Prest_Bruna.csv"
        novo = _p("08-2026", "ou_prestadores_03_08_2026_16-50.csv")
        self.assertEqual(_ordenar(novo, antigo)[-1], novo.name)

    def test_data_do_nome_manda_sobre_a_pasta(self):
        # arquivo mais novo guardado numa pasta de mes anterior (engano do
        # cliente): a data do nome e' que vale
        na_pasta_velha = _p("07-2026", "ou_prestadores_10_08_2026_09-00.csv")
        na_pasta_nova = _p("08-2026", "ou_prestadores_01_08_2026_09-00.csv")
        self.assertEqual(_ordenar(na_pasta_velha, na_pasta_nova)[-1],
                         na_pasta_velha.name)

    def test_ordem_e_deterministica_sem_data_nenhuma(self):
        a, b = BASE / "OU_Prest_A.csv", BASE / "OU_Prest_B.csv"
        self.assertEqual(_ordenar(a, b), _ordenar(b, a))


if __name__ == "__main__":
    unittest.main(verbosity=2)
