# Entrega — CVC IAM Analytics (Fase 1 — SYSTUR)

Dois pacotes de teste, ambos **autossuficientes** (não precisam instalar
nada nem ter o projeto montado). Extrair cada um numa pasta só.

## 1. `Projeto CVC.zip` — Visualizador

O painel que o cliente abre para **ver** os resultados. Lê o banco
SQLite direto, sem Power BI.

Conteúdo (`Projeto CVC/`):
- `APLICATIVO/` — `visualizador.exe` + `index.html` + `config.xml`
  + `chart.umd.min.js` + `visualizador.py` (código-fonte, para auditoria).
- `BANCO/` — a base `iam_analytics.db` (cenário atual).
- `LEIA-ME.txt` — instruções de uso.

Rodar `APLICATIVO/visualizador.exe`. O `config.xml` aponta para
`..\BANCO\iam_analytics.db` — manter `APLICATIVO/` e `BANCO/` lado a lado.

## 2. `Processador CVC.zip` — Processador

O motor que **importa** os arquivos de RH/SYSTUR/matrizes e **gera** o
banco `iam_analytics.db`.

Conteúdo (`Processador CVC/`):
- `config.xml` — parâmetros do processamento.
- `EXECUTAVEIS/` — `Processador.exe`.
- `ENTRADA/` — onde o cliente deposita os arquivos de entrada.
- `DADOS/` — saídas geradas (banco, parquet, relatórios, logs).
- `LEIA-ME.txt` — instruções de uso.

Rodar: depositar os arquivos em `ENTRADA/`, executar
`EXECUTAVEIS/Processador.exe`. O banco gerado fica em
`DADOS/BANCO/iam_analytics.db`.

## Como os dois se conectam

O Processador **gera** o banco; o Visualizador **lê** o banco. Para ver
no Visualizador um banco recém-processado, copie
`Processador CVC/DADOS/BANCO/iam_analytics.db` por cima de
`Projeto CVC/BANCO/iam_analytics.db`.

O `Projeto CVC.zip` já vem com um banco pronto (cenário atual), então o
Visualizador funciona de imediato — não é preciso rodar o Processador
para testar a visualização.
