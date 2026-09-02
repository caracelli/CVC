from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
from loguru import logger

from .leitor_base import LeitorArquivoBase, ler_tabela
from .leitor_matriz_franqueado import eh_matriz_franqueado
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
    "ORACLE EBS":               Sistema.ORACLE_EBS,
    "ORACLE_EBS":               Sistema.ORACLE_EBS,
}

# Candidatos para a coluna de cost center (em ordem de preferência)
_CANDIDATOS_CC = ["CCUSTO", "CENTRO DE CUSTO", "CENTRO_DE_CUSTO"]

# Candidatos para a coluna de cargo/função
_CANDIDATOS_CARGO = ["CARGO", "FUNÇÃO", "FUNCAO", "DESCRICAO CARGO", "FUNÇÃO DO CARGO"]

# Candidatos para a coluna de perfil esperado (SYSTUR/SIGOT/SICA: 'PERFIL ACESSO';
# Oracle EBS: 'RESPONSABILIDADE'). Ordem = preferência.
_CANDIDATOS_PERFIL = ["PERFIL ACESSO", "RESPONSABILIDADE", "PERFIL"]

# Coluna de acesso manual (presente na matriz SYSTUR)
_COL_ACESSO_MANUAL = "ACESSO MANUAL"


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


def _resolver_col_perfil(colunas: List[str]) -> Optional[str]:
    colunas_upper = {c.upper(): c for c in colunas}
    for candidato in _CANDIDATOS_PERFIL:
        if candidato.upper() in colunas_upper:
            return colunas_upper[candidato.upper()]
    return None


def _ler_df_perfis(arquivo: Path) -> pd.DataFrame:
    # XLSX/XLS ou CSV. Cabecalho normalmente na 1a linha (SYSTUR/SIGOT/SICA),
    # mas algumas matrizes (Oracle EBS) trazem uma linha de titulo antes — entao
    # se nao acharmos cargo/perfil no header=0, tentamos header=1 (so XLSX).
    df = _normalizar_colunas(ler_tabela(arquivo, dtype=str))
    if (_resolver_col_cargo(list(df.columns)) is None
            and _resolver_col_perfil(list(df.columns)) is None
            and arquivo.suffix.lower() in (".xlsx", ".xls")):
        df2 = _normalizar_colunas(ler_tabela(arquivo, dtype=str, header=1))
        if _resolver_col_cargo(list(df2.columns)) or _resolver_col_perfil(list(df2.columns)):
            return df2
    return df


def _ler_df_org(arquivo: Path) -> pd.DataFrame:
    # No XLSX a linha 0 e' titulo fundido e o cabecalho real esta' na linha 1;
    # no CSV (export) o cabecalho ja' vem na 1a linha. Mantemos essa distincao.
    header = 1 if arquivo.suffix.lower() in (".xlsx", ".xls") else 0
    return _normalizar_colunas(ler_tabela(arquivo, dtype=str, header=header))


class LeitorMatrizPerfis(LeitorArquivoBase):
    """Lê arquivos PERFIS_SISTEMAS — um arquivo por sistema, sistema extraído do nome."""

    def __init__(
        self,
        pasta_processados: Optional[str] = None,
        pasta_erros: Optional[str] = None,
    ):
        super().__init__(pasta_processados, pasta_erros)

    def ler(self, pasta: str, sistemas_em_escopo: Optional[set] = None
            ) -> Tuple[List[PerfilEsperado], List[str]]:
        """sistemas_em_escopo: se informado, so processa matrizes desses
        sistemas. Os demais sao ignorados em silencio (sem mover, sem log
        visivel) — assim sistemas ainda nao implementados nao geram falsa
        sensacao de processamento. None = processa todos (compat)."""
        perfis: List[PerfilEsperado] = []
        processados: List[str] = []

        for arquivo in self.listar_arquivos(pasta):
            sistema = _extrair_sistema(arquivo.name)
            if not sistema:
                logger.warning(f"Matriz Perfis: sistema não identificado no nome '{arquivo.name}' — ignorado.")
                continue

            if sistemas_em_escopo is not None and sistema not in sistemas_em_escopo:
                # Sistema fora do escopo desta fase: nao loga (debug fica abaixo
                # do nivel INFO da UI) e nao move o arquivo — fica pronto pra
                # quando o sistema entrar em escopo.
                logger.debug(
                    f"Matriz Perfis [{sistema.value}]: fora de escopo nesta fase "
                    f"— ignorada ('{arquivo.name}')."
                )
                continue

            try:
                df = _ler_df_perfis(arquivo).dropna(how="all")
                col_cc = _resolver_col_cc(list(df.columns))
                col_cargo = _resolver_col_cargo(list(df.columns))
                col_perfil = _resolver_col_perfil(list(df.columns))
                total_antes = len(perfis)

                # A matriz do FRANQUEADO mora na mesma pasta e casa por
                # cargo x tipo de atendimento x tipo de loja — nao tem centro de
                # custo. Ela e' de outro leitor (LeitorMatrizFranqueado): deixa
                # passar sem tocar. Sem isto o arquivo ia para ERROS na fase de
                # importacao e a regra do franqueado, que roda depois, nao
                # achava mais nada — a matriz sumia da ENTRADA no 1o processo.
                if eh_matriz_franqueado(list(df.columns)):
                    logger.debug(
                        f"Matriz Perfis: '{arquivo.name}' e' a matriz do "
                        f"franqueado — lida pelo leitor proprio."
                    )
                    continue

                if not col_cc or not col_perfil:
                    logger.warning(
                        f"Matriz Perfis '{arquivo.name}': colunas esperadas não encontradas. "
                        f"Disponíveis: {list(df.columns)}"
                    )
                    self.mover_para_erros(arquivo, "Colunas não encontradas")
                    continue

                col_manual = _COL_ACESSO_MANUAL if _COL_ACESSO_MANUAL in df.columns else None

                for _, row in df.iterrows():
                    cc = str(row.get(col_cc, "")).strip()
                    perfil = str(row.get(col_perfil, "")).strip()
                    if not (cc and perfil):
                        continue
                    cargo_desc = str(row.get(col_cargo, "")).strip() if col_cargo else ""
                    manual_raw = str(row.get(col_manual, "")).strip().upper() if col_manual else ""
                    perfis.append(PerfilEsperado(
                        cargo_codigo=cc,
                        sistema=sistema,
                        perfil=perfil,
                        cargo_descricao=cargo_desc,
                        acesso_manual=(manual_raw == "SIM"),
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

    _CAND_CC_COD  = ["CÓDIGO DO CENTRO DE CUSTO", "CODIGO DO CENTRO DE CUSTO", "CCUSTO", "CENTRO DE CUSTO"]
    _CAND_CC_NOME = ["NOME DO CENTRO DE CUSTO", "NOME CENTRO DE CUSTO"]
    _CAND_GESTOR  = ["NOME GESTOR", "NOME DO GESTOR", "GESTOR"]
    _CAND_FUNCAO  = ["FUNÇÃO", "FUNCAO"]
    _CAND_SISTEMA = ["SISTEMAS", "SISTEMA"]
    _CAND_PERFIL  = ["PERFIS", "PERFIL ACESSO", "PERFIL"]

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
        """Retorna lista de dicts com chaves: cc, cc_nome, funcao, sistema, perfil."""
        registros: List[dict] = []
        processados: List[str] = []

        for arquivo in self.listar_arquivos(pasta):
            try:
                df = _ler_df_org(arquivo).dropna(how="all")
                cols = list(df.columns)
                col_cc      = self._resolver(cols, self._CAND_CC_COD)
                col_nome    = self._resolver(cols, self._CAND_CC_NOME)
                col_gestor  = self._resolver(cols, self._CAND_GESTOR)
                col_funcao  = self._resolver(cols, self._CAND_FUNCAO)
                col_sistema = self._resolver(cols, self._CAND_SISTEMA)
                col_perfil  = self._resolver(cols, self._CAND_PERFIL)
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
                    sistema_raw = str(row.get(col_sistema, "")).strip() if col_sistema else ""
                    perfil_raw  = str(row.get(col_perfil, "")).strip() if col_perfil else ""
                    if not (sistema_raw and perfil_raw and sistema_raw.upper() not in ("NAN", "") and perfil_raw.upper() not in ("NAN", "")):
                        continue
                    registros.append({
                        "cc":      cc,
                        "cc_nome": str(row.get(col_nome, "")).strip() if col_nome else "",
                        "gestor":  str(row.get(col_gestor, "")).strip() if col_gestor else "",
                        "funcao":  str(row.get(col_funcao, "")).strip() if col_funcao else "",
                        "sistema": sistema_raw,
                        "perfil":  perfil_raw,
                    })

                self.mover_para_processados(arquivo)
                processados.append(arquivo.name)
                logger.success(f"Matriz CCO/CSC: {len(registros) - total_antes} mapeamentos de '{arquivo.name}'")

            except Exception as e:
                self.mover_para_erros(arquivo, str(e))

        # Deduplica por (cc, gestor, funcao, sistema, perfil) — arquivos idênticos com nomes diferentes
        seen: set = set()
        registros_unicos: List[dict] = []
        for r in registros:
            key = (r["cc"], r.get("gestor", ""), r["funcao"], r["sistema"], r["perfil"])
            if key not in seen:
                seen.add(key)
                registros_unicos.append(r)
        removidos = len(registros) - len(registros_unicos)
        if removidos:
            logger.warning(f"Matriz CCO/CSC: {removidos} registros duplicados removidos.")
        return registros_unicos, processados
