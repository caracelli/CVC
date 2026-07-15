# -*- coding: utf-8 -*-
"""CDC do ciclo de acesso como LOG DE EVENTOS por (matricula, sistema).

Gera a tabela append-only `ciclo_eventos_acesso`: cada transicao vira UMA
linha datada, agrupada em ciclos. Diferente do `ciclo_vida_acesso` (que guarda
um unico ciclo, first-wins), este log suporta REABERTURA — depois de ADERENTE,
uma nova pendencia abre o ciclo seguinte:

    ciclo 1: PENDENCIA -> RESOLVIDO -> ADERENTE
    ciclo 2: PENDENCIA (reabertura) -> ...

Como funciona (roda a cada processamento, depois da validacao e da dobra):
  1. Estado ATUAL de cada (matricula, sistema) vem de `validacao_acessos`
     (PENDENTE se ha status pendente; senao ADERENTE se ha OK).
  2. O ULTIMO evento de cada (matricula, sistema) vem do proprio log.
  3. Reconcilia: anexa so as transicoes que faltam. O UNIQUE
     (matricula, sistema, ciclo, tipo_evento) garante idempotencia.

Tudo ADITIVO e BLINDADO: nunca derruba o processamento (erro so e' logado) e
nao toca em nenhuma tabela existente.
"""
from datetime import datetime

from loguru import logger
from sqlalchemy import text

# status de validacao que contam como "pendencia" (precisa de acao)
_PENDENTES = ("SEM_ACESSO", "DIVERGENTE", "EM_ANALISE")

# ordem cronologica dos marcos dentro de um ciclo
_ORDEM = {"PENDENCIA": 0, "RESOLVIDO": 1, "ADERENTE": 2}


class RegistrarEventosAcesso:

    def __init__(self, conexao):
        self._conexao = conexao

    def executar(self, agora: str = None) -> int:
        try:
            return self._executar(agora)
        except Exception as e:  # blindagem: nunca derruba o processamento
            logger.warning(f"Eventos de acesso nao registrados (ignorado): {e}")
            return 0

    def _executar(self, agora: str = None) -> int:
        agora = agora or datetime.now().isoformat(sep=" ", timespec="seconds")
        with self._conexao.sessao() as sessao:
            if not self._tabela(sessao, "ciclo_eventos_acesso"):
                return 0

            estados = self._estados_atuais(sessao)   # (mat,sis) -> 'PENDENTE'|'ADERENTE'
            ricos = self._dados_ricos(sessao)        # (mat,sis) -> row ciclo_vida
            ultimos = self._ultimos_eventos(sessao)  # (mat,sis) -> (ciclo, tipo, data)

            n = 0
            for chave, estado in estados.items():
                n += self._reconciliar(
                    sessao, chave, estado,
                    ricos.get(chave), ultimos.get(chave), agora,
                )
            sessao.commit()

        if n:
            logger.success(f"Eventos de acesso: {n} novo(s) evento(s) registrado(s).")
        return n

    # ------------------------------------------------------------------
    # leitura de estado
    # ------------------------------------------------------------------
    def _estados_atuais(self, sessao) -> dict:
        """Estado atual por (matricula, sistema) a partir de validacao_acessos.
        PENDENTE se ha qualquer status pendente; senao ADERENTE se ha OK."""
        placeholders = ",".join(f"'{s}'" for s in _PENDENTES)
        rows = sessao.execute(text(f"""
            SELECT matricula, sistema,
                   SUM(CASE WHEN status IN ({placeholders}) THEN 1 ELSE 0 END) AS pend,
                   SUM(CASE WHEN status = 'OK' THEN 1 ELSE 0 END) AS ok
            FROM validacao_acessos
            WHERE COALESCE(perfil_esperado,'') <> ''
              AND matricula IS NOT NULL AND matricula <> ''
            GROUP BY matricula, sistema
        """)).fetchall()
        estados = {}
        for r in rows:
            if r.pend and r.pend > 0:
                estados[(r.matricula, r.sistema)] = "PENDENTE"
            elif r.ok and r.ok > 0:
                estados[(r.matricula, r.sistema)] = "ADERENTE"
        return estados

    def _dados_ricos(self, sessao) -> dict:
        """perfil/nome/login/cargo + resolucao (dt_resolvido, ticket) do ciclo_vida."""
        if not self._tabela(sessao, "ciclo_vida_acesso"):
            return {}
        rows = sessao.execute(text(
            "SELECT matricula, sistema, perfil, nome, login, cargo, "
            "dt_resolvido, ticket FROM ciclo_vida_acesso")).fetchall()
        return {(r.matricula, r.sistema): r for r in rows}

    def _ultimos_eventos(self, sessao) -> dict:
        """Ultimo evento (ciclo, tipo, data) por (matricula, sistema)."""
        rows = sessao.execute(text(
            "SELECT matricula, sistema, ciclo, tipo_evento, data_evento "
            "FROM ciclo_eventos_acesso")).fetchall()
        ult = {}
        for r in rows:
            chave = (r.matricula, r.sistema)
            rank = (r.ciclo, _ORDEM.get(r.tipo_evento, 0))
            atual = ult.get(chave)
            if atual is None or rank > atual[0]:
                ult[chave] = (rank, r.ciclo, r.tipo_evento, r.data_evento)
        return {k: (v[1], v[2], v[3]) for k, v in ult.items()}

    # ------------------------------------------------------------------
    # reconciliacao (maquina de estados do ciclo)
    # ------------------------------------------------------------------
    def _reconciliar(self, sessao, chave, estado, info, ult, agora) -> int:
        mat, sis = chave
        n = 0
        if ult is None:
            ciclo, tipo, pend_data = 0, None, None
        else:
            ciclo, tipo, _ = ult
            pend_data = ult[2] if tipo == "PENDENCIA" else None

        # aplica transicoes ate estabilizar (poucas por rodada)
        for _ in range(4):
            if tipo is None:
                # nenhum evento ainda -> abre o ciclo 1 conforme o estado atual
                if estado == "PENDENTE":
                    self._add(sessao, mat, sis, 1, "PENDENCIA", agora, info)
                    ciclo, tipo, pend_data = 1, "PENDENCIA", agora
                    n += 1
                elif estado == "ADERENTE":
                    self._add(sessao, mat, sis, 1, "ADERENTE", agora, info)
                    ciclo, tipo = 1, "ADERENTE"
                    n += 1
                else:
                    break

            elif tipo == "PENDENCIA":
                # RESOLVIDO: so se ha resolucao E ela pertence a ESTE ciclo
                # (dt_resolvido >= abertura da pendencia do ciclo) — evita a
                # resolucao do ciclo 1 vazar para uma reabertura (ciclo 2+).
                if (info and info.dt_resolvido
                        and self._pertence_ao_ciclo(info.dt_resolvido, pend_data)):
                    self._add(sessao, mat, sis, ciclo, "RESOLVIDO",
                              info.dt_resolvido, info, ticket=info.ticket)
                    tipo = "RESOLVIDO"
                    n += 1
                    continue
                if estado == "ADERENTE":
                    self._add(sessao, mat, sis, ciclo, "ADERENTE", agora, info)
                    tipo = "ADERENTE"
                    n += 1
                    continue
                break  # segue pendente

            elif tipo == "RESOLVIDO":
                if estado == "ADERENTE":
                    self._add(sessao, mat, sis, ciclo, "ADERENTE", agora, info)
                    tipo = "ADERENTE"
                    n += 1
                    continue
                break  # resolvido, aguardando aderencia

            elif tipo == "ADERENTE":
                if estado == "PENDENTE":
                    # REABERTURA: nova pendencia abre o ciclo seguinte
                    self._add(sessao, mat, sis, ciclo + 1, "PENDENCIA", agora,
                              info, detalhe="reabertura")
                    ciclo, tipo, pend_data = ciclo + 1, "PENDENCIA", agora
                    n += 1
                    continue
                break  # segue aderente

            else:
                break
        return n

    @staticmethod
    def _pertence_ao_ciclo(dt_resolvido: str, pend_data: str) -> bool:
        """RESOLVIDO pertence ao ciclo se aconteceu depois da abertura da
        pendencia dele. Sem data de pendencia (nao deveria), aceita."""
        if not pend_data:
            return True
        return str(dt_resolvido) >= str(pend_data)

    def _add(self, sessao, mat, sis, ciclo, tipo, data, info,
             ticket=None, detalhe=None):
        """INSERT OR IGNORE — idempotente pelo UNIQUE (mat,sis,ciclo,tipo)."""
        sessao.execute(text("""
            INSERT OR IGNORE INTO ciclo_eventos_acesso
                (matricula, sistema, ciclo, tipo_evento, data_evento,
                 perfil, nome, login, cargo, ticket, detalhe, dt_registro)
            VALUES
                (:mat, :sis, :ciclo, :tipo, :data,
                 :perfil, :nome, :login, :cargo, :ticket, :detalhe, datetime('now'))
        """), {
            "mat": mat, "sis": sis, "ciclo": ciclo, "tipo": tipo, "data": str(data),
            "perfil": getattr(info, "perfil", None) if info else None,
            "nome": getattr(info, "nome", None) if info else None,
            "login": getattr(info, "login", None) if info else None,
            "cargo": getattr(info, "cargo", None) if info else None,
            "ticket": ticket, "detalhe": detalhe,
        })

    @staticmethod
    def _tabela(sessao, nome: str) -> bool:
        return sessao.execute(text(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=:n"
        ), {"n": nome}).fetchone() is not None
