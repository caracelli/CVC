"""Cascata de matching multi-chave: vincula acessos de sistema a matriculas do RH.

Ordem da cascata (do mais confiavel pro menos):

  1. CPF exato         -> score 1.00, metodo=CPF
  2. Email exato       -> score 0.95, metodo=EMAIL
  3. CPF parcial (>=5 dig contiguos) + nome normalizado exato -> score 0.90, metodo=CPF_PARCIAL_NOME
  4. Nome normalizado exato (apenas) -> score 0.70, metodo=NOME (com flag)
  5. Fuzzy do nome (>=0.92 difflib)  -> score 0.50, metodo=FUZZY (so registra candidatos, NAO vincula)

Niveis 1-3: vinculam direto.
Nivel 4: vincula mas marca para revisao (so 1 candidato; se >1 candidatos por nome -> ambiguo).
Nivel 5: NAO vincula, registra candidatos para revisao humana.

Por que cascata: em IAM falso positivo e' grave — vincular o login do
SICA_RA da Joana Silva ao Joao Silva geraria divergencia falsa. Por isso:
- Quanto mais confiavel a chave, maior o score
- Em caso de ambiguidade (>1 candidato), nao escolhe — registra todos
- Fuzzy nunca vincula sozinho
"""
import difflib
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple


# Niveis e scores (constantes vivas — qualquer consumer pode importar)
METODO_CPF = "CPF"
METODO_EMAIL = "EMAIL"
METODO_CPF_PARCIAL_NOME = "CPF_PARCIAL_NOME"
METODO_NOME = "NOME"
METODO_FUZZY = "FUZZY"
METODO_NAO_VINCULADO = "NAO_VINCULADO"

SCORE_CPF = 1.00
SCORE_EMAIL = 0.95
SCORE_CPF_PARCIAL_NOME = 0.90
SCORE_NOME = 0.70
SCORE_FUZZY = 0.50
SCORE_NAO_VINCULADO = 0.0

# Vocabulario fixo de metodos (travado no schema — qualquer valor novo
# precisa de migration; documentar mudancas em docs/SCHEMA_DECISIONS.md)
METODOS_VALIDOS = frozenset({
    METODO_CPF, METODO_EMAIL, METODO_CPF_PARCIAL_NOME,
    METODO_NOME, METODO_FUZZY, METODO_NAO_VINCULADO,
})

_MIN_DIG_PARCIAL = 5     # minimo de digitos contiguos pra considerar CPF parcial
_FUZZY_THRESHOLD = 0.92  # similaridade minima do difflib pra entrar como candidato


@dataclass(frozen=True)
class FuncionarioRef:
    """Tudo do RH que precisamos para vincular. Imutavel/hashavel."""
    matricula: str
    cpf: str = ""        # ja normalizado: 11 digitos zfill
    email: str = ""      # ja normalizado: lower + trim
    nome: str = ""       # ja normalizado: upper, sem acento, espacos colapsados


@dataclass
class ResultadoVinculacao:
    metodo: str                          # ver METODO_*
    score: float                         # ver SCORE_*
    matricula: Optional[str] = None      # None quando nao vinculou
    candidatos: Optional[List[str]] = None  # so preenchido em ambiguidade ou fuzzy

    @property
    def vinculou(self) -> bool:
        return self.matricula is not None


# ---- normalizacao --------------------------------------------------------

def normalizar_cpf(v) -> str:
    """11 digitos com zero a esquerda. '' se nao tem digito."""
    if v is None:
        return ""
    d = re.sub(r"\D", "", str(v))
    return d.zfill(11) if d else ""


def extrair_cpf_parcial(v) -> str:
    """Sequencia mais longa de digitos contiguos. Util pra CPF mascarado
    estilo SICA_RA ('39328XXX' -> '39328'). Retorna '' se < _MIN_DIG_PARCIAL."""
    if v is None:
        return ""
    cand = re.findall(r"\d+", str(v))
    if not cand:
        return ""
    melhor = max(cand, key=len)
    return melhor if len(melhor) >= _MIN_DIG_PARCIAL else ""


def normalizar_email(v) -> str:
    if not v:
        return ""
    return str(v).strip().lower()


def normalizar_nome(v) -> str:
    """Upper, sem acentos, espacos colapsados."""
    if not v:
        return ""
    s = str(v).strip().upper()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.split())


# ---- servico -------------------------------------------------------------

class ServicoVinculacaoMultiChave:
    """Indexa o universo de funcionarios uma vez e resolve N vinculos em O(1)."""

    def __init__(self, funcionarios: Iterable[FuncionarioRef]):
        self._por_cpf: Dict[str, List[str]] = defaultdict(list)
        self._por_email: Dict[str, List[str]] = defaultdict(list)
        self._por_nome: Dict[str, List[str]] = defaultdict(list)
        # (cpf_parcial, nome) -> matriculas
        self._por_parcial_nome: Dict[Tuple[str, str], List[str]] = defaultdict(list)
        # lista de (nome_normalizado, matricula) pra fuzzy
        self._nomes_para_fuzzy: List[Tuple[str, str]] = []

        for f in funcionarios:
            if f.cpf:
                self._por_cpf[f.cpf].append(f.matricula)
            if f.email:
                self._por_email[f.email].append(f.matricula)
            if f.nome:
                self._por_nome[f.nome].append(f.matricula)
                self._nomes_para_fuzzy.append((f.nome, f.matricula))
                if f.cpf:
                    # registra (5 primeiros do CPF, nome) -> matricula
                    parcial = f.cpf[:_MIN_DIG_PARCIAL]
                    self._por_parcial_nome[(parcial, f.nome)].append(f.matricula)

    def vincular(self, *, cpf="", email="", nome="", cpf_mascarado="") -> ResultadoVinculacao:
        """Aplica a cascata pra um unico acesso. Inputs ja em formato bruto
        (a normalizacao acontece aqui)."""
        cpf_n = normalizar_cpf(cpf)
        email_n = normalizar_email(email)
        nome_n = normalizar_nome(nome)
        parcial = extrair_cpf_parcial(cpf_mascarado or cpf)

        # 1) CPF exato (so se tem 11 digitos completos)
        if cpf_n and len(cpf_n) == 11:
            cand = self._por_cpf.get(cpf_n, [])
            if len(cand) == 1:
                return ResultadoVinculacao(METODO_CPF, SCORE_CPF, cand[0])
            if len(cand) > 1:
                # CPF duplicado no RH (raro mas possivel: re-contratacao com mesma matricula?)
                return ResultadoVinculacao(METODO_CPF, SCORE_CPF, cand[0], candidatos=cand)

        # 2) Email exato
        if email_n:
            cand = self._por_email.get(email_n, [])
            if len(cand) == 1:
                return ResultadoVinculacao(METODO_EMAIL, SCORE_EMAIL, cand[0])
            if len(cand) > 1:
                return ResultadoVinculacao(METODO_EMAIL, SCORE_EMAIL, cand[0], candidatos=cand)

        # 3) CPF parcial + nome exato
        if parcial and nome_n:
            cand = self._por_parcial_nome.get((parcial, nome_n), [])
            if len(cand) == 1:
                return ResultadoVinculacao(METODO_CPF_PARCIAL_NOME, SCORE_CPF_PARCIAL_NOME, cand[0])
            if len(cand) > 1:
                return ResultadoVinculacao(
                    METODO_CPF_PARCIAL_NOME, SCORE_CPF_PARCIAL_NOME, cand[0], candidatos=cand)

        # 4) Nome exato (com flag)
        if nome_n:
            cand = self._por_nome.get(nome_n, [])
            if len(cand) == 1:
                return ResultadoVinculacao(METODO_NOME, SCORE_NOME, cand[0])
            if len(cand) > 1:
                # Ambiguo por nome — escolhe o primeiro mas marca como candidato multiplo
                return ResultadoVinculacao(METODO_NOME, SCORE_NOME, cand[0], candidatos=cand)

        # 5) Fuzzy nome — NAO vincula, so registra candidatos (top 3 acima do threshold)
        if nome_n:
            candidatos = self._fuzzy_top(nome_n, max_n=3)
            if candidatos:
                return ResultadoVinculacao(
                    METODO_FUZZY, SCORE_FUZZY, matricula=None, candidatos=candidatos)

        return ResultadoVinculacao(METODO_NAO_VINCULADO, SCORE_NAO_VINCULADO, matricula=None)

    def _fuzzy_top(self, alvo: str, max_n: int = 3) -> List[str]:
        if not self._nomes_para_fuzzy:
            return []
        pares = []
        for nome, matricula in self._nomes_para_fuzzy:
            r = difflib.SequenceMatcher(None, alvo, nome).ratio()
            if r >= _FUZZY_THRESHOLD:
                pares.append((r, matricula))
        if not pares:
            return []
        pares.sort(reverse=True)
        # deduplica preservando ordem
        vistos = []
        for _, m in pares:
            if m not in vistos:
                vistos.append(m)
            if len(vistos) >= max_n:
                break
        return vistos


# ---- helpers utilitarios --------------------------------------------------

def construir_universo(funcionarios: Iterable) -> List[FuncionarioRef]:
    """Constroi a lista de FuncionarioRef a partir de entidades RH/objeto bruto.
    Aceita qualquer objeto com atributos matricula, cpf, email, nome."""
    out = []
    for f in funcionarios:
        nome = getattr(f, "nome", "") or ""
        out.append(FuncionarioRef(
            matricula=getattr(f, "matricula", "") or "",
            cpf=normalizar_cpf(getattr(f, "cpf", "")),
            email=normalizar_email(getattr(f, "email", "")),
            nome=normalizar_nome(nome),
        ))
    return out
