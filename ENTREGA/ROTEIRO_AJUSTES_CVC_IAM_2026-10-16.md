# CVC IAM Analytics
## Atualização de 16/10 — ajustes aprovados (versão mantida em 1.0.3)
16/10/2026


## 1. O que muda

Ajustes aprovados no mockup de 16/10 (MOCKUP_PAINEL_AJUSTES_2026-10-16.html).

- Contas de robô e sistêmicas (login SIST…) nunca ficam vinculadas a uma pessoa: vão sempre para Pendências como “Usuário Não Encontrado”, para análise e quarentena. Antes, o robô cadastrado com o e-mail de quem o criou virava acesso dessa pessoa. A categoria “Contas de serviço” da aba Desligados passa a ficar vazia.
- Conta com e-mail de uma pessoa, mas CPF e nome de outra, deixa de ser atribuída a ela (caso ALEXANDRA, 90000266: o PERFIL_CONSULTA do SYSTUR era do robô “VISUAL TURISMO”). Nome abreviado continua valendo (ex.: “FELIPPE SATO”).
- Quem está na CCO é validado só pela CCO, inclusive no Oracle EBS: o que a função prevê e a pessoa não tem passa a ser “Incluir” (antes: “não tem mapeado na matriz”). Caso CLAUDIA, 90001433; na base de 09/10 são 52 pessoas.
- Transferidos: o perfil “CVC OIE BRASIL - Relatório de Despesas” é desconsiderado, como já era na validação. No detalhe e no Excel ele aparece como “desconsiderado (perfil padrão)”.
- Resolver pendência: com mais de uma pendência, o painel lista cada uma para escolher (nenhuma vem marcada; “marcar todas” resolve tudo de uma vez, como antes).
- Motivo do “Resolver pendência”: só “Acesso Indevido”.
- Layout: as barras de botões das abas Transferidos, Desligados, Quarentena e Consulta não quebram mais em telas menores.


## 2. Instalação na rede

O banco já vem processado (BANCO_PROCESSADO_2026-10-16.zip): base da rede de 13/10 com os extratos até 15/10, mais o RH e o SIG de 14 a 16/10, com as regras novas. O processamento da rede de 15/10 (iniciado às 17:17) não terminou e deixou um journal aberto; este banco o substitui. A versão dos executáveis continua 1.0.3: nenhuma máquina se atualiza sozinha.

- Feche os painéis e garanta que ninguém esteja rodando o Processador.
- Em <raiz>\DADOS\BANCO, mova JUNTOS para uma pasta de backup (ex.: _antes_1610) o iam_analytics.db, o iam_analytics.db-journal e o _processando.lock. Não apague o journal sozinho: sem ele o banco antigo fica corrompido.
- Copie o iam_analytics.db do BANCO_PROCESSADO_2026-10-16.zip para <raiz>\DADOS\BANCO.
- Não mexa na pasta INTERACOES. Em ENTRADA\SISTEMAS\SIG\10-2026, mova os 3 arquivos view_sig_14_10, view_sig_15_10 e view_sig_16_10 para a subpasta PROCESSADOS: eles já estão no banco novo (se ficarem, o próximo processamento os importa de novo, à toa).
- Copie a pasta EXECUTAVEIS do ATUALIZACAO_PRD_v1.0.3.zip por cima da EXECUTAVEIS da rede. Como a versão é a mesma, as máquinas não se atualizam sozinhas.
- Se existir a pasta <raiz>\EXECUTAVEIS\DADOS, apague ou renomeie: é um cache antigo de quando o painel era aberto direto da rede.
- Abra os painéis e clique em Atualizar.

PRÓXIMO PROCESSAMENTO: quem for processar precisa usar os executáveis novos — copie a EXECUTAVEIS da rede (já atualizada) por cima da sua cópia local antes de abrir o Processador.exe. Com o Processador antigo, as regras antigas voltam (robôs atribuídos às pessoas, EBS da CCO como informativo).

Os painéis das máquinas mostram os dados novos já com a versão atual (robôs em Pendências, ALEXANDRA aderente, EBS da CLAUDIA como inclusão). As mudanças de tela (escolher a pendência no Resolver, motivo só “Acesso Indevido”, “Relatório de Despesas” desconsiderado nos Transferidos e o layout das barras) aparecem em quem copiar a EXECUTAVEIS nova para a máquina.


## 3. O que conferir

- Pendências: as contas SIST… aparecem como “Usuário Não Encontrado”.
- Consulta da ALEXANDRA (90000266): SYSTUR aderente, só com B2B_PROJETOS.
- Consulta da CLAUDIA (90001433): ORACLE_EBS em “Acessos esperados” com os 8 perfis.
- Transferidos: o “Relatório de Despesas” não aparece no resumo do Oracle.
- Resolver pendência de quem tem pendência em mais de um sistema: a lista para escolher; motivo só “Acesso Indevido”.
