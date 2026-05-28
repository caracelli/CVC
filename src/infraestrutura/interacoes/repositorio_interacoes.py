# -*- coding: utf-8 -*-
"""Repositorio de interacoes multiusuario (arquivos .jsonl na rede).

Cada usuario escreve SO no proprio arquivo `interacao_<usuario>.jsonl` — um
escritor por arquivo, o que e' seguro mesmo sobre SMB. A leitura percorre todos
os arquivos da pasta.

============================================================================
ENVELOPE v1 — CONTRATO ESTAVEL
============================================================================
Toda interacao gravada a partir de 28/05/2026 segue o envelope v1:

    {
      "schema_version": 1,            # SEMPRE 1 — bump so com migration
      "tipo_interacao": "QUARENTENA"|"RESOLUCAO",
      "registro_id": "<id>",          # matricula, ou outra chave estavel
      "acao": "ENVIAR"|"RESOLVER"|... # vocabulario do tipo
      "usuario": "<quem fez>",        # getpass.getuser() do origem
      "data_acao": "ISO-8601",        # YYYY-MM-DDTHH:MM:SS
      "extras": {}                    # dict aberto pra evolucao sem mudar envelope
      # ... outros campos especificos do tipo (cargo, ticket, etc.)
    }

REGRAS QUE NAO PODEM MUDAR (quebrariam interacoes em producao):
- Os 6 campos obrigatorios (schema_version, tipo_interacao, registro_id,
  acao, usuario, data_acao) NUNCA mudam de nome ou tipo
- schema_version=1 e' fixo nesta versao; bump exige co-evolucao do dobrador
- Vocabulario de tipo_interacao e acao e' append-only (novos valores ok,
  remover valor existente quebra historico)

PRA EVOLUIR SEM QUEBRAR:
- Campos novos especificos vao em `extras: dict` (livre)
- Campos especificos do tipo podem ser adicionados no topo (consumer ignora desconhecidos)

LEGADO (v0 — antes de 28/05/2026):
- Nao tinha schema_version nem extras
- Consumer (dobrar_interacoes) e' tolerante: trata como v0 implicito
- Tudo o que ja esta gravado continua sendo lido normalmente

Ver tambem: docs/INTERACOES_ENVELOPE_V1.md
============================================================================
"""
import json
import os
from datetime import datetime

SCHEMA_VERSION = 1


def _sanitizar(usuario: str) -> str:
    return "".join(ch if (ch.isalnum() or ch in "._-") else "_"
                   for ch in (usuario or "anon"))


def arquivo_do_usuario(pasta_interacoes: str, usuario: str) -> str:
    """Caminho do .jsonl de um usuario."""
    return os.path.join(pasta_interacoes, f"interacao_{_sanitizar(usuario)}.jsonl")


def _envelope(interacao: dict) -> dict:
    """Garante campos obrigatorios do envelope v1, sem perder nada que o caller
    ja preencheu. Se vier sem schema_version, injeta v1. Se vier sem extras,
    injeta extras={}. Demais campos passam por cima do passado."""
    out = dict(interacao or {})
    out.setdefault("schema_version", SCHEMA_VERSION)
    out.setdefault("extras", {})
    if "data_acao" not in out:
        out["data_acao"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    return out


def gravar(pasta_interacoes: str, interacao: dict, usuario: str) -> None:
    """Anexa uma interacao ao .jsonl do usuario (uma linha, um write).
    Aplica o envelope v1 (preenche schema_version, extras, data_acao se faltarem)."""
    os.makedirs(pasta_interacoes, exist_ok=True)
    env = _envelope(interacao)
    linha = json.dumps(env, ensure_ascii=False)
    with open(arquivo_do_usuario(pasta_interacoes, usuario),
              "a", encoding="utf-8") as f:
        f.write(linha + "\n")


def ler_todas(pasta_interacoes: str) -> list:
    """Le todas as interacoes de todos os .jsonl da pasta.

    Tolerante: linha final incompleta ou corrompida e' ignorada (vira completa
    na proxima leitura). [] se a pasta nao existe.

    Compat v0/v1: registros sem schema_version sao tratados como v0
    implicito — funcionam normalmente porque os campos obrigatorios
    do v1 ja existiam por convencao no v0."""
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
                        obj = json.loads(linha)
                        # Normaliza para v1 implicito (sem regravar; so na leitura)
                        if isinstance(obj, dict):
                            obj.setdefault("schema_version", 0)  # 0 = legado implicito
                            obj.setdefault("extras", {})
                        todas.append(obj)
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
