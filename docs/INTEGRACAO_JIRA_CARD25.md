# Integração Jira — Cards 25-26

Levantamento feito em **10/08/2026** consultando a API do Jira ao vivo (sessão
autenticada no portal + API token pessoal, só chamadas GET). Nenhum chamado foi
criado. **Nenhum código foi escrito ainda** — a implementação está parada
aguardando as respostas da Bruna (ver "Pendências" no fim).

Este documento existe para que o levantamento não se perca e para que a máquina
de desenvolvimento tenha tudo o que foi apurado.

---

## O "Usuário Afetado" saiu do formulário (10/08) — CONFIRMADO

Na primeira consulta deste levantamento o formulário tinha **quatro** campos
obrigatórios, incluindo `customfield_11358` ("Usuário Afetado", User Picker).
Horas depois ele não estava mais lá. **A remoção foi pedida pela equipe** — é
intencional e definitiva, confirmado pelo Nelson em 10/08.

O formulário 8819 tem hoje **três** campos, todos obrigatórios:

```
summary            obrigatorio  string
description        obrigatorio  string
customfield_11936  obrigatorio  textfield  "Caracteristicas de Solicitacao"
```

Com isso cai o maior obstáculo do Card 25: **não é mais preciso resolver
`accountId`**. O endpoint interno da seção 3 deixa de ser necessário, e o popup
de desempate da seção 5 perde a razão de existir. Os 63 casos que não resolviam
deixam de ser problema — todos cabem na descrição, que é texto livre.

**As seções 3 e 5 abaixo ficam preservadas de propósito**, como contingência: se
o campo voltar, ou se aparecer em outro tipo de solicitação, o levantamento já
está feito e não precisa ser refeito. Não são o plano corrente.

---

## 1. Parâmetros confirmados

| Item | Valor | Como foi confirmado |
|---|---|---|
| Tenant | `https://cvccorp.atlassian.net` | — |
| `serviceDeskId` | **9** | `GET /rest/servicedeskapi/servicedesk` |
| `requestTypeId` | **8819** | `GET /rest/servicedeskapi/.../requesttype/8819` |
| Nome do tipo | "Gestão de Acessos API" | idem |
| Descrição do tipo | "Catálogo para API de Revogação Automática de GA" | idem |
| `issueTypeId` | 10109 | idem |
| `canRaiseOnBehalfOf` | **false** | `GET .../requesttype/8819/field` |

Neste tenant o id do portal na URL **é** o `serviceDeskId` — não são numerações
distintas, como se costuma supor.

O formulário antigo usado pelo robô do projeto `cvc_Bruna`
(`portal/1984/group/3223/create/7550`) **não** se aplica: o 8819 foi criado
especificamente para esta automação.

## 2. Campos — os quatro são obrigatórios

```
GET /rest/servicedeskapi/servicedesk/9/requesttype/8819/field
```

| Field ID | Nome | Obrigatório | Tipo |
|---|---|---|---|
| `customfield_11358` | Usuário Afetado | sim | `user` / userpicker |
| `summary` | Resumo | sim | string |
| `description` | Descrição | sim | string |
| `customfield_11936` | Características de Solicitação | sim | string (textfield) |

Nenhum dos quatro tem texto de ajuda — nem na API (`description: ""`), nem no
DOM do formulário. Confirmado inspecionando a página renderizada.

A descrição aceita **texto puro**: o `/rest/servicedeskapi/request` não exige
ADF (o JSON de blocos do editor), diferente da API genérica de issues.

## 3. Resolver o `accountId` — a parte que quase virou bloqueio

O `customfield_11358` é User Picker **obrigatório**. Via API ele não aceita nome
nem e-mail: exige `{"accountId": "..."}`. Como não é possível deixar em branco,
resolver o `accountId` é pré-requisito para abrir qualquer chamado.

A API pública de busca **não serve**:

```
GET /rest/api/3/user/search   ->  403
```

Falta a permissão global *Browse users and groups*, que uma conta cliente do JSM
nunca terá. Testado com token e com sessão de navegador: 403 nos dois casos.

**O endpoint que funciona** é o que o próprio portal usa no campo, descoberto
capturando a rede do navegador enquanto se digita no picker:

```
GET /rest/servicedesk/1/customer/portal/9/user-search
      ?fieldConfigId=11659&fieldName=customfield_11358&query=<termo>
```

- responde **200** para a mesma conta que leva 403 na API pública
- **aceita Basic auth com API token** (verificado)
- devolve `accountId`, `emailAddress` e `displayName`; `[]` quando não acha
- teto de **50 resultados** por consulta

Dois cuidados: é endpoint **interno e não documentado** (`/rest/servicedesk/1/`),
podendo mudar sem aviso; e o `fieldConfigId=11659` é amarrado à configuração do
campo — deve ir para o `config.xml`, nunca hardcoded.

### Regra de resolução (dois níveis, conjuntiva)

1. **Nível 1** — busca pelo e-mail da base; aceita se algum resultado tiver
   `emailAddress` exatamente igual.
2. **Nível 2** — busca pelo nome completo; aceita **somente** se houver
   **exatamente um** resultado com `displayName` idêntico (normalizado: sem
   acento, sem caixa, espaços colapsados).
3. **Falha explícita** — qualquer outro caso. Não chutar.

O nível 2 precisa dos dois critérios juntos. Nome sozinho não serve: buscar
"DANIELA LOPES" devolve 50 contas e nenhuma é a pessoa procurada.

### Medição sobre a base inteira

1.800 pessoas distintas de `validacao_acessos` (banco de `Arquivos_origem`,
08/07), ~2.100 requisições, zero erros de rede:

| Status | n | resolvem | falha | % |
|---|---|---|---|---|
| DIVERGENTE | 21 | 18 | 3 | 85,7% |
| EM_ANALISE | 154 | 145 | 9 | 94,2% |
| SEM_ACESSO | 520 | 493 | 27 | 94,8% |
| OK | 1.105 | 1.081 | 24 | 97,8% |
| **TOTAL** | **1.800** | **1.737** | **63** | **96,5%** |

O nível 2 responde por 110 dos acertos — sem ele a cobertura cairia para 90,4%.

O `DIVERGENTE` aparece pior, mas com n=21 três falhas já derrubam o percentual;
não dá para tratá-lo como diferente com esse volume.

**Hipótese testada e refutada:** supunha-se que quem precisa *receber* acesso
(`SEM_ACESSO`) teria menos conta Atlassian. Não tem — 94,8%, acima do
`EM_ANALISE`. Não precisa de tratamento especial.

### Os 63 que falham

Dividem-se em dois casos distintos:

- **Ambíguos** — a pessoa existe, mas com 2+ contas de `displayName` idêntico,
  tipicamente uma por coligada (`rexturadvance`, `trendviagens`, `experimento`,
  `ext.cvccorp`, `cvccorp`). Exemplo real: `GUSTAVO ALVES DE SOUSA` tem conta em
  `@cvccorp.com.br` e em `@ext.cvccorp.com.br`.
- **Ausência real** — nenhuma conta com aquele nome. A busca por nome traz só
  pessoas diferentes.

Há ainda contas com `emailAddress` **vazio** (privacidade da conta): para essas
o nível 1 nunca funciona, só o nível 2.

Existe também `accountId` em dois formatos: `712020:<uuid>` (conta Atlassian) e
`qm:<uuid>:<uuid>` (cliente do Service Management). Confirmar que o POST aceita
os dois.

## 4. Padrão de texto do chamado

Definido pelo Nelson em 10/08:

```
summary      Sanitização - <Sistema> - <Nome do Usuário>

description  Revogar usuario abaixo:

             <nome> <login> <sistema> <perfil>
```

Exemplo com dado real da base:

```
Sanitização - SYSTUR - AGATHA DIAS

Revogar usuario abaixo:

AGATHA DIAS  INTADM333  SYSTUR  UX_E_UI
```

O `summary` do Jira tem limite de 255 caracteres — truncar defensivamente.

## 5. Desenho acordado (ainda não implementado)

- Quem abre o chamado é o **Visualizador**, no clique do botão. O
  `_btnJira()` já existe em `REPORT/index.html`, visível e desabilitado desde o
  commit `0c2af6b` (05/08) — falta ligar na API.
- Código do Visualizador em `src/visualizador/main.py` + `REPORT/index.html`.
  Cliente HTTP em `urllib` (stdlib), sem `requests` nem a lib `jira`.
- **Popup de desempate** para os ambíguos: radio (não checkbox) com só os
  candidatos de nome idêntico, mostrando e-mail — ou `accountId` truncado quando
  o e-mail é privado. A escolha é **gravada por matrícula** e não se repete nos
  chamados seguintes; trafega pelo `.jsonl` de interações e é consolidada pelo
  Processador, ficando auditável.
- Quando não acha nada, o popup abre busca livre (cobre grafia divergente). Sem
  resultado, marca o status de exceção e cai no caminho manual, que já existe: o
  commit `0c2af6b` tornou o ticket **opcional** na tratativa justamente para isso.
- Rótulo sugerido para a exceção: **"Sem conta no Jira"**. Não usar "Usuário Não
  Encontrado" — já é o rótulo de exibição do status `NAO_MAPEADO`
  (`src/aplicacao/casos_de_uso/gerar_saidas.py`) e significa outra coisa: acesso
  no extrato cujo usuário não existe no RH.
- Parâmetro de usuário substituto para casos não localizados nasce **vazio =
  não abre chamado**. Só preencher se a CVC confirmar que o campo é informativo.

## 6. Pedido à CVC (não depende da Bruna)

> 1. Uma **conta de serviço Atlassian** (e-mail dedicado), cadastrada como
>    **cliente** do portal 9 com permissão de abrir chamados no tipo 8819.
>    Conta de cliente no JSM não consome licença de agente. A automação
>    **apenas abre chamados** — não transiciona nem encerra.
> 2. Um **API token** para essa conta. Confirmar se a política do tenant permite
>    API tokens; caso contrário, será necessário um app OAuth 2.0 (3LO).

Não é preciso pedir liberação de rede (todos os usuários já alcançam o tenant)
nem alteração no formulário.

Ressalva: os testes foram feitos com uma conta do tipo `atlassian`. A conta de
serviço será `customer`. O `user-search` é endpoint do portal do cliente, então
deve valer igual — mas é o único ponto a reconfirmar com a credencial definitiva.

## 7. Pendências com a Bruna — bloqueiam a implementação

1. O que vai em **"Características de Solicitação"** (`customfield_11936`)?
   Campo obrigatório, texto livre, sem nenhuma orientação no formulário.
2. O **"Usuário Afetado"** é informativo, ou alguma automação do lado do Jira o
   consome para executar a revogação? Decide se pode existir usuário substituto.
   Se for consumido, apontar outra pessoa equivale a revogar o acesso dela.
3. Confirmação do rótulo do status de exceção ("Sem conta no Jira").
4. **Um chamado por (usuário, sistema)** com N perfis listados na descrição, ou
   um chamado por perfil? Há casos reais com 6 perfis divergentes no mesmo
   sistema (`LETICIA DE LIMA DUARTE` no SYSTUR).
5. O botão "Abrir chamado" aparece **só nos casos de revogação**? O texto diz
   "Revogar" e o form é de "Revogação Automática", mas o painel também trata
   `SEM_ACESSO`, que é acesso **a incluir** — 520 das 1.800 pessoas.
