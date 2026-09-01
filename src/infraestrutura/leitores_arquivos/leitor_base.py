import re
import shutil
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence

import chardet
import pandas as pd
from loguru import logger

EXTENSOES_SUPORTADAS = {".csv", ".xlsx", ".xls"}

# BOM (Byte Order Mark) do UTF-8-SIG: vem colado no 1o nome de coluna.
_BOM = chr(0xFEFF)

# Ate onde procurar a linha de cabecalho. Relatorio com preambulo (SICA_RA
# antigo tinha 4 linhas; SIGOT, 2) cabe folgado; 25 evita varrer arquivo grande.
_MAX_LINHAS_CABECALHO = 25
# Quantos nomes de coluna esperados precisam bater para aceitar a linha como
# cabecalho. 1 acerto e' coincidencia (a palavra pode aparecer num titulo).
_MIN_ACERTOS_CABECALHO = 2

_SEPARADORES = (";", ",", "	")


def normalizar_nome_coluna(nome) -> str:
    """Nome de coluna em forma canonica para COMPARACAO: sem BOM, sem acento,
    sem espaco duplicado, maiusculo.

    E' o que permite o mesmo config atender exports diferentes do mesmo
    sistema. 'Data de Criacao', 'Data de Criação' e o mojibake 'Data de
    Criaçăo' (que o extrato do SICA_RA traz) colapsam todos em
    'DATA DE CRIACAO'.
    """
    s = str(nome).replace(_BOM, "").strip().strip('"').strip("'")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).upper()


def _acertos(celulas: Sequence[str], esperadas: set) -> int:
    """Quantos nomes esperados aparecem nesta linha (comparacao canonica)."""
    vistos = {normalizar_nome_coluna(c) for c in celulas if str(c).strip()}
    return len(vistos & esperadas)


def _canonizar_esperadas(colunas_esperadas) -> set:
    fora = set()
    for c in colunas_esperadas or ():
        if isinstance(c, str):
            fora.add(normalizar_nome_coluna(c))
        else:
            fora.update(normalizar_nome_coluna(x) for x in c)
    return {c for c in fora if c}


def _cabecalho_em_texto(linhas, esperadas: set, separador: Optional[str],
                        padrao: int):
    """Acha (indice_da_linha, separador) do cabecalho num CSV ja decodificado.

    Testa cada linha das primeiras _MAX_LINHAS_CABECALHO com CADA separador
    candidato e fica com a que reconhece mais colunas esperadas.

    O `separador` do config e' PALPITE, nao trava: entra so' como criterio de
    desempate. Se ele restringisse a busca, o extrato do SICA_RA de 01/09
    (virgula) seria procurado com ';' - uma linha inteira num campo so',
    zero coluna reconhecida - e cairia no skiprows do layout antigo, lendo
    zero acesso. Empate -> vence o separador do config, depois a linha que o
    config aponta, depois a mais alta.
    """
    seps = tuple(dict.fromkeys((separador,) + _SEPARADORES)) if separador else _SEPARADORES
    melhor = None                      # ((acertos, sep_config, linha_config, -i), i, sep)
    for i, linha in enumerate(linhas[:_MAX_LINHAS_CABECALHO]):
        for sep in seps:
            n = _acertos(linha.split(sep), esperadas)
            if n < _MIN_ACERTOS_CABECALHO:
                continue
            chave = (n, 1 if sep == separador else 0, 1 if i == padrao else 0, -i)
            if melhor is None or chave > melhor[0]:
                melhor = (chave, i, sep)
    return (melhor[1], melhor[2]) if melhor else None


def _cabecalho_em_excel(arquivo: Path, esperadas: set, padrao: int):
    """Mesma busca no XLSX/XLS: le so as primeiras linhas sem cabecalho."""
    try:
        amostra = pd.read_excel(arquivo, sheet_name=0, header=None, dtype=str,
                                nrows=_MAX_LINHAS_CABECALHO)
    except Exception as e:
        logger.debug(f"Amostra do cabecalho falhou ({arquivo.name}): {e!r}")
        return None
    melhor = None
    for i in range(len(amostra)):
        n = _acertos(list(amostra.iloc[i].values), esperadas)
        if n < _MIN_ACERTOS_CABECALHO:
            continue
        chave = (n, 1 if i == padrao else 0, -i)
        if melhor is None or chave > melhor[0]:
            melhor = (chave, i)
    return melhor[1] if melhor else None


def ler_tabela(arquivo, dtype=str, header=0, skiprows=0,
               encoding: str = None, separador: str = None,
               colunas_esperadas=None) -> "pd.DataFrame":
    """Leitura UNICA para todos os leitores: aceita XLSX/XLS (primeira aba),
    CSV DELIMITADO (',', ';' ou tab) OU CSV de LARGURA FIXA (colunas alinhadas
    por espacos, sem delimitador - ex.: view_IC do Integrador Contabil), com as
    MESMAS colunas/dados. Encoding e formato sao auto-detectados quando nao
    informados - assim o cliente pode mandar QUALQUER um dos formatos e todos
    sao importados. `encoding`/`separador` explicitos (config por sistema) tem
    prioridade sobre a deteccao; `separador` explicito nunca cai em largura fixa.

    Com `colunas_esperadas` (os nomes que o config do sistema procura, aliases
    inclusive) a LINHA DO CABECALHO tambem passa a ser procurada, em vez de vir
    fixa no `skiprows`. E' o que faz o mesmo sistema aceitar o relatorio com
    preambulo E o dump direto da tabela: o SICA_RA ja veio das duas formas
    (4 linhas de titulo + ';' em 30/04; cabecalho na 1a linha + ',' em 01/09).
    `skiprows` continua valendo como palpite - vence o empate e e' o fallback
    quando nada e' reconhecido.
    """
    arquivo = Path(arquivo)
    esperadas = _canonizar_esperadas(colunas_esperadas)
    if arquivo.suffix.lower() in (".xlsx", ".xls"):
        if esperadas:
            achado = _cabecalho_em_excel(arquivo, esperadas, skiprows + header)
            if achado is not None:
                if achado != skiprows + header:
                    logger.info(f"Cabecalho de '{arquivo.name}' localizado na "
                                f"linha {achado + 1} (config apontava "
                                f"{skiprows + header + 1})")
                skiprows, header = achado, 0
        return pd.read_excel(arquivo, sheet_name=0, dtype=dtype,
                             header=header, skiprows=skiprows)
    enc, sep = encoding, separador
    largura_fixa = False
    if enc is None or sep is None or esperadas:
        with open(arquivo, "rb") as f:
            bruto = f.read(65536)
        if enc is None:
            enc = (chardet.detect(bruto).get("encoding") if bruto else None) or "utf-8"
            # 'ascii' vindo da AMOSTRA nao garante ascii no arquivo todo: o
            # extrato do SIG de 15/07 (12 MB) so tem o 1o acento no byte 78.344
            # e estourava aqui, ja fora da janela lida. utf-8 e' superconjunto
            # do ascii - le tudo o que ascii leria, e ainda o acento tardio.
            if str(enc).lower() in ("ascii", "us-ascii"):
                enc = "utf-8"
        try:
            linhas = bruto.decode(enc, errors="replace").splitlines()
        except LookupError:
            enc = "utf-8"
            linhas = bruto.decode(enc, errors="replace").splitlines()
        if esperadas:
            achado = _cabecalho_em_texto(linhas, esperadas, separador,
                                         skiprows + header)
            if achado is not None:
                idx, sep_achado = achado
                if idx != skiprows + header:
                    logger.info(f"Cabecalho de '{arquivo.name}' localizado na "
                                f"linha {idx + 1} (config apontava "
                                f"{skiprows + header + 1})")
                skiprows, header = idx, 0
                sep = sep_achado
        if sep is None:
            # conta delimitadores NA LINHA DO CABECALHO real (skiprows+header)
            idx = skiprows + header
            alvo = linhas[idx] if len(linhas) > idx else (linhas[-1] if linhas else "")
            cont = {",": alvo.count(","), ";": alvo.count(";"), "\t": alvo.count("\t")}
            if any(cont.values()):
                sep = max(cont, key=cont.get)
            else:
                # nenhum delimitador no cabecalho -> arquivo de LARGURA FIXA.
                # read_fwf infere as colunas por posicao. So ocorre quando o
                # separador NAO foi configurado, entao CSV/XLSX seguem intactos.
                largura_fixa = True
    if largura_fixa:
        return pd.read_fwf(arquivo, dtype=dtype, header=header,
                           skiprows=skiprows, encoding=enc)
    return pd.read_csv(arquivo, sep=sep, dtype=dtype, encoding=enc,
                       header=header, skiprows=skiprows, on_bad_lines="skip")


class LeitorArquivoBase:

    def __init__(
        self,
        pasta_processados: Optional[str] = None,
        pasta_erros: Optional[str] = None,
    ):
        self._pasta_processados = Path(pasta_processados) if pasta_processados else None
        self._pasta_erros = Path(pasta_erros) if pasta_erros else None

    # Subpastas ignoradas na varredura recursiva (saídas do próprio processo)
    _SUBPASTAS_IGNORADAS = {"processados", "erros", "invalidos"}

    def listar_arquivos(self, pasta: str) -> List[Path]:
        """Varre a pasta RECURSIVAMENTE (ignorando PROCESSADOS/ERROS/INVALIDOS).
        Devolve só arquivos de tipo suportado (csv/xls/xlsx). Qualquer arquivo de
        tipo NÃO suportado, ou lock/temporário do Office (~$arquivo.xlsx), é MOVIDO
        para INVALIDOS/ — assim o Processador não trava tentando lê-los. Arquivos
        ocultos/estruturais (.gitkeep, .algo) são só ignorados (não movidos)."""
        p = Path(pasta)
        if not p.exists():
            logger.warning(f"Pasta não encontrada: {pasta}")
            return []
        validos: List[Path] = []
        invalidos: List[Path] = []
        for f in p.rglob("*"):
            if not f.is_file():
                continue
            if any(parte.lower() in self._SUBPASTAS_IGNORADAS
                   for parte in f.relative_to(p).parts[:-1]):
                continue
            nome = f.name
            if nome.startswith("."):            # .gitkeep e ocultos: estrutural, ignora
                continue
            if nome.startswith("~$"):            # lock/temporario do Office -> invalido
                invalidos.append(f)
            elif f.suffix.lower() in EXTENSOES_SUPORTADAS:
                validos.append(f)
            else:                               # tipo nao suportado -> invalido
                invalidos.append(f)
        for f in invalidos:
            self.mover_para_invalidos(f)
        logger.info(f"{len(validos)} arquivo(s) encontrado(s) em {p.name} (recursivo)"
                    + (f"; {len(invalidos)} invalido(s) movido(s)" if invalidos else ""))
        return sorted(validos)

    def mover_para_invalidos(self, arquivo: Path):
        """Move arquivo de tipo nao suportado / lock do Office para INVALIDOS/
        (na propria pasta de origem, igual a PROCESSADOS). Blindado: se o arquivo
        estiver em uso (lock aberto), apenas avisa e segue — nunca trava o processo."""
        destino = arquivo.parent / "INVALIDOS"
        try:
            destino.mkdir(parents=True, exist_ok=True)
            sufixo = datetime.now().strftime("%Y%m%d_%H%M%S")
            novo_nome = f"{arquivo.stem}_{sufixo}{arquivo.suffix}"
            shutil.move(str(arquivo), str(destino / novo_nome))
            logger.warning(f"Tipo nao suportado / lock -> INVALIDOS: {arquivo.name}")
        except Exception as e:
            logger.warning(f"Nao consegui mover invalido '{arquivo.name}' (em uso?): {e!r}")

    def mover_para_processados(self, arquivo: Path):
        # SEMPRE move para uma subpasta PROCESSADOS dentro da pasta do proprio
        # arquivo de origem (controle por pasta). A varredura recursiva ignora
        # "processados"/"erros" (_SUBPASTAS_IGNORADAS), entao nao reprocessa.
        destino = arquivo.parent / "PROCESSADOS"
        destino.mkdir(parents=True, exist_ok=True)
        sufixo = datetime.now().strftime("%Y%m%d_%H%M%S")
        novo_nome = f"{arquivo.stem}_{sufixo}{arquivo.suffix}"
        shutil.move(str(arquivo), str(destino / novo_nome))
        logger.info(f"Movido para processados: {destino}")

    def mover_para_erros(self, arquivo: Path, erro: str):
        destino = self._pasta_erros if self._pasta_erros else arquivo.parent / "ERROS"
        destino.mkdir(parents=True, exist_ok=True)
        sufixo = datetime.now().strftime("%Y%m%d_%H%M%S")
        novo_nome = f"{arquivo.stem}_{sufixo}{arquivo.suffix}"
        shutil.move(str(arquivo), str(destino / novo_nome))
        logger.error(f"Movido para erros: {arquivo.name} — {erro}")

    # Amostra por PONTO do arquivo. Ler so o comeco engana em export grande:
    # o extrato do SIG de 15/07 (12 MB) so tem o 1o acento no byte 78.344 —
    # a amostra antiga (50 KB do inicio) via ASCII puro, devolvia 'ascii' e a
    # leitura do arquivo INTEIRO estourava no primeiro 'Ç'. O arquivo era
    # descartado para ERROS e o snapshot se perdia em silencio.
    _AMOSTRA = 200_000

    def detectar_encoding(self, arquivo: Path) -> str:
        tam = arquivo.stat().st_size
        with open(arquivo, "rb") as f:
            raw = f.read(self._AMOSTRA)
            if tam > self._AMOSTRA * 2:          # tambem o meio e o fim
                f.seek(tam // 2)
                raw += f.read(self._AMOSTRA)
                f.seek(max(0, tam - self._AMOSTRA))
                raw += f.read(self._AMOSTRA)
        encoding = (chardet.detect(raw).get("encoding") or "utf-8").lower()
        # 'ascii' e' subconjunto de utf-8 E de cp1252: assumir utf-8 le tudo o
        # que ascii leria e ainda aguenta o acento que a amostra nao alcancou.
        if encoding in ("ascii", "us-ascii"):
            encoding = "utf-8"
        logger.debug(f"Encoding detectado ({arquivo.name}): {encoding}")
        return encoding
