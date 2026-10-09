# CVC IAM Analytics
## Atualização de 09/10 — banco corrompido e execução pela rede
09/10/2026


## 1. O que aconteceu

O banco da rede (iam_analytics.db) estava íntegro, com o processamento das 10:59. Ao lado dele ficou um arquivo iam_analytics.db-wal, resto de uma gravação anterior. Ao copiar o banco para a máquina, o painel aplicava esse resto por cima do banco novo e a cópia saía corrompida. Nenhum dado nem tratativa se perdeu.

A causa é o modo de gravação “WAL” do SQLite, que não é seguro em pasta de rede. Esta atualização deixa de usá-lo.


## 2. O que muda nesta atualização

- Processador: grava o banco da rede no modo seguro para pasta de rede. Se encontrar um -wal órfão, guarda-o como .orfao_<data> (não apaga).
- Painel: copia só o arquivo do banco (ignora -wal ao lado) e confere a cópia antes de usar. Se a cópia estiver ruim, mantém a anterior e avisa.
- Painel: descarta sozinho uma cópia local corrompida.
- Painel: não copia enquanto o Processador está rodando. Mostra “Processamento em andamento na rede” e só oferece a carga nova quando ele termina.
- Painel e Processador não abrem mais direto da pasta de rede: mostram um aviso. Rodado da rede, o programa prende a pasta (ninguém consegue atualizar) e o painel passa a usar um único arquivo de cópia na rede para todos, o que corrompe o banco. Cada pessoa usa a sua cópia local de EXECUTAVEIS (ex.: C:\CVC_IAM\EXECUTAVEIS); os dados continuam na rede.


## 3. Instalação na rede

- Feche o painel e o Processador em todas as máquinas. Quem abriu da rede: no Gerenciador de Tarefas, finalize launcher_visualizador.exe e launcher_processador.exe (o painel segue rodando após fechar o navegador). Sem saber quem abriu: renomeie os .exe da EXECUTAVEIS da rede (e da subpasta launcher) para .exe.old_0910 — um exe em uso pode ser renomeado, só não sobrescrito. Apague os .old_0910 depois.
- Em DADOS\BANCO: se ainda existirem iam_analytics.db-wal e iam_analytics.db-shm, mova os dois para uma pasta _orfao_0910 (não apague; não mexa no iam_analytics.db).
- Copie a pasta EXECUTAVEIS do zip por cima da EXECUTAVEIS da rede.
- No seu computador, copie a EXECUTAVEIS da rede (já atualizada) por cima da sua cópia local (ex.: C:\CVC_IAM\EXECUTAVEIS) e abra o Processador.exe de lá. Uma máquina só, com todos os painéis fechados; espere “Processamento finalizado”.
- Abra o painel (visualizador.exe da cópia local).

Versão: o pacote vem como 1.0.2. As máquinas só se atualizam sozinhas quando a versão do config da rede muda. Enquanto ela ficar 1.0.2, quem usar o programa precisa copiar a EXECUTAVEIS nova para a máquina.


## 4. O que conferir

- O painel abre sem a mensagem “database disk image is malformed”.
- Em DADOS\BANCO da rede ficam só o iam_analytics.db (sem -wal/-shm) depois do processamento.
- Com o Processador rodando, o botão Atualizar responde “Processamento em andamento na rede”; depois que ele termina, a carga nova aparece.
- Abrir o visualizador.exe ou o Processador.exe direto da pasta de rede mostra o aviso “não pode ser aberto direto da pasta de rede” e não abre.
- Os números batem com o processamento anterior (ex.: franqueados pela “Matriz franqueado”, CLAUDIA aderente pela CCO).
