from datetime import datetime
from typing import List

from loguru import logger

from dominio.entidades.transferido import Transferido
from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import TransferidoModel


class RepositorioTransferidoSqlite:
    """Persiste o de/para de quem mudou de cargo/CC/departamento/gestor.

    Snapshot (delete + insert), igual a `divergencias`: o detector devolve a
    mudanca MAIS RECENTE de cada pessoa ATIVA, entao a tabela sempre reflete o
    cenario da ultima analise — nao acumula historico (a trilha completa e' a
    tabela `historico`, que segue append-only)."""

    def __init__(self, conexao: ConexaoBancoDados):
        self._conexao = conexao

    def salvar_lote(self, transferidos: List[Transferido]) -> None:
        agora = datetime.now()
        registros = []
        for t in transferidos:
            f, ant = t.funcionario, t.cargo_anterior
            registros.append({
                "matricula": f.matricula,
                "nome": f.nome or "",
                "campos_mudados": t.campos_mudados,
                "data_transferencia": (t.data_transferencia.isoformat()
                                       if t.data_transferencia else ""),
                "cargo_codigo_anterior": ant.codigo or "",
                "cargo_anterior": ant.descricao or "",
                "departamento_anterior": ant.departamento or "",
                "centro_custo_anterior": ant.centro_custo or "",
                "gestor_anterior": t.gestor_anterior or "",
                "cargo_codigo_atual": f.cargo.codigo or "",
                "cargo_atual": f.cargo.descricao or "",
                "departamento_atual": f.cargo.departamento or "",
                "centro_custo_atual": f.cargo.centro_custo or "",
                "gestor_atual": f.gestor or "",
                "dt_importacao": agora,
            })
        with self._conexao.sessao() as sessao:
            sessao.query(TransferidoModel).delete()
            if registros:
                sessao.bulk_insert_mappings(TransferidoModel, registros)
            sessao.commit()
        logger.info(f"{len(transferidos)} transferido(s) com de/para gravado(s).")
