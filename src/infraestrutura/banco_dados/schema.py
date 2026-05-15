from datetime import datetime
from sqlalchemy import Boolean, Column, String, Date, DateTime, Integer, Text
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
    arquivo_parquet = Column(String)
    dt_criacao = Column(DateTime, default=datetime.now)


class AcessoSistema(Base):
    __tablename__ = "acessos_sistemas"

    sistema = Column(String, primary_key=True)
    usuario = Column(String, primary_key=True)
    nome_usuario = Column(String)
    cpf = Column(String, index=True)
    email = Column(String)
    perfil = Column(String)
    situacao = Column(String)
    data_criacao = Column(Date)
    ultimo_acesso = Column(DateTime)
    filial = Column(String)
    matricula_vinculada = Column(String, index=True)
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
    dt_importacao = Column(DateTime, default=datetime.now)


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
    origem_matriz = Column(String)
    dt_processamento = Column(DateTime, default=datetime.now)


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
