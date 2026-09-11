# -*- coding: utf-8 -*-
"""Pacote da BRUNA com o banco JA PROCESSADO — para quando ela nao vai rodar o
Processador (decisao de 11/09/2026).

Parte do UPDATE_BRUNA ja conferido (EXECUTAVEIS/ + ENTRADA/ de referencia) e
acrescenta DADOS/BANCO/iam_analytics.db — a base DELA reprocessada aqui com o
codigo do pacote.

O QUE NAO VIAJA, DE PROPOSITO: INTERACOES/. As tratativas que ela registrou
desde a ultima dobra estao nos .jsonl dela; o painel as le ao vivo e o proximo
Processador as dobra no banco. Mandar INTERACOES apagaria esse trabalho.

O banco sai por `sqlite3.backup` (e nao copia do arquivo): consolida o WAL e
gera um .db unico e consistente, sem -wal/-shm soltos que o Windows poderia
parear com o arquivo errado.

Uso:  python build_update_bruna_com_banco.py <zip base> <banco processado> <zip saida>
"""
import sqlite3
import sys
import tempfile
import zipfile
from pathlib import Path

DESTINO_BANCO = "DADOS/BANCO/iam_analytics.db"


def copia_limpa(banco: Path) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="bruna_banco_")) / "iam_analytics.db"
    src = sqlite3.connect(f"file:{banco}?mode=ro", uri=True)
    dst = sqlite3.connect(tmp)
    with dst:
        src.backup(dst)
    src.close()
    c = sqlite3.connect(tmp)
    ok = c.execute("PRAGMA integrity_check").fetchone()[0]
    c.execute("PRAGMA journal_mode=DELETE")    # .db unico, sem -wal
    c.close()
    if ok != "ok":
        raise SystemExit(f"FALHA: integrity_check do banco -> {ok}")
    return tmp


def main(argv):
    if len(argv) != 4:
        print(__doc__)
        return 1
    base, banco, saida = Path(argv[1]), Path(argv[2]), Path(argv[3])
    for p in (base, banco):
        if not p.exists():
            print(f"FALHA: nao existe -> {p}")
            return 1
    limpo = copia_limpa(banco)
    with zipfile.ZipFile(base) as zin:
        nomes = zin.namelist()
        if any(n.startswith(("DADOS/", "INTERACOES/")) for n in nomes):
            print("FALHA: o zip base ja traz DADOS/ ou INTERACOES/ — nao e' o UPDATE_BRUNA")
            return 1
        with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zout:
            for info in zin.infolist():
                zout.writestr(info, zin.read(info.filename))
            zout.write(limpo, DESTINO_BANCO)
    final = zipfile.ZipFile(saida).namelist()
    assert DESTINO_BANCO in final
    assert not any(n.startswith("INTERACOES/") for n in final), "INTERACOES vazou"
    print(f"OK -> {saida}  ({saida.stat().st_size/1024/1024:.1f} MB, {len(final)} arquivos)")
    print(f"     banco: {limpo.stat().st_size/1024/1024:.1f} MB, integrity_check ok, sem INTERACOES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
