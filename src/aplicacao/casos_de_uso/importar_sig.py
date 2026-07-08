"""Importacao do SIG (Card 12) — extrato matricial + de-para de codigos.

Fluxo:
  1. Le o de-para mais recente em MATRIZES/PERFIS_SISTEMAS/SIG/DE_PARA/
     e grava em catalogo_perfis (substituicao por sistema)
  2. Le os extratos em ENTRADA/SISTEMAS/SIG/ ordenados por data no nome
  3. Despivota cada linha (X = acesso) e traduz codigos via catalogo
  4. Grava em acessos_sistemas (substituicao por sistema)

Pre-requisito: a tabela catalogo_perfis e o sistema SIG devem existir.
Schema novo (commit 795e787) ja garante isso.

E' INDEPENDENTE do fluxo SYSTUR/SIGOT/etc. — pode ser desligado removendo
a chamada do main.py sem afetar nada.
"""
from pathlib import Path
from typing import Dict, Optional

from loguru import logger

from dominio.objetos_valor.sistema import Sistema
from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.leitores_arquivos.leitor_sig import LeitorCatalogoSig, LeitorSig
from infraestrutura.repositorios.repositorio_acesso_sqlite import RepositorioAcessoSqlite
from infraestrutura.repositorios.repositorio_catalogo_perfil import RepositorioCatalogoPerfil
from infraestrutura.repositorios.repositorio_log_importacao import (
    RepositorioLogImportacao, loga_se_reimportacao, data_modificacao,
)


class ImportarSig:

    def __init__(
        self,
        conexao: ConexaoBancoDados,
        pasta_extratos: str,
        pasta_de_para: str,
        pasta_processados: Optional[str] = None,
        pasta_erros: Optional[str] = None,
    ):
        self._pasta_extratos = pasta_extratos
        self._pasta_de_para = pasta_de_para
        self._catalogo_leitor = LeitorCatalogoSig(
            pasta_processados=None,  # de-para NAO move pra PROCESSADOS — fica
            pasta_erros=pasta_erros,
        )
        self._extrato_leitor = None  # criado depois do catalogo carregar
        self._repo_acesso = RepositorioAcessoSqlite(conexao)
        self._repo_catalogo = RepositorioCatalogoPerfil(conexao)
        self._repo_log = RepositorioLogImportacao(conexao)
        self._pasta_processados = pasta_processados
        self._pasta_erros = pasta_erros

    def executar(self) -> int:
        logger.info("=== Importacao SIG iniciada ===")

        if not Path(self._pasta_extratos).exists():
            logger.info(f"SIG: pasta de extratos nao existe ({self._pasta_extratos}). "
                        f"Pulando — SIG ainda nao em uso.")
            return 0

        # 1) Carrega o de-para mais recente em catalogo_perfis
        catalogo = self._carregar_catalogo()
        if not catalogo:
            logger.warning("SIG: catalogo vazio — codigos nao terao nome legivel. "
                           "Processando assim mesmo (codigo como fallback).")

        # 2) Le todos os extratos ordenados por data
        self._extrato_leitor = LeitorSig(
            catalogo=catalogo,
            pasta_processados=self._pasta_processados,
            pasta_erros=self._pasta_erros,
        )
        arquivos = self._extrato_leitor.listar_ordenado(self._pasta_extratos)
        if not arquivos:
            logger.warning(f"SIG: nenhum arquivo de extrato em {self._pasta_extratos}")
            return 0

        total_perfis = 0
        for arquivo in arquivos:
            dt_arq = data_modificacao(arquivo)
            try:
                hash_arq = loga_se_reimportacao(self._repo_log, caminho=arquivo, tipo="SIG")
            except Exception as e:
                logger.warning(f"SIG: falha calculando hash de {arquivo.name}: {e!r}")
                hash_arq = ""

            try:
                perfis = self._extrato_leitor.ler_um(arquivo)
            except Exception as e:
                logger.error(f"SIG: erro lendo '{arquivo.name}': {e!r}")
                self._repo_log.registrar(
                    arquivo=arquivo.name, tipo="SIG",
                    hash_arquivo=hash_arq, status="ERRO", mensagem_erro=str(e),
                    dt_arquivo=dt_arq,
                )
                self._extrato_leitor.mover_para_erros(arquivo, str(e))
                continue

            self._repo_acesso.substituir_sistema(Sistema.SIG, perfis, arquivo.name)
            self._repo_log.registrar(
                arquivo=arquivo.name, tipo="SIG",
                hash_arquivo=hash_arq, total_registros=len(perfis),
                status="SUCESSO", dt_arquivo=dt_arq,
            )
            self._extrato_leitor.mover_para_processados(arquivo)
            total_perfis += len(perfis)
            logger.success(
                f"SIG: '{arquivo.name}' processado — {len(perfis)} linhas "
                f"despivotadas e movido para PROCESSADOS."
            )

        total_no_banco = self._repo_acesso.contar_por_sistema(Sistema.SIG)
        logger.info(
            f"=== SIG: {len(arquivos)} arquivo(s) processado(s); "
            f"{total_no_banco} acessos no banco (estado final) ==="
        )
        return total_no_banco

    def _carregar_catalogo(self) -> Dict[str, str]:
        """Le o de-para XLSX mais recente e atualiza catalogo_perfis."""
        if not Path(self._pasta_de_para).exists():
            logger.warning(f"SIG: pasta de de-para nao existe ({self._pasta_de_para})")
            return {}
        arquivos = self._catalogo_leitor.listar_arquivos_decrescente(self._pasta_de_para)
        if not arquivos:
            logger.warning(f"SIG: nenhum arquivo de de-para em {self._pasta_de_para}")
            return {}
        arquivo = arquivos[0]
        try:
            mapa = self._catalogo_leitor.ler(arquivo)
        except Exception as e:
            logger.error(f"SIG: erro lendo de-para '{arquivo.name}': {e!r}")
            return {}
        # Atualiza catalogo_perfis (substituicao por sistema)
        de_para = mapa.items()
        self._repo_catalogo.substituir_catalogo(Sistema.SIG, de_para, arquivo.name)
        return mapa
