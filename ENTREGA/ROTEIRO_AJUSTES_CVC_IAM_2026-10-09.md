# CVC IAM Analytics
## Atualização 1.0.3 — erro “database disk image is malformed”
09/10/2026


## 1. O que aconteceu

O banco da rede (iam_analytics.db) estava íntegro, com o processamento das 10:59. Ao lado dele ficou um arquivo iam_analytics.db-wal, resto de uma gravação anterior. Ao copiar o banco para a máquina, o painel aplicava esse resto por cima do banco novo e a cópia saía corrompida. Nenhum dado nem tratativa se perdeu.

A causa é o modo de gravação “WAL” do SQLite, que não é seguro em pasta de rede. A versão 1.0.3 deixa de usá-lo.


## 2. O que muda na 1.0.3

- Processador: grava o banco da rede no modo seguro para pasta de rede. Se encontrar um -wal órfão, guarda-o como .orfao_<data> (não apaga).
- Painel: copia só o arquivo do banco (ignora -wal ao lado) e confere a cópia antes de usar. Se a cópia estiver ruim, mantém a anterior e avisa.
- Painel: descarta sozinho uma cópia local corrompida.
- Painel: não copia enquanto o Processador está rodando. Mostra “Processamento em andamento na rede” e só oferece a carga nova quando ele termina.


## 3. Instalação na rede

- Feche o painel e o Processador em todas as máquinas.
- Em DADOS\BANCO: se ainda existirem iam_analytics.db-wal e iam_analytics.db-shm, mova os dois para uma pasta _orfao_0910 (não apague; não mexa no iam_analytics.db).
- Copie a pasta EXECUTAVEIS do zip por cima da EXECUTAVEIS da rede.
- Rode o Processador.exe uma vez, com todos os painéis fechados, e espere “Processamento finalizado”.
- Abra o painel.


## 4. O que conferir

- O painel abre sem a mensagem “database disk image is malformed”.
- Em DADOS\BANCO da rede ficam só o iam_analytics.db (sem -wal/-shm) depois do processamento.
- Com o Processador rodando, o botão Atualizar responde “Processamento em andamento na rede”; depois que ele termina, a carga nova aparece.
- Os números batem com o processamento anterior (ex.: franqueados pela “Matriz franqueado”, CLAUDIA aderente pela CCO).
