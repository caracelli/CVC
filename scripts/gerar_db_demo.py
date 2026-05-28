# -*- coding: utf-8 -*-
"""Gera um iam_analytics.db de demonstracao com dados aleatorios coerentes.

Substitui o banco atual em CVC_IAM_ANALYTICS/DADOS/BANCO/iam_analytics.db.
Ideal para apresentacao ao cliente sem expor dados reais.

Conteudo gerado:
  - ~150 funcionarios ativos (rh_ativos)
  - ~30 desligados (rh_desligados)
  - Matriz de cargos x perfis SYSTUR (perfis_esperados)
  - Matriz CCO (matriz_cco)
  - ~200 acessos SYSTUR (acessos_sistemas) com mix:
      * acesso correto
      * acesso divergente do esperado
      * funcionario ainda com acesso apos desligamento
      * acesso sem vinculo RH ("nao mapeado")
  - ~50 divergencias calculadas (divergencias + bi_divergencias)
  - ~25 validacoes pendentes pra grid de Pendencias (validacao_acessos)
  - ~10 resolucoes ja feitas com tickets IAM-XXXX (resolucoes)
  - ~3 em quarentena ativa + ~6 no historico (quarentena, quarentena_historico)
  - ~15 movimentacoes recentes de RH (historico_rh)

Uso:
    python scripts/gerar_db_demo.py
"""
import json
import random
import sqlite3
from datetime import datetime, timedelta, date
from pathlib import Path

random.seed(42)  # determinismo: rodar 2x gera o mesmo cenario

DB_PATH = (Path(__file__).resolve().parent.parent
           / "CVC_IAM_ANALYTICS" / "DADOS" / "BANCO" / "iam_analytics.db")

HOJE = date(2026, 5, 26)
EMPRESA = "CVC BRASIL OPERADORA E AGENCIA DE VIAGENS S.A."

PRIMEIROS_NOMES = [
    "ANA", "BRUNO", "CARLA", "DANIEL", "EDUARDA", "FELIPE", "GABRIELA",
    "HENRIQUE", "ISABELA", "JOAO", "KARINA", "LUCAS", "MARIANA", "NATALIA",
    "OTAVIO", "PATRICIA", "QUEZIA", "RAFAEL", "SABRINA", "THIAGO",
    "URSULA", "VINICIUS", "WAGNER", "XIMENA", "YASMIN", "ZAIRA",
    "ALICE", "BERNARDO", "CAMILA", "DIEGO", "ELISA", "FABRICIO",
    "GIOVANA", "HELOISA", "IGOR", "JULIANA", "KAUE", "LARISSA",
    "MARCOS", "NICOLE", "OSVALDO", "PRISCILA", "RICARDO", "SILVIA",
    "TIAGO", "ULISSES", "VIVIANE", "WILLIAM", "YURI", "ZULMIRA",
]
SOBRENOMES = [
    "SILVA", "SANTOS", "OLIVEIRA", "SOUZA", "RODRIGUES", "FERREIRA",
    "ALMEIDA", "PEREIRA", "LIMA", "GOMES", "COSTA", "RIBEIRO", "MARTINS",
    "CARVALHO", "ARAUJO", "MELO", "BARBOSA", "ROCHA", "DIAS", "NASCIMENTO",
    "MENDES", "CASTRO", "CAMPOS", "CARDOSO", "MOREIRA", "AZEVEDO",
    "MIRANDA", "FREITAS", "TEIXEIRA", "PINTO", "MOURA", "CAVALCANTI",
    "DUARTE", "MONTEIRO", "RAMOS", "MACHADO", "VIEIRA", "FONSECA",
    "BORGES", "GUIMARAES",
]

# (codigo, descricao)
CARGOS = [
    ("AB001", "ANALISTA FISCAL PL"),
    ("AB002", "ANALISTA FISCAL SR"),
    ("AB003", "ANALISTA CONTABIL JR"),
    ("AB004", "ANALISTA CONTABIL PL"),
    ("AB005", "COORDENADOR FISCAL"),
    ("AB006", "COORDENADOR CONTABIL"),
    ("AB007", "GERENTE FISCAL"),
    ("AB008", "ANALISTA TRIBUTARIO PL"),
    ("CD001", "ANALISTA SERVICE DESK"),
    ("CD002", "COORDENADOR SERVICE DESK"),
    ("CD003", "GERENTE TI"),
    ("CD004", "ANALISTA SISTEMAS SR"),
    ("CD005", "ANALISTA INFRAESTRUTURA PL"),
    ("EF001", "ASSISTENTE SUPORTE VENDAS"),
    ("EF002", "ANALISTA VENDAS JR"),
    ("EF003", "ANALISTA VENDAS PL"),
    ("EF004", "COORDENADOR VENDAS"),
    ("EF005", "GERENTE DE VENDAS"),
    ("EF006", "DIRETOR COMERCIAL"),
    ("GH001", "ADVOGADO JR"),
    ("GH002", "ADVOGADO PL"),
    ("GH003", "COORDENADOR JURIDICO"),
    ("IJ001", "ANALISTA RH JR"),
    ("IJ002", "ANALISTA RH PL"),
    ("IJ003", "COORDENADOR RH"),
    ("KL001", "ASSISTENTE ADMINISTRATIVO"),
    ("KL002", "ANALISTA MARKETING JR"),
    ("KL003", "ANALISTA MARKETING PL"),
    ("MN001", "COORDENADOR ATENDIMENTO"),
    ("MN002", "GERENTE OPERACOES"),
    ("MN003", "DIRETOR FINANCEIRO"),
]

# (codigo, nome, departamento)
CENTROS_CUSTO = [
    ("01.02.06.01", "FISCAL OPERACIONAL", "FINANCEIRO"),
    ("01.02.06.02", "FISCAL TRIBUTARIO", "FINANCEIRO"),
    ("01.02.02.01", "CONTABILIDADE GERAL", "FINANCEIRO"),
    ("01.02.02.02", "CONTABILIDADE FISCAL", "FINANCEIRO"),
    ("01.02.03.01", "JURIDICO CONTENCIOSO", "JURIDICO"),
    ("01.02.03.02", "JURIDICO TRABALHISTA", "JURIDICO"),
    ("01.13.03.03", "SERVICE DESK", "TECNOLOGIA"),
    ("01.13.04.01", "INFRAESTRUTURA TI", "TECNOLOGIA"),
    ("01.13.05.01", "DESENVOLVIMENTO", "TECNOLOGIA"),
    ("05.02.07.08", "VENDAS ATENDIMENTO", "COMERCIAL"),
    ("05.02.07.10", "VENDAS CORPORATIVO", "COMERCIAL"),
    ("05.01.01.04", "VENDAS GERENCIA", "COMERCIAL"),
    ("05.01.02.01", "MARKETING DIGITAL", "MARKETING"),
    ("01.04.01.01", "DIRETORIA FINANCEIRA", "DIRETORIA"),
    ("01.05.01.01", "RH OPERACIONAL", "RH"),
    ("01.06.01.01", "ADMINISTRACAO", "ADMINISTRATIVO"),
]

LOCAIS = ["SAO PAULO/SP", "RIO DE JANEIRO/RJ", "BELO HORIZONTE/MG",
          "PORTO ALEGRE/RS", "CURITIBA/PR", "RECIFE/PE", "SALVADOR/BA"]

# Perfis SYSTUR validos
PERFIS_SYSTUR = [
    "FISCAL_BASICO", "FISCAL_TRIBUTARIO", "FISCAL_SUPERVISOR",
    "CONTABIL_OPERACIONAL", "CONTABIL_GERENCIAL", "CONTABIL_SUPERVISOR",
    "JURIDICO_CONTENCIOSO", "JURIDICO_TRABALHISTA",
    "JURIDICO_CONTENCIOSO_COM_REEMBOLSO",
    "TI_SISTEMAS_OPERADOR", "TI_SISTEMAS_SUPERVISOR", "TI_INFRA_OPERADOR",
    "VENDAS_CONSULTA", "VENDAS_OPERACIONAL", "VENDAS_GERENCIA",
    "VENDAS_DIRETORIA",
    "RH_OPERADOR", "RH_GERENTE",
    "ADMIN_BASICO", "ADMIN_FINANCEIRO", "ADMIN_DIRETORIA",
    "MKT_OPERADOR", "MKT_ANALISTA",
]

# Mapeamento cargo (codigo) -> perfis esperados (1+ perfis; alguns "em analise"
# que tem 2 perfis possiveis)
MATRIZ_CARGO_PERFIL = {
    "AB001": ["FISCAL_BASICO"],
    "AB002": ["FISCAL_TRIBUTARIO"],
    "AB003": ["CONTABIL_OPERACIONAL"],
    "AB004": ["CONTABIL_GERENCIAL"],
    "AB005": ["FISCAL_SUPERVISOR"],
    "AB006": ["CONTABIL_SUPERVISOR"],
    "AB007": ["FISCAL_SUPERVISOR"],
    "AB008": ["FISCAL_TRIBUTARIO"],
    "CD001": ["TI_SISTEMAS_OPERADOR"],
    "CD002": ["TI_SISTEMAS_SUPERVISOR"],
    "CD003": ["TI_SISTEMAS_SUPERVISOR"],
    "CD004": ["TI_SISTEMAS_OPERADOR"],
    "CD005": ["TI_INFRA_OPERADOR"],
    "EF001": ["VENDAS_CONSULTA"],
    "EF002": ["VENDAS_CONSULTA", "VENDAS_OPERACIONAL"],  # 2 opcoes -> em analise
    "EF003": ["VENDAS_OPERACIONAL"],
    "EF004": ["VENDAS_GERENCIA"],
    "EF005": ["VENDAS_GERENCIA"],
    "EF006": ["VENDAS_DIRETORIA"],
    "GH001": ["JURIDICO_CONTENCIOSO"],
    "GH002": ["JURIDICO_CONTENCIOSO",
              "JURIDICO_CONTENCIOSO_COM_REEMBOLSO"],  # em analise
    "GH003": ["JURIDICO_TRABALHISTA"],
    "IJ001": ["RH_OPERADOR"],
    "IJ002": ["RH_OPERADOR"],
    "IJ003": ["RH_GERENTE"],
    "KL001": ["ADMIN_BASICO"],
    "KL002": ["MKT_OPERADOR"],
    "KL003": ["MKT_ANALISTA"],
    "MN001": ["ADMIN_BASICO"],
    "MN002": ["ADMIN_FINANCEIRO"],
    "MN003": ["ADMIN_DIRETORIA"],
}


def gerar_cpf():
    """CPF fictiicio no formato XXXXXXXXXXX (so digitos, 11)."""
    return "".join(str(random.randint(0, 9)) for _ in range(11))


def gerar_nome_unico(usados: set) -> str:
    while True:
        nome = f"{random.choice(PRIMEIROS_NOMES)} {random.choice(SOBRENOMES)}"
        if random.random() < 0.4:
            nome += f" {random.choice(SOBRENOMES)}"
        if nome not in usados:
            usados.add(nome)
            return nome


def gerar_email(nome: str) -> str:
    primeiro = nome.split()[0].lower()
    ultimo = nome.split()[-1].lower()
    return f"{primeiro}.{ultimo}@cvccorp.com.br"


def data_aleatoria(inicio: date, fim: date) -> date:
    delta = (fim - inicio).days
    return inicio + timedelta(days=random.randint(0, max(delta, 0)))


def fmt_data(d) -> str:
    if isinstance(d, str):
        return d
    return d.strftime("%Y-%m-%d")


def fmt_dt(d) -> str:
    if isinstance(d, str):
        return d
    if isinstance(d, date) and not isinstance(d, datetime):
        d = datetime.combine(d, datetime.min.time())
    return d.strftime("%Y-%m-%d %H:%M:%S")


def criar_schema(cur):
    """Cria todas as tabelas necessarias."""
    cur.executescript("""
        DROP TABLE IF EXISTS rh_ativos;
        DROP TABLE IF EXISTS rh_desligados;
        DROP TABLE IF EXISTS perfis_esperados;
        DROP TABLE IF EXISTS matriz_cco;
        DROP TABLE IF EXISTS acessos_sistemas;
        DROP TABLE IF EXISTS catalogo_perfis;
        DROP TABLE IF EXISTS divergencias;
        DROP TABLE IF EXISTS bi_divergencias;
        DROP TABLE IF EXISTS validacao_acessos;
        DROP TABLE IF EXISTS resolucoes;
        DROP TABLE IF EXISTS quarentena;
        DROP TABLE IF EXISTS quarentena_historico;
        DROP TABLE IF EXISTS historico_rh;
        DROP TABLE IF EXISTS historico;
        DROP TABLE IF EXISTS snapshots_rh;
        DROP TABLE IF EXISTS log_importacoes;

        CREATE TABLE rh_ativos (
            matricula VARCHAR PRIMARY KEY, nome VARCHAR, cpf VARCHAR,
            cargo_codigo VARCHAR, cargo_descricao VARCHAR,
            centro_custo_codigo VARCHAR, centro_custo_nome VARCHAR,
            departamento VARCHAR, data_admissao DATE, email VARCHAR,
            situacao VARCHAR, empresa VARCHAR, local_trabalho VARCHAR,
            arquivo_origem VARCHAR, dt_importacao DATETIME);

        CREATE TABLE rh_desligados (
            matricula VARCHAR PRIMARY KEY, nome VARCHAR, cpf VARCHAR,
            cargo_codigo VARCHAR, cargo_descricao VARCHAR,
            centro_custo_codigo VARCHAR, centro_custo_nome VARCHAR,
            departamento VARCHAR, data_admissao DATE, data_desligamento DATE,
            email VARCHAR, empresa VARCHAR,
            arquivo_origem VARCHAR, dt_importacao DATETIME);

        CREATE TABLE perfis_esperados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cargo_codigo VARCHAR, cargo_descricao VARCHAR,
            sistema VARCHAR, perfil VARCHAR, acesso_manual BOOLEAN,
            arquivo_origem VARCHAR, dt_importacao DATETIME);

        CREATE TABLE matriz_cco (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cc VARCHAR, cc_nome VARCHAR, funcao VARCHAR,
            sistema VARCHAR, perfil VARCHAR,
            arquivo_origem VARCHAR, dt_importacao DATETIME);

        CREATE TABLE acessos_sistemas (
            sistema VARCHAR, usuario VARCHAR, perfil VARCHAR,
            nome_usuario VARCHAR, cpf VARCHAR, email VARCHAR, situacao VARCHAR,
            data_criacao DATE, ultimo_acesso DATETIME, filial VARCHAR,
            matricula_vinculada VARCHAR,
            metodo_vinculacao VARCHAR, score_vinculacao REAL,
            candidatos_matricula TEXT,
            arquivo_origem VARCHAR, dt_importacao DATETIME,
            PRIMARY KEY (sistema, usuario, perfil));

        CREATE TABLE catalogo_perfis (
            sistema VARCHAR, codigo VARCHAR, nome VARCHAR, familia VARCHAR,
            descricao TEXT, arquivo_origem VARCHAR, dt_importacao DATETIME,
            PRIMARY KEY (sistema, codigo));

        CREATE TABLE divergencias (
            id VARCHAR PRIMARY KEY, tipo VARCHAR, sistema VARCHAR,
            usuario VARCHAR, nome_usuario VARCHAR, matricula VARCHAR,
            perfil_encontrado VARCHAR, perfil_esperado VARCHAR,
            descricao TEXT, data_identificacao DATETIME,
            resolvida BOOLEAN, dt_importacao DATETIME);

        CREATE TABLE bi_divergencias (
            id TEXT, tipo TEXT, sistema TEXT, usuario TEXT,
            nome_usuario, matricula, perfil_encontrado, perfil_esperado,
            descricao, data_identificacao, resolvida NUM, acao, origem);

        CREATE TABLE validacao_acessos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            matricula VARCHAR, cpf VARCHAR, nome VARCHAR, email VARCHAR,
            centro_custo_codigo VARCHAR, centro_custo_nome VARCHAR,
            cargo_codigo VARCHAR, cargo_descricao VARCHAR,
            sistema VARCHAR, perfil_esperado VARCHAR, perfil_atual VARCHAR,
            acesso_manual BOOLEAN, status VARCHAR, origem_matriz VARCHAR,
            dt_processamento DATETIME, situacao_acao TEXT);

        CREATE TABLE resolucoes (
            registro_id TEXT PRIMARY KEY, ticket TEXT NOT NULL,
            ticket_url TEXT, descricao TEXT, pendencias TEXT,
            cargo TEXT, centro_custo TEXT, nome TEXT,
            resolvido_por TEXT, resolvido_em TEXT, dobrado_em TEXT);

        CREATE TABLE quarentena (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL, nome_usuario TEXT, sistema TEXT,
            matricula TEXT, origem TEXT,
            data_inicio TEXT NOT NULL, data_fim TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Em quarentena',
            criado_por TEXT, criado_em TEXT NOT NULL);

        CREATE TABLE quarentena_historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL, nome_usuario TEXT, sistema TEXT,
            matricula TEXT, origem TEXT,
            data_inicio TEXT NOT NULL, data_fim TEXT NOT NULL,
            data_saida TEXT NOT NULL, motivo TEXT NOT NULL,
            criado_por TEXT, criado_em TEXT, encerrado_por TEXT,
            movido_em TEXT NOT NULL);

        CREATE TABLE historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_snapshot DATE, entidade VARCHAR, chave_entidade VARCHAR,
            tipo_mudanca VARCHAR, campos_alterados TEXT,
            dados_anterior TEXT, dados_novo TEXT, dt_registro DATETIME,
            tipo VARCHAR, matricula VARCHAR);

        CREATE TABLE snapshots_rh (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_snapshot DATE, tipo VARCHAR, total_registros INTEGER,
            novos INTEGER, alterados INTEGER, removidos INTEGER,
            arquivo_parquet VARCHAR, dt_criacao DATETIME);

        CREATE TABLE log_importacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            arquivo VARCHAR, tipo VARCHAR, total_registros INTEGER,
            status VARCHAR, mensagem_erro TEXT, hash_arquivo VARCHAR,
            dt_importacao DATETIME);
    """)


def gerar_funcionarios(n: int, matriculas_usadas: set,
                      nomes_usados: set, is_desligado=False) -> list:
    fs = []
    for i in range(n):
        while True:
            mat = str(random.randint(1000, 99999))
            if mat not in matriculas_usadas:
                matriculas_usadas.add(mat)
                break
        nome = gerar_nome_unico(nomes_usados)
        cargo_cod, cargo_desc = random.choice(CARGOS)
        cc_cod, cc_nome, dept = random.choice(CENTROS_CUSTO)
        if is_desligado:
            admissao = data_aleatoria(date(2015, 1, 1), date(2024, 12, 31))
            desligamento = data_aleatoria(date(2024, 6, 1), HOJE)
        else:
            admissao = data_aleatoria(date(2010, 1, 1), date(2026, 4, 30))
            desligamento = None
        fs.append({
            "matricula": mat, "nome": nome, "cpf": gerar_cpf(),
            "cargo_codigo": cargo_cod, "cargo_descricao": cargo_desc,
            "centro_custo_codigo": cc_cod, "centro_custo_nome": cc_nome,
            "departamento": dept,
            "data_admissao": admissao,
            "data_desligamento": desligamento,
            "email": gerar_email(nome),
            "empresa": EMPRESA,
            "local_trabalho": random.choice(LOCAIS),
            # rh_ativos.situacao real: ATIVO | FÉRIAS | AFASTAMENTO.
            # rh_desligados nao tem coluna situacao.
            "situacao": (random.choices(
                ["ATIVO", "FÉRIAS", "AFASTAMENTO"], weights=[92, 5, 3])[0]
                if not is_desligado else None),
        })
    return fs


def inserir_rh_ativos(cur, ativos):
    agora = fmt_dt(datetime.now())
    for f in ativos:
        cur.execute("""INSERT INTO rh_ativos VALUES
            (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (f["matricula"], f["nome"], f["cpf"],
             f["cargo_codigo"], f["cargo_descricao"],
             f["centro_custo_codigo"], f["centro_custo_nome"],
             f["departamento"], fmt_data(f["data_admissao"]),
             f["email"], f["situacao"], f["empresa"],
             f["local_trabalho"], "PROJETOIAM_DEMO.CSV", agora))


def inserir_rh_desligados(cur, desligados):
    agora = fmt_dt(datetime.now())
    for f in desligados:
        cur.execute("""INSERT INTO rh_desligados VALUES
            (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (f["matricula"], f["nome"], f["cpf"],
             f["cargo_codigo"], f["cargo_descricao"],
             f["centro_custo_codigo"], f["centro_custo_nome"],
             f["departamento"], fmt_data(f["data_admissao"]),
             fmt_data(f["data_desligamento"]),
             f["email"], f["empresa"],
             "PROJETOIAMDESLIGADOS_DEMO.CSV", agora))


def inserir_perfis_esperados(cur):
    agora = fmt_dt(datetime.now())
    for cargo_cod, cargo_desc in CARGOS:
        perfis = MATRIZ_CARGO_PERFIL.get(cargo_cod, [])
        for perfil in perfis:
            cur.execute("""INSERT INTO perfis_esperados
                (cargo_codigo, cargo_descricao, sistema, perfil, acesso_manual,
                 arquivo_origem, dt_importacao) VALUES (?,?,?,?,?,?,?)""",
                (cargo_cod, cargo_desc, "SYSTUR", perfil, 0,
                 "MATRIZ DE PERFIL DE ACESSO SYSTUR DEMO.xlsx", agora))


def inserir_matriz_cco(cur):
    """Matriz CCO: alguns CCs com perfil especifico (override do cargo)."""
    agora = fmt_dt(datetime.now())
    # Alguns CCs especificos com perfil "manual" (override) — 5-10 entradas
    overrides = [
        ("01.02.06.02", "FISCAL TRIBUTARIO", "ANALISTA SR", "SYSTUR",
         "FISCAL_TRIBUTARIO"),
        ("01.02.03.01", "JURIDICO CONTENCIOSO", "ADVOGADO",
         "SYSTUR", "JURIDICO_CONTENCIOSO"),
        ("05.01.01.04", "VENDAS GERENCIA", "GERENTE",
         "SYSTUR", "VENDAS_GERENCIA"),
        ("01.13.03.03", "SERVICE DESK", "COORDENADOR",
         "SYSTUR", "TI_SISTEMAS_SUPERVISOR"),
    ]
    for cc, cc_nome, funcao, sistema, perfil in overrides:
        cur.execute("""INSERT INTO matriz_cco
            (cc, cc_nome, funcao, sistema, perfil, arquivo_origem, dt_importacao)
            VALUES (?,?,?,?,?,?,?)""",
            (cc, cc_nome, funcao, sistema, perfil,
             "Mapeamento CCO_CSC DEMO.xlsx", agora))


def gerar_acessos(ativos, desligados):
    """Gera ~200 acessos no SYSTUR com mix de:
      - acesso correto (~50%): funcionario tem o perfil que a matriz exige
      - acesso divergente (~20%): tem perfil mas nao bate com matriz
      - acesso de desligado (~10%): funcionario desligado ainda tem acesso
      - acesso sem vinculo (~10%): usuario no SYSTUR sem matricula RH
      - acesso "em analise" (~10%): cargo tem 2 perfis possiveis
    """
    acessos = []
    # 1. ~50% corretos
    n_certos = 75
    for f in random.sample(ativos, min(n_certos, len(ativos))):
        perfis = MATRIZ_CARGO_PERFIL.get(f["cargo_codigo"], [])
        if perfis:
            perfil = random.choice(perfis)
            acessos.append(_acesso_de(f, perfil, situacao="ATIVO"))
    # 2. ~20% divergentes (perfil errado)
    candidatos_div = [f for f in ativos if f["cargo_codigo"]
                      in MATRIZ_CARGO_PERFIL]
    for f in random.sample(candidatos_div, min(40, len(candidatos_div))):
        perfis_esp = MATRIZ_CARGO_PERFIL[f["cargo_codigo"]]
        outros = [p for p in PERFIS_SYSTUR if p not in perfis_esp]
        if outros:
            acessos.append(_acesso_de(f, random.choice(outros),
                                       situacao="ATIVO"))
    # 3. ~10% desligados com acesso
    for f in random.sample(desligados, min(15, len(desligados))):
        perfis = MATRIZ_CARGO_PERFIL.get(f["cargo_codigo"], PERFIS_SYSTUR[:3])
        acessos.append(_acesso_de(f, random.choice(perfis), situacao="ATIVO"))
    # 4. ~10% sem vinculo (usuario no SYSTUR sem matricula no RH)
    nomes_usados = {a["nome_usuario"] for a in acessos}
    nomes_seed = set()
    for _ in range(20):
        nome = gerar_nome_unico(nomes_seed)
        if nome in nomes_usados:
            continue
        acessos.append({
            "sistema": "SYSTUR",
            "usuario": f"EXMP{random.randint(1, 9999):04d}",
            "nome_usuario": nome,
            "cpf": "",
            "email": gerar_email(nome),
            "perfil": random.choice(PERFIS_SYSTUR),
            "situacao": "ATIVO",
            "data_criacao": fmt_data(data_aleatoria(date(2020, 1, 1), HOJE)),
            "ultimo_acesso": fmt_dt(data_aleatoria(date(2026, 1, 1), HOJE)),
            "filial": random.choice(LOCAIS),
            "matricula_vinculada": None,
        })
    return acessos


def _acesso_de(f, perfil, situacao="ATIVO"):
    return {
        "sistema": "SYSTUR",
        "usuario": str(f["matricula"]),
        "nome_usuario": f["nome"],
        "cpf": f["cpf"],
        "email": f["email"],
        "perfil": perfil,
        "situacao": situacao,
        "data_criacao": fmt_data(f["data_admissao"]),
        "ultimo_acesso": fmt_dt(data_aleatoria(date(2026, 1, 1), HOJE)),
        "filial": f["local_trabalho"],
        "matricula_vinculada": str(f["matricula"]),
    }


def inserir_acessos(cur, acessos):
    agora = fmt_dt(datetime.now())
    for a in acessos:
        mat = a["matricula_vinculada"]
        # Demo: assume CPF puro (todo o demo gera CPF completo); sem vinculo = NAO_VINCULADO
        if mat:
            metodo, score = "CPF", 1.0
        else:
            metodo, score = "NAO_VINCULADO", 0.0
        cur.execute("""INSERT OR IGNORE INTO acessos_sistemas
            (sistema, usuario, perfil, nome_usuario, cpf, email, situacao,
             data_criacao, ultimo_acesso, filial, matricula_vinculada,
             metodo_vinculacao, score_vinculacao, candidatos_matricula,
             arquivo_origem, dt_importacao)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (a["sistema"], a["usuario"], a["perfil"], a["nome_usuario"],
             a["cpf"], a["email"], a["situacao"], a["data_criacao"],
             a["ultimo_acesso"], a["filial"], mat,
             metodo, score, None,
             "relatorio_systur_DEMO.xlsx", agora))


def gerar_validacoes(ativos, acessos):
    """Para cada combinacao ativo x SYSTUR, gera 1 linha em validacao_acessos:
      - perfil_esperado da matriz; perfil_atual do acesso (se houver);
        status calculado.
    """
    by_user = {a["usuario"]: a for a in acessos if a["matricula_vinculada"]}
    agora = fmt_dt(datetime.now())
    validacoes = []
    for f in ativos:
        perfis_esp = MATRIZ_CARGO_PERFIL.get(f["cargo_codigo"], [])
        if not perfis_esp:
            continue
        ac = by_user.get(str(f["matricula"]))
        perfil_atual = ac["perfil"] if ac else None
        if not perfil_atual:
            status = "SEM_ACESSO"
        elif len(perfis_esp) > 1 and perfil_atual not in perfis_esp:
            status = "EM_ANALISE"
        elif perfil_atual in perfis_esp:
            status = "OK"
        else:
            status = "DIVERGENTE"
        # data_identificacao no PASSADO (30-60 dias atras): garante que
        # quando essa matricula for resolvida, o resolvido_em fica DEPOIS.
        di_inicio = HOJE - timedelta(days=60)
        di_fim = HOJE - timedelta(days=30)
        data_id = data_aleatoria(di_inicio, di_fim)
        validacoes.append({
            "f": f, "perfil_esp": "|".join(perfis_esp),
            "perfil_atual": perfil_atual or "",
            "status": status,                       # SEM_ACESSO|DIVERGENTE|EM_ANALISE|OK
            "origem": "MATRIZ",                     # origem_matriz: MATRIZ|CCO
            "dt": agora,
            "data_identificacao": fmt_dt(datetime.combine(data_id, datetime.min.time())),
        })
    return validacoes


def inserir_validacoes(cur, validacoes):
    """validacao_acessos.situacao_acao = 'PENDENTE' (uppercase, valor real do projeto)."""
    for v in validacoes:
        if v["status"] == "OK":
            continue  # so guarda as que tem acao
        f = v["f"]
        cur.execute("""INSERT INTO validacao_acessos
            (matricula, cpf, nome, email, centro_custo_codigo, centro_custo_nome,
             cargo_codigo, cargo_descricao, sistema, perfil_esperado,
             perfil_atual, acesso_manual, status, origem_matriz,
             dt_processamento, situacao_acao)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (f["matricula"], f["cpf"], f["nome"], f["email"],
             f["centro_custo_codigo"], f["centro_custo_nome"],
             f["cargo_codigo"], f["cargo_descricao"], "SYSTUR",
             v["perfil_esp"], v["perfil_atual"], 0,
             v["status"], v.get("origem", "MATRIZ"), v["dt"], "PENDENTE"))


def gerar_divergencias(ativos, desligados, acessos):
    """Gera divergencias:
      - ACESSO_DESLIGADO: desligado com acesso
      - ACESSO_SEM_VINCULO_RH: usuario sem matricula
      - PERFIL_INVALIDO: matricula com perfil divergente
    """
    by_mat_ativo = {f["matricula"]: f for f in ativos}
    by_mat_deslig = {f["matricula"]: f for f in desligados}
    divs = []
    contador = 1
    for a in acessos:
        if not a["matricula_vinculada"]:
            # Sem vinculo
            divs.append({
                "id": f"DIV{contador:05d}",
                "tipo": "ACESSO_SEM_VINCULO_RH",
                "sistema": "SYSTUR",
                "usuario": a["usuario"],
                "nome_usuario": a["nome_usuario"],
                "matricula": "",
                "perfil_encontrado": a["perfil"],
                "perfil_esperado": "",
                "descricao": "Usuário sem matrícula no RH ativo.",
                "origem": "",
            })
            contador += 1
            continue
        mat = a["matricula_vinculada"]
        if mat in by_mat_deslig:
            divs.append({
                "id": f"DIV{contador:05d}",
                "tipo": "ACESSO_DESLIGADO",
                "sistema": "SYSTUR",
                "usuario": a["usuario"],
                "nome_usuario": a["nome_usuario"],
                "matricula": mat,
                "perfil_encontrado": a["perfil"],
                "perfil_esperado": "",
                "descricao": "Funcionário desligado ainda com acesso ativo.",
                "origem": "",
            })
            contador += 1
            continue
        f = by_mat_ativo.get(mat)
        if not f:
            continue
        esperados = MATRIZ_CARGO_PERFIL.get(f["cargo_codigo"], [])
        if esperados and a["perfil"] not in esperados:
            divs.append({
                "id": f"DIV{contador:05d}",
                "tipo": "PERFIL_INVALIDO",
                "sistema": "SYSTUR",
                "usuario": a["usuario"],
                "nome_usuario": a["nome_usuario"],
                "matricula": mat,
                "perfil_encontrado": a["perfil"],
                "perfil_esperado": "|".join(esperados),
                "descricao": (f"Perfil '{a['perfil']}' nao corresponde "
                              f"a nenhum dos perfis esperados para o cargo."),
                "origem": "MATRIZ",
            })
            contador += 1
    return divs


def inserir_divergencias(cur, divs):
    agora = fmt_dt(datetime.now())
    for d in divs:
        cur.execute("""INSERT INTO divergencias VALUES
            (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (d["id"], d["tipo"], d["sistema"], d["usuario"],
             d["nome_usuario"], d["matricula"], d["perfil_encontrado"],
             d["perfil_esperado"], d["descricao"], agora, 0, agora))


def inserir_bi_divergencias(cur, divs, validacoes):
    """A tabela bi_divergencias e' o snapshot consolidado para o painel.
    Combina: validacao_acessos (com acao) + divergencias com tipo
    ACESSO_SEM_VINCULO_RH. A data_identificacao vem da propria validacao
    (no passado) — assim resolucoes futuras ficam coerentes (resolvido
    SEMPRE depois de identificado)."""
    # 1. validacoes (com data_identificacao no passado)
    for v in validacoes:
        if v["status"] == "OK":
            continue
        f = v["f"]
        if v["status"] == "SEM_ACESSO":   acao = "Incluir Acesso"
        elif v["status"] == "DIVERGENTE": acao = "Alterar Perfil"
        elif v["status"] == "EM_ANALISE": acao = "Em Análise"
        else:                              acao = "OK"
        cur.execute("""INSERT INTO bi_divergencias VALUES
            (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (f"VAL{f['matricula']}", v["status"], "SYSTUR",
             str(f["matricula"]), f["nome"], str(f["matricula"]),
             v["perfil_atual"], v["perfil_esp"], "",
             v["data_identificacao"], 0, acao, "MATRIZ"))
    # 2. acesso sem vinculo — data tambem no passado pra coerencia
    di_inicio = HOJE - timedelta(days=60)
    di_fim = HOJE - timedelta(days=30)
    for d in divs:
        if d["tipo"] != "ACESSO_SEM_VINCULO_RH":
            continue
        data_id = fmt_dt(datetime.combine(
            data_aleatoria(di_inicio, di_fim), datetime.min.time()))
        cur.execute("""INSERT INTO bi_divergencias VALUES
            (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (d["id"], d["tipo"], "SYSTUR", d["usuario"],
             d["nome_usuario"], "", d["perfil_encontrado"], "",
             d["descricao"], data_id, 0, "Não Mapeado", ""))


def gerar_resolucoes(validacoes, n=10):
    """~10 resolucoes com tickets IAM-XXXX. Escolhe entre as validacoes
    PENDENTES (= matriculas que tem bi_divergencias) e seta resolvido_em
    SEMPRE depois da data_identificacao da pendencia."""
    pendentes = [v for v in validacoes if v["status"] != "OK"]
    selected = random.sample(pendentes, min(n, len(pendentes)))
    resolucoes = []
    descricoes = [
        "Perfil ajustado conforme a matriz.",
        "Acesso de supervisao concedido apos validacao.",
        "Perfil corrigido para o adequado ao cargo.",
        "Acesso incluido conforme solicitacao do gestor.",
        "Acessos regularizados em massa.",
        "Perfil ajustado apos reuniao com o gestor.",
    ]
    for v in selected:
        f = v["f"]
        perfis_esp = v["perfil_esp"].split("|")
        # mapeia status -> rotulo de tipo da pendencia (igual ao do painel)
        tipo = {"SEM_ACESSO": "Sem Acesso", "DIVERGENTE": "Divergente",
                "EM_ANALISE": "Em Análise"}.get(v["status"], "Divergente")
        ticket_num = 2000 + random.randint(0, 200)
        # data_id da bi_divergencia (formato "YYYY-MM-DD HH:MM:SS")
        data_id = v["data_identificacao"]
        # parse pra date e seta resolvido_em entre (data_id + 3 dias) e HOJE
        data_id_d = datetime.strptime(data_id, "%Y-%m-%d %H:%M:%S").date()
        inicio_resolucao = data_id_d + timedelta(days=3)
        # garante que a janela e' valida (se data_id muito recente, fica >= HOJE)
        if inicio_resolucao > HOJE:
            inicio_resolucao = data_id_d + timedelta(days=1)
        resolvido_em = data_aleatoria(inicio_resolucao, HOJE)
        pendencias = [{
            "tipo": tipo, "acao": tipo,
            "sistema": "SYSTUR", "origem": "Matriz SYSTUR",
            "pe": v["perfil_atual"],
            "pp": perfis_esp[0] if perfis_esp else "",
            "opcoes": perfis_esp if tipo == "Em Análise" and len(perfis_esp) > 1 else [],
            "dt": data_id,
        }]
        resolucoes.append({
            "registro_id": str(f["matricula"]),
            "ticket": f"IAM-{ticket_num}",
            "ticket_url": f"https://jira.cvc.com.br/browse/IAM-{ticket_num}",
            "descricao": random.choice(descricoes),
            "pendencias": json.dumps(pendencias, ensure_ascii=False),
            "cargo": f["cargo_descricao"],
            "centro_custo": f["centro_custo_codigo"],
            "nome": f["nome"],
            "resolvido_por": random.choice(["nelson.diniz", "ana.souza",
                                             "carlos.lima", "patricia.melo"]),
            "resolvido_em": fmt_dt(datetime.combine(
                resolvido_em, datetime.min.time())),
        })
    return resolucoes


def inserir_resolucoes(cur, resolucoes):
    agora = fmt_dt(datetime.now())
    for r in resolucoes:
        cur.execute("""INSERT INTO resolucoes VALUES
            (?,?,?,?,?,?,?,?,?,?,?)""",
            (r["registro_id"], r["ticket"], r["ticket_url"], r["descricao"],
             r["pendencias"], r["cargo"], r["centro_custo"], r["nome"],
             r["resolvido_por"], r["resolvido_em"], agora))


def gerar_quarentena(ativos):
    """3 funcionarios em quarentena ATIVA + 6 ja saidos (no historico)."""
    selected = random.sample(ativos, 9)
    ativos_q = selected[:3]
    historico = selected[3:]
    agora = fmt_dt(datetime.now())

    quars = []
    for f in ativos_q:
        di = data_aleatoria(date(2026, 5, 10), date(2026, 5, 25))
        df = di + timedelta(days=90)
        quars.append({
            "usuario": str(f["matricula"]),
            "nome_usuario": f["nome"],
            "sistema": "SYSTUR",
            "matricula": str(f["matricula"]),
            "origem": "Inclusão / Alteração",
            "data_inicio": fmt_data(di),
            "data_fim": fmt_data(df),
            "status": "Em quarentena",
            "criado_por": random.choice(["nelson.diniz", "ana.souza"]),
            "criado_em": fmt_dt(di) + ".000000",
        })

    hist = []
    for f in historico:
        di = data_aleatoria(date(2026, 4, 1), date(2026, 5, 15))
        df = di + timedelta(days=90)
        saida = di + timedelta(days=random.randint(1, 14))
        hist.append({
            "usuario": str(f["matricula"]),
            "nome_usuario": f["nome"],
            "sistema": "SYSTUR",
            "matricula": str(f["matricula"]),
            "origem": "Inclusão / Alteração",
            "data_inicio": fmt_data(di),
            "data_fim": fmt_data(df),
            "data_saida": fmt_data(saida),
            "motivo": "Resolvido",
            "criado_por": random.choice(["nelson.diniz", "ana.souza"]),
            "criado_em": fmt_dt(di),
            "encerrado_por": random.choice(["nelson.diniz", "carlos.lima"]),
            "movido_em": agora,
        })
    return quars, hist


def inserir_quarentena(cur, ativos_q, hist_q):
    for q in ativos_q:
        cur.execute("""INSERT INTO quarentena
            (usuario, nome_usuario, sistema, matricula, origem,
             data_inicio, data_fim, status, criado_por, criado_em)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (q["usuario"], q["nome_usuario"], q["sistema"], q["matricula"],
             q["origem"], q["data_inicio"], q["data_fim"], q["status"],
             q["criado_por"], q["criado_em"]))
    for h in hist_q:
        cur.execute("""INSERT INTO quarentena_historico
            (usuario, nome_usuario, sistema, matricula, origem,
             data_inicio, data_fim, data_saida, motivo,
             criado_por, criado_em, encerrado_por, movido_em)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (h["usuario"], h["nome_usuario"], h["sistema"], h["matricula"],
             h["origem"], h["data_inicio"], h["data_fim"], h["data_saida"],
             h["motivo"], h["criado_por"], h["criado_em"],
             h["encerrado_por"], h["movido_em"]))


def gerar_historico_rh(ativos, desligados, n=15):
    """Mistura de NOVO (admissao), ALTERADO (mudou cargo/CC),
    REMOVIDO (desligado)."""
    eventos = []
    # Modelo do projeto (registrar_historico_rh.py):
    #   NOVO     -> dados_anterior=None, dados_novo=json, campos_alterados=None
    #   ALTERADO -> ambos JSON, campos_alterados="campo1,campo2"
    #   REMOVIDO -> dados_anterior=json, dados_novo=None, campos_alterados=None
    # tipo: ATIVO | DESLIGADO (mesmo do arquivo de RH origem)

    # ~5 admissoes (recentes)
    novos = sorted(ativos, key=lambda f: f["data_admissao"], reverse=True)[:5]
    for f in novos:
        eventos.append({
            "data_snapshot": fmt_data(f["data_admissao"]),
            "tipo": "ATIVO",
            "matricula": str(f["matricula"]),
            "tipo_mudanca": "NOVO",
            "campos_alterados": None,
            "dados_anterior": None,
            "dados_novo": json.dumps({
                "matricula": str(f["matricula"]),
                "nome": f["nome"],
                "cargo_descricao": f["cargo_descricao"],
                "centro_custo_nome": f["centro_custo_nome"],
                "departamento": f["departamento"],
                "data_admissao": fmt_data(f["data_admissao"]),
            }, ensure_ascii=False),
            "dt_registro": fmt_dt(datetime.now()),
        })
    # ~5 alteracoes (mudanca de cargo)
    for f in random.sample(ativos, 5):
        ant_cargo_cod, ant_cargo_desc = random.choice(CARGOS)
        if ant_cargo_cod == f["cargo_codigo"]:
            continue
        eventos.append({
            "data_snapshot": fmt_data(data_aleatoria(date(2026, 5, 1), HOJE)),
            "tipo": "ATIVO",
            "matricula": str(f["matricula"]),
            "tipo_mudanca": "ALTERADO",
            "campos_alterados": "cargo_codigo,cargo_descricao",
            "dados_anterior": json.dumps({
                "cargo_codigo": ant_cargo_cod,
                "cargo_descricao": ant_cargo_desc,
            }, ensure_ascii=False),
            "dados_novo": json.dumps({
                "cargo_codigo": f["cargo_codigo"],
                "cargo_descricao": f["cargo_descricao"],
            }, ensure_ascii=False),
            "dt_registro": fmt_dt(datetime.now()),
        })
    # ~5 desligamentos
    recentes_desligados = sorted(desligados,
                                  key=lambda f: f["data_desligamento"],
                                  reverse=True)[:5]
    for f in recentes_desligados:
        eventos.append({
            "data_snapshot": fmt_data(f["data_desligamento"]),
            "tipo": "DESLIGADO",
            "matricula": str(f["matricula"]),
            "tipo_mudanca": "REMOVIDO",
            "campos_alterados": None,
            "dados_anterior": json.dumps({
                "matricula": str(f["matricula"]),
                "nome": f["nome"],
                "cargo_descricao": f["cargo_descricao"],
            }, ensure_ascii=False),
            "dados_novo": None,
            "dt_registro": fmt_dt(datetime.now()),
        })
    return eventos


def inserir_historico_rh(cur, eventos):
    """Insere na tabela historico unificada. Preenche entidade e chave_entidade
    e duplica em tipo/matricula para compatibilidade com leitura legada."""
    for e in eventos:
        entidade = "RH_DESLIGADO" if e["tipo"] == "DESLIGADO" else "RH_ATIVO"
        cur.execute("""INSERT INTO historico
            (data_snapshot, entidade, chave_entidade, tipo_mudanca,
             campos_alterados, dados_anterior, dados_novo, dt_registro,
             tipo, matricula)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (e["data_snapshot"], entidade, e["matricula"],
             e["tipo_mudanca"], e["campos_alterados"],
             e["dados_anterior"], e["dados_novo"], e["dt_registro"],
             e["tipo"], e["matricula"]))


def main():
    print(f"Gerando DB demo em: {DB_PATH}")
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        bak = DB_PATH.with_suffix(".db.bak_pre_demo")
        if bak.exists():
            bak.unlink()
        DB_PATH.rename(bak)
        print(f"  Backup do banco anterior em: {bak}")

    con = sqlite3.connect(str(DB_PATH))
    con.execute("PRAGMA journal_mode=WAL")
    cur = con.cursor()

    criar_schema(cur)
    print("  schema criado")

    matriculas_usadas = set()
    nomes_usados = set()

    ativos = gerar_funcionarios(150, matriculas_usadas, nomes_usados,
                                 is_desligado=False)
    inserir_rh_ativos(cur, ativos)
    print(f"  rh_ativos: {len(ativos)}")

    desligados = gerar_funcionarios(30, matriculas_usadas, nomes_usados,
                                     is_desligado=True)
    inserir_rh_desligados(cur, desligados)
    print(f"  rh_desligados: {len(desligados)}")

    inserir_perfis_esperados(cur)
    inserir_matriz_cco(cur)
    print(f"  perfis_esperados / matriz_cco")

    acessos = gerar_acessos(ativos, desligados)
    inserir_acessos(cur, acessos)
    print(f"  acessos_sistemas: {len(acessos)}")

    validacoes = gerar_validacoes(ativos, acessos)
    inserir_validacoes(cur, validacoes)
    n_pend = sum(1 for v in validacoes if v["status"] != "OK")
    print(f"  validacao_acessos pendentes: {n_pend}")

    divs = gerar_divergencias(ativos, desligados, acessos)
    inserir_divergencias(cur, divs)
    inserir_bi_divergencias(cur, divs, validacoes)
    print(f"  divergencias: {len(divs)}")

    resolucoes = gerar_resolucoes(validacoes, n=10)
    inserir_resolucoes(cur, resolucoes)
    print(f"  resolucoes: {len(resolucoes)} (resolvido_em > data_identificacao)")

    ativos_q, hist_q = gerar_quarentena(ativos)
    inserir_quarentena(cur, ativos_q, hist_q)
    print(f"  quarentena ativa: {len(ativos_q)}, historico: {len(hist_q)}")

    eventos = gerar_historico_rh(ativos, desligados, n=15)
    inserir_historico_rh(cur, eventos)
    print(f"  historico (RH): {len(eventos)}")

    con.commit()
    con.close()
    sz = DB_PATH.stat().st_size / 1024 / 1024
    print(f"\nOK: {DB_PATH} ({sz:.2f} MB)")


if __name__ == "__main__":
    main()
