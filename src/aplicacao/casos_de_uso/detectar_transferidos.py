"""Detecta 'transferidos' a partir do HISTORICO do RH (CDC) — sem arquivo de
entrada. Uma pessoa entra na revisao quando uma carga de RH registrou mudanca de
cargo, centro de custo, departamento OU gestor (decisao da area, 29/07).

Alimenta a RegraAcessoTransferido, que marca os acessos dessas pessoas como
ACESSO_TRANSFERIDO (pendencia de revisao). Sem janela temporal: a mudanca conta
enquanto a pessoa estiver ATIVA (o tratamento sob ticket e' que resolve).
"""
import json
from datetime import date
from typing import List

from loguru import logger

from dominio.entidades.transferido import Transferido
from dominio.objetos_valor.cargo import Cargo
from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import Historico
from infraestrutura.repositorios.repositorio_funcionario_sqlite import RepositorioFuncionarioSqlite

# Campos cuja mudanca dispara revisao de acesso (== os comparados no CDC).
_CAMPOS_REVISAO = {"cargo_codigo", "cargo_descricao", "centro_custo_codigo",
                   "departamento", "gestor"}


class DetectarTransferidos:

    def __init__(self, conexao: ConexaoBancoDados):
        self._conexao = conexao
        self._repo_func = RepositorioFuncionarioSqlite(conexao)

    def executar(self) -> List[Transferido]:
        # So revisa quem esta ATIVO hoje (um desligado que mudou de cargo antes de
        # sair e' tratado pelo motor de desligados, nao aqui).
        ativos = {f.matricula: f for f in self._repo_func.obter_ativos()}

        with self._conexao.sessao() as sessao:
            rows = (sessao.query(Historico)
                    .filter(Historico.entidade == "RH_ATIVO",
                            Historico.tipo_mudanca == "ALTERADO")
                    .order_by(Historico.data_snapshot.desc(),
                              Historico.id.desc())
                    .all())
            # materializa o que precisamos ainda dentro da sessao
            regs = [(r.chave_entidade or r.matricula, r.campos_alterados or "",
                     r.dados_anterior, r.data_snapshot) for r in rows]

        transferidos: List[Transferido] = []
        vistos = set()
        for mat, campos_csv, dados_ant, dt_snap in regs:
            if not mat or mat in vistos:
                continue
            campos = {c.strip() for c in campos_csv.split(",") if c.strip()}
            if not (campos & _CAMPOS_REVISAO):
                continue
            func = ativos.get(mat)
            if func is None:
                continue
            vistos.add(mat)
            try:
                ant = json.loads(dados_ant) if dados_ant else {}
            except Exception:
                ant = {}
            cargo_ant = Cargo(
                codigo=ant.get("cargo_codigo") or "",
                descricao=ant.get("cargo_descricao") or "",
                departamento=ant.get("departamento") or "",
                centro_custo=ant.get("centro_custo_codigo") or "",
            )
            transferidos.append(Transferido(
                funcionario=func,
                cargo_anterior=cargo_ant,
                gestor_anterior=ant.get("gestor"),
                data_transferencia=dt_snap or date.today(),
            ))
        logger.info(
            f"Transferidos detectados (mudança cargo/CC/depto/gestor): "
            f"{len(transferidos)}")
        return transferidos
