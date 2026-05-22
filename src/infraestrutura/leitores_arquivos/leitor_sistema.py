import re
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

import pandas as pd
from loguru import logger

from .leitor_base import LeitorArquivoBase
from .configs_sistemas import ConfigLeitorSistema
from dominio.entidades.perfil_acesso import PerfilAcesso
from dominio.servicos_dominio.servico_padronizacao import ServicoPadronizacao

# BOM (Byte Order Mark) que aparece no inicio de arquivos UTF-8-SIG
_BOM = chr(0xFEFF)


def _parse_data(valor: Optional[str]) -> Optional[date]:
    if not valor or str(valor).strip() in ("", "nan"):
        return None
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(valor).strip()[:10], fmt).date()
        except Exception:
            continue
    return None


def _parse_datetime(valor: Optional[str]) -> Optional[datetime]:
    if not valor or str(valor).strip() in ("", "nan"):
        return None
    try:
        return pd.to_datetime(str(valor).strip(), dayfirst=True)
    except Exception:
        return None


def chave_data_arquivo(nome: str) -> tuple:
    """Extrai a data/hora embutida no nome do arquivo para ordenacao
    cronologica. Reconhece DD_MM_AAAA_HH-MM, DD_MM_AAAA e DD_MM.
    Arquivos sem data reconhecivel vao para o inicio da ordem."""
    m = re.search(r"(\d{2})[_-](\d{2})[_-](\d{4})[_-](\d{2})[-_](\d{2})", nome)
    if m:
        d, mes, ano, h, mi = (int(x) for x in m.groups())
        return (ano, mes, d, h, mi)
    m = re.search(r"(\d{2})[_-](\d{2})[_-](\d{4})", nome)
    if m:
        d, mes, ano = (int(x) for x in m.groups())
        return (ano, mes, d, 0, 0)
    m = re.search(r"(\d{2})[_-](\d{2})(?!\d)", nome)
    if m:
        d, mes = (int(x) for x in m.groups())
        return (0, mes, d, 0, 0)
    return (0, 0, 0, 0, 0)


class LeitorSistema(LeitorArquivoBase):

    def __init__(self, config: ConfigLeitorSistema, pasta_processados: str = None, pasta_erros: str = None):
        super().__init__(pasta_processados, pasta_erros)
        self._cfg = config
        self._pad = ServicoPadronizacao()

    def listar_ordenado(self, pasta: str) -> List[Path]:
        """Varre a pasta (recursivo) e devolve os arquivos ordenados pela
        data embutida no nome — do mais antigo para o mais recente."""
        return sorted(self.listar_arquivos(pasta), key=lambda f: chave_data_arquivo(f.name))

    def _ler_df(self, arquivo: Path, encoding: str) -> pd.DataFrame:
        if arquivo.suffix.lower() in (".xlsx", ".xls"):
            df = pd.read_excel(arquivo, dtype=str, skiprows=self._cfg.skiprows)
        else:
            df = pd.read_csv(
                arquivo,
                sep=self._cfg.separador,
                dtype=str,
                encoding=encoding,
                skiprows=self._cfg.skiprows,
                on_bad_lines="skip",
            )
        # o cabecalho pode vir com BOM e com espacos de preenchimento
        df.columns = [str(c).replace(_BOM, "").strip() for c in df.columns]
        return df

    def _valor(self, row: pd.Series, chave: str) -> str:
        col = self._cfg.colunas.get(chave)
        if not col or col not in row.index:
            return ""
        val = row[col]
        return "" if pd.isna(val) else str(val).strip()

    def _normalizar_situacao(self, valor: str) -> str:
        chave = valor.strip().upper()
        return self._cfg.mapa_situacao.get(chave, chave)

    def ler_um(self, arquivo: Path) -> List[PerfilAcesso]:
        """Le UM arquivo de extrato e devolve a lista de acessos."""
        enc = self.detectar_encoding(arquivo) if arquivo.suffix.lower() == ".csv" else "utf-8"
        df = self._ler_df(arquivo, enc).dropna(how="all")

        perfis: List[PerfilAcesso] = []
        for _, row in df.iterrows():
            usuario = self._valor(row, "usuario").strip()
            if not usuario:
                continue
            perfis.append(PerfilAcesso(
                usuario=usuario,
                nome_usuario=self._pad.normalizar_nome(self._valor(row, "nome")),
                sistema=self._cfg.sistema,
                perfil=self._valor(row, "perfil"),
                situacao=self._normalizar_situacao(self._valor(row, "situacao")),
                data_criacao=_parse_data(self._valor(row, "data_criacao")),
                ultimo_acesso=_parse_datetime(self._valor(row, "ultimo_acesso")),
                matricula_vinculada=None,
                cpf=self._pad.normalizar_cpf(self._valor(row, "cpf")),
            ))
        return perfis
