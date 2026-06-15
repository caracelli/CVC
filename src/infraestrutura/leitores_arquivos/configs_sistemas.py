from dataclasses import dataclass, field
from typing import Dict, Optional
from dominio.objetos_valor.sistema import Sistema


@dataclass
class ConfigLeitorSistema:
    sistema: Sistema
    colunas: Dict[str, str]  # chave generica -> nome real da coluna no arquivo
    skiprows: int = 0
    separador: str = ";"
    # Forca o encoding do CSV (ignora a deteccao automatica). Use quando o
    # chardet erra — ex.: SIGOT e' cp1252 mas e' detectado como cp1250.
    encoding: Optional[str] = None
    # Extrato com BLOCOS de perfil repetidos na mesma linha (cabecalho repete
    # ...;Grupo;... varias vezes -> pandas gera Grupo, Grupo.1, Grupo.2...).
    # Com despivot=True cada grupo preenchido vira um acesso.
    despivot: bool = False
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
            "perfil":       "CD_GRUPO_SIGLA",   # código do grupo (bate com a matriz)
            "situacao":     "S",                # extrato CSV novo: coluna "S" (A=Ativo)
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
        encoding="cp1252",   # chardet detecta cp1250 (errado); o arquivo e' cp1252
        despivot=True,       # cabecalho repete Filial;Padrao;Grupo;... 4x
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
        # O extrato SIGOT nao traz status (coluna em branco) -> trata como ATIVO.
        mapa_situacao={"": "ATIVO", "ATIVO": "ATIVO", "INATIVO": "INATIVO"},
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
