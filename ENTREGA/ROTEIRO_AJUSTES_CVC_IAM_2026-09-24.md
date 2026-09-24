# CVC IAM Analytics
## Roteiro de validação — os 8 pontos do seu documento de 22/09
24/09/2026

**Por que este documento existe**

Ele responde, um a um, os oito pontos do seu documento de 22/09 — as nove páginas, incluindo as que eram só imagem. Cada item diz o que mudou, como conferir e o valor esperado na sua base.

**Leia primeiro: o número de linhas DIMINUI**

Esta entrega tira da tela acessos que não deveriam estar lá, então o total cai de 14.176 para 11.732 linhas. Isso é o efeito pretendido: 2.929 dessas linhas vinham de uma FUNÇÃO que não é a da pessoa (o ponto que você levantou no SIG). As pendências, ao contrário, SOBEM — de 1.151 para 1.289 pessoas —, porque passamos a cobrar casos que antes passavam batidos.

> O pacote já traz a pasta DADOS com o banco processado: você NÃO precisa rodar o Processador. Se rodar, tudo bem — mas deixe as matrizes na pasta ENTRADA, porque a regra do Oracle depende de uma coluna que só entra quando a matriz é importada de novo.


## Antes de tudo: o que fazer, nesta ordem

- 1. Feche o painel e o Processador, se estiverem abertos.
- 2. BACKUP (obrigatório): copie as pastas DADOS\BANCO e INTERACOES para outro lugar. Se algo não sair como esperado, é só devolvê-las.
- 3. Extraia o pacote na pasta principal da instalação — a que contém DADOS, ENTRADA e EXECUTAVEIS — e aceite substituir os arquivos.
- 4. NÃO apague nem mexa na pasta INTERACOES: é onde ficam as suas tratativas, e o painel as lê ao vivo.
- 5. Abra o visualizador.exe.


## 1. Os oito pontos do seu documento


### ★ 1.1 Os acessos que a matriz prevê voltaram a aparecer

- **O que decide:** Quais acessos “a incluir” a aplicação mostra.
- **Critério:** Havia um corte que escondia a inclusão quando poucas pessoas do mesmo cargo tinham aquele acesso. Ele nasceu para não inundar a fila de pendências — mas em 29/07 você pediu que “sem acesso” saísse das pendências e ficasse só na Consulta. Desde então o corte só escondia informação. Foi desligado: agora vem 100% do que a matriz mapeia.
- **Como conferir:** Consulta → busque MARCELO DE CASTRO DIAS (1303) → “ver detalhe” → aba Acessos.
- **Deve mostrar (vale em qualquer base):** SYSTUR aparece com ATEND_AGENCIA_LJP_PROMOTORES_VC, que é o perfil da linha que você circulou na matriz. Antes ele vinha com “Sem registros de acesso” e os 7 sistemas em “Sem mapeamento”.
- **A regra está correta? Se não, qual deveria ser?:** ______


### 1.2 O SICA Esfera voltou a trazer o perfil sugerido

- **O que decide:** O acesso esperado de quem é coberto pelo Mapeamento CCO.
- **Critério:** Mesma causa do item anterior.
- **Como conferir:** Consulta → CAMILA DOS SANTOS TENORIO MARQUES (32696).
- **Deve mostrar (vale em qualquer base):** SICA_ESFERA aparece com CREDITO B2B B2C — o perfil da linha que você circulou. Na base inteira são 99 pessoas com acesso sugerido pelo CCO no SICA Esfera.
- **A regra está correta? Se não, qual deveria ser?:** ______


### ★ 1.3 O Oracle passa a seguir o perfil do SYSTUR

- **O que decide:** Quais acessos do Oracle EBS a pessoa pode ter.
- **Critério:** Você disse que os acessos do Oracle dependem do perfil liberado no SYSTUR. A matriz do Oracle tem a coluna PERFIL SYSTUR — 39 valores, 38 deles existindo igualzinho no extrato do SYSTUR — e a aplicação a ignorava: a pessoa recebia todas as responsabilidades do cargo dela. Agora a linha da matriz só vale se ela tiver aquele perfil no SYSTUR. Quem tem Oracle e NÃO tem perfil no SYSTUR vira pendência NO SYSTUR, porque é lá que está a falta.
- **Como conferir:** Consulta → PRISCILA SANTOS DE LIMA (90001455).
- **Deve mostrar (vale em qualquer base):** Oracle EBS aderente com os QUATRO perfis da função dela (CVC AP NOVA VISUAL / AP BRASIL / AP SUBMARINO / AP VISUAL Consulta). Na base: 190 pessoas com Oracle e sem perfil no SYSTUR, 81 com acesso fora do que o perfil delas prevê, e o “incluir” do Oracle cai de 354 para 244 pessoas.
- **A regra está correta? Se não, qual deveria ser?:** ______


### 1.4 Quando a matriz não cobre o cargo, a tela diz isso

- **O que decide:** O que aparece para quem tem acesso num sistema que a matriz não mapeia para o cargo dela.
- **Critério:** Seu pedido: “no ebs vir que não está mapeado”. A linha existe, é informativa (não é pendência) e mostra o acesso que a pessoa tem hoje. A matriz do Oracle cobre 36 centros de custo, então o caso é comum.
- **Como conferir:** Consulta → MARCELO DE CASTRO DIAS (1303) → bloco “Sem mapeamento”.
- **Deve mostrar (vale em qualquer base):** ORACLE_EBS — “tem hoje: CVC OIE BRASIL - Relatório de Despesas — sem perfil previsto para o cargo/centro de custo”. Na base: 281 pessoas.
- **A regra está correta? Se não, qual deveria ser?:** ______


### ★ 1.5 O CCO passa a seguir a FUNÇÃO da pessoa

- **O que decide:** Quais acessos do Mapeamento CCO valem para cada pessoa.
- **Critério:** Você apontou: “com base na matriz o usuário não pode ter acesso ao SIG”. O CCO casa por centro de custo + GESTOR, e o mesmo gestor tem várias funções — a pessoa recebia a soma de todas. Quem diz qual é a dela é o perfil do SYSTUR. Se ela TEM um acesso que a função dela não prevê, a linha não some: vira pendência dizendo isso.
- **Como conferir:** Consulta → BRENDA VASCONCELOS DERENCIO (34530984).
- **Deve mostrar (vale em qualquer base):** Nenhuma linha de SIG (eram 14, vindas da função “A Receber 2 + SIG”, que não é a dela). Na base: 2.929 linhas de outra função saíram — SIG 2.244, SIGOT 336, SICA RA 199, SICA Esfera 143 —, afetando 196 pessoas. Nenhuma pessoa entrou nem saiu da fila de pendências por causa disso.
- **A regra está correta? Se não, qual deveria ser?:** ______


### 1.6 Quantos perfis a pessoa pode ter

- **O que decide:** O que a coluna “Perfil Esperado” mostra.
- **Critério:** Você escreveu: “Ela pode ter acesso a 3 perfis do oracle e tem um só então está errado”. A linha guardava apenas o perfil que casou, e a tela usa esse campo para calcular a diferença — então ela anunciava como excesso tudo o que a matriz prevê e não foi o escolhido.
- **Como conferir:** Consulta → GILDA TAVARES DA SILVA (34530435) → Oracle EBS.
- **Deve mostrar (vale em qualquer base):** “Tem 41 · Faltam 6 · 1 a mais: CVC OIE BRASIL - Relatório de Despesas”. Antes dizia “41 a mais”, quando o acesso fora do previsto era UM.
- **A regra está correta? Se não, qual deveria ser?:** ______


### ★ 1.7 Transferidos em linhas e colunas

- **O que decide:** Como a aba Transferidos mostra a situação de quem mudou de área.
- **Critério:** Seu desenho: Sistema | Tem atualmente | mapeando nova área | Incluir/excluir/alterar acesso. As três perguntas de 17/09 viraram as três colunas. A tabela percorre TODOS os sistemas, inclusive aqueles em que não há nada a fazer — você pediu uma foto, e “nada aqui” também é informação.
- **Como conferir:** Aba Transferidos → GILDA TAVARES DA SILVA (34530435) → clique para expandir.
- **Deve mostrar (vale em qualquer base):** Sete linhas, uma por sistema, com o login em cinza abaixo do nome do sistema. SICA Esfera e SIG aparecem com “—”.
- **A regra está correta? Se não, qual deveria ser?:** ______


### ★ 1.8 O programa não cai mais ao trocar de janela

- **O que decide:** Se o painel continua respondendo depois de ficar em segundo plano.
- **Critério:** Eram dois problemas somados. O painel se encerrava sozinho após 5 minutos sem sinal de vida — e o navegador congela a aba quando a janela fica atrás de outra. E, no Windows, duas cópias do painel conseguiam abrir na mesma porta, de modo que fechar uma derrubava a outra: o próprio “fechar e abrir de novo” recriava o problema.
- **Como conferir:** Abra o painel, vá trabalhar em outra janela por mais de 5 minutos e volte.
- **Deve mostrar (vale em qualquer base):** Tudo continua funcionando, sem precisar fechar e abrir. A troca de abas também ficou mais rápida.
- **A regra está correta? Se não, qual deveria ser?:** ______


## 2. O que vai parecer diferente — e por quê

Três mudanças alteram números que você acompanha. Nenhuma delas é erro; todas vêm dos pontos acima.

- O total de linhas cai de 14.176 para 11.732. São os acessos de função que não é da pessoa (item 1.5) e os do Oracle que o perfil do SYSTUR não autoriza (item 1.3).
- As pendências SOBEM: de 1.151 para 1.289 pessoas. A maior parte são as 190 pessoas que têm Oracle e não têm perfil no SYSTUR.
- BRENDA VASCONCELOS DERENCIO passa a aparecer como pendência no Oracle. O único acesso dela fora do previsto é o CVC OIE BRASIL - Relatório de Despesas. Esse mesmo acesso responde por 76 das divergências do Oracle — 373 das 457 pessoas com Oracle o têm. Se ele for um acesso corporativo que não deve ser cobrado, a aplicação já tem onde configurar isso e a fila do Oracle cai de 99 para 18 pessoas.


## 3. Três perguntas para você


### 3.1 O Relatório de Despesas deve contar como pendência?

Hoje conta. São 373 das 457 pessoas com Oracle que têm esse acesso, e 278 têm só ele. Se for corporativo, ele deixa de contar e a fila do Oracle cai de 99 para 18 pessoas.

Sua resposta: ______________________________________________


### 3.2 No SIG, os perfis são alternativos ou se somam?

Hoje ter mais de um perfil no mesmo sistema vira pendência, e no SIG isso são 230 linhas. Mas 47% das pessoas com SIG têm mais de um (média de 18,7), e os nomes parecem permissões que se somam (ACESSO_CARRO_INTER_GRUPOS, CAD_FORNECEDOR_SALVAR). No SYSTUR, onde a regra faz sentido, são 1%.

Sua resposta: ______________________________________________


### 3.3 Quando a matriz por cargo lista dois perfis do mesmo sistema, eles são alternativas?

Exemplo: GILDA TAVARES DA SILVA tem INTERCOMPANY no SYSTUR e a tela diz “Falta 1: CUSTOS”. Se os dois forem alternativas, a sugestão está errada — e seguir por ela criaria uma pendência de “mais de um perfil”.

Sua resposta: ______________________________________________
