"""Processar numa COPIA LOCAL do banco da rede e publicar no fim (20/10/2026).

Por que: o SQLite numa pasta de rede (SMB) paga uma ida e volta pela rede a
cada gravacao. Medido com a mesma base: 2,2 min local x 19,6 min na rede num
dia normal. Em 15/10 o processamento passou de 4 horas, ficou pela metade e
deixou um -journal quente ao lado do banco.

Fluxo:
  1. `preparar_copia_local`: sob o lock, resolve gravacao pela metade no banco
     da rede (abre e faz BEGIN IMMEDIATE/ROLLBACK, que aplica o -journal quente;
     -wal orfao e' tratado pela ConexaoBancoDados) e copia o arquivo para uma
     pasta local. Confere a copia (quick_check).
  2. O Processador roda inteiro sobre a copia local.
  3. `publicar`: confere a copia, grava ao lado do banco da rede com nome
     temporario e troca de uma vez (os.replace). O banco da rede nunca fica
     pela metade: ou e' o antigo inteiro, ou o novo inteiro.

Se o Processador cair antes de publicar, o banco da rede fica intacto. Os
arquivos que ele ja tinha movido para PROCESSADOS/ERROS voltam ao lugar
(`leitor_base.desfazer_movimentos`) e as interacoes ficam na pasta
INTERACOES_processando* para a proxima execucao.
"""
import os
import shutil
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from loguru import logger

from infraestrutura.banco_dados.conexao import ConexaoBancoDados


def _quick_check(caminho: Path) -> bool:
    con = sqlite3.connect(str(caminho), timeout=30)
    try:
        return con.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    finally:
        con.close()


def _resolver_gravacao_pela_metade(banco: Path) -> None:
    """Deixa o banco da rede consistente ANTES de copiar so' o arquivo .db.

    -journal quente (processamento interrompido em modo DELETE): abrir e pegar
    a trava de escrita faz o SQLite aplicar o rollback e apagar o journal.
    Copiar o .db sem isto copiaria um banco pela metade."""
    journal = Path(str(banco) + "-journal")
    if journal.exists():
        logger.warning(
            f"'{journal.name}' encontrado ao lado do banco — gravacao interrompida. "
            f"Desfazendo pelo SQLite antes de copiar.")
    con = sqlite3.connect(str(banco), timeout=60)
    try:
        con.execute("BEGIN IMMEDIATE")
        con.execute("ROLLBACK")
    finally:
        con.close()
    # -wal orfao / banco em WAL: mesma regra do resto do projeto
    ConexaoBancoDados(str(banco))._garantir_journal_delete()


def preparar_copia_local(banco_rede: Path, pasta_local: Path) -> Path:
    """Copia o banco da rede para `pasta_local` e devolve o caminho da copia.
    Banco inexistente na rede (primeira carga): devolve o caminho local vazio."""
    pasta_local.mkdir(parents=True, exist_ok=True)
    local = pasta_local / banco_rede.name
    for ext in ("", "-journal", "-wal", "-shm"):
        p = Path(str(local) + ext)
        if p.exists():
            p.unlink()
    if not banco_rede.exists() or banco_rede.stat().st_size == 0:
        logger.info("Banco da rede ainda nao existe — processando um banco novo local.")
        return local
    _resolver_gravacao_pela_metade(banco_rede)
    inicio = datetime.now()
    shutil.copy2(str(banco_rede), str(local))
    if not _quick_check(local):
        raise RuntimeError(f"Copia local do banco nao passou no quick_check: {local}")
    logger.info(
        f"Banco copiado da rede para processamento local "
        f"({banco_rede.stat().st_size / 2**20:.1f} MB em "
        f"{(datetime.now() - inicio).total_seconds():.0f}s): {local}")
    return local


def publicar(banco_local: Path, banco_rede: Path) -> None:
    """Publica a copia local no lugar do banco da rede, de uma vez."""
    if not _quick_check(banco_local):
        raise RuntimeError(f"Banco processado nao passou no quick_check — NAO publicado: {banco_local}")
    banco_rede.parent.mkdir(parents=True, exist_ok=True)
    temp = banco_rede.with_name(banco_rede.name + ".publicando")
    inicio = datetime.now()
    shutil.copy2(str(banco_local), str(temp))
    if temp.stat().st_size != banco_local.stat().st_size:
        temp.unlink()
        raise RuntimeError("Copia para a rede incompleta — banco da rede mantido.")
    # Nenhum journal pode sobrar ao lado do banco novo: o SQLite o aplicaria
    # por cima e corromperia o banco publicado.
    carimbo = f"{datetime.now():%Y%m%d_%H%M%S}"
    for ext in ("-journal", "-wal", "-shm"):
        orf = Path(str(banco_rede) + ext)
        if orf.exists():
            shutil.move(str(orf), str(orf) + f".orfao_{carimbo}")
            logger.warning(f"'{orf.name}' movido para '.orfao_{carimbo}' antes de publicar.")
    os.replace(str(temp), str(banco_rede))
    logger.success(
        f"Banco publicado na rede ({banco_rede.stat().st_size / 2**20:.1f} MB em "
        f"{(datetime.now() - inicio).total_seconds():.0f}s): {banco_rede}")


class ProcessamentoCancelado(Exception):
    """O arquivo de processamento (lock) foi apagado — ou passou a ser de outra
    execucao — no meio do processamento: o Processador para."""


class BatimentoLock:
    """Sinal de vida do lock de processamento: reescreve o lock a cada
    `intervalo` segundos enquanto o Processador roda. A 1a linha e' sempre o
    ultimo batimento — quem le so' a 1a linha (o Visualizador, versoes
    anteriores) ve um lock "recente" enquanto o dono estiver vivo.

    CANCELAMENTO (20/10/2026): o lock e' tambem o "arquivo de processando".
    Apagar o lock cancela o Processador: `conferir()` roda a cada passo e, se o
    lock sumiu (ou nao tem mais as linhas desta execucao), levanta
    ProcessamentoCancelado. O batimento NUNCA recria um lock apagado (abre com
    "r+", que falha se o arquivo nao existe) e `liberar()` so' apaga o lock se
    ele ainda for desta execucao."""

    def __init__(self, lock: Path, conteudo_fixo: str, intervalo: float = 60.0):
        self._lock = lock
        self._fixo = conteudo_fixo
        self._intervalo = intervalo
        self._parar = threading.Event()
        self._thread = None
        self._mutex = threading.Lock()   # batimento x conferir no mesmo processo
        self.perdido = False

    def _e_meu(self) -> bool:
        try:
            return self._fixo in self._lock.read_text(encoding="utf-8")
        except FileNotFoundError:
            return False
        except OSError:
            return True      # oscilacao da rede na leitura: na duvida, segue

    def gravar(self) -> None:
        agora = datetime.now().isoformat(timespec="seconds")
        with self._mutex:
            if self.perdido:
                return
            if not self._e_meu():
                self.perdido = True
                logger.warning("Lock: arquivo de processamento apagado ou tomado por "
                               "outra execucao — o Processador vai parar no proximo passo.")
                return
            try:
                with open(self._lock, "r+", encoding="utf-8") as f:
                    f.seek(0)
                    f.write(f"{agora}\nbatimento={agora}\n{self._fixo}")
                    f.truncate()
            except FileNotFoundError:
                self.perdido = True
            except Exception as e:
                logger.warning(f"Lock: nao consegui atualizar o sinal de vida ({e!r}).")

    def conferir(self, passo: str = "") -> None:
        """Chamado a cada passo do Processador: para se o lock sumiu."""
        with self._mutex:
            if not self.perdido and not self._e_meu():
                self.perdido = True
        if self.perdido:
            raise ProcessamentoCancelado(
                f"arquivo '{self._lock.name}' apagado (ou de outra execucao)"
                + (f" antes de: {passo}" if passo else ""))

    def liberar(self) -> None:
        """Fim do processamento: para o batimento e apaga o lock, se for nosso."""
        self.parar()
        with self._mutex:
            if self._e_meu():
                try:
                    self._lock.unlink()
                except Exception:
                    pass

    def _loop(self):
        while not self._parar.wait(self._intervalo):
            self.gravar()

    def iniciar(self) -> "BatimentoLock":
        self._thread = threading.Thread(target=self._loop, name="batimento-lock", daemon=True)
        self._thread.start()
        return self

    def parar(self) -> None:
        self._parar.set()
        if self._thread:
            self._thread.join(timeout=5)
