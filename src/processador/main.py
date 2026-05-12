import sys
from pathlib import Path

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from infraestrutura.configuracao.leitor_config import LeitorConfig
from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from aplicacao.casos_de_uso.importar_rh import ImportarRh
from aplicacao.casos_de_uso.padronizar_rh import PadronizarRh
from aplicacao.casos_de_uso.importar_sistema import ImportarSistema
from dominio.objetos_valor.sistema import Sistema


def configurar_log(pasta_logs: str):
    Path(pasta_logs).mkdir(parents=True, exist_ok=True)
    logger.add(
        f"{pasta_logs}/processador_{{time:YYYY-MM-DD}}.log",
        rotation="1 day",
        retention="30 days",
        encoding="utf-8",
        level="INFO",
    )


def main():
    raiz = Path(__file__).resolve().parent.parent.parent
    caminho_config = raiz / "CVC_IAM_ANALYTICS" / "config.xml"

    if not caminho_config.exists():
        logger.error(f"config.xml não encontrado: {caminho_config}")
        sys.exit(1)

    cfg = LeitorConfig(str(caminho_config)).carregar()
    app_raiz = caminho_config.parent

    configurar_log(str(app_raiz / cfg.saida_logs))
    logger.info(f"IAM Analytics — {cfg.cliente} v{cfg.versao}")

    conexao = ConexaoBancoDados(str(app_raiz / cfg.banco_dados))
    conexao.inicializar()

    # Card 3 — Importação RH
    ImportarRh(
        conexao=conexao,
        pasta_ativos=str(app_raiz / cfg.rh_ativos_caminho),
        pasta_desligados=str(app_raiz / cfg.rh_desligados_caminho),
        pasta_parquet_rh=str(app_raiz / cfg.parquet_rh),
    ).executar()

    # Card 4 — Padronização e snapshot
    PadronizarRh(conexao).executar()

    # Card 6 — SYSTUR
    sis_cfg = cfg.sistemas.get("SYSTUR")
    if sis_cfg:
        ImportarSistema(
            conexao=conexao,
            sistema=Sistema.SYSTUR,
            pasta_entrada=str(app_raiz / sis_cfg.caminho_entrada),
            pasta_parquet=str(app_raiz / sis_cfg.caminho_parquet),
        ).executar()

    logger.info("Processamento finalizado.")


if __name__ == "__main__":
    main()
