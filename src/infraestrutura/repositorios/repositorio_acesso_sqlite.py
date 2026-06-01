import json
from datetime import datetime
from typing import Dict, List, Optional

from loguru import logger

from dominio.entidades.perfil_acesso import PerfilAcesso
from dominio.interfaces.i_repositorio_acesso import IRepositorioAcesso
from dominio.objetos_valor.sistema import Sistema
from dominio.servicos_dominio.servico_vinculacao_multi_chave import (
    FuncionarioRef, ResultadoVinculacao, ServicoVinculacaoMultiChave,
    METODO_CPF, SCORE_CPF,
)
from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.schema import AcessoSistema


class RepositorioAcessoSqlite(IRepositorioAcesso):
    """Persistencia de acessos com PK (sistema, usuario, perfil).

    A PK composta com perfil e' fundamental — usuarios sao multi-perfil.
    Antes a PK era (sistema, usuario) e so o ultimo perfil sobrevivia
    (bug que SIG escancarou com mediana de 88 perfis/usuario).
    """

    def __init__(self, conexao: ConexaoBancoDados):
        self._conexao = conexao

    # ------------------------------------------------------------------
    # Escrita
    # ------------------------------------------------------------------
    def salvar_lote(self, perfis: List[PerfilAcesso], arquivo_origem: str = "") -> None:
        """Faz merge linha-a-linha. Util quando o arquivo nao representa um
        snapshot completo (raro). Para snapshot use substituir_sistema."""
        if not perfis:
            return
        with self._conexao.sessao() as sessao:
            for p in perfis:
                sessao.merge(self._to_orm(p, arquivo_origem))
            sessao.commit()
        logger.info(f"{len(perfis)} acessos gravados — {perfis[0].sistema.value}")

    def salvar(self, perfil: PerfilAcesso) -> None:
        self.salvar_lote([perfil])

    def substituir_sistema(
        self,
        sistema: Sistema,
        perfis: List[PerfilAcesso],
        arquivo_origem: str = "",
    ) -> int:
        """Substitui TODOS os acessos do sistema (semantica de snapshot).

        Deduplica por (sistema, usuario, perfil) mantendo o ultimo na lista.
        E' a unica chave razoavel: o mesmo trio nao deveria aparecer 2x
        no extrato; se aparecer, manter o ultimo e' menos ruim que duplicar.
        """
        unicos: Dict[tuple, PerfilAcesso] = {}
        for p in perfis:
            unicos[(p.sistema.value, p.usuario, p.perfil)] = p

        with self._conexao.sessao() as sessao:
            removidos = (
                sessao.query(AcessoSistema)
                .filter_by(sistema=sistema.value)
                .delete()
            )
            sessao.flush()
            for p in unicos.values():
                sessao.add(self._to_orm(p, arquivo_origem))
            sessao.commit()

        logger.info(
            f"{sistema.value}: {removidos} acesso(s) da importacao anterior "
            f"removido(s), {len(unicos)} do arquivo gravado(s) (substituicao)."
        )
        return len(unicos)

    # ------------------------------------------------------------------
    # Leitura
    # ------------------------------------------------------------------
    def obter_todos(self) -> List[PerfilAcesso]:
        with self._conexao.sessao() as sessao:
            rows = sessao.query(AcessoSistema).all()
            return [self._para_perfil(r) for r in rows]

    def obter_por_sistema(self, sistema: Sistema) -> List[PerfilAcesso]:
        with self._conexao.sessao() as sessao:
            rows = sessao.query(AcessoSistema).filter_by(sistema=sistema.value).all()
            return [self._para_perfil(r) for r in rows]

    def contar_por_sistema(self, sistema: Sistema) -> int:
        """COUNT(*) do sistema — evita materializar todas as linhas em objetos
        ORM so pra contar (relevante no SIG: dezenas de milhares de acessos)."""
        with self._conexao.sessao() as sessao:
            return sessao.query(AcessoSistema).filter_by(sistema=sistema.value).count()

    def obter_por_usuario(self, usuario: str) -> List[PerfilAcesso]:
        with self._conexao.sessao() as sessao:
            rows = sessao.query(AcessoSistema).filter_by(usuario=usuario).all()
            return [self._para_perfil(r) for r in rows]

    # ------------------------------------------------------------------
    # Vinculacao
    # ------------------------------------------------------------------
    def vincular_por_cpf(self, mapa_cpf_matricula: Dict[str, str]) -> int:
        """Modo legado simples: vincula somente por CPF exato, score 1.0.

        Mantido por compatibilidade com vincular_acessos_rh atual. Para a
        cascata multi-chave (CPF/email/parcial+nome/nome/fuzzy), use
        vincular_multi_chave."""
        if not mapa_cpf_matricula:
            return 0
        count = 0
        with self._conexao.sessao() as sessao:
            rows = sessao.query(AcessoSistema).filter(AcessoSistema.cpf.isnot(None)).all()
            for row in rows:
                if row.cpf and row.cpf in mapa_cpf_matricula:
                    row.matricula_vinculada = mapa_cpf_matricula[row.cpf]
                    row.metodo_vinculacao = METODO_CPF
                    row.score_vinculacao = SCORE_CPF
                    row.candidatos_matricula = None
                    count += 1
            sessao.commit()
        return count

    def vincular_multi_chave(self, funcionarios: List[FuncionarioRef]) -> Dict[str, int]:
        """Cascata completa de matching multi-chave. Devolve contagem por metodo.

        Usado quando o sistema tem CPF mascarado/ausente (SICA_RA) ou queremos
        cobertura maior que o simples CPF exato."""
        servico = ServicoVinculacaoMultiChave(funcionarios)
        contagem: Dict[str, int] = {}
        with self._conexao.sessao() as sessao:
            rows = sessao.query(AcessoSistema).all()
            for row in rows:
                resultado: ResultadoVinculacao = servico.vincular(
                    cpf=row.cpf or "",
                    email=row.email or "",
                    nome=row.nome_usuario or "",
                    cpf_mascarado=row.cpf or "",
                )
                row.matricula_vinculada = resultado.matricula
                row.metodo_vinculacao = resultado.metodo
                row.score_vinculacao = resultado.score
                row.candidatos_matricula = (
                    json.dumps(resultado.candidatos, ensure_ascii=False)
                    if resultado.candidatos else None
                )
                contagem[resultado.metodo] = contagem.get(resultado.metodo, 0) + 1
            sessao.commit()
        return contagem

    # ------------------------------------------------------------------
    # Conversoes
    # ------------------------------------------------------------------
    def _to_orm(self, p: PerfilAcesso, arquivo_origem: str) -> AcessoSistema:
        candidatos = (
            json.dumps(p.candidatos_matricula, ensure_ascii=False)
            if p.candidatos_matricula else None
        )
        return AcessoSistema(
            sistema=p.sistema.value,
            usuario=p.usuario,
            perfil=p.perfil or "",
            nome_usuario=p.nome_usuario,
            cpf=p.cpf or None,
            email=p.email or None,  # corrigido: antes era hardcoded None
            situacao=p.situacao,
            data_criacao=p.data_criacao,
            ultimo_acesso=p.ultimo_acesso,
            matricula_vinculada=p.matricula_vinculada,
            metodo_vinculacao=p.metodo_vinculacao,
            score_vinculacao=p.score_vinculacao,
            candidatos_matricula=candidatos,
            arquivo_origem=arquivo_origem,
            dt_importacao=datetime.now(),
        )

    def _para_perfil(self, r: AcessoSistema) -> PerfilAcesso:
        candidatos: Optional[List[str]] = None
        if r.candidatos_matricula:
            try:
                candidatos = json.loads(r.candidatos_matricula)
            except Exception:
                candidatos = None
        return PerfilAcesso(
            usuario=r.usuario,
            nome_usuario=r.nome_usuario or "",
            sistema=Sistema(r.sistema),
            perfil=r.perfil or "",
            situacao=r.situacao or "",
            data_criacao=r.data_criacao,
            ultimo_acesso=r.ultimo_acesso,
            matricula_vinculada=r.matricula_vinculada,
            cpf=r.cpf,
            email=r.email,
            metodo_vinculacao=r.metodo_vinculacao,
            score_vinculacao=r.score_vinculacao,
            candidatos_matricula=candidatos,
        )
