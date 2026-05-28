"""Leitor do SIG — extrato matricial pivotado (X = acesso) + de-para de codigos.

Formato do extrato (1 aba, dinamica — sempre primeira; nome ja foi 'Select
tb_sys_sec_user' mas pode mudar se o cliente regenerar o export SQL):

    | LOGIN | NM_USER | STATUS | CPF | EMAIL | 1 | 10 | 11 | ... | 55106 |
    | john  | JOHN    | ATIVO  | ... | ...   |   | X  |    | ... |   X   |

5 colunas fixas + N colunas numericas (cada uma = um codigo de acesso do
tb_sys_sec_role). Celula 'X' = usuario tem aquele acesso.

Despivot: cada linha vira N PerfilAcesso (um por 'X'). Os codigos sao
traduzidos para nome legivel via catalogo (de-para no XLSX separado).
"""
import re
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

import pandas as pd
from loguru import logger

from .leitor_base import LeitorArquivoBase
from dominio.entidades.perfil_acesso import PerfilAcesso
from dominio.objetos_valor.sistema import Sistema
from dominio.servicos_dominio.servico_padronizacao import ServicoPadronizacao


# Colunas fixas do extrato SIG (case-insensitive, posicao matters menos)
_COLS_FIXAS = ("LOGIN", "NM_USER", "STATUS", "CPF", "EMAIL")

# Mapa de situacao do SIG. Hoje so vem 'ATIVO' no export, mas registramos
# previsao para 'INATIVO' caso futuro.
_MAPA_SITUACAO = {"ATIVO": "ATIVO", "INATIVO": "INATIVO"}


def _ler_primeira_aba_xlsx(arquivo: Path, dtype=str) -> pd.DataFrame:
    """Le sempre a PRIMEIRA aba. Nome real ('Select tb_sys_sec_user') pode
    mudar se o cliente regerar a query."""
    return pd.read_excel(arquivo, sheet_name=0, dtype=dtype)


class LeitorCatalogoSig(LeitorArquivoBase):
    """Le o de-para `ID -> NM_ROLE` do SIG (XLSX `ID_x_Perfis_SIG`).

    Espera 2 colunas (ID, NM_ROLE) na primeira aba. ID numerico, NM_ROLE
    snake_case ASCII.
    """

    def ler(self, arquivo: Path) -> Dict[str, str]:
        """Devolve {codigo_str: nome_str}. Codigo armazenado como string
        (consistente com a coluna do extrato e com catalogo_perfis)."""
        df = _ler_primeira_aba_xlsx(arquivo)
        if df.empty:
            logger.warning(f"De-para SIG vazio: {arquivo.name}")
            return {}
        # Identifica colunas com tolerancia a case (header real: 'ID', 'NM_ROLE')
        cols_norm = {c.strip().upper(): c for c in df.columns if c}
        col_id = cols_norm.get("ID")
        col_nome = cols_norm.get("NM_ROLE") or cols_norm.get("NOME") or cols_norm.get("PERFIL")
        if not col_id or not col_nome:
            raise ValueError(
                f"De-para SIG sem colunas esperadas (ID, NM_ROLE). "
                f"Colunas vistas: {list(df.columns)}"
            )
        mapa: Dict[str, str] = {}
        for _, row in df.iterrows():
            cod = row[col_id]
            nome = row[col_nome]
            if pd.isna(cod) or pd.isna(nome):
                continue
            cod_s = str(cod).strip()
            # numerico vindo do excel pode vir '15.0' — limpa
            if cod_s.endswith(".0"):
                cod_s = cod_s[:-2]
            mapa[cod_s] = str(nome).strip()
        logger.info(f"De-para SIG: {len(mapa)} codigos carregados de '{arquivo.name}'")
        return mapa

    def listar_arquivos_decrescente(self, pasta: str) -> List[Path]:
        """Pega os XLSX da pasta de de-para, mais recente primeiro."""
        return sorted(self.listar_arquivos(pasta), reverse=True)


class LeitorSig(LeitorArquivoBase):
    """Le o extrato matricial do SIG e despivota em uma lista de PerfilAcesso.

    Recebe o catalogo (id -> nome) ja resolvido para traduzir os codigos
    durante o despivot.
    """

    def __init__(self, catalogo: Dict[str, str],
                 pasta_processados: str = None,
                 pasta_erros: str = None):
        super().__init__(pasta_processados, pasta_erros)
        self._catalogo = catalogo or {}
        self._pad = ServicoPadronizacao()

    def listar_ordenado(self, pasta: str) -> List[Path]:
        """Mesma logica do LeitorSistema: ordena por data no nome (se houver)."""
        from .leitor_sistema import chave_data_arquivo
        return sorted(self.listar_arquivos(pasta), key=lambda f: chave_data_arquivo(f.name))

    def ler_um(self, arquivo: Path) -> List[PerfilAcesso]:
        df = _ler_primeira_aba_xlsx(arquivo).dropna(how="all")
        if df.empty:
            return []

        # Identifica colunas fixas (case-insensitive) e codigos (resto)
        cols_norm = {c.strip().upper(): c for c in df.columns if c}
        idx_login = cols_norm.get("LOGIN")
        idx_nm = cols_norm.get("NM_USER") or cols_norm.get("NOME")
        idx_status = cols_norm.get("STATUS") or cols_norm.get("SITUACAO")
        idx_cpf = cols_norm.get("CPF")
        idx_email = cols_norm.get("EMAIL") or cols_norm.get("E-MAIL")

        if not idx_login:
            raise ValueError(f"SIG: coluna LOGIN nao encontrada em {arquivo.name}")

        fixas = {idx_login, idx_nm, idx_status, idx_cpf, idx_email} - {None}
        cols_codigo = [c for c in df.columns if c and c not in fixas]

        # Sem codigos = nao e' SIG matricial valido
        if not cols_codigo:
            raise ValueError(
                f"SIG: nenhuma coluna de codigo encontrada em {arquivo.name} "
                f"(esperado: 5 colunas fixas + N codigos numericos)"
            )

        def _cell(idx) -> str:
            """Le celula com tolerancia a NaN/None do pandas."""
            if not idx:
                return ""
            v = row.get(idx)
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return ""
            s = str(v).strip()
            return "" if s.lower() == "nan" else s

        sem_traducao = set()
        perfis: List[PerfilAcesso] = []
        for _, row in df.iterrows():
            login = _cell(idx_login)
            if not login:
                continue
            nome = self._pad.normalizar_nome(_cell(idx_nm))
            cpf = self._pad.normalizar_cpf(_cell(idx_cpf))
            email = _cell(idx_email) or None
            status = _MAPA_SITUACAO.get(_cell(idx_status).upper() or "ATIVO", "ATIVO")

            for col in cols_codigo:
                val = row.get(col)
                if not self._marcado(val):
                    continue
                cod = str(col).strip()
                if cod.endswith(".0"):
                    cod = cod[:-2]
                nome_perfil = self._catalogo.get(cod)
                if nome_perfil is None:
                    sem_traducao.add(cod)
                    # Sem traducao: usa codigo como fallback (auditavel)
                    nome_perfil = cod
                perfis.append(PerfilAcesso(
                    usuario=login,
                    nome_usuario=nome,
                    sistema=Sistema.SIG,
                    perfil=nome_perfil,
                    situacao=status,
                    cpf=cpf or None,
                    email=email,
                ))

        if sem_traducao:
            amostra = sorted(sem_traducao)[:5]
            logger.warning(
                f"SIG: {len(sem_traducao)} codigo(s) sem traducao no de-para "
                f"(usando codigo cru). Exemplos: {amostra}")
        return perfis

    @staticmethod
    def _marcado(val) -> bool:
        """Aceita 'X', 'x', '1', True como marcado. Vazio/NaN/'0' = nao."""
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return False
        s = str(val).strip().upper()
        return s in ("X", "1", "TRUE", "Y", "S", "SIM")
