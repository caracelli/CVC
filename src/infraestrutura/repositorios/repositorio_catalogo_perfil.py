"""Catalogo de perfis por sistema (codigo -> nome legivel).

Persiste o de-para que sistemas como SIG e Oracle EBS exportam separadamente
(SIG_18.05.26.xlsx tem codigos numericos; ID_x_Perfis_SIG.xlsx tem o de-para).
Para sistemas onde o extrato ja traz nome legivel (SYSTUR, SIGOT), codigo=nome.

Familia: prefixo extraido do nome (ate o primeiro '_' ou ' '). Permite
agregacao por modulo no painel: ACESSO_HOTEL_*, ACESSO_CARRO_*, CAD_*, ATD_*.
"""
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

from loguru import logger

from dominio.objetos_valor.sistema import Sistema
from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import CatalogoPerfil


def familia_do_nome(nome: str) -> str:
    """Extrai o prefixo (familia/modulo) do nome do perfil.

    Regras: ate o primeiro '_' ou ' '. Empty se nome vazio. Util para
    agrupar 'ACESSO_HOTEL_NAC_*' como familia 'ACESSO_HOTEL'.
    """
    if not nome:
        return ""
    n = str(nome).strip().upper()
    # Familia composta de 2 niveis quando o segundo token e' muito comum
    # (HOTEL, CARRO, etc.) — heuristica simples por enquanto.
    partes = n.replace(" ", "_").split("_")
    if len(partes) >= 3 and partes[0] in ("ACESSO", "ATD"):
        return "_".join(partes[:2])  # ACESSO_HOTEL, ATD_HTL
    return partes[0]


class RepositorioCatalogoPerfil:

    def __init__(self, conexao: ConexaoBancoDados):
        self._conexao = conexao

    # ------------------------------------------------------------------
    # Escrita
    # ------------------------------------------------------------------
    def substituir_catalogo(
        self,
        sistema: Sistema,
        de_para: Iterable[Tuple[str, str]],
        arquivo_origem: str = "",
        descricoes: Optional[Dict[str, str]] = None,
    ) -> int:
        """Substitui TODO o catalogo do sistema (semantica de snapshot).

        de_para: iteravel de (codigo, nome).
        descricoes: dict opcional codigo -> descricao longa.
        """
        descricoes = descricoes or {}
        novos = []
        for codigo, nome in de_para:
            codigo = str(codigo).strip()
            nome = str(nome).strip()
            if not codigo or not nome:
                continue
            novos.append(CatalogoPerfil(
                sistema=sistema.value,
                codigo=codigo,
                nome=nome,
                familia=familia_do_nome(nome),
                descricao=descricoes.get(codigo),
                arquivo_origem=arquivo_origem,
                dt_importacao=datetime.now(),
            ))

        with self._conexao.sessao() as sessao:
            removidos = (
                sessao.query(CatalogoPerfil)
                .filter_by(sistema=sistema.value)
                .delete()
            )
            sessao.flush()
            for cp in novos:
                sessao.add(cp)
            sessao.commit()

        logger.info(
            f"Catalogo {sistema.value}: {removidos} entradas antigas removidas, "
            f"{len(novos)} gravadas."
        )
        return len(novos)

    # ------------------------------------------------------------------
    # Leitura
    # ------------------------------------------------------------------
    def obter_mapa(self, sistema: Sistema) -> Dict[str, str]:
        """codigo -> nome para todos os perfis de um sistema. Dict vazio
        se nao ha catalogo desse sistema (sistema com nome direto no extrato)."""
        with self._conexao.sessao() as sessao:
            rows = sessao.query(CatalogoPerfil).filter_by(sistema=sistema.value).all()
            return {r.codigo: r.nome for r in rows}

    def obter_familia(self, sistema: Sistema, codigo: str) -> Optional[str]:
        with self._conexao.sessao() as sessao:
            row = sessao.query(CatalogoPerfil).filter_by(
                sistema=sistema.value, codigo=str(codigo).strip()).first()
            return row.familia if row else None

    def obter_todos(self) -> List[CatalogoPerfil]:
        with self._conexao.sessao() as sessao:
            return sessao.query(CatalogoPerfil).all()
