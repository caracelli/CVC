# CVC IAM Analytics
## Roteiro de validação — seu documento de 29/09 (CCO)
29/09/2026

**Por que este documento existe**

Ele responde o seu documento de 29/09 (ajustes_apl_29_09): na CCO, a função da pessoa passa a ser definida pelo perfil que ela tem no SYSTUR, SICA RA, SICA ESFERA ou SIGOT. Traz também os 19 casos da sua base que mudaram com isso, com o antes e o depois, para você conferir.

> Este pacote substitui o de 28/09 e já inclui todos os ajustes dele. Ele traz a pasta DADOS com o banco processado: você NÃO precisa rodar o Processador.


## Antes de tudo: o que fazer, nesta ordem

- 1. Feche o painel e o Processador, se estiverem abertos.
- 2. BACKUP (obrigatório): copie as pastas DADOS\BANCO e INTERACOES para outro lugar. Se algo não sair como esperado, é só devolvê-las.
- 3. Extraia o pacote na pasta principal da instalação — a que contém DADOS, ENTRADA e EXECUTAVEIS — e aceite substituir os arquivos.
- 4. NÃO apague nem mexa na pasta INTERACOES: é onde ficam as suas tratativas, e o painel as lê ao vivo.
- 5. Abra o visualizador.exe.


## 1. O ajuste


### ★ 1 A função da CCO vem do SYSTUR, SICA RA, SICA ESFERA e SIGOT

- **O que decide:** Qual função da equipe (centro de custo + gestor) é cobrada de cada pessoa na CCO.
- **Critério:** Até aqui só o SYSTUR dizia a função. Quem não tinha SYSTUR recebia TODAS as funções da equipe — daí o “faltam 7” no Oracle e o “tem 2 de 13”. Agora vale o perfil que a pessoa tem em qualquer um dos quatro sistemas, buscado nas linhas da própria equipe. Oracle e SIG não definem a função (o mesmo perfil do Oracle está em várias funções); eles só recebem o que a função prevê. As demais funções da equipe aparecem em “Outras funções que a pessoa pode ter”, sem cobrança. Quem não tem perfil em nenhum dos quatro continua recebendo todas.
- **Como conferir:** Consulta → BRUNA OLIVEIRA FERREIRA DA SILVA (34532401) → aba Acessos. ANTES (pacote de 28/09): Oracle “Tem 1 · Faltam 7”; “Acessos esperados (12)” com SIGOT, SIG, SICA ESFERA e SYSTUR; “Outros acessos previstos: SICA_RA — 4 opções”; Funções previstas (5) com “Pós Faturamento — tem 2 de 13”.
- **Deve mostrar (vale em qualquer base):** DEPOIS — Oracle: “Tem 1: CVC AR BRASIL Faturamento · Faltam 2: CVC AP BRASIL Consulta, CVC AP BRASIL Cadastro de Fornecedor”. SICA RA: POS FATURAMENTO CONC. Sem “Acessos esperados” de SIGOT, SIG, SICA ESFERA e SYSTUR e sem “Outros acessos previstos”. Funções previstas: Pós Faturamento — “tem 2 de 4”. Outras funções que a pessoa pode ter: as outras 5 da equipe.
- **A regra está correta? Se não, qual deveria ser?:** ______


## 2. Os 19 casos da sua base que mudaram

Todos são da CCO, não têm SYSTUR e têm perfil em SICA RA ou SIGOT. Antes recebiam todas as funções da equipe; agora recebem só a função do perfil que têm. Para cada um: Consulta → busque a matrícula → aba Acessos, e compare com o “Depois”. As funções que saíram continuam visíveis em “Outras funções que a pessoa pode ter”, sem cobrança.


**34532401 — BRUNA OLIVEIRA FERREIRA DA SILVA** · SICA RA POS FATURAMENTO CONC → Pós Faturamento

- **Antes (pacote de 28/09):** Funções: Pos A Receber Comissão, Pós Faturamento, Pós Faturamento - Esfera, Pós Faturamento I, Pós Terrestre. Bloco “Acessos esperados”: SICA_ESFERA 3, SIG 5, SIGOT 2, SYSTUR 2. Pendências: nenhuma.
- **Depois (este pacote):** Função: Pós Faturamento. Bloco “Acessos esperados”: nenhum. Pendências: nenhuma.
- **Confere? Se não, o que deveria ser?:** 


**34532403 — MICHELE MARIANO DA SILVA** · SICA RA POS FAT TERRESTE CASH → Pós Faturamento Terreste_Cash

- **Antes (pacote de 28/09):** Funções: Pos A Receber Comissão, Pós Faturamento, Pós Faturamento - Esfera, Pós Faturamento I, Pós Faturamento Terreste_Cash, Pós Terrestre. Bloco “Acessos esperados”: SICA_ESFERA 3, SIG 5, SIGOT 2, SYSTUR 2. Pendências: nenhuma.
- **Depois (este pacote):** Função: Pós Faturamento Terreste_Cash. Bloco “Acessos esperados”: nenhum. Pendências: nenhuma.
- **Confere? Se não, o que deveria ser?:** 


**34532737 — ANA CAROLINE JARDIM BELLO** · SICA RA POS FAT ESFERA → Pós Faturamento - Esfera

- **Antes (pacote de 28/09):** Funções: Pos A Receber Comissão, Pós Faturamento, Pós Faturamento - Esfera, Pós Faturamento I, Pós Terrestre. Bloco “Acessos esperados”: SICA_ESFERA 3, SIG 5, SIGOT 2, SYSTUR 2. Pendências: nenhuma.
- **Depois (este pacote):** Função: Pós Faturamento - Esfera. Bloco “Acessos esperados”: SICA_ESFERA 1. Pendências: nenhuma.
- **Confere? Se não, o que deveria ser?:** 


**34532404 — PALOMA CAMPOREZE DE SOUZA** · SICA RA POS FATURAMENTO I → Pós Faturamento I

- **Antes (pacote de 28/09):** Funções: Pos A Receber Comissão, Pós Faturamento, Pós Faturamento - Esfera, Pós Faturamento I, Pós Terrestre. Bloco “Acessos esperados”: SICA_ESFERA 3, SIG 5, SIGOT 2, SYSTUR 2. Pendências: nenhuma.
- **Depois (este pacote):** Função: Pós Faturamento I. Bloco “Acessos esperados”: SICA_ESFERA 1. Pendências: nenhuma.
- **Confere? Se não, o que deveria ser?:** 


**34532734 — ALYNE VIANA SOUZA ROCHA** · SIGOT POSTERRESTRE → Pós Terrestre

- **Antes (pacote de 28/09):** Funções: Pos A Receber Comissão, Pós Faturamento, Pós Faturamento - Esfera, Pós Faturamento I, Pós Faturamento Terreste_Cash, Pós Terrestre. Bloco “Acessos esperados”: SICA_ESFERA 3, SICA_RA 5, SYSTUR 2. Pendências: nenhuma.
- **Depois (este pacote):** Função: Pós Terrestre. Bloco “Acessos esperados”: nenhum. Pendências: nenhuma.
- **Confere? Se não, o que deveria ser?:** 


**34532396 — JESSICA LOPES OLIVEIRA** · SIGOT POSTERRESTRE → Pós Terrestre

- **Antes (pacote de 28/09):** Funções: Pos A Receber Comissão, Pós Faturamento, Pós Faturamento - Esfera, Pós Faturamento I, Pós Faturamento Terreste_Cash, Pós Terrestre. Bloco “Acessos esperados”: SICA_ESFERA 3, SICA_RA 5, SYSTUR 2. Pendências: nenhuma.
- **Depois (este pacote):** Função: Pós Terrestre. Bloco “Acessos esperados”: nenhum. Pendências: nenhuma.
- **Confere? Se não, o que deveria ser?:** 


**34532735 — PALOMA ISABEL DA CUNHA QUEIROZ** · SIGOT POSTERRESTRE → Pós Terrestre

- **Antes (pacote de 28/09):** Funções: Pos A Receber Comissão, Pós Faturamento, Pós Faturamento - Esfera, Pós Faturamento I, Pós Faturamento Terreste_Cash, Pós Terrestre. Bloco “Acessos esperados”: SICA_ESFERA 3, SICA_RA 5, SYSTUR 2. Pendências: nenhuma.
- **Depois (este pacote):** Função: Pós Terrestre. Bloco “Acessos esperados”: nenhum. Pendências: nenhuma.
- **Confere? Se não, o que deveria ser?:** 


**34532321 — JESSICA LUZIA VASCO SIMOES** · SIGOT e SICA RA CP_BACKOFFICE → CP BACKOFFICE

- **Antes (pacote de 28/09):** Funções: CP BACKOFFICE, Carros e Hoteis, Coordenação Suporte + Carro e Hotéis, Internacional, Não Operacional, Suporte N1, Suporte N2. Bloco “Acessos esperados”: SICA_ESFERA 2, SICA_RA 4, SYSTUR 6. Pendências: SIG 1.
- **Depois (este pacote):** Função: CP BACKOFFICE. Bloco “Acessos esperados”: SICA_ESFERA 1, SICA_RA 1. Pendências: nenhuma.
- **Confere? Se não, o que deveria ser?:** 


**90000054 — ADRIANA MARQUES DE SOUZA SOARES** · SIGOT e SICA RA CP_BACKOFFICE → CP BACKOFFICE

- **Antes (pacote de 28/09):** Funções: CP BACKOFFICE, Carros e Hoteis, Coordenação Suporte + Carro e Hotéis, Internacional, Não Operacional, Suporte N1, Suporte N2. Bloco “Acessos esperados”: SICA_ESFERA 2, SICA_RA 4, SYSTUR 6. Pendências: SIG 1.
- **Depois (este pacote):** Função: CP BACKOFFICE. Bloco “Acessos esperados”: SICA_ESFERA 1, SICA_RA 1. Pendências: nenhuma.
- **Confere? Se não, o que deveria ser?:** 


**12698 — ERICKA CRISTINA REIS** · SIGOT Carros_Hoteis_CP → Carros e Hoteis

- **Antes (pacote de 28/09):** Funções: CP BACKOFFICE, Carros e Hoteis, Coordenação Suporte + Carro e Hotéis, Internacional, Não Operacional, Suporte N1, Suporte N2. Bloco “Acessos esperados”: SICA_ESFERA 2, SICA_RA 4, SYSTUR 6. Pendências: SIG 1.
- **Depois (este pacote):** Função: Carros e Hoteis. Bloco “Acessos esperados”: SICA_ESFERA 1, SICA_RA 1, SYSTUR 1. Pendências: nenhuma.
- **Confere? Se não, o que deveria ser?:** 


**15161 — JESSICA MACHADO DOS REIS** · SIGOT Carros_Hoteis_CP → Carros e Hoteis

- **Antes (pacote de 28/09):** Funções: CP BACKOFFICE, Carros e Hoteis, Coordenação Suporte + Carro e Hotéis, Internacional, Não Operacional, Suporte N1, Suporte N2. Bloco “Acessos esperados”: SICA_ESFERA 2, SICA_RA 4, SYSTUR 6. Pendências: SIG 1.
- **Depois (este pacote):** Função: Carros e Hoteis. Bloco “Acessos esperados”: SICA_ESFERA 1, SICA_RA 1, SYSTUR 1. Pendências: nenhuma.
- **Confere? Se não, o que deveria ser?:** 


**34532590 — NATALI ALMEIDA DE OLIVEIRA** · SIGOT Carros_Hoteis_CP → Carros e Hoteis

- **Antes (pacote de 28/09):** Funções: CP BACKOFFICE, Carros e Hoteis, Coordenação Suporte + Carro e Hotéis, Internacional, Não Operacional, Suporte N1, Suporte N2. Bloco “Acessos esperados”: SICA_ESFERA 2, SICA_RA 4, SYSTUR 6. Pendências: SIG 1.
- **Depois (este pacote):** Função: Carros e Hoteis. Bloco “Acessos esperados”: SICA_ESFERA 1, SICA_RA 1, SYSTUR 1. Pendências: nenhuma.
- **Confere? Se não, o que deveria ser?:** 


**90000066 — CILENE DO NASCIMENTO CRUZ** · SIGOT Carros_Hoteis_CP → Carros e Hoteis

- **Antes (pacote de 28/09):** Funções: CP BACKOFFICE, Carros e Hoteis, Coordenação Suporte + Carro e Hotéis, Internacional, Não Operacional, Suporte N1, Suporte N2. Bloco “Acessos esperados”: SICA_ESFERA 2, SICA_RA 4, SYSTUR 6. Pendências: SIG 1.
- **Depois (este pacote):** Função: Carros e Hoteis. Bloco “Acessos esperados”: SICA_ESFERA 1, SICA_RA 1, SYSTUR 1. Pendências: nenhuma.
- **Confere? Se não, o que deveria ser?:** 


**33057 — WAGNER NOVAES FAGUNDES** · SIGOT Carros_Hoteis_CP → Carros e Hoteis

- **Antes (pacote de 28/09):** Funções: CP BACKOFFICE, Carros e Hoteis, Coordenação Suporte + Carro e Hotéis, Internacional, Não Operacional, Suporte N1, Suporte N2. Bloco “Acessos esperados”: SICA_ESFERA 2, SICA_RA 4, SYSTUR 6. Pendências: SIG 1.
- **Depois (este pacote):** Função: Carros e Hoteis. Bloco “Acessos esperados”: SICA_ESFERA 1, SICA_RA 1, SYSTUR 1. Pendências: nenhuma.
- **Confere? Se não, o que deveria ser?:** 


**34532095 — KATHELIN LOPES CORREA** · SIGOT Internacional_CP → Internacional

- **Antes (pacote de 28/09):** Funções: CP BACKOFFICE, Carros e Hoteis, Coordenação Suporte + Carro e Hotéis, Internacional, Não Operacional, PÓS FATURAMENTO, Suporte N1, Suporte N2. Bloco “Acessos esperados”: SICA_ESFERA 2, SICA_RA 4, SYSTUR 6. Pendências: SIG 8.
- **Depois (este pacote):** Função: Internacional. Bloco “Acessos esperados”: SYSTUR 1. Pendências: SIG 1.
- **Confere? Se não, o que deveria ser?:** 


**34532254 — JESSICA ALVES MUNHOZ** · SIGOT PGTOS_NACIONAIS_CP_I → Pagamentos Nacionais I

- **Antes (pacote de 28/09):** Funções: Adiantamento + Conciliação bancária, Adiantamentos a fornecedores N2, Baixa Adiantamentos a fornecedores N1, Contas a Pagar I, Pagamentos Internacionais, Pagamentos Nacionais, Pagamentos Nacionais I, Suporte ao Caixa. Bloco “Acessos esperados”: SYSTUR 8. Pendências: SIG 1.
- **Depois (este pacote):** Função: Pagamentos Nacionais I. Bloco “Acessos esperados”: SYSTUR 1. Pendências: nenhuma.
- **Confere? Se não, o que deveria ser?:** 


**90000177 — HALANA TAROSSI NASCIMENTO** · SIGOT Atd_For_TREND_N2 → Atendimento a fornecedores TREND N2

- **Antes (pacote de 28/09):** Funções: Atendimento a fornecedores, Atendimento a fornecedores  CVC e VISUAL, Atendimento a fornecedores  TREND, Atendimento a fornecedores  TREND I, Atendimento a fornecedores TREND N2, Atendimento ao Fornecedor - Carros, Atendimento ao Fornecedor C&H. Bloco “Acessos esperados”: SYSTUR 6. Pendências: nenhuma.
- **Depois (este pacote):** Função: Atendimento a fornecedores TREND N2. Bloco “Acessos esperados”: SYSTUR 1. Pendências: nenhuma.
- **Confere? Se não, o que deveria ser?:** 


**90001090 — WELLINGTON RODRIGUES DE OLIVEIRA** · SIGOT SupFin → Sup Financeiro

- **Antes (pacote de 28/09):** Funções: Atendimento Backoffice - N2, Sup Financeiro, Sup Financeiro - Caixa. Bloco “Acessos esperados”: SYSTUR 3. Pendências: nenhuma.
- **Depois (este pacote):** Função: Sup Financeiro. Bloco “Acessos esperados”: nenhum. Pendências: nenhuma.
- **Confere? Se não, o que deveria ser?:** 


**34531885 — CAROLINE AGUILAR DE OLIVEIRA** · SIGOT SupFin → Sup Financeiro

- **Antes (pacote de 28/09):** Funções: Atendimento Backoffice - N2, Sup Financeiro, Sup Financeiro - Caixa. Bloco “Acessos esperados”: SYSTUR 3. Pendências: nenhuma.
- **Depois (este pacote):** Função: Sup Financeiro. Bloco “Acessos esperados”: nenhum. Pendências: nenhuma.
- **Confere? Se não, o que deveria ser?:** 

**Destaques**

- ERICKA CRISTINA REIS (12698): no ajuste de 28/09 ela continuou em análise porque tinha 3 dos 8 perfis de SIG previstos. Os 8 eram a soma de duas funções. Com a função certa (Carros e Hoteis), os 3 que ela tem são exatamente os previstos e o SIG fica aderente.
- KATHELIN LOPES CORREA (34532095): das 8 pendências sobra 1 — o SIG COM_INFORMATIVOS, que a função Internacional não prevê (“acesso fora da função”).
- BRUNA OLIVEIRA, MICHELE, ANA CAROLINE, PALOMA CAMPOREZE, ALYNE, JESSICA LOPES e PALOMA ISABEL são da mesma equipe (01.06.02.01): cada uma fica com a sua função de Pós Faturamento / Pós Terrestre.


## 3. O que vai parecer diferente

- O total de linhas cai de 13.446 para 13.114: são os esperados de outras funções que essas 19 pessoas recebiam.
- As pendências caem de 1.072 para 1.064 pessoas (de 1.123 para 1.108 linhas). Nas 19 pessoas, de 16 linhas para 1.
- Nenhuma outra pessoa muda: quem tem SYSTUR já tinha a função definida, e quem não é da CCO não passa por esta regra.


## 4. Uma pergunta para você

No bloco “Sem mapeamento”, os sistemas que a função da pessoa não prevê aparecem com o texto “sem perfil previsto para o cargo/centro de custo”. Para quem é da CCO, prefere que diga “a função da pessoa não prevê acesso a este sistema”?

Sua resposta: ______________________________________________
