# CVC IAM Analytics
## Roteiro de validação — seu documento de 01/10 (versão 2)
01/10/2026

**Por que este documento existe**

Ele responde os dois pontos do seu documento de 01/10 (ajuste_01_10) — o SYSTUR de quem é da CCO e a extração em Excel — e a sua resposta sobre o Oracle não previsto. Traz o antes e o depois de cada caso para você conferir.

> Este pacote substitui os de 29/09 e 01/10 e já inclui todos os ajustes deles. Ele traz a pasta DADOS com o banco processado: você NÃO precisa rodar o Processador.


## Antes de tudo: o que fazer, nesta ordem

- 1. Feche o painel e o Processador, se estiverem abertos.
- 2. BACKUP (obrigatório): copie as pastas DADOS\BANCO e INTERACOES para outro lugar. Se algo não sair como esperado, é só devolvê-las.
- 3. Extraia o pacote na pasta principal da instalação — a que contém DADOS, ENTRADA e EXECUTAVEIS — e aceite substituir os arquivos.
- 4. NÃO apague nem mexa na pasta INTERACOES: é onde ficam as suas tratativas, e o painel as lê ao vivo.
- 5. Abra o visualizador.exe.


## 1. CCO é uma regra à parte


### ★ 1 Quem é da CCO segue só o que a CCO prevê

- **O que decide:** O que vale para quem é da CCO: a CCO ou a matriz do cargo.
- **Critério:** Como combinamos: o que está na CCO é o que a pessoa pode ter. Quem é da CCO não recebe nada da matriz por cargo nem passa pela regra Oracle × SYSTUR. Os perfis que a função prevê não contam como “mais de um perfil” — a pessoa pode ter dois ou mais, se estiverem na função. É da CCO quem está no centro de custo + gestor da CCO e tem perfil (SYSTUR, SICA RA, SICA ESFERA ou SIGOT) de uma função dessa equipe — ou não tem perfil nenhum nesses sistemas. Assim os vice-presidentes da Presidência, que dividem o centro de custo com o diretor da CCO, continuam pela matriz do cargo.
- **Como conferir:** Consulta → ANA PAULA DE OLIVEIRA CARDAMONE (90001406) → aba Acessos. ANTES: SYSTUR em “Necessário análise” com “Usuário com mais de um perfil (2)” e “Esperado: 1 de 2 opções: CUSTOS, TESOURARIA”; a função A Receber 1 Comissão sem o SYSTUR.
- **Deve mostrar (vale em qualquer base):** DEPOIS: SYSTUR em “Acessos encontrados”, em verde, com GRP_COMISSOES_IMPORTACAO_ARQUIVOS e A_RECEBER_1_COMISSAO, sem alerta. Em “Funções previstas”, A Receber 1 Comissão — “tem 9 de 11”, com o SYSTUR dentro (faltam SICA ESFERA e SICA RA). Na base: 16 pessoas saem de pendência no SYSTUR.
- **A regra está correta? Se não, qual deveria ser?:** ______

**Os 16 casos que mudaram**


**14389 — TATIANE DA SILVA LEMES   ·   função N2 - Financeiro**

- **Antes (pacote de 29/09):** SYSTUR em análise por “mais de um perfil”: tem PARAMETROS_DE_CAIXA, N2_FINANCEIRO, os dois previstos pela função.
- **Depois (este pacote):** SYSTUR aderente pela função N2 - Financeiro, sem o alerta.
- **Confere? Se não, o que deveria ser?:** 


**15250 — ADRIANNE RODRIGUES   ·   função Marítimo,Associação e Conciliação de bilhetes a recibos - B2C I**

- **Antes (pacote de 29/09):** SYSTUR em análise por “mais de um perfil”: tem GRP_COMISSOES_IMPORTACAO_ARQUIVOS, MARITIMO_CONC, os dois previstos pela função.
- **Depois (este pacote):** SYSTUR aderente pela função Marítimo,Associação e Conciliação de bilhetes a recibos - B2C I, sem o alerta.
- **Confere? Se não, o que deveria ser?:** 


**2061 — ANDREIA REIS TEIXEIRA   ·   função Marítimo,Associação e Conciliação de bilhetes a recibos - B2C I**

- **Antes (pacote de 29/09):** SYSTUR em análise por “mais de um perfil”: tem GRP_COMISSOES_IMPORTACAO_ARQUIVOS, MARITIMO_CONC, os dois previstos pela função.
- **Depois (este pacote):** SYSTUR aderente pela função Marítimo,Associação e Conciliação de bilhetes a recibos - B2C I, sem o alerta.
- **Confere? Se não, o que deveria ser?:** 


**23217 — ROBERTO FERREIRA DOS SANTOS   ·   função Sup Financeiro - Caixa**

- **Antes (pacote de 29/09):** SYSTUR em análise por “mais de um perfil”: tem PARAMETROS_DE_CAIXA, CCO_SUPORTE_DE_CAIXA_SUP_FIN, os dois previstos pela função.
- **Depois (este pacote):** SYSTUR aderente pela função Sup Financeiro - Caixa, sem o alerta.
- **Confere? Se não, o que deveria ser?:** 


**2324 — SEBASTIAO CLAUDIO DE ANDRADE   ·   função Marítimo,Associação e Conciliação de bilhetes a recibos - B2C I**

- **Antes (pacote de 29/09):** SYSTUR em análise por “mais de um perfil”: tem GRP_COMISSOES_IMPORTACAO_ARQUIVOS, ASS_CONC_BILHETES_RECIBOS_B2C_I, os dois previstos pela função.
- **Depois (este pacote):** SYSTUR aderente pela função Marítimo,Associação e Conciliação de bilhetes a recibos - B2C I, sem o alerta.
- **Confere? Se não, o que deveria ser?:** 


**32446 — GRAZIELLI CARRILHO ANDRADE   ·   função Gerencia Operações**

- **Antes (pacote de 29/09):** SYSTUR em análise por “mais de um perfil”: tem GRP_COVID_VOADO_NAO_REMOVER, GER_OPER, os dois previstos pela função.
- **Depois (este pacote):** SYSTUR aderente pela função Gerencia Operações, sem o alerta.
- **Confere? Se não, o que deveria ser?:** 


**34531737 — THAYS MORAES PEREIRA DA SILVA   ·   função Apoio Canais criticos**

- **Antes (pacote de 29/09):** SYSTUR em análise por “mais de um perfil”: tem APOIO_CCRITICOS, CANAIS_CRITICOS, os dois previstos pela função.
- **Depois (este pacote):** SYSTUR aderente pela função Apoio Canais criticos, sem o alerta.
- **Confere? Se não, o que deveria ser?:** 


**34532400 — KATIA SUELI VIEIRA DIAS   ·   função A Receber 1 Comissão**

- **Antes (pacote de 29/09):** SYSTUR em análise por “mais de um perfil”: tem GRP_COMISSOES_IMPORTACAO_ARQUIVOS, A_RECEBER_1_COMISSAO, os dois previstos pela função.
- **Depois (este pacote):** SYSTUR aderente pela função A Receber 1 Comissão, sem o alerta.
- **Confere? Se não, o que deveria ser?:** 


**6506 — CRISTIANE VARELA GOMES   ·   função SUPERVISÃO**

- **Antes (pacote de 29/09):** SYSTUR em análise por “mais de um perfil”: tem CANAIS_CRITICOS, SUPERV_OPER_CCRITICOS, os dois previstos pela função.
- **Depois (este pacote):** SYSTUR aderente pela função SUPERVISÃO, sem o alerta.
- **Confere? Se não, o que deveria ser?:** 


**7496 — MIRIAM ARAUJO DE MOURA   ·   função Marítimo,Associação e Conciliação de bilhetes a recibos - B2C I**

- **Antes (pacote de 29/09):** SYSTUR em análise por “mais de um perfil”: tem GRP_COMISSOES_IMPORTACAO_ARQUIVOS, ASS_CONC_BILHETES_RECIBOS_B2C_I, os dois previstos pela função.
- **Depois (este pacote):** SYSTUR aderente pela função Marítimo,Associação e Conciliação de bilhetes a recibos - B2C I, sem o alerta.
- **Confere? Se não, o que deveria ser?:** 


**7530 — ADILSON LUIS BRUGNARO   ·   função Marítimo,Associação e Conciliação de bilhetes a recibos - B2C I**

- **Antes (pacote de 29/09):** SYSTUR em análise por “mais de um perfil”: tem GRP_COMISSOES_IMPORTACAO_ARQUIVOS, ASS_CONC_BILHETES_RECIBOS_B2C_I, os dois previstos pela função.
- **Depois (este pacote):** SYSTUR aderente pela função Marítimo,Associação e Conciliação de bilhetes a recibos - B2C I, sem o alerta.
- **Confere? Se não, o que deveria ser?:** 


**90001050 — MARCIO ALENCAR CARVALHO   ·   função Marítimo,Associação e Conciliação de bilhetes a recibos - B2C I**

- **Antes (pacote de 29/09):** SYSTUR em análise por “mais de um perfil”: tem GRP_COMISSOES_IMPORTACAO_ARQUIVOS, ASS_CONC_BILHETES_RECIBOS_B2C_I, os dois previstos pela função.
- **Depois (este pacote):** SYSTUR aderente pela função Marítimo,Associação e Conciliação de bilhetes a recibos - B2C I, sem o alerta.
- **Confere? Se não, o que deveria ser?:** 


**90001187 — MARIA EDUARDA CRESPO FARIAS   ·   função A Receber 1 Comissão**

- **Antes (pacote de 29/09):** SYSTUR em análise por “mais de um perfil”: tem GRP_COMISSOES_IMPORTACAO_ARQUIVOS, A_RECEBER_1_COMISSAO, os dois previstos pela função.
- **Depois (este pacote):** SYSTUR aderente pela função A Receber 1 Comissão, sem o alerta.
- **Confere? Se não, o que deveria ser?:** 


**90001406 — ANA PAULA DE OLIVEIRA CARDAMONE   ·   função A Receber 1 Comissão**

- **Antes (pacote de 29/09):** SYSTUR em análise: a matriz do cargo pedia CUSTOS ou TESOURARIA; tem GRP_COMISSOES_IMPORTACAO_ARQUIVOS, A_RECEBER_1_COMISSAO.
- **Depois (este pacote):** SYSTUR aderente pela função A Receber 1 Comissão, sem o alerta.
- **Confere? Se não, o que deveria ser?:** 


**90001433 — CLAUDIA DA LUZ SALIDO RIVERO   ·   função Atendimento a fornecedores TREND N2**

- **Antes (pacote de 29/09):** SYSTUR em análise: a matriz do cargo pedia CUSTOS ou TESOURARIA; tem ATD_FOR_TREND_N2.
- **Depois (este pacote):** SYSTUR aderente pela função Atendimento a fornecedores TREND N2, sem o alerta.
- **Confere? Se não, o que deveria ser?:** 


**9910 — ALINE DA SILVA NASCIMENTO OLIVARES   ·   função A Receber 1 Comissão**

- **Antes (pacote de 29/09):** SYSTUR em análise por “mais de um perfil”: tem GRP_COMISSOES_IMPORTACAO_ARQUIVOS, A_RECEBER_1_COMISSAO, os dois previstos pela função.
- **Depois (este pacote):** SYSTUR aderente pela função A Receber 1 Comissão, sem o alerta.
- **Confere? Se não, o que deveria ser?:** 

**Dois casos que mudam de motivo**

ELAINE ALVES MELKUNAS (33082) e SILMAR PERPETUO DA SILVA (34530333) estão no centro de custo + gestor de uma equipe da CCO, mas os perfis delas são de função de outra equipe. Por isso não contam como CCO dessa equipe e seguem a regra geral: continuam pendentes, agora como “tem acesso sem previsão” em vez de “acesso fora da função”.


## 2. A planilha da Consulta igual à tela


### ★ 2 Pendências e Status da planilha = os do painel

- **O que decide:** O que sai nas colunas Pendências e Status ao exportar a Consulta.
- **Critério:** A planilha contava de outro jeito: “Pendências” levava o total de linhas da pessoa e “Status” chamava de pendente o que é só “incluir acesso” e de aderente o que é “sem mapeamento”. Agora usa a mesma regra da tela, na linha da pessoa e na de cada sistema. Conferido na base inteira: 7.433 pessoas, nenhuma diferença entre planilha e tela. A exportação da aba Pendências continua trazendo só o que é pendência — e nenhuma pendência fica de fora dela.
- **Como conferir:** Consulta → LETICIA THAIS SABIAO SOUZA (9130) → Exportar Excel → Analítico. ANTES: SICA_RA “1 pendente” e ORACLE_EBS “Aderente”, com a tela dizendo Pendências 0.
- **Deve mostrar (vale em qualquer base):** DEPOIS: pessoa com Pendências 0 e “Incluir acessos”; ORACLE_EBS “Sem mapeamento” (CVC OIE BRASIL - Relatório de Despesas); SICA_RA “Incluir acessos” (SVA PRODUTOS); SYSTUR “Aderente”.
- **A regra está correta? Se não, qual deveria ser?:** ______


## 3. Oracle não previsto para o cargo vira pendência


### ★ 3 Acesso que a matriz não prevê entra na fila, uma linha por divergência

- **O que decide:** O que acontece com o Oracle que a pessoa tem, mas que a matriz não prevê para o cargo dela.
- **Critério:** Sua resposta: “ele vem na pendência por ter um perfil não mapeado para ela”. Até aqui esse Oracle era só informativo (“sem mapeamento”, como combinado em 23/09). Agora é pendência em análise — o mesmo “não pode ter acesso e tem” dos outros sistemas — e vai para a aba Pendências e para a planilha. A planilha de Pendências ganhou a coluna Sistema: quem tem o Oracle não previsto e uma divergência no SIG sai em duas linhas, e cada uma diz de qual sistema é.
- **Como conferir:** Consulta → LETICIA THAIS SABIAO SOUZA (9130). ANTES: Oracle em “Sem mapeamento”, status “Incluir acessos”, fora da planilha de Pendências. Depois, aba Pendências → Exportar Excel.
- **Deve mostrar (vale em qualquer base):** DEPOIS: Oracle em “Necessário análise” — “Tem hoje: CVC OIE BRASIL - Relatório de Despesas” —, status “1 pendente”. Na planilha: LETICIA em 1 linha (Sistema ORACLE_EBS); ARIANE CIRILLI DA SILVA (5135) em 2 linhas (SIG e ORACLE_EBS). Na base: 282 pessoas com esse Oracle (276 só com o Relatório de Despesas); 94 delas entram na fila pela primeira vez.
- **A regra está correta? Se não, qual deveria ser?:** ______


## 4. O que vai parecer diferente

- As pendências passam de 1.064 para 1.142 pessoas (de 1.108 para 1.371 linhas), comparando com o pacote de 29/09: caem 16 pessoas com o SYSTUR da CCO (item 1) e entram as 94 do Oracle não previsto (item 3).
- A planilha da Consulta não muda nenhum número da tela: ela passa a repetir o que a tela já mostrava (item 2).


## 5. Suas respostas de 01/10

A usuária do ponto da extração é a LETICIA THAIS SABIAO SOUZA (9130), e o Oracle que a matriz não prevê para o cargo passa a ser pendência — aplicado no item 3.
