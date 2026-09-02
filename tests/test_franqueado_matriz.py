# -*- coding: utf-8 -*-
"""FRANQUEADO validado pela MATRIZ de lojas (cargo x atendimento x tipo de loja).

Pedido da area em 31/08/2026 ("Testes 1.docx", print 7), textual:

    "Precisamos definir a regra para franqueado, para franqueado nao tem a
     questao de espelho. O perfil para franqueado e uma validacao entre cargo +
     tipo de loja, existe uma matriz para franqueado."

Tres coisas nao obvias que estes testes travam:

1. A matriz **nao fecha para frente**. TIPO DE LOJA e TIPO DE ATENDIMENTO nao
   existem no cadastro (medido em 01/09: `local_trabalho` e `filial` 100%
   vazios). O nome do perfil e' que os codifica. Entao a regra valida
   ADERENCIA ("o cargo justifica o perfil que ela TEM?") e NAO gera inclusao.

2. O arquivo tem um segundo bloco, "Perfis Excecoes", com 3 perfis que so'
   podem ser liberados com aval da Governanca de SI. Le-los como perfil
   esperado faria o painel MANDAR conceder MASTER_FRANQUEADO a todo gerente
   de franquia.

3. O cargo do RH nao fala a lingua da matriz (ATENDENTE x VENDEDOR). O de-para
   e' derivado do USO, com a mesma maioria de 70% do espelho — e nao pode
   engolir divergencia real.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import openpyxl

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import (
    RhAtivo, AcessoSistema, ValidacaoAcessoModel)
from infraestrutura.leitores_arquivos.leitor_matriz_franqueado import (
    LeitorMatrizFranqueado, RegraFranqueado, cargos_por_perfil,
    perfis_de_excecao, eh_matriz_franqueado)
from infraestrutura.leitores_arquivos.leitor_base import normalizar_nome_coluna as _N
from dominio.servicos_dominio.servico_depara_cargo import derivar_depara
from aplicacao.casos_de_uso.validar_acessos_sistema import ValidarAcessosSistema

SYS = "SYSTUR"
CAB = ["ACESSO MANUAL", "CARGO", "TIPO DE ATENDIMENTO", "TIPO DE LOJA", "PERFIL ACESSO"]

# recorte fiel do arquivo do cliente, com o bloco de excecao no fim
LINHAS = [
    ["SIM", "GERENTE", "ATENDIMENTO AO PUBLICO", "TERCEIRIZADA - FRANQUIA",
     "ATEND_PUBLIC_LJT_GERENTE_VC"],
    ["NÃO", "SUPERVISOR DE VENDAS", "ATENDIMENTO AO PUBLICO", "TERCEIRIZADA - FRANQUIA",
     "ATEND_PUBLIC_LJT_SUPERVISOR_VC"],
    ["NÃO", "SUPERVISOR ADMINISTRATIVO", "ATENDIMENTO AO PUBLICO", "TERCEIRIZADA - FRANQUIA",
     "ATEND_PUBLIC_LJT_SUPERVISOR_VC"],
    ["SIM", "ATENDENTE", "ATENDIMENTO AO PUBLICO", "TERCEIRIZADA - FRANQUIA",
     "ATEND_PUBLIC_LJT_VENDEDOR_VC"],
    ["NÃO", "CAIXA", "ATENDIMENTO AO PUBLICO", "LOJA PROPRIA",
     "ATEND_PUBLIC_LJP_CAIXA_VC"],
]
EXCECOES = [
    ["SIM", "GERENTE", "ATENDIMENTO AO PUBLICO", "TERCEIRIZADA - FRANQUIA", "FRANQUEADOS_VC"],
    ["SIM", "GERENTE", "ATENDIMENTO AO PUBLICO", "TERCEIRIZADA - FRANQUIA", "MASTER_FRANQUEADO"],
]


def _planilha(pasta, nome="MATRIZ DE PERFIL DE ACESSO SYSTUR - LOJAS.xlsx",
              titulo_excecao="Perfis Execeções: *"):
    """Reproduz a forma do arquivo real: matriz, linhas vazias, o titulo do
    bloco de excecao (com o erro de digitacao do original), o cabecalho
    REPETIDO e as excecoes."""
    p = Path(pasta) / nome
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(CAB)
    for l in LINHAS:
        ws.append(l)
    for _ in range(4):
        ws.append([])
    ws.append([titulo_excecao])
    ws.append(["*Os Perfis abaixo devem ser liberado para os usuários somente se "
               "tiver aprovação da área de Governança de Segurança da Informação"])
    ws.append(CAB)                     # o cabecalho se repete
    for l in EXCECOES:
        ws.append(l)
    wb.save(p)
    return p


class TestLeituraDaMatriz(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="cvc_franq_")

    def test_separa_matriz_de_excecao(self):
        rs = LeitorMatrizFranqueado().ler_um(_planilha(self._tmp))
        self.assertEqual(len([r for r in rs if not r.excecao]), len(LINHAS))
        self.assertEqual(sorted(r.perfil for r in rs if r.excecao),
                         ["FRANQUEADOS_VC", "MASTER_FRANQUEADO"])

    def test_excecao_nunca_vira_perfil_esperado(self):
        """O ponto de todo o cuidado: se MASTER_FRANQUEADO entrasse no indice,
        o painel mandaria conceder o perfil mais poderoso da base."""
        rs = LeitorMatrizFranqueado().ler_um(_planilha(self._tmp))
        cpp = cargos_por_perfil(rs)
        for p in perfis_de_excecao(rs):
            self.assertNotIn(p, cpp)
        self.assertIn(_N("MASTER_FRANQUEADO"), perfis_de_excecao(rs))

    def test_titulo_do_bloco_com_erro_de_digitacao(self):
        """O arquivo do cliente escreve 'Execeções' (E e X trocados). Procurar
        a palavra certa nao acha nada e as 3 excecoes entram como esperado."""
        for titulo in ("Perfis Execeções: *", "Perfis Exceções:", "PERFIS EXCECOES"):
            with self.subTest(titulo=titulo):
                rs = LeitorMatrizFranqueado().ler_um(
                    _planilha(self._tmp, nome="m_%d.xlsx" % abs(hash(titulo)),
                              titulo_excecao=titulo))
                self.assertEqual(len([r for r in rs if r.excecao]), len(EXCECOES))

    def test_cabecalho_repetido_nao_vira_regra(self):
        rs = LeitorMatrizFranqueado().ler_um(_planilha(self._tmp))
        self.assertNotIn("CARGO", [r.cargo.upper() for r in rs])

    def test_acesso_manual(self):
        rs = LeitorMatrizFranqueado().ler_um(_planilha(self._tmp))
        manual = {r.perfil for r in rs if r.acesso_manual}
        self.assertIn("ATEND_PUBLIC_LJT_GERENTE_VC", manual)
        self.assertNotIn("ATEND_PUBLIC_LJT_SUPERVISOR_VC", manual)

    def test_indice_ao_contrario(self):
        """perfil -> cargos autorizados. Um perfil pode servir a 2 cargos."""
        cpp = cargos_por_perfil(LeitorMatrizFranqueado().ler_um(_planilha(self._tmp)))
        self.assertEqual(cpp[_N("ATEND_PUBLIC_LJT_SUPERVISOR_VC")],
                         {_N("SUPERVISOR DE VENDAS"), _N("SUPERVISOR ADMINISTRATIVO")})
        self.assertEqual(cpp[_N("ATEND_PUBLIC_LJT_GERENTE_VC")], {_N("GERENTE")})

    def test_reconhece_o_arquivo_pelo_cabecalho(self):
        self.assertTrue(eh_matriz_franqueado(CAB))
        self.assertFalse(eh_matriz_franqueado(
            ["CCUSTO", "CARGO", "PERFIL ACESSO"]))     # matriz de sistema por CC

    def test_ler_pasta_ignora_arquivo_de_outro_leitor(self):
        pasta = tempfile.mkdtemp(prefix="cvc_franq_pasta_")
        _planilha(pasta)
        outra = Path(pasta) / "MATRIZ DE PERFIL DE ACESSO SYSTUR.xlsx"
        wb = openpyxl.Workbook(); ws = wb.active
        ws.append(["CCUSTO", "CARGO", "PERFIL ACESSO"])
        ws.append(["100", "ANALISTA", "P1"])
        wb.save(outra)
        regras, lidos = LeitorMatrizFranqueado().ler(pasta)
        self.assertEqual(lidos, ["MATRIZ DE PERFIL DE ACESSO SYSTUR - LOJAS.xlsx"])
        self.assertEqual(len(regras), len(LINHAS) + len(EXCECOES))


class TestDeParaDeCargo(unittest.TestCase):
    """O de-para nasce do uso: e' proposta medida, nao lista pedida a area."""

    def setUp(self):
        self._cpp = cargos_por_perfil(LeitorMatrizFranqueado().ler_um(
            _planilha(tempfile.mkdtemp(prefix="cvc_dp_"))))

    def test_deriva_sinonimo_de_cargo(self):
        pares = [(_N("VENDEDOR"), _N("ATEND_PUBLIC_LJT_VENDEDOR_VC"))] * 10
        dp = derivar_depara(pares, self._cpp)
        self.assertEqual(dp[_N("VENDEDOR")].cargo_matriz, _N("ATENDENTE"))
        self.assertEqual(dp[_N("VENDEDOR")].consistencia, 1.0)

    def test_cargo_que_ja_esta_na_matriz_nao_ganha_tradutor(self):
        """Mapear GERENTE esconderia divergencia: um GERENTE com perfil de
        ATENDENTE viraria 'ATENDENTE' e sairia aderente."""
        pares = [(_N("GERENTE"), _N("ATEND_PUBLIC_LJT_VENDEDOR_VC"))] * 10
        self.assertEqual(derivar_depara(pares, self._cpp), {})

    def test_perfil_de_dois_cargos_vota_nos_dois(self):
        """Descartar o perfil ambiguo deixava 'SUPERVISOR' sem tradutor e
        gerava divergencia falsa (626 x 231 medidos em 02/09)."""
        pares = [(_N("SUPERVISOR"), _N("ATEND_PUBLIC_LJT_SUPERVISOR_VC"))] * 8
        dp = derivar_depara(pares, self._cpp)
        self.assertIn(dp[_N("SUPERVISOR")].cargo_matriz,
                      {_N("SUPERVISOR DE VENDAS"), _N("SUPERVISOR ADMINISTRATIVO")})
        self.assertEqual(dp[_N("SUPERVISOR")].consistencia, 1.0)

    def test_abaixo_do_limiar_nao_vira_equivalencia(self):
        pares = ([(_N("MISTO"), _N("ATEND_PUBLIC_LJT_VENDEDOR_VC"))] * 5
                 + [(_N("MISTO"), _N("ATEND_PUBLIC_LJT_GERENTE_VC"))] * 5)
        self.assertEqual(derivar_depara(pares, self._cpp), {})

    def test_poucos_acessos_nao_viram_padrao(self):
        pares = [(_N("RARO"), _N("ATEND_PUBLIC_LJT_VENDEDOR_VC"))] * 2
        self.assertEqual(derivar_depara(pares, self._cpp), {})

    def test_perfil_fora_da_matriz_nao_vota(self):
        pares = [(_N("QUALQUER"), _N("PERFIL_DESCONHECIDO"))] * 10
        self.assertEqual(derivar_depara(pares, self._cpp), {})

    def test_resultado_nao_depende_da_ordem_de_leitura(self):
        pares = [(_N("SUPERVISOR"), _N("ATEND_PUBLIC_LJT_SUPERVISOR_VC"))] * 8
        a = derivar_depara(pares, self._cpp)[_N("SUPERVISOR")].cargo_matriz
        b = derivar_depara(list(reversed(pares)), self._cpp)[_N("SUPERVISOR")].cargo_matriz
        self.assertEqual(a, b)


def _cenario(cargo, perfis, ligada=True, vinculo="FRANQUEADO", colegas=()):
    tmp = tempfile.mkdtemp(prefix="cvc_franqv_")
    regras = LeitorMatrizFranqueado().ler_um(_planilha(tmp))
    cx = ConexaoBancoDados(os.path.join(tmp, "d.db"))
    cx.inicializar()
    s = cx.sessao()
    s.add(RhAtivo(matricula="M1", nome="ANA", cpf="11111111111",
                  cargo_descricao=cargo, situacao="ATIVO", tipo_vinculo=vinculo,
                  empresa="FRANQUIAS", gestor="CHEFE"))
    for p in perfis:
        s.add(AcessoSistema(sistema=SYS, usuario="ana", perfil=p,
                            matricula_vinculada="M1", situacao="ATIVO"))
    for i, (cg, ps) in enumerate(colegas, start=2):
        s.add(RhAtivo(matricula="M%d" % i, nome="COLEGA%d" % i,
                      cpf="%011d" % i, cargo_descricao=cg, situacao="ATIVO",
                      tipo_vinculo=vinculo, empresa="FRANQUIAS", gestor="CHEFE"))
        for p in ps:
            s.add(AcessoSistema(sistema=SYS, usuario="c%d" % i, perfil=p,
                                matricula_vinculada="M%d" % i, situacao="ATIVO"))
    s.commit(); s.close()
    ValidarAcessosSistema(
        cx, matriz_franqueado=regras if ligada else None).executar()
    s = cx.sessao()
    rows = [(r.status, r.origem_matriz, r.motivo_status or "",
             r.perfil_atual or "", r.perfil_esperado or "")
            for r in s.query(ValidacaoAcessoModel)
            .filter_by(matricula="M1", sistema=SYS).all()]
    s.close()
    return rows


class TestValidacaoPelaMatriz(unittest.TestCase):

    def test_cargo_autoriza_o_perfil_e_aderente(self):
        rows = _cenario("GERENTE", ["ATEND_PUBLIC_LJT_GERENTE_VC"])
        self.assertEqual(len(rows), 1)
        status, origem, motivo, atual, _ = rows[0]
        self.assertEqual(status, "OK")
        self.assertEqual(origem, "MATRIZ_FRANQUEADO")
        self.assertIn("autoriza", motivo)
        self.assertEqual(atual, "ATEND_PUBLIC_LJT_GERENTE_VC")

    def test_cargo_nao_autoriza_e_divergente(self):
        """ATENDENTE com perfil de GERENTE: escalada de privilegio."""
        rows = _cenario("ATENDENTE", ["ATEND_PUBLIC_LJT_GERENTE_VC"])
        status, origem, motivo, _, esperado = rows[0]
        self.assertEqual(status, "DIVERGENTE")
        self.assertEqual(origem, "MATRIZ_FRANQUEADO")
        self.assertIn("CARGO_NAO_AUTORIZA_PERFIL", motivo)
        # a tela mostra o que o cargo dela DARIA direito
        self.assertIn("ATEND_PUBLIC_LJT_VENDEDOR_VC", esperado)

    def test_perfil_de_excecao_vai_para_analise_citando_a_governanca(self):
        rows = _cenario("GERENTE", ["MASTER_FRANQUEADO"])
        status, origem, motivo, _, esperado = rows[0]
        self.assertEqual(status, "EM_ANALISE")
        self.assertIn("PERFIL_EXCECAO_GOVERNANCA", motivo)
        self.assertIn("Governanca", motivo)
        # nao sugere conceder nada
        self.assertEqual(esperado, "")

    def test_excecao_predomina_sobre_o_resto(self):
        rows = _cenario("GERENTE", ["ATEND_PUBLIC_LJT_GERENTE_VC", "FRANQUEADOS_VC"])
        self.assertEqual(rows[0][0], "EM_ANALISE")
        self.assertIn("PERFIL_EXCECAO_GOVERNANCA", rows[0][2])

    def test_de_para_torna_aderente_o_sinonimo_de_cargo(self):
        colegas = [("VENDEDOR", ["ATEND_PUBLIC_LJT_VENDEDOR_VC"]) for _ in range(6)]
        rows = _cenario("VENDEDOR", ["ATEND_PUBLIC_LJT_VENDEDOR_VC"], colegas=colegas)
        self.assertEqual(rows[0][0], "OK")
        self.assertIn("tratado como", rows[0][2])   # o de-para aparece na tela

    def test_de_para_nao_engole_divergencia(self):
        """VENDEDOR tratado como ATENDENTE continua sem direito a GERENTE."""
        colegas = [("VENDEDOR", ["ATEND_PUBLIC_LJT_VENDEDOR_VC"]) for _ in range(6)]
        rows = _cenario("VENDEDOR", ["ATEND_PUBLIC_LJT_GERENTE_VC"], colegas=colegas)
        self.assertEqual(rows[0][0], "DIVERGENTE")

    def test_sem_acesso_nao_vira_inclusao(self):
        """A matriz nao fecha para frente: sem TIPO DE LOJA nao da' para dizer
        QUAL perfil conceder. Franqueado sem acesso nao sai da matriz."""
        rows = _cenario("GERENTE", [])
        self.assertEqual([r for r in rows if r[1] == "MATRIZ_FRANQUEADO"], [])

    def test_perfil_fora_da_matriz_fica_com_o_espelho(self):
        colegas = [("GERENTE", ["OUTRO_PERFIL"]) for _ in range(4)]
        rows = _cenario("GERENTE", ["OUTRO_PERFIL"], colegas=colegas)
        self.assertEqual([r for r in rows if r[1] == "MATRIZ_FRANQUEADO"], [])

    def test_nao_gera_registro_duplicado_com_o_espelho(self):
        colegas = [("GERENTE", ["ATEND_PUBLIC_LJT_GERENTE_VC"]) for _ in range(4)]
        rows = _cenario("GERENTE", ["ATEND_PUBLIC_LJT_GERENTE_VC"], colegas=colegas)
        self.assertEqual(len(rows), 1, "matriz e espelho gravaram os dois")
        self.assertEqual(rows[0][1], "MATRIZ_FRANQUEADO")

    def test_regra_desligada_mantem_o_comportamento_antigo(self):
        colegas = [("GERENTE", ["ATEND_PUBLIC_LJT_GERENTE_VC"]) for _ in range(4)]
        rows = _cenario("GERENTE", ["ATEND_PUBLIC_LJT_GERENTE_VC"],
                        ligada=False, colegas=colegas)
        self.assertEqual([r for r in rows if r[1] == "MATRIZ_FRANQUEADO"], [])
        self.assertTrue(any(r[1] == "ESPELHO_FRANQUEADO" for r in rows))

    def test_so_franqueado_entra_na_regra(self):
        rows = _cenario("GERENTE", ["ATEND_PUBLIC_LJT_GERENTE_VC"], vinculo="TERCEIRO")
        self.assertEqual([r for r in rows if r[1] == "MATRIZ_FRANQUEADO"], [])


class TestMotivoSobrevive(unittest.TestCase):
    """Conta sem status no extrato leva o resultado a 'Em Analise' (regra da
    area). O STATUS muda, mas o PORQUE nao pode ser apagado — senao a escalada
    de privilegio some da tela. Medido em 02/09: eram 4.843 linhas."""

    def test_conta_indefinida_preserva_o_motivo_da_matriz(self):
        tmp = tempfile.mkdtemp(prefix="cvc_franq_ind_")
        regras = LeitorMatrizFranqueado().ler_um(_planilha(tmp))
        cx = ConexaoBancoDados(os.path.join(tmp, "d.db"))
        cx.inicializar()
        s = cx.sessao()
        s.add(RhAtivo(matricula="M1", nome="ANA", cpf="11111111111",
                      cargo_descricao="ATENDENTE", situacao="ATIVO",
                      tipo_vinculo="FRANQUEADO", empresa="F", gestor="C"))
        s.add(AcessoSistema(sistema=SYS, usuario="ana",
                            perfil="ATEND_PUBLIC_LJT_GERENTE_VC",
                            matricula_vinculada="M1", situacao=""))   # sem status
        s.commit(); s.close()
        ValidarAcessosSistema(cx, matriz_franqueado=regras).executar()
        s = cx.sessao()
        r = s.query(ValidacaoAcessoModel).filter_by(matricula="M1").one()
        s.close()
        self.assertEqual(r.status, "EM_ANALISE")
        self.assertIn("CONTA_INDEFINIDA", r.motivo_status)
        self.assertIn("CARGO_NAO_AUTORIZA_PERFIL", r.motivo_status)


if __name__ == "__main__":
    unittest.main()
