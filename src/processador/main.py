import os
import sys
import traceback
from pathlib import Path

from loguru import logger

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from infraestrutura.configuracao.leitor_config import LeitorConfig
from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.ui_web import janela_processador as ui
from aplicacao.casos_de_uso.importar_rh import ImportarRh
from aplicacao.casos_de_uso.importar_diretorio_ad import ImportarDiretorioAd
from aplicacao.casos_de_uso.padronizar_rh import PadronizarRh
from aplicacao.casos_de_uso.importar_sistema import ImportarSistema
from aplicacao.casos_de_uso.importar_sig import ImportarSig
from infraestrutura.leitores_arquivos.configs_sistemas import CONFIGS_SISTEMAS
from aplicacao.casos_de_uso.importar_matrizes import ImportarMatrizes
from aplicacao.casos_de_uso.vincular_acessos_rh import VincularAcessosRh
from aplicacao.casos_de_uso.analisar_divergencias import AnalisarDivergencias
from aplicacao.casos_de_uso.gerar_saidas import GerarSaidas
from aplicacao.casos_de_uso.validar_acessos_sistema import ValidarAcessosSistema
from aplicacao.casos_de_uso.revalidar_transferidos import RevalidarTransferidos
from aplicacao.casos_de_uso.registrar_ciclo_vida import RegistrarCicloVida
from aplicacao.casos_de_uso.registrar_ciclo_historico import RegistrarCicloHistorico
from aplicacao.casos_de_uso.registrar_eventos_acesso import RegistrarEventosAcesso
from aplicacao.casos_de_uso.dobrar_interacoes import DobrarInteracoes
from dominio.objetos_valor.sistema import Sistema


def _caminho_config() -> Path:
    if getattr(sys, "frozen", False):
        # Executavel em EXECUTAVEIS/launcher/, config em EXECUTAVEIS/CONFIG/
        return Path(sys.executable).parent.parent / "CONFIG" / "config.xml"
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
    # Se o visualizador nos lancou, ele setou PROCESSADOR_CHAMADO_POR=visualizador
    # e PROCESSADOR_URL_PAINEL com a URL do painel. A pagina do Processador
    # entao mostra "Clique em Fechar para abrir o painel" e ao clicar redireciona.
    chamado_por = os.environ.get("PROCESSADOR_CHAMADO_POR", "")
    url_painel = os.environ.get("PROCESSADOR_URL_PAINEL", "")
    try:
        ui.iniciar(abrir_navegador=abre_navegador,
                   chamado_por=chamado_por, url_painel=url_painel)
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
        # Bloqueia ate o usuario clicar em Fechar / fechar a aba — depois
        # o servidor cai. Timeout de 1h evita zumbi se o beacon falhar.
        # Em modo headless (PROCESSADOR_NOBROWSER=1) ninguem clica Fechar:
        # encerra rapido pra nao virar processo zumbi de 1h em runs agendados.
        if abre_navegador:
            ui.aguardar_e_encerrar(timeout_segundos=3600)
        else:
            ui.aguardar_e_encerrar(timeout_segundos=2)


def _verificar_e_criar_lock(banco_path):
    """Lock de processamento na pasta do banco (rede). Impede duas execucoes
    simultaneas do Processador (escrita concorrente corromperia o banco).

    Devolve (prosseguir, lock_path):
      - (False, None) -> ja ha processamento em andamento (lock recente): abortar.
      - (True, Path)  -> lock adquirido (remover no fim).
      - (True, None)  -> nao deu pra criar o lock; segue SEM trava (nao bloqueia
                          o processamento legitimo por causa de uma rede so-leitura).
    Um lock antigo (provavel execucao interrompida) e' assumido apos STALE_MIN
    minutos, para nao travar todos para sempre se o Processador cair no meio.
    STALE_MIN deve ser MAIOR que o maior tempo de processamento real (o log
    "Processamento finalizado em Xs" da a perspectiva pra calibrar).
    """
    import getpass
    from datetime import datetime
    STALE_MIN = 20   # run real ~1min local (medido); ~3-8min na rede (SMB). 20min
                     # da margem confortavel sem travar horas. O log "finalizado
                     # em Xs" mostra o tempo real pra recalibrar se preciso.
    lock = banco_path.parent / "_processando.lock"
    agora = datetime.now()
    if lock.exists():
        try:
            info = lock.read_text(encoding="utf-8").strip()
            ts = datetime.fromisoformat(info.splitlines()[0][:19])
            idade_min = (agora - ts).total_seconds() / 60
        except Exception:
            info, idade_min = "(ilegivel)", 99999
        if idade_min < STALE_MIN:
            logger.error(
                f"Processamento JA EM ANDAMENTO na rede (iniciado em {info}). "
                f"Abortando para nao conflitar o banco. Se tiver CERTEZA de que "
                f"ninguem esta rodando, apague '{lock.name}' em {lock.parent} e "
                f"rode novamente.")
            return False, None
        logger.warning(
            f"Lock de processamento antigo ({info}, ~{idade_min:.0f} min) — provavel "
            f"execucao interrompida. Assumindo e prosseguindo.")
    try:
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text(
            f"{agora.isoformat(timespec='seconds')}\n"
            f"usuario={getpass.getuser()}\n", encoding="utf-8")
        return True, lock
    except Exception as e:
        logger.warning(f"Nao foi possivel criar o lock ({e!r}) — seguindo sem trava.")
        return True, None


def _sistemas_em_escopo(cfg) -> set:
    """Conjunto de Sistema com ativo=true no config — os implementados nesta
    fase. Usado para filtrar matrizes (e, futuramente, importacoes) de
    sistemas ainda fora de escopo, evitando falsa sensacao de processamento."""
    escopo = set()
    for sc in cfg.sistemas.values():
        if not sc.ativo:
            continue
        try:
            escopo.add(Sistema(sc.nome))
        except ValueError:
            pass
    return escopo


def _executar(caminho_config: Path) -> int:
    """Logica original do Processador. Devolve 0 se OK, 1 se erro."""
    if not caminho_config.exists():
        logger.error(f"config.xml não encontrado: {caminho_config}")
        return 1

    # Auto-update agora e' responsabilidade do principal (Processador.exe
    # no top level) e do launcher_atualizador.exe. Este motor so PROCESSA.

    cfg = LeitorConfig(str(caminho_config)).carregar()
    # Raiz dos dados: rede (se <rede><raiz> definido) ou local (modo dev).
    if cfg.rede_raiz:
        app_raiz = Path(cfg.rede_raiz)
        if not app_raiz.exists():
            logger.error(f"Raiz de rede inacessível: {app_raiz} — abortando.")
            sys.exit(1)
    else:
        # config em EXECUTAVEIS/launcher/CONFIG/ NAO existe — config esta em
        # EXECUTAVEIS/CONFIG/. Sobe 4 niveis: config -> CONFIG -> EXECUTAVEIS/launcher
        # nao, esperar: o exe esta em EXECUTAVEIS/launcher/, e config_path foi
        # calculado como ../CONFIG/config.xml. Entao caminho_config tem
        # 4 niveis ate a raiz do app:
        #   config.xml -> CONFIG -> EXECUTAVEIS -> CVC_IAM_ANALYTICS
        app_raiz = caminho_config.parent.parent.parent

    configurar_log(str(app_raiz / cfg.saida_logs))
    logger.info(f"IAM Analytics — {cfg.cliente} v{cfg.versao}")

    pasta_proc = str(app_raiz / cfg.processados)
    pasta_err = str(app_raiz / cfg.erros)

    conexao = ConexaoBancoDados(str(app_raiz / cfg.banco_dados))
    conexao.inicializar()

    from datetime import datetime as _dt
    _inicio = _dt.now()
    # Lock de processamento na rede: impede duas execucoes simultaneas do
    # Processador (escrita concorrente corromperia o banco). Liberado no finally.
    prosseguir, lock = _verificar_e_criar_lock(app_raiz / cfg.banco_dados)
    if not prosseguir:
        return 1
    try:
        # Dobra das interacoes (.jsonl) nas tabelas de quarentena. Em modo rede a
        # pasta esta na raiz compartilhada; em modo local, dentro do app_raiz.
        DobrarInteracoes(
            caminho_banco=str(app_raiz / cfg.banco_dados),
            pasta_interacoes=str(app_raiz / cfg.rede_interacoes),
            quarentena_dias=cfg.visualizador_quarentena_dias,
        ).executar()

        # Diretorio AD (franqueados/prestadores) — base PRINCIPAL de identidade
        # (decisao da area, 22/07): entra ANTES do RH. Da dono aos acessos
        # orfaos via login. Nao sobrepoe o CLT: a matricula e' namespaced
        # (FRANQ-/PREST-<login>), entao o merge do RH opera em chaves disjuntas;
        # e a precedencia no matching e' explicita em VincularAcessosRh (CLT
        # primeiro), nao decorre desta ordem de importacao.
        ImportarDiretorioAd(
            conexao=conexao,
            pasta=str(app_raiz / cfg.rh_diretorio_ad_caminho),
            pasta_processados=pasta_proc,
            pasta_erros=pasta_err,
            processar=cfg.rh_processar_diretorio_ad,
        ).executar()

        # Card 3 — Importação RH
        ImportarRh(
            conexao=conexao,
            pasta_ativos=str(app_raiz / cfg.rh_ativos_caminho),
            pasta_desligados=str(app_raiz / cfg.rh_desligados_caminho),
            pasta_processados=pasta_proc,
            pasta_erros=pasta_err,
            processar_desligados=cfg.rh_processar_desligados,
            processar_terceiros=cfg.rh_processar_terceiros,
        ).executar()

        # Card 4 — Padronização (snapshot/histórico já gravado no Card 3, antes do merge)
        PadronizarRh(conexao).executar()

        # Card 5 — Matrizes (perfis esperados e estrutura organizacional).
        # Filtra matrizes pelos sistemas em escopo (ativo=true no config) —
        # sistemas ainda nao implementados nao geram falsa sensacao de
        # processamento no log.
        ImportarMatrizes(
            conexao=conexao,
            pasta_perfis=str(app_raiz / cfg.matrizes_perfis_caminho),
            pasta_org=str(app_raiz / cfg.matrizes_org_caminho),
            pasta_processados=pasta_proc,
            pasta_erros=pasta_err,
            sistemas_em_escopo=_sistemas_em_escopo(cfg),
        ).executar()

        # Card 6+ — Importacao dos extratos dos sistemas em escopo (ativo=true)
        # que tem leitor padrao em CONFIGS_SISTEMAS (SYSTUR, IC, SIGOT, SICA_*).
        # O SIG (matricial) tem fluxo proprio logo abaixo; sistemas sem leitor
        # padrao (scaffold, ex.: ORACLE_EBS) sao ignorados em silencio.
        for _sc in cfg.sistemas.values():
            if not _sc.ativo:
                continue
            try:
                _sis = Sistema(_sc.nome)
            except ValueError:
                continue
            if _sis is Sistema.SIG or _sis not in CONFIGS_SISTEMAS:
                continue
            ImportarSistema(
                conexao=conexao,
                sistema=_sis,
                pasta_entrada=str(app_raiz / _sc.caminho_entrada),
                pasta_processados=pasta_proc,
                pasta_erros=pasta_err,
            ).executar()

        # Card 12 — SIG (matricial + de-para). Condicional: roda so se houver
        # pasta de entrada configurada E ativo. Nao bloqueia o pipeline se faltar
        # arquivo (ImportarSig loga "nao em uso" e segue).
        sig_cfg = cfg.sistemas.get("SIG")
        if sig_cfg and sig_cfg.ativo and sig_cfg.caminho_entrada:
            ImportarSig(
                conexao=conexao,
                pasta_extratos=str(app_raiz / sig_cfg.caminho_entrada),
                pasta_de_para=str(app_raiz / sig_cfg.caminho_de_para) if sig_cfg.caminho_de_para else "",
                pasta_processados=pasta_proc,
                pasta_erros=pasta_err,
            ).executar()

        # Card 7 — Vincular acessos ao RH por CPF
        VincularAcessosRh(conexao=conexao).executar()

        # Card 8 — Analisar divergencias
        AnalisarDivergencias(conexao=conexao).executar()

        # Validação de acessos (inclusão/alteração) — grava na tabela validacao_acessos
        ValidarAcessosSistema(conexao=conexao).executar()

        # Card 23 — revalidacao POS-TRANSFERENCIA. Depois do AnalisarDivergencias
        # (que grava a tabela `transferidos` com o de/para) e da validacao, para
        # usar o mesmo criterio de "esperado" de cada sistema.
        RevalidarTransferidos(conexao=conexao).executar()

        # Ciclo de vida (Pendencia -> Resolvido -> Aderente) — idempotente/blindado.
        # Depois da validacao (validacao_acessos) e da dobra (resolucoes, acima).
        RegistrarCicloVida(conexao=conexao).executar()

        # Log de eventos por (matricula, sistema) — ciclos + REABERTURA. CDC
        # aditivo sobre validacao_acessos; alimenta o Historico por sistema.
        # Depois do ciclo de vida (usa seus dados ricos e a resolucao).
        RegistrarEventosAcesso(conexao=conexao).executar()

        # Projeta os marcos do ciclo (Pendencia/Resolvido/Aderente) na trilha
        # `historico` — uma linha por marco, idempotente, em ordem. Cobre
        # transicoes manuais (ticket) e do processador.
        RegistrarCicloHistorico(conexao=conexao).executar()

        # Card 9 — Gerar saidas (Excel) — usa validações acima para a coluna acao
        GerarSaidas(
            conexao=conexao,
            pasta_saidas=str(app_raiz / cfg.saida_divergencias),
        ).executar()

        # Consolida o WAL no .db pra o Visualizador detectar a atualizacao
        # (ele decide recopiar o cache por tamanho/mtime do .db).
        conexao.checkpoint()

        _dur = (_dt.now() - _inicio).total_seconds()
        logger.success(
            f"Processamento finalizado em {_dur:.0f}s ({_dur/60:.1f} min).")
        return 0
    finally:
        if lock:
            try:
                lock.unlink()
            except Exception:
                pass


if __name__ == "__main__":
    main()
