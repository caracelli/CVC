# -*- coding: utf-8 -*-
"""Quem SUMIU do arquivo de ativos mais recente nao ganha "Não Mapeado".

A rh_ativos acumula (merge, bc7af3e), entao quem saiu da base continua gravado
com o arquivo antigo em `arquivo_origem`. Na base de 15/09/2026 os 79 CLT nessa
situacao estavam todos na base de desligados; com a correcao do filtro de
Sistema da Consulta, eles apareceriam como ativos sem mapeamento. Decisao do
usuario (15/09): quem sumiu nao recebe a linha.

Tambem trava que as decisoes FECHADAS seguem como estavam (usuario, 15/09,
"voltar as decisoes fechadas"): prestador sem grupo-espelho e franqueado sem
acesso continuam sem linha.
"""
import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import RhAtivo, AcessoSistema, ValidacaoAcessoModel
from aplicacao.casos_de_uso.validar_acessos_sistema import ValidarAcessosSistema

NOVO, VELHO = datetime(2026, 9, 15, 11, 0), datetime(2026, 7, 1, 14, 0)


def _rh(mat, arquivo=None, dt=None, vinculo="FUNCIONARIO"):
    kw = {"arquivo_origem": arquivo} if arquivo else {}
    if dt:
        kw["dt_importacao"] = dt
    return RhAtivo(matricula=mat, nome=f"P {mat}", cpf=mat.rjust(11, "0"),
                   cargo_codigo="CG", cargo_descricao="SEM MATRIZ",
                   centro_custo_codigo="999", situacao="ATIVO",
                   tipo_vinculo=vinculo, empresa="ACME", gestor="CHEFE",
                   departamento="OPS", **kw)


class NaoMapeadoDeQuemSumiu(unittest.TestCase):

    def _status(self, pessoas):
        tmp = tempfile.mkdtemp(prefix="cvc_desat_")
        cx = ConexaoBancoDados(os.path.join(tmp, "d.db"))
        cx.inicializar()
        s = cx.sessao()
        s.add_all(pessoas)
        # SYSTUR precisa ter dados (senao vira SEM_DADOS)
        s.add(AcessoSistema(situacao="ATIVO", sistema="SYSTUR", usuario="z",
                            perfil="ZZ", matricula_vinculada="ZZ"))
        s.commit(); s.close()
        ValidarAcessosSistema(cx).executar()
        s = cx.sessao()
        try:
            out = {}
            for r in s.query(ValidacaoAcessoModel).all():
                out.setdefault(r.matricula, []).append(r.status)
            return out
        finally:
            s.close()

    def test_quem_sumiu_do_arquivo_mais_recente_fica_sem_linha(self):
        st = self._status([_rh("A1", "NOVO.CSV", NOVO), _rh("A2", "NOVO.CSV", NOVO),
                           _rh("A3", "NOVO.CSV", NOVO), _rh("S1", "VELHO.CSV", VELHO)])
        self.assertEqual(st.get("A1"), ["NAO_MAPEADO"])
        self.assertNotIn("S1", st, "quem sumiu da base apareceu como ativo")

    def test_arquivo_mais_recente_parcial_nao_esconde_ninguem(self):
        """1 no arquivo novo e 3 no velho: parece export parcial."""
        st = self._status([_rh("A1", "NOVO.CSV", NOVO), _rh("S1", "VELHO.CSV", VELHO),
                           _rh("S2", "VELHO.CSV", VELHO), _rh("S3", "VELHO.CSV", VELHO)])
        for m in ("A1", "S1", "S2", "S3"):
            self.assertEqual(st.get(m), ["NAO_MAPEADO"], m)

    def test_sem_arquivo_de_origem_ninguem_some(self):
        st = self._status([_rh("A1"), _rh("A2")])
        self.assertEqual(st.get("A1"), ["NAO_MAPEADO"])
        self.assertEqual(st.get("A2"), ["NAO_MAPEADO"])

    def test_cada_populacao_tem_o_seu_arquivo_mais_recente(self):
        """O prestador vem de outro arquivo (AD) e nao pode tornar o CLT
        'desatualizado'."""
        st = self._status([_rh("A1", "PROJETOIAM.CSV", VELHO),
                           _rh("A2", "PROJETOIAM.CSV", VELHO),
                           _rh("P1", "ou_prestadores_15_09.csv", NOVO, "PRESTADOR")])
        self.assertEqual(st.get("A1"), ["NAO_MAPEADO"])

    # ── decisoes FECHADAS, mantidas ────────────────────────────────────────
    def test_prestador_sem_espelho_segue_sem_linha(self):
        st = self._status([_rh("P1", "ou_prestadores_15_09.csv", NOVO, "PRESTADOR")])
        self.assertNotIn("P1", st)

    def test_franqueado_sem_acesso_segue_sem_linha(self):
        st = self._status([_rh("F1", "ou_franqueados_15_09.csv", NOVO, "FRANQUEADO")])
        self.assertNotIn("F1", st)


if __name__ == "__main__":
    unittest.main()
