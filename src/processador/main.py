import os
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

from loguru import logger

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from infraestrutura.configuracao.leitor_config import LeitorConfig
from infraestrutura.banco_dados.conexao import ConexaoBancoDados
from infraestrutura.banco_dados.processamento_local import (
    BatimentoLock, ProcessamentoCancelado, preparar_copia_local, publicar)
from infraestrutura.leitores_arquivos import leitor_base
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
from infraestrutura.leitores_arquivos.leitor_matriz_franqueado import LeitorMatrizFranqueado
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


# ── Nao rodar da pasta de REDE (09/10/2026) ──────────────────────────────
# Mesma funcao em src/launcher/principal.py, src/visualizador/main.py e
# src/processador/main.py (tests/test_nao_roda_da_rede.py confere).
# Rodado da rede, o exe fica preso (ninguem consegue atualizar a pasta) e o
# painel usa <rede>\EXECUTAVEIS\DADOS\BANCO como "copia local" — um arquivo
# so', na rede, para todos que abrem de la' — o que corrompe o banco.
def _executando_da_rede(pasta, rede_raiz=""):
    """True se `pasta` (onde o exe esta) fica numa pasta de rede: caminho
    UNC, unidade mapeada (DRIVE_REMOTE) ou dentro de <rede><raiz>."""
    import os as _os
    try:
        p = _os.path.abspath(str(pasta))
    except Exception:
        return False
    if p.startswith("\\\\") or p.startswith("//"):
        return True
    if rede_raiz:
        r = _os.path.normcase(_os.path.abspath(rede_raiz)).rstrip("\\/")
        pn = _os.path.normcase(p)
        if pn == r or pn.startswith(r + _os.sep):
            return True
    if sys.platform == "win32":
        try:
            import ctypes
            unidade = _os.path.splitdrive(p)[0]
            if unidade and ctypes.windll.kernel32.GetDriveTypeW(unidade + "\\") == 4:
                return True
        except Exception:
            pass
    return False


def _avisar_rede(pasta, exe):
    """Caixa de mensagem (os exes nao tem console) explicando o que fazer."""
    msg = ("O CVC IAM Analytics nao pode ser aberto direto da pasta de rede.\n\n"
           f"Pasta: {pasta}\n\n"
           "Rodar da rede trava a atualizacao para todos e pode corromper o "
           "banco.\n\n"
           "Copie a pasta EXECUTAVEIS da rede para o seu computador (ex.: "
           f"C:\\CVC_IAM\\EXECUTAVEIS) e abra o {exe} de la'. Os dados "
           "continuam sendo lidos e gravados na rede.")
    print(msg)
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, msg, "CVC IAM Analytics", 0x10)
        except Exception:
            pass


def main():
    _exec = _caminho_config().parent.parent          # pasta EXECUTAVEIS
    try:
        import xml.etree.ElementTree as _ET
        _rr = (_ET.parse(_caminho_config()).getroot().findtext("rede/raiz") or "").strip()
    except Exception:
        _rr = ""
    if _executando_da_rede(_exec, _rr):
        _avisar_rede(_exec, "Processador.exe")
        return 1
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

    Devolve (prosseguir, lock_path, conteudo_fixo):
      - (False, None, "") -> ha processamento em andamento: abortar.
      - (True, Path, txt) -> lock adquirido (remover no fim). `txt` sao as linhas
                             fixas (inicio, usuario, maquina) para o batimento.
      - (True, None, "")  -> nao deu pra criar o lock; segue SEM trava (nao
                             bloqueia o processamento por uma rede so-leitura).

    SINAL DE VIDA (20/10/2026). Ate' aqui o lock valia por IDADE: depois de 20
    min era "antigo" e o proximo assumia. Um processamento normal na rede ja'
    levava 19,6 min (13/10); em 15/10 as execucoes das 14:29 e 17:16 assumiram
    o lock com a das 13:56 ainda viva, e varios Processadores gravaram no mesmo
    banco ao mesmo tempo — a padronizacao foi de 21 s para 7.566 s e o banco
    ficou com um -journal quente. Agora o dono reescreve o lock a cada minuto
    (BatimentoLock); o lock so' e' abandonado apos BATIMENTO_MIN sem sinal.
    Lock de versao anterior (sem batimento) segue a regra antiga de 20 min.
    """
    import getpass
    import socket
    from datetime import datetime
    BATIMENTO_MIN = 10   # sem sinal de vida ha' 10 min = dono caiu
    LEGADO_MIN = 20      # lock sem "batimento=" (versao anterior)
    lock = banco_path.parent / "_processando.lock"
    agora = datetime.now()
    if lock.exists():
        try:
            info = lock.read_text(encoding="utf-8").strip()
            ts = datetime.fromisoformat(info.splitlines()[0][:19])
            idade_min = (agora - ts).total_seconds() / 60
        except Exception:
            info, idade_min = "(ilegivel)", 99999
        com_batimento = "batimento=" in info
        limite = BATIMENTO_MIN if com_batimento else LEGADO_MIN
        quem = " ".join(l for l in info.splitlines()[1:] if l.startswith(("usuario=", "maquina=", "inicio=")))
        if idade_min < limite:
            logger.error(
                f"Processamento JA EM ANDAMENTO na rede ({quem or info}; ultimo sinal "
                f"ha' {idade_min:.0f} min). Abortando para nao conflitar o banco. "
                f"Espere a mensagem 'Processamento finalizado' de quem esta' rodando. "
                f"Para CANCELAR o processamento em andamento, apague '{lock.name}' "
                f"em {lock.parent}: ele para no proximo passo, sem alterar o banco "
                f"da rede. Depois rode novamente.")
            return False, None, ""
        logger.warning(
            f"Lock de processamento sem sinal de vida ha' ~{idade_min:.0f} min "
            f"({quem or info}) — execucao interrompida. Assumindo e prosseguindo.")
    try:
        lock.parent.mkdir(parents=True, exist_ok=True)
        fixo = (f"inicio={agora.isoformat(timespec='seconds')}\n"
                f"usuario={getpass.getuser()}\n"
                f"maquina={socket.gethostname()}\n")
        lock.write_text(f"{agora.isoformat(timespec='seconds')}\n"
                        f"batimento={agora.isoformat(timespec='seconds')}\n{fixo}",
                        encoding="utf-8")
        return True, lock, fixo
    except Exception as e:
        logger.warning(f"Nao foi possivel criar o lock ({e!r}) — seguindo sem trava.")
        return True, None, ""


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

    from datetime import datetime as _dt
    _inicio = _dt.now()
    banco_rede = app_raiz / cfg.banco_dados
    # Lock de processamento na rede: impede duas execucoes simultaneas do
    # Processador (escrita concorrente corromperia o banco). Verificado ANTES
    # de abrir o banco — antes, o `inicializar` ja' mexia no banco da rede
    # mesmo quando havia outro Processador rodando. Liberado no finally.
    prosseguir, lock, lock_fixo = _verificar_e_criar_lock(banco_rede)
    if not prosseguir:
        return 1
    batimento = BatimentoLock(lock, lock_fixo).iniciar() if lock else None

    def _passo(nome):
        """CANCELAMENTO (20/10/2026): apagar o _processando.lock para o
        Processador aqui, antes do proximo passo (ver BatimentoLock.conferir)."""
        if batimento:
            batimento.conferir(nome)

    # COPIA LOCAL (20/10/2026): em modo rede, processa numa copia do banco na
    # maquina e publica no fim (ver processamento_local). CVC_PROCESSAR_NA_REDE=1
    # volta ao comportamento anterior (gravar direto na rede).
    copia_local = bool(cfg.rede_raiz) and os.environ.get("CVC_PROCESSAR_NA_REDE") != "1"
    banco_trabalho = banco_rede
    publicado = not copia_local
    dobra = None
    conexao = None
    # pasta PROPRIA desta execucao (nada compartilhado entre execucoes na
    # mesma maquina); apagada no fim
    pasta_local = (Path(tempfile.gettempdir()) / "CVC_IAM_PROCESSADOR"
                   / f"{_inicio:%Y%m%d_%H%M%S}_{os.getpid()}")
    leitor_base.MOVIMENTOS.clear()
    try:
        _passo("Copia do banco")
        if copia_local:
            banco_trabalho = preparar_copia_local(banco_rede, pasta_local)

        _passo("Abertura do banco")
        conexao = ConexaoBancoDados(str(banco_trabalho))
        conexao.inicializar()

        # Dobra das interacoes (.jsonl) nas tabelas de quarentena. Em modo rede a
        # pasta esta na raiz compartilhada; em modo local, dentro do app_raiz.
        dobra = DobrarInteracoes(
            caminho_banco=str(banco_trabalho),
            pasta_interacoes=str(app_raiz / cfg.rede_interacoes),
            quarentena_dias=cfg.visualizador_quarentena_dias,
            remover_ao_dobrar=not copia_local,
        )
        dobra.executar()

        # Diretorio AD (franqueados/prestadores) — base PRINCIPAL de identidade
        # (decisao da area, 22/07): entra ANTES do RH. Da dono aos acessos
        # orfaos via login. Nao sobrepoe o CLT: a matricula e' namespaced
        # (FRANQ-/PREST-<login>), entao o merge do RH opera em chaves disjuntas;
        # e a precedencia no matching e' explicita em VincularAcessosRh (CLT
        # primeiro), nao decorre desta ordem de importacao.
        _passo("Diretorio AD")
        ImportarDiretorioAd(
            conexao=conexao,
            pasta=[str(app_raiz / p) for p in cfg.rh_diretorio_ad_caminhos],
            pasta_processados=pasta_proc,
            pasta_erros=pasta_err,
            processar=cfg.rh_processar_diretorio_ad,
        ).executar()

        # Card 3 — Importação RH
        _passo("Importacao RH")
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
        _passo("Padronizacao RH")
        PadronizarRh(conexao).executar()

        # Card 5 — Matrizes (perfis esperados e estrutura organizacional).
        # Filtra matrizes pelos sistemas em escopo (ativo=true no config) —
        # sistemas ainda nao implementados nao geram falsa sensacao de
        # processamento no log.
        _passo("Matrizes")
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
            _passo(f"Importacao {_sis.value}")
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
        _passo("SIG")
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
        _passo("Vinculacao")
        VincularAcessosRh(conexao=conexao,
                          prefixos_conta_servico=cfg.conta_servico_prefixos).executar()

        # Card 8 — Analisar divergencias
        _passo("Divergencias")
        AnalisarDivergencias(
            conexao=conexao,
            prefixos_conta_servico=cfg.conta_servico_prefixos,
            sig_so_matriz=cfg.validacao_sig_so_matriz,
        ).executar()

        # Matriz do FRANQUEADO (cargo x tipo de loja): vive na mesma pasta das
        # outras matrizes e e' reconhecida pelo cabecalho. Falta do arquivo NAO
        # quebra o processamento — a regra so' fica inerte.
        _passo("Validacao")
        regras_franq = []
        if cfg.validacao_franqueado_matriz and cfg.matrizes_perfis_caminho:
            try:
                regras_franq, _lidos = LeitorMatrizFranqueado().ler(
                    str(app_raiz / cfg.matrizes_perfis_caminho))
            except Exception as e:
                logger.warning(f"Matriz de franqueado nao carregada: {e!r}")

        # Validação de acessos (inclusão/alteração) — grava na tabela validacao_acessos
        ValidarAcessosSistema(
            conexao=conexao,
            excesso_gera_pendencia=cfg.validacao_excesso_gera_pendencia,
            pendente_vira_inclusao=cfg.validacao_pendente_vira_inclusao,
            matriz_franqueado=regras_franq,
            multi_perfil_gera_pendencia=cfg.validacao_multi_perfil_gera_pendencia,
            multi_perfil_sistemas=cfg.validacao_multi_perfil_sistemas,
            multi_perfil_sistemas_fora=cfg.validacao_multi_perfil_sistemas_fora,
            limiar_inclusao=cfg.validacao_limiar_inclusao,
            ancora_systur_sistemas=cfg.validacao_ancora_systur_sistemas,
            ancora_systur_isentos=cfg.validacao_ancora_systur_isentos,
            sig_so_matriz=cfg.validacao_sig_so_matriz,
        ).executar()

        # Card 23 — revalidacao POS-TRANSFERENCIA. Depois do AnalisarDivergencias
        # (que grava a tabela `transferidos` com o de/para) e da validacao, para
        # usar o mesmo criterio de "esperado" de cada sistema.
        _passo("Transferidos")
        RevalidarTransferidos(
            conexao=conexao,
            ancora_systur_sistemas=cfg.validacao_ancora_systur_sistemas,
            ancora_systur_isentos=cfg.validacao_ancora_systur_isentos,
            sig_so_matriz=cfg.validacao_sig_so_matriz).executar()

        # Ciclo de vida (Pendencia -> Resolvido -> Aderente) — idempotente/blindado.
        # Depois da validacao (validacao_acessos) e da dobra (resolucoes, acima).
        _passo("Ciclo de vida")
        RegistrarCicloVida(conexao=conexao).executar()

        # Log de eventos por (matricula, sistema) — ciclos + REABERTURA. CDC
        # aditivo sobre validacao_acessos; alimenta o Historico por sistema.
        # Depois do ciclo de vida (usa seus dados ricos e a resolucao).
        _passo("Eventos")
        RegistrarEventosAcesso(conexao=conexao).executar()

        # Projeta os marcos do ciclo (Pendencia/Resolvido/Aderente) na trilha
        # `historico` — uma linha por marco, idempotente, em ordem. Cobre
        # transicoes manuais (ticket) e do processador.
        _passo("Historico")
        RegistrarCicloHistorico(conexao=conexao).executar()

        # Card 9 — Gerar saidas (Excel) — usa validações acima para a coluna acao
        _passo("Saidas")
        GerarSaidas(
            conexao=conexao,
            pasta_saidas=str(app_raiz / cfg.saida_divergencias),
        ).executar()

        # Consolida o WAL no .db pra o Visualizador detectar a atualizacao
        # (ele decide recopiar o cache por tamanho/mtime do .db).
        _passo("Fechamento do banco")
        conexao.checkpoint()

        _passo("Publicacao na rede")
        if copia_local:
            publicar(banco_trabalho, banco_rede)
            publicado = True
            dobra.remover_pastas_dobradas()

        _dur = (_dt.now() - _inicio).total_seconds()
        logger.success(
            f"Processamento finalizado em {_dur:.0f}s ({_dur/60:.1f} min).")
        return 0
    except ProcessamentoCancelado as e:
        logger.error(f"Processamento CANCELADO: {e}.")
        return 1
    finally:
        if not publicado:
            # caiu antes de publicar: o banco da rede ficou intacto. Os arquivos
            # ja' movidos voltam a ENTRADA e as interacoes ficam nas pastas
            # INTERACOES_processando* para a proxima execucao.
            n = leitor_base.desfazer_movimentos()
            logger.error(
                f"Processamento NAO concluido — banco da rede mantido como estava; "
                f"{n} arquivo(s) devolvido(s) a ENTRADA. Rode de novo.")
        if conexao is not None:
            try:
                conexao._engine.dispose()
            except Exception:
                pass
        if copia_local:
            shutil.rmtree(pasta_local, ignore_errors=True)
        if batimento:
            batimento.liberar()     # so' apaga o lock se ainda for desta execucao


if __name__ == "__main__":
    main()
