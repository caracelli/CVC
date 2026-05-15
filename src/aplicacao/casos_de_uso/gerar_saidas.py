from datetime import datetime
from typing import Optional

import pandas as pd
from loguru import logger

from dominio.objetos_valor.tipo_divergencia import TipoDivergencia
from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.escritores_arquivos.escritor_excel import EscritorExcel
from infraestrutura.escritores_arquivos.escritor_parquet import EscritorParquet
from infraestrutura.repositorios.repositorio_divergencia_sqlite import RepositorioDivergenciaSqlite
from infraestrutura.repositorios.repositorio_matriz_sqlite import RepositorioMatrizSqlite

_STATUS_LABEL = {
    "SEM_ACESSO":  "Incluir Acesso",
    "DIVERGENTE":  "Alterar Perfil",
    "EM_ANALISE":  "Em Análise",
    "NAO_MAPEADO": "Não Mapeado",
}


class GerarSaidas:

    def __init__(
        self,
        conexao: ConexaoBancoDados,
        pasta_saidas: str,
        pasta_parquet: str,
        pasta_processados: Optional[str] = None,
        pasta_erros: Optional[str] = None,
    ):
        self._repo_div = RepositorioDivergenciaSqlite(conexao)
        self._repo_matriz = RepositorioMatrizSqlite(conexao)
        self._escritor_excel = EscritorExcel()
        self._escritor_parquet = EscritorParquet()
        self._pasta_saidas = pasta_saidas
        self._pasta_parquet = pasta_parquet

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
            logger.warning("Nenhuma divergencia encontrada — saidas nao geradas.")
            return 0

        # Excel (usa entidades Divergencia originais, excluindo ACESSO_DESLIGADO)
        _TIPOS_EXCLUIDOS = {TipoDivergencia.ACESSO_DESLIGADO}
        divergencias_excel = [d for d in self._repo_div.obter_todas() if d.tipo not in _TIPOS_EXCLUIDOS]
        if divergencias_excel:
            caminho_excel = self._escritor_excel.salvar_divergencias(divergencias_excel, self._pasta_saidas)
            logger.info(f"Excel gerado: {caminho_excel}")

        # Parquet para Power BI
        df = pd.DataFrame(all_rows)
        df = df.astype({
            "id": "str", "tipo": "str", "sistema": "str", "usuario": "str",
            "nome_usuario": "str", "matricula": "str", "perfil_encontrado": "str",
            "perfil_esperado": "str", "descricao": "str", "data_identificacao": "str",
            "acao": "str",
        })
        df["resolvida"] = df["resolvida"].astype("bool")

        self._escritor_parquet.salvar_fixo(
            df,
            f"{self._pasta_parquet}/DIVERGENCIAS",
            "divergencias",
        )

        logger.info(f"=== Saidas geradas: {len(all_rows)} registros ===")
        return len(all_rows)
