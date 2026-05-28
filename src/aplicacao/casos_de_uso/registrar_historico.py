"""CDC unificado (trilha de auditoria) — RH e acessos no mesmo historico.

Antes existia RegistrarHistoricoRh especifico para RH. Esta versao
generaliza: qualquer entidade (RH_ATIVO, RH_DESLIGADO, ACESSO_SISTEMA, ...)
pode registrar mudancas na tabela unica `historico`.

Por que unificar: o painel de auditoria precisa de uma trilha cronologica
unica do que aconteceu por funcionario — admissao, mudanca de cargo, ganho
de acesso, perda de acesso. Tabelas separadas obrigavam UNION em toda query.

Comparacao continua igual: NOVO / ALTERADO / REMOVIDO. Carga inicial nao
gera trilha (so estabelece baseline).
"""
import json
from datetime import date
from typing import Callable, Dict, List, Optional

from loguru import logger

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import RhAtivo, RhDesligado, SnapshotRh, Historico
from dominio.servicos_dominio.servico_padronizacao import ServicoPadronizacao


# Vocabulario fixo de entidades — adicionar aqui implica documentar em SCHEMA_DECISIONS
ENTIDADE_RH_ATIVO = "RH_ATIVO"
ENTIDADE_RH_DESLIGADO = "RH_DESLIGADO"
ENTIDADE_ACESSO_SISTEMA = "ACESSO_SISTEMA"

# Campos comparados por tipo (ordem usada no JSON da trilha)
_CAMPOS_ATIVO = [
    "nome", "cpf", "cargo_codigo", "cargo_descricao", "centro_custo_codigo",
    "departamento", "data_admissao", "email", "situacao",
]
_CAMPOS_DESLIGADO = [
    "nome", "cpf", "cargo_codigo", "cargo_descricao", "centro_custo_codigo",
    "departamento", "data_admissao", "data_desligamento", "email",
]


class RegistrarHistorico:
    """Servico generico de CDC — assina como antes mas grava em `historico`."""

    def __init__(self, conexao: ConexaoBancoDados):
        self._conexao = conexao
        self._pad = ServicoPadronizacao()

    # ---- API publica para RH (compativel com chamadas legadas) -------------

    def registrar_ativos(self, ativos: list) -> dict:
        return self._registrar(
            entidade=ENTIDADE_RH_ATIVO,
            tipo_compat="ATIVO",
            modelo_orm=RhAtivo,
            campos=_CAMPOS_ATIVO,
            recebidos=ativos,
            chave_orm=lambda r: self._pad.normalizar_matricula(r.matricula),
            chave_entidade=lambda f: self._pad.normalizar_matricula(f.matricula),
        )

    def registrar_desligados(self, desligados: list) -> dict:
        return self._registrar(
            entidade=ENTIDADE_RH_DESLIGADO,
            tipo_compat="DESLIGADO",
            modelo_orm=RhDesligado,
            campos=_CAMPOS_DESLIGADO,
            recebidos=desligados,
            chave_orm=lambda r: self._pad.normalizar_matricula(r.matricula),
            chave_entidade=lambda f: self._pad.normalizar_matricula(f.matricula),
        )

    # ---- nucleo do CDC ---------------------------------------------------

    def _registrar(self, *, entidade: str, tipo_compat: str, modelo_orm,
                   campos: list, recebidos: list,
                   chave_orm: Callable, chave_entidade: Callable) -> dict:
        hoje = date.today()

        with self._conexao.sessao() as sessao:
            anterior = {
                chave_orm(r): self._dict_orm(r, campos)
                for r in sessao.query(modelo_orm).all()
            }
            novo: Dict[str, dict] = {}
            for f in recebidos:
                chave = chave_entidade(f)
                novo[chave] = self._dict_entidade(f, campos)

            # Carga inicial: base anterior vazia = marco zero. Estabelece a
            # baseline e NAO gera trilha — a auditoria de ouvidoria registra
            # apenas os ajustes a partir da 2a importacao.
            if not anterior:
                sessao.add(SnapshotRh(
                    data_snapshot=hoje, tipo=tipo_compat, total_registros=len(novo),
                    novos=0, alterados=0, removidos=0,
                ))
                sessao.commit()
                logger.info(
                    f"Historico {entidade}: carga inicial — baseline de "
                    f"{len(novo)} registros estabelecida, trilha nao gerada."
                )
                return {"total": len(novo), "novos": 0, "alterados": 0,
                        "removidos": 0, "carga_inicial": True}

            novos = alterados = removidos = 0

            for chave, dados_novo in novo.items():
                dados_ant = anterior.get(chave)
                if dados_ant is None:
                    sessao.add(self._registro_historico(
                        hoje, entidade, tipo_compat, chave,
                        tipo_mudanca="NOVO", campos_alterados=None,
                        dados_ant=None, dados_novo=dados_novo,
                    ))
                    novos += 1
                else:
                    difs = [c for c in campos if dados_ant.get(c) != dados_novo.get(c)]
                    if difs:
                        sessao.add(self._registro_historico(
                            hoje, entidade, tipo_compat, chave,
                            tipo_mudanca="ALTERADO", campos_alterados=",".join(difs),
                            dados_ant=dados_ant, dados_novo=dados_novo,
                        ))
                        alterados += 1

            for chave, dados_ant in anterior.items():
                if chave not in novo:
                    sessao.add(self._registro_historico(
                        hoje, entidade, tipo_compat, chave,
                        tipo_mudanca="REMOVIDO", campos_alterados=None,
                        dados_ant=dados_ant, dados_novo=None,
                    ))
                    removidos += 1

            sessao.add(SnapshotRh(
                data_snapshot=hoje, tipo=tipo_compat, total_registros=len(novo),
                novos=novos, alterados=alterados, removidos=removidos,
            ))
            sessao.commit()

        logger.info(
            f"Historico {entidade}: {novos} novos, {alterados} alterados, "
            f"{removidos} removidos (total na base: {len(novo)})."
        )
        return {"total": len(novo), "novos": novos, "alterados": alterados, "removidos": removidos}

    def _registro_historico(self, hoje, entidade, tipo_compat, chave, *,
                            tipo_mudanca, campos_alterados, dados_ant, dados_novo):
        # Mantem tipo e matricula populados em entidades RH para o codigo
        # legado de leitura (visualizador, queries antigas).
        is_rh = entidade in (ENTIDADE_RH_ATIVO, ENTIDADE_RH_DESLIGADO)
        return Historico(
            data_snapshot=hoje,
            entidade=entidade,
            chave_entidade=chave,
            tipo_mudanca=tipo_mudanca,
            campos_alterados=campos_alterados,
            dados_anterior=self._json(dados_ant) if dados_ant else None,
            dados_novo=self._json(dados_novo) if dados_novo else None,
            tipo=tipo_compat if is_rh else None,
            matricula=chave if is_rh else None,
        )

    # ---- normalizacao para comparacao ------------------------------------

    def _dict_orm(self, r, campos: list) -> dict:
        bruto = {
            "nome": r.nome, "cpf": r.cpf,
            "cargo_codigo": r.cargo_codigo, "cargo_descricao": r.cargo_descricao,
            "centro_custo_codigo": r.centro_custo_codigo,
            "departamento": r.departamento,
            "data_admissao": r.data_admissao,
            "email": r.email,
            "situacao": getattr(r, "situacao", None),
            "data_desligamento": getattr(r, "data_desligamento", None),
        }
        return self._normalizar({c: bruto.get(c) for c in campos})

    def _dict_entidade(self, f, campos: list) -> dict:
        bruto = {
            "nome": f.nome, "cpf": f.cpf,
            "cargo_codigo": f.cargo.codigo, "cargo_descricao": f.cargo.descricao,
            "centro_custo_codigo": f.cargo.centro_custo,
            "departamento": f.cargo.departamento,
            "data_admissao": getattr(f, "data_admissao", None),
            "email": f.email,
            "situacao": getattr(f, "situacao", None),
            "data_desligamento": getattr(f, "data_desligamento", None),
        }
        return self._normalizar({c: bruto.get(c) for c in campos})

    def _normalizar(self, d: dict) -> dict:
        out = {}
        for k, v in d.items():
            if k == "cpf":
                out[k] = self._pad.normalizar_cpf(v)
            elif k == "nome":
                out[k] = self._pad.normalizar_nome(v)
            elif k == "situacao":
                out[k] = self._pad.normalizar_situacao(v)
            elif k in ("data_admissao", "data_desligamento"):
                out[k] = str(v) if v else ""
            else:
                out[k] = (str(v).strip() if v is not None else "")
        return out

    @staticmethod
    def _json(d: dict) -> str:
        return json.dumps(d, ensure_ascii=False, sort_keys=True)


# ---- compat: alias para imports legados ----------------------------------
# A classe foi renomeada de RegistrarHistoricoRh para RegistrarHistorico (e
# generalizada). Mantemos o alias para nao quebrar quem ainda importa o nome
# antigo durante a transicao.
RegistrarHistoricoRh = RegistrarHistorico
