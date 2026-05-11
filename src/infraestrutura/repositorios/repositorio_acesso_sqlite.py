from datetime import datetime
from typing import List

from loguru import logger

from dominio.entidades.perfil_acesso import PerfilAcesso
from dominio.interfaces.i_repositorio_acesso import IRepositorioAcesso
from dominio.objetos_valor.sistema import Sistema
from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import AcessoSistema


class RepositorioAcessoSqlite(IRepositorioAcesso):

    def __init__(self, conexao: ConexaoBancoDados):
        self._conexao = conexao

    def salvar_lote(self, perfis: List[PerfilAcesso], arquivo_origem: str = "") -> None:
        with self._conexao.sessao() as sessao:
            for p in perfis:
                sessao.merge(AcessoSistema(
                    sistema=p.sistema.value,
                    usuario=p.usuario,
                    nome_usuario=p.nome_usuario,
                    cpf=None,
                    email=None,
                    perfil=p.perfil,
                    situacao=p.situacao,
                    data_criacao=p.data_criacao,
                    ultimo_acesso=p.ultimo_acesso,
                    matricula_vinculada=p.matricula_vinculada,
                    arquivo_origem=arquivo_origem,
                    dt_importacao=datetime.now(),
                ))
            sessao.commit()
        logger.info(f"{len(perfis)} acessos gravados — {perfis[0].sistema.value if perfis else ''}")

    def salvar(self, perfil: PerfilAcesso) -> None:
        self.salvar_lote([perfil])

    def obter_por_sistema(self, sistema: Sistema) -> List[PerfilAcesso]:
        with self._conexao.sessao() as sessao:
            rows = sessao.query(AcessoSistema).filter_by(sistema=sistema.value).all()
            return [self._para_perfil(r) for r in rows]

    def obter_por_usuario(self, usuario: str) -> List[PerfilAcesso]:
        with self._conexao.sessao() as sessao:
            rows = sessao.query(AcessoSistema).filter_by(usuario=usuario).all()
            return [self._para_perfil(r) for r in rows]

    def _para_perfil(self, r: AcessoSistema) -> PerfilAcesso:
        return PerfilAcesso(
            usuario=r.usuario,
            nome_usuario=r.nome_usuario or "",
            sistema=Sistema(r.sistema),
            perfil=r.perfil or "",
            situacao=r.situacao or "",
            data_criacao=r.data_criacao,
            ultimo_acesso=r.ultimo_acesso,
            matricula_vinculada=r.matricula_vinculada,
        )
