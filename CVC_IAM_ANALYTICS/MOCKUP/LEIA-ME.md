# Quarentena — Aplicativo CVC IAM Analytics

Aplicativo local que abre o painel do IAM Analytics e permite **enviar usuários
para quarentena** direto da grade de Inclusão / Alteração. Os dados são lidos
**ao vivo** da base `iam_analytics.db` — a mesma fonte do Power BI. Não há
arquivo intermediário (json/xml/txt): a página conversa com um servidor local
e o servidor conversa direto com o banco SQLite.

## O que tem nesta pasta

| Arquivo | O quê |
|---|---|
| `MockupServer.exe`   | O aplicativo. Servidor local + navegador. Não instala nada, não abre janela de terminal. |
| `index.html`         | A página do painel (servida pelo exe). |
| `config.xml`         | Parametrização: caminho do banco, sistema, dias de quarentena. |
| `chart.umd.min.js`   | Biblioteca de gráficos — **embutida**, funciona sem internet. |
| `mockup_server.py`   | Código-fonte do exe (transparência / auditoria). |
| `LEIA-ME.md`         | Este guia. |

## Pré-requisito

A base `iam_analytics.db` já processada pelo Processador (tabelas
`validacao_acessos`, `divergencias`, `rh_ativos`). O app **lê** essa base e
**grava** a tabela `quarentena` dentro dela.

## Onde colocar esta pasta

O `config.xml` aponta, por padrão, para `..\DADOS\BANCO\iam_analytics.db` —
caminho **relativo à pasta do exe**. Duas formas de usar:

1. **Dentro da estrutura do projeto** — coloque esta pasta como filha de
   `CVC_IAM_ANALYTICS\` (ao lado de `DADOS\`, `ENTRADA\`...). O caminho padrão
   já funciona.
2. **Em qualquer outro lugar** — edite o `config.xml` e aponte
   `<banco caminho="...">` para o caminho absoluto ou de rede (UNC) do banco.
   Ex.: `\\servidorcvc\share\IAM\iam_analytics.db`.

## config.xml

```xml
<config>
  <banco caminho="..\DADOS\BANCO\iam_analytics.db" />
  <sistema valor="SYSTUR" />
  <quarentena duracao_dias="90" />
</config>
```

- `banco/caminho` — relativo (resolvido na pasta do exe) ou absoluto/UNC.
- `sistema/valor` — escopo dos KPIs e da grade (vazio = todos os sistemas).
- `quarentena/duracao_dias` — `data_fim` = `data_inicio` + N dias.

## Como rodar

1. (Opcional) Ajuste o `config.xml`.
2. Duplo clique em `MockupServer.exe`. **Não abre janela de terminal — é normal.**
3. O navegador abre sozinho em `http://127.0.0.1:8800/`.
4. Na aba **Inclusão / Alteração**, cada linha tem o botão **⛔ Quarentena**.
5. Ao clicar e confirmar, o usuário é gravado na tabela `quarentena` e **sai da
   grade**. Ele volta sozinho quando a quarentena vence (`data_fim`).
6. **Para encerrar:** feche a aba/navegador. O servidor detecta e se fecha
   sozinho (na hora, ou em ~15 s).

## Onde os dados ficam

A quarentena é gravada na tabela `quarentena` **dentro do `iam_analytics.db`** —
persiste depois de fechar o app. O aplicativo não cria nenhum arquivo de dados
separado.

## Atualizar o cenário

O painel reflete um snapshot (`bi_divergencias`) recriado a cada processamento.
Para forçar a atualização ao cenário atual do banco sem reprocessar, rode uma
vez `MockupServer.exe refresh`.

## Diagnóstico

`mockup_log.txt` (na pasta do exe) registra cada execução — útil se algo for
bloqueado pela política de segurança da estação.
