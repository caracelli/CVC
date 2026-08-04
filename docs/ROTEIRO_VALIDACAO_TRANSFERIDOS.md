# Roteiro de validação — Transferidos (Cards 22, 23 e 24)

Pacote: `TESTE_LOCAL_BRUNA_v1.0.0.zip`. Roda 100% local, não usa a rede e não
interfere na versão instalada no ambiente do cliente.

> **Antes de começar — dois avisos que evitam falso alarme**
>
> 1. O Processador **não abre janela preta**: ele abre uma **aba do navegador**
>    com o log ao vivo. Quando aparecer "Concluído", clique em **Fechar** nessa
>    aba. Se rodar de novo sem fechar, fica uma aba por execução.
> 2. A aba **Transferidos nasce vazia no primeiro processamento**. Isso é o
>    esperado, não é erro — o sistema descobre quem foi transferido comparando
>    **duas** cargas de RH (o "antes" e o "depois"). O passo 2 abaixo traz a
>    segunda carga.

---

## Passo 1 — primeiro processamento

1. Extraia a pasta `CVC_IAM_ANALYTICS` em qualquer lugar do seu PC.
2. Rode `EXECUTAVEIS\Processador.exe`. Ao terminar, clique em **Fechar** na aba.
3. Rode `EXECUTAVEIS\visualizador.exe` — o painel abre em `http://127.0.0.1:8800/`.

- [ ] A aba **Transferidos** está vazia. *(esperado neste momento)*

## Passo 2 — chega a segunda carga de RH

4. Copie `CVC_IAM_ANALYTICS\2a_CARGA_RH\PROJETOIAM.CSV` para
   `CVC_IAM_ANALYTICS\ENTRADA\RH\ATIVOS\`.
5. Rode o `Processador.exe` de novo (e clique em **Fechar** ao terminar).
6. Atualize o painel (F5).

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

## 3. Visão Geral (Card 24)

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
