from pathlib import Path

from loguru import logger

from dominio.objetos_valor.sistema import Sistema
from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.leitores_arquivos.configs_sistemas import CONFIGS_SISTEMAS
from infraestrutura.leitores_arquivos.leitor_sistema import LeitorSistema
from infraestrutura.repositorios.repositorio_acesso_sqlite import RepositorioAcessoSqlite
from infraestrutura.repositorios.repositorio_log_importacao import (
    RepositorioLogImportacao, loga_se_reimportacao,
)


class ImportarSistema:

    def __init__(
        self,
        conexao: ConexaoBancoDados,
        sistema: Sistema,
        pasta_entrada: str,
        pasta_processados: str = None,
        pasta_erros: str = None,
    ):
        cfg = CONFIGS_SISTEMAS[sistema]
        self._leitor = LeitorSistema(cfg, pasta_processados=pasta_processados, pasta_erros=pasta_erros)
        self._repositorio = RepositorioAcessoSqlite(conexao)
        self._log = RepositorioLogImportacao(conexao)
        self._sistema = sistema
        self._pasta_entrada = pasta_entrada

    def executar(self) -> int:
        logger.info(f"=== Importacao {self._sistema.value} iniciada ===")

        # varredura recursiva da pasta de entrada, ordenada pela data no nome
        arquivos = self._leitor.listar_ordenado(self._pasta_entrada)
        if not arquivos:
            logger.warning(f"{self._sistema.value}: nenhum arquivo encontrado.")
            return 0

        # PROCESSADOS na raiz da pasta do sistema (ex.: .../SYSTUR/PROCESSADOS)
        destino_proc = Path(self._pasta_entrada) / "PROCESSADOS"

        for arquivo in arquivos:
            # Hash antes da leitura — assim, mesmo se a leitura falhar, logamos
            # tentativa de processar o arquivo com seu fingerprint.
            try:
                hash_arq = loga_se_reimportacao(self._log, caminho=arquivo, tipo=self._sistema.value)
            except Exception as e:
                logger.warning(f"Falha calculando hash de '{arquivo.name}': {e!r}")
                hash_arq = ""

            try:
                perfis = self._leitor.ler_um(arquivo)
            except Exception as e:
                logger.error(f"Erro lendo '{arquivo.name}': {e!r}")
                self._log.registrar(
                    arquivo=arquivo.name, tipo=self._sistema.value,
                    hash_arquivo=hash_arq, status="ERRO", mensagem_erro=str(e),
                )
                self._leitor.mover_para_erros(arquivo, str(e))
                continue
            # substituicao (snapshot): remove os dados do sistema da
            # importacao anterior e grava os do arquivo atual
            self._repositorio.substituir_sistema(self._sistema, perfis, arquivo.name)
            self._log.registrar(
                arquivo=arquivo.name, tipo=self._sistema.value,
                hash_arquivo=hash_arq, total_registros=len(perfis),
                status="SUCESSO",
            )
            self._leitor.mover_para_processados(arquivo, destino=destino_proc)
            logger.success(
                f"{self._sistema.value}: '{arquivo.name}' processado "
                f"({len(perfis)} linhas) e movido para PROCESSADOS."
            )

        total = len(self._repositorio.obter_por_sistema(self._sistema))
        logger.info(
            f"=== {self._sistema.value}: {len(arquivos)} arquivo(s) processado(s); "
            f"{total} acessos no banco (estado final) ==="
        )
        return total
