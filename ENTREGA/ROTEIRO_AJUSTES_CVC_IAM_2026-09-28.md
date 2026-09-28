# CVC IAM Analytics
## Roteiro de validação — seu documento de 28/09
28/09/2026

**Por que este documento existe**

Ele responde, um a um, os seis pontos do seu documento de 28/09 (ajustes_apl_28_09). Todos precisavam de correção. Cada item diz o que era, o que mudou, como conferir e o valor esperado na sua base.

**Leia primeiro: as pendências DIMINUEM**

As pendências caem de 1.278 para 1.072 pessoas, porque quem tem no SIG exatamente os perfis da função deixou de ser pendência (item 5). O total de linhas sobe de 12.310 para 13.446, porque o Oracle previsto voltou a aparecer para 33 pessoas que não têm SYSTUR (item 4).

> O pacote já traz a pasta DADOS com o banco processado: você NÃO precisa rodar o Processador. Se rodar, tudo bem — deixe as matrizes na pasta ENTRADA, como da última vez.


## Antes de tudo: o que fazer, nesta ordem

- 1. Feche o painel e o Processador, se estiverem abertos.
- 2. BACKUP (obrigatório): copie as pastas DADOS\BANCO e INTERACOES para outro lugar. Se algo não sair como esperado, é só devolvê-las.
- 3. Extraia o pacote na pasta principal da instalação — a que contém DADOS, ENTRADA e EXECUTAVEIS — e aceite substituir os arquivos.
- 4. NÃO apague nem mexa na pasta INTERACOES: é onde ficam as suas tratativas, e o painel as lê ao vivo.
- 5. Abra o visualizador.exe.


## 1. Os seis pontos do seu documento de 28/09


### ★ 1 O Excel volta a bater com a tela

- **O que decide:** O que sai na planilha da Consulta no formato Analítico.
- **Critério:** No Analítico, cada linha de sistema completava o que vinha vazio com o valor da linha da pessoa — e a linha da pessoa junta os perfis de todos os sistemas. Por isso os perfis do SIG apareciam como “Perfil Encontrado” em todos os sistemas. Agora só a identificação (matrícula, nome, cargo, centro de custo, e-mail) se repete; perfil vazio num sistema quer dizer que a pessoa não tem acesso nele. O mesmo defeito fazia as exportações de Inclusão, Histórico RH e Quarentena perderem o primeiro registro de cada pessoa no Analítico — corrigido junto.
- **Como conferir:** Consulta → busque BRUNA OLIVEIRA SANTOS → Exportar → Analítico.
- **Deve mostrar (vale em qualquer base):** Sete linhas com a matrícula PREST-corpp03779. “Perfil Encontrado” preenchido só na linha do SIG; nas demais, vazio. “Perfil Esperado” com o perfil de cada sistema.
- **A regra está correta? Se não, qual deveria ser?:** ______


### ★ 2 Oracle: o mesmo perfil não aparece mais em “falta” e “a mais”

- **O que decide:** Como a aplicação lê os acentos dos arquivos.
- **Critério:** Os seus arquivos estão certos. A aplicação tentava adivinhar a codificação e às vezes errava: “Criação” virava “Criaçăo” e não batia com a matriz. A leitura foi corrigida para TODOS os arquivos. Na sua base isso atingia 47 perfis do Oracle, 110 nomes do SYSTUR e departamento/cargo do RH — e a data de admissão, que vinha vazia. Correções só de acento não são tratadas como movimentação: o Histórico e os Transferidos não mudam.
- **Como conferir:** Consulta → HERMES LUIS DOS SANTOS (90000639) → Oracle EBS.
- **Deve mostrar (vale em qualquer base):** “Tem 46 · Faltam 3: CVC AR RA VIAGENS Consulta Fiscal, CVC PA NOVA VISUAL Analista, CVC RI NOVA VISUAL Consulta Fiscal · 1 a mais: CVC OIE BRASIL - Relatório de Despesas” — exatamente a sua conferência manual. Os “CVC INV … Criação Itens” estão entre os 46 que ele tem. Na base: 42 falsos “perfil inválido” do Oracle deixaram de existir.
- **A regra está correta? Se não, qual deveria ser?:** ______


### 3 A lista de perfis sai sempre do mesmo jeito

- **O que decide:** Como a tela mostra vários perfis de um mesmo sistema.
- **Critério:** Quando cada perfil era uma linha separada, a tela os juntava com vírgula; quando vinham juntos, mostrava em lista. Agora é sempre um embaixo do outro, com os 6 primeiros visíveis e “+N outros” para abrir o resto — com a mesma formatação.
- **Como conferir:** Consulta → LETICIA LEMOS DE SOUZA (34532586) → Oracle EBS → clique em “+17 outros”.
- **Deve mostrar (vale em qualquer base):** Os 23 acessos esperados em lista vertical, do começo ao fim.
- **A regra está correta? Se não, qual deveria ser?:** ______


### ★ 4 O Oracle previsto aparece para quem não tem SYSTUR

- **O que decide:** O que a aplicação mostra no Oracle para quem não tem perfil no SYSTUR nem acesso no Oracle.
- **Critério:** A regra do Oracle segue o perfil do SYSTUR. Sem perfil no SYSTUR, ela não tinha com o que comparar e escondia todo o Oracle — a tela dizia “sem perfil previsto”, o que não é verdade. Agora vale o perfil de SYSTUR que a matriz prevê para a pessoa (o mesmo que a pendência de SYSTUR manda incluir). Quem TEM Oracle e não tem SYSTUR continua como estava: a pendência fica no SYSTUR.
- **Como conferir:** Consulta → RAFAEL FELIPE DE MORAES (14546).
- **Deve mostrar (vale em qualquer base):** Oracle EBS em “Acessos esperados” com 39 perfis, junto de SIGOT (Contabil1) e SYSTUR (INTEGRADOR_CONTABIL). O Oracle sai do bloco “Sem mapeamento”. Na base: 33 pessoas.
- **A regra está correta? Se não, qual deveria ser?:** ______


### ★ 5 SIG com exatamente os perfis da função é aderente

- **O que decide:** Se quem tem no SIG o conjunto previsto pela função vira pendência por “mais de um perfil”.
- **Critério:** Sua resposta à pergunta de 24/09: no SIG os perfis da função se somam. Quem tem exatamente o conjunto previsto passa a ser aderente, sem o alerta, e a lista sai uma vez só (não mais “Tem hoje” + “Deveria ter” iguais). Quem tem só parte do conjunto, ou algo a mais, continua em análise. Nos outros sistemas a regra de “um perfil por sistema” não muda.
- **Como conferir:** Consulta → ATHAMIRIS DA SILVA TORRES (23242).
- **Deve mostrar (vale em qualquer base):** SIG em “Acessos encontrados”, em verde, sem alerta. Em “Funções previstas”, Supervisor de Operações “completa”. Na base: 219 linhas do SIG deixaram de ser pendência.
- **A regra está correta? Se não, qual deveria ser?:** ______


### 6 As funções mostram um perfil por linha

- **O que decide:** Como aparece o sistema com vários perfis dentro de “Funções previstas”.
- **Critério:** O SIG vinha num parágrafo com um status só (“Em Análise”), enquanto “Outras funções” mostrava perfil a perfil. Agora as duas têm a mesma leitura: cada perfil previsto aparece como “tem” ou “falta”, o que a pessoa tem fora do previsto como “a mais”, e a conta da função é por perfil.
- **Como conferir:** Consulta → PAMELLA DE OLIVEIRA DA SILVA (6171) → Funções previstas → clique em “Operacional e Não Operacional”.
- **Deve mostrar (vale em qualquer base):** “completa”, com cada perfil do SIG numa linha marcada “tem”, seguidos de SIGOT e SYSTUR (“tem”) e Opera (“sem extrato”).
- **A regra está correta? Se não, qual deveria ser?:** ______


## 2. O que vai parecer diferente — e por quê

Estas mudanças alteram números que você acompanha. Nenhuma delas é erro; todas vêm dos pontos acima.

- As pendências CAEM de 1.278 para 1.072 pessoas (de 1.342 para 1.123 linhas): são as 219 linhas do SIG com o conjunto exato da função (item 5).
- O total de linhas SOBE de 12.310 para 13.446: são os perfis de Oracle a incluir das 33 pessoas sem SYSTUR (item 4).
- A data de admissão passa a aparecer. Nesta base, 1.997 pessoas (as do último arquivo de RH); as demais entram à medida que os próximos arquivos chegarem.
- Histórico e Transferidos não mudam: correções só de acento não contam como movimentação (item 2).


## 3. Suas respostas às perguntas de 24/09

4.1 — Relatório de Despesas: você o apontou como “a mais” no Oracle do HERMES. Continua contando como pendência, como já estava.

4.2 — SIG: os perfis da função se somam. Aplicado no item 5.
