# CVC IAM Analytics
## Roteiro de validação — seus documentos de 22/09 e 24/09
24/09/2026

**Por que este documento existe**

Ele responde, um a um, os oito pontos do seu documento de 22/09 — as nove páginas, incluindo as que eram só imagem — e os do seu documento de 24/09 (Sistema_24_09). Cada item diz o que mudou, como conferir e o valor esperado na sua base.

**Leia primeiro: o número de linhas DIMINUI**

Esta entrega tira da tela acessos que não deveriam estar lá, então o total cai de 14.176 para 12.310 linhas. Isso é o efeito pretendido: boa parte dessas linhas vinha de uma FUNÇÃO que não é a da pessoa (o ponto que você levantou no SIG). As pendências, ao contrário, SOBEM — de 1.151 para 1.278 pessoas —, porque passamos a cobrar casos que antes passavam batidos.

> O pacote já traz a pasta DADOS com o banco processado: você NÃO precisa rodar o Processador. Se rodar, tudo bem — mas deixe as matrizes na pasta ENTRADA, porque a regra do Oracle depende de uma coluna que só entra quando a matriz é importada de novo.


## Antes de tudo: o que fazer, nesta ordem

- 1. Feche o painel e o Processador, se estiverem abertos.
- 2. BACKUP (obrigatório): copie as pastas DADOS\BANCO e INTERACOES para outro lugar. Se algo não sair como esperado, é só devolvê-las.
- 3. Extraia o pacote na pasta principal da instalação — a que contém DADOS, ENTRADA e EXECUTAVEIS — e aceite substituir os arquivos.
- 4. NÃO apague nem mexa na pasta INTERACOES: é onde ficam as suas tratativas, e o painel as lê ao vivo.
- 5. Abra o visualizador.exe.


## 1. Os oito pontos do seu documento de 22/09


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
- **Deve mostrar (vale em qualquer base):** Oracle EBS aderente com os QUATRO perfis da função dela (CVC AP NOVA VISUAL / AP BRASIL / AP SUBMARINO / AP VISUAL Consulta). Na base: 185 pessoas com Oracle e sem perfil no SYSTUR, 68 com acesso fora do que o perfil delas prevê, e o “incluir” do Oracle cai de 354 para 233 pessoas. Quem é do Mapeamento CCO não passa por esta regra (item 2.1).
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
- **Deve mostrar (vale em qualquer base):** Nenhuma linha de SIG cobrada (eram 14, vindas da função “A Receber 2 + SIG”, que não é a dela). As outras funções da equipe continuam visíveis como “o que ela pode ter” (item 2.4). Na base: 2.929 linhas de outra função saíram da cobrança — SIG 2.244, SIGOT 336, SICA RA 199, SICA Esfera 143 —, afetando 196 pessoas.
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


## 2. Seu documento de 24/09 e os ajustes do dia


### ★ 2.1 Quem é do Mapeamento CCO não passa pela regra Oracle x SYSTUR

- **O que decide:** Se o Oracle de quem está no CCO depende do perfil do SYSTUR.
- **Critério:** Para quem está no Mapeamento CCO (centro de custo + gestor), o Oracle é comparado direto com o que o CCO prevê, sem o filtro pelo perfil do SYSTUR e sem as pendências “sem perfil no SYSTUR” e “perfil fora do SYSTUR”. São 57 das 457 pessoas com Oracle.
- **Como conferir:** Consulta → BRENDA VASCONCELOS DERENCIO (34530984).
- **Deve mostrar (vale em qualquer base):** Oracle EBS aderente — tem os 6 perfis da função dela; o CVC OIE BRASIL - Relatório de Despesas aparece como “1 a mais”, informativo. Ela não é pendência.
- **A regra está correta? Se não, qual deveria ser?:** ______


### 2.2 “Não tem mapeado na matriz”

- **O que decide:** O que aparece para quem é do CCO, não tem Oracle e só o CCO da equipe prevê Oracle.
- **Critério:** Seu pedido: colocar que não tem mapeado na matriz. Em vez de sugerir incluir, a linha é informativa e diz isso — dentro da função, com cada perfil, e no bloco “Sem mapeamento”. A função passa a mostrar quantos perfis ficaram de fora da conta, para não dizer “completa” com metade dos acessos.
- **Como conferir:** Consulta → ROSE APARECIDA DIOGO (2752).
- **Deve mostrar (vale em qualquer base):** Oracle: “não tem mapeado na matriz — a previsão vem só da CCO da equipe”. A função “Atendimento a fornecedores CVC e VISUAL” mostra “completa · 4 não mapeados na matriz”. Na base: 61 pessoas.
- **A regra está correta? Se não, qual deveria ser?:** ______


### 2.3 Opera Operacional aparece pelo Mapeamento CCO

- **O que decide:** Se o Opera Operacional aparece na aplicação.
- **Critério:** Não recebemos extrato do Opera, então não dá para conferir se a pessoa tem o acesso. O que o CCO prevê para a função dela aparece como informativo — nunca como pendência nem como “incluir”.
- **Como conferir:** Consulta → EDISON ALVES DO NASCIMENTO (1759) → Funções previstas → A Receber 2 + SIG.
- **Deve mostrar (vale em qualquer base):** OPERA_OPERACIONAL · A_RECEBER_2 · “sem extrato”. Na base: 149 pessoas, 203 linhas.
- **A regra está correta? Se não, qual deveria ser?:** ______


### ★ 2.4 As outras funções da equipe que a pessoa pode ter

- **O que decide:** O que aparece das funções do gestor que não são a da pessoa.
- **Critério:** O CCO lista todas as funções da equipe. A função da pessoa — a que o perfil do SYSTUR indica — é a cobrada. As demais aparecem logo abaixo, com cada acesso marcado “tem” / “não tem”, sem virar pendência. Quem não tem perfil no SYSTUR recebe todas as funções, como antes.
- **Como conferir:** Consulta → BRENDA VASCONCELOS DERENCIO (34530984) → final da aba Acessos.
- **Deve mostrar (vale em qualquer base):** “Outras funções que a pessoa pode ter (3)”: A Receber 1 Comissão, A Receber 2 + SIG e A Receber 3. Na base: 374 pessoas têm o bloco.
- **A regra está correta? Se não, qual deveria ser?:** ______


### ★ 2.5 Um perfil por sistema: as outras opções não são “falta”

- **O que decide:** Como aparece o sistema em que a matriz prevê mais de uma opção e a pessoa tem uma.
- **Critério:** Seu documento: “se um dos acessos mapeados estiver ok traz ele ok, e os a mais precisam ser trazidos estilo as funções do CCO”. O sistema vem aderente, sem “Falta 1”, e as outras opções vão para o bloco “Outros acessos previstos”. Uma opção aparece direto; mais de uma fica recolhida. Vale para todos os sistemas menos o Oracle, onde cada perfil é um acesso.
- **Como conferir:** Consulta → ROSELAINE DO NASCIMENTO FIGUEIREDO (34532575); depois CAIO LUIZ DA COSTA (34531299).
- **Deve mostrar (vale em qualquer base):** Roselaine: SIGOT, SYSTUR e IC aderentes; em “Outros acessos previstos”, SIGOT Intercompany, SYSTUR INTERCOMPANY e IC IC_CADASTRO. Caio: “SYSTUR — 2 opções”, recolhido. Na base: 168 pessoas.
- **A regra está correta? Se não, qual deveria ser?:** ______


### ★ 2.6 “Não pode ter acesso e tem”

- **O que decide:** O que aparece para quem tem acesso num sistema que nem a matriz nem o CCO preveem para ela.
- **Critério:** A tela dizia só “sem perfil previsto”, sem mostrar o acesso. Agora é pendência, com o perfil que a pessoa tem. Nas linhas de análise com um lado só, a tela diz qual é: “Deveria ter:” ou “Tem hoje:”.
- **Como conferir:** Consulta → DENISE APARECIDA GONCALVES DOS SANTOS (1562).
- **Deve mostrar (vale em qualquer base):** Necessário análise: SYSTUR “Deveria ter: INTEGRADOR_CONTABIL” e IC “Tem hoje: IC_CADASTRO”. Na base: 7 pessoas.
- **A regra está correta? Se não, qual deveria ser?:** ______


### 2.7 A função certa em cada acesso

- **O que decide:** Em qual função do CCO cada acesso aparece.
- **Critério:** O mesmo perfil do Oracle está em várias funções da equipe, e a aplicação pegava a primeira da planilha. Agora vale a função que o SYSTUR da pessoa indica. Só muda o nome da função exibida; nenhum status muda.
- **Como conferir:** Consulta → EDISON ALVES DO NASCIMENTO (1759).
- **Deve mostrar (vale em qualquer base):** Uma função só: A Receber 2 + SIG, com o Oracle dentro dela. Antes aparecia também “A Receber 1”, que não é a dele.
- **A regra está correta? Se não, qual deveria ser?:** ______


## 3. O que vai parecer diferente — e por quê

Estas mudanças alteram números que você acompanha. Nenhuma delas é erro; todas vêm dos pontos acima.

- O total de linhas cai de 14.176 para 12.310. São os acessos de função que não é da pessoa (item 1.5) e os do Oracle que o perfil do SYSTUR não autoriza (item 1.3).
- As pendências SOBEM: de 1.151 para 1.278 pessoas. A maior parte são as 185 pessoas que têm Oracle e não têm perfil no SYSTUR.
- Aparecem linhas novas de Opera Operacional (149 pessoas) e de “não tem mapeado na matriz” no Oracle (61 pessoas) — as duas informativas.
- Aparecem 7 pendências novas de “não pode ter acesso e tem”.


## 4. Duas perguntas para você


### 4.1 O Relatório de Despesas deve contar como pendência?

Hoje conta para quem passa pela regra do SYSTUR. São 373 das 457 pessoas com Oracle que têm esse acesso. Se for corporativo, ele deixa de contar e a fila do Oracle diminui bastante.

Sua resposta: ______________________________________________


### 4.2 No SIG, os perfis são alternativos ou se somam?

Hoje ter mais de um perfil no mesmo sistema vira pendência, e no SIG isso são 230 linhas. Mas 47% das pessoas com SIG têm mais de um (média de 18,7), e os nomes parecem permissões que se somam (ACESSO_CARRO_INTER_GRUPOS, CAD_FORNECEDOR_SALVAR). No SYSTUR, onde a regra faz sentido, são 1%.

Sua resposta: ______________________________________________
