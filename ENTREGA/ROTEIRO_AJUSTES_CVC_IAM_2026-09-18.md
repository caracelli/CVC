# CVC IAM Analytics
## Roteiro de validação — o que você pediu em 17 e 18/09
18/09/2026

**Por que este documento existe**

Ele responde, um a um, os quatro pontos do seu documento de 17/09 e o pedido do contador de registros que você mandou em 18/09. No fim há quatro perguntas — são decisões suas, e a aplicação segue como está até você responder.

**Como usar**

Igual aos roteiros de 08/09 e 11/09: cada ajuste tem “Como conferir” e o valor esperado, e a última linha pergunta se a regra está CERTA. As marcadas com ★ são as que mais aparecem na tela.

> Se o pacote que você recebeu tiver a pasta DADOS, o banco já vai processado e você NÃO precisa rodar o Processador. Se ele tiver só EXECUTAVEIS, rode o Processador UMA vez depois de copiar: o item 1 (funções) e os acessos a incluir dependem dessa rodada.


## Antes de tudo: o que fazer, nesta ordem

- 1. Feche o painel e o Processador, se estiverem abertos.
- 2. BACKUP (obrigatório): copie as pastas DADOS\BANCO e INTERACOES para outro lugar. Se algo não sair como esperado, é só devolvê-las.
- 3. Extraia o pacote na pasta principal da instalação — a que contém DADOS, ENTRADA e EXECUTAVEIS — e aceite substituir os arquivos.
- 4. NÃO apague nem mexa na pasta INTERACOES: é onde ficam as suas tratativas, e o painel as lê ao vivo.
- 5. Se o pacote NÃO trouxer a pasta DADOS, rode o Processador.exe uma vez e espere terminar (alguns minutos; não feche a janela no meio).
- 6. Abra o visualizador.exe.


## 1. O que você pediu em 17/09 e 18/09


### ★ 1.1 Funções do Mapeamento CCO, com abrir e fechar

- **O que decide:** De onde vem o acesso esperado da pessoa: matriz por cargo ou Mapeamento CCO (centro de custo + gestor).
- **Critério:** Quando o esperado vem do CCO, a aplicação passa a guardar também a FUNÇÃO daquele acesso. Na Consulta, abaixo dos blocos de acessos, aparece a lista “Funções previstas”, recolhida. Cada função abre no “+” e mostra os acessos que a formam, com sistema, perfil e se a pessoa tem ou falta. As funções com algo faltando vêm primeiro; a que está completa aparece marcada.
- **Como conferir:** Consulta → busque uma pessoa do centro de custo 01.06.04.01 (por exemplo BRENDA SILVA BRITO) → “ver detalhe” → role até “Funções previstas”.
- **Medido na sua base (a de 15/09, reprocessada aqui com esta versão):** 7 funções. Ao abrir “Atendimento a fornecedores  CVC e VISUAL”: “tem 1 de 5” — SYSTUR ATD_FOR_CVC_VISUAL_CP (tem) e os quatro CVC AP … Consulta do Oracle EBS (faltam).
- **A regra está correta? Se não, qual deveria ser?:** ______


### ★ 1.2 Quem não tem mapeamento deixa de aparecer como “Aderente”

- **O que decide:** O status que a Consulta mostra para quem a matriz não prevê nada.
- **Critério:** Aderência é por SISTEMA. Quem não tem nenhum acesso aderente passa a aparecer como “Sem perfis mapeados”, em cinza, e não mais como “Aderente”. Quem é aderente em um sistema continua “Aderente”, mesmo sem mapeamento nos outros. Continua sendo informativo: não entra em Pendências nem nos cards.
- **Como conferir:** Consulta → coluna Status. Procure alguém com “sem mapeamento” no detalhe (o seu exemplo era PAULO HENRIQUE FICUCHIELLO).
- **Medido na sua base (a de 15/09, reprocessada aqui com esta versão):** Status “Sem perfis mapeados”: 589 linhas assim, sendo 539 pessoas que só têm essa linha.
- **A regra está correta? Se não, qual deveria ser?:** ______


### ★ 1.3 Aviso de mais de um perfil no SYSTUR

- **O que decide:** Quantos perfis a pessoa tem no mesmo sistema.
- **Critério:** No SYSTUR, quando a pessoa tem mais de um perfil, a Consulta mostra o aviso “Usuário com mais de um acesso”. É um aviso: não vira pendência, seguindo o que já valia para perfil a mais (a cobrança depende de uma configuração, hoje desligada). Vale só para o SYSTUR — no SIG, ter vários perfis é o normal.
- **Como conferir:** Consulta → busque THAIANE TAVARES SILVA DE PAULA (matrícula 14510) ou ADRIANA TATEISHI (1243) → “ver detalhe”.
- **Medido na sua base (a de 15/09, reprocessada aqui com esta versão):** O aviso aparece acima dos perfis. São 68 pessoas com mais de um perfil no SYSTUR: 62 com dois, 1 com três e 5 com 42.
- **A regra está correta? Se não, qual deveria ser?:** ______


### ★ 1.4 Transferidos: o que tem, o que deveria ter, o que alterar

- **O que decide:** A leitura da aba Transferidos e da planilha exportada.
- **Critério:** Ao abrir a pessoa, o detalhe passa a ter três blocos: 1) os acessos que ela tem; 2) os que deveria ter na nova área; 3) o que precisa alterar, separando REVOGAR (sobrou da área anterior) de INCLUIR (a nova equipe tem e ela não), com a função de cada acesso. Quando não há diferença, aparece “Validado: os acessos da nova área já estão aderentes”. A planilha ganhou as colunas “Situação do acesso” e “Função (CCO)” e agora também traz as linhas do que falta incluir. As colunas antigas não mudaram de lugar.
- **Como conferir:** Transferidos → abra uma pessoa no “+” → veja os três blocos. Depois clique em Exportar Excel e confira as duas colunas novas, no fim da planilha.
- **Medido na sua base (a de 15/09, reprocessada aqui com esta versão):** 199 pessoas na aba e 295 acessos já com a função preenchida.
- **A regra está correta? Se não, qual deveria ser?:** ______


### ★ 1.5 Contador de registros: arquivo × aplicação

- **O que decide:** Se tudo o que estava no arquivo entrou na aplicação.
- **Critério:** A tela de bases (o link “Arquivos importados”) passa a mostrar, em cada base, quantas linhas o arquivo tinha e quantas estão na aplicação, com “confere” quando bate. Para RH e diretório AD a tela diz “acumulado”: essas bases somam as cargas anteriores por desenho, então o total é maior que o do arquivo e comparar um a um acusaria um erro que não existe.
- **Como conferir:** Clique em “Arquivos importados”, abra um setor e olhe a linha abaixo do nome da base.
- **Medido na sua base (a de 15/09, reprocessada aqui com esta versão):** Todos os extratos e as matrizes conferem: SYSTUR 7.074, SIG 80.140, SIGOT 208, Oracle EBS 2.804, SICA RA 257, SICA Esfera 44, IC 65, matriz de perfis 2.699 e CCO 1.241.
- **A regra está correta? Se não, qual deveria ser?:** ______


## 2. O que já tinha entrado na rodada de 16/09

Se você ainda não aplicou o pacote de 16/09, ele está incluído aqui. Resumo do que muda:

- Os 23 nomes que você listou como “ativos que seguem não vindo na aplicação” voltaram a aparecer na Consulta — os 23.
- Quem não tem expectativa de acesso aparece como “Não Mapeado”, com o texto “Não tem mapeamento localizado para o centro de custo.”.
- Quem saiu do arquivo de ativos mais recente deixou de aparecer como ativo (eram pessoas que já constavam na base de desligados).
- A regra de provável desligamento passou a valer só para quem também sumiu do arquivo de ativos. Com isso, 318 pessoas que estavam ativas e tinham perdido o acesso voltaram a aparecer como “Incluir Acesso”.


## 3. Quatro perguntas para você


### 3.1  A matriz do centro de custo 05.12.02.01 mudou de propósito?

Na matriz do SYSTUR de 18/08 saíram as linhas de GERENTE ATENDIMENTO e GERENTE DE OPERAÇÕES desse centro de custo; ficou só GERENTE EXECUTIVO ATENDIMENTO. É por isso que a equipe da PATRICIA MARAGNA aparece sem mapeamento. Foi intencional, ou essas linhas deveriam voltar?

Sua resposta: ______________________________________________


### 3.2  O limiar de 30% deve continuar cortando esses casos?

Quando menos de 30% das pessoas do cargo têm um acesso, a aplicação não cobra a inclusão. Na sua lista de 23 nomes, 9 estão nessa situação: têm perfil previsto na matriz, mas o acesso não é cobrado. Quer que passem a aparecer como “Incluir Acesso”?

Sua resposta: ______________________________________________


### 3.3  As contas com 42 perfis no SYSTUR entram no aviso?

Das 68 pessoas com mais de um perfil no SYSTUR, 5 têm 42 perfis e parecem contas técnicas. Elas devem receber o mesmo aviso, ou ficam de fora? E o aviso deve continuar informativo, ou virar pendência?

Sua resposta: ______________________________________________


### 3.4  Por que a mesma matrícula aparece duas vezes nos desligados?

O arquivo de desligados de 15/09 tem 11.634 linhas, mas 11.072 matrículas distintas: 556 matrículas aparecem repetidas. A aplicação considera cada pessoa uma vez, então nada se perdeu — mas vale entender se é rescisão dupla, vínculo antigo ou erro de extração.

Sua resposta: ______________________________________________


## 4. Duas correções em documentos anteriores

- Perfil a mais (perfil excessivo): o roteiro de 08/09 fala em 141 casos e 178 perfis; o número correto, medido nos 7 sistemas, é 130 casos e 186 perfis a mais.
- O roteiro de 06/08 diz, na seção “O que ainda não tem regra”, que o perfil a mais não é sinalizado. Isso deixou de valer em 28/08: ele aparece na Consulta (“N a mais”), e só a cobrança continua desligada.


## 5. O que NÃO mudou

Nenhuma regra de validação foi alterada nesta entrega. Comparando a sua base antes e depois, os números de Aderente (6.344), Em Análise (508) e Alterar Perfil (318) ficaram idênticos, assim como as divergências de desligados, transferidos e contas de serviço, o RH, os acessos e o ciclo de vida. Seguem valendo as decisões já fechadas: franqueado sem acesso não recebe sugestão, prestador sem grupo de espelho não gera linha, e a cobrança de perfil a mais continua desligada.
