# Envelope das Interações Multiusuário — v1

**Status:** estável e congelado a partir de 28/05/2026 (branch `sig-fase1`).
**Versão:** 1
**Arquivo de origem:** `INTERACOES/interacao_<usuario>.jsonl` (append-only, um por usuário, na pasta da rede)

---

## Por que este documento existe

Os JSONL de interação são **a parte mais arriscada** do sistema de fazer evoluir
depois do go-live. Diferente do banco SQLite (que dá pra migrar com `ALTER TABLE`),
os arquivos `.jsonl` na pasta da rede **acumulam para sempre** — toda interação
gravada em produção precisa continuar sendo lida pelo consumer (`dobrar_interacoes`)
mesmo depois de várias evoluções do código.

Este documento **trava o contrato**. Qualquer mudança aqui exige co-evolução do
consumer + bump de `schema_version` + migration explícita.

---

## Estrutura

Cada linha do `.jsonl` é um objeto JSON com **6 campos obrigatórios**:

```json
{
  "schema_version": 1,
  "tipo_interacao": "QUARENTENA",
  "registro_id": "12345",
  "acao": "ENVIAR",
  "usuario": "joao.silva",
  "data_acao": "2026-05-28T10:23:45",
  "extras": {},
  "nome": "Joao Silva",
  "sistema": "SYSTUR",
  "...": "demais campos específicos do tipo"
}
```

### Campos obrigatórios (NUNCA mudam)

| Campo | Tipo | Descrição |
|---|---|---|
| `schema_version` | int | Versão do envelope. **Sempre 1** nesta versão |
| `tipo_interacao` | str | `QUARENTENA` ou `RESOLUCAO` (append-only) |
| `registro_id` | str | Chave estável da entidade (matrícula, normalmente) |
| `acao` | str | Verbo do tipo: `ENVIAR`, `RESOLVER`, ... (append-only por tipo) |
| `usuario` | str | Quem fez a ação (`getpass.getuser()` da máquina origem) |
| `data_acao` | str | ISO-8601 sem timezone: `YYYY-MM-DDTHH:MM:SS` |

### Campo de evolução

| Campo | Tipo | Descrição |
|---|---|---|
| `extras` | dict | **Aberto**. Qualquer chave nova vai aqui — não exige bump de schema |

### Campos específicos do tipo

Cada `tipo_interacao` tem seus campos próprios além do envelope. Eles podem
ser **adicionados** livremente (consumer ignora desconhecidos), mas **não
podem ser renomeados nem ter tipo trocado**.

#### QUARENTENA

```json
{
  "schema_version": 1, "tipo_interacao": "QUARENTENA",
  "registro_id": "12345", "acao": "ENVIAR",
  "usuario": "...", "data_acao": "...", "extras": {},
  "nome": "Joao Silva",
  "sistema": "SYSTUR",
  "origem": "Inclusão / Alteração"
}
```

`acao` válidas: `ENVIAR`, `RESOLVER`.

#### RESOLUCAO

```json
{
  "schema_version": 1, "tipo_interacao": "RESOLUCAO",
  "registro_id": "12345", "acao": "RESOLVER",
  "usuario": "...", "data_acao": "...", "extras": {},
  "ticket": "IAM-1234",
  "ticket_url": "https://jira.cvc.com.br/browse/IAM-1234",
  "descricao": "Texto livre do resolvedor",
  "pendencias": [...],
  "cargo": "ANALISTA OPERACOES",
  "centro_custo": "01.04.02.03",
  "nome": "Joao Silva"
}
```

`acao` válidas: `RESOLVER`.

---

## Regras que não podem mudar

Estas regras travam o contrato. Mudá-las **quebra** os JSONL gravados em produção:

1. **Nomes e tipos dos 6 campos obrigatórios** — nunca mudam
2. **`schema_version`** é monotônico crescente. Bump exige migration explícita
3. **Vocabulários** (`tipo_interacao`, `acao`) são **append-only**:
   - Adicionar novo valor: ✅ ok
   - Remover ou renomear valor existente: ❌ proibido (quebra histórico)
4. **Compatibilidade legado v0**: registros gravados antes de 28/05/2026 não
   têm `schema_version`. O consumer trata como v0 implícito e continua lendo.
   **Esta tolerância nunca pode ser removida.**

---

## Como evoluir sem quebrar

### Adicionar campo opcional → usar `extras`

```json
{
  "schema_version": 1, "tipo_interacao": "RESOLUCAO", ...,
  "extras": {
    "anexos": ["s3://bucket/file.pdf"],
    "aprovador": "maria.santos"
  }
}
```

Consumer atual ignora `extras`. Consumer futuro lê os campos.

### Adicionar campo de primeira classe → ok, com cuidado

Pode adicionar campos no topo do envelope (não dentro de `extras`) desde que:
- Sejam **opcionais** (consumer atual continua funcionando sem eles)
- Documentados aqui

### Adicionar novo `tipo_interacao` ou `acao` → ok

Mas atualizar este doc + o consumer.

### Mudar tipo de campo ou renomear → **proibido sem bump de schema**

Exige:
1. Bump `SCHEMA_VERSION` em `repositorio_interacoes.py`
2. Consumer (`dobrar_interacoes.py`) deve detectar versão e aplicar normalização
3. Atualizar este doc com seção "v2"

---

## Onde isso vive no código

| Componente | Arquivo |
|---|---|
| Constante `SCHEMA_VERSION` | `src/infraestrutura/interacoes/repositorio_interacoes.py` |
| Função `gravar()` (escrita) | idem |
| Função `ler_todas()` (leitura tolerante) | idem |
| Consumer (consolidação) | `src/aplicacao/casos_de_uso/dobrar_interacoes.py` |
| Tabelas de destino | `quarentena`, `quarentena_historico`, `resolucoes` (em `iam_analytics.db`) |
