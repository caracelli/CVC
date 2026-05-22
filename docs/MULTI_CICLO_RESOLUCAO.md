# Multi-ciclo de Resolução de Pendência — especificação

> **Status:** a implementar — trabalho focado, fora do escopo single-ciclo da
> Fase 1 atual. Documento versionado para não depender de memória.

## Cenário

A **mesma matrícula**, ao longo do tempo (vários processamentos), recebe
operações de acesso distintas — **inclusão**, **alteração**, **exclusão**. Cada
uma é uma pendência própria, identificada e resolvida no seu momento, sob seu
ticket do Jira. O Histórico da matrícula é a **linha do tempo** dessas
operações, e precisa ser navegável.

## Limitação atual (modelo single-ciclo)

- A tabela `resolucoes` tem chave = `registro_id` (matrícula) → **1 resolução
  por matrícula**.
- `construir_db` faz `u.resolvido = (u.u in _resolucoes_mescladas())` → uma vez
  resolvida, a matrícula fica **resolvida para sempre**.
- **Consequência (defeito para operação contínua):** se o Processador rodar de
  novo e a matrícula tiver uma pendência **nova**, a tela continua mostrando
  "Resolvido" — a pendência nova fica **mascarada**.

Para a Fase 1 (foto única: processa, resolve, entrega) o modelo single-ciclo
basta. O defeito só se manifesta a partir do 2º processamento.

## Solução — 3 partes

### 1. Resolução cobre pendências específicas (não a matrícula para sempre)

- O snapshot da resolução passa a guardar o **`id`** de cada pendência
  (`bi_divergencias.id` = `matricula_sistema_perfilesperado`).
- `construir_db`: para cada matrícula, comparar os `id` das pendências atuais
  (`bi_divergencias`) com os `id` já resolvidos. Pendência com `id` **não
  resolvido** → a matrícula é **Pendente** (novo ciclo). As já resolvidas
  permanecem resolvidas.
- `resolver_pendencia` já captura o snapshot das pendências — só falta incluir
  o `id` em cada item de `pendencias`.

### 2. Chave `resolucoes` = matrícula + data

- A PK passa de `registro_id` para `(registro_id, resolvido_em)` — ou um `id`
  autoincrement com índice em `registro_id`. Cada ciclo = 1 registro.
- `dobrar_interacoes.py` deixa de usar `INSERT OR REPLACE` por matrícula —
  passa a inserir cada ciclo.
- `_resolucoes_db` / `_resolucoes_mescladas` passam a devolver **lista de
  ciclos** por matrícula (hoje devolvem 1).
- `listar_historico_rh` gera o par "Pendência identificada" / "Pendência
  resolvida" **por ciclo**.

### 3. Popup único navegável

- Os dois popups atuais (`_modalDetalhe` / `_modalResolucao`) viram **um popup
  navegável**: rodapé com `‹ Anterior · "X de N" · Próximo ›`.
- Percorre toda a linha do tempo da matrícula e **ajusta o formato sozinho**
  por item — detalhe da pendência ou resolução.
- Largura fixa (560px) para não "pular" ao alternar de formato.

## O que dispara o novo ciclo

Não é "reabrir" um resolvido manualmente. O ciclo 2 nasce quando o Processador
detecta, num processamento seguinte, uma pendência (`id`) para a matrícula que
não está coberta por nenhuma resolução existente.

## Por que está adiado

- Só se manifesta com **múltiplos processamentos** ao longo do tempo — não há
  como validar numa foto única.
- Mexe no **núcleo** do rastreamento de "resolvido" — merece implementação
  dedicada, não encaixada no fim de uma rodada longa.
- Conecta-se ao **fluxo de 3 estados do Jira** (Pendente → Enviado ao Jira →
  Resolvido) — ver memória do projeto.

## Quando implementar

Junto com a etapa de integração com o Jira / preparação para operação
contínua. A base atual (dobra de resolução single-ciclo) está coberta por
`tests/test_regras_fase1.py :: TestDobraResolucaoHistorico`.
