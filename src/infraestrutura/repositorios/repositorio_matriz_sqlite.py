from datetime import datetime
from typing import Dict, List

from loguru import logger

from dominio.entidades.perfil_esperado import PerfilEsperado
from dominio.objetos_valor.sistema import Sistema
from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import MatrizOrganizacionalModel, PerfilEsperadoModel


class RepositorioMatrizSqlite:

    def __init__(self, conexao: ConexaoBancoDados):
        self._conexao = conexao

    def salvar_perfis_esperados(self, perfis: List[PerfilEsperado], arquivo_origem: str = ""):
        with self._conexao.sessao() as sessao:
            sessao.query(PerfilEsperadoModel).delete()
            for p in perfis:
                sessao.add(PerfilEsperadoModel(
                    cargo_codigo=p.cargo_codigo,
                    cargo_descricao=p.cargo_descricao,
                    sistema=p.sistema.value,
                    perfil=p.perfil,
                    arquivo_origem=arquivo_origem,
                    dt_importacao=datetime.now(),
                ))
            sessao.commit()
        logger.info(f"{len(perfis)} perfis esperados gravados no banco.")

    def obter_perfis_esperados(self) -> List[PerfilEsperado]:
        with self._conexao.sessao() as sessao:
            rows = sessao.query(PerfilEsperadoModel).all()
            return [
                PerfilEsperado(
                    cargo_codigo=r.cargo_codigo,
                    cargo_descricao=r.cargo_descricao or "",
                    sistema=Sistema(r.sistema),
                    perfil=r.perfil,
                )
                for r in rows
            ]

    def salvar_organizacional(self, registros: List[Dict], arquivo_origem: str = ""):
        with self._conexao.sessao() as sessao:
            sessao.query(MatrizOrganizacionalModel).delete()
            for r in registros:
                sessao.merge(MatrizOrganizacionalModel(
                    cargo_codigo=r["cargo_codigo"],
                    cargo_descricao=r.get("cargo_descricao", ""),
                    departamento=r.get("departamento", ""),
                    centro_custo=r.get("centro_custo", ""),
                    arquivo_origem=arquivo_origem,
                    dt_importacao=datetime.now(),
                ))
            sessao.commit()
        logger.info(f"{len(registros)} cargos organizacionais gravados no banco.")
