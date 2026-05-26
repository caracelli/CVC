# CVC IAM Analytics — Guia rápido do painel

## Filtros laterais

Aparecem em todas as abas. **Clique simples** isola o valor;
**Ctrl+clique** adiciona/remove (multi-seleção).

| Filtro | Para que serve |
|---|---|
| **Vínculo** | Separa Funcionário (CLT, na base RH) de Terceiro (quando a integração existir). |
| **Ação** | O que precisa ser feito com a pendência: Incluir Acesso, Alterar Perfil, Em Análise ou Não Mapeado. |
| **Status** | Pendente (ainda não tratado) ou Resolvido (já passou pela Resolução). |
| **Tipo** | Mesma classificação da Ação, com o rótulo usado na grid: Sem Acesso, Divergente, Em Análise, Sem Vínculo RH. |
| **Sistema** | Filtra por sistema de origem do acesso. Na Fase 1, apenas SYSTUR. |

---

## O que cada Ação significa

| Ação | Quando aparece |
|---|---|
| **Incluir Acesso** | Funcionário sem o acesso que a matriz do cargo exige. |
| **Alterar Perfil** | Funcionário com perfil diferente do permitido para o cargo. |
| **Em Análise** | O cargo tem mais de um perfil possível na matriz — alguém precisa decidir. |
| **Não Mapeado** | Acesso no sistema sem funcionário correspondente no RH ativo (usuário "órfão"). |

---

## Aba Pendências

Lista todos os funcionários (e usuários sem vínculo) com alguma
pendência de acesso. Uma linha por pessoa.

**Regras aplicadas:**

- Mostra somente pendências com Ação (Incluir, Alterar, Em Análise ou Não Mapeado).
- A coluna **Status** indica se já houve resolução: Pendente = não, Resolvido = sim.
- A linha agrupa todas as pendências do mesmo funcionário (quando há mais de uma, o número aparece na coluna **Qtd** e dá pra expandir).

**Ações disponíveis na linha:**

| Botão | O que faz |
|---|---|
| **Resolver (⊕)** | Abre um modal pra registrar a resolução sob ticket do Jira. Depois de confirmar, a linha passa a Resolvido e aparece no Histórico. |
| **Quarentena** | Coloca o funcionário em quarentena por 90 dias. Ele sai das Pendências e vai pra aba Quarentena. |
| **Lupa (🔍)** | Aparece quando a pendência já foi resolvida. Abre o modal com os detalhes da resolução (ticket, descrição, quem resolveu). |

---

## Aba Quarentena

Funcionários colocados em "compasso de espera" antes da decisão final.

**Regras aplicadas:**

- A quarentena dura **90 dias** a partir do envio (encerra sozinha após esse prazo).
- Quem manda pra cá é o usuário do painel (botão Quarentena na grid de Pendências).
- Dois sub-modos no topo da aba:
  - **Ativas**: quem está em quarentena agora.
  - **Histórico**: quem já saiu (com motivo e data de saída).
- Cada linha mostra quem criou a quarentena (usuário Windows) e quem encerrou (no Histórico).
- Botão **Retirar** (nas Ativas) encerra a quarentena antes do prazo. Vai pro Histórico com motivo "Resolvido".

---

## Aba Histórico

Trilha de auditoria das resoluções de pendências. Mostra o ciclo de
vida de cada pendência que foi tratada.

**Regras aplicadas:**

- Cada resolução gera **duas linhas**:
  - **Pendência identificada**: quando a pendência foi detectada pelo Processador.
  - **Pendência resolvida**: quando o usuário registrou a resolução sob ticket do Jira.
- A Pendência resolvida é **sempre posterior** à Pendência identificada (regra cronológica).
- Botão **Exportar Excel**: gera planilha com o mesmo agrupamento e formatação da grid.
- Histórico apenas lê — nada é editado aqui. As resoluções vêm da aba Pendências.

---

_CVC IAM Analytics — v2.0.1_
