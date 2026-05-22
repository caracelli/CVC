# Regras de Negócio — CVC IAM Analytics
## Fase 1 — Sistema SYSTUR

Documento de apoio para apresentação ao cliente. Explica, em linguagem direta,
como o sistema analisa os acessos e classifica cada pendência.

---

## 1. O que o sistema faz

A cada processamento, o sistema:

1. Importa a base de **RH** — funcionários ativos e desligados.
2. Importa os **extratos de acesso** do SYSTUR.
3. Importa as **matrizes de perfis** — que definem qual perfil cada cargo
   deve ter em cada sistema.
4. Cruza tudo e gera a lista de **pendências** — situações que fogem do
   esperado e precisam de tratamento.

## 2. Como a validação funciona

Para **cada funcionário ativo**, o sistema:

- Identifica o **cargo** e o **centro de custo** do funcionário.
- Consulta a **matriz de perfis**: qual perfil aquele cargo deveria ter no SYSTUR.
- Compara com o **acesso real** do funcionário no SYSTUR.

Do resultado dessa comparação nasce a **classificação da pendência**.

## 3. As classificações de pendência

A grade de **Pendências** mostra quatro tipos de situação. Cada um vem de uma
regra exata:

### Incluir Acesso  *(tipo "Sem Acesso")*
- **O que é:** o funcionário **não tem** o acesso que o cargo dele exige.
- **Como é detectado:** a matriz diz que o cargo deve ter um perfil no SYSTUR,
  mas o funcionário não aparece com nenhum acesso no sistema.
- **Ação recomendada:** incluir o perfil para o funcionário.

### Alterar Perfil  *(tipo "Divergente")*
- **O que é:** o funcionário **tem** acesso, mas com o **perfil errado**.
- **Como é detectado:** o funcionário tem um perfil no SYSTUR, mas ele é
  **diferente** do perfil que a matriz define para o cargo.
- **Ação recomendada:** alterar o perfil para o que a matriz determina.

### Em Análise
- **O que é:** não é possível decidir automaticamente qual o perfil correto.
- **Como é detectado:** a matriz lista **mais de um perfil possível** para
  aquele cargo. O sistema não escolhe sozinho — marca para revisão.
- **Ação recomendada:** análise manual para definir o perfil adequado.

### Não Mapeado  *(tipo "Sem Vínculo RH")*
- **O que é:** existe um acesso no SYSTUR que **não pertence a ninguém** do RH.
- **Como é detectado:** o acesso no sistema não tem funcionário correspondente
  na base de RH ativa.
- **Ação recomendada:** investigar a origem do acesso (conta antiga, terceiro,
  erro de cadastro) e regularizar ou remover.

## 4. Situação da pendência

Toda pendência nasce **Pendente**. Depois de tratada, passa a **Resolvida** —
é o ciclo de acompanhamento do trabalho de regularização.

## 5. Quarentena

A quarentena é um período em que um funcionário fica **separado para revisão**.
Ao enviar para a quarentena, ele sai da lista de pendências ativas por um prazo
configurado (padrão: **90 dias**), registrando **quem enviou** e **quando**.
Pode ser retirado a qualquer momento, e o histórico de entradas e saídas fica
guardado.

## 6. Histórico de pendências

A aba **Histórico** é a trilha das pendências tratadas. Para cada resolução,
registra duas marcações, formando a linha do tempo de cada funcionário:

- **Pendência identificada** — quando a pendência foi detectada pelo
  processamento.
- **Pendência resolvida** — quando foi encerrada, com o ticket do Jira.

O Histórico é agrupado por funcionário e ordenado por data (mais recente no
topo). Clicando em cada marcação, abre-se o detalhe — o que era a pendência
ou os dados da resolução.

---

*As classificações e seus critérios são aplicados pelo motor de validação do
Processador. Este documento reflete as regras vigentes da Fase 1 — SYSTUR.*
