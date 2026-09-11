# CVC IAM Analytics
## Roteiro de validação — respostas ao seu teste de 09/09
Pacote UPDATE_BRUNA_v1.0.0 · 11/09/2026

**Por que este documento existe**

Ele responde, ponto a ponto, o documento de testes que você mandou em 09/09 (“Testes 2”). Cinco pontos viraram correção no painel e três eram dúvidas de funcionamento, que estão respondidas aqui. No caminho entraram mais dois ajustes, também descritos.

**Como usar**

Igual ao roteiro de 08/09: cada ajuste tem “Como conferir” e o valor esperado, e a última linha pergunta se a regra está CERTA. As marcadas com ★ são as que mais aparecem na tela.

> Os números “medidos” deste documento vêm da SUA base: o pacote de 08/09 trouxe o banco e os arquivos de entrada da sua máquina, e reprocessamos aqui com a versão nova. Se você depositou arquivos novos depois de 08/09, os seus números podem diferir um pouco.


## Antes de tudo: o que fazer, nesta ordem

O mesmo procedimento de 08/09. O passo 3 continua obrigatório: as correções agem na fase de ANÁLISE, e sem rodar o Processador a tela continua com os números da rodada anterior.

1. Feche o painel e o Processador, se estiverem abertos.
2. Extraia o pacote e copie EXECUTAVEIS/ por cima da pasta atual. NÃO apague nem mexa em DADOS/ e INTERACOES/ — é onde ficam o banco e as tratativas que você já registrou.
2b. Copie também a pasta ENTRADA/ do pacote por cima da atual. Ela leva só os dois arquivos de referência de sempre (o de-para do SIG e a matriz do franqueado). Nenhum dado seu é substituído.
3. Rode o Processador.exe UMA VEZ. Obrigatório.
4. Abra o visualizador.exe.

## 1. O que você apontou e foi corrigido


### ★ 1.1 Colaborador ativo que não aparecia na Consulta

- **O que decide:** Se todo colaborador ativo aparece na Consulta.
- **Critério:** Quem não tem nenhum acesso esperado relevante para o cargo (a matriz não prevê nada, ou prevê sistemas que quase ninguém do cargo usa — o limiar de 30%) ficava sem nenhuma linha e sumia da tela inteira. Agora aparece na Consulta com a situação “Sem Expectativa”: é informativo, NÃO entra em Pendências nem nos contadores.
- **Como conferir:** Consulta → busque WILIAN MANOEL DE OLIVEIRA, AURELINA DE SOUZA SANTOS CAMILO ou qualquer outro nome da sua lista.
- **Medido na sua base (reprocessada aqui com a versão nova):** 19 dos 21 nomes da lista passam a aparecer. Os ativos sem nenhuma linha no painel caem de 6.747 para 6.194 — o restante é explicado na nota abaixo.
- **A regra está correta? Se não, qual deveria ser?:** ______

> Os três nomes que continuam de fora têm motivo próprio. PRISCILA SANTOS DE LIMA não está na sua base de ativos (há uma JAQUELINE PRISCILA OLIVEIRA DE LIMA, que é outra pessoa) — vale conferir de onde veio o nome. LEONARDO COELHO PALADINO e ANA PAULA DE BARROS BRAGA SOARES eram aderentes no SYSTUR em 01/07 e hoje não têm nenhum acesso ativo: a regra temporária de “provável desligamento” os tira da tela até a fase de desligados. Dos demais que seguem fora, a grande maioria são franqueados e prestadores sem acesso nenhum, pelas regras já combinadas (roteiro de 08/09, item 1.1, e roteiro de 06/08, item 2.6); o restante são outros casos da mesma regra de provável desligamento.


### ★ 1.2 SYSTUR na Consulta com a mesma leitura da Pendências

- **O que decide:** Como aparece o acesso que casa com mais de um perfil do cargo.
- **Critério:** No SYSTUR a pessoa só pode ter UM perfil. Quando o perfil dela não bate com nenhum dos que o cargo permite, a Consulta listava cada perfil possível como uma linha — lia como “faltam 5”. Agora é uma linha só, como na Pendências: “Tem hoje: X · Esperado: 1 de N opções”. O contador de pendências da pessoa conta esse acesso uma vez.
- **Como conferir:** Consulta → uma pessoa com “Em Análise” no SYSTUR → “ver detalhe”.
- **Medido na sua base (reprocessada aqui com a versão nova):** 12 pessoas nessa situação (SYSTUR, SIGOT e Oracle EBS), que somavam 42 linhas e agora são 12 — uma por acesso.
- **A regra está correta? Se não, qual deveria ser?:** ______


### 1.3 “Acessos iguais” vindo como Em Análise

- **O que decide:** Quando o perfil da pessoa e o dos colegas são o mesmo escrito diferente.
- **Critério:** A comparação com os colegas (usada para terceiro e prestador) era letra a letra: “gestao de acessos” e “GESTAO DE ACESSOS” contavam como perfis diferentes. Agora ignora maiúscula, acento e espaço. A tela continua mostrando cada perfil como está escrito no extrato.
- **Como conferir:** Consulta → CAROLINA MOTA SANTOS DE JESUS → SICA_RA.
- **Medido na sua base (reprocessada aqui com a versão nova):** O SICA_RA dela sai como Aderente. Era a única linha nesse caso (Em Análise do espelho de prestador: 26 → 25).
- **A regra está correta? Se não, qual deveria ser?:** ______


### ★ 1.4 Trocar de aba perdia os dados

- **O que decide:** O que a aba mostra quando a leitura dos dados falha.
- **Critério:** Quando a leitura de uma aba falhava uma vez, o painel guardava o erro como se fosse a resposta, e a aba ficava vazia em toda volta até fechar e abrir de novo. Agora o erro não é guardado — a próxima visita lê de novo. Se ainda assim falhar, a aba DIZ que falhou, em vez de mostrar a lista vazia com o contador antigo em cima.
- **Como conferir:** Navegue entre as abas várias vezes, principalmente Transferidos.
- **Deve mostrar (vale em qualquer base):** Nunca “Nenhuma transferência detectada” com o contador preenchido (era o seu print: “69 a revisar” sobre uma lista vazia). Em falha, a mensagem “Não foi possível carregar os transferidos”.
- **A regra está correta? Se não, qual deveria ser?:** ______


### 1.5 O que é o “D” na Consulta

- **O que decide:** O selo D da coluna Abas.
- **Critério:** D quer dizer que a matrícula consta na base de DESLIGADOS — não que haja algo a remover. Quem consta como desligado mas não tem nenhum acesso ativo é “OK”: nada a fazer. Por isso você filtrava e não achava nada. Agora o botão diz qual é o caso ao passar o mouse, e fica apagado quando não há nada a remover.
- **Como conferir:** Consulta → passe o mouse sobre um “D”.
- **Deve mostrar (vale em qualquer base):** D apagado = desligado sem acesso ativo (nada a remover). D normal = acesso ativo a revogar, ou já encaminhado para tratamento.
- **A regra está correta? Se não, qual deveria ser?:** ______


## 2. Suas dúvidas de funcionamento


**“Se eu tratar um caso que não muda o perfil na próxima atualização da base, o que se espera?”**

A tratativa não se perde e não expira. Na próxima atualização, se o caso vier IGUAL (mesma pessoa, mesmo sistema, mesmo perfil), ele continua como Resolvido. Se o perfil encontrado MUDAR, é um caso novo: aparece como Pendente, e a tratativa anterior fica registrada no histórico.

> Um cuidado: a tratativa dada para a PESSOA inteira ou para um SISTEMA inteiro vale para o escopo todo — se aparecer uma pendência nova nesse escopo, ela também sai como Resolvido. Tratar pelo acesso específico evita isso. Separar os ciclos de tratativa ao longo do tempo está previsto para a fase de integração com o Jira.


**“O usuário com perfil básico que pode não estar mapeado na matriz — como ele se comporta?”**

Se o cargo não tem nenhum acesso esperado, ele aparece na Consulta como “Sem Expectativa” (item 1.1): é informativo e nunca vira pendência. Se o cargo tem expectativa e o perfil dele não é o previsto, ele aparece como Alterar Perfil ou Em Análise; tratado, segue a regra acima.


### 2.1 Tratativa por sistema ou por acesso entra no Histórico

- **O que decide:** Se toda tratativa aparece no Histórico e no tempo médio.
- **Critério:** Achado ao revisar a sua dúvida. A tratativa pode ser dada para a pessoa inteira, para um sistema ou para um acesso. Só a primeira chegava ao Histórico e ao tempo médio da Visão Geral; as outras duas apareciam Resolvido na Pendências e não entravam lá. Agora as três entram.
- **Como conferir:** Trate uma pendência só de um sistema → rode o Processador → Histórico da pessoa.
- **Deve mostrar (vale em qualquer base):** O marco “Pendência resolvida” aparece no sistema tratado, com o ticket e a data da tratativa.
- **A regra está correta? Se não, qual deveria ser?:** ______


**“O transferido apaga o histórico do que ele já trouxe? Fica pendente até ser tratado?”**

A lista de Transferidos é refeita a cada carga (compara a base de RH nova com a anterior), mas nada se perde: a movimentação e a tratativa ficam registradas. Sim, a pessoa fica em “A Revisar” até ser tratada.


**“Se eu der a tratativa, ele encerra o ciclo? Ou, se o perfil ficar inaderente, ele vem nas pendências?”**

As duas coisas, porque são verificações separadas. A tratativa encerra o caso na aba Transferidos. Já a Pendências olha o perfil: se o acesso continuar fora do esperado para a função nova, ele aparece lá — e é resolvido lá.


**“O transferido pode, já no primeiro apontamento, aparecer nas duas guias?”**

Sim, é esperado. A aba Transferidos mostra que a pessoa mudou de função; a Pendências mostra se o acesso dela está certo para a função nova. Tratar em uma não resolve a outra.

> Um cuidado na aba Transferidos: a tratativa é registrada pela matrícula. Se a mesma pessoa for transferida de novo mais adiante, ela aparece como já tratada — vale conferir o de → para antes de considerar o caso encerrado.


## 3. Preparado para os próximos arquivos


### 3.1 SICA no mesmo modelo do SICA_RA

- **O que decide:** Como os extratos de SICA que ainda não chegaram serão lidos.
- **Critério:** Confirmado que os demais arquivos de SICA virão no mesmo modelo do SICA_RA de 01/09. O SICA_ESFERA já está preparado para esse modelo, sem deixar de ler o relatório que você manda hoje — lido nos dois arquivos reais (24/06 e 15/08), o resultado é idêntico ao de antes.
- **Como conferir:** Quando depositar o arquivo novo: painel → “Arquivos importados”.
- **Deve mostrar (vale em qualquer base):** A data do arquivo novo aparece, e a quantidade de acessos não é zero. Se vier zero, me avise — é o sinal de layout diferente do esperado.
- **A regra está correta? Se não, qual deveria ser?:** ______


## 4. As perguntas do roteiro de 08/09


**“3 de 3 — Qual extrato do SYSTUR está na sua ENTRADA?”**

Respondida pela sua própria base: é o formato novo (view_systur_08_09_2026_07-00.csv), com a coluna de status. Nada a trocar.

Seguem em aberto as outras duas. Com o extrato novo, os franqueados que ficam em Em Análise são, na sua base, principalmente os perfis de exceção da pergunta 1 (199 linhas) — é ela que mais mexe na fila.


## 5. Resumo para devolver

As duas perguntas em aberto e, abaixo, o que discordar. O que não for citado fica entendido como aprovado.

1. Os perfis de exceção (FRANQUEADOS_VC, GERENTE_GERAL_MASTER, MASTER_FRANQUEADO) têm aprovação da Governança de SI?
2. As 11 equivalências de cargo derivadas do uso estão corretas?

| Item | O que está errado | O que deveria ser |
|---|---|---|
| | | |
| | | |
| | | |
