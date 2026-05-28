"""Log de importacoes com hash do arquivo de origem.

O hash (md5) e' calculado uma vez por arquivo e gravado em log_importacoes.
Permite:
- Detectar reimportacao do MESMO conteudo (mesmo arquivo, mesmo nome ou nao)
- Auditoria: qual versao do arquivo gerou esta importacao
- (Futuro) Skip de reprocessamento se hash ja existe — hoje so loga aviso
"""
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger

from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import LogImportacao


def md5_arquivo(caminho: Path, bloco: int = 65536) -> str:
    """MD5 streaming — nao carrega o arquivo todo em memoria."""
    h = hashlib.md5()
    with open(caminho, "rb") as f:
        while True:
            chunk = f.read(bloco)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


class RepositorioLogImportacao:

    def __init__(self, conexao: ConexaoBancoDados):
        self._conexao = conexao

    def hash_ja_importado(self, hash_arquivo: str) -> Optional[str]:
        """Devolve o nome do arquivo que ja foi importado com este hash, ou None."""
        if not hash_arquivo:
            return None
        with self._conexao.sessao() as sessao:
            row = (sessao.query(LogImportacao)
                   .filter_by(hash_arquivo=hash_arquivo, status="SUCESSO")
                   .order_by(LogImportacao.dt_importacao.desc())
                   .first())
            return row.arquivo if row else None

    def registrar(self, *, arquivo: str, tipo: str, hash_arquivo: str,
                  total_registros: int = 0, status: str = "SUCESSO",
                  mensagem_erro: str = None) -> None:
        with self._conexao.sessao() as sessao:
            sessao.add(LogImportacao(
                arquivo=arquivo,
                tipo=tipo,
                hash_arquivo=hash_arquivo,
                total_registros=total_registros,
                status=status,
                mensagem_erro=mensagem_erro,
                dt_importacao=datetime.now(),
            ))
            sessao.commit()


def loga_se_reimportacao(repo: RepositorioLogImportacao, *,
                          caminho: Path, tipo: str) -> str:
    """Calcula hash, avisa se ja foi importado (mas NAO bloqueia — fase 1).
    Devolve o hash para gravacao posterior no log."""
    h = md5_arquivo(caminho)
    ja = repo.hash_ja_importado(h)
    if ja and ja != caminho.name:
        logger.warning(
            f"Reimportacao detectada ({tipo}): conteudo identico ao arquivo "
            f"'{ja}' (hash {h[:8]}...). Processando assim mesmo.")
    elif ja:
        logger.info(
            f"Arquivo {caminho.name} ({tipo}) ja foi importado com este hash "
            f"({h[:8]}...). Reprocessando.")
    return h
