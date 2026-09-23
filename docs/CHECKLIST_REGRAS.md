# Checklist das regras — sequência, mudanças e situação

Para cada regra, na ordem em que o motor as aplica: **o que ela faz**, **o
número medido hoje**, e **o histórico de mudanças** — data e o que foi pedido.

Fontes: o código (que registra a data de cada decisão nos comentários), os
roteiros de 06/08, 08/09, 11/09 e 18/09, o retorno de 22/09 e a conversa do
Teams. Medições feitas em 22/09/2026 na base real reprocessada (base de 15/09:
13.733 ativos, 90.592 acessos, 11.441 linhas de validação).

Situação: **OK** conferida hoje contra o dado real · **ACHADO** conferida e não
bate, ou revela efeito que ninguém decidiu · **—** não conferida.

Cobertura: 21 das 39 conferidas · 5 achados · **11 regras mudaram desde 06/08**.

---

## Fase 1 — Importação

**#1 · Dobra das interações** — os `.jsonl` por usuário viram quarentena e
resoluções no banco. · **—**

**#2 · Diretório AD antes do RH** — é a base principal de identidade; dá dono
aos acessos órfãos pelo login. · **—**
- *22/07 (área)* — pedido: o AD passa a ser base principal de identidade, não
  complemento.

**#3 · RH ativos e desligados** — 13.733 / 30.247. O snapshot é gravado antes do
merge. · **—**

**#4 · Padronização do RH** · **—**

**#5 · Matrizes** — ORACLE 1.998 · SYSTUR 545 · SICA_RA 61 · SIGOT 60 · IC 28 ·
**SICA_ESFERA 7** linhas. · **ACHADO**
- *18/08 (cliente, sem nos avisar)* — a matriz do SYSTUR trocou de aba: de
  ~2.100 linhas para ~546. O centro de custo 05.12.02.01 perdeu GERENTE
  ATENDIMENTO e GERENTE DE OPERAÇÕES. Foi causa direta de sumiço na
  investigação de 15/09.
- *18/09 (nós → ela)* — pergunta 3.1: "foi intencional, ou essas linhas
  deveriam voltar?" **Sem resposta.**
- **Achado:** a matriz do SICA Esfera tem 7 linhas para 5 centros de custo, num
  sistema com 42 usuários. Na prática ele não tem matriz própria — depende
  quase só da CCO.

**#6 · Extratos dos sistemas** — contador arquivo × aplicação: diferença 0 em
todos. · **OK**
- *01/09* — o SICA_RA chegou num layout novo e o leitor antigo lia ZERO acesso
  **sem dar erro**. Falha silenciosa.
- *08/09* — mudança: o leitor passou a procurar o cabeçalho e o separador pelos
  nomes de coluna, em vez de contar linhas fixas.
- *18/09 (ela, por mensagem)* — pedido: mostrar "linhas lidas no arquivo ×
  linhas carregadas na aplicação" por base. Entregue.

**#7 · SIG** — diferença 0. · **OK**

## Fase 2 — Vinculação

**#8 · Cascata de 6 níveis** — CPF 48.040 · nome 9.256 · e-mail 1.756 · login
129 · CPF parcial 24 · fuzzy 724 · **sem dono 30.663**. · **OK**
- *Conferido hoje:* o fuzzy **não vincula** — 0 dos 724 têm dono, como a regra
  promete. Só sugere candidatos.
- *A observar:* 34% dos acessos ficam sem dono. Não é defeito da regra; é o
  tamanho do problema de identidade.

## Fase 3 — Divergências

**#9 · Acesso de desligado** — 2 linhas. · **OK**
- *10/08 (Bruna, textual)* — pedido: desligado que voltou a trabalhar com o
  MESMO login não é acesso a revogar. Derrubou os falsos positivos de 762 para
  24 pessoas.
- *Conferido hoje, e o número engana:* 22.175 linhas de acesso têm CPF de
  alguém que está nos desligados. Filtrando: 21.657 CPFs só existem lá → 1.402
  acessos → **só 2 com conta ativa**, e o motor pegou exatamente esses 2. Os
  outros 1.400 já estão bloqueados. **A regra está certa.**

**#10 · Conta de serviço** — 212. · **—**
- *28 e 31/08 (Bruna)* — pedido, textual: "porque tá vindo uns usuários
  sistêmicos nos desligados". Login com prefixo configurado sai da lista de
  revogação e ganha categoria própria — revogar robô derruba produção.

**#11 · Acesso sem vínculo no RH** — 18. · **—**

**#12 · Transferidos** — 199 pessoas, 2.364 acessos marcados. · **—**
- *29/07 (área)* — pedido: entra na revisão quem mudou de cargo, centro de
  custo, departamento **ou** gestor. Sem janela temporal.

## Fase 4 — Validação

### Preparação

**#13 · Conta bloqueada ou inativa não é acesso** — 17.341 acessos descartados.
· **ACHADO** (ver o achado final)
- *22/07 (área)* — pedido: conta revogada não conta como acesso.

**#14 · Conta com status indefinido** — 11. · **OK**
- *10/08 (área)* — pedido: não assumir que a conta está ativa quando o extrato
  não diz.

**#15 · Adesão cargo × sistema** — adesão máxima 100% em todos os 7 sistemas. ·
**OK**
- *Conferido hoje, e derruba uma hipótese:* sistema pequeno **não** é
  estruturalmente barrado pelo limiar. Até o SICA Esfera tem 11 cargos acima
  de 30%.

**#16 · Quem sumiu do arquivo de ativos** — 27 pessoas. · **OK**
- *15/09 (usuário)* — pedido: "todo mundo que sumiu" do arquivo de ativos mais
  recente não deve ser tratado como ativo.

### Por pessoa

**#17 · Matriz e CCO num conjunto único por sistema** · **—**
- *Correção de desenho:* sem isso a mesma pessoa saía OK pela matriz e
  Divergente pela CCO na mesma rodada.

**#18 · Função da CCO carimbada na linha** — 1.800 linhas com função. · **—**
- *17/09 (Bruna)* — pedido: quando o esperado vem do CCO, mostrar as FUNÇÕES
  disponíveis, e ao expandir, os acessos que formam cada uma.
- *22/09 (Bruna)* — **reprovado**: "não está completo". O bloco monta a função
  só com o que o motor gravou, então diz "completa" com 2 de 5 acessos.
  **Não corrigido.**

### Por sistema — a primeira que casar decide

**#19 · Sistema sem extrato** — nenhum caso. · **OK**
- Os 7 sistemas do projeto têm extrato. A regra existe para o dia em que um
  arquivo não chegar — e já quase aconteceu: em 01/09 o SICA_RA veio num
  layout novo e o leitor leu ZERO acesso sem dar erro.

**#20 · Pelo menos um aderente → Aderente** — 5.925. · **OK**

**#20a · Perfil excessivo** — 121 casos, 173 perfis. · **OK**
- *29/07 (área, 1º retorno)* — pedido: "acessos necessário análise — acessos
  onde ele pode ter mais um perfil".
- *28/08* — mudança: o extra passou a aparecer no perfil atual. Antes a tela
  afirmava o que a pessoa tinha, e afirmava errado. Separado em VER (sempre) e
  COBRAR (só com a flag, hoje desligada — cobrar 130 casos de uma vez é
  decisão da área).
- *18/09* — correção de número: são 130 casos e 186 perfis, não 141 e 178 como
  dizia o roteiro de 08/09.

**#20b · Os outros perfis previstos que ela tem** — 158 linhas ganharam perfil.
· **OK**
- *22/09* — mudança: o campo só trazia o perfil que casou mais os não
  previstos; o perfil previsto que ela tinha e não foi o escolhido sumia. A
  tela dizia "tem 1 perfil" para quem tem dois.

**#21 · Provável desligamento** — 37. · **OK**
- *12/06* — nasceu quando ainda não havia base de desligados e "perdeu o
  acesso" era a única pista.
- *15/09 (usuário)* — mudança, textual: "se estão ativos é porque ainda têm
  acesso, pode seguir normalmente". Passou a exigir **também** ter sumido do
  arquivo de ativos. Com isso 318 pessoas voltaram como "Incluir Acesso", e a
  regra caiu de 323 para 37 casos.

**#22 · B1 — limiar de 30%** — **1.176 inclusões suprimidas**. · **ACHADO**
- *Desenho original* — evitar inundar a fila com esperado irrelevante quando a
  matriz é abrangente demais.
- *09/09 (Bruna)* — reclamação: "gente ativa some da Consulta". A regra **não**
  mudou; criou-se o Não Mapeado (#29) como contorno.
- *18/09 (nós → ela)* — pergunta 3.2: "quer que passem a aparecer como Incluir
  Acesso?" **Sem resposta.**
- *22/09 (Bruna)* — de novo: o Marcelo do SYSTUR "seguiu sem vir o perfil
  mapeado", e "95 do SICA Esfera são relacionados à matriz CCO".
- **O mecanismo:** a CCO atribui por centro de custo + gestor, mas o limiar
  filtra por adesão do **cargo**. Chaves diferentes. BRENDA, ANALISTA
  FINANCEIRO SR: a CCO diz que o time dela usa SICA Esfera, mas 0 das 12
  pessoas com o cargo dela usam → suprimida. No SICA_RA o mesmo cargo tem 58%
  e passa.
- Origem das supressões (aproximado): matrizes 769 · CCO 187. Por sistema:
  SYSTUR 401 · SICA_RA 231 · SIGOT 172 · SICA_ESFERA 82 · ORACLE 49 · IC 21.

**#23 · Sem acesso → Incluir Acesso** — 3.682. · **OK**

**#24 · Ambíguo → Em Análise** — 927. · **OK**
- *09/09 (Bruna, "Testes 2")* — pedido: no SYSTUR a pessoa só pode ter um
  perfil, e a Consulta listava cada candidato como uma linha ("faltam 5").
  Virou uma linha só: "Tem hoje X · Esperado: 1 de N opções".

**#25 · 1 × 1 que não casa → Alterar Perfil** — 318. · **OK**

### Caminhos paralelos

**#26 · SIG por espelho** — 607 linhas. · **—**
- *24/06 (usuária)* — decidido: o SIG não tem matriz; o esperado é o padrão do
  grupo, presente em ≥70% dos colegas que usam SIG, com mínimo de 2 colegas.

**#27 · Franqueado por matriz própria** — 4.969 linhas. · **—**
- *31/08 (Bruna, textual)* — pedido: "para franqueado não tem a questão de
  espelho".
- *04/09 (Bruna)* — repetiu olhando o print com a origem "Espelho —
  franqueados". Implementado: franqueado saiu do espelho.
- *Consequência aceita:* franqueado sem acesso nenhum deixou de receber
  sugestão de inclusão — sem o tipo de loja no cadastro, a matriz não diz qual
  perfil conceder, e inventar a partir dos colegas era o que ela vetou. São
  ~5.400 pessoas.

**#28 · Terceiro e prestador por espelho** — 1.483 linhas; 85 acessos sem par. ·
**—**
- *30/07* — regra 2.6: sem grupo com padrão não gera linha, para não inflar a
  fila com ruído.
- *11/09* — mudança: a comparação passou a ignorar maiúscula, acento e espaço.
  "gestao de acessos" e "GESTAO DE ACESSOS" contavam como perfis diferentes.

### Fallback e pós-processamento

**#29 · Não Mapeado** — 589. · **OK**
- *09/09 (Bruna)* — reclamação: colaborador ativo que não aparecia na Consulta.
  Eram 6.747 de 13.638 ativos (49%) com zero linha em qualquer lugar do painel.
  Mudança: o status passou a ser salvo como informativo.
- *15/09 (Bruna)* — pedido: o rótulo "Sem Expectativa" virou **"Não Mapeado"**,
  com a frase dela: "Não tem mapeamento localizado para o centro de custo."
- *17/09 (Bruna)* — pedido: quem não tem mapeamento não pode aparecer como
  "Aderente". Virou "Sem perfis mapeados". Entregue em 18/09.

**#30 · Sumiu dos ativos não ganha Não Mapeado** — 27. · **OK**
- *15/09 (usuário)* — pedido, junto com a #16.

**#31 · Conta indefinida** — 11. · **OK**
- *31/08 (Bruna, textual)* — pedido: "se a pessoa estiver com acesso nesse
  status, inativo, bloqueado ou P, e ela poder ter o acesso, trazer como a
  incluir e o perfil que pode ser liberado para ela".
- *08/09* — correção nossa: franqueado ficou **fora** desse ramo. A conversão
  apagava o achado de escalada de privilégio (atendente com perfil de gerente
  virava só "Incluir Acesso").

**#32 · Conta bloqueada explica o Sem Acesso** — **121**. · **ACHADO**
- *22/07 (área)* — conta bloqueada não é acesso.
- *10/08 e 25/08 (área)* — pedido: explicar na tela, senão o painel mostra o
  login preenchido e manda CRIAR um acesso que já existe. A ação é desbloquear.
- **Achado:** só 121 linhas carregam o aviso, quando existem **536** pares
  pessoa/sistema na situação. Ver o achado final.

**#33 · Mais de um perfil no mesmo sistema** — 419. · **OK**
- *17/09 (Bruna)* — pedido: aviso "Usuário com mais de um acesso" no SYSTUR,
  onde não se pode ter mais de um perfil. Entregue em 18/09 como **aviso**,
  sem virar pendência.
- *22/09 (Bruna, textual)* — mudança: "Mais de um perfil não pode ficar nada
  como aderente, ele precisa vir como pendência para análise".
- *22/09 (usuário)* — decisão de escopo: vale para **todos os sistemas**, não
  só o SYSTUR. Medido: 419 linhas, e a fila de pendências vai de 826 para
  1.245. **Construído, não commitado.**

**#34 · Filtro de gravação** — descarta `SEM_DADOS`. · **ACHADO** (ver #19)

**#35 · O que é pendência** — 1.245 (Divergente + Em Análise). · **OK**
- *Fase 1 (Bruna)* — decidido: "Incluir Acesso" é informativo, não pendência —
  quem não tem o acesso não é irregularidade a corrigir.
- *25/08 (área)* — "Aderente é quem não tem pendência nenhuma" — a tela agrega
  por pessoa, enquanto o motor julga por sistema.
- *22/09 (Bruna, no Teams)* — reforço: "não precisa vir no incluir pendente,
  **mas precisa vir na consulta**". Hoje a combinação #13 + #22 impede isso.
- **Em contradição:** na mesma conversa, o nosso lado disse que alguns casos de
  "incluir acesso" precisam aparecer em pendentes. Os dois lados dizem coisas
  opostas — **precisa voltar para ela**.

## Fase 5 — Pós-validação

**#36 · Revalidação pós-transferência** — 2.826 acessos julgados. · **—**
- *17/09 (Bruna)* — reclamação: "visualização muito confusa". Pedido: três
  blocos — o que tem, o que deveria ter, o que alterar. Entregue em 18/09.
- *22/09 (Bruna)* — **reprovado**: quer em linhas, uma por sistema, no formato
  "Sistema | Tem atualmente | Mapeando nova área | Incluir/excluir/alterar".
  **Não construído.**

**#37 · Ciclo de vida** — 9.833 linhas, 6.793 com data de aderente, **0
resolvidos**. · **—**

**#38 · Eventos e histórico** · **—**

**#39 · Saídas em Excel** — 11.459 registros. · **—**
- *22/09 (Bruna, no Teams)* — pedido: poder exportar sem agrupamento, porque
  ao filtrar por sistema a matrícula some (ela está na linha-pai, o sistema na
  linha-filha). **Construído, não commitado.**

---

## O achado que atravessa duas regras

**#13 + #22, com efeito na #32.**

1. A conta da pessoa está bloqueada ou inativa → **#13** descarta o acesso;
2. ela fica com zero acesso → cai em **#22**;
3. o cargo tem adesão baixa → a linha é descartada;
4. a pessoa **não aparece em lugar nenhum** — nem na Consulta.

O aviso da **#32** só é carimbado em linhas que sobreviveram. Quem o limiar
matou nunca chega lá — por isso a #32 marca **121** linhas, quando existem
**536** pares pessoa/sistema nessa situação: SIG 327 · SICA_RA 187 ·
SICA_ESFERA 22.

Cada regra está certa isoladamente. A combinação, ninguém decidiu. E ela
contraria diretamente o que a área pediu em 22/09: *"precisa vir na consulta"*.

## Perguntas em aberto, por regra

| Regra | Pergunta | Desde |
|---|---|---|
| #5 | A matriz do CC 05.12.02.01 mudou de propósito em 18/08? | 18/09 |
| #22 | O limiar de 30% deve continuar cortando? | 18/09 |
| #33 | As 5 contas com 42 perfis (são robôs) entram? | 18/09 |
| #3 | Por que 556 matrículas aparecem repetidas nos desligados? | 18/09 |
| #27 | Os perfis de exceção têm aprovação da Governança de SI? | 08/09 |
| #27 | As 11 equivalências de cargo derivadas do uso estão certas? | 08/09 |
| #35 | "Incluir Acesso" deve ou não virar pendência? | 22/09 |

## Ressalva de precisão

A reconstrução da origem das supressões da #22 soma 956, e o motor registra
1.176. A diferença são os casos de conta bloqueada: a reconstrução exclui quem
tem qualquer acesso, enquanto o motor descarta o acesso bloqueado e a pessoa
**chega** ao limiar.

É sintoma do mesmo problema de fundo: enquanto o motor contar descartes sem
registrar **quem** foi descartado, qualquer conferência depende de reconstruir
o raciocínio por fora — e a reconstrução erra.
