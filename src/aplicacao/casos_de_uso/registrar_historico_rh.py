"""CDC da base de RH — trilha de auditoria.

Roda no momento da importação, **antes** do merge gravar os novos valores
sobre os antigos. Compara o estado atual do banco (importação anterior) com
os registros recebidos no arquivo e registra apenas o que mudou:

  NOVO     — matrícula veio no arquivo e não existia no banco
  ALTERADO — matrícula existe nos dois lados e algum campo mudou
  REMOVIDO — matrícula existia no banco e não veio no arquivo

REMOVIDO é apenas registrado na trilha (auditoria); a linha **não** é
apagada do banco — o tratamento de quem saiu da base (desligado/transferido)
é fluxo separado, a ser feito posteriormente.

A comparação aplica a mesma padronização de CPF/nome/matrícula/situação dos
dois lados, senão diferença de formatação viraria falsa "alteração".
"""

import json
from datetime import date

from loguru import logger

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import RhAtivo, RhDesligado, SnapshotRh, HistoricoRh
from dominio.servicos_dominio.servico_padronizacao import ServicoPadronizacao

# Campos comparados por tipo (ordem usada também no JSON da trilha)
_CAMPOS_ATIVO = [
    "nome", "cpf", "cargo_codigo", "cargo_descricao", "centro_custo_codigo",
    "departamento", "data_admissao", "email", "situacao",
]
_CAMPOS_DESLIGADO = [
    "nome", "cpf", "cargo_codigo", "cargo_descricao", "centro_custo_codigo",
    "departamento", "data_admissao", "data_desligamento", "email",
]


class RegistrarHistoricoRh:

    def __init__(self, conexao: ConexaoBancoDados):
        self._conexao = conexao
        self._pad = ServicoPadronizacao()

    # ---- API pública -----------------------------------------------------

    def registrar_ativos(self, ativos: list) -> dict:
        return self._registrar("ATIVO", RhAtivo, _CAMPOS_ATIVO, ativos)

    def registrar_desligados(self, desligados: list) -> dict:
        return self._registrar("DESLIGADO", RhDesligado, _CAMPOS_DESLIGADO, desligados)

    # ---- núcleo do CDC ---------------------------------------------------

    def _registrar(self, tipo: str, modelo, campos: list, recebidos: list) -> dict:
        hoje = date.today()

        with self._conexao.sessao() as sessao:
            anterior = {
                self._pad.normalizar_matricula(r.matricula): self._dict_orm(r, campos)
                for r in sessao.query(modelo).all()
            }
            novo = {}
            for f in recebidos:
                chave = self._pad.normalizar_matricula(f.matricula)
                novo[chave] = self._dict_entidade(f, campos)

            novos = alterados = removidos = 0

            for matricula, dados_novo in novo.items():
                dados_ant = anterior.get(matricula)
                if dados_ant is None:
                    sessao.add(HistoricoRh(
                        data_snapshot=hoje, tipo=tipo, matricula=matricula,
                        tipo_mudanca="NOVO", campos_alterados=None,
                        dados_anterior=None, dados_novo=self._json(dados_novo),
                    ))
                    novos += 1
                else:
                    difs = [c for c in campos if dados_ant.get(c) != dados_novo.get(c)]
                    if difs:
                        sessao.add(HistoricoRh(
                            data_snapshot=hoje, tipo=tipo, matricula=matricula,
                            tipo_mudanca="ALTERADO", campos_alterados=",".join(difs),
                            dados_anterior=self._json(dados_ant),
                            dados_novo=self._json(dados_novo),
                        ))
                        alterados += 1

            for matricula, dados_ant in anterior.items():
                if matricula not in novo:
                    sessao.add(HistoricoRh(
                        data_snapshot=hoje, tipo=tipo, matricula=matricula,
                        tipo_mudanca="REMOVIDO", campos_alterados=None,
                        dados_anterior=self._json(dados_ant), dados_novo=None,
                    ))
                    removidos += 1

            sessao.add(SnapshotRh(
                data_snapshot=hoje, tipo=tipo, total_registros=len(novo),
                novos=novos, alterados=alterados, removidos=removidos,
            ))
            sessao.commit()

        logger.info(
            f"Histórico {tipo}: {novos} novos, {alterados} alterados, "
            f"{removidos} removidos (total na base: {len(novo)})."
        )
        return {"total": len(novo), "novos": novos, "alterados": alterados, "removidos": removidos}

    # ---- normalização para comparação ------------------------------------

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
