# Roteiro de validação — Transferidos (Cards 22, 23 e 24)

Pacote: `TESTE_LOCAL_BRUNA_v1.0.0.zip`. Roda 100% local, não usa a rede e não
interfere na versão instalada no ambiente do cliente.

## Como começar

1. Extraia a pasta `CVC_IAM_ANALYTICS` em qualquer lugar do seu PC.
2. Rode `EXECUTAVEIS\visualizador.exe` — o painel abre em
   `http://127.0.0.1:8800/`.

**Só isso.** Você **não precisa rodar o Processador**: o banco já vem pronto,
com dois meses de dados (junho a agosto/2026). O histórico de movimentações
existe porque várias cargas de RH foram comparadas ao longo do período.

Pode tratar, resolver, quarentenar e exportar à vontade — tudo fica na sua
cópia local e não afeta a rede nem a versão do cliente.

---

---

## 1. Quem se moveu (Card 22)

**Onde:** aba **Transferidos**.

- [ ] O contador do topo mostra pessoas **a revisar**, **tratados** e
      **sem acesso**.
- [ ] Segmentos **A Revisar · Tratados · Sem acesso · Todos**.
- [ ] Expanda uma pessoa (**+**): a primeira linha é a **movimentação**, com o
      **de → para** do que mudou no cadastro — por exemplo
      `gestor: FULANO → CICLANO`. É esse par que diz se o acesso antigo ainda
      faz sentido.
- [ ] Abaixo do movimento vêm os acessos, **agrupados por sistema**.
- [ ] No segmento **Sem acesso** aparecem pessoas que mudaram de cargo ou de
      gestor e **não têm acesso em nenhum sistema**. Elas não entram na fila de
      trabalho (não há o que revisar), mas a movimentação fica visível.
- [ ] Clique **tratar** numa pessoa → ticket + motivo → ela vira **Tratado**,
      com lupa para rever os dados do tratamento.
- [ ] **Exportar Excel**: traz o agrupamento (+/−) igual à tela e as colunas
      **De** e **Para**.

## 2. O que deixou de fazer sentido (Card 23)

**Onde:** aba **Transferidos**, expandindo uma pessoa.

Este é o ponto principal desta entrega. Antes, o sistema mandava revisar
**todos** os acessos de quem foi transferido. Agora ele aponta quais deixaram
de caber na função/equipe nova.

- [ ] Na linha da pessoa, ao lado da contagem de acessos, aparece o selo
      **"N sobrou"** (laranja) quando há acesso que só a situação anterior
      justificava.
- [ ] Ao expandir, o bloco **revalidação pós-transferência** mostra quatro
      números: quantos **mantêm**, quantos **sobraram da anterior**, quantos
      estão **fora do padrão** e quantos **faltam na nova**.
- [ ] A lista **"Sobraram da função/equipe anterior — candidatos a revogar"**
      nomeia sistema e perfil de cada um.
- [ ] O que **falta** aparece em azul, marcado como **informativo** — a inclusão
      já é tratada nas pendências; aqui é só contexto da mudança.
- [ ] Quando o critério é a equipe (caso do SIG), aparece também o tamanho dos
      grupos comparados, ex.: *(equipe de 4 → 19 pessoas)*.

**Como o sistema decide:**

| sistema | critério do "esperado" |
|---|---|
| com matriz (SYSTUR, SIGOT, Oracle, SICA, IC) | matriz de perfil por centro de custo + cargo, e a CCO por centro de custo + gestor |
| SIG | **padrão da equipe** — perfil que ≥70% dos colegas que usam o SIG possuem, agrupando por centro de custo + gestor + cargo |

Por isso uma **troca de gestor** muda o resultado no SIG: a pessoa passa a ser
comparada com a equipe nova.

## 3. Formulário de tratativa (regra nova)

**Onde:** qualquer botão de tratar/resolver — nas abas Pendências, Desligados e
Transferidos. O formulário agora é o mesmo nos três.

Antes o **nº do ticket do Jira era obrigatório**: não dava para registrar uma
tratativa sem ter um chamado aberto. Agora o formulário separa as duas coisas.

- [ ] O formulário tem duas seções: **Tratativa do analista** (Motivo e Parecer,
      os dois obrigatórios) e **Chamado no Jira**, marcada como **opcional**.
- [ ] O cursor começa no **Motivo**, não no ticket.
- [ ] O combobox de **Motivo** vem preenchido com os três motivos:
      Exceção · Transferência de Área · Acesso Indevido.
      *(Se aparecer um aviso amarelo dizendo que não conseguiu ler a lista,
      avise — a tela continua funcionando, mas é sinal de problema.)*
- [ ] **Resolver sem informar ticket**: preencha só Motivo e Parecer e confirme.
      Tem que funcionar — é o ponto principal da mudança.
- [ ] **Tentar resolver sem Parecer**: tem que recusar e explicar o que falta.
- [ ] **Tentar resolver sem Motivo**: idem.
- [ ] O botão **"Abrir chamado no Jira"** aparece, mas está **desabilitado** —
      passe o mouse e leia a explicação. É o esperado nesta versão: a abertura
      automática depende do formulário no Jira.
- [ ] Na **lupa** de um caso já tratado, as duas seções aparecem separadas, e o
      bloco do Jira está marcado como **somente leitura**.
- [ ] Numa tratativa registrada **sem** chamado, a lupa diz
      *"tratativa registrada sem chamado"* em vez de campos vazios.

> **Sobre o histórico:** as resoluções antigas continuam lá, inteiras. Algumas
> têm motivos da lista anterior (ex.: "Justificado pelo gestor"), que não estão
> mais disponíveis para escolha. A tela mostra o motivo **registrado na época** —
> histórico não é reescrito para caber na lista atual.

## 4. Visão Geral (Card 24)

**Onde:** aba **Visão Geral**.

- [ ] Novo indicador **"Acessos p/ Revogar"** com o total de acessos que
      sobraram das funções anteriores.
- [ ] Abaixo dele, o detalhe: quantas **movimentações** houve e quantas pessoas
      têm **acesso a revisar**.
- [ ] Clicar no indicador **leva direto para a aba Transferidos**, já no
      segmento "A Revisar".
- [ ] Os indicadores que já existiam (Pendências, Desligados com Acesso,
      Cobertura RH, Quarentena, Incluir Acesso) continuam iguais.

---

## O que ainda NÃO está nesta entrega

- **Revogar pelo sistema.** O painel aponta os candidatos; a revogação em si
  segue sendo feita fora, e registrada aqui pelo "tratar" com ticket.
- **Corte temporal** de transferência (toda mudança conta, sem janela de data).
- **Abertura automática de chamado no Jira** — Cards 25 e 26.

## Se algum número parecer estranho

Vale registrar o caso (matrícula + sistema + o que esperava ver). Dois
comportamentos são propositais e costumam gerar dúvida:

- pessoa que mudou **só de gestor** mantendo cargo e centro de custo **não**
  muda nada nos sistemas com matriz — só no SIG, que compara por equipe;
- quando a equipe tem menos de 2 pessoas usando o sistema, não há padrão para
  comparar e o sistema **não emite veredito** em vez de chutar.
