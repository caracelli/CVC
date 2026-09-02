"""Confere um pacote de entrega em tres niveis.

1. index.html do zip == index.html do HEAD (byte a byte) + marcadores do dia
2. codigo DENTRO dos launcher/*.exe (os .pyc vao comprimidos: grep cru nao serve)
3. config.xml: versao, raiz, gera_pendencia, e ausencia de jira.xml com credencial

Uso: python confere_pacote.py <caminho do zip> [...]
"""
import hashlib
import io
import re
import subprocess
import sys
import zipfile
from pathlib import Path

RAIZ = Path(r"c:\Users\user\OneDrive\Backup Note\Projetos\Antlia\cvc\CVC")
REL_INDEX = "CVC_IAM_ANALYTICS/EXECUTAVEIS/REPORT/index.html"

MARCADORES = [
    "invalidarCacheAPI()",   # 02d4822 escrita invalida o cache
    "fetchAPI(",             # 1f5284a cache por token
    "/api/versao",           # 0d4d95e refresh condicional
    "_FORCA_APOS_MS",        # rede de seguranca do refresh
    "_TETO_SIS",             # 214e506 teto por (categoria,sistema)
    "ver detalhe",           # 7fd20e6 navegacao no drawer
    "172px",                 # 214e506 alinhamento em duas colunas
    "_csSemMapeamento",      # 2o doc: "nao mapeado" x "mapeado e nao tem"
]

# (marcador, em qual exe deve estar)
DENTRO_DOS_EXES = [
    ("launcher/launcher_processador.exe", b"PERFIL_EXCESSIVO"),
    ("launcher/launcher_processador.exe", b"perfil_excessivo"),
    ("launcher/launcher_visualizador.exe", b"token_mudanca"),
    ("launcher/launcher_visualizador.exe", b"/api/versao"),
]


def sha(b):
    return hashlib.sha256(b).hexdigest()


def _sem_eol(b: bytes) -> bytes:
    """Normaliza CRLF -> LF para comparar conteudo, nao fim de linha."""
    return b.replace(b"\r\n", b"\n")


def le_exe_interno(dados: bytes) -> bytes:
    """Concatena TODO o codigo dentro de um exe do PyInstaller.

    Usa o leitor do proprio PyInstaller. A varredura por blocos zlib "no olho"
    que eu tinha escrito antes deu FALSO NEGATIVO no launcher_visualizador:
    disse que `token_mudanca` nao estava la, e estava (modulo `main`).
    """
    import tempfile
    from dentro_do_exe import modulos
    with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as f:
        f.write(dados)
        tmp = f.name
    try:
        return b"\n".join(modulos(Path(tmp)).values())
    finally:
        try:
            Path(tmp).unlink()
        except OSError:
            pass


def confere(caminho: Path):
    print("\n" + "=" * 72)
    print(caminho.name, f"({caminho.stat().st_size/1024/1024:.1f} MB)")
    print("=" * 72)
    z = zipfile.ZipFile(caminho)
    ruim = z.testzip()
    print(f"  integridade do zip .......... {'OK' if ruim is None else 'CORROMPIDO ' + str(ruim)}")
    nomes = z.namelist()
    print(f"  arquivos .................... {len(nomes)}")

    ok_tudo = ruim is None

    # -------------------------------------------------- 1. index.html
    alvo = [n for n in nomes if n.endswith("REPORT/index.html")]
    if not alvo:
        print("  index.html .................. AUSENTE")
        ok_tudo = False
    else:
        pk = z.read(alvo[0])
        head = subprocess.run(["git", "show", f"HEAD:{REL_INDEX}"],
                              cwd=str(RAIZ), capture_output=True).stdout
        # Compara IGNORANDO fim de linha. O working tree grava CRLF (autocrlf
        # do Windows) e o blob do git guarda LF, entao a comparacao byte a byte
        # reprova um pacote CORRETO: em 02/09 acusou 385.726 x 378.210 bytes, e
        # a diferenca era exatamente 7.516 — o numero de linhas do arquivo.
        # Conferidor que da falso negativo custa mais caro que conferidor
        # nenhum: manda regerar o que ja estava certo.
        igual = sha(_sem_eol(pk)) == sha(_sem_eol(head))
        print(f"  index.html == HEAD .......... {'OK' if igual else 'DIFERENTE'}"
              f"  ({len(pk)} bytes, sha {sha(pk)[:16]})")
        ok_tudo &= igual
        txt = pk.decode("utf-8", errors="replace")
        faltam = [m for m in MARCADORES if m not in txt]
        print(f"  marcadores no painel ........ {len(MARCADORES)-len(faltam)}/{len(MARCADORES)}"
              + (f"  FALTAM: {faltam}" if faltam else ""))
        ok_tudo &= not faltam

    # -------------------------------------------------- 2. dentro dos exes
    cache = {}
    for rel, marca in DENTRO_DOS_EXES:
        cand = [n for n in nomes if n.endswith(rel)]
        if not cand:
            print(f"  {rel} .. AUSENTE")
            ok_tudo = False
            continue
        if cand[0] not in cache:
            cache[cand[0]] = le_exe_interno(z.read(cand[0]))
        dentro = marca in cache[cand[0]]
        print(f"  {Path(rel).name:32s} {marca.decode():22s} {'OK' if dentro else 'NAO ENCONTRADO'}")
        ok_tudo &= dentro

    # -------------------------------------------------- 3. config
    cfg = [n for n in nomes if n.endswith("CONFIG/config.xml")]
    if not cfg:
        print("  config.xml .................. AUSENTE")
        ok_tudo = False
    else:
        c = z.read(cfg[0]).decode("utf-8", errors="replace")
        def tag(t):
            m = re.search(r"<%s>(.*?)</%s>" % (t, t), c, re.S)
            return m.group(1).strip() if m else "(ausente)"
        raiz_vazia = bool(re.search(r"<raiz\s*/>|<raiz>\s*</raiz>", c))
        print(f"  config: versao .............. {tag('versao')}")
        print(f"  config: raiz vazia (local) .. {'OK' if raiz_vazia else 'TEM RAIZ: ' + tag('raiz')}")
        print(f"  config: gera_pendencia ...... {tag('gera_pendencia')}")
        ok_tudo &= raiz_vazia

    # O que nao pode viajar e' a CREDENCIAL, nao o arquivo: o build gera um
    # jira.xml modelo com <usuario>/<token> VAZIOS de proposito. A regra antiga
    # ("existe jira.xml -> reprova") deu falso positivo no pacote completo.
    jira = [n for n in nomes if n.endswith("jira.xml")]
    vazado = []
    for n in jira:
        j = z.read(n).decode("utf-8", errors="replace")
        for campo in ("usuario", "token", "senha", "api_token"):
            for m in re.finditer(r"<%s>([^<]*)</%s>" % (campo, campo), j):
                if m.group(1).strip():
                    vazado.append(f"{n}:<{campo}>")
    if not jira:
        print("  credencial do Jira .......... nenhum jira.xml (ok)")
    elif not vazado:
        print(f"  credencial do Jira .......... modelo com campos VAZIOS (ok) — {jira[0].split('/')[-1]}")
    else:
        print(f"  credencial do Jira .......... VAZANDO: {vazado}")
    ok_tudo &= not vazado

    print(f"\n  >>> {caminho.name}: {'APROVADO' if ok_tudo else 'REPROVADO'}")
    return ok_tudo


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    tudo = True
    for arg in sys.argv[1:]:
        tudo &= confere(Path(arg))
    print("\n" + ("TODOS APROVADOS" if tudo else "HA PACOTE REPROVADO"))
    sys.exit(0 if tudo else 1)
