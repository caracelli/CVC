# -*- coding: utf-8 -*-
"""Testes da identidade de diretorio (AD): leitor dos exports por OU, o nivel
LOGIN da cascata de matching e a precedencia CLT > AD no universo.

Contexto: os 3 exports do AD (Franq/Prest/Deslig) existem para dar dono aos
acessos ORFAOS — os que nao tem CPF nem email no extrato, so o login. A chave
de ouro e' o Login (== `usuario`/CD_LOGIN do extrato de acesso).
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from aplicacao.casos_de_uso.importar_diretorio_ad import _populacao
from infraestrutura.leitores_arquivos.leitor_diretorio_ad import _nome_do_dn
from dominio.servicos_dominio.servico_vinculacao_multi_chave import (
    METODO_CPF, METODO_EMAIL, METODO_LOGIN, METODO_NAO_VINCULADO,
    ORDEM_METODOS, SCORE_LOGIN, FuncionarioRef, ServicoVinculacaoMultiChave,
    normalizar_login,
)
from infraestrutura.leitores_arquivos.leitor_diretorio_ad import LeitorDiretorioAd

CABECALHO = "Nome;Email;Login;CPF;Escritorio;Cargo;Departamento;Empresa;Status;Manager;Criacao"


def _csv_ad(linhas):
    """Escreve um CSV no layout dos exports do AD. Devolve o caminho."""
    tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w",
                                      encoding="utf-8", newline="")
    tmp.write(CABECALHO + "\n")
    for l in linhas:
        tmp.write(";".join(l) + "\n")
    tmp.close()
    return Path(tmp.name)


class TestRoteamentoPopulacao(unittest.TestCase):
    """O tipo_vinculo sai do NOME do arquivo — se isso quebrar, franqueado vira
    prestador silenciosamente."""

    def test_franqueado(self):
        self.assertEqual(_populacao("OU_Franq_Bruna.csv"), "FRANQUEADO")

    def test_prestador(self):
        self.assertEqual(_populacao("OU_Prest_Bruna.csv"), "PRESTADOR")

    def test_desligados_alimenta_o_motor_de_desligados(self):
        # B2 respondido pela usuaria (29/07): SIM. O OU_Desligados NAO vira
        # identidade ativa — vai para rh_desligados (chave = login).
        self.assertEqual(_populacao("OU_Desligados_Bruna.csv"), "DESLIGADOS")
        self.assertNotIn(_populacao("OU_Desligados_Bruna.csv"),
                         ("FRANQUEADO", "PRESTADOR"))

    def test_arquivo_desconhecido_nao_importa(self):
        self.assertIsNone(_populacao("qualquer_outra_coisa.csv"))


class TestLeitorDiretorioAd(unittest.TestCase):
    def setUp(self):
        self.leitor = LeitorDiretorioAd()

    def test_matricula_namespaced_nao_colide_com_clt(self):
        arq = _csv_ad([["ANA SOUZA", "ana@x.com", "corpp001", "11122233344",
                        "SP", "AGENTE", "VENDAS", "ACME", "ATIVO", "CHEFE", ""]])
        ids = self.leitor.ler(arq, tipo_vinculo="FRANQUEADO")
        self.assertEqual(len(ids), 1)
        self.assertEqual(ids[0].matricula, "FRANQ-corpp001")
        self.assertEqual(ids[0].tipo_vinculo, "FRANQUEADO")
        self.assertEqual(ids[0].login, "corpp001")

    def test_prefixo_por_populacao(self):
        arq = _csv_ad([["BIA", "", "corpp002", "", "", "", "", "", "", "", ""]])
        self.assertEqual(self.leitor.ler(arq, "PRESTADOR")[0].matricula, "PREST-corpp002")

    def test_dedup_por_login_primeiro_vence(self):
        arq = _csv_ad([
            ["ANA SOUZA", "ana@x.com", "corpp001", "111", "", "", "", "", "", "", ""],
            ["ANA S. SOUZA", "ana2@x.com", "corpp001", "111", "", "", "", "", "", "", ""],
        ])
        ids = self.leitor.ler(arq, "FRANQUEADO")
        self.assertEqual(len(ids), 1)
        self.assertEqual(ids[0].nome, "ANA SOUZA")

    def test_descarta_sem_login_e_sem_cpf(self):
        arq = _csv_ad([
            ["SEM CHAVE", "so@email.com", "", "", "", "", "", "", "", "", ""],
            ["COM LOGIN", "", "corpp003", "", "", "", "", "", "", "", ""],
        ])
        ids = self.leitor.ler(arq, "PRESTADOR")
        self.assertEqual([i.matricula for i in ids], ["PREST-corpp003"])

    def test_sem_login_usa_cpf_na_matricula(self):
        arq = _csv_ad([["CARLA", "", "", "99988877766", "", "", "", "", "", "", ""]])
        ids = self.leitor.ler(arq, "FRANQUEADO")
        self.assertEqual(ids[0].matricula, "FRANQ-99988877766")
        self.assertIsNone(ids[0].login)

    def test_sem_cpf_nao_quebra_a_entidade(self):
        # Funcionario deixou de exigir CPF exatamente por causa do AD
        arq = _csv_ad([["DANI", "d@x.com", "corpp004", "", "", "", "", "", "", "", ""]])
        self.assertEqual(self.leitor.ler(arq, "PRESTADOR")[0].cpf, "")

    def test_manager_dn_vira_gestor_nome_puro(self):
        # o "Manager" do AD vem como Distinguished Name; deve virar o nome do CN
        # em MAIUSCULO (homogeneo com o gestor do RH). Este é o furo que fechamos.
        # colunas: Nome;Email;Login;CPF;Escritorio;Cargo;Departamento;Empresa;
        #          Status;Manager;Criacao  -> Manager é o índice 9
        arq = _csv_ad([["ANA", "a@x.com", "corpp001", "", "", "", "", "", "",
                        "CN=Erika Paulin,OU=Franqueado,DC=intra,DC=cvc", ""]])
        self.assertEqual(self.leitor.ler(arq, "FRANQUEADO")[0].gestor, "ERIKA PAULIN")

    def test_sem_manager_gestor_none(self):
        arq = _csv_ad([["BIA", "", "corpp002", "", "", "", "", "", "", "", ""]])
        self.assertIsNone(self.leitor.ler(arq, "PRESTADOR")[0].gestor)


class TestNomeDoDn(unittest.TestCase):
    """Extração do nome (CN) do Distinguished Name do AD."""

    def test_extrai_cn(self):
        self.assertEqual(
            _nome_do_dn("CN=Fabio Rico,OU=Funcionario,DC=intra,DC=cvc"), "FABIO RICO")

    def test_cn_case_insensitive(self):
        self.assertEqual(_nome_do_dn("cn=Joao Silva,OU=x"), "JOAO SILVA")

    def test_nome_puro_passa_direto(self):
        # se já vier nome puro (sem CN=), normaliza p/ maiúsculo
        self.assertEqual(_nome_do_dn("Marcia Souza"), "MARCIA SOUZA")

    def test_vazio(self):
        self.assertEqual(_nome_do_dn(""), "")
        self.assertEqual(_nome_do_dn(None), "")


class TestNivelLoginNaCascata(unittest.TestCase):
    """O nivel LOGIN entra DEPOIS de CPF e email — de proposito. Medicao sobre a
    base real (22/07): subir o LOGIN ao topo resolveria 0 orfao a mais e tiraria
    166 acessos do terceiro do RH (TERC-<cpf>, com cargo/empresa) para a
    identidade AD, mais pobre. Estes testes travam essa ordem."""

    def setUp(self):
        self.clt = FuncionarioRef(matricula="10001", cpf="11122233344",
                                  email="ana@cvc.com.br", nome="ANA SOUZA")
        self.ad = FuncionarioRef(matricula="PREST-CORPP001", cpf="11122233344",
                                 email="ana@acme.com", nome="ANA SOUZA",
                                 login="CORPP001")
        # precedencia do caso de uso: CLT primeiro, AD depois
        self.svc = ServicoVinculacaoMultiChave([self.clt, self.ad])

    def test_login_vincula_orfao_sem_cpf_nem_email(self):
        r = self.svc.vincular(login="corpp001")
        self.assertEqual(r.metodo, METODO_LOGIN)
        self.assertEqual(r.matricula, "PREST-CORPP001")
        self.assertEqual(r.score, SCORE_LOGIN)

    def test_cpf_prevalece_sobre_login(self):
        # mesmo com login do AD batendo, o CPF liga ao vinculo do RH
        r = self.svc.vincular(cpf="11122233344", login="corpp001")
        self.assertEqual(r.metodo, METODO_CPF)
        self.assertEqual(r.matricula, "10001")

    def test_email_prevalece_sobre_login(self):
        r = self.svc.vincular(email="ana@cvc.com.br", login="corpp001")
        self.assertEqual(r.metodo, METODO_EMAIL)
        self.assertEqual(r.matricula, "10001")

    def test_login_nao_afeta_universo_sem_ad(self):
        # RH puro nao tem login: o nivel e' inerte, CLT segue inalterado
        svc = ServicoVinculacaoMultiChave([self.clt])
        r = svc.vincular(login="corpp001")
        self.assertEqual(r.metodo, METODO_NAO_VINCULADO)
        self.assertIsNone(r.matricula)

    def test_login_normaliza_caixa_e_espaco(self):
        self.assertEqual(normalizar_login("  CorpP 001 "), "CORPP001")
        self.assertEqual(self.svc.vincular(login=" corpp 001 ").matricula,
                         "PREST-CORPP001")

    def test_login_ambiguo_registra_candidatos(self):
        outro = FuncionarioRef(matricula="FRANQ-CORPP001", login="CORPP001")
        svc = ServicoVinculacaoMultiChave([self.ad, outro])
        r = svc.vincular(login="corpp001")
        self.assertEqual(r.metodo, METODO_LOGIN)
        self.assertEqual(sorted(r.candidatos), ["FRANQ-CORPP001", "PREST-CORPP001"])


class TestOrdemMetodosDoLog(unittest.TestCase):
    """O log por metodo itera ORDEM_METODOS. Quando o LOGIN foi adicionado a
    cascata, o loop do log ficou para tras e os matches por login sumiram do
    relatorio — esta e' a blindagem."""

    def test_ordem_cobre_todos_os_metodos_validos(self):
        from dominio.servicos_dominio.servico_vinculacao_multi_chave import METODOS_VALIDOS
        self.assertEqual(set(ORDEM_METODOS), set(METODOS_VALIDOS))
        self.assertEqual(len(ORDEM_METODOS), len(METODOS_VALIDOS))

    def test_login_aparece_entre_email_e_cpf_parcial(self):
        i = ORDEM_METODOS.index
        self.assertLess(i(METODO_CPF), i(METODO_EMAIL))
        self.assertLess(i(METODO_EMAIL), i(METODO_LOGIN))
        self.assertLess(i(METODO_LOGIN), i("CPF_PARCIAL_NOME"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
