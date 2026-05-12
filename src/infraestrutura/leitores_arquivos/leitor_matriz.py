from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
from loguru import logger

from .leitor_base import LeitorArquivoBase
from dominio.entidades.perfil_esperado import PerfilEsperado
from dominio.objetos_valor.sistema import Sistema

# Mapeamento de fragmentos do nome do arquivo → Sistema
_SISTEMA_POR_NOME: Dict[str, Sistema] = {
    "SIGOT":                    Sistema.SIGOT,
    "SICA ESFERA":              Sistema.SICA_ESFERA,
    "SICA_ESFERA":              Sistema.SICA_ESFERA,
    "SICA RA":                  Sistema.SICA_RA,
    "SICA_RA":                  Sistema.SICA_RA,
    "SYSTUR":                   Sistema.SYSTUR,
    "IC INTEGRADOR CONTABIL":   Sistema.IC_INTEGRADOR_CONTABIL,
    "IC_INTEGRADOR_CONTABIL":   Sistema.IC_INTEGRADOR_CONTABIL,
}

# Candidatos para a coluna de cost center (em ordem de preferência)
_CANDIDATOS_CC = ["CCUSTO", "CENTRO DE CUSTO", "CENTRO_DE_CUSTO"]

# Candidatos para a coluna de cargo/função
_CANDIDATOS_CARGO = ["CARGO", "FUNÇÃO", "FUNCAO", "DESCRICAO CARGO", "FUNÇÃO DO CARGO"]

# Coluna de perfil esperado
_COL_PERFIL = "PERFIL ACESSO"


def _extrair_sistema(nome_arquivo: str) -> Optional[Sistema]:
    nome = nome_arquivo.upper()
    for chave, sistema in _SISTEMA_POR_NOME.items():
        if chave in nome:
            return sistema
    return None


def _normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _resolver_col_cc(colunas: List[str]) -> Optional[str]:
    colunas_upper = {c.upper(): c for c in colunas}
    for candidato in _CANDIDATOS_CC:
        if candidato in colunas_upper:
            return colunas_upper[candidato]
    return None


def _resolver_col_cargo(colunas: List[str]) -> Optional[str]:
    colunas_upper = {c.upper(): c for c in colunas}
    for candidato in _CANDIDATOS_CARGO:
        if candidato.upper() in colunas_upper:
            return colunas_upper[candidato.upper()]
    return None


def _ler_df_perfis(arquivo: Path) -> pd.DataFrame:
    if arquivo.suffix.lower() in (".xlsx", ".xls"):
        return _normalizar_colunas(pd.read_excel(arquivo, dtype=str))
    return _normalizar_colunas(pd.read_csv(arquivo, sep=";", dtype=str, on_bad_lines="skip"))


def _ler_df_org(arquivo: Path) -> pd.DataFrame:
    if arquivo.suffix.lower() in (".xlsx", ".xls"):
        # Linha 0 é título fundido; linha 1 contém os cabeçalhos reais
        df = pd.read_excel(arquivo, dtype=str, header=1)
    else:
        df = pd.read_csv(arquivo, sep=";", dtype=str, on_bad_lines="skip")
    return _normalizar_colunas(df)


class LeitorMatrizPerfis(LeitorArquivoBase):
    """Lê arquivos PERFIS_SISTEMAS — um arquivo por sistema, sistema extraído do nome."""

    def __init__(
        self,
        pasta_processados: Optional[str] = None,
        pasta_erros: Optional[str] = None,
    ):
        super().__init__(pasta_processados, pasta_erros)

    def ler(self, pasta: str) -> Tuple[List[PerfilEsperado], List[str]]:
        perfis: List[PerfilEsperado] = []
        processados: List[str] = []

        for arquivo in self.listar_arquivos(pasta):
            sistema = _extrair_sistema(arquivo.name)
            if not sistema:
                logger.warning(f"Matriz Perfis: sistema não identificado no nome '{arquivo.name}' — ignorado.")
                continue

            try:
                df = _ler_df_perfis(arquivo).dropna(how="all")
                col_cc = _resolver_col_cc(list(df.columns))
                col_cargo = _resolver_col_cargo(list(df.columns))
                total_antes = len(perfis)

                if not col_cc or _COL_PERFIL not in df.columns:
                    logger.warning(
                        f"Matriz Perfis '{arquivo.name}': colunas esperadas não encontradas. "
                        f"Disponíveis: {list(df.columns)}"
                    )
                    self.mover_para_erros(arquivo, "Colunas não encontradas")
                    continue

                for _, row in df.iterrows():
                    cc = str(row.get(col_cc, "")).strip()
                    perfil = str(row.get(_COL_PERFIL, "")).strip()
                    if not (cc and perfil):
                        continue
                    cargo_desc = str(row.get(col_cargo, "")).strip() if col_cargo else ""
                    perfis.append(PerfilEsperado(
                        cargo_codigo=cc,
                        sistema=sistema,
                        perfil=perfil,
                        cargo_descricao=cargo_desc,
                    ))

                self.mover_para_processados(arquivo)
                processados.append(arquivo.name)
                logger.success(
                    f"Matriz Perfis [{sistema.value}]: "
                    f"{len(perfis) - total_antes} registros de '{arquivo.name}'"
                )

            except Exception as e:
                self.mover_para_erros(arquivo, str(e))

        return perfis, processados


class LeitorMatrizOrganizacional(LeitorArquivoBase):
    """Lê arquivo de mapeamento CCO/CSC — cabeçalhos reais na linha 1 do Excel."""

    # Candidatos para cada coluna relevante
    _CAND_CC_COD = ["CÓDIGO DO CENTRO DE CUSTO", "CODIGO DO CENTRO DE CUSTO", "CCUSTO", "CENTRO DE CUSTO"]
    _CAND_CC_NOME = ["NOME DO CENTRO DE CUSTO", "NOME CENTRO DE CUSTO"]
    _CAND_FUNCAO = ["FUNÇÃO", "FUNCAO", "FUNÇÃO"]

    def __init__(
        self,
        pasta_processados: Optional[str] = None,
        pasta_erros: Optional[str] = None,
    ):
        super().__init__(pasta_processados, pasta_erros)

    def _resolver(self, colunas: List[str], candidatos: List[str]) -> Optional[str]:
        upper = {c.upper(): c for c in colunas}
        for cand in candidatos:
            if cand.upper() in upper:
                return upper[cand.upper()]
        return None

    def ler(self, pasta: str) -> Tuple[List[dict], List[str]]:
        registros: List[dict] = []
        processados: List[str] = []

        for arquivo in self.listar_arquivos(pasta):
            try:
                df = _ler_df_org(arquivo).dropna(how="all")
                cols = list(df.columns)
                col_cc = self._resolver(cols, self._CAND_CC_COD)
                col_nome = self._resolver(cols, self._CAND_CC_NOME)
                col_funcao = self._resolver(cols, self._CAND_FUNCAO)
                total_antes = len(registros)

                if not col_cc:
                    logger.warning(
                        f"Matriz Org '{arquivo.name}': coluna de centro de custo não encontrada. "
                        f"Disponíveis: {cols}"
                    )
                    self.mover_para_erros(arquivo, "Coluna de centro de custo não encontrada")
                    continue

                for _, row in df.iterrows():
                    cc = str(row.get(col_cc, "")).strip()
                    if not cc or cc.upper() in ("NAN", ""):
                        continue
                    registros.append({
                        "cargo_codigo": cc,
                        "cargo_descricao": str(row.get(col_nome, "")).strip() if col_nome else "",
                        "departamento": str(row.get(col_funcao, "")).strip() if col_funcao else "",
                        "centro_custo": cc,
                    })

                self.mover_para_processados(arquivo)
                processados.append(arquivo.name)
                logger.success(f"Matriz Org: {len(registros) - total_antes} centros de custo de '{arquivo.name}'")

            except Exception as e:
                self.mover_para_erros(arquivo, str(e))

        return registros, processados
