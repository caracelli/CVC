# -*- coding: utf-8 -*-
"""Dados SIMULADOS para teste visual da aba Historico do Visualizador.

A aba Historico e' a trilha de pendencias: cada resolucao gera o par
"Pendencia identificada" / "Pendencia resolvida". Este script popula a tabela
`resolucoes` com matriculas ficticias na faixa '99xxx'.

  python scripts/simular_historico.py          # insere os dados simulados
  python scripts/simular_historico.py limpar   # remove os dados simulados

E re-executavel: antes de inserir, limpa as proprias linhas '99xxx'. Nao
toca em nenhum dado real. Escreve nos dois bancos (rede + cache do exe).
"""
import json
import os
import sqlite3
import sys
from datetime import datetime

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DBS = [
    os.path.join(_RAIZ, "CVC_IAM_ANALYTICS", "DADOS", "BANCO", "iam_analytics.db"),
    os.path.join(_RAIZ, "CVC_IAM_ANALYTICS", "EXECUTAVEIS", "iam_analytics.db"),
]

_SQL_RES = """CREATE TABLE IF NOT EXISTS resolucoes (
  registro_id TEXT PRIMARY KEY, ticket TEXT NOT NULL, ticket_url TEXT,
  descricao TEXT, pendencias TEXT, cargo TEXT, centro_custo TEXT, nome TEXT,
  resolvido_por TEXT, resolvido_em TEXT, dobrado_em TEXT)"""

AGORA = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _pd(tipo, pe, pp, sis="SYSTUR", origem="Matriz SYSTUR", opcoes=None):
    """Monta o dict de uma pendencia para o snapshot da resolucao."""
    return {"tipo": tipo, "acao": tipo, "sistema": sis, "origem": origem,
            "pe": pe, "pp": pp, "opcoes": opcoes or []}


# (matricula, nome, cargo, centro_custo, data_acao, ticket, descricao, [pendencias])
RESOLUCOES = [
    ("99001", "ANA PAULA SOUZA", "ANALISTA FISCAL PL", "01.02.06.01",
     "2026-05-12T09:14:02", "IAM-2010", "Perfil ajustado conforme a matriz.",
     [_pd("Divergente", "FISCAL_BASICO", "FISCAL_TRIBUTARIO")]),
    ("99002", "BRUNO CARVALHO LIMA", "COORDENADOR SERVICE DESK", "01.13.03.03",
     "2026-05-14T09:32:10", "IAM-2041", "Acesso de supervisao concedido.",
     [_pd("Sem Acesso", "", "TI_SISTEMAS_SUPERVISOR")]),
    ("99003", "CARLA MENDES DIAS", "ADVOGADO PL", "01.02.03.01",
     "2026-05-16T14:05:48", "IAM-2088", "Perfil definido com a area juridica.",
     [_pd("Em Análise", "JURIDICO_CONTENCIOSO", "",
          opcoes=["JURIDICO_CONTENCIOSO", "JURIDICO_CONTENCIOSO_COM_REEMBOLSO"])]),
    ("99004", "DANIEL ROCHA FERREIRA", "ASSISTENTE SUPORTE VENDAS", "05.02.07.08",
     "2026-05-09T11:48:20", "IAM-1998", "Perfil corrigido.",
     [_pd("Divergente", "VENDAS_CONSULTA", "VENDAS_OPERACIONAL")]),
    ("99005", "EDUARDA SILVA NOGUEIRA", "ANALISTA CONTABIL JR", "01.02.02.02",
     "2026-05-19T11:20:00", "IAM-2150", "Acesso incluido.",
     [_pd("Sem Acesso", "", "CONTABIL_OPERACIONAL")]),
    ("99006", "FELIPE ARAUJO COSTA", "GERENTE DE VENDAS", "05.01.01.04",
     "2026-05-18T15:27:39", "IAM-2133", "Dois acessos regularizados.",
     [_pd("Divergente", "VENDAS_OPERACIONAL", "VENDAS_GERENCIA"),
      _pd("Sem Acesso", "", "RELATORIOS_GERENCIAIS")]),
    ("99007", "GABRIELA PINTO MARTINS", "COORDENADOR CUSTOS", "01.03.05.01",
     "2026-05-20T16:48:33", "IAM-2199", "Pendencias de custos resolvidas.",
     [_pd("Divergente", "CUSTOS_BASICO", "CUSTOS_COORDENACAO"),
      _pd("Em Análise", "CUSTOS_BASICO", "",
          opcoes=["CUSTOS_COORDENACAO", "CUSTOS_RELATORIOS", "CUSTOS_AUDITORIA"])]),
    ("99008", "HENRIQUE GOMES BARROS", "ANALISTA DE TI SR", "01.13.02.01",
     "2026-05-08T08:55:11", "IAM-1971", "Perfil de TI ajustado.",
     [_pd("Divergente", "TI_BASICO", "TI_SISTEMAS_AVANCADO")]),
    ("99009", "ISABELA FONSECA RAMOS", "ASSISTENTE ADMINISTRATIVO", "01.05.04.02",
     "2026-05-21T10:02:44", "IAM-2221", "Acesso administrativo incluido.",
     [_pd("Sem Acesso", "", "ADMIN_OPERACIONAL")]),
    ("99010", "JOAO VITOR ALMEIDA", "SUPERVISOR DE ATENDIMENTO", "05.03.02.07",
     "2026-05-21T08:15:27", "IAM-2233", "Perfil de supervisao alterado.",
     [_pd("Divergente", "ATENDIMENTO_N1", "ATENDIMENTO_SUPERVISAO")]),
    ("99011", "KARINA LOPES TEIXEIRA", "ANALISTA DE RH PL", "01.04.01.03",
     "2026-05-13T13:36:09", "IAM-2025", "Perfil de RH em analise resolvido.",
     [_pd("Em Análise", "RH_CONSULTA", "",
          opcoes=["RH_OPERACIONAL", "RH_FOLHA"])]),
    ("99012", "LUCAS MOREIRA SANTOS", "COORDENADOR FISCAL", "01.02.06.02",
     "2026-05-15T13:40:05", "IAM-2102", "Tres pendencias resolvidas.",
     [_pd("Sem Acesso", "", "FISCAL_OPERACIONAL"),
      _pd("Divergente", "FISCAL_BASICO", "FISCAL_COORDENACAO"),
      _pd("Em Análise", "FISCAL_BASICO", "",
          opcoes=["FISCAL_COORDENACAO", "FISCAL_TRIBUTARIO"])]),
    ("99013", "MARIANA DUARTE CAMPOS", "ANALISTA COMERCIAL", "05.01.03.05",
     "2026-05-10T17:09:51", "IAM-2003", "Perfil comercial corrigido.",
     [_pd("Divergente", "COMERCIAL_CONSULTA", "COMERCIAL_OPERACIONAL")]),
    ("99014", "NELSON RIBEIRO AZEVEDO", "DIRETOR DE OPERACOES", "01.01.02.01",
     "2026-05-22T10:03:51", "IAM-2270", "Acesso de diretoria concedido.",
     [_pd("Sem Acesso", "", "DIRETORIA_FULL")]),
]


def _conectar(p):
    c = sqlite3.connect(p, timeout=15)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=8000")
    return c


def limpar(c):
    try:
        rh = c.execute("DELETE FROM historico_rh WHERE matricula LIKE '99%'").rowcount
    except sqlite3.OperationalError:
        rh = 0
    try:
        rs = c.execute("DELETE FROM resolucoes WHERE registro_id LIKE '99%'").rowcount
    except sqlite3.OperationalError:
        rs = 0
    return rh, rs


def inserir(c):
    c.executescript(_SQL_RES)
    for mat, nome, cargo, cc, data_acao, ticket, descricao, pendencias in RESOLUCOES:
        c.execute(
            "INSERT OR REPLACE INTO resolucoes (registro_id,ticket,ticket_url,"
            "descricao,pendencias,cargo,centro_custo,nome,resolvido_por,"
            "resolvido_em,dobrado_em) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [mat, ticket, "https://jira.cvc.com.br/browse/" + ticket,
             descricao, json.dumps(pendencias, ensure_ascii=False),
             cargo, cc, nome, "simulacao", data_acao, AGORA])
    return len(RESOLUCOES)


def main():
    so_limpar = len(sys.argv) > 1 and sys.argv[1].lower() == "limpar"
    for p in DBS:
        if not os.path.exists(p):
            print(f"  (pulado, nao existe) {p}")
            continue
        c = _conectar(p)
        try:
            rh, rs = limpar(c)
            if so_limpar:
                c.commit()
                print(f"  LIMPO  {p}  (-{rh} historico_rh, -{rs} resolucoes)")
                continue
            n = inserir(c)
            c.commit()
            print(f"  OK     {p}  (+{n} resolucoes)")
        finally:
            c.close()
    print("Limpeza concluida." if so_limpar else "Concluido.")


if __name__ == "__main__":
    main()
