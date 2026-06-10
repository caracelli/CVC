# -*- coding: utf-8 -*-
"""Regressao: importar a matriz (perfis ou CCO) de UM sistema nao pode apagar
a dos outros. Antes o salvar_* fazia DELETE global; agora e' substituicao POR
SISTEMA. Garante o isolamento exigido para reprocessar com subconjunto de
arquivos (ex.: so a matriz do SYSTUR)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.repositorios.repositorio_matriz_sqlite import RepositorioMatrizSqlite
from dominio.entidades.perfil_esperado import PerfilEsperado
from dominio.objetos_valor.sistema import Sistema


def _pe(sistema: Sistema, perfil: str, cargo="ANALISTA"):
    return PerfilEsperado(cargo_codigo="CG", cargo_descricao=cargo, descricao="",
                          sistema=sistema, perfil=perfil, acesso_manual=False)


def _cco(sistema: str, cc: str, perfil: str):
    return {"cc": cc, "cc_nome": "X", "gestor": "G", "funcao": "F",
            "sistema": sistema, "perfil": perfil}


class TestMatrizIsolamentoPorSistema(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.mkdtemp(prefix="cvc_iso_")
        self.cx = ConexaoBancoDados(os.path.join(tmp, "d.db"))
        self.cx.inicializar()
        self.repo = RepositorioMatrizSqlite(self.cx)

    def _perfis_por_sistema(self):
        out = {}
        for p in self.repo.obter_perfis_esperados():
            out.setdefault(p.sistema.value, set()).add(p.perfil)
        return out

    def _cco_por_sistema(self):
        out = {}
        for r in self.repo.obter_cco():
            out.setdefault(r["sistema"], set()).add(r["perfil"])
        return out

    # ---- perfis_esperados -------------------------------------------------

    def test_perfis_reimportar_um_sistema_preserva_os_outros(self):
        self.repo.salvar_perfis_esperados([_pe(Sistema.SYSTUR, "P_SYS")])
        self.repo.salvar_perfis_esperados([_pe(Sistema.SIGOT, "P_SIG")])
        # ambos coexistem
        self.assertEqual(self._perfis_por_sistema(),
                         {"SYSTUR": {"P_SYS"}, "SIGOT": {"P_SIG"}})
        # reimporta SO o SYSTUR (perfil novo) — SIGOT tem que sobreviver
        self.repo.salvar_perfis_esperados([_pe(Sistema.SYSTUR, "P_SYS2")])
        self.assertEqual(self._perfis_por_sistema(),
                         {"SYSTUR": {"P_SYS2"}, "SIGOT": {"P_SIG"}})

    def test_perfis_lote_vazio_nao_apaga_nada(self):
        self.repo.salvar_perfis_esperados([_pe(Sistema.SYSTUR, "P_SYS")])
        self.repo.salvar_perfis_esperados([])  # no-op
        self.assertEqual(self._perfis_por_sistema(), {"SYSTUR": {"P_SYS"}})

    # ---- matriz CCO -------------------------------------------------------

    def test_cco_reimportar_um_sistema_preserva_os_outros(self):
        self.repo.salvar_cco([_cco("SYSTUR", "100", "A")])
        self.repo.salvar_cco([_cco("SIGOT", "200", "B")])
        self.assertEqual(self._cco_por_sistema(),
                         {"SYSTUR": {"A"}, "SIGOT": {"B"}})
        self.repo.salvar_cco([_cco("SYSTUR", "101", "A2")])
        self.assertEqual(self._cco_por_sistema(),
                         {"SYSTUR": {"A2"}, "SIGOT": {"B"}})

    def test_cco_lote_vazio_nao_apaga_nada(self):
        self.repo.salvar_cco([_cco("SYSTUR", "100", "A")])
        self.repo.salvar_cco([])  # no-op
        self.assertEqual(self._cco_por_sistema(), {"SYSTUR": {"A"}})


if __name__ == "__main__":
    unittest.main(verbosity=2)
