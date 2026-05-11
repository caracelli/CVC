from datetime import datetime
from sqlalchemy import Column, String, Date, DateTime, Integer, Text
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
