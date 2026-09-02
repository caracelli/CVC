# -*- coding: utf-8 -*-
"""Matriz de perfil do FRANQUEADO (`MATRIZ DE PERFIL DE ACESSO SYSTUR - LOJAS`).

Pedido da area em 31/08/2026: *"para franqueado nao tem a questao de espelho; o
perfil e' uma validacao entre cargo + tipo de loja"*.

O arquivo tem DUAS secoes e so' a primeira e' matriz de verdade:

    ACESSO MANUAL | CARGO | TIPO DE ATENDIMENTO | TIPO DE LOJA | PERFIL ACESSO
    ...34 linhas...

    Perfis Execeções: *
    *Os Perfis abaixo devem ser liberado para os usuarios somente se tiver
     aprovacao da area de Governanca de Seguranca da Informacao
    ACESSO MANUAL | CARGO | ... (o cabecalho se REPETE)
    ...3 linhas...

⚠️ Ler o arquivo inteiro em linha reta carrega `FRANQUEADOS_VC`,
`GERENTE_GERAL_MASTER` e `MASTER_FRANQUEADO` como perfil ESPERADO — e o painel
passaria a MANDAR conceder MASTER_FRANQUEADO a todo gerente de franquia. Por
isso o corte no marcador de excecao e' parte da leitura, nao um detalhe.
"""
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

import pandas as pd
from loguru import logger

from .leitor_base import LeitorArquivoBase, ler_tabela, normalizar_nome_coluna

COL_CARGO = "CARGO"
COL_ATENDIMENTO = "TIPO DE ATENDIMENTO"
COL_LOJA = "TIPO DE LOJA"
COL_PERFIL = "PERFIL ACESSO"
COL_MANUAL = "ACESSO MANUAL"

_COLUNAS = (COL_MANUAL, COL_CARGO, COL_ATENDIMENTO, COL_LOJA, COL_PERFIL)

# O que marca o fim da matriz e o inicio do bloco de excecao.
#
# Nao da' para procurar "EXCECOES": o arquivo do cliente esta escrito
# "Perfis Execeções" — com o E e o X trocados. Comparar so' letras (sem acento,
# sem caixa, sem pontuacao) e aceitar o prefixo "PERFISEX" pega as duas grafias.
# A frase seguinte cita a Governanca de Seguranca da Informacao e serve de
# segundo sinal, caso o titulo mude.
_MARCAS_EXCECAO = ("PERFISEX", "GOVERNANC")


def _so_letras(v) -> str:
    return "".join(c for c in normalizar_nome_coluna(v) if c.isalpha())


def _marca_excecao(celulas) -> bool:
    for c in celulas:
        compacto = _so_letras(c)
        if any(m in compacto for m in _MARCAS_EXCECAO):
            return True
    return False


def _norm(v) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    return "" if s.lower() == "nan" else s


def eh_matriz_franqueado(colunas: Sequence[str]) -> bool:
    """True quando o arquivo e' a matriz do franqueado (cargo x tipo de
    atendimento x tipo de loja) e NAO uma matriz de sistema por centro de custo.

    Serve para rotear: `LeitorMatrizPerfis` deixa este arquivo passar em vez de
    manda-lo para ERROS por "colunas nao encontradas".
    """
    canon = {normalizar_nome_coluna(c) for c in colunas}
    return (normalizar_nome_coluna(COL_LOJA) in canon
            and normalizar_nome_coluna(COL_ATENDIMENTO) in canon
            and normalizar_nome_coluna(COL_PERFIL) in canon)


class RegraFranqueado:
    """Uma linha da matriz. `excecao=True` = so' com aval da Governanca de SI."""

    __slots__ = ("cargo", "atendimento", "loja", "perfil", "acesso_manual", "excecao")

    def __init__(self, cargo: str, atendimento: str, loja: str, perfil: str,
                 acesso_manual: bool = False, excecao: bool = False):
        self.cargo = cargo
        self.atendimento = atendimento
        self.loja = loja
        self.perfil = perfil
        self.acesso_manual = acesso_manual
        self.excecao = excecao

    def __repr__(self):
        return ("RegraFranqueado(%r, %r, %r, %r, manual=%r, excecao=%r)"
                % (self.cargo, self.atendimento, self.loja, self.perfil,
                   self.acesso_manual, self.excecao))

    def __eq__(self, o):
        return isinstance(o, RegraFranqueado) and self._k() == o._k()

    def __hash__(self):
        return hash(self._k())

    def _k(self):
        return (self.cargo, self.atendimento, self.loja, self.perfil,
                self.acesso_manual, self.excecao)


class LeitorMatrizFranqueado(LeitorArquivoBase):
    """Le a matriz do franqueado de uma pasta (a mesma das outras matrizes)."""

    def ler_um(self, arquivo: Path) -> List[RegraFranqueado]:
        df = ler_tabela(arquivo, dtype=str, colunas_esperadas=list(_COLUNAS))
        df.columns = [str(c).strip() for c in df.columns]
        mapa = {normalizar_nome_coluna(c): c for c in df.columns}

        def col(nome) -> Optional[str]:
            return mapa.get(normalizar_nome_coluna(nome))

        c_cargo, c_perfil = col(COL_CARGO), col(COL_PERFIL)
        if not c_cargo or not c_perfil:
            raise ValueError("matriz de franqueado sem CARGO/PERFIL ACESSO")
        c_atend, c_loja, c_manual = col(COL_ATENDIMENTO), col(COL_LOJA), col(COL_MANUAL)

        regras: List[RegraFranqueado] = []
        em_excecao = False
        for _, row in df.iterrows():
            celulas = [_norm(v) for v in row.values]
            if not any(celulas):
                continue
            # marcador do bloco de excecao — vale para o resto do arquivo
            if _marca_excecao(celulas):
                em_excecao = True
                continue
            cargo = _norm(row.get(c_cargo))
            perfil = _norm(row.get(c_perfil))
            if not cargo or not perfil:
                continue
            # o cabecalho se REPETE dentro do bloco de excecao
            if normalizar_nome_coluna(cargo) == normalizar_nome_coluna(COL_CARGO):
                continue
            regras.append(RegraFranqueado(
                cargo=cargo,
                atendimento=_norm(row.get(c_atend)) if c_atend else "",
                loja=_norm(row.get(c_loja)) if c_loja else "",
                perfil=perfil,
                acesso_manual=(normalizar_nome_coluna(_norm(row.get(c_manual))) == "SIM"
                               if c_manual else False),
                excecao=em_excecao,
            ))
        return regras

    def ler(self, pasta: str) -> Tuple[List[RegraFranqueado], List[str]]:
        """Varre a pasta e devolve (regras, arquivos lidos). Arquivo que nao for
        a matriz do franqueado e' ignorado em silencio (e' de outro leitor)."""
        regras: List[RegraFranqueado] = []
        lidos: List[str] = []
        for arquivo in self.listar_arquivos(pasta):
            try:
                df = ler_tabela(arquivo, dtype=str, colunas_esperadas=list(_COLUNAS))
            except Exception as e:
                logger.debug(f"Matriz franqueado: '{arquivo.name}' nao lido ({e!r})")
                continue
            if not eh_matriz_franqueado(list(df.columns)):
                continue
            try:
                novas = self.ler_um(arquivo)
            except Exception as e:
                logger.error(f"Matriz de franqueado '{arquivo.name}': {e!r}")
                self.mover_para_erros(arquivo, str(e))
                continue
            regras.extend(novas)
            lidos.append(arquivo.name)
            n_exc = sum(1 for r in novas if r.excecao)
            logger.info(
                f"Matriz de franqueado '{arquivo.name}': {len(novas) - n_exc} regra(s) "
                f"+ {n_exc} perfil(is) de EXCECAO (Governanca de SI)."
            )
        return regras, lidos


# ----------------------------------------------------------------------
# Indices derivados — o que a validacao consome
# ----------------------------------------------------------------------

def cargos_por_perfil(regras: Sequence[RegraFranqueado]) -> Dict[str, Set[str]]:
    """perfil normalizado -> cargos (normalizados) que a matriz autoriza.

    E' o indice AO CONTRARIO, e e' o unico que fecha com o dado que temos:
    TIPO DE LOJA e TIPO DE ATENDIMENTO nao existem no cadastro (medido em
    01/09: `rh_ativos.local_trabalho` e `acessos_sistemas.filial` 100% vazios),
    entao nao da' para dizer QUAL perfil a pessoa deveria ter. Da' para dizer,
    do perfil que ela TEM, se o CARGO dela o justifica.
    """
    fora: Dict[str, Set[str]] = {}
    for r in regras:
        if r.excecao:
            continue
        fora.setdefault(normalizar_nome_coluna(r.perfil), set()).add(
            normalizar_nome_coluna(r.cargo))
    return fora


def perfis_de_excecao(regras: Sequence[RegraFranqueado]) -> Set[str]:
    """Perfis que so' podem ser liberados com aval da Governanca de SI."""
    return {normalizar_nome_coluna(r.perfil) for r in regras if r.excecao}
