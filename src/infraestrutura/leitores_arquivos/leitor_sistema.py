import re
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

import pandas as pd

from .leitor_base import LeitorArquivoBase, ler_tabela
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
        # XLSX (1a aba) ou CSV. O separador do sistema vem do config (explicito,
        # tem prioridade); o skiprows tambem. Nomes de aba/export podem mudar,
        # por isso sheet_name=0 dentro do helper.
        df = ler_tabela(
            arquivo, dtype=str, skiprows=self._cfg.skiprows,
            encoding=encoding, separador=self._cfg.separador,
        )
        # o cabecalho pode vir com BOM e com espacos de preenchimento
        df.columns = [str(c).replace(_BOM, "").strip() for c in df.columns]
        return df

    def _valor(self, row: pd.Series, chave: str) -> str:
        # O config aceita UM nome de coluna ou VARIOS (tupla/lista de aliases):
        # o mesmo extrato muda de layout entre exports (o IC ja veio com a coluna
        # de status como 'ST_HABILITACAO' no XLSX e como 'S' no texto de largura
        # fixa). Usa o primeiro alias presente na linha.
        col = self._cfg.colunas.get(chave)
        if not col:
            return ""
        for nome in ((col,) if isinstance(col, str) else tuple(col)):
            if nome in row.index:
                val = row[nome]
                return "" if pd.isna(val) else str(val).strip()
        return ""

    def _normalizar_situacao(self, valor: str) -> str:
        chave = valor.strip().upper()
        return self._cfg.mapa_situacao.get(chave, chave)

    def _cols_perfil(self, df: pd.DataFrame) -> List[str]:
        """Despivot: todas as colunas de perfil repetidas. O cabecalho repete
        a coluna de perfil (ex.: Grupo, Grupo.1, Grupo.2...) — pandas sufixa com
        '.N'. Retorna a coluna base + as sufixadas, na ordem do arquivo."""
        base = self._cfg.colunas.get("perfil")
        if not base:
            return []
        return [c for c in df.columns if c == base or c.startswith(base + ".")]

    def ler_um(self, arquivo: Path) -> List[PerfilAcesso]:
        """Le UM arquivo de extrato e devolve a lista de acessos."""
        if self._cfg.encoding:
            enc = self._cfg.encoding
        else:
            enc = self.detectar_encoding(arquivo) if arquivo.suffix.lower() == ".csv" else "utf-8"
        df = self._ler_df(arquivo, enc).dropna(how="all")
        cols_perfil = self._cols_perfil(df) if self._cfg.despivot else None

        perfis: List[PerfilAcesso] = []
        for _, row in df.iterrows():
            usuario = self._valor(row, "usuario").strip()
            if not usuario:
                continue
            comuns = dict(
                usuario=usuario,
                nome_usuario=self._pad.normalizar_nome(self._valor(row, "nome")),
                sistema=self._cfg.sistema,
                situacao=self._normalizar_situacao(self._valor(row, "situacao")),
                data_criacao=_parse_data(self._valor(row, "data_criacao")),
                ultimo_acesso=_parse_datetime(self._valor(row, "ultimo_acesso")),
                matricula_vinculada=None,
                cpf=self._pad.normalizar_cpf(self._valor(row, "cpf")),
                email=(self._valor(row, "email") or None),
            )
            if cols_perfil is not None:
                # um acesso por grupo preenchido (sem repetir o mesmo grupo)
                vistos = []
                for c in cols_perfil:
                    v = row.get(c)
                    v = "" if pd.isna(v) else str(v).strip()
                    if v and v not in vistos:
                        vistos.append(v)
                        perfis.append(PerfilAcesso(perfil=v, **comuns))
                # sem nenhum grupo -> usuario sem acesso no sistema (nao emite)
            else:
                perfis.append(PerfilAcesso(perfil=self._valor(row, "perfil"), **comuns))
        return perfis
