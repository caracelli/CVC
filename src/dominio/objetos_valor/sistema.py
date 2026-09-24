from enum import Enum


class Sistema(Enum):
    SIGOT = "SIGOT"
    SICA_RA = "SICA_RA"
    SICA_ESFERA = "SICA_ESFERA"
    SYSTUR = "SYSTUR"
    IC_INTEGRADOR_CONTABIL = "IC_INTEGRADOR_CONTABIL"
    SIG = "SIG"
    ORACLE_EBS = "ORACLE_EBS"
    # SEM EXTRATO: existe so' para a CCO poder falar dele (usuario, 24/09/2026:
    # "opera operacional pode trazer no painel so' para cco"). Nenhum leitor,
    # nenhuma pasta de ENTRADA, ativo=false no config. O motor grava o que a
    # CCO preve como linha informativa SEM_EXTRATO_* — ver validar_acessos.
    OPERA_OPERACIONAL = "OPERA_OPERACIONAL"


# Normaliza o nome do sistema como vem da planilha CCO para o enum
_CCO_SISTEMA_MAP: dict[str, Sistema] = {
    "SYSTUR": Sistema.SYSTUR,
    "SIGOT": Sistema.SIGOT,
    "SICA RA": Sistema.SICA_RA,
    "SICA_RA": Sistema.SICA_RA,
    "SICA ESFERA": Sistema.SICA_ESFERA,
    "SICA_ESFERA": Sistema.SICA_ESFERA,
    "SIG": Sistema.SIG,
    "ORACLE EBS": Sistema.ORACLE_EBS,
    "OPERA OPERACIONAL": Sistema.OPERA_OPERACIONAL,
}


def sistema_do_texto(texto: str) -> "Sistema | None":
    return _CCO_SISTEMA_MAP.get(texto.strip().upper()) if texto else None
