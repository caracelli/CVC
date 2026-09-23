# -*- coding: utf-8 -*-
"""Gera ENTREGA/CHECKLIST_REGRAS_CVC_IAM_2026-09-22.docx.

Checklist das regras na ORDEM DE EXECUCAO. Para cada uma: COMO E' FEITO (quem
entra, o que e' comparado, o que sai) e, quando mudou, A DATA e O QUE FOI
MUDADO.

Descricao tirada do codigo, nao de paragrafo: o denominador do limiar exclui
terceiro, cargo com menos de 2 pessoas nao e' avaliado, o casamento de perfil
ignora acento e no IC ignora underscore, etc.

Fontes: src/aplicacao/casos_de_uso/*.py, docs/CRONOGRAMA.md (26 cards), os
roteiros de 06/08, 08/09, 11/09 e 18/09, o retorno de 22/09 e o Teams.

Uso:  python scripts/gerar_checklist_regras.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gerar_roteiro_ajustes as base  # noqa: E402

from docx import Document  # noqa: E402
from docx.shared import Pt, Cm, RGBColor  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: E402

h1, shade = base.h1, base.shade
AZUL, CINZA, TEXTO = base.AZUL, base.CINZA, base.TEXTO
VERMELHO = base.VERMELHO

RAIZ = Path(__file__).resolve().parent.parent
OUT_DOCX = RAIZ / "ENTREGA" / "CHECKLIST_REGRAS_CVC_IAM_2026-09-22.docx"

NOTA = "__nota__"

# (codigo, titulo, como e' feito, [ (data, o que mudou), ... ])
FASES = [
 ("Fase 1 — Importação", [
  ("#1", "Dobra das interações",
   "Cada usuário do painel grava as próprias tratativas e quarentenas num arquivo "
   "só dele, dentro da pasta INTERACOES — um escritor por arquivo, que é o que "
   "torna seguro vários usuários ao mesmo tempo na rede. O Processador lê todos "
   "esses arquivos, grava o conteúdo nas tabelas de quarentena e resolução, e "
   "então renomeia a pasta inteira de uma vez, criando uma nova e vazia no lugar.",
   []),

  ("#2", "Diretório AD (Card 3)",
   "O diretório de franqueados e prestadores é importado ANTES da base de RH. "
   "Cada identidade recebe uma matrícula formada por prefixo mais login — FRANQ- "
   "ou PREST- —, então ela nunca colide com a matrícula real de um CLT, e a carga "
   "do RH depois opera em chaves separadas. Quem vence quando os dois poderiam "
   "casar não depende dessa ordem: está escrito na vinculação (#8), onde o CLT "
   "tem precedência.",
   [("22/07", "o diretório passou a ser a base PRINCIPAL de identidade, e não um "
              "complemento do RH.")]),

  ("#3", "Importação do RH (Cards 3 e 4)",
   "As bases de ativos e de desligados são carregadas por merge: a linha nova "
   "atualiza a existente e as ausentes continuam gravadas. É de propósito — "
   "apagar e reinserir faria sumir quem não veio no arquivo do dia. Por isso "
   "cada linha guarda de qual arquivo veio e quando foi importada, que é o que "
   "permite mais tarde saber quem sumiu (#16). O snapshot do histórico é gravado "
   "ANTES do merge; se fosse depois, a mudança de cargo ou gestor já estaria "
   "sobrescrita e a detecção de transferidos perderia o de/para.",
   []),

  ("#4", "Padronização do RH (Card 4)",
   "Os campos usados como chave — cargo, centro de custo, gestor — são "
   "normalizados: maiúsculas, acentos removidos e espaços internos colapsados. "
   "É essa forma normalizada que casa com as matrizes depois.",
   []),

  ("#5", "Importação das matrizes (Cards 15 e 16)",
   "São duas planilhas independentes. A matriz de perfis por sistema é indexada "
   "por centro de custo + cargo. A matriz organizacional (CCO) é indexada por "
   "centro de custo + gestor, e cada linha dela traz também a função. A carga é "
   "por substituição POR SISTEMA: ao receber um arquivo, os mapeamentos daquele "
   "sistema são apagados e regravados, preservando os dos demais. Só entram os "
   "sistemas marcados como ativos na configuração.",
   [("18/08", "a matriz do SYSTUR trocou de aba, de cerca de 2.100 para 546 "
              "linhas. O centro de custo 05.12.02.01 perdeu GERENTE ATENDIMENTO "
              "e GERENTE DE OPERAÇÕES. A mudança veio dentro do arquivo — não foi "
              "pedida nem avisada.")]),

  ("#6", "Importação dos extratos (Cards 6 a 13)",
   "Cada exportação de sistema traz a base inteira com o status do dia, então o "
   "arquivo mais recente substitui o anterior; quando o nome não tem data, vale a "
   "data do arquivo. O leitor não conta linhas fixas: procura a linha de "
   "cabeçalho e descobre o separador pelos nomes de coluna que espera encontrar.",
   [("08/09", "o leitor passou a procurar o cabeçalho pelos nomes das colunas. "
              "Motivo: o SICA_RA chegou em 01/09 num layout novo e o leitor "
              "antigo lia ZERO acesso sem dar erro nenhum."),
    ("18/09", "a tela de bases passou a mostrar quantas linhas o arquivo tinha e "
              "quantas entraram na aplicação.")]),

  ("#7", "Importação do SIG (Card 12)",
   "O SIG vem matricial: pessoas nas linhas, perfis nas colunas, marcação no "
   "cruzamento. Um arquivo de-para converte isso numa lista de acessos, uma "
   "linha por pessoa e perfil. Se o arquivo não estiver na pasta, o passo é "
   "registrado como não utilizado e o processamento segue.",
   []),
 ]),

 ("Fase 2 — Vinculação do acesso à pessoa (Card 7)", [
  ("#8", "Cascata de seis chaves  ·  regra 1.1 de 06/08",
   "Cada linha de acesso é cruzada contra as identidades tentando seis chaves, "
   "em ordem, e parando na primeira que casa: CPF exato, e-mail exato, login "
   "exato, CPF parcial combinado com o nome, nome exato e, por último, "
   "semelhança de nome. Cada nível grava o método usado e uma pontuação de "
   "confiança, de 1,00 no CPF a 0,50 na semelhança. A semelhança de nome NÃO "
   "vincula: ela apenas registra os candidatos no campo próprio, para não "
   "inventar dono. Quando o sistema traz CPF limpo, o primeiro nível resolve a "
   "maioria; os outros existem para os extratos com CPF mascarado ou ausente.",
   [("01/09", "entrou o nível por LOGIN, necessário para casar as identidades do "
              "diretório, que não têm CPF.")]),
 ]),

 ("Fase 3 — Divergências (Cards 19, 20 e 22)", [
  ("#9", "Acesso de desligado  ·  regra 3.1 de 06/08",
   "São considerados os acessos cuja conta está ATIVA e cujo dono aparece na base "
   "de desligados. O dono é procurado por UNIÃO de três chaves: a matrícula "
   "vinculada no passo anterior, o CPF que vem no próprio extrato e o login. "
   "Casar só por matrícula subconta, porque a vinculação cruza contra a base de "
   "ATIVOS — o acesso de um desligado costuma ficar sem matrícula anexada.",
   [("10/08", "quando a conta pertence a alguém ativo hoje com o MESMO login, "
              "deixou de ser acesso a revogar: é a conta que a pessoa usa. Só "
              "aponta quando o ativo tem login diferente e a conta antiga sobra.")]),

  ("#10", "Conta de serviço",
   "Antes de montar a lista de revogação, o login de cada acesso é comparado "
   "contra os prefixos configurados. Batendo, o acesso sai da lista e recebe uma "
   "categoria própria — continua consultável na tela, só não é cobrado. A lista "
   "de prefixos fica na configuração, não no código, para a área mexer sem "
   "recompilar.",
   [("31/08", "regra criada, depois do apontamento de usuários sistêmicos "
              "aparecendo entre os desligados. Revogar robô derruba produção.")]),

  ("#11", "Acesso sem vínculo no RH  ·  regra 1.3 de 06/08",
   "É o que sobra da cascata: as linhas de acesso em que nenhuma das seis chaves "
   "encontrou identidade. Elas aparecem na tela com a ação “Usuário Não "
   "Encontrado”, com o login no lugar do nome.",
   []),

  ("#12", "Detecção de transferidos  ·  regra 3.2 de 06/08 (Card 22)",
   "Não vem de arquivo: sai do histórico do próprio RH. A cada carga, a linha "
   "nova é comparada com a anterior da mesma matrícula, e a pessoa entra na "
   "revisão se mudou cargo, centro de custo, departamento OU gestor. O de/para é "
   "gravado, e é ele que permite a revalidação do Card 23. Não há janela de "
   "tempo: a pessoa fica em revisão enquanto estiver ativa e não for tratada.",
   [("29/07", "definido que a mudança de GESTOR também entra, não só cargo e "
              "centro de custo.")]),
 ]),

 ("Fase 4 — Motor de validação (Card 17) · preparação", [
  ("#13", "O que conta como acesso  ·  regra 1.2 de 06/08",
   "Ao montar a lista de acessos de cada pessoa, o registro cuja situação no "
   "extrato seja inativa, bloqueada ou revogada é DESCARTADO da lista. Ele deixa "
   "de existir para todas as regras seguintes: a partir daí a pessoa é tratada "
   "como se não tivesse aquele acesso. O par pessoa/sistema fica anotado à parte, "
   "para a regra #32 poder explicar o caso mais adiante.",
   [("22/07", "regra definida: conta revogada não conta como acesso.")]),

  ("#14", "Conta com status indefinido  ·  regra 2.9 de 06/08",
   "Quando o status vem vazio ou como pendente, o acesso CONTA normalmente na "
   "lista, mas o par pessoa/sistema é anotado. No fechamento (regra #31) essa "
   "linha é revista, em vez de se assumir que a conta está ativa.",
   [("10/08", "definido que não se assume conta ativa.")]),

  ("#15", "Medição da adesão do cargo ao sistema",
   "Para cada cargo, conta-se quantas pessoas daquele cargo realmente têm acesso "
   "em cada sistema (numerador) sobre o total de pessoas do cargo (denominador). "
   "O denominador é a população de ativos EXCLUINDO terceiros. Cargo com menos "
   "de duas pessoas não é avaliado: a adesão dele é tratada como 100%, para não "
   "bloquear por falta de base. É só o cálculo — quem usa o resultado é o "
   "limiar (#22).",
   []),

  ("#16", "Quem sumiu do arquivo de ativos",
   "Como a base de RH acumula (#3), quem saiu continua gravado com o arquivo "
   "antigo no campo de origem. Para cada população — CLT, terceiro, prestador — "
   "descobre-se qual é o arquivo mais recente, olhando a linha com maior data de "
   "importação, e são dadas como sumidas as pessoas cujo arquivo de origem é "
   "outro. Sem data ou sem arquivo de origem, ninguém some. Se o mais recente "
   "cobre menos da METADE da população, também ninguém some e um aviso é "
   "registrado no log — protege contra um export parcial esconder meia empresa.",
   [("15/09", "regra criada, para que quem saiu da base não continue aparecendo "
              "como ativo.")]),
 ]),

 ("Fase 4 · como a lista de acessos possíveis é montada", [
  ("#17", "A lista de possíveis acessos do usuário  ·  regras 2.1 e 2.2 de 06/08",
   "É a base de tudo que vem depois. Para cada pessoa, duas buscas: na matriz de "
   "perfis por sistema, pela dupla centro de custo + CARGO; e na CCO, pela dupla "
   "centro de custo + GESTOR. Os resultados são reunidos num conjunto ÚNICO por "
   "sistema, cada perfil guardando de qual matriz veio. Perfil repetido conta uma "
   "vez só, e o dedup usa a mesma normalização do casamento — a matriz traz o "
   "mesmo perfil grafado de dois jeitos, e sem isso a tela mostrava “9 opções” e "
   "“8 opções” para a mesma lista. Quando o mesmo perfil vem das duas matrizes, "
   "vence o da matriz por cargo. O SIG é excluído da CCO: ele tem caminho "
   "próprio (#26).",
   [("—", "correção: avaliadas separadas, a mesma pessoa saía Aderente pela "
          "matriz e Alterar Perfil pela CCO na mesma rodada.")]),

  ("#18", "A função que originou o acesso",
   "Cada perfil vindo da CCO carrega o nome da função daquela linha da planilha. "
   "Depois de gerar os registros da pessoa, a função é carimbada na linha "
   "correspondente, casando por sistema e perfil. Linha vinda da matriz por cargo "
   "fica sem função — aquela planilha não traz esse dado.",
   [("17/09", "regra criada, a pedido da área.")]),
 ]),

 ("Fase 4 · o julgamento, sistema a sistema", [
  (NOTA, "Para cada pessoa e cada sistema em que ela tem acessos possíveis, as "
         "regras abaixo são avaliadas nesta ordem. A primeira que casar decide a "
         "linha; as seguintes não são nem consultadas.", None),

  ("#19", "Sistema sem extrato",
   "Se o sistema não tem nenhum registro de acesso no banco, não há como dizer se "
   "a pessoa tem ou não tem: o resultado sai como “sem dados”. Esse resultado não "
   "está na lista dos que são guardados (#34), então a linha é descartada na "
   "gravação.",
   []),

  ("#20", "Aderente",
   "São considerados aderentes os usuários que têm PELO MENOS UM dos perfis da "
   "lista de possíveis. A comparação é por nome de perfil, ignorando maiúsculas, "
   "acentos e espaços duplicados; no IC, ignora também a diferença entre "
   "underscore e espaço, porque o extrato escreve IC_CONSULTA e a matriz escreve "
   "IC CONSULTA. Basta um casar — não é exigido ter todos os possíveis. A linha "
   "gravada usa o primeiro perfil que casou como referência, e no campo do que a "
   "pessoa tem vai esse perfil mais os demais que ela possui.",
   []),

  ("#20a", "Perfil a mais, dentro do Aderente",
   "Ainda na linha de aderente, os perfis que a pessoa tem e que NÃO estão na "
   "lista de possíveis são acrescentados ao campo do que ela tem, e a linha "
   "recebe um motivo indicando isso. Ver e cobrar são coisas separadas: por "
   "configuração, hoje o perfil a mais aparece na tela mas não vira pendência.",
   [("28/08", "o perfil a mais passou a aparecer. Antes a linha gravava só o "
              "perfil que casou, e a tela afirmava o que a pessoa tinha — "
              "afirmando errado.")]),

  ("#20b", "Os outros possíveis que a pessoa tem",
   "Também entram no campo os demais perfis da lista de possíveis que a pessoa "
   "tem, além do que foi usado como referência. Antes só o primeiro casamento "
   "era gravado.",
   [("22/09", "regra criada. Até aqui esse perfil sumia do campo, e a tela dizia "
              "“tem 1 perfil” para quem tem dois.")]),

  ("#21", "Provável desligamento",
   "A pessoa é retirada — nenhuma linha é gerada — quando reúne três condições ao "
   "mesmo tempo: já constou como aderente naquele sistema em alguma rodada "
   "anterior (isso vem da tabela de ciclo de vida), hoje está com zero acesso "
   "nele, e não veio no arquivo de ativos mais recente (#16). Se for engano, o "
   "acesso é reincluído no sistema e ela reaparece como aderente na próxima "
   "rodada: a regra se autocorrige.",
   [("15/09", "passou a exigir TAMBÉM ter sumido do arquivo de ativos. Antes "
              "bastava ter perdido o acesso, e isso escondia gente ativa.")]),

  ("#22", "Limiar de 30% de adesão  ·  regra 2.5 de 06/08",
   "Chegando aqui, a pessoa está sem acesso no sistema e tem perfis possíveis. "
   "Antes de gerar a inclusão, consulta-se a adesão medida na #15 para o CARGO "
   "dela naquele sistema. Se for menor que 30%, nada é gerado e a pessoa não "
   "aparece para aquele sistema. O corte é sempre pelo cargo — inclusive quando "
   "os perfis possíveis vieram da CCO, que os atribuiu por centro de custo e "
   "gestor. O valor é configurável: zero desliga a regra.",
   [("25/08", "solicitado que, havendo mapeamento na matriz, o acesso possível "
              "apareça na Consulta mesmo sem a pessoa tê-lo. O limiar corta "
              "antes disso, então o pedido não se cumpre nesses casos."),
    ("17/09", "reaberto no documento “Usuário que veio sem mapeamento mas tem "
              "acesso previsto na matriz”."),
    ("22/09", "reaberto de novo: o caso do SYSTUR que “seguiu sem vir o perfil "
              "mapeado” e os 95 do SICA Esfera. PENDENTE de decisão.")]),

  ("#23", "Inclusão (Incluir Acesso)",
   "São considerados os usuários ATIVOS que não têm nenhum acesso naquele "
   "sistema, mas têm acessos possíveis, e que passaram pelo limiar. A linha "
   "gravada traz a LISTA INTEIRA dos perfis possíveis para ele naquele sistema — "
   "não um só —, para a Consulta poder mostrar tudo o que ele poderia receber. É "
   "informativa: não entra na contagem de pendências.",
   [("29/07", "solicitado separar o “sem acesso” das pendências: deixou de sair "
              "na fila e passou a ser informativo, só na Consulta. Na época as "
              "pendências caíram de 7.090 para 792."),
    ("25/08", "solicitado que, quando o usuário não tem o acesso mas está "
              "mapeado na matriz, a Consulta mostre QUAL acesso ele pode ter "
              "naquele sistema. É o que a linha passou a listar.")]),

  ("#24", "Em Análise  ·  regra 2.7 de 06/08",
   "São considerados os usuários que TÊM acesso no sistema, nenhum deles casando "
   "com a lista de possíveis, e em que há mais de um perfil possível OU mais de "
   "um acesso. Como não dá para dizer qual seria o certo, o caso vai para análise "
   "humana. A linha traz todos os acessos atuais e, do lado do esperado, as "
   "opções possíveis.",
   [("09/09", "no SYSTUR, onde a pessoa só pode ter um perfil, a Consulta listava "
              "cada opção como uma linha e lia como “faltam 5”. Passou a ser uma "
              "linha só: “Tem hoje X · Esperado: 1 de N opções”.")]),

  ("#25", "Alteração (Alterar Perfil)",
   "Sobra o caso mais simples: exatamente um perfil possível, exatamente um "
   "acesso, e os dois não são o mesmo. A linha sai como Alterar Perfil, com o "
   "que a pessoa tem de um lado e o que deveria ter do outro.",
   []),
 ]),

 ("Fase 4 · populações sem matriz", [
  (NOTA, "Terceiro, franqueado e prestador não passam pelas regras acima: não "
         "têm cargo e centro de custo nas matrizes. Para eles o esperado é "
         "inferido dos colegas, e o SIG segue o mesmo caminho por não ter "
         "matriz própria.", None),

  ("#26", "SIG pelo espelho dos colegas  ·  regra 2.3 de 06/08",
   "O SIG não tem matriz por cargo nem usa CCO. Cada pessoa é agrupada com os "
   "colegas por centro de custo + gestor + cargo; se esse grupo não tiver pelo "
   "menos dois colegas que usam o SIG, cai para centro de custo + gestor. O "
   "esperado do grupo é o conjunto de perfis presentes em pelo menos 70% dos "
   "colegas que usam o SIG. Comparando com o que a pessoa tem: igual ao padrão é "
   "aderente; não usa o SIG é inclusão; tem parte do padrão e falta o resto é "
   "alteração; tem algo além do padrão é análise. Sem grupo comparável, ou grupo "
   "que não converge em padrão nenhum, só reporta se a própria pessoa usa o SIG "
   "— senão o sistema não se aplica a ela e nada é gerado.",
   [("24/06", "critério definido com a área.")]),

  ("#27", "Franqueado pela matriz de lojas",
   "A matriz do franqueado cruza cargo, tipo de atendimento e tipo de loja. Os "
   "dois últimos não existem no cadastro — local de trabalho e filial vêm "
   "vazios —, mas estão codificados no NOME do perfil: ATEND_PUBLIC_LJT_… é "
   "atendimento ao público em loja terceirizada. Por isso a regra só fecha ao "
   "contrário: parte do perfil que a pessoa TEM e diz se o cargo dela o "
   "autoriza. Ela valida aderência e não gera inclusão. O cargo do RH é "
   "traduzido para o cargo da matriz por um de-para derivado do próprio uso: se "
   "pelo menos 70% dos acessos de um cargo apontam para o mesmo cargo da matriz, "
   "ele é tratado como equivalente; cargo que já existe na matriz não ganha "
   "tradutor. Três perfis de exceção da Governança nunca entram como esperado.",
   [("31/08", "franqueado saiu do espelho de colegas e passou a ser validado "
              "apenas pela matriz."),
    ("04/09", "confirmado. Consequência aceita: franqueado sem acesso nenhum "
              "deixou de receber sugestão de inclusão, porque sem o tipo de loja "
              "não dá para dizer qual perfil conceder.")]),

  ("#28", "Terceiro e prestador pelo espelho  ·  regras 2.4 e 2.6 de 06/08",
   "Mesmo mecanismo do SIG, aplicado a todos os sistemas, mas com chaves "
   "próprias: terceiro agrupa por empresa + supervisor; franqueado e prestador "
   "do diretório agrupam por empresa + gestor, com queda para só o gestor. O "
   "padrão é o perfil presente em pelo menos 70% dos colegas do grupo que usam "
   "aquele sistema. Quando o grupo existe mas não converge num padrão, nada é "
   "gerado — a área pediu para não inflar pendência com ruído.",
   [("11/09", "a comparação passou a ignorar maiúscula, acento e espaço. Antes "
              "“gestao de acessos” e “GESTAO DE ACESSOS” contavam como perfis "
              "diferentes.")]),
 ]),

 ("Fase 4 · fechamento", [
  ("#29", "Não Mapeado",
   "Depois de percorrer todos os sistemas, se a pessoa não gerou NENHUMA linha — "
   "porque não tem acessos possíveis em lugar nenhum, ou porque tudo o que tinha "
   "foi cortado pelo limiar —, ela recebe uma linha informativa, sem sistema, "
   "dizendo que não há mapeamento localizado para o centro de custo dela. É o que "
   "impede a pessoa de desaparecer da tela inteira. Atenção ao termo: no "
   "documento de regras da Fase 1, “Não Mapeado” significava outra coisa — um "
   "acesso sem dono no RH, que hoje se chama “Usuário Não Encontrado” (#11).",
   [("10/08", "solicitado que a tela DISTINGA dois casos: “a matriz não prevê "
              "nada para este centro de custo e cargo” e “a matriz prevê e a "
              "pessoa não tem”. Hoje os dois leem a mesma frase. PENDENTE."),
    ("09/09", "regra criada. Até então quem não tinha expectativa relevante "
              "ficava sem nenhuma linha em qualquer lugar do painel."),
    ("15/09", "o rótulo “Sem Expectativa” virou “Não Mapeado”, com a frase “Não "
              "tem mapeamento localizado para o centro de custo.”."),
    ("17/09", "deixou de aparecer como “Aderente” e passou a aparecer como “Sem "
              "perfis mapeados”.")]),

  ("#30", "Quem sumiu dos ativos não recebe o Não Mapeado",
   "A linha da #29 não é gerada para quem está na lista de sumidos da #16. Evita "
   "que um desligado ainda acumulado na base apareça como ativo sem mapeamento. "
   "Quem caiu na regra de provável desligamento (#21) também não recebe — aquela "
   "regra tem dono próprio na fase de desligados.",
   [("15/09", "regra criada, junto com a #16.")]),

  ("#31", "Conta que não está ativa vira inclusão",
   "Passando por todos os registros já gerados: a linha de Aderente ou de Alterar "
   "Perfil cujo par pessoa/sistema foi anotado na #14 é convertida. Ela passa a "
   "Incluir Acesso, o campo do que a pessoa tem é LIMPO — afirmar posse de uma "
   "conta que não está ativa seria o mesmo erro ao contrário — e a linha mostra o "
   "perfil que pode ser liberado. Franqueado não entra nesta conversão.",
   [("31/08", "regra criada a pedido da área."),
    ("08/09", "o franqueado ficou de fora. A conversão apagava o veredito da "
              "matriz: um atendente com perfil de gerente virava apenas “Incluir "
              "Acesso”, e a tela passava a sugerir CONCEDER um acesso que ele já "
              "tinha indevidamente.")]),

  ("#32", "Conta bloqueada se explica na tela",
   "Passando pelas linhas de Incluir Acesso com o campo de perfil atual vazio: se "
   "o par pessoa/sistema foi anotado na #13 como conta revogada, a linha recebe o "
   "motivo dizendo que a conta existe e está bloqueada, e que a ação é "
   "DESBLOQUEAR, não criar. Sem isso a tela mostra o login preenchido e manda "
   "criar um acesso que já existe.",
   [("25/08", "aviso criado.")]),

  ("#33", "Mais de um perfil no mesmo sistema",
   "Passando pelas linhas de Aderente: contam-se os perfis DISTINTOS no campo do "
   "que a pessoa tem, usando a mesma normalização do casamento — duas grafias do "
   "mesmo perfil contam como um. Sendo mais de um, a linha passa a Em Análise e "
   "recebe o motivo, preservando o motivo que já tivesse. Não é o perfil a mais "
   "(#20a): aqui não importa se a matriz prevê os dois; o limite é um.",
   [("17/09", "criado como AVISO na tela, só para o SYSTUR, sem virar pendência."),
    ("22/09", "passou a ser PENDÊNCIA: “mais de um perfil não pode ficar nada "
              "como aderente, ele precisa vir como pendência para análise”. E o "
              "escopo deixou de ser só o SYSTUR: vale para todos os sistemas.")]),

  ("#34", "O que é guardado no banco",
   "Dos resultados gerados, só cinco são salvos: Aderente, Incluir Acesso, "
   "Alterar Perfil, Em Análise e Não Mapeado. O “sem dados” da #19 é descartado "
   "aqui. Cada linha salva nasce marcada como pendente ou como resolvida, "
   "conforme a regra #35.",
   []),

  ("#35", "O que conta como pendência",
   "Só Alterar Perfil e Em Análise nascem como pendência. Incluir Acesso e Não "
   "Mapeado nascem resolvidos: aparecem na Consulta, mas não entram na fila nem "
   "nos contadores — quem não tem o acesso não é irregularidade a corrigir.",
   [("29/07", "solicitado separar o “sem acesso” (Incluir Acesso) das "
              "pendências: virou informativo, só na Consulta. Pendências "
              "7.090 → 792; Em Análise 4.199 → 854."),
    ("25/08", "na tela, Aderente passou a ser quem não tem pendência nenhuma. A "
              "tela agrega por pessoa; o motor julga por sistema.")]),
 ]),

 ("Fase 5 — Pós-validação (Cards 23 a 26)", [
  ("#36", "Revalidação pós-transferência  ·  regra 3.3 de 06/08 (Card 23)",
   "O Card 22 diz quem mudou; aqui cada acesso é julgado. Para a pessoa "
   "transferida, monta-se o esperado nos DOIS momentos, com o mesmo critério de "
   "cada sistema: matriz mais CCO onde há matriz, espelho do grupo no SIG. O "
   "estado anterior vem do de/para gravado pelo Card 22. Para o grupo antigo "
   "usam-se os colegas que estão HOJE naquela chave — são os que ela deixou para "
   "trás. Daí saem as três leituras: o que ela tem, o que a nova área tem e ela "
   "não, e o que sobrou da área anterior.",
   [("17/09", "o detalhe passou a ter três blocos: o que a pessoa tem, o que "
              "deveria ter na nova área, e o que alterar, separando revogar de "
              "incluir.")]),

  ("#37", "Ciclo de vida do acesso",
   "Por par pessoa e sistema, registram-se as datas de pendência, de resolução "
   "por ticket e de aderência. Cada data só grava na primeira vez em que "
   "acontece, então reprocessar não altera o histórico. É a base do tempo de "
   "tratamento no Histórico e do tempo médio da Visão Geral. Todo o passo é "
   "blindado: qualquer erro é apenas registrado e não derruba o processamento. "
   "LIMITAÇÃO CONHECIDA E ADIADA: a resolução é gravada por matrícula, então uma "
   "matrícula tratada segue como resolvida mesmo que uma pendência NOVA apareça "
   "num processamento seguinte. Só se manifesta a partir da segunda rodada; a "
   "correção está especificada e prevista para a etapa do Jira.",
   []),

  ("#38", "Eventos e trilha de histórico",
   "Sobre o ciclo de vida, é gravado um log de eventos por pessoa e sistema, "
   "incluindo as reaberturas, e os marcos são projetados na trilha de histórico, "
   "uma linha por marco, de forma idempotente.",
   []),

  ("#39", "Geração das saídas (Card 9)",
   "Os relatórios em Excel são gerados a partir das mesmas tabelas que a tela "
   "lê, respeitando os filtros aplicados.",
   [("22/09", "a exportação passou a perguntar entre agrupado e analítico. No "
              "agrupado a matrícula fica na linha-pai e o sistema na linha-filha, "
              "então filtrar por sistema escondia a matrícula.")]),
 ]),
]


def regra(doc, cod, titulo, como, mudancas=None):
    if cod == NOTA:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(6)
        r = p.add_run(titulo)
        r.italic = True
        r.font.size = Pt(9)
        r.font.color.rgb = CINZA
        return

    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(13)
    p.paragraph_format.space_after = Pt(3)
    r = p.add_run(f"{cod}  {titulo}")
    r.bold = True
    r.font.size = Pt(10.5)
    r.font.color.rgb = AZUL

    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(3)
    r = p.add_run(como)
    r.font.size = Pt(9.5)
    r.font.color.rgb = TEXTO

    if not mudancas:
        return

    tbl = doc.add_table(rows=1, cols=2)
    tbl.style = "Table Grid"
    for i, rot in enumerate(("Mudou em", "O que foi mudado")):
        c = tbl.rows[0].cells[i]
        rr = c.paragraphs[0].add_run(rot)
        rr.bold = True
        rr.font.size = Pt(8)
        rr.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        shade(c, "1F2D5C")
    for data, oque in mudancas:
        cells = tbl.add_row().cells
        cells[0].width = Cm(2.4)
        cells[1].width = Cm(14.1)
        r0 = cells[0].paragraphs[0].add_run(data)
        r0.bold = True
        r0.font.size = Pt(8.5)
        r0.font.color.rgb = AZUL
        shade(cells[0], "EEF2F8")
        r1 = cells[1].paragraphs[0].add_run(oque)
        r1.font.size = Pt(8.5)
        r1.font.color.rgb = TEXTO


def resumo(doc):
    """Tabela final: tudo o que foi pedido, na ordem das datas, e se saiu.

    Montada a partir das MESMAS tuplas das regras — não há lista paralela para
    sair de sincronia com o corpo do documento."""
    import re
    itens = []
    for _fase, regras in FASES:
        for it in regras:
            cod, tit = it[0], it[1]
            if cod == NOTA:
                continue
            for data, oque in (it[3] if len(it) > 3 and it[3] else []):
                itens.append((data, cod, tit.split("  ·")[0], oque))

    def chave(d):
        m = re.match(r"(\d\d)/(\d\d)", d)
        return (int(m.group(2)), int(m.group(1))) if m else (0, 0)
    itens.sort(key=lambda x: chave(x[0]))
    pendentes = sum(1 for i in itens if "PENDENTE" in i[3])

    h1(doc, "O que foi pedido e o que foi entregue")
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    r = p.add_run(
        f"São {len(itens)} mudanças registradas, de junho até hoje: "
        f"{len(itens) - pendentes} entregues e {pendentes} pendentes. A tabela "
        "repete, em ordem de data, o que já está no corpo do documento — serve "
        "para ver o conjunto de uma vez.")
    r.font.size = Pt(9.5)
    r.font.color.rgb = TEXTO

    tbl = doc.add_table(rows=1, cols=4)
    tbl.style = "Table Grid"
    for i, rot in enumerate(("Data", "Regra", "O que foi pedido / mudado", "Saiu?")):
        c = tbl.rows[0].cells[i]
        rr = c.paragraphs[0].add_run(rot)
        rr.bold = True
        rr.font.size = Pt(8)
        rr.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        shade(c, "1F2D5C")
    for data, cod, tit, oque in itens:
        pend = "PENDENTE" in oque
        txt = oque.replace(" PENDENTE.", ".").replace(" PENDENTE de decisão.", ".")
        cells = tbl.add_row().cells
        larg = (Cm(1.6), Cm(4.4), Cm(9.0), Cm(1.6))
        for c, w in zip(cells, larg):
            c.width = w
        for c, v, b in ((cells[0], data, True),
                        (cells[1], f"{cod} {tit}", False),
                        (cells[2], txt, False),
                        (cells[3], "pendente" if pend else "sim", True)):
            rr = c.paragraphs[0].add_run(v)
            rr.bold = b
            rr.font.size = Pt(8)
            rr.font.color.rgb = VERMELHO if (pend and b) else TEXTO
        if pend:
            for c in cells:
                shade(c, "FCF3F3")


def main():
    base._MD.clear()
    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10)

    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.LEFT
    r = t.add_run("CVC IAM Analytics")
    r.bold = True
    r.font.size = Pt(20)
    r.font.color.rgb = AZUL
    s = doc.add_paragraph()
    r = s.add_run("Checklist das regras — como cada uma é feita e o que mudou")
    r.font.size = Pt(13)
    r.font.color.rgb = CINZA
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run("22/09/2026")
    r.font.size = Pt(9)
    r.font.color.rgb = CINZA

    doc.add_paragraph()
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(
        "As regras na ordem em que a aplicação as executa. Para cada uma: quem "
        "entra, o que é comparado e o que sai — como está implementado, não como "
        "foi planejado. Quando houve mudança, a data e o que foi mudado. Regra "
        "sem tabela é regra que não mudou desde o roteiro de 06/08.")
    r.font.size = Pt(9.5)
    r.font.color.rgb = TEXTO

    for titulo_fase, regras in FASES:
        h1(doc, titulo_fase)
        for item in regras:
            regra(doc, *item)

    resumo(doc)

    OUT_DOCX.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT_DOCX)
    print(f"OK  {OUT_DOCX}")


if __name__ == "__main__":
    main()
