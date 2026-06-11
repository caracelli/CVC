# -*- coding: utf-8 -*-
"""Gera um ZIP com o PROJETO (codigo-fonte) para atualizar o repositorio do
cliente. Inclui o estado ATUAL do working tree (arquivos versionaveis), porem
SEM:
  - artefatos criados: *.exe, *.zip
  - config de git: .git/, .gitignore, .gitattributes
  - caches: __pycache__/, *.pyc
  - dados/referencia: Arquivos_origem/, OLD/, ENTREGA/

O conjunto de arquivos vem do git (tracked + novos nao-ignorados), entao tudo
que o .gitignore ja exclui (DADOS, INTERACOES, ENTRADA, executaveis...) fica de
fora automaticamente. As paths no zip sao relativas a raiz do projeto, para
descompactar POR CIMA da pasta do cliente.

Uso:  cd deploy && python build_zip_cliente.py
Gatilho: quando o usuario disser "prepare para o git do cliente".
"""
import fnmatch
import subprocess
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
# fora da arvore do projeto, p/ nao se auto-incluir nem entrar no git/LFS
SAIDA = RAIZ.parent / "PROJETO_CVC_CLIENTE.zip"

EXCLUI_EXATO = {".gitignore", ".gitattributes"}
EXCLUI_GLOB = ["*.exe", "*.zip", "*.pyc"]
EXCLUI_PREFIXO = ("Arquivos_origem/", "OLD/", "ENTREGA/", ".git/",
                  "__pycache__/", "INTERACOES/")


def _git(args):
    r = subprocess.run(["git"] + args, cwd=str(RAIZ),
                       capture_output=True, text=True)
    return [l for l in r.stdout.splitlines() if l.strip()]


def _listar_arquivos():
    # tracked + novos (nao-ignorados) = estado atual versionavel do working tree
    tracked = _git(["ls-files"])
    novos = _git(["ls-files", "--others", "--exclude-standard"])
    return sorted(set(tracked) | set(novos))


def _incluir(rel: str) -> bool:
    if rel in EXCLUI_EXATO:
        return False
    if rel.startswith(EXCLUI_PREFIXO):
        return False
    if "/__pycache__/" in rel:
        return False
    nome = rel.rsplit("/", 1)[-1]
    return not any(fnmatch.fnmatch(nome, g) for g in EXCLUI_GLOB)


def main():
    arquivos = [f for f in _listar_arquivos() if _incluir(f)]
    if SAIDA.exists():
        SAIDA.unlink()
    n = 0
    with zipfile.ZipFile(SAIDA, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel in arquivos:
            p = RAIZ / rel
            if p.is_file():
                z.write(p, rel)
                n += 1
    print(f"OK -> {SAIDA}")
    print(f"  {n} arquivos | {SAIDA.stat().st_size/1024/1024:.2f} MB")
    print("  Descompacte POR CIMA da pasta do repositorio do cliente.")


if __name__ == "__main__":
    main()
