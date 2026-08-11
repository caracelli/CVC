import shutil
from datetime import datetime
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from loguru import logger
from .schema import Base

_MAGIC_SQLITE = b"SQLite format 3\x00"   # cabecalho de todo arquivo SQLite valido


class ConexaoBancoDados:

    def __init__(self, caminho_db: str):
        Path(caminho_db).parent.mkdir(parents=True, exist_ok=True)
        self._caminho = caminho_db
        self._engine = create_engine(f"sqlite:///{caminho_db}", echo=False)
        self._SessionFactory = sessionmaker(bind=self._engine)

    def _garantir_banco_valido(self):
        """Se o arquivo do banco EXISTE mas NAO e' um SQLite valido (corrompido,
        escrita parcial na rede/SMB, arquivo trocado por texto/pointer), move-o
        para '.corrompido_<data>' e deixa o create_all recriar um banco novo —
        em vez de travar com 'file is not a database'. Arquivo de 0 bytes o
        SQLite ja trata como banco novo, entao nao mexe."""
        p = Path(self._caminho)
        try:
            if not p.exists() or p.stat().st_size == 0:
                return
            with open(p, "rb") as f:
                cabecalho = f.read(16)
        except OSError:
            return
        if cabecalho == _MAGIC_SQLITE:
            return   # banco valido
        self._engine.dispose()
        destino = p.with_name(p.name + f".corrompido_{datetime.now():%Y%m%d_%H%M%S}")
        try:
            shutil.move(str(p), str(destino))
            for ext in ("-wal", "-shm"):     # remove journais orfaos do corrompido
                orf = Path(str(p) + ext)
                if orf.exists():
                    try:
                        orf.unlink()
                    except OSError:
                        pass
            logger.warning(
                f"Banco INVALIDO (nao e' SQLite) em '{p}' — movido para "
                f"'{destino.name}'. Recriando um banco novo (sera repovoado no "
                f"processamento a partir da ENTRADA e das INTERACOES).")
        except Exception as e:
            logger.error(
                f"Banco em '{p}' nao e' um SQLite valido e nao consegui move-lo "
                f"({e!r}). Remova/renomeie o arquivo manualmente e rode de novo.")
            raise

    def inicializar(self):
        self._garantir_banco_valido()
        Base.metadata.create_all(self._engine)
        self._migrar()
        logger.info("Banco de dados inicializado.")

    def checkpoint(self):
        """Consolida o WAL no .db (TRUNCATE). O banco fica em journal_mode=WAL
        (setado por dobrar_interacoes); sem checkpoint, escritas ficam no
        .db-wal e o .db nao muda de tamanho/mtime — entao o Visualizador, que
        decide recopiar o cache por tamanho/mtime do .db, nao detecta a
        atualizacao e mostra dado velho. Chamado ao fim do processamento.

        Dispose primeiro pra liberar conexoes do pool (TRUNCATE exige que
        ninguem segure o WAL)."""
        import sqlite3
        try:
            self._engine.dispose()
            con = sqlite3.connect(self._caminho, timeout=15)
            try:
                con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            finally:
                con.close()
        except Exception as e:
            logger.warning(f"checkpoint WAL falhou (segue): {e!r}")

    # ------------------------------------------------------------------
    # Migrations incrementais
    # ------------------------------------------------------------------
    def _migrar(self):
        """Aplica mudancas incrementais de schema em bancos existentes.

        Cada bloco e' idempotente: detecta se a mudanca ja foi aplicada antes
        de aplicar de novo. Seguro pra rodar em todo startup."""
        with self._engine.connect() as conn:
            self._migrar_perfis_esperados(conn)
            self._migrar_snapshots_rh(conn)
            self._migrar_validacao_acessos(conn)
            self._migrar_matriz_cco(conn)
            self._migrar_log_importacoes_hash(conn)
            self._migrar_log_importacoes_dt_arquivo(conn)
            self._migrar_historico_unificado(conn)
            self._migrar_acessos_sistemas_pk_e_matching(conn)
            self._migrar_rh_ativos_tipo_vinculo(conn)
            self._migrar_rh_ativos_login(conn)
            self._migrar_rh_desligados_login(conn)
            self._migrar_gestor(conn)
            self._migrar_ciclo_vida(conn)
            self._migrar_ciclo_eventos_backfill(conn)

    def _cols(self, conn, tabela: str) -> set:
        return {row[1] for row in conn.execute(text(f"PRAGMA table_info({tabela})"))}

    def _tabelas(self, conn) -> set:
        return {row[0] for row in conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'"))}

    def _pk_cols(self, conn, tabela: str) -> list:
        """Devolve nomes das colunas PK na ordem definida na tabela."""
        rows = list(conn.execute(text(f"PRAGMA table_info({tabela})")))
        # row[5] e' o pk index (>0 indica posicao na PK)
        pks = [(r[5], r[1]) for r in rows if r[5] > 0]
        return [name for _, name in sorted(pks)]

    # ---- migrations especificas ---------------------------------------

    def _migrar_perfis_esperados(self, conn):
        if "perfis_esperados" not in self._tabelas(conn):
            return
        cols = self._cols(conn, "perfis_esperados")
        if "cargo_descricao" not in cols:
            conn.execute(text("ALTER TABLE perfis_esperados ADD COLUMN cargo_descricao TEXT"))
            conn.commit()
            logger.info("Migration: perfis_esperados.cargo_descricao adicionada.")
        if "acesso_manual" not in cols:
            conn.execute(text("ALTER TABLE perfis_esperados ADD COLUMN acesso_manual INTEGER DEFAULT 0"))
            conn.commit()
            logger.info("Migration: perfis_esperados.acesso_manual adicionada.")

    def _migrar_snapshots_rh(self, conn):
        if "snapshots_rh" not in self._tabelas(conn):
            return
        cols = self._cols(conn, "snapshots_rh")
        for coluna in ("novos", "alterados", "removidos"):
            if coluna not in cols:
                conn.execute(text(f"ALTER TABLE snapshots_rh ADD COLUMN {coluna} INTEGER DEFAULT 0"))
                conn.commit()
                logger.info(f"Migration: snapshots_rh.{coluna} adicionada.")

    def _migrar_validacao_acessos(self, conn):
        if "validacao_acessos" not in self._tabelas(conn):
            return
        cols = self._cols(conn, "validacao_acessos")
        if "situacao_acao" not in cols:
            conn.execute(text(
                "ALTER TABLE validacao_acessos ADD COLUMN situacao_acao TEXT DEFAULT 'PENDENTE'"))
            conn.commit()
            logger.info("Migration: validacao_acessos.situacao_acao adicionada.")
        # POR QUE esta linha caiu neste status (retorno da area 10/08/2026: a
        # tela mostrava "Em Analise" com esperado == encontrado e nao dizia o
        # motivo — a conta estava com status pendente no extrato).
        if "motivo_status" not in cols:
            conn.execute(text(
                "ALTER TABLE validacao_acessos ADD COLUMN motivo_status TEXT"))
            conn.commit()
            logger.info("Migration: validacao_acessos.motivo_status adicionada.")

    def _migrar_rh_ativos_tipo_vinculo(self, conn):
        if "rh_ativos" not in self._tabelas(conn):
            return
        if "tipo_vinculo" not in self._cols(conn, "rh_ativos"):
            conn.execute(text(
                "ALTER TABLE rh_ativos ADD COLUMN tipo_vinculo TEXT DEFAULT 'FUNCIONARIO'"))
            conn.commit()
            logger.info("Migration: rh_ativos.tipo_vinculo adicionada.")

    def _migrar_rh_ativos_login(self, conn):
        """Coluna 'login' (aditiva) em rh_ativos — chave de vinculo do diretorio
        AD (franqueado/prestador). Idempotente."""
        if "rh_ativos" not in self._tabelas(conn):
            return
        if "login" not in self._cols(conn, "rh_ativos"):
            conn.execute(text("ALTER TABLE rh_ativos ADD COLUMN login TEXT"))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_rh_ativos_login ON rh_ativos (login)"))
            conn.commit()
            logger.info("Migration: rh_ativos.login adicionada.")

    def _migrar_rh_desligados_login(self, conn):
        """Coluna 'login' (aditiva) em rh_desligados — chave do OU_Desligados do
        diretorio AD, que so tem login (sem matricula de RH). Idempotente."""
        if "rh_desligados" not in self._tabelas(conn):
            return
        if "login" not in self._cols(conn, "rh_desligados"):
            conn.execute(text("ALTER TABLE rh_desligados ADD COLUMN login TEXT"))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_rh_desligados_login ON rh_desligados (login)"))
            conn.commit()
            logger.info("Migration: rh_desligados.login adicionada.")

    def _migrar_gestor(self, conn):
        """Coluna 'gestor' (aditiva) em rh_ativos e matriz_cco — chave do
        casamento da CCO por (centro de custo + gestor)."""
        tabelas = self._tabelas(conn)
        if "rh_ativos" in tabelas and "gestor" not in self._cols(conn, "rh_ativos"):
            conn.execute(text("ALTER TABLE rh_ativos ADD COLUMN gestor TEXT"))
            conn.commit()
            logger.info("Migration: rh_ativos.gestor adicionada.")
        if "matriz_cco" in tabelas and "gestor" not in self._cols(conn, "matriz_cco"):
            conn.execute(text("ALTER TABLE matriz_cco ADD COLUMN gestor TEXT"))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_matriz_cco_gestor ON matriz_cco (gestor)"))
            conn.commit()
            logger.info("Migration: matriz_cco.gestor adicionada.")

    def _migrar_ciclo_vida(self, conn):
        """Tabela ciclo_vida_acesso (aditiva). CREATE IF NOT EXISTS — nao toca
        em nenhuma tabela existente. Guarda o ciclo Pendencia->Resolvido->Aderente
        com timestamps (first-wins) para medir tempo de tratamento."""
        if "ciclo_vida_acesso" in self._tabelas(conn):
            return
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ciclo_vida_acesso (
                matricula      TEXT NOT NULL,
                sistema        TEXT NOT NULL,
                perfil         TEXT,
                nome           TEXT,
                login          TEXT,
                cargo          TEXT,
                dt_pendencia   TEXT,
                dt_resolvido   TEXT,
                ticket         TEXT,
                dt_aderente    TEXT,
                dt_atualizacao TEXT,
                PRIMARY KEY (matricula, sistema)
            )"""))
        conn.commit()
        logger.info("Migration: tabela ciclo_vida_acesso criada.")

    def _migrar_ciclo_eventos_backfill(self, conn):
        """Backfill do CICLO 1 no log de eventos (ciclo_eventos_acesso) a partir
        do resumo ja existente em ciclo_vida_acesso. Aditivo e idempotente: a
        tabela ja foi criada pelo create_all; aqui so semeamos o 1o ciclo da base
        atual do cliente para o Historico aparecer sem reprocesso. O UNIQUE
        (matricula, sistema, ciclo, tipo_evento) impede duplicar em reprocessos —
        cada marco entra uma unica vez. Eventos novos (inclusive REABERTURAS) vem
        depois pelo RegistrarEventosAcesso durante o processamento."""
        tabelas = self._tabelas(conn)
        if "ciclo_eventos_acesso" not in tabelas or "ciclo_vida_acesso" not in tabelas:
            return
        # PENDENCIA / RESOLVIDO / ADERENTE do 1o ciclo, cada um so quando ha data.
        marcos = (
            ("PENDENCIA", "dt_pendencia", "NULL"),
            ("RESOLVIDO", "dt_resolvido", "ticket"),
            ("ADERENTE",  "dt_aderente",  "NULL"),
        )
        total = 0
        for tipo, col_data, col_ticket in marcos:
            res = conn.execute(text(f"""
                INSERT OR IGNORE INTO ciclo_eventos_acesso
                    (matricula, sistema, ciclo, tipo_evento, data_evento,
                     perfil, nome, login, cargo, ticket, detalhe, dt_registro)
                SELECT matricula, sistema, 1, '{tipo}', {col_data},
                       perfil, nome, login, cargo, {col_ticket}, NULL, datetime('now')
                FROM ciclo_vida_acesso
                WHERE {col_data} IS NOT NULL AND {col_data} <> ''
            """))
            total += res.rowcount if res.rowcount and res.rowcount > 0 else 0
        conn.commit()
        if total:
            logger.info(f"Migration: backfill de {total} evento(s) do ciclo 1 "
                        f"em ciclo_eventos_acesso (a partir de ciclo_vida_acesso).")

    def _migrar_matriz_cco(self, conn):
        # matriz_organizacional foi substituida por matriz_cco
        tabelas = self._tabelas(conn)
        if "matriz_organizacional" in tabelas and "matriz_cco" not in tabelas:
            conn.execute(text("DROP TABLE matriz_organizacional"))
            conn.commit()
            logger.info("Migration: matriz_organizacional removida (substituida por matriz_cco).")

    def _migrar_log_importacoes_hash(self, conn):
        if "log_importacoes" not in self._tabelas(conn):
            return
        cols = self._cols(conn, "log_importacoes")
        if "hash_arquivo" not in cols:
            conn.execute(text("ALTER TABLE log_importacoes ADD COLUMN hash_arquivo TEXT"))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_log_importacoes_hash_arquivo "
                "ON log_importacoes (hash_arquivo)"))
            conn.commit()
            logger.info("Migration: log_importacoes.hash_arquivo adicionada.")

    def _migrar_log_importacoes_dt_arquivo(self, conn):
        if "log_importacoes" not in self._tabelas(conn):
            return
        if "dt_arquivo" not in self._cols(conn, "log_importacoes"):
            conn.execute(text("ALTER TABLE log_importacoes ADD COLUMN dt_arquivo DATETIME"))
            conn.commit()
            logger.info("Migration: log_importacoes.dt_arquivo adicionada.")

    def _migrar_historico_unificado(self, conn):
        """Unifica historico_rh -> historico com coluna entidade.

        Estrategia (idempotente):
        1. Se historico_rh existe e historico nao: cria historico (via SQLAlchemy
           ja fez no create_all) e copia dados de historico_rh, preenchendo
           entidade e chave_entidade.
        2. Se historico ja tem dados: pula.
        3. Apaga historico_rh apos copia bem sucedida.
        """
        tabelas = self._tabelas(conn)
        if "historico_rh" not in tabelas:
            return  # ja migrado ou banco novo
        # Garantir que a coluna entidade existe em historico_rh para uniformizar
        # antes de copiar (banco antigo nao tem).
        cols_old = self._cols(conn, "historico_rh")

        # Conta linhas em historico (nova)
        ja_tem = conn.execute(text("SELECT COUNT(*) FROM historico")).scalar() or 0
        if ja_tem == 0:
            # Copia dados do historico_rh -> historico
            for col_compat in ("tipo", "matricula", "campos_alterados", "dados_anterior", "dados_novo"):
                if col_compat not in cols_old:
                    cols_old.add(col_compat)  # so pra evitar erro abaixo
            conn.execute(text("""
                INSERT INTO historico (data_snapshot, entidade, chave_entidade,
                    tipo_mudanca, campos_alterados, dados_anterior, dados_novo,
                    dt_registro, tipo, matricula)
                SELECT data_snapshot,
                       CASE WHEN tipo='DESLIGADO' THEN 'RH_DESLIGADO' ELSE 'RH_ATIVO' END,
                       matricula,
                       tipo_mudanca, campos_alterados, dados_anterior, dados_novo,
                       dt_registro, tipo, matricula
                FROM historico_rh
            """))
            conn.commit()
            copiados = conn.execute(text("SELECT COUNT(*) FROM historico")).scalar()
            logger.info(f"Migration: {copiados} registros copiados de historico_rh -> historico.")
        else:
            logger.info("Migration: tabela historico ja populada — pulando copia de historico_rh.")

        conn.execute(text("DROP TABLE historico_rh"))
        conn.commit()
        logger.info("Migration: historico_rh removida (unificada em historico).")

    def _migrar_acessos_sistemas_pk_e_matching(self, conn):
        """Migra acessos_sistemas para PK (sistema, usuario, perfil) e adiciona
        colunas de matching.

        SQLite nao suporta ALTER PRIMARY KEY: precisamos recriar a tabela.
        Estrategia idempotente:
        - Se PK ja e' (sistema, usuario, perfil) E ja tem colunas matching: skip
        - Senao: cria acessos_sistemas_new com schema novo, copia dados (deduplica
          por (sistema, usuario, perfil) na copia), troca os nomes.
        """
        if "acessos_sistemas" not in self._tabelas(conn):
            return

        cols = self._cols(conn, "acessos_sistemas")
        pk = self._pk_cols(conn, "acessos_sistemas")
        pk_ok = pk == ["sistema", "usuario", "perfil"]
        cols_matching_ok = {"metodo_vinculacao", "score_vinculacao", "candidatos_matricula"} <= cols
        email_existe = "email" in cols

        if pk_ok and cols_matching_ok and email_existe:
            return  # ja migrado

        logger.warning(
            f"Migration: recriando acessos_sistemas. PK atual={pk}, "
            f"matching_ok={cols_matching_ok}, email={email_existe}.")

        # Coleta colunas existentes para SELECT seguro (lista o que de fato
        # existe pra nao quebrar em bancos parciais)
        cols_comuns_possiveis = [
            "sistema", "usuario", "perfil", "nome_usuario", "cpf",
            "situacao", "data_criacao", "ultimo_acesso", "filial",
            "matricula_vinculada", "arquivo_origem", "dt_importacao",
        ]
        cols_select = [c for c in cols_comuns_possiveis if c in cols]
        # email a parte: legado tinha email mas o repositorio gravava None
        if email_existe:
            cols_select.insert(cols_select.index("cpf") + 1, "email")

        select_expr = ", ".join(cols_select)
        # Coluna list pra INSERT na tabela nova (mesmo nome)
        insert_cols = list(cols_select)

        conn.execute(text("DROP TABLE IF EXISTS acessos_sistemas_new"))
        conn.execute(text("""
            CREATE TABLE acessos_sistemas_new (
                sistema TEXT NOT NULL,
                usuario TEXT NOT NULL,
                perfil TEXT NOT NULL,
                nome_usuario TEXT,
                cpf TEXT,
                email TEXT,
                situacao TEXT,
                data_criacao DATE,
                ultimo_acesso DATETIME,
                filial TEXT,
                matricula_vinculada TEXT,
                metodo_vinculacao TEXT,
                score_vinculacao REAL,
                candidatos_matricula TEXT,
                arquivo_origem TEXT,
                dt_importacao DATETIME,
                PRIMARY KEY (sistema, usuario, perfil)
            )
        """))
        # Copia deduplicando: para cada (sistema, usuario, perfil), mantem
        # a linha mais recente (max dt_importacao). Garante zero perda.
        # Em banco legado com PK (sistema, usuario), uma unica linha existia
        # por par; ela vai pra tabela nova como (sistema, usuario, perfil_unico).
        conn.execute(text(f"""
            INSERT OR REPLACE INTO acessos_sistemas_new ({", ".join(insert_cols)})
            SELECT {select_expr} FROM acessos_sistemas
            WHERE perfil IS NOT NULL AND perfil <> ''
        """))
        copiados = conn.execute(text("SELECT COUNT(*) FROM acessos_sistemas_new")).scalar()
        conn.execute(text("DROP TABLE acessos_sistemas"))
        conn.execute(text("ALTER TABLE acessos_sistemas_new RENAME TO acessos_sistemas"))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_acessos_sistemas_cpf "
            "ON acessos_sistemas (cpf)"))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_acessos_sistemas_matricula_vinculada "
            "ON acessos_sistemas (matricula_vinculada)"))
        conn.commit()
        logger.info(
            f"Migration: acessos_sistemas recriada com PK (sistema, usuario, perfil) "
            f"+ colunas de matching ({copiados} registros copiados).")

    # ------------------------------------------------------------------
    def sessao(self) -> Session:
        return self._SessionFactory()

    @property
    def engine(self):
        return self._engine
