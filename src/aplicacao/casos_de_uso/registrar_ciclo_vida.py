# -*- coding: utf-8 -*-
"""Registra o CICLO DE VIDA de cada acesso por (matricula, sistema):
Pendencia -> Resolvido (ticket Jira) -> Aderente (acesso OK), com timestamps
FIRST-WINS (idempotente: cada data so grava na 1a vez, nao sobrescreve).

Base para o tempo de tratamento (Historico) e tempo medio (Visao Geral).

Tudo ADITIVO e BLINDADO: usa a tabela isolada ciclo_vida_acesso e NUNCA derruba
o processamento — qualquer erro e' apenas logado.
"""
from datetime import datetime

from loguru import logger
from sqlalchemy import text

# subquery do login (CD_LOGIN) a partir do acesso da pessoa no sistema
_LOGIN = ("COALESCE((SELECT a.usuario FROM acessos_sistemas a "
          "WHERE a.matricula_vinculada = v.matricula AND a.sistema = v.sistema "
          "LIMIT 1), '')")


class RegistrarCicloVida:

    def __init__(self, conexao):
        self._conexao = conexao

    def executar(self, agora: str = None) -> int:
        try:
            return self._executar(agora)
        except Exception as e:  # blindagem: nunca derruba o processamento
            logger.warning(f"Ciclo de vida nao registrado (ignorado): {e}")
            return 0

    def _executar(self, agora: str = None) -> int:
        # agora injetavel (testes); por padrao o instante do processamento
        agora = agora or datetime.now().isoformat(sep=" ", timespec="seconds")
        with self._conexao.sessao() as sessao:
            # 1) PENDENCIA — 1a vez que a pessoa tem pendencia no sistema.
            #    ON CONFLICT colapsa as N linhas (ex.: Em Analise) numa so por
            #    (matricula, sistema), mantendo a 1a data (first-wins).
            sessao.execute(text(f"""
                INSERT INTO ciclo_vida_acesso
                    (matricula, sistema, perfil, nome, cargo, login, dt_pendencia, dt_atualizacao)
                SELECT v.matricula, v.sistema, v.perfil_esperado, v.nome, v.cargo_descricao,
                       {_LOGIN}, :agora, :agora
                FROM validacao_acessos v
                WHERE v.status IN ('SEM_ACESSO','DIVERGENTE','EM_ANALISE')
                  AND COALESCE(v.perfil_esperado,'') <> ''
                ON CONFLICT(matricula, sistema) DO UPDATE SET
                    dt_pendencia   = COALESCE(ciclo_vida_acesso.dt_pendencia, excluded.dt_pendencia),
                    nome = excluded.nome, cargo = excluded.cargo,
                    dt_atualizacao = excluded.dt_atualizacao
            """), {"agora": agora})

            # 2) ADERENTE — 1a vez conforme no sistema (status OK). Atualiza o
            #    perfil/login para o do acesso aderente.
            sessao.execute(text(f"""
                INSERT INTO ciclo_vida_acesso
                    (matricula, sistema, perfil, nome, cargo, login, dt_aderente, dt_atualizacao)
                SELECT v.matricula, v.sistema, v.perfil_esperado, v.nome, v.cargo_descricao,
                       {_LOGIN}, :agora, :agora
                FROM validacao_acessos v
                WHERE v.status = 'OK' AND COALESCE(v.perfil_esperado,'') <> ''
                ON CONFLICT(matricula, sistema) DO UPDATE SET
                    dt_aderente    = COALESCE(ciclo_vida_acesso.dt_aderente, excluded.dt_aderente),
                    perfil = excluded.perfil, login = excluded.login,
                    nome = excluded.nome, cargo = excluded.cargo,
                    dt_atualizacao = excluded.dt_atualizacao
            """), {"agora": agora})

            # 3) RESOLVIDO — do ticket Jira (tabela resolucoes, ja dobrada).
            #    First-wins na data e no ticket.
            tem_res = sessao.execute(text(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='resolucoes'"
            )).fetchone()
            if tem_res:
                sessao.execute(text("""
                    UPDATE ciclo_vida_acesso
                    SET dt_resolvido = COALESCE(dt_resolvido,
                            (SELECT r.resolvido_em FROM resolucoes r
                             WHERE r.registro_id = ciclo_vida_acesso.matricula)),
                        ticket = COALESCE(ticket,
                            (SELECT r.ticket FROM resolucoes r
                             WHERE r.registro_id = ciclo_vida_acesso.matricula)),
                        dt_atualizacao = :agora
                    WHERE matricula IN (SELECT registro_id FROM resolucoes)
                """), {"agora": agora})

            n = sessao.execute(text("SELECT COUNT(*) FROM ciclo_vida_acesso")).fetchone()[0]
            sessao.commit()
        logger.success(f"Ciclo de vida registrado: {n} (matricula, sistema) rastreado(s).")
        return n
