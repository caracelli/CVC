import sys
from pathlib import Path

from loguru import logger

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from infraestrutura.configuracao.leitor_config import LeitorConfig
from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from aplicacao.casos_de_uso.importar_rh import ImportarRh
from aplicacao.casos_de_uso.padronizar_rh import PadronizarRh
from aplicacao.casos_de_uso.importar_sistema import ImportarSistema
from aplicacao.casos_de_uso.importar_matrizes import ImportarMatrizes
from aplicacao.casos_de_uso.vincular_acessos_rh import VincularAcessosRh
from aplicacao.casos_de_uso.analisar_divergencias import AnalisarDivergencias
from aplicacao.casos_de_uso.gerar_saidas import GerarSaidas
from aplicacao.casos_de_uso.validar_acessos_sistema import ValidarAcessosSistema
from dominio.objetos_valor.sistema import Sistema


def _caminho_config() -> Path:
    if getattr(sys, "frozen", False):
        # Executável em EXECUTAVEIS/, config.xml está um nível acima
        return Path(sys.executable).parent.parent / "config.xml"
    # Script em src/processador/main.py, CVC_IAM_ANALYTICS em ../../../
    return Path(__file__).resolve().parent.parent.parent / "CVC_IAM_ANALYTICS" / "config.xml"


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
    caminho_config = _caminho_config()

    if not caminho_config.exists():
        logger.error(f"config.xml não encontrado: {caminho_config}")
        sys.exit(1)

    cfg = LeitorConfig(str(caminho_config)).carregar()
    app_raiz = caminho_config.parent

    configurar_log(str(app_raiz / cfg.saida_logs))
    logger.info(f"IAM Analytics — {cfg.cliente} v{cfg.versao}")

    pasta_proc = str(app_raiz / cfg.processados)
    pasta_err = str(app_raiz / cfg.erros)

    conexao = ConexaoBancoDados(str(app_raiz / cfg.banco_dados))
    conexao.inicializar()

    # Card 3 — Importação RH
    ImportarRh(
        conexao=conexao,
        pasta_ativos=str(app_raiz / cfg.rh_ativos_caminho),
        pasta_desligados=str(app_raiz / cfg.rh_desligados_caminho),
        pasta_parquet_rh=str(app_raiz / cfg.parquet_rh),
        pasta_processados=pasta_proc,
        pasta_erros=pasta_err,
    ).executar()

    # Card 4 — Padronização e snapshot
    PadronizarRh(conexao).executar()

    # Card 5 — Matrizes (perfis esperados e estrutura organizacional)
    ImportarMatrizes(
        conexao=conexao,
        pasta_perfis=str(app_raiz / cfg.matrizes_perfis_caminho),
        pasta_org=str(app_raiz / cfg.matrizes_org_caminho),
        pasta_parquet=str(app_raiz / "DADOS" / "PARQUET"),
        pasta_processados=pasta_proc,
        pasta_erros=pasta_err,
    ).executar()

    # Card 6 — SYSTUR
    sis_cfg = cfg.sistemas.get("SYSTUR")
    if sis_cfg:
        ImportarSistema(
            conexao=conexao,
            sistema=Sistema.SYSTUR,
            pasta_entrada=str(app_raiz / sis_cfg.caminho_entrada),
            pasta_parquet=str(app_raiz / sis_cfg.caminho_parquet),
            pasta_processados=pasta_proc,
            pasta_erros=pasta_err,
        ).executar()

    # Card 7 — Vincular acessos ao RH por CPF
    VincularAcessosRh(conexao=conexao).executar()

    # Card 8 — Analisar divergencias
    AnalisarDivergencias(conexao=conexao).executar()

    # Validação de acessos (inclusão/alteração) — gera parquet para Power BI
    ValidarAcessosSistema(
        conexao=conexao,
        pasta_parquet=str(app_raiz / "DADOS" / "PARQUET"),
    ).executar()

    # Card 9 — Gerar saidas (Excel + Parquet) — usa validações acima para coluna acao
    GerarSaidas(
        conexao=conexao,
        pasta_saidas=str(app_raiz / cfg.saida_divergencias),
        pasta_parquet=str(app_raiz / "DADOS" / "PARQUET"),
    ).executar()

    logger.info("Processamento finalizado.")


if __name__ == "__main__":
    main()
