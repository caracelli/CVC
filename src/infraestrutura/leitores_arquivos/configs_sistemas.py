from dataclasses import dataclass, field
from typing import Dict
from dominio.objetos_valor.sistema import Sistema


@dataclass
class ConfigLeitorSistema:
    sistema: Sistema
    colunas: Dict[str, str]  # chave generica -> nome real da coluna no arquivo
    skiprows: int = 0
    separador: str = ";"
    # Mapeamento de valores de situacao para padrao interno
    mapa_situacao: Dict[str, str] = field(default_factory=lambda: {
        "A": "ATIVO", "ATIVO": "ATIVO", "I": "INATIVO", "INATIVO": "INATIVO",
    })


CONFIGS_SISTEMAS: Dict[Sistema, ConfigLeitorSistema] = {

    Sistema.SYSTUR: ConfigLeitorSistema(
        sistema=Sistema.SYSTUR,
        skiprows=0,
        colunas={
            "usuario":      "CD_LOGIN",
            "nome":         "NM_PESSOA",
            "cpf":          "CPF / CNPJ",
            "email":        "EMAIL",
            "perfil":       "NM_GRUPO",
            "situacao":     "ST_HABILITACAO",
        },
    ),

    Sistema.SICA_RA: ConfigLeitorSistema(
        sistema=Sistema.SICA_RA,
        skiprows=4,
        colunas={
            "usuario":       "Usuario",
            "nome":          "Nome",
            "cpf":           "CPF",
            "email":         "E-mail",
            "perfil":        "Grupo",
            "situacao":      "Status",
            "data_criacao":  "Data de Criaçăo",
            "ultimo_acesso": "Ultimo Acesso",
            "filial":        "Filial",
        },
        mapa_situacao={"ATIVO": "ATIVO", "INATIVO": "INATIVO", "BLOQUEADO": "BLOQUEADO"},
    ),

    Sistema.SIGOT: ConfigLeitorSistema(
        sistema=Sistema.SIGOT,
        skiprows=2,
        colunas={
            "usuario":       "Usuario",
            "nome":          "Nome",
            "cpf":           "CPF",
            "email":         "E-mail",
            "perfil":        "Grupo",
            "situacao":      "Status do Usuário",
            "data_criacao":  "Data de Criação",
            "ultimo_acesso": "Ultimo Acesso",
            "filial":        "Filial",
        },
        mapa_situacao={"ATIVO": "ATIVO", "INATIVO": "INATIVO"},
    ),

    Sistema.IC_INTEGRADOR_CONTABIL: ConfigLeitorSistema(
        sistema=Sistema.IC_INTEGRADOR_CONTABIL,
        skiprows=0,
        colunas={
            "usuario":  "CD_LOGIN",
            "nome":     "NM_PESSOA",
            "cpf":      "CPF",
            "email":    "CD_EMAIL",
            "perfil":   "NM_GRUPO",
            "situacao": "ST_HABILITACAO",
        },
    ),

    Sistema.SICA_ESFERA: ConfigLeitorSistema(
        sistema=Sistema.SICA_ESFERA,
        skiprows=4,
        colunas={
            "usuario":       "Usuario",
            "nome":          "Nome",
            "cpf":           "CPF",
            "email":         "E-mail",
            "perfil":        "Grupo",
            "situacao":      "Status",
            "data_criacao":  "Data de Criaçăo",
            "ultimo_acesso": "Ultimo Acesso",
            "filial":        "Filial",
        },
        mapa_situacao={"ATIVO": "ATIVO", "INATIVO": "INATIVO", "BLOQUEADO": "BLOQUEADO"},
    ),
}
