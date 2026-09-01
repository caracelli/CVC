import re
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

import pandas as pd

from .leitor_base import LeitorArquivoBase, ler_tabela, normalizar_nome_coluna
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


# Milissegundo separado por ':' em vez de '.' -> '07:37:04:853'. O dump direto
# do SICA_RA (01/09) escreve assim; o relatorio antigo usava virgula.
_RE_MS = re.compile(r"(\d{1,2}:\d{2}:\d{2})[:,](\d{1,6})")
# Fuso solto no fim, com ou sem espaco: ' - 03:00' / '-03:00' -> '-0300'.
# Data que ja comeca por ano (ISO): 2026-03-27.
_RE_ISO = re.compile(r"\s*\d{4}-\d{2}-\d{2}")
_RE_FUSO = re.compile(r"\s*([+-])\s*(\d{2}):?(\d{2})\s*$")


def _limpar_timestamp(valor: str) -> str:
    """Formas de escrever a MESMA hora que ja chegaram do cliente:
    '30/04/2026 07:37:04,853-03:00' (relatorio SICA_RA de 30/04) e
    '2026-03-27 12:16:39:165 - 03:00' (dump SICA_RA de 01/09). Sem isto a
    segunda vira None e o ultimo acesso se perde em silencio - eram 86% das
    linhas do extrato de 01/09."""
    s = str(valor).strip()
    s = _RE_MS.sub(r"\1.\2", s)
    s = _RE_FUSO.sub(r"\1\2\3", s)
    return s


def _parse_datetime(valor: Optional[str]) -> Optional[datetime]:
    if not valor or str(valor).strip() in ("", "nan"):
        return None
    limpo = _limpar_timestamp(valor)
    for tentativa in (limpo, str(valor).strip()):
        # ISO (2026-03-27...) ja e' ano-mes-dia: dayfirst nao se aplica e o
        # pandas avisa. Data brasileira (30/04/2026) precisa de dayfirst.
        dia_primeiro = not _RE_ISO.match(tentativa)
        try:
            return pd.to_datetime(tentativa, dayfirst=dia_primeiro)
        except Exception:
            continue
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

    @staticmethod
    def _chave_ordem(arquivo: Path) -> tuple:
        """Data do arquivo para ordenar a importacao. Do NOME quando ele traz
        uma data; senao da DATA DE MODIFICACAO.

        O fallback existe porque a importacao e' SNAPSHOT (substituir_sistema)
        e o extrato e' CUMULATIVO: vale o ULTIMO arquivo lido. Sem data no
        nome, a chave era (0,0,0,0,0) e o arquivo ia para o INICIO da fila —
        o mais novo era sobrescrito pelo mais velho, calado. Aconteceria com
        o 'sicara 1.csv' de 01/09 ao lado do relatorio de 30/04: o painel
        terminaria com a foto de abril."""
        do_nome = chave_data_arquivo(arquivo.name)
        if do_nome != (0, 0, 0, 0, 0):
            return do_nome
        try:
            m = datetime.fromtimestamp(arquivo.stat().st_mtime)
        except OSError:
            return do_nome
        return (m.year, m.month, m.day, m.hour, m.minute)

    def listar_ordenado(self, pasta: str) -> List[Path]:
        """Varre a pasta (recursivo) e devolve os arquivos ordenados pela
        data embutida no nome — ou, na falta dela, pela data de modificacao —
        do mais antigo para o mais recente."""
        return sorted(self.listar_arquivos(pasta), key=self._chave_ordem)

    def _ler_df(self, arquivo: Path, encoding: str) -> pd.DataFrame:
        # XLSX (1a aba) ou CSV. O separador do sistema vem do config (explicito,
        # tem prioridade); o skiprows tambem. Nomes de aba/export podem mudar,
        # por isso sheet_name=0 dentro do helper.
        df = ler_tabela(
            arquivo, dtype=str, skiprows=self._cfg.skiprows,
            encoding=encoding, separador=self._cfg.separador,
            colunas_esperadas=list(self._cfg.colunas.values()),
        )
        # o cabecalho pode vir com BOM e com espacos de preenchimento
        df.columns = [str(c).replace(_BOM, "").strip() for c in df.columns]
        return df

    @staticmethod
    def _mapa_colunas(colunas) -> dict:
        """nome canonico -> nome real da coluna no arquivo. Primeira ocorrencia
        vence (colunas repetidas viram Grupo, Grupo.1... e nao colidem)."""
        mapa = {}
        for c in colunas:
            mapa.setdefault(normalizar_nome_coluna(c), c)
        return mapa

    def _valor(self, row: pd.Series, chave: str, mapa: dict = None) -> str:
        # O config aceita UM nome de coluna ou VARIOS (tupla/lista de aliases):
        # o mesmo extrato muda de layout entre exports (o IC ja veio com a coluna
        # de status como 'ST_HABILITACAO' no XLSX e como 'S' no texto de largura
        # fixa; o SICA_RA trocou 'Grupo'/'Status' por 'grupo'/'ustatus' no dump
        # de 01/09). Usa o primeiro alias presente na linha.
        #
        # A comparacao e' CANONICA (sem acento, sem caixa, sem espaco duplo):
        # 'E-mail' e 'E-MAIL' sao a mesma coluna, e o mojibake 'Data de Criaçăo'
        # encontra 'Data de Criação'. So o que muda de PALAVRA precisa de alias.
        col = self._cfg.colunas.get(chave)
        if not col:
            return ""
        if mapa is None:
            mapa = self._mapa_colunas(row.index)
        for nome in ((col,) if isinstance(col, str) else tuple(col)):
            real = mapa.get(normalizar_nome_coluna(nome))
            if real is not None and real in row.index:
                val = row[real]
                return "" if pd.isna(val) else str(val).strip()
        return ""

    def _normalizar_situacao(self, valor: str) -> str:
        chave = valor.strip().upper()
        return self._cfg.mapa_situacao.get(chave, chave)

    def _cols_perfil(self, df: pd.DataFrame) -> List[str]:
        """Despivot: todas as colunas de perfil repetidas. O cabecalho repete
        a coluna de perfil (ex.: Grupo, Grupo.1, Grupo.2...) — pandas sufixa com
        '.N'. Retorna a coluna base + as sufixadas, na ordem do arquivo.

        Aceita perfil declarado como ALIAS (tupla) e casa o nome em forma
        canonica, igual ao _valor — senao o despivot para de achar a coluna
        assim que o export troca a caixa do cabecalho."""
        base = self._cfg.colunas.get("perfil")
        if not base:
            return []
        alvos = {normalizar_nome_coluna(n)
                 for n in ((base,) if isinstance(base, str) else tuple(base))}
        out = []
        for c in df.columns:
            canon = normalizar_nome_coluna(c)
            raiz = canon.rsplit(".", 1)[0] if re.fullmatch(r".+\.\d+", canon) else canon
            if raiz in alvos:
                out.append(c)
        return out

    def ler_um(self, arquivo: Path) -> List[PerfilAcesso]:
        """Le UM arquivo de extrato e devolve a lista de acessos."""
        if self._cfg.encoding:
            enc = self._cfg.encoding
        else:
            enc = self.detectar_encoding(arquivo) if arquivo.suffix.lower() == ".csv" else "utf-8"
        df = self._ler_df(arquivo, enc).dropna(how="all")
        mapa = self._mapa_colunas(df.columns)
        cols_perfil = self._cols_perfil(df) if self._cfg.despivot else None

        perfis: List[PerfilAcesso] = []
        for _, row in df.iterrows():
            usuario = self._valor(row, chave="usuario", mapa=mapa).strip()
            if not usuario:
                continue
            comuns = dict(
                usuario=usuario,
                nome_usuario=self._pad.normalizar_nome(self._valor(row, chave="nome", mapa=mapa)),
                sistema=self._cfg.sistema,
                situacao=self._normalizar_situacao(self._valor(row, chave="situacao", mapa=mapa)),
                data_criacao=_parse_data(self._valor(row, chave="data_criacao", mapa=mapa)),
                ultimo_acesso=_parse_datetime(self._valor(row, chave="ultimo_acesso", mapa=mapa)),
                matricula_vinculada=None,
                cpf=self._pad.normalizar_cpf(self._valor(row, chave="cpf", mapa=mapa)),
                email=(self._valor(row, chave="email", mapa=mapa) or None),
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
                perfis.append(PerfilAcesso(perfil=self._valor(row, chave="perfil", mapa=mapa), **comuns))
        return perfis
