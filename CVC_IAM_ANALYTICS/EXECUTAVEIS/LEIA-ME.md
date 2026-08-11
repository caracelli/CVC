# CVC IAM Analytics — Aplicativos

Esta pasta (`EXECUTAVEIS`) contém os dois aplicativos do projeto.

## O que tem aqui

| Item | O quê |
|---|---|
| `Processador.exe` | Lê as bases de `ENTRADA`, processa e grava o banco `iam_analytics.db`. |
| `visualizador.exe` | Abre o painel do IAM Analytics no navegador. Servidor local — não instala nada, não abre janela de terminal. |
| `CONFIG\config.xml` | Configuração única: raiz de rede, banco, sistema, quarentena, versão. |
| `REPORT\` | A página do painel (`index.html`) e a biblioteca de gráficos. |
| `visualizador.py` | Código-fonte do visualizador (transparência / auditoria). |

## Como usar

1. **Processar** — rode o `Processador.exe`. Ele lê `ENTRADA\`, cruza com as
   matrizes e grava o `iam_analytics.db`.
2. **Visualizar** — rode o `visualizador.exe`. O navegador abre em
   `http://127.0.0.1:8800/` com o painel.
3. Na aba **Inclusão / Alteração**, cada linha tem o botão de **quarentena**.
4. **Para encerrar o visualizador:** feche a aba do navegador — o servidor se
   fecha sozinho.

## Multiusuário

Vários usuários podem abrir o visualizador ao mesmo tempo. As interações da
quarentena são gravadas na pasta de rede `INTERACOES\` (um arquivo `.jsonl` por
usuário) e o Processador as consolida no banco a cada execução. A raiz de rede
fica em `CONFIG\config.xml`, seção `<rede>`.

## Atualização automática

Ao iniciar, cada exe compara a `<versao>` do `config.xml` local com a da rede;
se diferente, copia a versão nova da rede e reinicia.

## Abertura de chamado no Jira (instalação — feita uma vez)

O botão **Abrir chamado no Jira**, na aba Desligados, nasce desabilitado. Para
habilitar, alguém com acesso ao compartilhamento cria **um arquivo**:

```
<raiz de rede>\EXECUTAVEIS\CONFIG\jira.xml
```

Use o modelo `CONFIG\jira.xml.exemplo`, que já vem com todos os campos
comentados. A infra preenche `<ativo>true</ativo>`, o e-mail da conta de serviço
e o token; o resto já vem preenchido.

Três coisas que valem saber:

- **É colocado uma vez e fica.** Nenhuma atualização de versão sobrescreve ou
  apaga esse arquivo.
- **É lido direto da rede**, não da cópia local. Trocar o token vale para todos
  os analistas na próxima vez que abrirem o painel — sem republicar versão.
- **Não vai para o pacote de atualização.** Se existir um `jira.xml` na máquina
  de quem gera o build, ele é deliberadamente excluído do zip, para a credencial
  não se espalhar.

Deve ser uma **conta de serviço**, cadastrada como cliente do portal — não a
conta pessoal de um analista. Ela só precisa abrir chamado.

Para conferir se funcionou, abra o visualizador e olhe a linha `Jira` no início
do log:

```
Jira      : ativo (rede) — svc-iam@cvccorp.com.br -> portal 9 / tipo 8819
Jira      : nao configurado (sem CONFIG/jira.xml)
Jira      : INCOMPLETO (rede) — falta token
```

## Diagnóstico

`visualizador_log.txt` (nesta pasta) registra cada execução do visualizador.
