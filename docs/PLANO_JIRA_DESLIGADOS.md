# Plano de construção — Abrir chamado no Jira (desligados)

Escopo fechado com a área em 11/08/2026: **somente o fluxo de DESLIGADOS**
(revogação). Pendência e transferido seguem com o botão desabilitado até
alinhamento. Parâmetros e decisões em `docs/INTEGRACAO_JIRA_CARD25.md`.

O que o usuário faz, em uma frase: abre o desligado, escreve o parecer, clica em
**Abrir chamado no Jira**, recebe o número na tela e conclui a tratativa.

---

## Já construído

| # | Item | Onde |
|---|------|------|
| 1 | `CONFIG/jira.xml` — todos os parâmetros num arquivo só, lido **da rede** (não da cópia local), com fallback local em modo dev. Modelo versionado em `jira.xml.exemplo` | `src/visualizador/main.py` · `_jira_xml_path`, `carregar_config_jira` |
| 2 | Diagnóstico no banner de abertura — 6 estados (ativo / desligado / incompleto / inválido / ausente / sem credencial) | `jira_diagnostico` |
| 3 | Cliente HTTP em `urllib`, Basic auth, POST em `/rest/servicedeskapi/request`, erro tipado | `jira_abrir_chamado`, `JiraErro` |
| 4 | Montagem dos 3 campos: título gerado, descrição com tabela + contexto + parecer, tipo fixo | `jira_titulo`, `jira_descricao`, `_data_br` |
| 5 | Endpoint `/api/abrir-chamado` (409 carrega o número quando o chamado nasceu mas o registro falhou) | `do_POST` |
| 6 | Envelope `CHAMADO_ABERTO` gravado na resposta do POST | `abrir_chamado_desligado` |
| 7 | Guarda de duplicata no **servidor**, lendo `.jsonl` de todos + tabela **da rede** | `chamados_abertos` |

Suíte medida em 12/08 sobre o `33e35cb` fechado: **737 passed / 53 subtests**,
sem regressão. (O número 718 citado antes era parcial, tirado no meio da
construção.)

---

## O que falta

> **Situação em 13/08/2026:** os itens 4 a 8 abaixo **estão construídos** (commit
> `86a64ea`) e a suíte fecha em 737 passed + 53 subtests. O texto foi mantido
> porque descreve o *porquê* de cada decisão, que continua valendo. O que
> permanece aberto é só o bloqueio externo do componente — ver a seção final.

### 4. Tabela `chamados_abertos` ✅

**Por quê.** O `.jsonl` não é permanente: a cada execução o Processador renomeia
`INTERACOES/`, dobra no banco e apaga a pasta. Sem a tabela, a guarda de
duplicata esquece tudo a cada processamento — e a duplicata volta, agora
invisível (o número existe no Jira e em lugar nenhum aqui).

**Onde.** `src/infraestrutura/banco_dados/schema.py`

**Como.** Tabela **aditiva** (o projeto já tem `test_schema_aditivo.py` cobrindo
esse padrão), com `registro_id` como chave:

```
chamados_abertos
  registro_id  TEXT PK     matrícula do desligado
  fluxo        TEXT        'DESLIGADO' (prepara pendência/transferido)
  ticket       TEXT
  ticket_url   TEXT
  nome         TEXT        snapshot p/ auditoria
  sistema      TEXT
  acessos      TEXT        JSON, os perfis que entraram no chamado
  aberto_por   TEXT
  aberto_em    TEXT        ISO
```

**Nunca é limpa**, nem depois da tratativa concluída — é dela que a lupa mostra
de onde veio o número.

**Como verificar.** Banco antigo (sem a tabela) continua abrindo o painel;
`garantir_estrutura` cria sem apagar nada.

---

### 5. Consolidação no Processador ✅

**Onde.** `src/aplicacao/casos_de_uso/dobrar_interacoes.py`, método `_aplicar`

**Como.** Mais um bloco, no mesmo formato dos outros quatro tipos — mas com uma
diferença que precisa ficar explícita no código:

> Nos outros tipos **vence a interação mais recente**. Aqui vence a **primeira**:
> o chamado já existe no Service Desk e não há o que sobrepor. Se dois registros
> chegarem para a mesma matrícula, o segundo é a duplicata que queríamos impedir
> e não pode apagar o primeiro.

`INSERT OR IGNORE` sobre a PK dá idempotência: reprocessar não duplica nem
reescreve.

**Como verificar.** Teste que dobra duas interações da mesma matrícula e confirma
que sobra a primeira; dobra duas vezes e confirma que nada muda.

---

### 6. Tela ✅

**Onde.** `CVC_IAM_ANALYTICS/EXECUTAVEIS/REPORT/index.html`

Quatro mudanças:

**a. `_btnJira()` passa a receber estado.** Hoje devolve sempre desabilitado.
Passa a ter três formas: desabilitado com o motivo na dica (integração desligada
ou parecer vazio), habilitado, e concluído (`✓ GAAR-1487 aberto`).

**b. Habilitar conforme o parecer.** O texto do analista vai dentro do chamado,
então não existe chamado antes dele. Listener no `#tr-desc` liga o botão quando
há conteúdo.

**c. Travar depois de abrir.** Número e link chegam preenchidos e em somente
leitura — a fonte da verdade é o Jira, e editável criaria dois números
divergentes. **O Parecer continua editável**, senão o caso ficaria preso: com
chamado aberto e sem como registrar o parecer, nunca viraria resolvido.

**d. Selo na grid.** Linha com `chamado` e sem `tratado` mostra
`⏳ Aguardando chamado · GAAR-1487`, e o modal já abre travado. É o que impede o
segundo analista de abrir outro chamado para o mesmo caso.

**Tratamento das respostas:** 200 preenche e trava; 400 mostra o erro no
`#tr-err`; **409 exibe a mensagem inteira** — ela pode conter o número de um
chamado que nasceu sem registro, e perder esse texto significa perder o número.

**Como verificar.** Mockup aprovado em 11/08:
https://claude.ai/code/artifact/1d68456f-dd59-48e8-9345-f28267853908

As quatro mudanças foram validadas pelo formulário, com o analista clicando, em
14/08 — ver a seção "Validação ponta a ponta" no fim deste documento.

---

### 7. Testes ✅

| Alvo | O que cobre |
|------|-------------|
| `jira_titulo` / `jira_descricao` / `_data_br` | texto exato dos 3 campos, 1 e N perfis, data BR |
| `carregar_config_jira` | os 6 estados, precedência rede > local, XML inválido |
| `chamados_abertos` | mescla banco+jsonl, **primeiro vence**, leitura da rede pós-dobra |
| `abrir_chamado_desligado` | guarda de duplicata barra **antes** do POST; sem acessos não abre; falha de gravação devolve o número na mensagem |
| Consolidação | idempotência e "primeiro vence" |

---

### 8. Fechamento ✅

- Atualizar `docs/INTEGRACAO_JIRA_CARD25.md` com o que foi construído
- Passo da infra no `LEIA-ME.md` dos executáveis (criar o `jira.xml` na rede)
- **`build_update_executaveis.py` precisa excluir `jira.xml`** do `copytree`:
  hoje ele copia a pasta inteira, então um `jira.xml` presente na máquina de
  build entraria no pacote e se espalharia

---

## Fora de escopo, e por quê

**Evento no ciclo de vida.** Cheguei a propor `CHAMADO_ABERTO` como marco entre
`PENDENCIA` e `RESOLVIDO` em `ciclo_eventos_acesso`, renumerando a `_ORDEM`.
**Não vamos fazer agora.** O selo âmbar sai da tabela `chamados_abertos`, sem
tocar no ciclo — e mexer na `_ORDEM` afeta os tempos (`dt_pendencia`,
`dt_resolvido`) e os funis da Visão Geral, que é risco de regressão sem ganho
correspondente. Revisitar só se o aging por estado for pedido.

**Criptografia do token.** O painel roda como o analista: tudo que ele lê, o
analista lê. Criptografar com chave acessível ao programa é ofuscação, não
proteção. A defesa real é privilégio mínimo — conta de serviço que é *cliente*
do portal e só abre chamado, capacidade que esses analistas já têm pelo
navegador.

---

## Validado ao vivo em 11/08 — chamado SDTTI-1545753

Chamado de teste criado pela API, com **dados falsos** (`TESTE000000`): o
request type se chama "Catálogo para API de Revogação Automática de GA", e um
teste com login real poderia disparar uma revogação de verdade que cancelar o
chamado depois não desfaz.

**O formato está validado.** O `renderedValue` devolvido pela API mostra que as
quebras de linha sobrevivem (`<br>`), os blocos viram parágrafos e a acentuação
passa intacta. A tabela **não** vira `<table>` — as linhas com `|` ficam como
texto, exatamente como previsto. O separador foi escolhido por isso: alinhamento
por espaço se perderia em fonte proporcional. **Não há retrabalho no texto.**

Os três campos foram aceitos como enviados.

### ⚠️ Achado que bloqueia o valor da entrega — falta o COMPONENTE

**O chamado não cai em nenhuma fila.** Varremos as **71 filas** do service desk
9 (987 issues, zero erros): `SDTTI-1545753` não está em nenhuma. Chamado criado
que ninguém vê na fila é entrega no vazio.

A causa está no JQL das filas — elas filtram por **componente**, não por tipo de
solicitação. A fila do nosso fluxo é a `1517 — 7 - Gestão de Acessos -
Desligamento`, com 29 chamados ativos:

```sql
project = SDTTI
AND status in (Aberto, "Aguardando Fornecedor", "Aguardando RFC",
               "Aguardando usuário", "Em análise Nível 1", "Em análise nível 2",
               "Em progresso", Pendente, Reaberto)
AND component = "7 - Gestão de Acessos - Desligamento"     ← id 12165
```

O chamado atendia o `status`. Faltou só o componente, que o tipo 8819 não
atribui.

**E não conseguimos resolver do nosso lado — testado, não suposto.** Em
`SDTTI-1545878` criamos o chamado e tentamos carimbar o componente via
`PUT /rest/api/3/issue/{key}`:

```
404 — "O item não existe ou você não tem permissão para vê-lo"
```

Isso mesmo com `mypermissions` afirmando `EDIT_ISSUES: True`. Permissão de
projeto não se traduz em acesso ao issue: para o Jira a conta é *cliente*
naquele chamado, e cliente só opera pela API do portal. **O `mypermissions` não
serve como previsão** — reporta concessões, não capacidade efetiva.

Depender disso também exigiria conta de serviço com perfil de agente, o oposto
do privilégio mínimo que sustenta o resto do desenho.

**Pedido a quem criou o formulário:**

> O tipo de solicitação 8819 cria chamados **sem componente**, e as filas de
> Gestão de Acessos filtram por `component`. Configurar o 8819 para atribuir
> automaticamente o componente do fluxo — por valor padrão no tipo ou por
> automação no projeto. Pela API do portal não conseguimos enviá-lo: o
> formulário expõe apenas `summary`, `description` e `customfield_11936`.

*(Qual componente vai neste pedido depende da confirmação da área — ver a
reconferência de 13/08 logo abaixo.)*

Confirmar com a área se é essa a fila do fluxo de desligamento — existem também
`Revogações`, `Ouro`, `Fornecedores` e `N3 CVC`.

#### Reconferido em 13/08/2026 — continua valendo, e a fila mudou de candidata

Reabrimos a questão porque havia a impressão de que o componente já tinha sido
resolvido. **Não foi.** Quatro medições, todas com o token pessoal:

| Verificação | Resultado |
|---|---|
| `GET /servicedesk/9/requesttype/8819/field` | devolve **3 campos** — `summary`, `description`, `customfield_11936`. Componente não está exposto |
| Chamado do portal aberto hoje (`SDTTI-1550975`), fila 1231 | fila com **0 itens** enquanto ele estava `Aberto` |
| Varredura das 71 filas em 11/08 (`SDTTI-1545753`, também do portal) | não estava em nenhuma |
| Teste de controle: fila 1517 | **31 itens** — a conta *consegue* ler filas, então o zero acima é ausência real, não falta de permissão |

**A confusão veio do `teste_fila_1231.py`** (scratchpad da sessão de 11/08). Ele
provou *"componente ⇒ cai na fila"*, mas criando pela **API genérica**
(`/rest/api/3/issue`) com o componente colado à mão — o próprio cabeçalho do
script diz que não é a solução. O caminho real do painel é o do portal, e por
ele o chamado continua nascendo sem componente.

**Qual componente pedir — decisão da área, não técnica.** Surgiram dois
candidatos e eles apontam para lados opostos:

| Fila | Componente | Chamados abertos hoje |
|---|---|---|
| 1231 — `5 - Gestão de Acessos - Revogações` | 11681 | **0** |
| 1517 — `7 - Gestão de Acessos - Desligamento` | 12165 | **31** |

A 5 é a que o nome sugere (o fluxo é revogação), mas está vazia. A 7 é a que a
equipe efetivamente opera. Pedir a configuração da 5 sem confirmar significa
carimbar chamado para uma fila que ninguém abre — falha silenciosa, pior que o
estado atual, porque o painel passaria a reportar sucesso.

**Nota sobre leitura de chamado do portal:** a conta não lê os chamados que ela
mesma cria pelo portal via `/rest/api/3/issue` nem por JQL (404 / vazio) — nesses
ele é *cliente*. Só `/rest/servicedeskapi/request/{key}` responde. Por isso a
verificação do componente tem de ser feita **pela fila**, não lendo o issue.
Cancelamento funciona pelo portal (`transition` id 261, 204).

Chamados de teste de 13/08 (`SDTTI-1550975`, `SDTTI-1550995`): ambos cancelados.

Ressalva: a conta usada não é agente, então a confirmação final é um agente
vendo o chamado na própria fila.

**Ambos os chamados de teste foram cancelados** (`Cancelado pelo solicitante`).
O ciclo criar → cancelar é automatizável pela API (transição id 261, 204 limpo),
o que permite revalidar depois do ajuste sem sujar a fila.

---

## Validação ponta a ponta em 14/08/2026 — pelo formulário, com o analista clicando

Até aqui o que existia do lado do painel era teste de servidor mais um smoke de
browser conferindo que `_btnJira` renderiza os 3 estados. **O fluxo pelo
formulário nunca tinha sido exercitado.** Foi, agora: ambiente isolado (banco
copiado, `<raiz>` de rede vazia, desligado fictício semeado), analista clicando
na tela de verdade, POST real no Jira.

| # | O que se queria provar | Resultado |
|---|---|---|
| 1 | Botão nasce desabilitado e só liga com o parecer | ✅ |
| 2 | Após abrir, número e link chegam travados; parecer segue editável | ✅ |
| 3 | Segundo clique no mesmo registro é recusado (guarda de duplicata) | ✅ |
| 4 | Selo `⏳ Aguardando chamado` na grid | ✅ |

O chamado `SDTTI-1552741` nasceu com os 3 campos exatamente como montados —
título, tabela de perfis linha a linha, contexto de desligamento, parecer e
`Revogação de acessos`. Cancelado ao fim.

Os itens 3 e 4 foram fechados num segundo registro, **depois da dobra** — ou
seja, com a guarda lendo da tabela `chamados_abertos` e não do `.jsonl`, que é o
caminho mais difícil de exercitar e o que de fato roda em produção. Nenhum
chamado foi criado nesse teste: a guarda barra **antes** do POST, por desenho.

### 🐞 O que a validação encontrou — a dobra derrubava o Processador inteiro

Bug real, corrigido no mesmo dia. A tabela `chamados_abertos` tinha **duas
definições que discordavam** na última coluna:

| Onde | Coluna |
|---|---|
| `schema.py` — quem cria o banco em produção | `dt_registro DATETIME` |
| `dobrar_interacoes.py`, `CREATE TABLE **IF NOT EXISTS**` | `dobrado_em TEXT` |
| o INSERT da dobra | escrevia em **`dobrado_em`** |

Em produção quem cria a tabela é o `schema.py`; o `IF NOT EXISTS` da dobra vira
no-op e a coluna errada permanece. A primeira consolidação com um chamado
estourava `no such column: dobrado_em`. E como a dobra é o **primeiro passo**
dentro do `try` do Processador — que só tem `finally`, sem `except` — a exceção
subia e **matava a execução inteira**: sem importar RH, sem analisar
divergências, sem gerar relatório. Bastava um analista ter aberto um chamado.

Efeito colateral observado ao vivo: a dobra renomeia `INTERACOES/` **antes** de
inserir, então o `.jsonl` ficou preso em `INTERACOES_processando/` e a tabela
vazia — a amnésia exata que esta tabela existe para impedir. Quem "consertasse"
apenas embrulhando a dobra num `try/except` trocaria a falha ruidosa por essa
falha silenciosa, que é pior.

**Por que os testes não pegaram** — dois motivos somados em
`ConsolidacaoNoProcessador`: criava a tabela pelo `_SQL_CHAMADOS` (o DDL da
própria dobra), nunca pelo `schema.py`; e não chamava `DobrarInteracoes` —
escrevia um INSERT próprio de 4 colunas, que nunca tocava a coluna divergente.
Validava a semântica do `INSERT OR IGNORE` do SQLite, não o código.

**Correção:** `schema.py` alinhado para `dobrado_em`; migração aditiva
`_migrar_chamados_dobrado_em` em `conexao.py` para os bancos já criados; e a
classe `DobraSobreSchemaDeProducao`, que cria pelo `schema.py` e roda o
`executar()` de verdade. Os 4 testes novos falham com a correção revertida —
conferido, para não virarem teste decorativo como os anteriores.

Suíte: **741 passed + 53 subtests**.

---

## Go-live — o que a CVC assumiu (14/08/2026)

Os três pontos externos foram para o lado da CVC:

| | Ponto | Decisão |
|---|---|---|
| 1 | Componente no tipo 8819 | assumido pela área |
| 2 | Configuração do formulário | assumida |
| 3 | Conta de serviço + API token | **entra na subida para produção** |

Enquanto isso, a integração fica com `<ativo>false</ativo>` e o botão
desabilitado — que é o estado seguro: com o componente pendente, um botão ligado
faria o analista abrir chamado que não entra em fila, e o painel exibiria
"✓ aberto" por cima da falha. Botão desabilitado é visível; sucesso falso não é.

### Conferência obrigatória no go-live

**A conferência de campos do 8819 não serve como prova.** Em 14/08 ela ainda
devolve só `summary`, `description` e `customfield_11936` — mas o componente pode
ser atribuído por automação do projeto, que não aparece nessa listagem. Ou seja:
essa leitura não confirma nem desmente.

O único teste conclusivo é o de ponta, e leva ~2 minutos:

1. criar um chamado pelo portal (tipo 8819) com dados falsos (`TESTE000000`);
2. varrer as filas do service desk 9 e confirmar em **qual** ele aparece;
3. cancelar (transição 261 pela API do portal, 204).

Lembrar de duas armadilhas já pagas neste projeto:
- **não** validar criando pela API genérica com o componente na mão — isso prova
  o roteamento do Jira, não o do nosso caminho (foi o engano de 11/08);
- a conta não lê pela API genérica o chamado que ela mesma abre pelo portal
  (404 / JQL vazia). A verificação tem de ser **pela fila**, e sempre com um
  teste de controle numa fila conhecida — fila vazia pode ser falta de permissão
  disfarçada de zero.

Fazer isso **antes** de virar o `<ativo>` para `true`. Confirmação final é um
agente vendo o chamado na própria fila.

### O token dos testes não pode virar o de produção

Os testes usaram a conta pessoal `nelsondiniz@ext.cvccorp.com.br`.

Atenção ao perfil: em 11/08 a TI concedeu a essa conta `TRANSITION_ISSUES`,
`Browse users and groups` e `canRaiseOnBehalfOf` — perfil de **agente**. A conta
de serviço de produção **deve ser cliente, só criar**: consome menos licença e,
principalmente, é o privilégio mínimo que sustenta a decisão de manter o token
num arquivo compartilhado. Uma conta com `TRANSITION_ISSUES` pode mexer em
chamados alheios do `Atendimento T.I.` inteiro; se a de produção nascer assim, a
conclusão sobre não criptografar precisa ser revista.
