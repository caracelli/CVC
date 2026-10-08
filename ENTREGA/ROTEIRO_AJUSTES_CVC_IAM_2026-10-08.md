# CVC IAM Analytics
## Roteiro de validação — seu documento de 07/10
08/10/2026

**Por que este documento existe**

Ele responde o seu documento de 07/10 (Aplicação_CVC_07_10) e explica o que encontramos na base da rede. Parte dos casos que você apontou (CLAUDIA, franqueados em espelho) não era regra: eram arquivos que não chegaram a ser processados na rede. Isso está no item 1.


## 1. O que aconteceu na rede

No dia 06/10, às 13:37, rodou na rede uma versão ANTIGA do Processador (de junho), de alguma instalação velha que ainda aponta para a rede. Ela durou um minuto, mas mandou para DADOS\ERROS o extrato do SYSTUR de 06/10 e a matriz de lojas (franqueados), e parou com erro. As execuções seguintes, com a versão correta, terminaram — mas sem esses dois arquivos. Além disso, a matriz da CCO enviada em 05/10 veio sem a linha de título e era rejeitada pelo programa; isso foi corrigido nesta versão.

- Sem a matriz nova da CCO, quem é da CCO e mudou de gestor (como a CLAUDIA) ficava fora da CCO e caía na matriz do cargo.
- Sem a matriz de lojas, os franqueados eram comparados pelo espelho.
- Recomendação: apagar instalações antigas do programa nas máquinas que acessam a rede.


## 2. Os ajustes desta versão


### ★ 2.1 Oracle: o Relatório de Despesas é desconsiderado

- **O que decide:** Se o perfil CVC OIE BRASIL - RELATÓRIO DE DESPESAS conta na validação do Oracle.
- **Critério:** Seu pedido: desconsiderar o perfil. Ele sai inteiro da validação: não é mais “a mais”, nem “não pode ter e tem”, nem “mais de um perfil”. O extrato continua igual.
- **Como conferir:** Consulta → GILDA TAVARES DA SILVA (34530435) e LETICIA THAIS SABIAO SOUZA (9130) → Oracle EBS.
- **Deve mostrar (vale em qualquer base):** GILDA: Oracle aderente (o único “a mais” era o Relatório). LETICIA: sem linha de Oracle. Na rede: 377 acessos desconsiderados; as pendências de Oracle dos funcionários caem de 350 para 1.
- **A regra está correta? Se não, qual deveria ser?:** ______


### ★ 2.2 A matriz da CCO volta a ser lida

- **O que decide:** Se a matriz da CCO sem linha de título é aceita.
- **Critério:** A matriz de 05/10 tem o cabeçalho na primeira linha; a anterior tinha um título antes. O programa agora aceita as duas.
- **Como conferir:** Consulta → CLAUDIA DA LUZ SALIDO RIVERO (90001433).
- **Deve mostrar (vale em qualquer base):** SYSTUR, SIG e SIGOT aderentes pela CCO (gestora HELEN ANTONIA LA SPINA RUAS) — sem TESOURARIA/CUSTOS e sem pendência. Na rede: as pendências de SYSTUR dos funcionários caem de 211 para 48.
- **A regra está correta? Se não, qual deveria ser?:** ______


### ★ 2.3 Franqueados: matriz de lojas, não espelho

- **O que decide:** Como os franqueados são validados no SYSTUR.
- **Critério:** Seu pedido: usar a matriz do SYSTUR de lojas. Ela passou a ser lida. Agora cada franqueado é comparado com o que a matriz prevê para o cargo, o tipo de atendimento e o tipo de loja.
- **Como conferir:** Aba Pendências → filtre Categoria = Franqueado.
- **Deve mostrar (vale em qualquer base):** Origem “Matriz franqueado” em vez de “Espelho — franqueados”. Na rede: 4.855 linhas pela matriz (eram 774 pelo espelho) e 522 franqueados com pendência — 317 com perfil que o cargo não autoriza (ex.: Atendente com perfil de Supervisor) e 192 com perfil que a matriz só libera com aprovação da Governança (ex.: Gerente com FRANQUEADOS_VC). Ver a pergunta 4.1.
- **A regra está correta? Se não, qual deveria ser?:** ______


### 2.4 Transferidos sem linhas repetidas

- **O que decide:** Como a aba Transferidos mostra os sistemas de quem é da CCO.
- **Critério:** A planilha da CCO escreve “Sigot”, “Systur”, “Oracle EBS”; os acessos usam SIGOT, SYSTUR, ORACLE_EBS. O mesmo sistema saía em duas linhas, e o que a CCO prevê nunca casava com o que a pessoa tem (falta e sobrou falsos). Os nomes agora são unificados.
- **Como conferir:** Aba Transferidos → ELAINE ALVES MELKUNAS (33082).
- **Deve mostrar (vale em qualquer base):** Uma linha por sistema; SIGOT e SYSTUR com “tem”, sem as linhas “Sigot” e “Systur” de inclusão.
- **A regra está correta? Se não, qual deveria ser?:** ______


### 2.5 Quarentena com motivo

- **O que decide:** O que se informa ao enviar para quarentena.
- **Critério:** Seu pedido: um campo Motivo com Exceção, Férias/Cobertura de férias e Usuário sistêmico. É obrigatório; o texto livre virou “Detalhe (opcional)”.
- **Como conferir:** Qualquer pendência → Enviar para quarentena.
- **Deve mostrar (vale em qualquer base):** Campo Motivo com as 3 opções; sem escolher, a quarentena não é enviada. No histórico aparece “Opção — detalhe”.
- **A regra está correta? Se não, qual deveria ser?:** ______


## 3. Respostas às suas perguntas

**ALEXANDRA RODRIGUES DE LIMA DIAS (90000266) — de onde vem o 2º perfil**

Vem do login SIST00207, que no SYSTUR tem o nome “VISUAL TURISMO” e outro CPF, mas está cadastrado com o e-mail dela (alexandra.dias@cvccorp.com.br). O programa liga a conta à pessoa pelo e-mail — por isso não aparece quando o extrato é filtrado pelo nome dela. Ver a pergunta 4.2.

**Tratado, mas não regularizado: volta a apontar?**

Volta. Se, no processamento seguinte, o acesso continua divergente, a pendência reaparece marcada como REABERTA (como no seu primeiro print).

**Pode ter e não tem / tem e não pode ter**

É a regra aplicada: o que a matriz prevê e a pessoa não tem aparece em “Acessos esperados” (não é pendência); o que a pessoa tem e não pode ter é pendência. O caso da GILDA era o Relatório de Despesas (item 2.1).

**Dá para simular cenários (quarentena vencendo, transferido tratado errado, base manipulada)?**

Dá. Montamos bases de teste com esses cenários e mostramos o resultado antes de cada entrega.


## 4. Perguntas para você


### 4.1 Franqueados com perfil que só a Governança libera

Na matriz de lojas, a coluna ACESSO MANUAL = SIM marca perfis que só podem ser liberados com aprovação. Hoje isso vira pendência (192 franqueados). Deve continuar como pendência, ou ser só informativo?

Sua resposta: ______________________________________________


### 4.2 Conta genérica cadastrada com o e-mail de uma pessoa

Caso da ALEXANDRA: a conta “VISUAL TURISMO” (outro CPF) usa o e-mail dela e foi ligada a ela. Deve continuar ligada à pessoa, ou contas com CPF diferente não devem ser ligadas pelo e-mail? (Ou tratar como usuário sistêmico na quarentena.)

Sua resposta: ______________________________________________


### 4.3 Itens do seu documento que precisam de conversa

Transferidos (não pendente enquanto em transferidos, data da identificação, volta à fila depois do tratamento); “deixar apenas em tratativa do analista” na resolução; escolher qual pendência está sendo tratada; CCO com perfis de funções diferentes. Podemos marcar uma conversa para fechar esses pontos?

Sua resposta: ______________________________________________
