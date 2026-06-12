from typing import Optional

from loguru import logger

from dominio.objetos_valor.tipo_divergencia import TipoDivergencia
from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.repositorios.repositorio_divergencia_sqlite import RepositorioDivergenciaSqlite
from infraestrutura.repositorios.repositorio_matriz_sqlite import RepositorioMatrizSqlite

_STATUS_LABEL = {
    "SEM_ACESSO":  "Incluir Acesso",
    "DIVERGENTE":  "Alterar Perfil",
    "EM_ANALISE":  "Em Análise",
    "NAO_MAPEADO": "Não Mapeado",
    "OK":          "Aderente",
}


class GerarSaidas:

    def __init__(
        self,
        conexao: ConexaoBancoDados,
        pasta_saidas: str,
        pasta_processados: Optional[str] = None,
        pasta_erros: Optional[str] = None,
    ):
        self._repo_div = RepositorioDivergenciaSqlite(conexao)
        self._repo_matriz = RepositorioMatrizSqlite(conexao)
        self._pasta_saidas = pasta_saidas

    def executar(self) -> int:
        logger.info("=== Geracao de Saidas iniciada ===")

        # ── Fonte 1: validações com ação pendente (mesma origem do validacao_acessos.parquet) ──
        validacoes = self._repo_matriz.obter_validacoes()
        rows_validacao = [
            {
                "id":                f"{v['matricula']}_{v['sistema']}_{v.get('perfil_esperado', '') or ''}",
                "tipo":              v["status"],
                "sistema":           v["sistema"],
                "usuario":           v["matricula"],
                "nome_usuario":      v["nome"],
                "matricula":         v["matricula"],
                "perfil_encontrado": v["perfil_atual"] or "",
                "perfil_esperado":   v["perfil_esperado"] or "",
                "descricao":         "",
                "data_identificacao": (
                    v["dt_processamento"].strftime("%Y-%m-%d %H:%M:%S")
                    if v.get("dt_processamento") else ""
                ),
                "resolvida":         False,
                "acao":              _STATUS_LABEL.get(v["status"], ""),
            }
            for v in validacoes
        ]

        # ── Fonte 2: acessos sem vínculo RH → "Não Mapeado" ──
        divergencias_sem_vinculo = [
            d for d in self._repo_div.obter_todas()
            if d.tipo == TipoDivergencia.ACESSO_SEM_VINCULO_RH
        ]
        rows_sem_vinculo = [
            {
                "id":                d.id,
                "tipo":              d.tipo.value,
                "sistema":           d.sistema.value,
                "usuario":           d.usuario,
                "nome_usuario":      d.nome_usuario or d.usuario,
                "matricula":         d.matricula or "",
                "perfil_encontrado": d.perfil_encontrado or "",
                "perfil_esperado":   d.perfil_esperado or "",
                "descricao":         d.descricao or "",
                "data_identificacao": (
                    d.data_identificacao.strftime("%Y-%m-%d %H:%M:%S")
                    if d.data_identificacao else ""
                ),
                "resolvida":         d.resolvida,
                "acao":              "Não Mapeado",
            }
            for d in divergencias_sem_vinculo
        ]

        all_rows = rows_validacao + rows_sem_vinculo

        if not all_rows:
            logger.warning("Nenhuma divergencia encontrada.")
            return 0

        # Excel automatico REMOVIDO (gerava um arquivo por run em SAIDAS/, sem
        # uso — o usuario exporta da grid do painel sob demanda). Esta etapa
        # so contabiliza/loga as divergencias do cenario.
        logger.info(f"=== Divergencias do cenario: {len(all_rows)} registros ===")
        return len(all_rows)
