from enum import Enum


class StatusValidacao(str, Enum):
    ADERENTE = "ADERENTE"
    DIVERGENTE = "DIVERGENTE"
    EM_ANALISE = "EM_ANALISE"
    NAO_MAPEADO = "NAO_MAPEADO"
    SEM_ACESSO = "SEM_ACESSO"
    SEM_DADOS = "SEM_DADOS"
