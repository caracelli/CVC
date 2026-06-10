from enum import Enum


class StatusValidacao(str, Enum):
    ADERENTE = "ADERENTE"
    DIVERGENTE = "DIVERGENTE"
    EM_ANALISE = "EM_ANALISE"
    NAO_MAPEADO = "NAO_MAPEADO"
    SEM_ACESSO = "SEM_ACESSO"
    SEM_DADOS = "SEM_DADOS"
    # Conforme: tem pelo menos um perfil aderente ao esperado (por sistema).
    # Aparece na grid como OK, mas NAO conta como pendencia.
    OK = "OK"
