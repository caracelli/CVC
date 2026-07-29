from datetime import datetime
from sqlalchemy import (
    Boolean, Column, Float, String, Date, DateTime, Integer, Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class RhAtivo(Base):
    __tablename__ = "rh_ativos"

    matricula = Column(String, primary_key=True)
    nome = Column(String, nullable=False)
    cpf = Column(String, nullable=False, index=True)
    cargo_codigo = Column(String)
    cargo_descricao = Column(String)
    centro_custo_codigo = Column(String)
    centro_custo_nome = Column(String)
    departamento = Column(String)
    data_admissao = Column(Date)
    email = Column(String)
    situacao = Column(String)
    gestor = Column(String)   # "Nome Gestor" do RH — chave do casamento CCO
    # FUNCIONARIO (CLT proprio) | TERCEIRO | FRANQUEADO | PRESTADOR
    tipo_vinculo = Column(String, default="FUNCIONARIO")
    # Login do diretorio (AD) — chave de vinculo p/ franqueado/prestador, cujo
    # `usuario` do extrato de acesso == este login. Vazio p/ CLT (RH nao tem login).
    login = Column(String, index=True)
    empresa = Column(String)
    local_trabalho = Column(String)
    arquivo_origem = Column(String)
    dt_importacao = Column(DateTime, default=datetime.now)


class RhDesligado(Base):
    __tablename__ = "rh_desligados"

    matricula = Column(String, primary_key=True)
    nome = Column(String, nullable=False)
    cpf = Column(String, nullable=False, index=True)
    cargo_codigo = Column(String)
    cargo_descricao = Column(String)
    centro_custo_codigo = Column(String)
    centro_custo_nome = Column(String)
    departamento = Column(String)
    data_admissao = Column(Date)
    data_desligamento = Column(Date)
    email = Column(String)
    empresa = Column(String)
    arquivo_origem = Column(String)
    dt_importacao = Column(DateTime, default=datetime.now)


class SnapshotRh(Base):
    __tablename__ = "snapshots_rh"

    id = Column(Integer, primary_key=True, autoincrement=True)
    data_snapshot = Column(Date, nullable=False, index=True)
    tipo = Column(String, nullable=False)  # ATIVO / DESLIGADO
    total_registros = Column(Integer)
    novos = Column(Integer, default=0)
    alterados = Column(Integer, default=0)
    removidos = Column(Integer, default=0)
    arquivo_parquet = Column(String)
    dt_criacao = Column(DateTime, default=datetime.now)


class Historico(Base):
    """Trilha de auditoria unificada (CDC).

    Substitui historico_rh: agora qualquer entidade pode registrar mudancas
    aqui — RH (ativos/desligados) e acessos de sistema, e qualquer outra
    entidade que surgir. Para nao quebrar compatibilidade, mantemos as
    colunas legadas tipo e matricula populadas para entidades RH."""

    __tablename__ = "historico"

    id = Column(Integer, primary_key=True, autoincrement=True)
    data_snapshot = Column(Date, nullable=False, index=True)
    entidade = Column(String, nullable=False, index=True)  # RH_ATIVO / RH_DESLIGADO / ACESSO_SISTEMA / ...
    chave_entidade = Column(String, nullable=False, index=True)  # matricula (RH) ou sistema|usuario|perfil (acesso)
    tipo_mudanca = Column(String, nullable=False, index=True)  # NOVO / ALTERADO / REMOVIDO
    campos_alterados = Column(Text)                            # CSV dos campos (so ALTERADO)
    dados_anterior = Column(Text)                              # JSON (null em NOVO)
    dados_novo = Column(Text)                                  # JSON (null em REMOVIDO)
    dt_registro = Column(DateTime, default=datetime.now)

    # --- compatibilidade com leitura legada (campos populados para entidades RH) ---
    tipo = Column(String, index=True)        # ATIVO / DESLIGADO (espelho de entidade para RH)
    matricula = Column(String, index=True)   # espelho de chave_entidade para RH


class AcessoSistema(Base):
    """Um registro por (sistema, usuario, perfil).

    A PK composta com perfil e' fundamental: usuarios sao multi-perfil na maioria
    dos sistemas. Sem perfil na PK, o merge sobrescreve e so o ultimo perfil
    sobrevive — bug que o SIG escancarou (mediana de 88 perfis/usuario).
    """
    __tablename__ = "acessos_sistemas"

    sistema = Column(String, primary_key=True)
    usuario = Column(String, primary_key=True)
    perfil = Column(String, primary_key=True)
    nome_usuario = Column(String)
    cpf = Column(String, index=True)
    email = Column(String)
    situacao = Column(String)
    data_criacao = Column(Date)
    ultimo_acesso = Column(DateTime)
    filial = Column(String)
    matricula_vinculada = Column(String, index=True)
    # Cascata de vinculacao (matching multi-chave): registra como conseguimos
    # ligar este acesso a uma matricula do RH. Permite auditoria do match e
    # filtros por nivel de confianca no painel.
    metodo_vinculacao = Column(String)     # CPF / EMAIL / CPF_PARCIAL_NOME / NOME / FUZZY / NAO_VINCULADO
    score_vinculacao = Column(Float)       # 1.0 (CPF) ... 0.5 (fuzzy) ... 0.0 (nao vinculado)
    candidatos_matricula = Column(Text)    # JSON list de matriculas candidatas quando ambiguo
    arquivo_origem = Column(String)
    dt_importacao = Column(DateTime, default=datetime.now)


class CatalogoPerfil(Base):
    """Catalogo de perfis por sistema (codigo -> nome legivel).

    Necessario para sistemas que exportam acessos como codigo numerico
    (SIG, Oracle EBS) e fornecem o de-para em arquivo separado. Tambem
    serve para os outros sistemas, com codigo=nome (idempotente).

    Familia: prefixo derivado do nome (ACESSO_HOTEL, ATD, CAD, ...), util
    para agregacoes no painel.
    """
    __tablename__ = "catalogo_perfis"

    sistema = Column(String, primary_key=True)
    codigo = Column(String, primary_key=True)
    nome = Column(String, nullable=False)
    familia = Column(String, index=True)
    descricao = Column(Text)
    arquivo_origem = Column(String)
    dt_importacao = Column(DateTime, default=datetime.now)


class LogImportacao(Base):
    __tablename__ = "log_importacoes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    arquivo = Column(String, nullable=False)
    tipo = Column(String, nullable=False)
    total_registros = Column(Integer)
    status = Column(String)  # SUCESSO / ERRO
    mensagem_erro = Column(Text)
    hash_arquivo = Column(String, index=True)  # md5 do conteudo — detecta reimportacao
    dt_importacao = Column(DateTime, default=datetime.now)
    dt_arquivo = Column(DateTime)  # data de modificacao do PROPRIO arquivo (disponibilizacao)


class PerfilEsperadoModel(Base):
    __tablename__ = "perfis_esperados"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cargo_codigo = Column(String, nullable=False, index=True)
    cargo_descricao = Column(String)
    sistema = Column(String, nullable=False)
    perfil = Column(String, nullable=False)
    acesso_manual = Column(Boolean, default=False)
    arquivo_origem = Column(String)
    dt_importacao = Column(DateTime, default=datetime.now)


class MatrizCcoModel(Base):
    __tablename__ = "matriz_cco"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cc = Column(String, nullable=False, index=True)
    cc_nome = Column(String)
    gestor = Column(String, index=True)   # "Nome Gestor" da CCO — chave do casamento
    funcao = Column(String, index=True)
    sistema = Column(String, nullable=False)
    perfil = Column(String, nullable=False)
    arquivo_origem = Column(String)
    dt_importacao = Column(DateTime, default=datetime.now)


class ValidacaoAcessoModel(Base):
    __tablename__ = "validacao_acessos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    matricula = Column(String, index=True)
    cpf = Column(String, index=True)
    nome = Column(String)
    email = Column(String)
    centro_custo_codigo = Column(String, index=True)
    centro_custo_nome = Column(String)
    cargo_codigo = Column(String)
    cargo_descricao = Column(String)
    sistema = Column(String, nullable=False)
    perfil_esperado = Column(String)
    perfil_atual = Column(String)
    acesso_manual = Column(Boolean, default=False)
    status = Column(String, nullable=False, index=True)
    situacao_acao = Column(String, default="PENDENTE", index=True)  # PENDENTE / RESOLVIDO
    origem_matriz = Column(String)
    dt_processamento = Column(DateTime, default=datetime.now)


class CicloVidaAcessoModel(Base):
    """Ciclo de vida de uma pendencia de acesso: Pendencia -> Resolvido (ticket)
    -> Aderente (acesso OK). Append/upsert IDEMPOTENTE (first-wins): cada data so
    e' gravada na PRIMEIRA vez; processamentos seguintes nao sobrescrevem. Serve
    de base p/ o tempo de tratamento (Historico) e tempo medio (Visao Geral)."""
    __tablename__ = "ciclo_vida_acesso"

    # Chave (matricula, sistema): "a pessoa esta resolvida nesse sistema".
    # Por perfil deixaria opcoes de Em Analise penduradas quando a pessoa
    # escolhe uma das N e as outras somem.
    matricula = Column(String, primary_key=True)
    sistema = Column(String, primary_key=True)
    perfil = Column(String)   # perfil representativo (esperado/atual) p/ exibicao
    nome = Column(String)
    login = Column(String)
    cargo = Column(String)
    dt_pendencia = Column(String)   # ISO datetime — 1a vez vista como pendencia
    dt_resolvido = Column(String)   # ISO datetime — quando resolvida (ticket Jira)
    ticket = Column(String)         # numero do chamado Jira
    dt_aderente = Column(String)    # ISO datetime — 1a vez conforme (acesso OK)
    dt_atualizacao = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class CicloEventosAcessoModel(Base):
    """Log de eventos (APPEND-ONLY) do ciclo de vida de acesso por
    (matricula, sistema). Cada transicao e' UMA linha datada:

        PENDENCIA -> RESOLVIDO -> ADERENTE   (um ciclo)

    e suporta REABERTURA: apos ADERENTE, uma nova PENDENCIA abre o ciclo
    seguinte (ciclo = ciclo anterior + 1). O "status atual" de um
    (matricula, sistema) e' simplesmente o ULTIMO evento.

    Aditivo e independente: NAO substitui ciclo_vida_acesso (que segue como
    resumo do 1o ciclo / tempo de tratamento). O UNIQUE garante idempotencia —
    reprocessar nao duplica o mesmo marco do mesmo ciclo."""
    __tablename__ = "ciclo_eventos_acesso"
    __table_args__ = (
        UniqueConstraint("matricula", "sistema", "ciclo", "tipo_evento",
                         name="uq_ciclo_eventos_marco"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    matricula = Column(String, nullable=False, index=True)
    sistema = Column(String, nullable=False, index=True)
    ciclo = Column(Integer, nullable=False, default=1)
    tipo_evento = Column(String, nullable=False)  # PENDENCIA / RESOLVIDO / ADERENTE
    data_evento = Column(String)                  # ISO datetime do marco
    perfil = Column(String)                        # perfil representativo p/ exibicao
    nome = Column(String)
    login = Column(String)
    cargo = Column(String)
    ticket = Column(String)                        # numero do chamado (so RESOLVIDO)
    detalhe = Column(String)                        # texto livre (ex.: motivo da reabertura)
    dt_registro = Column(DateTime, default=datetime.now)


class DivergenciaModel(Base):
    __tablename__ = "divergencias"

    id = Column(String, primary_key=True)
    tipo = Column(String, nullable=False, index=True)
    sistema = Column(String, nullable=False)
    usuario = Column(String, nullable=False)
    nome_usuario = Column(String)
    matricula = Column(String, index=True)
    perfil_encontrado = Column(String)
    perfil_esperado = Column(String)
    descricao = Column(Text)
    data_identificacao = Column(DateTime)
    resolvida = Column(Boolean, default=False)
    dt_importacao = Column(DateTime, default=datetime.now)


# ---- compat: alias para nao quebrar imports legados -----------------------
# Antes da unificacao, existia HistoricoRh; agora e' Historico com coluna
# entidade. Mantemos o nome antigo importavel para qualquer codigo legado
# que nao tenha sido migrado ainda.
HistoricoRh = Historico
