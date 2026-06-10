# -*- coding: utf-8 -*-
"""Projeta os ADERENTES (ciclo_vida_acesso com dt_aderente) na trilha de
auditoria `historico`, como entidade ACESSO_SISTEMA / tipo_mudanca ADERENTE.

Regra decidida com o cliente: grava SO para quem ainda NAO tem registro no
historico E nao passou por resolucao previa — o "conforme direto". Idempotente:
uma vez gravada a linha, a matricula passa a ter registro e nao e' reinserida
nas proximas rodadas. Tudo ADITIVO e BLINDADO (qualquer erro so e' logado).
"""
import json
from datetime import datetime

from loguru import logger
from sqlalchemy import text


class RegistrarAderenteHistorico:

    def __init__(self, conexao):
        self._conexao = conexao

    def executar(self, agora: str = None) -> int:
        try:
            return self._executar(agora)
        except Exception as e:  # blindagem: nunca derruba o processamento
            logger.warning(f"Aderentes no historico nao registrados (ignorado): {e}")
            return 0

    def _executar(self, agora: str = None) -> int:
        agora = agora or datetime.now().isoformat(sep=" ", timespec="seconds")
        with self._conexao.sessao() as sessao:
            if not self._tabela(sessao, "ciclo_vida_acesso"):
                return 0
            tem_res = self._tabela(sessao, "resolucoes")
            # "conforme direto": dt_aderente preenchido, sem registro previo no
            # historico (idempotencia + exclui quem ja tem movimentacao) e sem
            # resolucao previa (esses ja aparecem na trilha via resolucao).
            res_clause = (
                " AND cv.matricula NOT IN (SELECT registro_id FROM resolucoes)"
                if tem_res else ""
            )
            candidatos = sessao.execute(text(f"""
                SELECT cv.matricula, cv.sistema, cv.perfil, cv.nome, cv.login,
                       cv.cargo, cv.dt_aderente
                FROM ciclo_vida_acesso cv
                WHERE cv.dt_aderente IS NOT NULL
                  AND cv.matricula NOT IN (SELECT chave_entidade FROM historico)
                  {res_clause}
                ORDER BY cv.dt_aderente
            """)).fetchall()

            n = 0
            vistos = set()  # uma linha por matricula (trilha por funcionario)
            for r in candidatos:
                if r.matricula in vistos:
                    continue
                vistos.add(r.matricula)
                dados = {
                    "sistema": r.sistema or "", "perfil": r.perfil or "",
                    "nome": r.nome or "", "login": r.login or "",
                    "cargo": r.cargo or "", "dt_aderente": r.dt_aderente or "",
                }
                data_snap = (r.dt_aderente or agora)[:10]
                sessao.execute(text("""
                    INSERT INTO historico
                        (data_snapshot, entidade, chave_entidade, tipo_mudanca,
                         dados_novo, dt_registro, matricula)
                    VALUES
                        (:data_snap, 'ACESSO_SISTEMA', :mat, 'ADERENTE',
                         :dados, :agora, :mat)
                """), {
                    "data_snap": data_snap, "mat": r.matricula,
                    "dados": json.dumps(dados, ensure_ascii=False, sort_keys=True),
                    "agora": agora,
                })
                n += 1
            sessao.commit()
        logger.success(f"Aderentes projetados no historico: {n} novo(s).")
        return n

    @staticmethod
    def _tabela(sessao, nome: str) -> bool:
        return sessao.execute(text(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=:n"
        ), {"n": nome}).fetchone() is not None
