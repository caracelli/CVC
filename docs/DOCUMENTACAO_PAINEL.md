# Documentação do painel IAM Analytics — CVC

Guia explicativo de cada tela, KPI, filtro, badge e tooltip do painel
servido por `visualizador.exe`.

---

## Índice

1. [Visão geral do produto](#1-visão-geral-do-produto)
2. [Abas (navegação principal)](#2-abas-navegação-principal)
3. [Cabeçalho do painel](#3-cabeçalho-do-painel)
4. [Aba Visão Geral](#4-aba-visão-geral)
5. [Aba Pendências](#5-aba-pendências)
6. [Aba Quarentena](#6-aba-quarentena)
7. [Aba Histórico](#7-aba-histórico)
8. [Aba Consulta](#8-aba-consulta)
9. [Filtros laterais](#9-filtros-laterais)
10. [Tooltips e textos do (i)](#10-tooltips-e-textos-do-i)
11. [Badges, cores e significados](#11-badges-cores-e-significados)
12. [Modais](#12-modais)
13. [Glossário](#13-glossário)

---

## 1. Visão geral do produto

O **IAM Analytics** confronta a base de RH da CVC com os extratos de acesso
dos sistemas corporativos (SYSTUR na Fase 1; SIGOT, SICA RA, SICA Esfera,
IC nas fases seguintes) e gera **pendências de acesso** quando há
divergência entre o que o cargo do funcionário exige (matriz) e o que
ele de fato possui.

O painel apresenta essas pendências em uma interface de governança —
**não** edita o banco diretamente: ações do usuário (enviar para
quarentena, resolver pendência sob ticket Jira) são registradas como
**interações** que o Processador consolida na próxima execução.

---

## 2. Abas (navegação principal)

| Aba | Função |
|---|---|
| **Visão Geral** | KPIs e gráficos resumindo as pendências do sistema em escopo |
| **Pendências** | Grade detalhada de todas as pendências (uma linha por funcionário/usuário) |
| **Consulta** | (Em construção) Consulta livre por filtros |
| **Histórico** | Trilha de auditoria das resoluções de pendências |
| **Quarentena** | Funcionários em quarentena (ativos e finalizados) |

Trocar de aba **força a releitura do banco** (atualiza a grid com o
estado mais recente, sem precisar dar F5).

---

## 3. Cabeçalho do painel

| Item | Significado |
|---|---|
| **Referência** | Mês/ano da data mais recente em `bi_divergencias.data_identificacao`. Indica o "fechamento" do cenário atualmente carregado |
| **Última atualização** | Mesma data acima, com hora — reflete quando o Processador rodou pela última vez |
| **Logo CVC** | Volta para a aba Visão Geral |

---

## 4. Aba Visão Geral

### KPIs (cards superiores)

Cinco cards no topo:

| Card | O que conta | Cor de barra |
|---|---|---|
| **Incluir Acesso** | Funcionários sem o acesso que a matriz exige (`status=SEM_ACESSO`) | Azul claro `#2980B9` |
| **Alterar Perfil** | Funcionários com perfil diferente do esperado (`status=DIVERGENTE`) | Azul escuro `#154360` |
| **Em Análise** | Cargos com mais de um perfil possível na matriz (`status=EM_ANALISE`) — requer decisão humana | Laranja `#E67E22` |
| **Total Não Mapeados** | Usuários no SYSTUR sem matrícula correspondente no RH ativo (`tipo=ACESSO_SEM_VINCULO_RH`) | Roxo `#7D3C98` |
| **Total c/ Ação** | Soma dos quatro acima — pendências totais | Verde `#1E8449` |

### Gráficos

| Gráfico | O que mostra |
|---|---|
| **Por Sistema** | Quantidade de pendências por sistema (Fase 1: SYSTUR) |
| **Por Ação** | Distribuição dos quatro tipos de ação (Incluir Acesso, Alterar Perfil, Em Análise, Não Mapeado) |

---

## 5. Aba Pendências

A grid mais importante. Cada linha é um **funcionário ou usuário** com
uma ou mais pendências.

### Colunas

| # | Coluna | Conteúdo | Observações |
|---|---|---|---|
| 1 | **Quarentena** | Botão de ação (ícone) | Envia o usuário para a aba Quarentena |
| 2 | _(expandir)_ | `+` / `−` | Expande detalhes (quando há mais de uma pendência) |
| 3 | **Vínculo** | `Funcionário` ou `Terceiro` | Para os "Não Mapeados", vem como Funcionário; com integração de Terceiros (futura), virá `Terceiro` |
| 4 | **Usuário/Acesso** | Login do usuário no sistema | Para "Não Mapeado", é o identificador do SYSTUR (ex.: `EXMP0001`) |
| 5 | **Qtd** | Número de pendências do usuário | Maior que 1 → linha agrupada com expand |
| 6 | **Nome** | Nome completo | Vem do RH (Funcionário) ou do SYSTUR (Não Mapeado) |
| 7 | **Matrícula** | Matrícula RH | Vazia para Não Mapeado |
| 8 | **Departamento** | Departamento do funcionário | Vem da matriz organizacional (CCO) |
| 9 | **Cargo** | Cargo do funcionário | Vem da base RH |
| 10 | **Tipo** | Badge com o tipo da pendência | Ver [seção 11](#11-badges-cores-e-significados) |
| 11 | **Perfil Encontrado** | Perfil que o usuário TEM no sistema | Vazio em "Sem Acesso" |
| 12 | **Perfil Esperado** | Perfil que a matriz EXIGE | Múltiplos separados por `\|` em "Em Análise" |
| 13 | **Data** | Quando a pendência foi identificada | `dd/mm/aaaa hh:mm:ss` |
| 14 | **Status** | Badge `Pendente` ou `Resolvido` | Resolvido = quem já passou pelo fluxo de Resolução |
| 15 | **Origem** | `Matriz <SISTEMA>` ou `Matriz CCO` ou `—` | Indica de qual fonte veio o perfil esperado |

### Ações nas linhas

- **Lupa (`🔍`)** — pendência **já resolvida**: abre modal com os dados da resolução (ticket Jira, descrição, quem resolveu).
- **Botão Resolver (`⊕`)** — pendência **pendente**: abre modal pra registrar a resolução sob ticket do Jira.
- **Botão Quarentena (1ª coluna)** — envia o usuário para a aba Quarentena por 90 dias (configurável).

### Filtros e ordenação na grid

- **Clique no nome da coluna**: ordena (clica de novo inverte).
- **Funil (ao lado do nome)**: filtro de valores tipo Excel (caixinhas marcáveis, busca por valor).
- **Filtros laterais**: ver [seção 9](#9-filtros-laterais).

---

## 6. Aba Quarentena

Dois sub-modos, controlados pela barra de toolbar no topo da página:

### "Ativas"
Funcionários atualmente em quarentena. Colunas:

| Coluna | Significado |
|---|---|
| Usuário | Login/matrícula |
| Nome | Nome do funcionário |
| Sistema | Sistema do acesso (SYSTUR) |
| Origem | "Inclusão / Alteração" (de onde veio) |
| Data início | Quando entrou na quarentena |
| Data fim | Quando sai automaticamente (início + 90 dias) |
| Criado por | Usuário do Windows que executou a ação |
| Ação | Botão **Retirar da quarentena** — encerra antes da data |

### "Histórico"
Quarentenas encerradas. Mesmas colunas, mais:

| Coluna | Significado |
|---|---|
| Data saída | Quando saiu da quarentena |
| Motivo | "Resolvido" (saiu por ação manual) |
| Encerrado por | Quem retirou |

---

## 7. Aba Histórico

Trilha de auditoria das **resoluções** de pendências. Cada resolução
gera **duas linhas**:

| Movimentação | Significado |
|---|---|
| **Pendência identificada** | Quando a divergência apareceu pela primeira vez (`MIN(data_identificacao)` em `bi_divergencias` da matrícula) |
| **Pendência resolvida** | Quando o usuário registrou a resolução sob ticket Jira (`resolucoes.resolvido_em`) |

A regra de coerência: **`Pendência resolvida` é sempre posterior a
`Pendência identificada`**.

### Colunas

| Coluna | Conteúdo |
|---|---|
| _(expandir)_ | Mostra detalhes adicionais quando agrupado por funcionário |
| **Matrícula** | Matrícula do funcionário |
| **Nome** | Nome completo |
| **Movimentação** | `Pendência identificada` ou `Pendência resolvida` (badge colorido) |
| **Data** | Data do evento |
| **Detalhe** | Ticket Jira (resolvida) ou "ver detalhes" (lupa para abrir modal completo) |

### Badges de movimentação

| Badge | Cor | Significado |
|---|---|---|
| `Pendência identificada` | Cinza `h-pen` | Linha que abre a trilha |
| `Pendência resolvida` | Verde `h-res` | Fecha a trilha sob ticket Jira |
| `Admitido` _(reservado)_ | Azul `h-adm` | Movimentação cadastral RH (atualmente não exibida) |
| `Alterado` _(reservado)_ | Amarelo `h-alt` | Movimentação cadastral RH (atualmente não exibida) |

### Exportação

Botão **Exportar Excel** exporta o histórico com a mesma estrutura
(agrupamentos por funcionário, mesma formatação visual).

---

## 8. Aba Consulta

Em construção. Será uma grade de consulta livre com filtros adicionais.
Os filtros serão definidos junto com o cliente.

---

## 9. Filtros laterais

Painel lateral esquerdo (todas as abas exceto Consulta). Funciona
**em conjunto** com a grid atual. Cinco filtros independentes:

| Filtro | Campo | Valores possíveis |
|---|---|---|
| **Vínculo** | `vinc` | `Funcionário`, `Terceiro` |
| **Ação** | `a` | `Incluir Acesso`, `Alterar Perfil`, `Em Análise`, `Não Mapeado` |
| **Status** | `s` | `Pendente`, `Resolvido` |
| **Tipo** | `tl` | `Sem Acesso`, `Divergente`, `Em Análise`, `Sem Vínculo RH` |
| **Sistema** | `sis` | `SYSTUR` (Fase 1); outros nas fases seguintes |

### Comportamento dos filtros

> "Clique **isola** o valor · `Ctrl+clique` **combina**"

- **Clique simples**: filtra só por esse valor, descarta os outros.
- **`Ctrl+clique`**: adiciona/remove o valor da seleção atual (multi-seleção).
- **Sem nada marcado**: tudo é mostrado.

### Tooltip (i) ao lado de cada valor

Pequeno ícone (i) ao lado dos valores: passa o mouse e mostra a
descrição. Os textos estão na [seção 10](#10-tooltips-e-textos-do-i).

---

## 10. Tooltips e textos do (i)

Aparecem nos filtros laterais e nos cards de pendência (modais).

### Ação

| Valor | Tooltip |
|---|---|
| **Incluir Acesso** | Funcionário sem o acesso que a matriz do cargo exige — precisa incluir o perfil. |
| **Alterar Perfil** | Funcionário com perfil diferente do permitido para o cargo — precisa alterar. |
| **Em Análise** | O cargo tem mais de um perfil possível na matriz — requer análise manual. |
| **Não Mapeado** | Acesso no sistema sem funcionário correspondente na base de RH ativa. |

### Tipo (mesma classificação, rótulo usado na grid)

| Valor | Tooltip |
|---|---|
| **Sem Acesso** | Funcionário sem o acesso que a matriz do cargo exige — precisa incluir o perfil. |
| **Divergente** | Funcionário com perfil diferente do permitido para o cargo — precisa alterar. |
| **Sem Vínculo RH** | Acesso no sistema sem funcionário correspondente na base de RH ativa. |

### Status

| Valor | Tooltip |
|---|---|
| **Pendente** | Pendência ainda não tratada. |
| **Resolvido** | Pendência já tratada e resolvida. |

---

## 11. Badges, cores e significados

### Badges de Tipo (na coluna **Tipo** da grid Pendências)

| Badge | Classe CSS | Cor | Origem na base |
|---|---|---|---|
| `Sem Acesso` | `b-sem-acesso` | Azul claro | `bi_divergencias.tipo='SEM_ACESSO'` |
| `Divergente` | `b-divergente` | Azul escuro | `bi_divergencias.tipo='DIVERGENTE'` |
| `Em Análise` | `b-em-analise` | Laranja | `bi_divergencias.tipo='EM_ANALISE'` |
| `Sem Vínculo RH` | `b-sem-vinculo` | Roxo | `bi_divergencias.tipo='ACESSO_SEM_VINCULO_RH'` |

### Badges de Status

| Badge | Classe CSS | Cor | Origem |
|---|---|---|---|
| `Pendente` | `b-pendente` | Amarelo | Calculado: ainda sem resolução |
| `Resolvido` | `b-resolvida` | Verde | Há registro em `resolucoes` para a matrícula |

### Badges de Movimentação (Histórico)

| Badge | Classe CSS | Cor |
|---|---|---|
| `Pendência identificada` | `h-pen` | Cinza |
| `Pendência resolvida` | `h-res` | Verde |
| `Admitido` _(reservado)_ | `h-adm` | Azul |
| `Alterado` _(reservado)_ | `h-alt` | Amarelo |

---

## 12. Modais

### Modal **Resolver pendência(s)**

Abre ao clicar no botão `⊕` (Resolver) em uma linha pendente.

| Campo | Obrigatório | Descrição |
|---|---|---|
| **N° do ticket do Jira** | Sim | Ex.: `IAM-1234`. Formato livre; ideal seguir o padrão Jira da CVC |
| **Link do ticket** | Não | URL completo do ticket (ex.: `https://jira.cvc.com.br/browse/IAM-1234`) |
| **Descrição** | Não | Observações sobre como/por que foi resolvido. Até 600 caracteres |

Ao confirmar: grava uma **interação RESOLUCAO** na rede (arquivo
`.jsonl` em `INTERACOES/`). Na próxima execução do Processador, a
interação é **consolidada** (dobrada) na tabela `resolucoes` e a
matrícula passa a aparecer como `Resolvido` na grid.

### Modal **Detalhes da resolução** (lupa)

Abre ao clicar na lupa (`🔍`) de uma linha já resolvida ou em "ver
detalhes" no Histórico. Mostra:

- Cargo e Centro de Custo na época da resolução
- Lista de pendências resolvidas (tipo, perfil encontrado → esperado)
- Ticket Jira (com link) + descrição
- Quem resolveu (usuário do Windows) e quando

### Modal **Detalhe da pendência** (no Histórico)

Aberto pelo botão "ver detalhes" na coluna **Detalhe** do Histórico
quando a movimentação é `Pendência identificada`. Mostra a divergência
original, antes da resolução.

---

## 13. Glossário

| Termo | Significado |
|---|---|
| **Pendência** | Diferença entre o que o cargo exige (matriz) e o acesso real do funcionário no sistema |
| **Matriz** | Mapa cargo → perfil(is) esperado(s) por sistema. Mantida pela CVC e importada pelo Processador |
| **Matriz CCO** | Override por centro de custo — quando um CC específico tem perfil próprio, sobrepondo a matriz de cargo |
| **Cargo** | Função RH do funcionário, com código (ex.: `AB001`) e descrição (ex.: `ANALISTA FISCAL PL`) |
| **Centro de Custo (CC)** | Estrutura organizacional, formato `XX.XX.XX.XX` |
| **Vínculo** | `Funcionário` (CLT, na base RH) ou `Terceiro` (futura integração com base de terceiros) |
| **Quarentena** | Estado "em espera" antes de ação definitiva. Funcionário em quarentena permanece 90 dias (configurável) antes de auto-encerrar |
| **Resolução** | Ação manual de marcar uma pendência como tratada, sob ticket do Jira. Vai pro Histórico, sai das Pendências ativas |
| **Interação** | Registro de uma ação do usuário (envio para quarentena, resolução, retirada). Gravado em `.jsonl` na rede; consolidado no banco pelo Processador |
| **Auto-update** | Mecanismo do `visualizador.exe` que compara `<versao>` local vs rede e baixa atualizações automaticamente |
| **`bi_divergencias`** | Tabela snapshot consolidada que alimenta o painel (combina validações + divergências) |
| **`resolucoes`** | Tabela com as resoluções já confirmadas (sob ticket Jira) |
| **`INTERACOES/`** | Pasta na rede com os `.jsonl` por usuário (um arquivo por `USERNAME` do Windows) |

---

## Anexo: Mapeamento status → ação (lógica do Processador)

| Cenário | `bi_divergencias.tipo` | `bi_divergencias.acao` (no painel) | Como aparece |
|---|---|---|---|
| Funcionário sem perfil no sistema | `SEM_ACESSO` | `Incluir Acesso` | Card azul claro |
| Funcionário com perfil errado | `DIVERGENTE` | `Alterar Perfil` | Card azul escuro |
| Cargo com 2+ perfis possíveis | `EM_ANALISE` | `Em Análise` | Card laranja |
| Usuário no SYSTUR sem matrícula | `ACESSO_SEM_VINCULO_RH` | `Não Mapeado` | Card roxo |
| Funcionário desligado com acesso | (em `divergencias`, tipo `ACESSO_DESLIGADO`) | _(visão futura)_ | _(ainda não no painel)_ |

---

_Documento referente à versão v2.0.1 do sistema._
