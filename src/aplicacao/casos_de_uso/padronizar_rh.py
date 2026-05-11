from datetime import date

from loguru import logger

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import RhAtivo, RhDesligado, SnapshotRh
from dominio.servicos_dominio.servico_padronizacao import ServicoPadronizacao


class PadronizarRh:

    def __init__(self, conexao: ConexaoBancoDados):
        self._conexao = conexao
        self._pad = ServicoPadronizacao()

    def executar(self):
        logger.info("=== Padronização RH iniciada ===")
        total_ativos = self._padronizar_ativos()
        total_desligados = self._padronizar_desligados()
        self._registrar_snapshot("ATIVO", total_ativos)
        self._registrar_snapshot("DESLIGADO", total_desligados)
        logger.info(f"=== Padronização concluída: {total_ativos} ativos, {total_desligados} desligados ===")

    def _padronizar_ativos(self) -> int:
        with self._conexao.sessao() as sessao:
            registros = sessao.query(RhAtivo).all()
            for r in registros:
                r.cpf = self._pad.normalizar_cpf(r.cpf)
                r.nome = self._pad.normalizar_nome(r.nome)
                r.matricula = self._pad.normalizar_matricula(r.matricula)
                r.situacao = self._pad.normalizar_situacao(r.situacao)
            sessao.commit()
            total = len(registros)
        logger.info(f"{total} ativos padronizados.")
        return total

    def _padronizar_desligados(self) -> int:
        with self._conexao.sessao() as sessao:
            registros = sessao.query(RhDesligado).all()
            for r in registros:
                r.cpf = self._pad.normalizar_cpf(r.cpf)
                r.nome = self._pad.normalizar_nome(r.nome)
                r.matricula = self._pad.normalizar_matricula(r.matricula)
            sessao.commit()
        return len(registros)

    def _registrar_snapshot(self, tipo: str, total: int):
        with self._conexao.sessao() as sessao:
            sessao.add(SnapshotRh(
                data_snapshot=date.today(),
                tipo=tipo,
                total_registros=total,
            ))
            sessao.commit()
        logger.info(f"Snapshot registrado: {tipo} — {total} registros.")
