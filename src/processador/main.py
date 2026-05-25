import os
import sys
import traceback
from pathlib import Path

from loguru import logger

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from infraestrutura.configuracao.leitor_config import LeitorConfig
from infraestrutura.atualizacao.auto_update import verificar_atualizacao
from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.ui_web import janela_processador as ui
from aplicacao.casos_de_uso.importar_rh import ImportarRh
from aplicacao.casos_de_uso.padronizar_rh import PadronizarRh
from aplicacao.casos_de_uso.importar_sistema import ImportarSistema
from aplicacao.casos_de_uso.importar_matrizes import ImportarMatrizes
from aplicacao.casos_de_uso.vincular_acessos_rh import VincularAcessosRh
from aplicacao.casos_de_uso.analisar_divergencias import AnalisarDivergencias
from aplicacao.casos_de_uso.gerar_saidas import GerarSaidas
from aplicacao.casos_de_uso.validar_acessos_sistema import ValidarAcessosSistema
from aplicacao.casos_de_uso.dobrar_interacoes import DobrarInteracoes
from dominio.objetos_valor.sistema import Sistema


def _caminho_config() -> Path:
    if getattr(sys, "frozen", False):
        # Executável em EXECUTAVEIS/, config em EXECUTAVEIS/CONFIG/config.xml
        return Path(sys.executable).parent / "CONFIG" / "config.xml"
    # Script em src/processador/main.py
    return (Path(__file__).resolve().parent.parent.parent
            / "CVC_IAM_ANALYTICS" / "EXECUTAVEIS" / "CONFIG" / "config.xml")


def configurar_log(pasta_logs: str):
    Path(pasta_logs).mkdir(parents=True, exist_ok=True)
    logger.add(
        f"{pasta_logs}/processador_{{time:YYYY-MM-DD}}.log",
        rotation="1 day",
        retention="30 days",
        encoding="utf-8",
        level="INFO",
    )


def _ligar_sink_ui():
    """Encaminha cada mensagem do loguru para a janela HTML do Processador.
    Formato curto: '12:34:56 INFO    | mensagem'."""
    def _sink(message):
        ui.escrever(str(message))
    logger.add(_sink, level="INFO",
               format="{time:HH:mm:ss} {level: <7} | {message}")


def _detectar_etapa(msg: str) -> str:
    """Mapeia trechos de log para o rotulo de status amigavel do topo."""
    m = msg.lower()
    if "auto-update" in m:        return "Verificando atualização..."
    if "importação rh" in m:      return "Importando RH..."
    if "padronizando rh" in m or "padronizacao" in m: return "Padronizando RH..."
    if "matrizes" in m:           return "Importando matrizes..."
    if "importação systur" in m or "systur iniciada" in m: return "Importando SYSTUR..."
    if "vincular" in m or "vinculacao" in m: return "Vinculando acessos ao RH..."
    if "divergenci" in m:         return "Analisando divergências..."
    if "validacao" in m or "validação" in m: return "Validando acessos..."
    if "saidas" in m or "saídas" in m: return "Gerando saídas (Excel)..."
    if "dobra" in m:              return "Consolidando interações..."
    return ""


def _ligar_sink_status():
    """Sink leve so para atualizar o rotulo de status do topo da pagina."""
    def _sink(message):
        et = _detectar_etapa(str(message))
        if et:
            ui.status(et)
    logger.add(_sink, level="INFO", format="{message}")


def main():
    # Sobe a janela HTML (substitui o terminal — Processador.exe e' --noconsole).
    # Em dev (script .py), tambem abre, util pra depurar.
    abre_navegador = os.environ.get("PROCESSADOR_NOBROWSER") != "1"
    # Se o visualizador nos lancou, ele setou PROCESSADOR_ON_DONE com a URL do
    # painel — a aba do Processador redireciona pra la quando terminar.
    on_done = os.environ.get("PROCESSADOR_ON_DONE", "")
    try:
        ui.iniciar(abrir_navegador=abre_navegador, on_done_url=on_done)
    except Exception as e:
        print(f"[ui] falha ao iniciar janela HTML: {e!r}")
    _ligar_sink_ui()
    _ligar_sink_status()

    erro = False
    try:
        codigo = _executar(_caminho_config())
        if codigo != 0:
            erro = True
    except SystemExit:
        raise  # auto-update reinicia via sys.exit(0)
    except Exception as e:
        erro = True
        logger.error(f"Erro nao tratado: {e!r}")
        logger.error(traceback.format_exc())
    finally:
        ui.concluir(erro=erro)
        # Da tempo do usuario ler a mensagem final antes do servidor cair
        ui.aguardar_e_encerrar(segundos=10)


def _executar(caminho_config: Path) -> int:
    """Logica original do Processador. Devolve 0 se OK, 1 se erro."""
    if not caminho_config.exists():
        logger.error(f"config.xml não encontrado: {caminho_config}")
        return 1

    # Auto-update: se a versao da rede diferir, copia e re-executa (encerra aqui)
    verificar_atualizacao(logger.info)

    cfg = LeitorConfig(str(caminho_config)).carregar()
    # Raiz dos dados: rede (se <rede><raiz> definido) ou local (modo dev).
    if cfg.rede_raiz:
        app_raiz = Path(cfg.rede_raiz)
        if not app_raiz.exists():
            logger.error(f"Raiz de rede inacessível: {app_raiz} — abortando.")
            sys.exit(1)
    else:
        # config em EXECUTAVEIS/CONFIG/ -> raiz do app sobe tres niveis
        app_raiz = caminho_config.parent.parent.parent

    configurar_log(str(app_raiz / cfg.saida_logs))
    logger.info(f"IAM Analytics — {cfg.cliente} v{cfg.versao}")

    pasta_proc = str(app_raiz / cfg.processados)
    pasta_err = str(app_raiz / cfg.erros)

    conexao = ConexaoBancoDados(str(app_raiz / cfg.banco_dados))
    conexao.inicializar()

    # Dobra das interacoes (.jsonl) nas tabelas de quarentena. Em modo rede a
    # pasta esta na raiz compartilhada; em modo local, dentro do app_raiz.
    DobrarInteracoes(
        caminho_banco=str(app_raiz / cfg.banco_dados),
        pasta_interacoes=str(app_raiz / cfg.rede_interacoes),
        quarentena_dias=cfg.visualizador_quarentena_dias,
    ).executar()

    # Card 3 — Importação RH
    ImportarRh(
        conexao=conexao,
        pasta_ativos=str(app_raiz / cfg.rh_ativos_caminho),
        pasta_desligados=str(app_raiz / cfg.rh_desligados_caminho),
        pasta_processados=pasta_proc,
        pasta_erros=pasta_err,
    ).executar()

    # Card 4 — Padronização (snapshot/histórico já gravado no Card 3, antes do merge)
    PadronizarRh(conexao).executar()

    # Card 5 — Matrizes (perfis esperados e estrutura organizacional)
    ImportarMatrizes(
        conexao=conexao,
        pasta_perfis=str(app_raiz / cfg.matrizes_perfis_caminho),
        pasta_org=str(app_raiz / cfg.matrizes_org_caminho),
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
            pasta_processados=pasta_proc,
            pasta_erros=pasta_err,
        ).executar()

    # Card 7 — Vincular acessos ao RH por CPF
    VincularAcessosRh(conexao=conexao).executar()

    # Card 8 — Analisar divergencias
    AnalisarDivergencias(conexao=conexao).executar()

    # Validação de acessos (inclusão/alteração) — grava na tabela validacao_acessos
    ValidarAcessosSistema(conexao=conexao).executar()

    # Card 9 — Gerar saidas (Excel) — usa validações acima para a coluna acao
    GerarSaidas(
        conexao=conexao,
        pasta_saidas=str(app_raiz / cfg.saida_divergencias),
    ).executar()

    logger.success("Processamento finalizado.")
    return 0


if __name__ == "__main__":
    main()
