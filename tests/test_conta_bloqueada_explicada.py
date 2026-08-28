# -*- coding: utf-8 -*-
"""Conta BLOQUEADA nao pode virar um "sem acesso" mudo na tela.

Retorno da area (3o documento, 25/08/2026): "acesso existente vindo como sem
acesso". Medido: 81 casos (SIG 78, SICA_ESFERA 3) e TODOS com conta
BLOQUEADO/INATIVO — nenhuma conta ativa marcada errado. O motor esta certo:
pela regra de 22/07 conta revogada nao e' acesso, entao o resultado e'
SEM_ACESSO ("Incluir Acesso").

O defeito e' de TRANSPARENCIA, nao de calculo — e o precedente e' a decisao da
propria area em 10/08 sobre o caso irmao (`CONTA_INDEFINIDA`): "corrigir
explicando na tela, nao mudando a regra".

Sem a explicacao a grid mostra o LOGIN da pessoa preenchido (o subselect do
login nao filtra por situacao) e ao lado afirma que ela nao tem acesso —
mandando CRIAR um acesso que ja existe, quando a acao certa e' DESBLOQUEAR.

Caso real que originou: matricula 2752, SIG, login `rpdiogo`, perfil 100,
situacao BLOQUEADO.
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import (
    RhAtivo, PerfilEsperadoModel, AcessoSistema, ValidacaoAcessoModel)
from aplicacao.casos_de_uso.validar_acessos_sistema import ValidarAcessosSistema

SYS = "SYSTUR"


class MotorExplicaOSemAcesso(unittest.TestCase):
    """Passa pelo motor de verdade: o motivo nasce na validacao, nao na tela."""

    def _run(self, situacao_do_acesso):
        """situacao_do_acesso=None => a pessoa nao tem conta nenhuma."""
        tmp = tempfile.mkdtemp(prefix="cvc_bloq_")
        cx = ConexaoBancoDados(os.path.join(tmp, "d.db"))
        cx.inicializar()
        s = cx.sessao()
        s.add(RhAtivo(matricula="M1", nome="ROSE", cpf="11111111111",
                      cargo_codigo="CG", cargo_descricao="ANALISTA",
                      centro_custo_codigo="100", situacao="ATIVO"))
        s.add(PerfilEsperadoModel(cargo_codigo="100", cargo_descricao="ANALISTA",
                                  sistema=SYS, perfil="P1"))
        # colega com acesso vivo: mantem a adesao do cargo alta (regra B1),
        # senao a inclusao e' suprimida e nao sobra registro para conferir
        s.add(RhAtivo(matricula="M2", nome="BIA", cpf="22222222222",
                      cargo_codigo="CG", cargo_descricao="ANALISTA",
                      centro_custo_codigo="100", situacao="ATIVO"))
        s.add(AcessoSistema(sistema=SYS, usuario="u2", perfil="P1",
                            matricula_vinculada="M2", situacao="ATIVO"))
        if situacao_do_acesso is not None:
            s.add(AcessoSistema(sistema=SYS, usuario="rpdiogo", perfil="P1",
                                matricula_vinculada="M1",
                                situacao=situacao_do_acesso))
        s.commit(); s.close()
        ValidarAcessosSistema(cx).executar()
        s = cx.sessao()
        rows = [(r.status, r.motivo_status)
                for r in s.query(ValidacaoAcessoModel).filter_by(matricula="M1").all()]
        s.close()
        return rows

    def test_conta_bloqueada_diz_por_que(self):
        self.assertEqual(self._run("BLOQUEADO"),
                         [("SEM_ACESSO", "CONTA_BLOQUEADA")])

    def test_conta_inativa_tambem(self):
        self.assertEqual(self._run("INATIVO"),
                         [("SEM_ACESSO", "CONTA_BLOQUEADA")])

    def test_quem_NAO_TEM_conta_continua_sem_motivo(self):
        """O discriminador: aqui a acao e' criar mesmo. Se o rotulo fosse
        aplicado em bloco a todo SEM_ACESSO, este teste falharia — e a tela
        passaria a mandar desbloquear conta que nao existe."""
        self.assertEqual(self._run(None), [("SEM_ACESSO", None)])

    def test_conta_ativa_aderente_nao_ganha_motivo(self):
        self.assertEqual(self._run("ATIVO"), [("OK", None)])

    def test_status_indefinido_continua_conta_indefinida(self):
        """Protege o precedente de 10/08 — que nao tinha teste nenhum."""
        self.assertEqual(self._run("PENDENTE"),
                         [("EM_ANALISE", "CONTA_INDEFINIDA")])


class TelaTraduzOMotivo(unittest.TestCase):
    """Passa pelo SQL real do painel (`_SQL_BI`): o motor grava o codigo, a
    materializacao vira texto. Se o CASE nao souber do codigo, o motivo chega
    vazio na tela e o defeito continua de pe."""

    def _bi(self, motivo_status, com_conta):
        tmp = tempfile.mkdtemp(prefix="cvc_bi_")
        db = os.path.join(tmp, "iam.db")
        ConexaoBancoDados(db).inicializar()
        c = sqlite3.connect(db)
        try:
            c.execute(
                "INSERT INTO validacao_acessos (matricula, nome, sistema,"
                " perfil_esperado, perfil_atual, status, motivo_status,"
                " dt_processamento) VALUES (?,?,?,?,?,?,?,?)",
                ("2752", "ROSE APARECIDA DIOGO", "SIG", "100, 55001", "",
                 "SEM_ACESSO", motivo_status, "2026-08-26 09:00:00"))
            if com_conta:
                c.execute(
                    "INSERT INTO acessos_sistemas (sistema, usuario, perfil,"
                    " matricula_vinculada, situacao) VALUES (?,?,?,?,?)",
                    ("SIG", "rpdiogo", "100", "2752", "BLOQUEADO"))
            c.commit()
            import visualizador.main as vm
            c.executescript(vm._SQL_BI)
            return c.execute(
                "SELECT acao, motivo, login FROM bi_divergencias").fetchone()
        finally:
            c.close()

    def test_conta_bloqueada_vira_texto_e_mostra_o_login(self):
        acao, motivo, login = self._bi("CONTA_BLOQUEADA", com_conta=True)
        self.assertEqual(acao, "Incluir Acesso")
        self.assertEqual(login, "rpdiogo",
                         "o login existe — e' o que torna a tela contraditoria")
        self.assertTrue(motivo, "a linha nao pode chegar muda na tela")
        self.assertIn("BLOQUEADA", motivo.upper())
        self.assertIn("DESBLOQUEAR", motivo.upper(),
                      "tem de dizer qual e' a acao certa")

    def test_sem_acesso_de_verdade_continua_sem_motivo(self):
        acao, motivo, login = self._bi(None, com_conta=False)
        self.assertEqual((acao, motivo, login), ("Incluir Acesso", "", ""))



# --------------------------------------------------------------------------
# A tela: o "?" tem de aparecer ONDE os casos estao.
# --------------------------------------------------------------------------
import json
import shutil
import subprocess

RAIZ = Path(__file__).resolve().parent.parent
INDEX = RAIZ / "CVC_IAM_ANALYTICS" / "EXECUTAVEIS" / "REPORT" / "index.html"
NODE = shutil.which("node")


def _funcao(nome):
    html = INDEX.read_text(encoding="utf-8")
    i = html.index(f"function {nome}(")
    j, nivel = html.index("{", i), 0
    for k in range(j, len(html)):
        if html[k] == "{":
            nivel += 1
        elif html[k] == "}":
            nivel -= 1
            if nivel == 0:
                return html[i:k + 1]
    raise AssertionError(f"função {nome} não fecha")


@unittest.skipUnless(NODE, "Node não disponível nesta máquina")
class IconeDoMotivoNaConsulta(unittest.TestCase):
    """O "?" existia SO na grid de Pendencias (`tipoBadge`). Mas "Incluir
    Acesso" nao e' pendencia — por decisao da propria area e' informativo e
    aparece SO na Consulta. Ou seja: sem este ajuste o motivo da conta
    bloqueada nasceria invisivel, exatamente no unico lugar onde esses 81
    casos sao vistos."""

    def _render(self, divs):
        js = f"""
        const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;')
                                  .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
        const fmtDH = s => s;
        let _csAccSeq = 0;
        {_funcao('motIcone')}
        {_funcao('_csCorAcao')}
        {_funcao('_csListaPerfis')}
        {_funcao('_csDelta')}
        {_funcao('_csPerfilTxt')}
        {_funcao('_csAccBloco')}
        console.log(_csAccBloco('SIG', {json.dumps(divs)}, 'cs-acc', false));
        """
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                         encoding="utf-8") as f:
            f.write(js)
            caminho = f.name
        try:
            # o HTML gerado tem "▸"/"●": sem encoding explicito o Windows
            # tenta cp1252 na saida do Node e a leitura estoura
            r = subprocess.run([NODE, caminho], capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
            self.assertEqual(r.returncode, 0, r.stderr)
            return r.stdout
        finally:
            os.unlink(caminho)

    def _div(self, mot=""):
        return {"a": "Incluir Acesso", "t": "SEM_ACESSO", "tl": "Sem Acesso",
                "pe": "", "pp": "100", "mot": mot, "dt": "", "sis": "SIG"}

    def test_conta_bloqueada_mostra_o_aviso(self):
        html = self._render([self._div("A pessoa JA TEM conta ... DESBLOQUEAR")])
        self.assertIn("mot-info", html,
                      "o motivo nao chega na Consulta — o fix fica invisivel")
        self.assertIn("DESBLOQUEAR", html)

    def test_linha_sem_motivo_nao_ganha_icone(self):
        """A esmagadora maioria das linhas nao tem motivo: um "?" em todas
        viraria ruido e ninguem mais leria nenhum."""
        html = self._render([self._div("")])
        self.assertNotIn("mot-info", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
