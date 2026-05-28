"""Teste manual de migration: cria banco com schema antigo, popula dados,
roda migration e verifica preservacao.

Cobre:
- acessos_sistemas com PK antiga (sistema, usuario) -> nova (sistema, usuario, perfil)
- historico_rh -> historico (com entidade derivada de tipo)
- log_importacoes sem hash_arquivo -> com
"""
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sqlalchemy import text
from infraestrutura.banco_dados.conexao import ConexaoBancoDados


def criar_schema_legado(db_path):
    """Recria o schema como estava ANTES das mudancas."""
    c = sqlite3.connect(db_path)
    cur = c.cursor()
    cur.executescript("""
        CREATE TABLE acessos_sistemas (
            sistema VARCHAR NOT NULL,
            usuario VARCHAR NOT NULL,
            nome_usuario VARCHAR,
            cpf VARCHAR,
            email VARCHAR,
            perfil VARCHAR,
            situacao VARCHAR,
            data_criacao DATE,
            ultimo_acesso DATETIME,
            filial VARCHAR,
            matricula_vinculada VARCHAR,
            arquivo_origem VARCHAR,
            dt_importacao DATETIME,
            PRIMARY KEY (sistema, usuario)
        );

        CREATE TABLE historico_rh (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_snapshot DATE NOT NULL,
            tipo VARCHAR NOT NULL,
            matricula VARCHAR NOT NULL,
            tipo_mudanca VARCHAR NOT NULL,
            campos_alterados TEXT,
            dados_anterior TEXT,
            dados_novo TEXT,
            dt_registro DATETIME
        );

        CREATE TABLE log_importacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            arquivo VARCHAR NOT NULL,
            tipo VARCHAR NOT NULL,
            total_registros INTEGER,
            status VARCHAR,
            mensagem_erro TEXT,
            dt_importacao DATETIME
        );

        CREATE TABLE rh_ativos (
            matricula VARCHAR PRIMARY KEY,
            nome VARCHAR NOT NULL,
            cpf VARCHAR NOT NULL,
            cargo_codigo VARCHAR, cargo_descricao VARCHAR,
            centro_custo_codigo VARCHAR, centro_custo_nome VARCHAR,
            departamento VARCHAR, data_admissao DATE,
            email VARCHAR, situacao VARCHAR,
            empresa VARCHAR, local_trabalho VARCHAR,
            arquivo_origem VARCHAR, dt_importacao DATETIME
        );
    """)
    c.commit()
    c.close()


def popular_dados(db_path):
    c = sqlite3.connect(db_path)
    cur = c.cursor()
    # 3 acessos antes da migration (PK antigo: 1 por par sistema/usuario)
    cur.executemany(
        "INSERT INTO acessos_sistemas (sistema, usuario, nome_usuario, "
        "cpf, email, perfil, situacao, matricula_vinculada, arquivo_origem, "
        "dt_importacao) VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            ("SYSTUR", "user1", "Joao", "11111111111", "joao@x", "PERFIL_A", "ATIVO", "MAT1", "arq.csv", "2026-05-26 10:00:00"),
            ("SYSTUR", "user2", "Maria", "22222222222", "maria@x", "PERFIL_B", "ATIVO", "MAT2", "arq.csv", "2026-05-26 10:00:00"),
            ("SIGOT",  "user3", "Pedro", "33333333333", "pedro@x", "PERFIL_C", "ATIVO", "MAT3", "arq.csv", "2026-05-26 10:00:00"),
        ]
    )
    # 5 registros de historico_rh (2 ativos, 3 desligados)
    cur.executemany(
        "INSERT INTO historico_rh (data_snapshot, tipo, matricula, "
        "tipo_mudanca, dados_novo, dt_registro) VALUES (?,?,?,?,?,?)",
        [
            ("2026-05-20", "ATIVO", "MAT1", "NOVO", '{"nome": "Joao"}', "2026-05-20 10:00:00"),
            ("2026-05-21", "ATIVO", "MAT2", "ALTERADO", '{"cargo": "X"}', "2026-05-21 10:00:00"),
            ("2026-05-22", "DESLIGADO", "MAT3", "NOVO", '{"nome": "Pedro"}', "2026-05-22 10:00:00"),
            ("2026-05-23", "DESLIGADO", "MAT4", "NOVO", '{"nome": "Ana"}', "2026-05-23 10:00:00"),
            ("2026-05-24", "ATIVO", "MAT5", "REMOVIDO", '{"nome": "Bia"}', "2026-05-24 10:00:00"),
        ]
    )
    # 2 logs
    cur.executemany(
        "INSERT INTO log_importacoes (arquivo, tipo, total_registros, status) VALUES (?,?,?,?)",
        [("arq1.csv", "SYSTUR", 100, "SUCESSO"), ("arq2.csv", "SIGOT", 50, "SUCESSO")]
    )
    c.commit()
    c.close()


def main():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db = tmp.name
    try:
        print(f"DB: {db}")
        print("\n=== 1. Criando schema legado ===")
        criar_schema_legado(db)
        popular_dados(db)
        print("  schema legado criado + 3 acessos + 5 historico + 2 logs")

        # Pre-migration verificacao
        c = sqlite3.connect(db)
        pks = [r[1] for r in c.execute("PRAGMA table_info(acessos_sistemas)") if r[5] > 0]
        print(f"  PK antes da migration: {pks}")
        n_acessos = c.execute("SELECT COUNT(*) FROM acessos_sistemas").fetchone()[0]
        n_hist_rh = c.execute("SELECT COUNT(*) FROM historico_rh").fetchone()[0]
        n_log = c.execute("SELECT COUNT(*) FROM log_importacoes").fetchone()[0]
        cols_log = [r[1] for r in c.execute("PRAGMA table_info(log_importacoes)")]
        print(f"  acessos: {n_acessos}, historico_rh: {n_hist_rh}, log: {n_log}")
        print(f"  log_importacoes cols: {cols_log}")
        c.close()

        print("\n=== 2. Rodando migration ===")
        cx = ConexaoBancoDados(db)
        cx.inicializar()

        # Pos-migration verificacao
        print("\n=== 3. Verificando preservacao ===")
        c = sqlite3.connect(db)
        # PK nova
        pks = [r[1] for r in c.execute("PRAGMA table_info(acessos_sistemas)") if r[5] > 0]
        assert pks == ["sistema", "usuario", "perfil"], f"PK errada: {pks}"
        print(f"  PK pos migration: {pks} OK")

        # Acessos preservados (3)
        n = c.execute("SELECT COUNT(*) FROM acessos_sistemas").fetchone()[0]
        assert n == n_acessos, f"perdeu acessos: {n} vs {n_acessos}"
        print(f"  acessos preservados: {n} OK")

        # email nao mais NULL hardcoded — agora deveria estar preservado
        emails = [r[0] for r in c.execute("SELECT email FROM acessos_sistemas ORDER BY usuario")]
        print(f"  emails preservados: {emails}")
        assert all(e for e in emails), "email NULL onde deveria ter valor"

        # historico_rh nao existe mais; historico tem os 5 com entidade correta
        tabs = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "historico_rh" not in tabs, "historico_rh ainda existe"
        assert "historico" in tabs
        n_hist = c.execute("SELECT COUNT(*) FROM historico").fetchone()[0]
        assert n_hist == n_hist_rh, f"perdeu historico: {n_hist} vs {n_hist_rh}"
        print(f"  historico unificado: {n_hist} OK (historico_rh removida)")

        # Verificar entidades
        entidades = sorted([r[0] for r in c.execute(
            "SELECT entidade FROM historico ORDER BY id")])
        esperadas = sorted(["RH_ATIVO", "RH_ATIVO", "RH_DESLIGADO", "RH_DESLIGADO", "RH_ATIVO"])
        assert entidades == esperadas, f"entidades erradas: {entidades}"
        print(f"  entidades RH derivadas corretamente: {entidades}")

        # chave_entidade = matricula
        for row in c.execute("SELECT matricula, chave_entidade FROM historico"):
            assert row[0] == row[1], f"chave_entidade != matricula: {row}"
        print(f"  chave_entidade espelha matricula OK")

        # log_importacoes agora tem hash_arquivo
        cols_log_new = [r[1] for r in c.execute("PRAGMA table_info(log_importacoes)")]
        assert "hash_arquivo" in cols_log_new, "falta hash_arquivo"
        print(f"  log_importacoes.hash_arquivo presente OK")

        # Catalogo_perfis criada
        assert "catalogo_perfis" in tabs
        print(f"  catalogo_perfis criada OK")

        c.close()
        print("\nTODOS OS CHECKS PASSARAM — migration preservou tudo.")
    finally:
        try:
            os.unlink(db)
        except Exception:
            pass


if __name__ == "__main__":
    main()
