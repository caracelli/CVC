# Roadmap de entrega — CVC IAM Analytics

Estado em **14/08/2026 (sexta)**. Substitui o `RETOMAR_11082026.md`, que ficou
para trás (ele aponta HEAD `d4261a0`; de lá para cá entraram a integração Jira,
a correção da dobra e as validações).

O código está construído e validado. **O que falta não é desenvolvimento** — é
uma entrega agendada, uma decisão do Nelson e dois pontos com a CVC.

---

## 📅 Segunda, 17/08/2026 (manhã) — enviar o pacote para a Bruna

**O pacote já está gerado:** `ENTREGA/UPDATE_BRUNA_v1.1.1.zip` (109,2 MB, 12
arquivos, `testzip` limpo). Se algo mudar no código antes de segunda, regerar com:

```
cd deploy && python build_update_bruna.py
```

**Por que é um UPDATE e não o pacote completo.** Os arquivos de entrada do
cliente não estão versionados e a máquina atual não tem 16 deles (SIGOT,
SICA_RA, SICA_ESFERA e SIG) — o `ENTRADA.zip` disponível é de outro ciclo. Mas a
Bruna **já tem tudo isso** do pacote de 07/08 (`bfc9546`: 4 grupos, 14 bases,
Pendências 421 · Consulta 3.042 · Aderentes 2.714). O que mudou foi código, então
só a `EXECUTAVEIS/` viaja e a base dela fica onde está.

**O que vai no pacote:** `<versao>1.1.1</versao>`, `<raiz>` vazia (modo local),
os 7 sistemas ativos. **Sem** `jira.xml` (credencial) e **sem**
`launcher_atualizador.exe` (inútil em modo local e é o que o Defender derruba).
O builder aborta se um `jira.xml` escapar para o pacote.

### Instrução que vai junto

1. Fechar o painel e o Processador.
2. Extrair e copiar `EXECUTAVEIS/` **por cima** da pasta atual. **Não** tocar em
   `DADOS/` nem `INTERACOES/`.
3. **Rodar o `Processador.exe` uma vez — obrigatório.** Sem isso os números da
   tela continuam os antigos: os 6 ajustes agem na fase de *análise*, não na
   importação. É o reprocessamento que faz os **762 desligados recontratados
   virarem 24**.
4. Abrir o `visualizador.exe`.

### Avisar antes que os números vão mudar

O ajuste A muda a contagem por ordem de grandeza (762 → 24), e os demais mexem
na Consulta, na dedup dos perfis e nas colunas da grid. **Qualquer roteiro,
print ou planilha que ela tenha feito sobre o pacote atual fica desatualizado.**
Melhor avisar antes do que ela descobrir conferindo.

### A atualização foi simulada ponta a ponta (14/08)

Não é teoria — rodei o caminho inteiro numa cópia:

| Etapa | Resultado |
|---|---|
| Copiar `EXECUTAVEIS/` por cima | versão 1.0.0 → 1.1.1, raiz local preservada |
| Rodar o Processador | exit 0, `Processamento finalizado` |
| Dados | `rh_desligados` 32→32, `chamados_abertos` 2→2 |
| Quarentena gravada **antes** do update | sobreviveu com ticket, título e prazo |
| `INTERACOES/` | consolidada e resetada, sem pasta órfã |

A quarentena escrita no `.jsonl` antes da troca de versão foi consolidada pelo
Processador novo depois dela. **O trabalho já registrado pela Bruna não se perde.**

---

## 🔸 Decisão do Nelson — trava o pacote de PRODUÇÃO

**Qual é a raiz de rede correta?** Os empacotadores discordam:

| Builder | Raiz que grava no `config.xml` | Versão |
|---|---|---|
| `build_entrega_prd.py` | `\\intra.cvc\fscvc\Processos_Antlia\CVC\CVC_IAM\ANALYTICS` | 1.3.1 |
| `build_entrega_rede.py` | `Z:\CVC\CVC_IAM_ANALYTICS` | — |
| `build_update_executaveis.py` | `Z:\CVC\CVC_IAM_ANALYTICS` | 1.4.5 |

O `config.xml` do repositório usa a UNC, igual ao `_prd`.

**Por que não dá para chutar:** o update copia a `EXECUTAVEIS/` inteira por cima
da rede, **incluindo o `config.xml`**. Empacotar com a raiz errada troca o
caminho da produção — e o erro não aparece no build, aparece na máquina do
cliente, como uma instalação que não acha os dados.

Definida a raiz, o pacote sai na sequência (`VERSAO` já está em 1.4.5). Corrigir
junto o docstring do `build_entrega_prd.py`, que diz "versao 1.0.0, raiz Z:"
enquanto o código faz 1.3.1 e UNC.

**Também pendente:** decidir se o `UPDATE_BRUNA_v1.1.1.zip` (109 MB) entra no
LFS. A política do `.gitignore` é versionar os pacotes de propósito, com a regra
de limpar os antigos — se for versionar, apagar o `TESTE_LOCAL_BRUNA_v1.0.0.zip`
junto, senão acumula como os 994 MB anteriores.

---

## 🔹 Com a CVC — fluxo do Jira

Assumidos pela área em 14/08. O código está pronto e validado pelo formulário;
até estes pontos fecharem, a integração fica com `<ativo>false</ativo>` e o botão
desabilitado — que é o estado seguro.

1. **Componente no tipo 8819.** Sem ele o chamado não entra em fila nenhuma.
2. **Conta de serviço + API token** — cadastrada como **cliente** do portal, não
   agente. Entra na subida para produção.

**Conferência obrigatória antes de ligar o `<ativo>`:** criar chamado pelo portal
com dados falsos → varrer as filas → cancelar (transição 261). Passo a passo e as
duas armadilhas já pagas estão em `PLANO_JIRA_DESLIGADOS.md`, seção "Go-live".

---

## ✅ Fechamento do projeto

**Não há documento de entrega final** (definido em 14/08). O **aceite da Bruna
encerra o Card 26** — e portanto o projeto. O caminho crítico é, literalmente:
enviar segunda → ela validar → aceite.

---

## Estado da construção (validado em 14/08)

Seis ângulos de validação, todos cobertos:

| Ângulo | Resultado |
|---|---|
| Suíte | 746 passed + 53 subtests, 746 coletados, zero skip/xfail |
| Executáveis | os 5 sobem; Processador ponta a ponta, exit 0 |
| Migrações | banco de 14/07 migrado, `chamados_abertos` preservado |
| API | 11 rotas 200 + escrita real do `.jsonl` pelo exe |
| Schema | 14 INSERTs conferidos, zero coluna inexistente |
| Empacotadores | `jira.xml` sem vetor de vazamento; raiz divergente (acima) |

O ciclo multiusuário fecha **dentro dos binários**: POST escreve o `.jsonl`, o
Processador dobra no banco, a leitura seguinte mostra o dado.
