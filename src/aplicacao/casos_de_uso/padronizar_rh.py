from loguru import logger

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import RhAtivo, RhDesligado
from dominio.servicos_dominio.servico_padronizacao import ServicoPadronizacao


class PadronizarRh:

    def __init__(self, conexao: ConexaoBancoDados):
        self._conexao = conexao
        self._pad = ServicoPadronizacao()

    def executar(self):
        logger.info("=== Padronização RH iniciada ===")
        total_ativos = self._padronizar_ativos()
        total_desligados = self._padronizar_desligados()
        logger.info(f"=== Padronização concluída: {total_ativos} ativos, {total_desligados} desligados ===")

    def _padronizar_ativos(self) -> int:
        with self._conexao.sessao() as sessao:
            registros = sessao.query(RhAtivo).all()
            existentes = {r.matricula for r in registros}
            for r in registros:
                r.cpf = self._pad.normalizar_cpf(r.cpf)
                r.nome = self._pad.normalizar_nome(r.nome)
                r.situacao = self._pad.normalizar_situacao(r.situacao)
                self._renomear_matricula(r, existentes)
            sessao.commit()
            total = len(registros)
        logger.info(f"{total} ativos padronizados.")
        return total

    def _padronizar_desligados(self) -> int:
        with self._conexao.sessao() as sessao:
            registros = sessao.query(RhDesligado).all()
            existentes = {r.matricula for r in registros}
            for r in registros:
                r.cpf = self._pad.normalizar_cpf(r.cpf)
                r.nome = self._pad.normalizar_nome(r.nome)
                self._renomear_matricula(r, existentes)
            sessao.commit()
        return len(registros)

    def _renomear_matricula(self, r, existentes: set) -> None:
        """Normaliza a matricula (PK) in-place, mas SO se nao colidir com outra
        ja presente. Ex.: '00100' e '100' normalizam para '100' — renomear os
        dois quebraria a PK (UNIQUE constraint) e derrubaria a padronizacao
        inteira. Mantem o segundo sem alterar e loga."""
        nova = self._pad.normalizar_matricula(r.matricula)
        if nova == r.matricula:
            return
        if nova in existentes:
            logger.warning(
                f"Padronização: matrícula '{r.matricula}' normalizaria para "
                f"'{nova}', que já existe — mantida sem alterar (evita colisão de PK).")
            return
        existentes.discard(r.matricula)
        existentes.add(nova)
        r.matricula = nova
