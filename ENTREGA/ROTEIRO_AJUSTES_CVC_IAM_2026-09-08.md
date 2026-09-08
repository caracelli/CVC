# CVC IAM Analytics
## Roteiro de validação dos ajustes — o que mudou desde 06/08
Pacote UPDATE_BRUNA_v1.0.0 · 08/09/2026

Pacote UPDATE_BRUNA_v1.0.0  ·  08/09/2026

**Por que este documento existe**

O roteiro de 06/08 descreve as regras que já estavam no ar. Este cobre só o que MUDOU desde então — que é justamente onde a tela vai parecer diferente do que você conhece. A ideia é que nenhuma diferença apareça como surpresa: se algo mudou de lugar, está explicado aqui, com o critério e o passo para conferir.

**Como usar**

Cada ajuste tem “Como conferir” (o que filtrar na tela) e um valor esperado. A última linha é a que importa: dizer se a regra está CERTA. Se não bater com o que você vê, já é um achado — anote e me avise.

As regras marcadas com ★ são as que mais mudam o volume da fila. Se o tempo for curto, comece por elas.

> Uma diferença importante em relação ao roteiro de 06/08: aquele pacote levava o banco pronto, então dava para cravar o número exato de cada tela. Este pacote leva só os executáveis — o banco é gerado na sua máquina, com os seus extratos. Por isso cada linha diz se o valor é um INVARIANTE (tem de valer em qualquer base) ou apenas o que MEDIMOS na nossa base de referência, que serve como ordem de grandeza.


## Antes de tudo: o que fazer, nesta ordem

O passo 3 é o que costuma escapar, e sem ele nada deste documento acontece na tela — os ajustes agem na fase de ANÁLISE, não na importação. Enquanto o Processador não rodar, os números continuam os da rodada anterior.

1. Feche o painel e o Processador, se estiverem abertos.
2. Extraia o pacote e copie EXECUTAVEIS/ por cima da pasta atual. NÃO apague nem mexa em DADOS/ e INTERACOES/ — é onde ficam o banco e as tratativas que você já registrou.
2b. Copie também a pasta ENTRADA/ do pacote por cima da atual. Ela leva só dois arquivos de referência (o de-para do SIG e a matriz do franqueado). Nenhum dado seu é substituído.
3. Rode o Processador.exe UMA VEZ. Obrigatório.
4. Abra o visualizador.exe.
**Os números vão mudar bastante**

Esta rodada mexe em como várias populações são julgadas, então a comparação com a tela de antes não fecha — e isso é esperado, não defeito. Print ou planilha tirada da tela atual fica desatualizada depois do passo 3.


## 1. Franqueado — a mudança maior

Foi o pedido que você fez em 31/08 (“para franqueado não tem a questão de espelho”) e repetiu em 04/09, olhando o print com a origem “Espelho — franqueados”. Está atendido, e é a mudança que mais altera a tela.


### ★ 1.1 Franqueado saiu do espelho

- **O que decide:** Como o perfil esperado do franqueado é determinado.
- **Critério:** Enquanto a matriz de lojas estiver carregada, franqueado NÃO passa mais pelo espelho dos colegas. Terceiro e prestador continuam no espelho — eles não têm matriz, e tirá-los apagaria essa população da tela.
- **Como conferir:** Pendências ou Consulta → funil da coluna Origem.
- **Deve mostrar (vale em qualquer base):** “Espelho — franqueados” não pode aparecer nenhuma vez. Se aparecer, a matriz não foi lida — me avise.
- **A regra está correta? Se não, qual deveria ser?:** ______

> Consequência aceita: franqueado SEM acesso nenhum deixou de receber sugestão de inclusão. Sem o tipo de loja no cadastro, a matriz não consegue dizer QUAL perfil conceder — e inventar a partir dos colegas era exatamente o que você vetou.


### ★ 1.2 Matriz de lojas — o que ela valida

- **O que decide:** Se o perfil que o franqueado TEM é justificado pelo cargo dele.
- **Critério:** A matriz cruza CARGO × TIPO DE ATENDIMENTO × TIPO DE LOJA. As duas últimas não existem no cadastro (local de trabalho e filial vêm vazios), mas o NOME do perfil as codifica — ATEND_PUBLIC_LJT_… é atendimento ao público em loja terceirizada. Por isso a regra só fecha ao contrário: valida ADERÊNCIA, não gera inclusão.
- **Como conferir:** Pendências ou Consulta → funil da coluna Origem = “Matriz — franqueado”.
- **Deve mostrar (vale em qualquer base):** Toda linha dessa origem tem de trazer um motivo dizendo se o cargo autoriza o perfil. Linha sem motivo é achado.
- **A regra está correta? Se não, qual deveria ser?:** ______


### ★ 1.3 Cargo que não autoriza o perfil

- **O que decide:** O achado de segurança desta rodada.
- **Critério:** Quando o cargo da pessoa não consta na matriz para o perfil que ela tem, a linha sai como divergência com o motivo CARGO_NAO_AUTORIZA_PERFIL. São os dois sentidos: atendente com perfil de gerente (escalada de privilégio) e gerente com perfil abaixo do cargo.
- **Como conferir:** Consulta → busque pelo texto do motivo, ou filtre a origem “Matriz — franqueado” e olhe a coluna de motivo.
- **Medido na base de referência (o seu pode diferir):** 231 acessos (215 pessoas) — dos quais 44 atendentes com perfil de supervisor e 31 com perfil de gerente.
- **A regra está correta? Se não, qual deveria ser?:** ______

> Este é o número que vale conferir caso a caso: cada um é uma pessoa com acesso que o cargo dela não prevê.


### ★ 1.4 Perfis de exceção da Governança de SI

- **O que decide:** O bloco separado no fim da sua planilha de matriz.
- **Critério:** FRANQUEADOS_VC, GERENTE_GERAL_MASTER e MASTER_FRANQUEADO nunca são carregados como perfil esperado — se fossem, o painel passaria a MANDAR conceder MASTER_FRANQUEADO a todo gerente de franquia. Quem tem um deles vai para Em Análise citando a Governança.
- **Como conferir:** Consulta → busque por FRANQUEADOS_VC ou MASTER_FRANQUEADO.
- **Deve mostrar (vale em qualquer base):** Nenhum desses três pode aparecer como perfil ESPERADO / a conceder. Se aparecer, é defeito.
- **A regra está correta? Se não, qual deveria ser?:** ______

> PERGUNTA EM ABERTO (1 de 3): existe aprovação da Governança de Segurança da Informação para esses acessos? Medimos 207 na base de referência — entre eles 1 caixa e 3 atendentes com FRANQUEADOS_VC, que são os que mais saltam.


### 1.5 De-para de cargo derivado do uso

- **O que decide:** Como o cargo do RH é traduzido para o cargo da matriz.
- **Critério:** O RH escreve VENDEDOR, VENDEDORA, ATENDENTE - ; a matriz fala ATENDENTE. Em vez de pedir a lista, o de-para é derivado do próprio uso: se pelo menos 70% dos acessos de um cargo apontam para o mesmo cargo da matriz, ele é tratado como equivalente. Cargo que já existe na matriz NÃO ganha tradutor — senão um gerente com perfil de atendente viraria aderente.
- **Como conferir:** Consulta → a coluna de motivo mostra “cargo X tratado como Y (N acessos, M% de consistência)”.
- **Medido na base de referência (o seu pode diferir):** 11 equivalências. As cinco maiores: ATENDENTE - → ATENDENTE (1.144 acessos, 98%) · SUPERVISOR → SUPERVISOR ADMINISTRATIVO (326, 93%) · GERENTE - → GERENTE (200, 96%) · GERENTE DE VENDAS → GERENTE (166, 98%) · VENDEDOR → ATENDENTE (131, 94%).
- **A regra está correta? Se não, qual deveria ser?:** ______

> PERGUNTA EM ABERTO (2 de 3): essas equivalências estão certas? Elas saem do uso, não de uma definição sua — se alguma estiver errada, ela está escondendo ou criando divergência.


## 2. Por que tanto franqueado em “Em Análise”

Esta seção existe porque é o ponto onde a tela mais vai destoar do que você viu na rodada passada, e a causa não é a regra nova — é o extrato.


### ★ 2.1 Conta sem status no extrato

- **O que decide:** O que fazer quando o extrato não diz se a conta está ativa.
- **Critério:** A regra que você definiu é que não se assume conta ativa. O extrato SYSTUR antigo (o relatório de 30/04, em XLSX) não traz coluna de status; o formato novo (view_systur_….csv) traz. Sem status, o resultado vai para Em Análise — mas agora PRESERVANDO o veredito da matriz no motivo, em vez de apagá-lo.
- **Como conferir:** Consulta → filtre origem “Matriz — franqueado” e leia a coluna de motivo.
- **Deve mostrar (vale em qualquer base):** Se o seu extrato SYSTUR não tiver status, quase todo franqueado cai em Em Análise — mas cada linha continua dizendo se o cargo autoriza o perfil. O veredito não se perde.
- **A regra está correta? Se não, qual deveria ser?:** ______

> PERGUNTA EM ABERTO (3 de 3): qual extrato do SYSTUR está na sua ENTRADA? Se for o de 30/04, vale trocar pelo mais recente no formato view_systur_….csv — com a coluna de status, os aderentes aparecem como Aderente e as divergências como Divergente, limpo. Foi o que medimos: 4.405 aderentes / 231 divergentes / 207 de exceção.


### 2.2 Conta pendente ou bloqueada vira “a incluir”

- **O que decide:** O desfecho de quem tem conta, mas ela não está ativa.
- **Critério:** Pedido seu em 31/08: conta com status inativo, bloqueado ou P, quando a pessoa pode ter o acesso, sai como “a incluir” mostrando o perfil liberável. Vale para todos os sistemas — com UMA exceção: franqueado, porque ali essa conversão apagaria a escalada de privilégio da regra 1.3.
- **Como conferir:** Pendências → filtro Ação = “Incluir Acesso”; a coluna de motivo distingue CONTA_PENDENTE de CONTA_BLOQUEADA.
- **Deve mostrar (vale em qualquer base):** Nenhuma linha de franqueado pode sair com o motivo CONTA_PENDENTE genérico — o motivo dela tem de citar a matriz.
- **A regra está correta? Se não, qual deveria ser?:** ______

> Esta exceção é uma decisão nossa, e é o ponto do documento que mais merece a sua opinião: ela privilegia não perder o achado de segurança, ao custo de o franqueado ficar em Em Análise em vez de “a incluir”. Se preferir o contrário, é reversível numa linha.


## 3. Desligados e contas de sistema


### ★ 3.1 Conta de serviço não é acesso de desligado

- **O que decide:** O que fazer com robô cadastrado com o e-mail de uma pessoa.
- **Critério:** Login com prefixo SIST é conta de serviço: sai da lista de revogação e passa a ter categoria própria, em vez de aparecer como acesso a revogar de quem saiu. O robô não é revogado porque quem o cadastrou foi embora — revogar derruba produção. A lista de prefixos está no config, não no código.
- **Como conferir:** Desligados → a categoria própria de conta de serviço.
- **Medido na base de referência (o seu pode diferir):** 297 acessos saíram da lista de revogação — 69% das 432 linhas que havia. Vieram de 10 logins: ROBO MARITIMO, AUTOMACAO RPA SOLO, PROJETO JENKINS, ROBO AEREO GRUPOS, entre outros.
- **A regra está correta? Se não, qual deveria ser?:** ______

> Era o SIST0230 do seu print de 28/08. Uma conta ficou de fora do corte e vale o seu olhar: MTZOPE288 / CCO PLANTAO — conta compartilhada de plantão, nem robô nem pessoa.


### 3.2 Desligado que voltou a trabalhar

- **O que decide:** Quando um desligado com acesso é falso positivo.
- **Critério:** Se a conta pertence a alguém ATIVO hoje com o MESMO login, não é acesso a revogar — é a conta que a pessoa usa. Só aponta quando o ativo tem login diferente, aí a conta antiga sobra mesmo. Regra sua, textual, de 10/08.
- **Como conferir:** Desligados → a lista de revogação.
- **Medido na base de referência (o seu pode diferir):** A regra derrubou os falsos positivos de 762 para 24 pessoas na base em que foi medida.
- **A regra está correta? Se não, qual deveria ser?:** ______


## 4. Consulta — identidade e perfis


### 4.1 Mesma pessoa em dois vínculos vira uma linha

- **O que decide:** Quando duas identidades são a mesma pessoa.
- **Critério:** Você apontou em 10/08: “se é a mesma pessoa por que traz separado?”. Acontece quando alguém existe em duas origens — prestador no diretório e terceiro no RH, mesmo CPF. Agora elas viram uma linha só, somando os acessos. É fusão de APRESENTAÇÃO: cada tratativa continua gravada contra a identidade real, e o detalhe mostra de qual identidade veio cada acesso.
- **Como conferir:** Consulta → busque por um CPF que você saiba ter dois cadastros.
- **Deve mostrar (vale em qualquer base):** Uma linha por pessoa, com os dois vínculos na coluna Categoria (ex.: “Prestador · Terceiro”).
- **A regra está correta? Se não, qual deveria ser?:** ______

> Ajuste de 08/09: a fusão passou a exigir também que o NOME tenha algo em comum. Encontramos 8 casos na base em que o mesmo CPF estava em pessoas diferentes — código de terceiro cadastrado no campo de CPF. Sem essa trava, o acesso de uma apareceria sob o nome da outra.


### 4.2 Perfil excessivo aparece na tela

- **O que decide:** Quem tem o perfil certo MAIS outros que o cargo não prevê.
- **Critério:** Antes o veredito Aderente prevalecia e o extra sumia — a tela afirmava o que a pessoa tinha, e afirmava errado. Agora o extra aparece no perfil atual e a linha ganha um “?” explicando. Por decisão de configuração, isso NÃO vira pendência: é informativo.
- **Como conferir:** Consulta → linhas com o ícone “?” e o texto de perfil excessivo.
- **Medido na base de referência (o seu pode diferir):** 141 casos, somando 178 perfis a mais.
- **A regra está correta? Se não, qual deveria ser?:** ______

> Existe uma chave de configuração para transformar isso em pendência de verdade. Está desligada porque cobrar 141 casos de uma vez é decisão sua, não nossa.


## 5. Leitura dos arquivos


### ★ 5.1 O leitor acha o cabeçalho sozinho

- **O que decide:** Como cada extrato é interpretado.
- **Critério:** O leitor passou a procurar a linha do cabeçalho e o separador pelos nomes de coluna que espera, em vez de contar linhas fixas. Nasceu do SICA_RA, que chegou em 01/09 num layout novo — e o leitor antigo lia ZERO acesso sem dar erro nenhum. Falha silenciosa é o pior tipo.
- **Como conferir:** Painel → link “Arquivos importados”, no topo.
- **Deve mostrar (vale em qualquer base):** Cada base tem de mostrar a data do arquivo que você depositou. Data velha em alguma base significa que aquele arquivo não entrou.
- **A regra está correta? Se não, qual deveria ser?:** ______


### 5.2 Extrato cumulativo — o mais novo manda

- **O que decide:** Qual arquivo vale quando chegam vários do mesmo sistema.
- **Critério:** Cada exportação traz a base inteira com o status do dia, então o arquivo mais recente substitui o anterior. Quando o nome não tem data, vale a data do arquivo.
- **Como conferir:** Painel → “Arquivos importados”.
- **Deve mostrar (vale em qualquer base):** A data mostrada tem de ser a do arquivo mais recente que você colocou na pasta.
- **A regra está correta? Se não, qual deveria ser?:** ______

> Achado que vale a sua confirmação: no extrato do SICA_RA de 01/09, 116 dos 135 acessos que o painel mostrava não existem mais como acesso vivo (110 viraram inativo, 6 bloqueado, 7 sumiram). Se esse arquivo for o extrato COMPLETO do sistema, está certo; se for um recorte, precisamos do arquivo inteiro.


## 6. O que NÃO mudou (e continua valendo)

Tudo que está no roteiro de 06/08 segue em vigor. Vale reforçar três pontos que costumam gerar dúvida e não foram alterados nesta rodada:

- Conta BLOQUEADA ou INATIVA não conta como acesso — a ação certa nesses casos é desbloquear, não criar.
- “Incluir Acesso” e “Aderente” não entram na contagem de pendências: quem não tem o acesso não é irregularidade a corrigir.
- O limiar de 30% de adesão continua suprimindo inclusão em cargo onde quase ninguém tem o acesso — é o que evita inundar a fila.

## 7. Resumo para devolver

Se preferir responder de uma vez: as três perguntas em aberto e, abaixo, o que discordar. O que não for citado fica entendido como aprovado.

1. Os perfis de exceção (FRANQUEADOS_VC, GERENTE_GERAL_MASTER, MASTER_FRANQUEADO) têm aprovação da Governança de SI?
2. As 11 equivalências de cargo derivadas do uso estão corretas?
3. Qual extrato do SYSTUR está na sua ENTRADA — o de 30/04 ou o formato novo com coluna de status?

| Regra | O que está errado | O que deveria ser |
|---|---|---|
| | | |
| | | |
| | | |

> Toda regra deste documento é critério ou parâmetro que pode mudar. Alteração exige um reprocessamento para os números refletirem a decisão.
