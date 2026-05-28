# -*- coding: utf-8 -*-
"""Testes de integracao: pipeline end-to-end + compat JSONL v0/v1.

- Pipeline: RH -> acessos -> vincular multi-chave -> validar -> conferir contagens
- JSONL: leitura tolerante a v0 (legado, sem schema_version) e v1 (atual)
- Schema: round-trip (gravar + ler) de PerfilAcesso com matching multi-chave
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dominio.entidades.funcionario_ativo import FuncionarioAtivo
from dominio.entidades.funcionario_desligado import FuncionarioDesligado
from dominio.entidades.perfil_acesso import PerfilAcesso
from dominio.objetos_valor.cargo import Cargo
from dominio.objetos_valor.sistema import Sistema
from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.repositorios.repositorio_acesso_sqlite import RepositorioAcessoSqlite
from infraestrutura.repositorios.repositorio_funcionario_sqlite import RepositorioFuncionarioSqlite
from infraestrutura.interacoes.repositorio_interacoes import gravar, ler_todas, SCHEMA_VERSION
from aplicacao.casos_de_uso.vincular_acessos_rh import VincularAcessosRh


def _ativo(matricula, cpf, nome, email=None):
    return FuncionarioAtivo(
        matricula=matricula, nome=nome, cpf=cpf,
        cargo=Cargo(codigo="CG1", descricao="ANALISTA",
                    departamento="TI", centro_custo="100"),
        email=email, data_admissao=date(2020, 1, 1), situacao="ATIVO",
    )


def _deslig(matricula, cpf, nome, email=None):
    return FuncionarioDesligado(
        matricula=matricula, nome=nome, cpf=cpf,
        cargo=Cargo(codigo="CG1", descricao="ANALISTA",
                    departamento="TI", centro_custo="100"),
        email=email, data_admissao=date(2020, 1, 1),
        data_desligamento=date(2024, 6, 1),
    )


def _perfil(usuario, perfil, sistema=Sistema.SYSTUR, **kw):
    return PerfilAcesso(
        usuario=usuario, nome_usuario=kw.get("nome", f"USER {usuario}"),
        sistema=sistema, perfil=perfil, situacao="ATIVO",
        cpf=kw.get("cpf"), email=kw.get("email"),
    )


class TestPipelineCompleto(unittest.TestCase):
    """Simula o fluxo real: importar RH -> importar acessos -> vincular ->
    verificar que tudo bate."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.cx = ConexaoBancoDados(self.tmp.name)
        self.cx.inicializar()

    def tearDown(self):
        try:
            self.cx.engine.dispose()
            os.unlink(self.tmp.name)
        except Exception:
            pass

    def test_pipeline_e2e_multi_perfil_e_multi_chave(self):
        repo_func = RepositorioFuncionarioSqlite(self.cx)
        repo_acesso = RepositorioAcessoSqlite(self.cx)

        # 1) Importa 3 ativos + 1 desligado
        ativos = [
            _ativo("MAT1", "11111111111", "JOAO SILVA", "joao@cvc.com"),
            _ativo("MAT2", "22222222222", "MARIA SOUZA", "maria@cvc.com"),
            _ativo("MAT3", "33333333333", "PEDRO LIMA", "pedro@cvc.com"),
        ]
        repo_func.salvar_ativos(ativos, "rh.csv")
        repo_func.salvar_desligados(
            [_deslig("MAT9", "99999999999", "BOB DESLIGADO", "bob@cvc.com")],
            "rh_deslig.csv",
        )

        # 2) Importa acessos (multi-perfil + 1 com nome sem CPF + 1 desligado ainda ativo)
        acessos = [
            # JOAO: 3 perfis no SYSTUR (multi-perfil)
            _perfil("joao", "PERFIL_A", cpf="11111111111", email="joao@cvc.com", nome="JOAO SILVA"),
            _perfil("joao", "PERFIL_B", cpf="11111111111", email="joao@cvc.com", nome="JOAO SILVA"),
            _perfil("joao", "PERFIL_C", cpf="11111111111", email="joao@cvc.com", nome="JOAO SILVA"),
            # MARIA: vincula por email (CPF "errado")
            _perfil("maria", "PERFIL_X", cpf="00000000000", email="maria@cvc.com", nome="MARIA SOUZA"),
            # PEDRO: vincula por nome (sem CPF, sem email)
            _perfil("pedro", "PERFIL_Y", cpf=None, email=None, nome="PEDRO LIMA"),
            # BOB DESLIGADO: acesso ativo de quem foi desligado
            _perfil("bob", "PERFIL_Z", cpf="99999999999", email="bob@cvc.com", nome="BOB DESLIGADO"),
            # Sem vinculo possivel
            _perfil("orfa", "PERFIL_W", cpf="12121212121", email=None, nome="NINGUEM"),
        ]
        repo_acesso.substituir_sistema(Sistema.SYSTUR, acessos, "acessos.csv")

        # Confirma multi-perfil
        salvos = repo_acesso.obter_por_sistema(Sistema.SYSTUR)
        self.assertEqual(len(salvos), 7, "todas as 7 linhas devem persistir (multi-perfil)")
        joao_count = sum(1 for p in salvos if p.usuario == "joao")
        self.assertEqual(joao_count, 3, "JOAO tem 3 perfis distintos")

        # 3) Vinculacao com cascata
        contagem = VincularAcessosRh(self.cx).executar()
        self.assertGreaterEqual(contagem.get("CPF", 0), 4,
                                "JOAO (3 linhas) + BOB devem vincular por CPF")
        self.assertGreaterEqual(contagem.get("EMAIL", 0), 1,
                                "MARIA deve vincular por email")
        self.assertGreaterEqual(contagem.get("NOME", 0), 1,
                                "PEDRO deve vincular por nome")
        self.assertGreaterEqual(contagem.get("NAO_VINCULADO", 0), 1,
                                "ORFA nao deveria vincular a ninguem")

        # 4) Conferencia final
        salvos = {(p.usuario, p.perfil): p for p in repo_acesso.obter_por_sistema(Sistema.SYSTUR)}
        # JOAO: vinculado a MAT1 via CPF
        for perfil in ("PERFIL_A", "PERFIL_B", "PERFIL_C"):
            self.assertEqual(salvos[("joao", perfil)].matricula_vinculada, "MAT1")
            self.assertEqual(salvos[("joao", perfil)].metodo_vinculacao, "CPF")
        # MARIA: vinculada a MAT2 via EMAIL
        self.assertEqual(salvos[("maria", "PERFIL_X")].matricula_vinculada, "MAT2")
        self.assertEqual(salvos[("maria", "PERFIL_X")].metodo_vinculacao, "EMAIL")
        # PEDRO: vinculado a MAT3 via NOME
        self.assertEqual(salvos[("pedro", "PERFIL_Y")].matricula_vinculada, "MAT3")
        self.assertEqual(salvos[("pedro", "PERFIL_Y")].metodo_vinculacao, "NOME")
        # BOB: vinculado a MAT9 (desligado) — isso e' o sinal de "acesso de desligado"
        self.assertEqual(salvos[("bob", "PERFIL_Z")].matricula_vinculada, "MAT9")
        # ORFA: sem vinculo
        self.assertIsNone(salvos[("orfa", "PERFIL_W")].matricula_vinculada)
        self.assertEqual(salvos[("orfa", "PERFIL_W")].metodo_vinculacao, "NAO_VINCULADO")


class TestInteracoesV0CompatV1(unittest.TestCase):
    """JSONL gravados no formato legado (v0) devem continuar sendo lidos
    junto com os novos (v1)."""

    def setUp(self):
        self.pasta = tempfile.mkdtemp(prefix="interacoes_test_")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.pasta, ignore_errors=True)

    def test_grava_v1_aplica_envelope_automatico(self):
        gravar(self.pasta, {
            "tipo_interacao": "QUARENTENA",
            "registro_id": "12345",
            "acao": "ENVIAR",
            "usuario": "joao",
        }, "joao")
        lidas = ler_todas(self.pasta)
        self.assertEqual(len(lidas), 1)
        # Envelope v1 aplicado automaticamente
        self.assertEqual(lidas[0]["schema_version"], SCHEMA_VERSION)
        self.assertIn("extras", lidas[0])
        self.assertEqual(lidas[0]["extras"], {})
        self.assertIn("data_acao", lidas[0])

    def test_le_v0_legado_sem_schema_version(self):
        # Simula registro gravado antes de 28/05/2026 (sem schema_version)
        legado = {
            "tipo_interacao": "RESOLUCAO",
            "registro_id": "99999",
            "acao": "RESOLVER",
            "usuario": "maria",
            "data_acao": "2026-04-01T10:00:00",
            "ticket": "IAM-1000",
        }
        with open(os.path.join(self.pasta, "interacao_maria.jsonl"), "w",
                  encoding="utf-8") as f:
            f.write(json.dumps(legado, ensure_ascii=False) + "\n")
        lidas = ler_todas(self.pasta)
        self.assertEqual(len(lidas), 1)
        # Reader marca como v0 e adiciona extras (defensivo)
        self.assertEqual(lidas[0]["schema_version"], 0)  # legado implicito
        self.assertEqual(lidas[0]["extras"], {})
        self.assertEqual(lidas[0]["ticket"], "IAM-1000")

    def test_le_v0_e_v1_juntos(self):
        # 1 legado + 1 novo no mesmo arquivo
        with open(os.path.join(self.pasta, "interacao_x.jsonl"), "w",
                  encoding="utf-8") as f:
            f.write(json.dumps({"tipo_interacao": "QUARENTENA", "registro_id": "A",
                                "acao": "ENVIAR", "usuario": "x",
                                "data_acao": "2026-04-01T10:00:00"}) + "\n")
        gravar(self.pasta, {
            "tipo_interacao": "QUARENTENA",
            "registro_id": "B", "acao": "ENVIAR", "usuario": "x",
        }, "x")
        lidas = ler_todas(self.pasta)
        self.assertEqual(len(lidas), 2)
        ver = sorted(l["schema_version"] for l in lidas)
        self.assertEqual(ver, [0, SCHEMA_VERSION])

    def test_linha_corrompida_e_ignorada(self):
        with open(os.path.join(self.pasta, "interacao_ruim.jsonl"), "w",
                  encoding="utf-8") as f:
            f.write('{"tipo_interacao": "QUARENTENA", "registro_id": "OK", "acao": "ENVIAR", "usuario": "x"}\n')
            f.write('{linha incompleta sem fechar\n')  # JSON quebrado
            f.write('{"tipo_interacao": "QUARENTENA", "registro_id": "OK2", "acao": "ENVIAR", "usuario": "y"}\n')
        lidas = ler_todas(self.pasta)
        self.assertEqual(len(lidas), 2, "linha corrompida e' ignorada, demais sobrevivem")


if __name__ == "__main__":
    unittest.main()
