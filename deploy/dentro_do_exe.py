"""Procura strings DENTRO de um exe do PyInstaller, do jeito certo.

Usa o leitor do proprio PyInstaller (CArchiveReader + ZlibArchiveReader) para
abrir o PYZ e descomprimir cada .pyc. Varredura por blocos zlib "no olho" da
FALSO NEGATIVO — foi o que aconteceu com o launcher_visualizador.

Uso: python dentro_do_exe.py <exe> <string> [<string> ...]
"""
import io
import sys
import zlib
from pathlib import Path


def modulos(exe: Path):
    """Devolve {nome_do_modulo: codigo_fonte_bytes} de todos os .pyc do PYZ."""
    from PyInstaller.archive.readers import CArchiveReader

    car = CArchiveReader(str(exe))
    achados = {}

    # toc: {nome: (offset, tam_comprimido, tam, comprimido, tipo)} nas versoes
    # novas; nas antigas e' uma lista de tuplas. Tratamos os dois.
    itens = car.toc.items() if hasattr(car.toc, "items") else \
        [(t[-1], t) for t in car.toc]

    for nome, _ in itens:
        try:
            dados = car.extract(nome)
        except Exception:
            continue
        if isinstance(dados, tuple):
            dados = dados[1]
        if not isinstance(dados, (bytes, bytearray)):
            continue
        achados[nome] = bytes(dados)
        # o PYZ e' um arquivo dentro do arquivo
        if nome.endswith(".pyz") or nome == "PYZ-00.pyz":
            achados.update(_abrir_pyz(bytes(dados)))
    return achados


def _abrir_pyz(blob: bytes):
    """Descomprime cada entrada do PYZ (formato: cabecalho + TOC marshalado)."""
    import marshal
    saida = {}
    if not blob.startswith(b"PYZ\0"):
        return saida
    pos_toc = int.from_bytes(blob[8:12], "big")
    try:
        toc = marshal.loads(blob[pos_toc:])
    except Exception:
        return saida
    itens = toc.items() if hasattr(toc, "items") else toc
    for entrada in itens:
        try:
            nome, (_tipo, desloc, tam) = entrada
            saida[nome] = zlib.decompress(blob[desloc:desloc + tam])
        except Exception:
            continue
    return saida


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    exe = Path(sys.argv[1])
    alvos = [s.encode() for s in sys.argv[2:]]
    mods = modulos(exe)
    total = sum(len(v) for v in mods.values())
    print(f"{exe.name}: {len(mods)} entradas, {total/1024/1024:.1f} MB descomprimidos")
    tudo_ok = True
    for alvo in alvos:
        onde = [n for n, v in mods.items() if alvo in v]
        ok = bool(onde)
        tudo_ok &= ok
        amostra = ", ".join(onde[:3]) + (" …" if len(onde) > 3 else "")
        print(f"  {alvo.decode():24s} {'OK' if ok else 'NAO ENCONTRADO':16s} {amostra}")
    sys.exit(0 if tudo_ok else 1)


if __name__ == "__main__":
    main()
