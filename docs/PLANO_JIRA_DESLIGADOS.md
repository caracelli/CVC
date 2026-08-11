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

Suíte em 718 passed / 53 subtests, sem regressão.

---

## O que falta

### 4. Tabela `chamados_abertos`

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

### 5. Consolidação no Processador

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

### 6. Tela

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

---

### 7. Testes

| Alvo | O que cobre |
|------|-------------|
| `jira_titulo` / `jira_descricao` / `_data_br` | texto exato dos 3 campos, 1 e N perfis, data BR |
| `carregar_config_jira` | os 6 estados, precedência rede > local, XML inválido |
| `chamados_abertos` | mescla banco+jsonl, **primeiro vence**, leitura da rede pós-dobra |
| `abrir_chamado_desligado` | guarda de duplicata barra **antes** do POST; sem acessos não abre; falha de gravação devolve o número na mensagem |
| Consolidação | idempotência e "primeiro vence" |

---

### 8. Fechamento

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

### ⚠️ Achado que bloqueia o valor da entrega

**O chamado não cai em nenhuma fila.** Varremos as **71 filas** do service desk
9 (987 issues, zero erros de leitura): `SDTTI-1545753` não está em nenhuma.

Filas do JSM são filtros JQL. Se o tipo 8819 não estiver no filtro de nenhuma,
os chamados são criados mas **não aparecem para os agentes trabalharem** — a
automação entregaria no vazio.

Indício forte: a fila `1231 — 5 - Gestão de Acessos - Revogações` existe e está
com **zero issues**. Parece feita para esses chamados, mas o filtro ainda não os
alcança.

**Pedido a quem criou o formulário:** incluir o tipo de solicitação 8819 no
filtro da fila apropriada. O SDTTI-1545753 serve de caso concreto.

Ressalva: a conta usada não é agente pleno (o `/rest/api/3/issue/` devolve 404
nela), então a confirmação definitiva é um agente olhando a própria fila.

---

## Bloqueio externo

**Conta de serviço + API token.** Até existirem, a integração fica com
`<ativo>false</ativo>` e o botão desabilitado. Os testes usaram a conta pessoal
`nelsondiniz@ext.cvccorp.com.br`.

Atenção ao perfil: em 11/08 a TI concedeu a essa conta `TRANSITION_ISSUES`,
`Browse users and groups` e `canRaiseOnBehalfOf` — perfil de **agente**. A conta
de serviço de produção **deve ser cliente, só criar**: consome menos licença e,
principalmente, é o privilégio mínimo que sustenta a decisão de manter o token
num arquivo compartilhado. Uma conta com `TRANSITION_ISSUES` pode mexer em
chamados alheios do `Atendimento T.I.` inteiro; se a de produção nascer assim, a
conclusão sobre não criptografar precisa ser revista.
