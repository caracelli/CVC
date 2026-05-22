# -*- coding: utf-8 -*-
"""Repositorio de interacoes multiusuario (arquivos .jsonl na rede).

Cada usuario escreve SO no proprio arquivo `interacao_<usuario>.jsonl` — um
escritor por arquivo, o que e' seguro mesmo sobre SMB. A leitura percorre todos
os arquivos da pasta.

Cada linha e' um objeto JSON completo:
    {"tipo_interacao": "QUARENTENA", "registro_id": "<matricula>",
     "acao": "ENVIAR"|"RESOLVER", "usuario": "<quem fez>",
     "data_acao": "2026-05-22T14:33", ...}
"""
import json
import os


def _sanitizar(usuario: str) -> str:
    return "".join(ch if (ch.isalnum() or ch in "._-") else "_"
                   for ch in (usuario or "anon"))


def arquivo_do_usuario(pasta_interacoes: str, usuario: str) -> str:
    """Caminho do .jsonl de um usuario."""
    return os.path.join(pasta_interacoes, f"interacao_{_sanitizar(usuario)}.jsonl")


def gravar(pasta_interacoes: str, interacao: dict, usuario: str) -> None:
    """Anexa uma interacao ao .jsonl do usuario (uma linha, um write)."""
    os.makedirs(pasta_interacoes, exist_ok=True)
    linha = json.dumps(interacao, ensure_ascii=False)
    with open(arquivo_do_usuario(pasta_interacoes, usuario),
              "a", encoding="utf-8") as f:
        f.write(linha + "\n")


def ler_todas(pasta_interacoes: str) -> list:
    """Le todas as interacoes de todos os .jsonl da pasta.

    Tolerante: linha final incompleta ou corrompida e' ignorada (vira completa
    na proxima leitura). [] se a pasta nao existe."""
    todas = []
    if not pasta_interacoes or not os.path.isdir(pasta_interacoes):
        return todas
    for nome in sorted(os.listdir(pasta_interacoes)):
        if not nome.lower().endswith(".jsonl"):
            continue
        caminho = os.path.join(pasta_interacoes, nome)
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                for linha in f:
                    linha = linha.strip()
                    if not linha:
                        continue
                    try:
                        todas.append(json.loads(linha))
                    except Exception:
                        pass  # linha incompleta/corrompida -> ignora
        except Exception:
            pass
    return todas


def consolidar(interacoes: list, tipo: str = None) -> dict:
    """Agrupa por registro_id e mantem a interacao de `data_acao` mais recente
    (regra "vence o mais recente"). Se `tipo` for dado, filtra por
    tipo_interacao. Devolve {registro_id: interacao}."""
    atual = {}
    for it in interacoes:
        if tipo and it.get("tipo_interacao") != tipo:
            continue
        rid = it.get("registro_id")
        if not rid:
            continue
        ant = atual.get(rid)
        if ant is None or str(it.get("data_acao", "")) >= str(ant.get("data_acao", "")):
            atual[rid] = it
    return atual
