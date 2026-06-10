from datetime import datetime
from typing import Dict, List

from loguru import logger

from dominio.entidades.perfil_esperado import PerfilEsperado
from dominio.objetos_valor.sistema import Sistema
from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import MatrizCcoModel, PerfilEsperadoModel, ValidacaoAcessoModel


class RepositorioMatrizSqlite:

    def __init__(self, conexao: ConexaoBancoDados):
        self._conexao = conexao

    def salvar_perfis_esperados(self, perfis: List[PerfilEsperado], arquivo_origem: str = ""):
        if not perfis:
            return
        # Substituicao POR SISTEMA: apaga so os perfis dos sistemas presentes
        # neste lote. Importar a matriz de um sistema NAO toca nos outros
        # (isolamento — antes era DELETE global e zerava todas as matrizes).
        sistemas = {p.sistema.value for p in perfis}
        with self._conexao.sessao() as sessao:
            sessao.query(PerfilEsperadoModel).filter(
                PerfilEsperadoModel.sistema.in_(sistemas)
            ).delete(synchronize_session=False)
            for p in perfis:
                sessao.add(PerfilEsperadoModel(
                    cargo_codigo=p.cargo_codigo,
                    cargo_descricao=p.cargo_descricao,
                    sistema=p.sistema.value,
                    perfil=p.perfil,
                    acesso_manual=bool(p.acesso_manual),
                    arquivo_origem=arquivo_origem,
                    dt_importacao=datetime.now(),
                ))
            sessao.commit()
        logger.info(
            f"{len(perfis)} perfis esperados gravados ({', '.join(sorted(sistemas))})."
        )

    def obter_perfis_esperados(self) -> List[PerfilEsperado]:
        with self._conexao.sessao() as sessao:
            rows = sessao.query(PerfilEsperadoModel).all()
            return [
                PerfilEsperado(
                    cargo_codigo=r.cargo_codigo,
                    cargo_descricao=r.cargo_descricao or "",
                    sistema=Sistema(r.sistema),
                    perfil=r.perfil,
                    acesso_manual=bool(r.acesso_manual),
                )
                for r in rows
            ]

    def salvar_cco(self, registros: List[Dict], arquivo_origem: str = ""):
        if not registros:
            return
        # Substituicao POR SISTEMA tambem na CCO: apaga so os mapeamentos dos
        # sistemas presentes neste arquivo, preservando os demais.
        sistemas = {r["sistema"] for r in registros}
        with self._conexao.sessao() as sessao:
            sessao.query(MatrizCcoModel).filter(
                MatrizCcoModel.sistema.in_(sistemas)
            ).delete(synchronize_session=False)
            for r in registros:
                sessao.add(MatrizCcoModel(
                    cc=r["cc"],
                    cc_nome=r.get("cc_nome", ""),
                    gestor=r.get("gestor", ""),
                    funcao=r.get("funcao", ""),
                    sistema=r["sistema"],
                    perfil=r["perfil"],
                    arquivo_origem=arquivo_origem,
                    dt_importacao=datetime.now(),
                ))
            sessao.commit()
        logger.info(f"{len(registros)} mapeamentos CCO/CSC gravados no banco.")

    def obter_cco(self) -> List[Dict]:
        with self._conexao.sessao() as sessao:
            rows = sessao.query(MatrizCcoModel).all()
            return [
                {"cc": r.cc, "cc_nome": r.cc_nome or "",
                 "gestor": getattr(r, "gestor", None) or "", "funcao": r.funcao or "",
                 "sistema": r.sistema, "perfil": r.perfil}
                for r in rows
            ]

    def salvar_validacoes(self, registros: List[Dict]):
        with self._conexao.sessao() as sessao:
            sessao.query(ValidacaoAcessoModel).delete()
            for r in registros:
                sessao.add(ValidacaoAcessoModel(**r, dt_processamento=datetime.now()))
            sessao.commit()
        logger.info(f"{len(registros)} validações de acesso gravadas no banco.")

    def obter_validacoes(self) -> List[Dict]:
        with self._conexao.sessao() as sessao:
            rows = sessao.query(ValidacaoAcessoModel).all()
            return [
                {
                    "matricula": r.matricula, "cpf": r.cpf, "nome": r.nome, "email": r.email,
                    "centro_custo_codigo": r.centro_custo_codigo, "centro_custo_nome": r.centro_custo_nome,
                    "cargo_codigo": r.cargo_codigo, "cargo_descricao": r.cargo_descricao,
                    "sistema": r.sistema, "perfil_esperado": r.perfil_esperado,
                    "perfil_atual": r.perfil_atual, "acesso_manual": r.acesso_manual,
                    "status": r.status, "situacao_acao": r.situacao_acao,
                    "origem_matriz": r.origem_matriz,
                    "dt_processamento": r.dt_processamento,
                }
                for r in rows
            ]
