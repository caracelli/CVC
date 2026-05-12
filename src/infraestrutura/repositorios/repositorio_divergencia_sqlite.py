from datetime import datetime
from typing import List

from loguru import logger

from dominio.entidades.divergencia import Divergencia
from dominio.objetos_valor.sistema import Sistema
from dominio.objetos_valor.tipo_divergencia import TipoDivergencia
from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import DivergenciaModel


class RepositorioDivergenciaSqlite:

    def __init__(self, conexao: ConexaoBancoDados):
        self._conexao = conexao

    def salvar_lote(self, divergencias: List[Divergencia]) -> None:
        with self._conexao.sessao() as sessao:
            sessao.query(DivergenciaModel).delete()
            for d in divergencias:
                sessao.add(DivergenciaModel(
                    id=d.id,
                    tipo=d.tipo.value,
                    sistema=d.sistema.value,
                    usuario=d.usuario,
                    nome_usuario=d.nome_usuario,
                    matricula=d.matricula,
                    perfil_encontrado=d.perfil_encontrado,
                    perfil_esperado=d.perfil_esperado,
                    descricao=d.descricao,
                    data_identificacao=d.data_identificacao,
                    resolvida=d.resolvida,
                    dt_importacao=datetime.now(),
                ))
            sessao.commit()
        logger.info(f"{len(divergencias)} divergencias gravadas no banco.")

    def obter_todas(self) -> List[Divergencia]:
        with self._conexao.sessao() as sessao:
            rows = sessao.query(DivergenciaModel).all()
            return [self._para_divergencia(r) for r in rows]

    def _para_divergencia(self, r: DivergenciaModel) -> Divergencia:
        return Divergencia(
            id=r.id,
            tipo=TipoDivergencia(r.tipo),
            sistema=Sistema(r.sistema),
            usuario=r.usuario,
            nome_usuario=r.nome_usuario or "",
            matricula=r.matricula,
            perfil_encontrado=r.perfil_encontrado,
            perfil_esperado=r.perfil_esperado,
            descricao=r.descricao or "",
            data_identificacao=r.data_identificacao or datetime.now(),
            resolvida=r.resolvida or False,
        )
