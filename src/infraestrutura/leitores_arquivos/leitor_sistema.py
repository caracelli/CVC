from datetime import date, datetime
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd
from loguru import logger

from .leitor_base import LeitorArquivoBase
from .configs_sistemas import ConfigLeitorSistema
from dominio.entidades.perfil_acesso import PerfilAcesso
from dominio.servicos_dominio.servico_padronizacao import ServicoPadronizacao


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


class LeitorSistema(LeitorArquivoBase):

    def __init__(self, config: ConfigLeitorSistema):
        self._cfg = config
        self._pad = ServicoPadronizacao()

    def _ler_df(self, arquivo: Path, encoding: str) -> pd.DataFrame:
        if arquivo.suffix.lower() in (".xlsx", ".xls"):
            return pd.read_excel(arquivo, dtype=str, skiprows=self._cfg.skiprows)
        return pd.read_csv(
            arquivo,
            sep=self._cfg.separador,
            dtype=str,
            encoding=encoding,
            skiprows=self._cfg.skiprows,
            on_bad_lines="skip",
        )

    def _valor(self, row: pd.Series, chave: str) -> str:
        col = self._cfg.colunas.get(chave)
        if not col or col not in row.index:
            return ""
        val = row[col]
        return "" if pd.isna(val) else str(val).strip()

    def _normalizar_situacao(self, valor: str) -> str:
        chave = valor.strip().upper()
        return self._cfg.mapa_situacao.get(chave, chave)

    def ler(self, pasta: str) -> Tuple[List[PerfilAcesso], List[str]]:
        perfis: List[PerfilAcesso] = []
        processados: List[str] = []

        for arquivo in self.listar_arquivos(pasta):
            try:
                enc = self.detectar_encoding(arquivo) if arquivo.suffix.lower() == ".csv" else "utf-8"
                df = self._ler_df(arquivo, enc)

                # remove linhas completamente vazias
                df = df.dropna(how="all")

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
                    ))

                self.mover_para_processados(arquivo)
                processados.append(arquivo.name)
                logger.success(f"{self._cfg.sistema.value}: {len(perfis)} registros de '{arquivo.name}'")

            except Exception as e:
                self.mover_para_erros(arquivo, str(e))

        return perfis, processados
