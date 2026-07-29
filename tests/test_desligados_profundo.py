# -*- coding: utf-8 -*-
"""Testes PROFUNDOS do motor de desligados (Card 19).

Cobre as duas correcoes de julho/2026 e suas bordas de normalizacao:
  Fix 1 — LeitorSig honra a coluna STATUS (BLOQUEADO nao vira ATIVO);
  Fix 2 — RegraAcessoDesligado so conta acesso REALMENTE ativo (conta
          bloqueada/inativa de desligado ja esta revogada, nao e' divergencia).

Foco em variacoes de caixa/espaco/acento/rotulos de status, matching por
matricula, multi-sistema e integracao pelo ServicoAnaliseDivergencias.
"""
import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dominio.objetos_valor.cargo import Cargo
from dominio.objetos_valor.sistema import Sistema
from dominio.objetos_valor.tipo_divergencia import TipoDivergencia
from dominio.entidades.perfil_acesso import PerfilAcesso
from dominio.entidades.funcionario_desligado import FuncionarioDesligado
from dominio.regras.regra_acesso_desligado import RegraAcessoDesligado, _conta_ativa, _norm_cpf
from dominio.servicos_dominio.servico_analise_divergencias import ServicoAnaliseDivergencias
from infraestrutura.leitores_arquivos.leitor_sig import LeitorSig


# ─────────────────────────── helpers ───────────────────────────
def _desligado(mat, cpf="222"):
    return FuncionarioDesligado(matricula=mat, nome=f"D{mat}", cpf=cpf,
                                cargo=Cargo(codigo="CG", descricao="X", departamento="TI",
                                            centro_custo="100"),
                                data_desligamento=date(2026, 1, 1))


def _acesso(usuario="u1", vinc="20", situacao="ATIVO", sistema=Sistema.SYSTUR, perfil="P1", cpf=""):
    return PerfilAcesso(usuario=usuario, nome_usuario="N", sistema=sistema,
                        perfil=perfil, situacao=situacao, cpf=cpf, matricula_vinculada=vinc)


def _sig_xlsx(linhas):
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tmp.close()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Select tb_sys_sec_user"
    for l in linhas:
        ws.append(l)
    wb.save(tmp.name)
    wb.close()
    return Path(tmp.name)


# rotulos que devem ser tratados como SEM acesso efetivo
INATIVOS = ["INATIVO", "INACTIVE", "BLOQUEADO", "BLOCKED", "SUSPENSO",
            "DESATIVADO", "CANCELADO", "I", "B"]
# rotulos/variacoes que devem contar como acesso ativo
ATIVOS = ["ATIVO", "ACTIVE", "A", "", "ativo", "Ativo"]


# ─────────────── Fix 2: filtro de conta ativa na regra ───────────────
class TestRegraStatusMatrix(unittest.TestCase):
    def setUp(self):
        self.regra = RegraAcessoDesligado()

    def test_todos_status_inativos_nao_geram(self):
        for st in INATIVOS:
            for variante in (st, st.lower(), f"  {st}  ", f"{st.title()} "):
                with self.subTest(status=repr(variante)):
                    divs = self.regra.verificar(
                        [_acesso(situacao=variante)], [_desligado("20")])
                    self.assertEqual(divs, [], f"status {variante!r} deveria ser ignorado")

    def test_status_ativos_e_vazios_geram(self):
        for st in ATIVOS:
            with self.subTest(status=repr(st)):
                divs = self.regra.verificar(
                    [_acesso(situacao=st)], [_desligado("20")])
                self.assertEqual(len(divs), 1, f"status {st!r} deveria gerar divergencia")
                self.assertEqual(divs[0].tipo, TipoDivergencia.ACESSO_DESLIGADO)

    def test_situacao_none_conta_como_ativo(self):
        divs = self.regra.verificar([_acesso(situacao=None)], [_desligado("20")])
        self.assertEqual(len(divs), 1)

    def test_status_desconhecido_conta_como_ativo(self):
        # rotulo fora da lista de inativos -> conservador: conta como acesso
        divs = self.regra.verificar([_acesso(situacao="LIBERADO")], [_desligado("20")])
        self.assertEqual(len(divs), 1)

    def test_conta_ativa_helper_direto(self):
        for st in INATIVOS:
            self.assertFalse(_conta_ativa(st), st)
            self.assertFalse(_conta_ativa(f" {st.lower()} "), st)
        for st in ATIVOS + [None, "QUALQUER"]:
            self.assertTrue(_conta_ativa(st), repr(st))


class TestRegraMatchingEStatus(unittest.TestCase):
    def setUp(self):
        self.regra = RegraAcessoDesligado()

    def test_ativo_mas_sem_vinculo_nao_gera(self):
        # sem matricula_vinculada nao ha como saber que e' desligado
        divs = self.regra.verificar([_acesso(vinc=None, situacao="ATIVO")], [_desligado("20")])
        self.assertEqual(divs, [])

    def test_matricula_nao_desligada_nao_gera(self):
        divs = self.regra.verificar([_acesso(vinc="99", situacao="ATIVO")], [_desligado("20")])
        self.assertEqual(divs, [])

    def test_multi_sistema_status_misto_so_ativo_conta(self):
        # mesmo desligado: SYSTUR ativo (conta) + SIG bloqueado (nao conta)
        divs = self.regra.verificar(
            [_acesso(vinc="20", situacao="ATIVO", sistema=Sistema.SYSTUR),
             _acesso(vinc="20", situacao="BLOQUEADO", sistema=Sistema.SIG)],
            [_desligado("20")])
        self.assertEqual(len(divs), 1)
        self.assertEqual(divs[0].sistema, Sistema.SYSTUR)

    def test_varios_ativos_do_mesmo_desligado_geram_todos(self):
        divs = self.regra.verificar(
            [_acesso("u1", vinc="20", sistema=Sistema.SYSTUR),
             _acesso("u2", vinc="20", sistema=Sistema.IC_INTEGRADOR_CONTABIL)],
            [_desligado("20")])
        self.assertEqual(len(divs), 2)

    def test_todas_bloqueadas_zero_divergencia(self):
        divs = self.regra.verificar(
            [_acesso("u1", vinc="20", situacao="BLOQUEADO", sistema=Sistema.SIG),
             _acesso("u1", vinc="20", situacao="BLOQUEADO", sistema=Sistema.SIG, perfil="P2")],
            [_desligado("20")])
        self.assertEqual(divs, [])


# ─────────────── Matching por UNIAO (matricula OU CPF) ───────────────
CPF_A = "39053344705"   # 11 digitos, digitos variados
CPF_B = "52998224725"


class TestMatchingUniaoCpf(unittest.TestCase):
    def setUp(self):
        self.regra = RegraAcessoDesligado()

    def test_match_so_por_cpf_sem_matricula(self):
        # acesso sem matricula anexada, mas CPF bate com desligado -> gera,
        # e a matricula da divergencia vem do desligado.
        d = _desligado("777", cpf=CPF_A)
        acesso = _acesso(vinc=None, cpf=CPF_A)
        divs = self.regra.verificar([acesso], [d])
        self.assertEqual(len(divs), 1)
        self.assertEqual(divs[0].matricula, "777")

    def test_match_so_por_matricula_sem_cpf(self):
        divs = self.regra.verificar([_acesso(vinc="20", cpf="")], [_desligado("20", cpf=CPF_A)])
        self.assertEqual(len(divs), 1)
        self.assertEqual(divs[0].matricula, "20")

    def test_match_pelas_duas_chaves_nao_duplica(self):
        d = _desligado("20", cpf=CPF_A)
        acesso = _acesso(vinc="20", cpf=CPF_A)
        divs = self.regra.verificar([acesso], [d])
        self.assertEqual(len(divs), 1)  # uma linha -> uma divergencia

    def test_cpf_com_mascara_bate(self):
        d = _desligado("777", cpf="390.533.447-05")
        divs = self.regra.verificar([_acesso(vinc=None, cpf=CPF_A)], [d])
        self.assertEqual(len(divs), 1)

    def test_cpf_com_zeros_a_esquerda_perdidos(self):
        # desligado salvo como numero perde zeros; acesso tem os 11 digitos
        d = _desligado("777", cpf="53344705")           # zfill -> 00053344705
        divs = self.regra.verificar([_acesso(vinc=None, cpf="00053344705")], [d])
        self.assertEqual(len(divs), 1)

    def test_cpf_invalido_todos_iguais_nao_bate(self):
        # 000.000.000-00 (linha 'sistema' do SIG) nao pode casar
        d = _desligado("777", cpf="00000000000")
        divs = self.regra.verificar([_acesso(vinc=None, cpf="000.000.000-00")], [d])
        self.assertEqual(divs, [])

    def test_cpf_parcial_mascarado_nao_bate(self):
        # CPF parcial (<11 digitos, ex.: SICA_ESFERA mascarado) nao casa por CPF
        d = _desligado("777", cpf=CPF_A)
        divs = self.regra.verificar([_acesso(vinc=None, cpf="447")], [d])
        self.assertEqual(divs, [])

    def test_bloqueado_com_cpf_batendo_ainda_nao_gera(self):
        # status manda: mesmo com CPF batendo, conta bloqueada nao e' divergencia
        d = _desligado("777", cpf=CPF_A)
        divs = self.regra.verificar([_acesso(vinc=None, cpf=CPF_A, situacao="BLOQUEADO")], [d])
        self.assertEqual(divs, [])

    def test_cpf_de_ativo_nao_bate(self):
        # acesso com CPF que NAO e' de desligado -> nada
        d = _desligado("777", cpf=CPF_A)
        divs = self.regra.verificar([_acesso(vinc=None, cpf=CPF_B)], [d])
        self.assertEqual(divs, [])

    def test_norm_cpf_helper(self):
        self.assertEqual(_norm_cpf("390.533.447-05"), "39053344705")  # mascara limpa
        self.assertEqual(_norm_cpf("53344705"), "00053344705")        # zeros a esquerda recuperados
        self.assertEqual(_norm_cpf("00000000000"), "")                # todos iguais -> invalido
        self.assertEqual(_norm_cpf("11111111111"), "")                # todos iguais -> invalido
        self.assertEqual(_norm_cpf("447"), "00000000447")             # zfill (fragmento -> 11 digitos)
        self.assertEqual(_norm_cpf("123456789012"), "")               # >11 digitos (CNPJ) -> nao casa
        self.assertEqual(_norm_cpf(None), "")
        self.assertEqual(_norm_cpf(""), "")


# ─────────────── Fix 1: LeitorSig honra STATUS ───────────────
class TestLeitorSigStatus(unittest.TestCase):
    def setUp(self):
        self.leitor = LeitorSig(catalogo={"10": "PERFIL_A", "12": "PERFIL_B"})

    def _ler(self, status):
        arq = _sig_xlsx([
            ["LOGIN", "NM_USER", "STATUS", "CPF", "EMAIL", "10", "12"],
            ["u1", "USER", status, "111", "u@x", "X", "X"],
        ])
        try:
            return self.leitor.ler_um(arq)
        finally:
            os.unlink(arq)

    def test_bloqueado_preservado_em_variacoes(self):
        for st in ("BLOQUEADO", "bloqueado", " Bloqueado ", "BLOQUEADO "):
            with self.subTest(status=repr(st)):
                perfis = self._ler(st)
                self.assertTrue(perfis)
                self.assertTrue(all(p.situacao == "BLOQUEADO" for p in perfis))

    def test_ativo_normalizado(self):
        for st in ("ATIVO", "ativo", " Ativo ", "A"):
            with self.subTest(status=repr(st)):
                self.assertTrue(all(p.situacao == "ATIVO" for p in self._ler(st)))

    def test_inativo_normalizado(self):
        for st in ("INATIVO", "inativo", "I"):
            with self.subTest(status=repr(st)):
                self.assertTrue(all(p.situacao == "INATIVO" for p in self._ler(st)))

    def test_status_vazio_vira_ativo(self):
        self.assertTrue(all(p.situacao == "ATIVO" for p in self._ler("")))

    def test_status_desconhecido_preservado_nao_vira_ativo(self):
        perfis = self._ler("SUSPENSO")
        self.assertTrue(perfis)
        self.assertTrue(all(p.situacao == "SUSPENSO" for p in perfis))

    def test_status_propaga_para_todos_os_perfis_do_usuario(self):
        # usuario bloqueado com 2 acessos -> os 2 PerfilAcesso ficam BLOQUEADO
        perfis = self._ler("BLOQUEADO")
        self.assertEqual(len(perfis), 2)
        self.assertEqual({p.situacao for p in perfis}, {"BLOQUEADO"})

    def test_mistura_ativo_e_bloqueado_no_mesmo_extrato(self):
        arq = _sig_xlsx([
            ["LOGIN", "NM_USER", "STATUS", "CPF", "EMAIL", "10", "12"],
            ["ativo1", "A", "ATIVO", "1", "", "X", ""],
            ["bloq1", "B", "BLOQUEADO", "2", "", "X", "X"],
            ["inat1", "I", "INATIVO", "3", "", "X", ""],
        ])
        try:
            perfis = self.leitor.ler_um(arq)
            sit = {}
            for p in perfis:
                sit.setdefault(p.usuario, set()).add(p.situacao)
            self.assertEqual(sit["ativo1"], {"ATIVO"})
            self.assertEqual(sit["bloq1"], {"BLOQUEADO"})
            self.assertEqual(sit["inat1"], {"INATIVO"})
        finally:
            os.unlink(arq)


# ─────────────── Integracao ponta-a-ponta pelo servico ───────────────
class TestServicoDesligadoStatus(unittest.TestCase):
    def setUp(self):
        self.servico = ServicoAnaliseDivergencias(perfis_esperados=[])

    def test_bloqueado_num_sistema_ativo_noutro(self):
        acessos = [
            _acesso("u1", vinc="20", situacao="BLOQUEADO", sistema=Sistema.SIG),
            _acesso("u1", vinc="20", situacao="ATIVO", sistema=Sistema.SYSTUR),
        ]
        divs = [d for d in self.servico.analisar(acessos=acessos, ativos=[],
                                                 desligados=[_desligado("20")], transferidos=[])
                if d.tipo == TipoDivergencia.ACESSO_DESLIGADO]
        self.assertEqual(len(divs), 1)
        self.assertEqual(divs[0].sistema, Sistema.SYSTUR)

    def test_desligado_todo_bloqueado_nao_gera_desligado(self):
        acessos = [_acesso("u1", vinc="20", situacao="BLOQUEADO", sistema=Sistema.SIG)]
        divs = [d for d in self.servico.analisar(acessos=acessos, ativos=[],
                                                 desligados=[_desligado("20")], transferidos=[])
                if d.tipo == TipoDivergencia.ACESSO_DESLIGADO]
        self.assertEqual(divs, [])


if __name__ == "__main__":
    unittest.main()
