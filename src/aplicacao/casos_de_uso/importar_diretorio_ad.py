"""Importa os exports do diretorio (AD) por OU e grava como identidades no
`rh_ativos` (tipo_vinculo FRANQUEADO/PRESTADOR), para dar dono aos acessos
orfaos via login. NAO passa pela trilha CDC do RH (nao e' movimentacao de RH).

Roteia a populacao pelo NOME do arquivo:
  OU_Franq*      -> FRANQUEADO (identidade ativa)
  OU_Prest*      -> PRESTADOR  (identidade ativa)
  OU_Desligados* -> DESLIGADOS (B2 = sim, 29/07): grava em rh_desligados com o
                    LOGIN como chave, alimentando o motor de acesso de desligado.
"""
from pathlib import Path

from loguru import logger

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.leitores_arquivos.leitor_diretorio_ad import LeitorDiretorioAd
from infraestrutura.repositorios.repositorio_funcionario_sqlite import RepositorioFuncionarioSqlite


def _populacao(nome_arquivo: str):
    n = nome_arquivo.lower()
    if "franq" in n:
        return "FRANQUEADO"
    if "prest" in n:
        return "PRESTADOR"
    if "deslig" in n:
        return "DESLIGADOS"   # B2 = sim: alimenta o motor de desligados
    return None


class ImportarDiretorioAd:

    def __init__(
        self,
        conexao: ConexaoBancoDados,
        pasta,
        pasta_processados: str = None,
        pasta_erros: str = None,
        processar: bool = True,
    ):
        """`pasta` aceita um caminho OU uma lista deles. Desde 05/08/2026 o
        cliente entrega os exports do AD em pastas separadas por populacao
        (AD_FRANQUEADOS / AD_PRESTADORES / AD_DESLIGADOS), cada uma com
        subpastas por mes — antes era uma pasta unica. O roteamento continua
        sendo pelo NOME do arquivo, nao pela pasta: uma pasta com o nome
        'errado' nao classifica ninguem errado."""
        self._leitor = LeitorDiretorioAd(pasta_processados=pasta_processados, pasta_erros=pasta_erros)
        self._repo = RepositorioFuncionarioSqlite(conexao)
        self._pastas = [pasta] if isinstance(pasta, (str, Path)) else list(pasta or [])
        self._processar = processar

    def executar(self) -> int:
        if not self._processar:
            logger.info("Diretorio AD fora de escopo (processar=false) — ignorado.")
            return 0
        logger.info("=== Importacao Diretorio AD iniciada ===")

        total = 0
        arquivos = []
        vistos = set()
        for pasta in self._pastas:
            for arq in self._leitor.listar_arquivos(str(pasta)):
                # a mesma pasta configurada duas vezes (ou aninhada) nao pode
                # importar o mesmo arquivo duas vezes
                chave = str(arq.resolve()).lower()
                if chave not in vistos:
                    vistos.add(chave)
                    arquivos.append(arq)
        for arquivo in arquivos:
            pop = _populacao(arquivo.name)
            if pop is None:
                logger.info(f"Diretorio AD: '{arquivo.name}' sem populacao mapeada — ignorado.")
                continue
            try:
                if pop == "DESLIGADOS":
                    identidades = self._leitor.ler_desligados(arquivo)
                    if identidades:
                        self._repo.salvar_desligados(identidades, arquivo.name)
                        total += len(identidades)
                else:
                    identidades = self._leitor.ler(arquivo, tipo_vinculo=pop)
                    if identidades:
                        self._repo.salvar_ativos(identidades, arquivo.name)
                        total += len(identidades)
                self._leitor.mover_para_processados(arquivo)
            except Exception as e:
                logger.error(f"Diretorio AD: erro em '{arquivo.name}': {e!r}")
                self._leitor.mover_para_erros(arquivo, str(e))

        logger.info(f"=== Diretorio AD: {total} identidades gravadas ===")
        return total
