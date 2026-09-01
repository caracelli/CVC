from dataclasses import dataclass, field
from typing import Dict, Optional, Sequence, Union
from dominio.objetos_valor.sistema import Sistema


@dataclass
class ConfigLeitorSistema:
    sistema: Sistema
    # chave generica -> nome real da coluna no arquivo. Aceita uma tupla de
    # ALIASES quando o mesmo extrato muda de layout entre exports (o leitor usa
    # o primeiro alias presente).
    colunas: Dict[str, Union[str, Sequence[str]]]
    skiprows: int = 0
    separador: str = ";"
    # Forca o encoding do CSV (ignora a deteccao automatica). Use quando o
    # chardet erra — ex.: SIGOT e' cp1252 mas e' detectado como cp1250.
    encoding: Optional[str] = None
    # Extrato com BLOCOS de perfil repetidos na mesma linha (cabecalho repete
    # ...;Grupo;... varias vezes -> pandas gera Grupo, Grupo.1, Grupo.2...).
    # Com despivot=True cada grupo preenchido vira um acesso.
    despivot: bool = False
    # Mapeamento de valores de situacao para padrao interno. Letras soltas sao
    # o padrao dos extratos (SYSTUR/IC): A=Ativo, I=Inativo, D=Desligado,
    # P=Pendente. A semantica de cada valor vive em dominio/situacao_conta.py.
    mapa_situacao: Dict[str, str] = field(default_factory=lambda: {
        "A": "ATIVO", "ATIVO": "ATIVO", "I": "INATIVO", "INATIVO": "INATIVO",
        "D": "DESLIGADO", "P": "PENDENTE",
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

    # O SICA_RA ja chegou em DOIS layouts e os dois sao importados:
    #  - 30/04: relatorio ';' com 4 linhas de preambulo (cabecalho na 5a),
    #    'Nome'/'CPF'/'Grupo'/'Status', CPF mascarado '39328XXX';
    #  - 01/09: dump da tabela, ',' e cabecalho na 1a linha,
    #    'User-Name'/'Description'/'grupo'/'ustatus', CPF '42182XXXXX1'.
    # A linha do cabecalho e o separador sao LOCALIZADOS (ler_tabela) a partir
    # destes nomes; o skiprows abaixo e' so o palpite do layout antigo.
    Sistema.SICA_RA: ConfigLeitorSistema(
        sistema=Sistema.SICA_RA,
        skiprows=4,
        colunas={
            "usuario":       ("Usuario", "usuario"),
            "nome":          ("Nome", "User-Name"),
            # No dump o CPF mascarado vem em 'Description'. extrair_cpf_parcial
            # pega os 5 primeiros digitos nos dois formatos.
            "cpf":           ("CPF", "Description"),
            "email":         ("E-mail", "email"),
            "perfil":        ("Grupo", "grupo"),
            "situacao":      ("Status", "ustatus"),
            "data_criacao":  ("Data de Criaçăo", "Create_date"),
            "ultimo_acesso": ("Ultimo Acesso", "Last_login"),
            "filial":        ("Filial", "filial"),
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
        separador=None,   # auto-detecta: extrato vem ora .xlsx ora .csv (virgula)
        colunas={
            "usuario":  "CD_LOGIN",
            "nome":     "NM_PESSOA",
            "cpf":      "CPF",
            "email":    "CD_EMAIL",
            "perfil":   "NM_GRUPO",
            # O layout de largura fixa (view_IC_*) chama a coluna de status de
            # 'S'; o XLSX antigo chamava 'ST_HABILITACAO'. Aceita os dois — sem
            # isso o status vinha VAZIO e a conta era assumida como ativa.
            "situacao": ("ST_HABILITACAO", "S"),
        },
        # Significado provado no cruzamento com o RH (29/07/2026, extrato de
        # 29/07): D = 100% na base de DESLIGADOS; P e I = 100% em RH ATIVOS
        # (conta pendente/inativa de gente da casa); A = ativo.
        mapa_situacao={"A": "ATIVO", "I": "INATIVO",
                       "D": "DESLIGADO", "P": "PENDENTE"},
    ),

    Sistema.SICA_ESFERA: ConfigLeitorSistema(
        sistema=Sistema.SICA_ESFERA,
        skiprows=4,                  # 4 linhas de cabecalho de relatorio; header na 5a
        encoding="cp1252",           # arquivo real e' cp1252 (acentos: Criacao/Alcada)
        # Layout real do extrato (SICA_ESFERA_24_06.csv): login = 'ID',
        # estabelecimento = 'Estab', sem acento em 'Data de Criacao'. CPF mascarado
        # (vinculacao por e-mail/CPF-parcial+nome).
        colunas={
            "usuario":       "ID",
            "nome":          "Nome",
            "cpf":           "CPF",
            "email":         "E-mail",
            "perfil":        "Grupo",
            "situacao":      "Status",
            "data_criacao":  "Data de Criacao",
            "ultimo_acesso": "Ultimo Acesso",
            "filial":        "Estab",
        },
        mapa_situacao={"ATIVO": "ATIVO", "INATIVO": "INATIVO", "BLOQUEADO": "BLOQUEADO"},
    ),

    # Oracle EBS (Card 11). Extrato XLSX (aba "Select per_all_people_f"), formato
    # LONGO (1 linha por usuario-perfil; sem despivot). CPF + MAIL = boa vinculacao.
    # Sem matriz de perfil esperado (gestao "por espelho", como o SIG) — a
    # validacao por cargo depende de decisao posterior. ativo=false (dormente).
    Sistema.ORACLE_EBS: ConfigLeitorSistema(
        sistema=Sistema.ORACLE_EBS,
        skiprows=0,
        colunas={
            "usuario":       "USUÁRIO",
            "nome":          "NM_USUÁRIO",
            "cpf":           "CPF",
            "email":         "MAIL",
            "perfil":        "PERFIL",
            "situacao":      "STATUS",
            "ultimo_acesso": "ÚLTIMO_ACESSO_EBS",
        },
        mapa_situacao={"ACTIVE": "ATIVO", "INACTIVE": "INATIVO",
                       "ATIVO": "ATIVO", "INATIVO": "INATIVO"},
    ),
}
