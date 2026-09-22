# Regras aplicadas, na ordem de execução

Levantado do código em 22/09/2026 (`sig-fase1`, HEAD `48b25c5` + ajustes não commitados).

As datas entre parênteses são as que o próprio código registra como origem da
regra — quase sempre um retorno da área. Regra sem data é de desenho original.

Marcações usadas aqui:

- **[SOME]** — ponto em que uma pessoa pode deixar de gerar linha, e portanto
  desaparecer da tela. São 6 no total, listados de novo no fim.
- **[FLAG]** — comportamento que depende de chave no `config.xml`.

---

## Fase 1 — Importação

| # | Regra | Origem |
|---|---|---|
| 1 | Dobra das interações: os `.jsonl` por usuário viram quarentena/resoluções no banco, e a pasta é resetada por rename atômico | arquitetura multiusuário |
| 2 | Diretório AD (franqueados/prestadores) entra **antes** do RH. É a base principal de identidade: dá dono aos acessos órfãos pelo login. Matrícula fica namespaced (`FRANQ-`/`PREST-<login>`), então não colide com CLT | área, 22/07 |
| 3 | Importa RH ativos e desligados. O snapshot/histórico é gravado **antes** do merge, senão a mudança se perde | |
| 4 | Padroniza o RH | |
| 5 | Importa matrizes: perfis por sistema (CC + cargo) e a CCO organizacional (CC + gestor). Filtra pelos sistemas com `ativo=true` | |
| 6 | Importa os extratos dos sistemas em escopo | |
| 7 | Importa o SIG (formato matricial + de-para). Ausência do arquivo não quebra o pipeline | |

## Fase 2 — Vinculação de acesso a pessoa

| # | Regra | Origem |
|---|---|---|
| 8 | Cascata de 6 níveis, nesta ordem: CPF exato (1.00) · e-mail exato (0.95) · login exato (0.93) · CPF parcial + nome (0.90) · nome exato (0.70) · fuzzy de nome (0.50, **não vincula** — só sugere candidatos). CLT tem precedência explícita sobre AD | |

## Fase 3 — Divergências

| # | Regra | Origem |
|---|---|---|
| 9 | **Acesso de desligado**: casa por união de chaves — matrícula **ou** CPF do extrato **ou** login. Só matrícula subcontava, porque o vínculo cruza contra ativos | |
| 10 | **Conta de serviço** (robô/automação) com prefixo de login configurado sai da lista de revogação e vira tipo próprio. Não some: sai da cobrança | área, 28 e 31/08 |
| 11 | **Acesso sem vínculo no RH**: acesso sem dono | |
| 12 | **Transferidos**: entra na revisão quem mudou de cargo, centro de custo, departamento **ou** gestor. Sem janela temporal — vale enquanto a pessoa estiver ativa | área, 29/07 |

## Fase 4 — Validação de acessos

É aqui que mora quase tudo. O que a tela mostra como Aderente, Incluir,
Alterar, Em Análise e Não Mapeado sai desta fase.

### 4.1 Preparação

| # | Regra | Origem |
|---|---|---|
| 13 | **Conta bloqueada ou inativa não é acesso** — o acesso é descartado da lista da pessoa | área, 22/07 |
| 14 | Conta com status indefinido (`P` ou vazio) conta como acesso, mas a linha será revista no fim | área, 10/08 |
| 15 | Calcula a adesão de cada cargo a cada sistema — insumo da regra B1 (#22) | |
| 16 | Calcula quem **sumiu do arquivo de ativos mais recente**. Se o último arquivo tem menos de 50% da população, ninguém some e sai um aviso | usuário, 15/09 |

### 4.2 Por pessoa

Terceiro, franqueado e prestador **não** passam por aqui: têm caminho próprio
(#25 e #26).

| # | Regra | Origem |
|---|---|---|
| 17 | Monta o esperado juntando **matriz** (CC + cargo) e **CCO** (CC + gestor) num conjunto único por sistema, com dedup. A matriz tem precedência. **O SIG nunca usa CCO** | |
| 18 | Carimba na linha a função da CCO que originou o esperado | área, 17/09 |

### 4.3 Por sistema — na ordem em que o motor decide

A primeira que casar decide a linha.

| # | Regra | Resultado | Origem |
|---|---|---|---|
| 19 | Sistema sem nenhum extrato no banco | `SEM_DADOS` — **[SOME]** descartado na hora de salvar | |
| 20 | **Tem pelo menos um perfil esperado aderente** | `OK` (Aderente) | |
| 20a | Dentro do OK: perfil que ela tem e a matriz **não** explica entra no campo e marca perfil excessivo. Só vira pendência com a flag **[FLAG]** | informativo por padrão | área, 28/08 |
| 20b | Dentro do OK: os outros perfis previstos que ela também tem passaram a aparecer no campo | | 22/09 |
| 21 | **Provável desligamento**: já foi aderente naquele sistema **e** está com zero acesso **e** sumiu do arquivo de ativos | **[SOME]** nenhuma linha | 12/06, endurecida em 15/09 |
| 22 | **B1 — limiar de adesão**: está sem acesso nenhum e menos de 30% do cargo usa aquele sistema | **[SOME]** nenhuma linha | |
| 23 | Está sem acesso e passou da B1 | `SEM_ACESSO` (Incluir Acesso) | |
| 24 | Tem acesso, nenhum aderente, e há 2+ perfis esperados ou 2+ acessos | `EM_ANALISE` | |
| 25 | Tem acesso, nenhum aderente, 1 esperado × 1 acesso | `DIVERGENTE` (Alterar Perfil) | |

### 4.4 Caminhos paralelos

| # | Regra | Origem |
|---|---|---|
| 26 | **SIG por espelho**: não tem matriz. O esperado é o padrão do grupo — perfil presente em ≥70% dos colegas que usam SIG, exigindo ≥2 colegas, agrupando por CC+gestor+cargo com queda para CC+gestor. Sem par comparável e sem usar SIG, **[SOME]** não gera linha | usuária, 24/06 |
| 27 | **Franqueado por matriz própria**: cargo × tipo de atendimento × tipo de loja. Como os dois últimos não existem no cadastro, a regra só fecha ao contrário — do perfil que a pessoa tem, diz se o cargo justifica. Valida aderência e **não gera inclusão**; franqueado sem acesso **[SOME]** não aparece | área, 31/08 e 04/09 |
| 28 | **Terceiro e prestador por espelho de vínculo**: mesmo critério de ≥70%. Sem grupo com padrão, **[SOME]** não vira pendência — para não inflar a fila com ruído | área, 30/07 |

### 4.5 Fallback por pessoa

| # | Regra | Origem |
|---|---|---|
| 29 | Não gerou linha em sistema nenhum → `NAO_MAPEADO` ("Não Mapeado"), salvo como informativo. Antes disso a pessoa ficava com zero linha em qualquer lugar do painel — eram 49% dos ativos | Bruna, 09/09 |
| 30 | Quem sumiu do arquivo de ativos mais recente **[SOME]** não ganha o Não Mapeado | usuário, 15/09 |

### 4.6 Pós-processamento, sobre todas as linhas

| # | Regra | Origem |
|---|---|---|
| 31 | **Conta indefinida**: linha OK ou Divergente com conta em status indefinido vira `SEM_ACESSO` com o perfil liberável **[FLAG]**, ou `EM_ANALISE`. Franqueado nunca entra nesse ramo — apagaria uma escalada de privilégio real | área, 31/08; correção 08/09 |
| 32 | **Conta bloqueada**: explica o Sem Acesso — "a conta existe e está revogada; a ação é desbloquear, não criar" | área, 10/08 e 25/08 |
| 33 | **Mais de um perfil no mesmo sistema**: linha que seria Aderente vira `EM_ANALISE` **[FLAG]**. Não é o perfil excessivo — aqui não importa se a matriz prevê os dois | área, 22/09 |
| 34 | **Filtro de gravação**: só são salvos `DIVERGENTE`, `EM_ANALISE`, `OK`, `SEM_ACESSO` e `NAO_MAPEADO`. O `SEM_DADOS` é descartado aqui | |
| 35 | **O que é pendência**: só `DIVERGENTE` e `EM_ANALISE`. `SEM_ACESSO` é informativo e aparece só na Consulta; `NAO_MAPEADO` idem | Bruna, Fase 1 |

## Fase 5 — Pós-validação

| # | Regra | Origem |
|---|---|---|
| 36 | **Revalidação pós-transferência**: cada acesso é julgado contra o esperado da área nova e da antiga, com o mesmo critério de cada sistema | Card 23 |
| 37 | **Ciclo de vida** por (matrícula, sistema): Pendência → Resolvido → Aderente, com datas first-wins | |
| 38 | Eventos de acesso e trilha de histórico | |
| 39 | Geração das saídas em Excel | |

---

## Os 6 pontos onde uma pessoa desaparece

Esta é a lista que interessa quando alguém pergunta "por que o fulano não
aparece". Hoje o motor **conta** cada um deles no log, mas não registra **quem**
foi descartado — por isso responder exige investigação manual, caso a caso.

| Ponto | Regra | Volume medido em 22/09 |
|---|---|---|
| #19 | Sistema sem extrato (`SEM_DADOS` descartado ao salvar) | não medido |
| #21 | Provável desligamento | 37 casos |
| #22 | **B1 — limiar de 30%** | **1.176 inclusões** |
| #26 / #28 | Espelho sem par ou sem padrão | 85 acessos |
| #27 | Franqueado sem acesso | ~5.400 (decisão aceita em 04/09) |
| #30 | Sem expectativa **e** sumiu dos ativos | 27 pessoas |

### A combinação que ninguém decidiu

As regras #13 e #22 se somam sem que ninguém tenha decidido isso:

1. A conta da pessoa está bloqueada ou inativa → #13 descarta o acesso;
2. ela fica com zero acesso → cai em #22;
3. o cargo tem adesão baixa → a linha é descartada;
4. a pessoa **não aparece em lugar nenhum**, nem na Consulta.

O aviso "a conta existe e está bloqueada, a ação é desbloquear" (#32) só é
carimbado em linhas que sobreviveram — quem a B1 matou nunca chega lá.

Medido na base real: **536 pares pessoa/sistema** nessa situação — SIG 327,
SICA_RA 187, SICA_ESFERA 22. Para comparar, só 121 linhas hoje carregam o aviso
de conta bloqueada.

O argumento da B1 é "a matriz é abrangente demais, não inundar a tela com
esperado irrelevante". Quando a pessoa **tem conta** naquele sistema, existe
prova direta de que o acesso é relevante para ela, e o argumento não se aplica.
