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


class LeitorRh(LeitorArquivoBase):

    def __init__(self, separador: str = ";", pasta_processados: str = None, pasta_erros: str = None):
        super().__init__(pasta_processados, pasta_erros)
        self._separador = separador

    def ler_ativos(self, pasta: str) -> Tuple[List[FuncionarioAtivo], List[str]]:
        ativos: List[FuncionarioAtivo] = []
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
                    ativos.append(FuncionarioAtivo(
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
                    ))

                self.mover_para_processados(arquivo)
                processados.append(arquivo.name)
                logger.success(f"RH Ativos: {len(ativos)} registros de '{arquivo.name}'")

            except Exception as e:
                self.mover_para_erros(arquivo, str(e))

        return ativos, processados

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
