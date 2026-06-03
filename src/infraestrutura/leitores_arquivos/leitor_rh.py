import re
from datetime import date
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd
from loguru import logger

from .leitor_base import LeitorArquivoBase
from dominio.entidades.funcionario_ativo import FuncionarioAtivo
from dominio.entidades.funcionario_desligado import FuncionarioDesligado
from dominio.objetos_valor.cargo import Cargo

# Mapeamento flexível de colunas — ordem de prioridade
_COLUNAS = {
    "matricula":           ["Matricula", "MATRICULA", "Matrícula"],
    "nome":                ["Nome da Pessoa", "NOME", "Nome"],
    "cpf":                 ["Numero do CPF", "Número do CPF", "CPF", "NUMERO_CPF"],
    "cargo_codigo":        ["Código do Cargo", "Codigo do Cargo", "CARGO_CODIGO", "CodCargo"],
    "cargo_descricao":     ["Descritivo do Cargo", "CARGO_DESCRICAO", "Cargo", "DescCargo"],
    "centro_custo_codigo": ["Código do Centro de Custo", "Codigo do Centro de Custo", "CENTRO_CUSTO"],
    "centro_custo_nome":   ["Nome do Centro de Custo", "NOME_CENTRO_CUSTO", "CentroCusto"],
    "departamento":        ["Diretoria Executiva", "DEPARTAMENTO", "Departamento"],
    "data_admissao":       ["Data de Admissão", "Data de Admissao", "DATA_ADMISSAO", "DtAdmissao"],
    "email":               ["Email", "EMAIL", "E-mail"],
    "situacao":            ["Status do Funcionário", "Status do Funcionario", "SITUACAO", "Status"],
    "empresa":             ["Razão Social Empresa/Filial", "Razao Social Empresa/Filial", "EMPRESA"],
    "local_trabalho":      ["Local de Trabalho", "LOCAL_TRABALHO"],
    "data_desligamento":   ["Data do Desligamento", "Data de Desligamento", "DATA_DESLIGAMENTO"],
}


def _resolver_coluna(df: pd.DataFrame, chave: str) -> Optional[str]:
    for candidato in _COLUNAS.get(chave, []):
        if candidato in df.columns:
            return candidato
    return None


def _valor(row: pd.Series, col: Optional[str]) -> str:
    if not col or col not in row.index:
        return ""
    val = row[col]
    return "" if pd.isna(val) else str(val).strip()


def _parse_data(valor: str) -> Optional[date]:
    if not valor:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return pd.to_datetime(valor, format=fmt).date()
        except Exception:
            continue
    try:
        return pd.to_datetime(valor, dayfirst=True).date()
    except Exception:
        return None


def _ler_df(arquivo: Path, encoding: str, separador: str = ";") -> pd.DataFrame:
    if arquivo.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(arquivo, dtype=str)
    return pd.read_csv(
        arquivo, sep=separador, dtype=str,
        encoding=encoding, on_bad_lines="skip",
    )


# ---- Terceiros (layout QuickReport: EMPRESA FORNECEDORA / CNPJ / NOME DO
#      SUPERVISOR / NOME / CODIGO / STATUS RH). Cabecalho na 2a linha. -------
_TERC_COLS = {
    "empresa":    ["EMPRESA FORNECEDORA"],
    "cnpj":       ["CNPJ"],
    "supervisor": ["NOME DO SUPERVISOR", "SUPERVISOR"],
    "nome":       ["NOME"],
    "codigo":     ["CÓDIGO", "CODIGO"],
    "status":     ["STATUS RH", "STATUS"],
}


def _cols_upper(df: pd.DataFrame) -> set:
    return {str(c).strip().upper() for c in df.columns}


def _eh_terceiro(df: pd.DataFrame) -> bool:
    up = _cols_upper(df)
    return "EMPRESA FORNECEDORA" in up or "STATUS RH" in up


def _tem_matricula_clt(df: pd.DataFrame) -> bool:
    up = _cols_upper(df)
    return bool({"MATRICULA", "MATRÍCULA"} & up)


def _resolver_terc(df: pd.DataFrame, chave: str) -> Optional[str]:
    up = {str(c).strip().upper(): c for c in df.columns}
    for cand in _TERC_COLS.get(chave, []):
        if cand.upper() in up:
            return up[cand.upper()]
    return None


def _digitos(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def _cpf_valido(c: str) -> bool:
    if len(c) != 11 or len(set(c)) == 1:
        return False
    for i in (9, 10):
        soma = sum(int(c[j]) * ((i + 1) - j) for j in range(i))
        d = (soma * 10) % 11
        d = 0 if d == 10 else d
        if d != int(c[i]):
            return False
    return True


def _cpf_de_codigo(cod: str) -> str:
    """CODIGO do terceiro e' majoritariamente CPF salvo como numero (perde
    zeros a esquerda). Faz zfill(11) e valida; se nao bater, devolve os
    digitos crus (cai no matching residual 'sem CPF')."""
    d = _digitos(cod)
    if not d:
        return ""
    p = d.zfill(11)
    return p if (len(d) <= 11 and _cpf_valido(p)) else d


def _norm_nome(s: str) -> str:
    # remove espaco nao-quebravel (\xa0) e normaliza espacos
    return " ".join((s or "").replace("\xa0", " ").split())


class LeitorRh(LeitorArquivoBase):

    def __init__(self, separador: str = ";", pasta_processados: str = None,
                 pasta_erros: str = None, processar_terceiros: bool = True):
        super().__init__(pasta_processados, pasta_erros)
        self._separador = separador
        self._processar_terceiros = processar_terceiros

    def ler_ativos(self, pasta: str) -> Tuple[List[FuncionarioAtivo], List[str]]:
        """Le os arquivos da pasta de ATIVOS. Roteia por layout: arquivo de
        terceiros (EMPRESA FORNECEDORA / STATUS RH) vira FuncionarioAtivo com
        tipo_vinculo=TERCEIRO; o demais segue como CLT/proprio."""
        ativos: List[FuncionarioAtivo] = []
        processados: List[str] = []

        for arquivo in self.listar_arquivos(pasta):
            try:
                enc = self.detectar_encoding(arquivo) if arquivo.suffix.lower() == ".csv" else "utf-8"
                df, tipo = self._carregar_df_rh(arquivo, enc)
                if tipo == "TERCEIRO" and not self._processar_terceiros:
                    # Escopo da fase: terceiros ficam fora (regra de espelho
                    # ainda nao definida). Nao importa nem move o arquivo.
                    logger.info(
                        f"Terceiro fora de escopo nesta fase — ignorado ('{arquivo.name}').")
                    continue
                novos = (self._parse_terceiros(df) if tipo == "TERCEIRO"
                         else self._parse_clt(df))
                ativos.extend(novos)

                self.mover_para_processados(arquivo)
                processados.append(arquivo.name)
                logger.success(f"RH Ativos [{tipo}]: {len(novos)} registros de '{arquivo.name}'")

            except Exception as e:
                self.mover_para_erros(arquivo, str(e))

        return ativos, processados

    def _carregar_df_rh(self, arquivo: Path, enc: str) -> Tuple[pd.DataFrame, str]:
        """Devolve (df, tipo) onde tipo e' 'TERCEIRO' ou 'FUNCIONARIO'.
        O QuickReport de terceiros tem o cabecalho na 2a linha (1a em branco),
        entao se a leitura padrao nao reconhecer nem terceiro nem CLT, tenta
        reler o xlsx com header=1."""
        df = _ler_df(arquivo, enc, self._separador)
        if _eh_terceiro(df):
            return df, "TERCEIRO"
        if _tem_matricula_clt(df):
            return df, "FUNCIONARIO"
        if arquivo.suffix.lower() in (".xlsx", ".xls"):
            df2 = pd.read_excel(arquivo, dtype=str, header=1)
            if _eh_terceiro(df2):
                return df2, "TERCEIRO"
            if _tem_matricula_clt(df2):
                return df2, "FUNCIONARIO"
        return df, "FUNCIONARIO"  # default conservador

    def _parse_clt(self, df: pd.DataFrame) -> List[FuncionarioAtivo]:
        col = {k: _resolver_coluna(df, k) for k in _COLUNAS}
        out: List[FuncionarioAtivo] = []
        for _, row in df.iterrows():
            mat = _valor(row, col["matricula"])
            if not mat:
                continue
            out.append(FuncionarioAtivo(
                matricula=mat,
                nome=_valor(row, col["nome"]),
                cpf=_valor(row, col["cpf"]),
                cargo=Cargo(
                    codigo=_valor(row, col["cargo_codigo"]),
                    descricao=_valor(row, col["cargo_descricao"]),
                    departamento=_valor(row, col["departamento"]),
                    centro_custo=_valor(row, col["centro_custo_codigo"]),
                ),
                email=_valor(row, col["email"]) or None,
                data_admissao=_parse_data(_valor(row, col["data_admissao"])),
                situacao=_valor(row, col["situacao"]) or "ATIVO",
                tipo_vinculo="FUNCIONARIO",
            ))
        return out

    def _parse_terceiros(self, df: pd.DataFrame) -> List[FuncionarioAtivo]:
        col = {k: _resolver_terc(df, k) for k in _TERC_COLS}
        out: List[FuncionarioAtivo] = []
        vistos: set = set()
        dups = 0
        for _, row in df.iterrows():
            codigo = _digitos(_valor(row, col["codigo"]))
            nome = _norm_nome(_valor(row, col["nome"]))
            if not codigo or not nome:
                continue
            if codigo in vistos:
                dups += 1
                continue
            vistos.add(codigo)
            status = _valor(row, col["status"]).strip().upper()
            situacao = "INATIVO" if status.startswith("INATIV") else "ATIVO"
            supervisor = _norm_nome(_valor(row, col["supervisor"]))
            empresa = _valor(row, col["empresa"]) or None
            cpf = _cpf_de_codigo(codigo) or codigo
            out.append(FuncionarioAtivo(
                # chave com namespace pra nao colidir com matricula CLT
                matricula=f"TERC-{codigo}",
                nome=nome,
                cpf=cpf,
                # supervisor reaproveita 'departamento' por ora (sem coluna propria)
                cargo=Cargo(codigo="", descricao="", departamento=supervisor, centro_custo=""),
                email=None,
                data_admissao=None,
                situacao=situacao,
                tipo_vinculo="TERCEIRO",
                empresa=empresa,
            ))
        if dups:
            logger.warning(f"RH Terceiros: {dups} codigo(s) duplicado(s) ignorado(s).")
        return out

    def ler_desligados(self, pasta: str) -> Tuple[List[FuncionarioDesligado], List[str]]:
        desligados: List[FuncionarioDesligado] = []
        processados: List[str] = []

        for arquivo in self.listar_arquivos(pasta):
            try:
                enc = self.detectar_encoding(arquivo) if arquivo.suffix.lower() == ".csv" else "utf-8"
                df = _ler_df(arquivo, enc, self._separador)
                col = {k: _resolver_coluna(df, k) for k in _COLUNAS}

                for _, row in df.iterrows():
                    mat = _valor(row, col["matricula"])
                    if not mat:
                        continue
                    desligados.append(FuncionarioDesligado(
                        matricula=mat,
                        nome=_valor(row, col["nome"]),
                        cpf=_valor(row, col["cpf"]),
                        cargo=Cargo(
                            codigo=_valor(row, col["cargo_codigo"]),
                            descricao=_valor(row, col["cargo_descricao"]),
                            departamento=_valor(row, col["departamento"]),
                            centro_custo=_valor(row, col["centro_custo_codigo"]),
                        ),
                        email=_valor(row, col["email"]) or None,
                        data_admissao=_parse_data(_valor(row, col["data_admissao"])),
                        data_desligamento=_parse_data(_valor(row, col["data_desligamento"])),
                    ))

                self.mover_para_processados(arquivo)
                processados.append(arquivo.name)
                logger.success(f"RH Desligados: {len(desligados)} registros de '{arquivo.name}'")

            except Exception as e:
                self.mover_para_erros(arquivo, str(e))

        return desligados, processados
