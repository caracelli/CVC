# Entrega — CVC IAM Analytics (Fase 1 — SYSTUR)

Dois pacotes de teste, ambos **autossuficientes** (não precisam
instalar nada nem ter o projeto montado). Cada zip traz a pasta
`CVC_IAM_ANALYTICS/` espelhando a arquitetura do produto, com
`<rede><raiz>` **vazia** — funcionam em qualquer lugar onde o cliente
extrair (não exigem drive de rede mapeado).

## 1. `Projeto CVC.zip` — Visualizador (com cenário atual)

O painel que o cliente abre para **ver** os resultados. Lê o banco
SQLite direto, sem Power BI. Já vem com um banco preparado, então
funciona de imediato — não é preciso rodar o Processador para testar.

Conteúdo:

```
Projeto CVC/
  LEIA-ME.txt
  CVC_IAM_ANALYTICS/
    EXECUTAVEIS/
      visualizador.exe
      visualizador.py            (código-fonte, auditoria)
      CONFIG/config.xml          (<raiz> vazia)
      REPORT/index.html          (painel) + chart.umd.min.js
      LEIA-ME.md
    DADOS/BANCO/iam_analytics.db (cenário atual)
    INTERACOES/                  (multiusuário)
```

Rodar `CVC_IAM_ANALYTICS\EXECUTAVEIS\visualizador.exe`. O navegador
abre em `http://127.0.0.1:8800/`.

## 2. `Processador CVC.zip` — Processador (motor)

O motor que **importa** os arquivos de RH/SYSTUR/matrizes e **gera**
o banco `iam_analytics.db`. Vem com a estrutura `ENTRADA/` e `DADOS/`
vazias para o cliente preencher.

Conteúdo:

```
Processador CVC/
  LEIA-ME.txt
  CVC_IAM_ANALYTICS/
    EXECUTAVEIS/
      Processador.exe
      CONFIG/config.xml          (<raiz> vazia)
      LEIA-ME.md
    ENTRADA/
      RH/{ATIVOS, DESLIGADOS}/
      MATRIZES/{ORGANIZACIONAL, PERFIS_SISTEMAS}/
      SISTEMAS/{SIGOT, SICA_RA, SICA_ESFERA, SYSTUR, IC}/
    DADOS/
      BANCO/, SAIDAS/{...}, PROCESSADOS/, ERROS/, LOGS/
    INTERACOES/
```

Depositar os arquivos em `CVC_IAM_ANALYTICS\ENTRADA\` e rodar
`CVC_IAM_ANALYTICS\EXECUTAVEIS\Processador.exe`. O banco gerado fica
em `CVC_IAM_ANALYTICS\DADOS\BANCO\iam_analytics.db`.

## Como os dois se conectam

O Processador **gera** o banco; o Visualizador **lê** o banco. Para
ver no Visualizador um banco recém-processado, copie
`Processador CVC\CVC_IAM_ANALYTICS\DADOS\BANCO\iam_analytics.db` por
cima de `Projeto CVC\CVC_IAM_ANALYTICS\DADOS\BANCO\iam_analytics.db`.

## Configuração / arquitetura

- `config.xml` (em `EXECUTAVEIS\CONFIG\`) traz `<rede><raiz>` **vazia**
  nesta entrega — todos os caminhos resolvem dentro do
  `CVC_IAM_ANALYTICS\` extraído.
- Em ambiente real (multiusuário), `<raiz>` aponta para a raiz de
  rede compartilhada (ex.: `Z:\CVC\CVC_IAM_ANALYTICS`); aí o
  Processador e os Visualizadores de cada usuário convergem na mesma
  base, com interações gravadas em `INTERACOES\` por usuário.
- Auto-update: ao iniciar, cada exe compara a `<versao>` local com a
  da rede; se diferente, copia a versão nova e reinicia (no modo
  local desta entrega, é no-op).

## Como regerar estes zips

```
cd deploy
python build_processador.py   # gera Processador.exe
python build_visualizador.py  # gera visualizador.exe
python build_entrega.py       # monta os dois zips em ENTREGA/
```

`build_entrega.py` usa o `config.xml` do projeto, zera `<raiz>` (só no
zip — o config local de dev não é tocado) e faz cópia consistente do
banco via API do SQLite.
