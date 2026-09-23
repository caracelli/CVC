# -*- coding: utf-8 -*-
"""ANCORA NO PERFIL DO SYSTUR — o Oracle depende do que a pessoa tem no SYSTUR.

Regra definida pela area em 23/09/2026, textual:

    "a regra e ele so pode ter os acessos oracle se o perfil bater com o
     systur que ele tem, se no systur nao vier perfil e pendencia systur,
     entendeu, se no oracle o perfil ou acesso divergir do systur e pendencia
     oracle"

O QUE MUDOU
  antes: a matriz do Oracle EBS casava por (centro de custo, cargo) e a pessoa
         recebia TODAS as responsabilidades daquele par. A coluna PERFIL SYSTUR
         existia no arquivo do cliente (39 valores, 2.556 linhas) e o leitor a
         descartava em silencio.
  agora: a linha da matriz so' vale se a pessoa tiver, no SYSTUR, o perfil que
         a coluna aponta. A CCO entra pela FUNCAO, traduzida pelas linhas de
         'Systur' da propria CCO.

O QUE ESTES TESTES PROTEGEM, em ordem de importancia:
  1. a regra nao pode ESCONDER ninguem — quem tem acesso e ficou sem esperado
     ganha linha de pendencia (era o risco real da mudanca);
  2. o filtro so' ESTREITA: linha que nao fala de SYSTUR fica como estava;
  3. lista de sistemas vazia = regra desligada, comportamento anterior.

Medido em 23/09/2026 na base de 15/09 (457 pessoas com Oracle vivo): 190 sem
perfil no SYSTUR, 106 com perfil que matriz nenhuma conhece, 99 divergentes,
17 a incluir, 45 aderentes.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import (
    RhAtivo, AcessoSistema, MatrizCcoModel, PerfilEsperadoModel,
    ValidacaoAcessoModel)
from aplicacao.casos_de_uso.validar_acessos_sistema import ValidarAcessosSistema

ORA = "ORACLE_EBS"
SYS = "SYSTUR"
CC = "01.02.03"
CARGO = "ANALISTA FINANCEIRO"


def _base(perfis_systur_da_pessoa, acessos_oracle, com_cco=True,
          com_matriz=True):
    """Uma pessoa (M1), duas responsabilidades Oracle na matriz.

    A matriz preve:
        CUSTOS       -> 'CVC GL CUSTOS'
        INTERCOMPANY -> 'CVC GL INTERCOMPANY'
    Quem tem CUSTOS no SYSTUR so' pode receber a primeira.

    A CCO preve, para a funcao 'A Receber 1', o 'CVC AR BRASIL'; e as linhas de
    'Systur' da CCO traduzem A_RECEBER_1 <-> 'A Receber 1'.
    """
    tmp = tempfile.mkdtemp(prefix="cvc_ancora_")
    cx = ConexaoBancoDados(os.path.join(tmp, "d.db"))
    cx.inicializar()
    s = cx.sessao()

    s.add(RhAtivo(matricula="M1", nome="PESSOA UM", cpf="00000000001",
                  cargo_codigo="CG", cargo_descricao=CARGO,
                  centro_custo_codigo=CC, gestor="GESTOR X", situacao="ATIVO",
                  tipo_vinculo="FUNCIONARIO"))
    # um colega com Oracle, so' para o sistema ter extrato
    s.add(RhAtivo(matricula="M2", nome="PESSOA DOIS", cpf="00000000002",
                  cargo_codigo="CG", cargo_descricao=CARGO,
                  centro_custo_codigo=CC, gestor="GESTOR X", situacao="ATIVO",
                  tipo_vinculo="FUNCIONARIO"))
    s.add(AcessoSistema(sistema=ORA, usuario="u2", perfil="CVC GL CUSTOS",
                        matricula_vinculada="M2", situacao="ATIVO"))
    s.add(AcessoSistema(sistema=SYS, usuario="s2", perfil="CUSTOS",
                        matricula_vinculada="M2", situacao="ATIVO"))

    for p in perfis_systur_da_pessoa:
        s.add(AcessoSistema(sistema=SYS, usuario="s1", perfil=p,
                            matricula_vinculada="M1", situacao="ATIVO"))
    for p in acessos_oracle:
        s.add(AcessoSistema(sistema=ORA, usuario="u1", perfil=p,
                            matricula_vinculada="M1", situacao="ATIVO"))

    if com_matriz:
        for perfil, p_systur in (("CVC GL CUSTOS", "CUSTOS"),
                                 ("CVC GL INTERCOMPANY", "INTERCOMPANY")):
            s.add(PerfilEsperadoModel(cargo_codigo=CC, cargo_descricao=CARGO,
                                      sistema=ORA, perfil=perfil,
                                      perfil_systur=p_systur))
    if com_cco:
        s.add(MatrizCcoModel(cc=CC, gestor="GESTOR X", funcao="A Receber 1",
                             sistema="Oracle EBS", perfil="CVC AR BRASIL"))
        s.add(MatrizCcoModel(cc=CC, gestor="GESTOR X", funcao="A Receber 1",
                             sistema="Systur", perfil="A_RECEBER_1"))
    s.commit(); s.close()
    return cx


def _rodar(cx, ancora=(ORA,), isentos=()):
    uc = ValidarAcessosSistema(cx, ancora_systur_sistemas=list(ancora),
                               ancora_systur_isentos=list(isentos))
    uc.executar()
    return uc


def _linhas(cx, sistema, mat="M1"):
    s = cx.sessao()
    r = sorted((x.status, x.perfil_esperado or "", x.motivo_status or "")
               for x in s.query(ValidacaoAcessoModel).filter_by(matricula=mat).all()
               if x.sistema == sistema)
    s.close()
    return r


class OFiltroEstreitaOEsperado(unittest.TestCase):

    def test_so_vem_o_que_o_perfil_do_systur_autoriza(self):
        """⭐ O coracao da regra. Ela tem CUSTOS no SYSTUR: a matriz preve dois
        acessos Oracle, mas so' o de CUSTOS e' dela."""
        cx = _base(["CUSTOS"], [], com_cco=False)
        _rodar(cx)
        self.assertEqual(
            [(st, esp) for st, esp, _ in _linhas(cx, ORA)],
            [("SEM_ACESSO", "CVC GL CUSTOS")])

    def test_sem_a_ancora_vinham_os_dois(self):
        """Nao-regressao: lista de sistemas vazia = comportamento anterior."""
        cx = _base(["CUSTOS"], [], com_cco=False)
        _rodar(cx, ancora=())
        self.assertEqual(
            sorted(esp for _, esp, _ in _linhas(cx, ORA)),
            ["CVC GL CUSTOS", "CVC GL INTERCOMPANY"])

    def test_a_cco_entra_pela_funcao_traduzida(self):
        """A_RECEBER_1 no extrato -> funcao 'A Receber 1' -> o Oracle dela.

        A traducao vem das linhas de 'Systur' da propria CCO: a matriz do
        Oracle usa o nome tecnico e a CCO usa o nome humano.

        SEM MATRIZ de proposito: desde 23/09 a matriz por cargo tem
        PRECEDENCIA (ver test_matriz_antes_da_cco.py), entao a CCO so' responde
        pelo sistema sobre o qual a matriz calou. Com as duas, este caminho
        nem seria alcancado — e o teste estaria verde medindo outra coisa."""
        cx = _base(["A_RECEBER_1"], [], com_matriz=False)
        _rodar(cx)
        self.assertEqual(
            [(st, esp) for st, esp, _ in _linhas(cx, ORA)],
            [("SEM_ACESSO", "CVC AR BRASIL")])

    def test_quem_adere_continua_aderente(self):
        cx = _base(["CUSTOS"], ["CVC GL CUSTOS"], com_cco=False)
        _rodar(cx)
        self.assertEqual([st for st, _, _ in _linhas(cx, ORA)], ["OK"])


class QuantosPerfisAPessoaPodeTer(unittest.TestCase):
    """Retorno da area (Bruna) em 23/09/2026, sobre a matricula 90001455:

        "Ela pode ter acesso a 3 perfis do oracle e tem um so entao esta
         errado"

    A CCO da' 4 perfis do Oracle a funcao dela ("Atendimento a fornecedores
    CVC e VISUAL"), ela TEM os 4, e a coluna "Perfil Esperado" mostrava um so'
    — o primeiro que casou. Mesmo defeito do perfil excessivo (corrigido em
    28/08) e do perfil_atual (22/09), agora no campo do ESPERADO.

    Regra do usuario: "para matriz ele traz somente o que casa para incluir,
    para cco precisa trazer todos — para cco todos os perfis encontrados sao
    acessos que a pessoa PODE ter".

    Este caso e' tambem a prova de que a ancora e o campo trabalham juntos:
    sem a ancora a Priscila veria 8 perfis (os 4 dela + 4 de OUTRAS funcoes da
    mesma gestora, porque a CCO casa por cc+gestor, nao por funcao).
    """

    def _priscila(self, ancora):
        tmp = tempfile.mkdtemp(prefix="cvc_esp_")
        cx = ConexaoBancoDados(os.path.join(tmp, "d.db"))
        cx.inicializar()
        s = cx.sessao()
        s.add(RhAtivo(matricula="90001455", nome="PRISCILA SANTOS DE LIMA",
                      cpf="00090001455", cargo_codigo="CG",
                      cargo_descricao="ANALISTA FINANCEIRO JR",
                      centro_custo_codigo="01.06.04.01",
                      gestor="HELEN ANTONIA LA SPINA RUAS", situacao="ATIVO",
                      tipo_vinculo="FUNCIONARIO"))
        dela = ["CVC AP NOVA VISUAL Consulta", "CVC AP BRASIL Consulta",
                "CVC AP SUBMARINO Consulta", "CVC AP VISUAL Consulta"]
        # a funcao DELA
        for p in dela:
            s.add(MatrizCcoModel(cc="01.06.04.01",
                                 gestor="HELEN ANTONIA LA SPINA RUAS",
                                 funcao="Atendimento a fornecedores  CVC e VISUAL",
                                 sistema="Oracle EBS", perfil=p))
        s.add(MatrizCcoModel(cc="01.06.04.01",
                             gestor="HELEN ANTONIA LA SPINA RUAS",
                             funcao="Atendimento a fornecedores  CVC e VISUAL",
                             sistema="Systur", perfil="ATD_FOR_CVC_VISUAL_CP"))
        # OUTRA funcao do MESMO cc+gestor — e' o que vaza sem a ancora
        for p in ("CVC GL BRASIL Consulta", "CVC GL VISUAL Consulta"):
            s.add(MatrizCcoModel(cc="01.06.04.01",
                                 gestor="HELEN ANTONIA LA SPINA RUAS",
                                 funcao="Atendimento ao Fornecedor C&H",
                                 sistema="Oracle EBS", perfil=p))
        s.add(MatrizCcoModel(cc="01.06.04.01",
                             gestor="HELEN ANTONIA LA SPINA RUAS",
                             funcao="Atendimento ao Fornecedor C&H",
                             sistema="Systur", perfil="ATD_FOR_CH"))
        s.add(AcessoSistema(sistema=SYS, usuario="pslima",
                            perfil="ATD_FOR_CVC_VISUAL_CP",
                            matricula_vinculada="90001455", situacao="ATIVO"))
        for p in dela:
            s.add(AcessoSistema(sistema=ORA, usuario="pslima", perfil=p,
                                matricula_vinculada="90001455", situacao="ATIVO"))
        s.commit(); s.close()
        _rodar(cx, ancora=ancora)
        s = cx.sessao()
        r = [(x.status, x.perfil_esperado or "")
             for x in s.query(ValidacaoAcessoModel)
             .filter_by(matricula="90001455", sistema=ORA).all()]
        s.close()
        return r

    def test_a_linha_aderente_lista_os_quatro(self):
        """⭐ O apontamento dela: eram 4, a tela mostrava 1."""
        r = self._priscila(ancora=(ORA,))
        self.assertEqual(len(r), 1)
        status, esperado = r[0]
        self.assertEqual(status, "OK")
        self.assertEqual(
            sorted(x.strip() for x in esperado.split(",")),
            sorted(["CVC AP NOVA VISUAL Consulta", "CVC AP BRASIL Consulta",
                    "CVC AP SUBMARINO Consulta", "CVC AP VISUAL Consulta"]))

    def test_sem_a_ancora_vazariam_os_da_outra_funcao(self):
        """A CCO casa por cc+GESTOR, nao por funcao: sem a ancora ela herdaria
        os perfis das outras funcoes da mesma gestora. E' o perfil do SYSTUR
        que diz qual das funcoes daquele par e' a dela."""
        _, esperado = self._priscila(ancora=())[0]
        self.assertIn("CVC GL BRASIL Consulta", esperado,
                      "sem a ancora, o vazamento e' justamente o defeito")

    def test_a_matriz_tambem_lista_todos_os_previstos(self):
        """⭐ Mudou na validacao visual de 23/09, e o caso explica por que.

        GILDA (34530435), ANALISTA CUSTOS SR: o perfil INTERCOMPANY dela
        autoriza 47 acessos do Oracle; ela tem 42, dos quais 41 AUTORIZADOS e
        UM fora (o relatorio de despesas). Com o campo guardando so' o perfil
        que casou, a tela comparava 42 contra 1 e anunciava "41 a mais" — um
        alarme falso de 41 para 1.

        A regra do usuario ("para matriz traz so' o que casa para incluir")
        vale para as linhas de INCLUSAO, que saem uma por perfil num ramo
        proprio. Este campo e' a base do delta da tela: incompleto, ele mente.
        """
        cx = _base(["CUSTOS", "INTERCOMPANY"], ["CVC GL CUSTOS"], com_cco=False)
        _rodar(cx)
        s = cx.sessao()
        r = [x.perfil_esperado for x in s.query(ValidacaoAcessoModel)
             .filter_by(matricula="M1", sistema=ORA).all()]
        s.close()
        self.assertEqual(len(r), 1, "continua UMA linha de aderente")
        self.assertEqual(sorted(x.strip() for x in r[0].split(",")),
                         ["CVC GL CUSTOS", "CVC GL INTERCOMPANY"],
                         "o previsto tem de vir inteiro, senao o delta mente")


class NinguemPodeSumir(unittest.TestCase):
    """O risco real da mudanca: filtrar o esperado poderia APAGAR a linha de
    quem tem acesso — exatamente o oposto do que a regra quer."""

    def test_acesso_sem_nenhum_esperado_ainda_gera_linha(self):
        """⭐ Ela tem um Oracle que perfil nenhum do SYSTUR dela preve. O filtro
        zera o esperado; a cobranca precisa criar a linha."""
        cx = _base(["CUSTOS"], ["CVC AP BRASIL MASTER"], com_cco=False)
        _rodar(cx)
        linhas = _linhas(cx, ORA)
        self.assertEqual(len(linhas), 1)
        self.assertEqual(linhas[0][0], "EM_ANALISE")
        self.assertIn("PERFIL_FORA_DO_SYSTUR", linhas[0][2])

    def test_sem_perfil_no_systur_vira_pendencia_no_systur(self):
        """"se no systur nao vier perfil e pendencia systur"."""
        cx = _base([], ["CVC GL CUSTOS"], com_cco=False)
        uc = _rodar(cx)
        linhas = _linhas(cx, SYS)
        self.assertEqual([st for st, _, _ in linhas], ["EM_ANALISE"])
        self.assertIn("SEM_PERFIL_SYSTUR_COM_ORACLE", linhas[0][2])
        self.assertEqual(uc._ancora_sem_systur, 1)

    def test_a_pendencia_do_systur_nao_duplica(self):
        cx = _base([], ["CVC GL CUSTOS"], com_cco=False)
        _rodar(cx)
        self.assertEqual(len(_linhas(cx, SYS)), 1)

    def test_quem_nao_tem_oracle_nao_e_cobrado(self):
        """Sem acesso no Oracle nao ha' o que ancorar: a falta de perfil no
        SYSTUR dela nao vira pendencia por causa desta regra."""
        cx = _base([], [], com_cco=False)
        uc = _rodar(cx)
        self.assertEqual(uc._ancora_sem_systur, 0)


class AMatrizNaoCobreOCargo(unittest.TestCase):
    """Pedido da area (Bruna) em 23/09/2026, sobre a matricula 1303:

        "tem o centro de custo dele mas nao tem o cargo no EBS, ai vai ter que
         vir o perfil que pode ter no systur e no ebs vir que nao esta
         mapeado, isso pode acontecer"

    Nao e' pendencia: enquanto a matriz nao disser o que o cargo pode ter, nao
    ha' o que incluir nem o que revogar. A falta que gera acao e' a do SYSTUR.
    Na base de 15/09 a matriz do Oracle cobre 307 dos 13.733 ativos — o caso e'
    a norma, nao a excecao.
    """

    def _sem_matriz_de_oracle(self, perfis_systur, acessos_oracle):
        """Mesma base, mas a pessoa fica num cargo que a matriz NAO menciona."""
        tmp = tempfile.mkdtemp(prefix="cvc_anc_nm_")
        cx = ConexaoBancoDados(os.path.join(tmp, "d.db"))
        cx.inicializar()
        s = cx.sessao()
        s.add(RhAtivo(matricula="M1", nome="MARCELO", cpf="00000000001",
                      cargo_codigo="CG", cargo_descricao="EXECUTIVO VENDAS",
                      centro_custo_codigo="05.11.03.04", gestor="G",
                      situacao="ATIVO", tipo_vinculo="FUNCIONARIO"))
        # a matriz do Oracle fala de OUTRO cargo, em OUTRO centro de custo
        s.add(PerfilEsperadoModel(cargo_codigo=CC, cargo_descricao=CARGO,
                                  sistema=ORA, perfil="CVC GL CUSTOS",
                                  perfil_systur="CUSTOS"))
        # ...e a do SYSTUR mapeia o cargo dele (e' o "perfil que pode ter")
        s.add(PerfilEsperadoModel(cargo_codigo="05.11.03.04",
                                  cargo_descricao="EXECUTIVO VENDAS",
                                  sistema=SYS, perfil="ATEND_AGENCIA_LJP"))
        for p in perfis_systur:
            s.add(AcessoSistema(sistema=SYS, usuario="s1", perfil=p,
                                matricula_vinculada="M1", situacao="ATIVO"))
        for p in acessos_oracle:
            s.add(AcessoSistema(sistema=ORA, usuario="u1", perfil=p,
                                matricula_vinculada="M1", situacao="ATIVO"))
        s.commit(); s.close()
        return cx

    def test_o_caso_do_marcelo_inteiro(self):
        """⭐ Tem Oracle, nao tem SYSTUR, e a matriz do Oracle nao cobre o cargo.
        Saem DUAS linhas: o perfil que ele pode ter no SYSTUR (pendencia, que e'
        onde esta' a falta) e o Oracle como "Nao Mapeado" (informativo)."""
        cx = self._sem_matriz_de_oracle(
            [], ["CVC OIE BRASIL - Relatorio de Despesas"])
        uc = _rodar(cx)

        oracle = _linhas(cx, ORA)
        self.assertEqual(len(oracle), 1)
        self.assertEqual(oracle[0][0], "NAO_MAPEADO")
        self.assertIn("SEM_MAPEAMENTO_ORACLE_EBS", oracle[0][2])
        self.assertEqual(uc._ancora_nao_mapeado, 1)

        systur = _linhas(cx, SYS)
        self.assertEqual([st for st, _, _ in systur], ["EM_ANALISE"])
        self.assertEqual(systur[0][1], "ATEND_AGENCIA_LJP",
                         "o perfil que ele PODE ter precisa aparecer")

    def test_a_linha_nao_mapeada_mostra_o_acesso(self):
        cx = self._sem_matriz_de_oracle([], ["CVC OIE BRASIL - Relatorio"])
        _rodar(cx)
        s = cx.sessao()
        atual = [x.perfil_atual for x in s.query(ValidacaoAcessoModel)
                 .filter_by(matricula="M1", sistema=ORA).all()]
        s.close()
        self.assertEqual(atual, ["CVC OIE BRASIL - Relatorio"])

    def test_nao_mapeado_nao_e_pendencia(self):
        """O status informativo e' o ponto: NAO_MAPEADO nao entra em
        _STATUS_ACAO, entao a linha nao cobra acao de ninguem."""
        cx = self._sem_matriz_de_oracle([], ["CVC OIE BRASIL"])
        _rodar(cx)
        s = cx.sessao()
        sit = [x.situacao_acao for x in s.query(ValidacaoAcessoModel)
               .filter_by(matricula="M1", sistema=ORA).all()]
        s.close()
        self.assertEqual(sit, ["OK"])

    def test_com_perfil_no_systur_so_sai_a_linha_nao_mapeada(self):
        """Ela TEM perfil no SYSTUR, mas a matriz do Oracle nao cobre o cargo:
        nao ha' esperado para comparar, entao nao ha' divergencia a acusar —
        so' o informativo. Sem este ramo, a pessoa seria acusada de ter perfil
        "fora do SYSTUR" por um acesso que a matriz sequer menciona."""
        cx = self._sem_matriz_de_oracle(["CUSTOS"], ["CVC AP BRASIL MASTER"])
        uc = _rodar(cx)
        self.assertEqual([st for st, _, _ in _linhas(cx, ORA)], ["NAO_MAPEADO"])
        self.assertEqual(uc._ancora_divergentes, 0)
        self.assertEqual(uc._ancora_sem_systur, 0)

    def test_quem_a_matriz_cobre_nao_ganha_a_linha(self):
        """O discriminador: com o cargo na matriz, o caminho e' o normal."""
        cx = _base(["CUSTOS"], ["CVC GL CUSTOS"], com_cco=False)
        uc = _rodar(cx)
        self.assertEqual(uc._ancora_nao_mapeado, 0)
        self.assertEqual([st for st, _, _ in _linhas(cx, ORA)], ["OK"])


class PerfisIsentos(unittest.TestCase):
    """Acesso corporativo que matriz nenhuma prescreve. VAZIO em producao por
    decisao de 23/09 ("joga como pendencia"); a chave existe para recuar sem
    rebuild."""

    def test_isento_nao_conta_como_divergencia(self):
        cx = _base(["CUSTOS"], ["CVC GL CUSTOS", "CVC OIE BRASIL - RELATORIO"],
                   com_cco=False)
        _rodar(cx, isentos=["CVC OIE BRASIL"])
        self.assertEqual([st for st, _, _ in _linhas(cx, ORA)], ["OK"])

    def test_sem_a_isencao_ele_cobra(self):
        cx = _base(["CUSTOS"], ["CVC GL CUSTOS", "CVC OIE BRASIL - RELATORIO"],
                   com_cco=False)
        _rodar(cx)
        self.assertEqual([st for st, _, _ in _linhas(cx, ORA)], ["EM_ANALISE"])

    def test_a_isencao_casa_por_prefixo(self):
        cx = _base(["CUSTOS"], ["CVC GL CUSTOS",
                                "CVC OIE BRASIL - RELATORIO DE DESPESAS"],
                   com_cco=False)
        _rodar(cx, isentos=["cvc oie brasil"])
        self.assertEqual([st for st, _, _ in _linhas(cx, ORA)], ["OK"])


class OLeitorLeAColuna(unittest.TestCase):
    """A coluna existia no arquivo do cliente e era descartada em silencio."""

    def test_perfil_systur_chega_na_entidade(self):
        import openpyxl
        from infraestrutura.leitores_arquivos.leitor_matriz import LeitorMatrizPerfis
        from dominio.objetos_valor.sistema import Sistema

        tmp = Path(tempfile.mkdtemp(prefix="cvc_mtz_"))
        arq = tmp / "MATRIZ DE PERFIL DE ACESSO ORACLE EBS_teste.xlsx"
        wb = openpyxl.Workbook(); ws = wb.active
        ws.append(["titulo fundido"])          # a matriz do Oracle tem 1 linha antes
        ws.append(["ACESSO MANUAL", "CARGO", "CENTRO DE CUSTO", "AREA",
                   "PERFIL SYSTUR", "RESPONSABILIDADE"])
        ws.append(["NAO", CARGO, CC, "CFO", "CUSTOS", "CVC GL CUSTOS"])
        ws.append(["NAO", CARGO, CC, "CFO", "INTERCOMPANY", "CVC GL INTER"])
        wb.save(arq)

        perfis, _ = LeitorMatrizPerfis(
            str(tmp / "proc"), str(tmp / "err")).ler(
                str(tmp), sistemas_em_escopo={Sistema.ORACLE_EBS})
        self.assertEqual(
            sorted((p.perfil, p.perfil_systur) for p in perfis),
            [("CVC GL CUSTOS", "CUSTOS"), ("CVC GL INTER", "INTERCOMPANY")])


class OConfigEhAFonte(unittest.TestCase):

    def _cfg(self, xml):
        from infraestrutura.configuracao.leitor_config import LeitorConfig
        tmp = Path(tempfile.mkdtemp(prefix="cvc_cfg_")) / "config.xml"
        tmp.write_text(xml, encoding="utf-8")
        return LeitorConfig(str(tmp)).carregar()

    def test_config_do_projeto_ancora_o_oracle(self):
        from infraestrutura.configuracao.leitor_config import LeitorConfig
        raiz = Path(__file__).resolve().parent.parent
        cfg = LeitorConfig(str(
            raiz / "CVC_IAM_ANALYTICS/EXECUTAVEIS/CONFIG/config.xml")).carregar()
        self.assertEqual(cfg.validacao_ancora_systur_sistemas, ["ORACLE_EBS"])

    def test_producao_nao_isenta_ninguem(self):
        """Decisao de 23/09: "joga como pendencia". Se algum dia alguem
        preencher isso, o teste avisa que a decisao mudou."""
        from infraestrutura.configuracao.leitor_config import LeitorConfig
        raiz = Path(__file__).resolve().parent.parent
        cfg = LeitorConfig(str(
            raiz / "CVC_IAM_ANALYTICS/EXECUTAVEIS/CONFIG/config.xml")).carregar()
        self.assertEqual(cfg.validacao_ancora_systur_isentos, [])

    def test_config_antigo_sem_a_chave_fica_desligado(self):
        cfg = self._cfg("<configuracao><versao>1.0.0</versao></configuracao>")
        self.assertEqual(cfg.validacao_ancora_systur_sistemas, [])
        self.assertEqual(cfg.validacao_ancora_systur_isentos, [])

    def test_le_a_lista_de_isentos(self):
        cfg = self._cfg(
            "<configuracao><validacao><ancora_systur>"
            "<sistemas>ORACLE_EBS</sistemas>"
            "<perfis_isentos>CVC OIE BRASIL, CVC HR CONSULTA</perfis_isentos>"
            "</ancora_systur></validacao></configuracao>")
        self.assertEqual(cfg.validacao_ancora_systur_isentos,
                         ["CVC OIE BRASIL", "CVC HR CONSULTA"])


class TelaTraduzOsMotivosNovos(unittest.TestCase):
    """Passa pelo SQL real do painel (`_SQL_BI`): o motor grava o CODIGO e a
    materializacao vira texto. Se o CASE nao souber do codigo, a linha chega
    MUDA na tela — o analista ve uma pendencia sem saber por que. Ja' aconteceu
    com o encadeamento de motivos em 22/09."""

    def _bi(self, motivo_status):
        import sqlite3
        tmp = tempfile.mkdtemp(prefix="cvc_bi_anc_")
        db = os.path.join(tmp, "iam.db")
        ConexaoBancoDados(db).inicializar()
        c = sqlite3.connect(db)
        try:
            c.execute(
                "INSERT INTO validacao_acessos (matricula, nome, sistema,"
                " perfil_esperado, perfil_atual, status, motivo_status,"
                " dt_processamento) VALUES (?,?,?,?,?,?,?,?)",
                ("34530984", "BRENDA VASCONCELOS DERENCIO", ORA,
                 "CVC AP NOVA VISUAL Consulta", "CVC OIE BRASIL",
                 "EM_ANALISE", motivo_status, "2026-09-23 09:00:00"))
            c.commit()
            import visualizador.main as vm
            c.executescript(vm._SQL_BI)
            return c.execute("SELECT motivo, motivo_cod FROM bi_divergencias").fetchone()
        finally:
            c.close()

    def test_perfil_fora_do_systur_vira_texto(self):
        motivo, cod = self._bi("PERFIL_FORA_DO_SYSTUR")
        self.assertTrue(motivo, "a linha nao pode chegar muda na tela")
        self.assertIn("SYSTUR", motivo.upper())
        self.assertEqual(cod, "PERFIL_FORA_DO_SYSTUR")

    def test_motivo_encadeado_tambem_casa(self):
        """⭐ O motor encadeia ("PERFIL_FORA_DO_SYSTUR | PERFIL_EXCESSIVO") —
        81 linhas assim na base de 15/09. Igualdade exata deixaria cair no ELSE
        e a tela ficaria sem texto."""
        motivo, _ = self._bi("PERFIL_FORA_DO_SYSTUR | PERFIL_EXCESSIVO")
        self.assertIn("SYSTUR", motivo.upper())

    def test_sem_perfil_no_systur_vira_texto(self):
        motivo, _ = self._bi("SEM_PERFIL_SYSTUR_COM_ORACLE_EBS")
        self.assertTrue(motivo)
        self.assertIn("SYSTUR", motivo.upper())

    def test_sem_mapeamento_vira_texto_proprio(self):
        """Nao pode herdar o texto do NAO_MAPEADO antigo ("nao tem mapeamento
        localizado para o centro de custo"): aqui o centro de custo pode ate'
        estar na matriz — o que falta e' o CARGO, e a pessoa TEM acesso."""
        motivo, _ = self._bi("SEM_MAPEAMENTO_ORACLE_EBS")
        self.assertTrue(motivo, "a linha nao pode chegar muda na tela")
        self.assertNotIn("localizado para o centro de custo", motivo)
        self.assertIn("nao e uma pendencia", motivo.lower())


class ATelaMostraOAcessoQueMotivouAPendencia(unittest.TestCase):
    """A linha e' do SYSTUR e o `perfil_atual` dela e' (corretamente) vazio —
    entao a tela dizia "falta SYSTUR porque ela tem Oracle" sem nunca mostrar
    QUAL Oracle. Era a reclamacao original da area sobre a matricula 1303:
    "esses acessos dele precisam aparecer". 190 pessoas neste caso."""

    def _motivo(self, acessos, sistema=ORA):
        import sqlite3
        tmp = tempfile.mkdtemp(prefix="cvc_bi_lst_")
        db = os.path.join(tmp, "iam.db")
        ConexaoBancoDados(db).inicializar()
        c = sqlite3.connect(db)
        try:
            c.execute(
                "INSERT INTO validacao_acessos (matricula, nome, sistema,"
                " perfil_esperado, perfil_atual, status, motivo_status,"
                " dt_processamento) VALUES (?,?,?,?,?,?,?,?)",
                ("1303", "MARCELO DE CASTRO DIAS", SYS,
                 "ATEND_AGENCIA_LJP_PROMOTORES_VC", "", "EM_ANALISE",
                 "SEM_PERFIL_SYSTUR_COM_" + sistema, "2026-09-23 09:00:00"))
            for perfil, situacao in acessos:
                c.execute(
                    "INSERT INTO acessos_sistemas (sistema, usuario, perfil,"
                    " matricula_vinculada, situacao) VALUES (?,?,?,?,?)",
                    (sistema, "mcdias", perfil, "1303", situacao))
            c.commit()
            import visualizador.main as vm
            c.executescript(vm._SQL_BI)
            return c.execute("SELECT motivo FROM bi_divergencias").fetchone()[0]
        finally:
            c.close()

    def test_o_acesso_aparece_no_texto(self):
        """⭐ O caso do MARCELO: um unico acesso, o relatorio de despesas."""
        motivo = self._motivo([("CVC OIE BRASIL - Relatório de Despesas", "ATIVO")])
        self.assertIn("CVC OIE BRASIL - Relatório de Despesas", motivo)

    def test_conta_bloqueada_nao_e_listada(self):
        """Conta revogada nao e' acesso — listar seria afirmar posse que a
        propria regra de 22/07 nega."""
        motivo = self._motivo([("CVC AP BRASIL MASTER", "BLOQUEADO")])
        self.assertNotIn("CVC AP BRASIL MASTER", motivo)
        self.assertIn("nenhum ativo", motivo)

    def test_lista_longa_e_cortada_com_o_total(self):
        """O motivo vira um `title` nativo do navegador: 30 acessos ali ficam
        ilegiveis. 16 das 190 pessoas caem neste ramo."""
        motivo = self._motivo([(f"CVC PERFIL NUMERO {i:02d} Consulta", "ATIVO")
                               for i in range(30)])
        self.assertIn("30 acessos no total", motivo)
        self.assertLess(len(motivo), 800, "tooltip nao pode virar um paredao")

    def test_o_sistema_sai_do_codigo_do_motivo(self):
        motivo = self._motivo([("PERFIL X", "ATIVO")], sistema="SIGOT")
        self.assertIn("acesso no SIGOT", motivo)


class ALinhaNaoMapeadaApareceNaConsulta(unittest.TestCase):
    """A linha nova quase virou o defeito que ela veio corrigir.

    `_csCatDe` devolve null para "Nao Mapeado" — proposital, para o registro
    MARCADOR (que vem sem sistema) nao cair em "Necessario analise" como se
    fosse pendencia. E `_csSemMapeamento` so' listava sistema SEM NENHUMA
    linha. A linha criada em 23/09 tem sistema preenchido: caia nos dois
    filtros e SUMIA da tela, escondendo justamente o acesso que a area pediu
    para ver ("no ebs vir que nao esta mapeado", matricula 1303).
    """

    @classmethod
    def setUpClass(cls):
        import shutil
        import subprocess
        if not shutil.which("node"):
            raise unittest.SkipTest("node nao disponivel")
        cls.node = subprocess.run
        raiz = Path(__file__).resolve().parent.parent
        cls.html = (raiz / "CVC_IAM_ANALYTICS/EXECUTAVEIS/REPORT/index.html"
                    ).read_text(encoding="utf-8")

    def _rodar(self, divs_json):
        import json as _json
        import re
        import subprocess
        m = re.search(r"function _csSemMapeamento\(u\)\{[\s\S]*?\n\}", self.html)
        self.assertIsNotNone(m, "a funcao mudou de forma")
        script = (
            "const esc=s=>String(s==null?'':s);\n"
            "const _sisTodos=()=>['ORACLE_EBS','SICA_RA','SYSTUR','SIG'];\n"
            + m.group(0) + "\n"
            "console.log(_csSemMapeamento({divs:" + _json.dumps(divs_json) + "}));"
        )
        # encoding explicito: no Windows o default e' cp1252 e os nomes de
        # perfil tem acento ("Relatório de Despesas").
        r = subprocess.run(["node", "-e", script], capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_o_acesso_do_sistema_nao_mapeado_aparece(self):
        """⭐ O caso do MARCELO."""
        out = self._rodar([
            {"sis": "SYSTUR", "a": "Em Análise", "pe": ""},
            {"sis": "ORACLE_EBS", "a": "Não Mapeado",
             "pe": "CVC OIE BRASIL - Relatório de Despesas"},
        ])
        self.assertIn("ORACLE_EBS", out)
        self.assertIn("CVC OIE BRASIL", out,
                      "sem isto, o acesso que motivou a linha some da tela")
        self.assertIn("tem hoje", out)

    def test_o_marcador_sem_sistema_continua_de_fora(self):
        """O registro que so' garante a pessoa existir na Consulta nao pode
        virar uma linha de sistema."""
        out = self._rodar([{"sis": "", "a": "Não Mapeado", "pe": ""}])
        self.assertNotIn("tem hoje", out)

    def test_sistema_sem_linha_nenhuma_continua_listado(self):
        """Nao-regressao do comportamento antigo do bloco."""
        out = self._rodar([{"sis": "SYSTUR", "a": "Aderente", "pe": "X"}])
        self.assertIn("SICA_RA", out)
        self.assertIn("sem perfil previsto", out)


class ODominioEhAFonteDoStatus(unittest.TestCase):
    """O SQL do painel nao importa o modulo de dominio, entao a lista de
    situacoes "sem acesso" esta' escrita la' de novo. Este teste existe para o
    dia em que alguem acrescentar um status ao dominio e esquecer do SQL — a
    tela passaria a listar conta revogada como se fosse acesso."""

    def test_a_lista_do_sql_e_a_do_dominio_nao_divergem(self):
        import re
        import visualizador.main as vm
        from dominio.objetos_valor import situacao_conta

        trecho = re.search(
            r"NOT IN\s*\(\s*('INATIVO'.*?)\)", vm._SQL_BI, re.S)
        self.assertIsNotNone(trecho, "o filtro de situacao sumiu do SQL")
        no_sql = set(re.findall(r"'([^']+)'", trecho.group(1)))
        self.assertEqual(no_sql, set(situacao_conta.SEM_ACESSO))


if __name__ == "__main__":
    unittest.main()
