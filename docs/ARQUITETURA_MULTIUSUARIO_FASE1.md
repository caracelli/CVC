# Arquitetura Multiusuário — Fase 1 SYSTUR

> Especificação do desenho acordado para múltiplos usuários acessarem o
> Visualizador ao mesmo tempo, com interações (quarentena) replicadas entre
> eles — **sem servidor e sem PC host**.

## 1. Problema

- A base de dados precisa ficar **na rede** (todos consomem a mesma).
- Vários usuários abrem o Visualizador ao mesmo tempo (> 1, número incerto).
- As interações da quarentena precisam **replicar** entre todos.
- SQLite num compartilhamento de rede (SMB) com **vários escritores corrompe** —
  os locks de arquivo não são confiáveis sobre SMB. Não há servidor disponível
  nem máquina que possa ser host.

## 2. Solução — três camadas

| Camada | Onde mora | Acesso |
|--------|-----------|--------|
| `iam_analytics.db` | Rede → **copiado para local** por cada Visualizador no startup | Só-leitura |
| `INTERACOES\` (`.jsonl` por usuário) | Rede | 1 escritor por arquivo, N leitores |
| Tela (`index.html`) | Local | Mescla base local + `.jsonl` da rede |

Regra de ouro que elimina a corrupção: **um arquivo, um único escritor.**
Cada usuário escreve só no `.jsonl` dele; ninguém compartilha arquivo de escrita;
o `.db` é só-leitura. O cenário que corrompe SQLite simplesmente não ocorre.

## 3. Estrutura de pastas na rede

Base inicial: `Z:\CVC\CVC_IAM_ANALYTICS\`

```
Z:\CVC\CVC_IAM_ANALYTICS\
  EXECUTAVEIS\
    CONFIG\config.xml          # config oficial (a versão manda no auto-update)
    Processador.exe
    Visualizador.exe
    REPORT\                    # index.html + assets (chart.umd.min.js)
  DADOS\
    BANCO\iam_analytics.db     # master, gerado pelo Processador
  INTERACOES\                  # 1 .jsonl append-only por usuário
    interacao_<username>.jsonl
```

A pasta `MOCKUP\` deixa de existir; vira `EXECUTAVEIS\` com `CONFIG\` e `REPORT\`.

## 4. Modelo de interação (`.jsonl`)

Uma linha = uma interação = um objeto JSON completo + quebra de linha, gravado
num único `write()` (append). Sem timestamp separado: a data da ação **é** a
data de entrada/saída da quarentena.

```json
{"tipo_interacao":"QUARENTENA","registro_id":"SYSTUR-500-P1","acao":"ENVIAR","usuario":"joao.silva","data_acao":"2026-05-22T14:33"}
{"tipo_interacao":"QUARENTENA","registro_id":"SYSTUR-500-P1","acao":"RESOLVER","usuario":"maria.souza","data_acao":"2026-05-23T09:10"}
```

- `tipo_interacao` → categoria da interação. Hoje só `QUARENTENA`; o campo já
  deixa o modelo pronto para novos tipos de interação sem mudar o formato do
  arquivo (página e Processador roteiam pelo `tipo_interacao`).
- `usuario` → `%USERNAME%` do Windows (mesma fonte que nomeia o arquivo).
- `acao` → `ENVIAR` (entra na quarentena) / `RESOLVER` (sai). O conjunto de
  ações válidas depende do `tipo_interacao`.
- `data_acao` → vira `data_entrada` ou `data_saida` no `.db`.
- Leitura tolerante: se a última linha estiver incompleta (sem `\n`), é
  ignorada — vem completa na próxima leitura.

## 5. Fluxo da página (releitura por evento)

A página relê as interações da rede **somente quando o usuário age** — não há
timer de atualização. Eventos que disparam a releitura:

- Trocar de aba do dashboard.
- Aplicar ou limpar filtro.
- F5 (recarrega tudo naturalmente).

A releitura faz:

1. Lê **todos** os `.jsonl` de `INTERACOES\` na rede.
2. Agrupa por `registro_id`; aplica a ação de `data_acao` mais recente
   (**vence o mais recente** — resolve dois usuários no mesmo registro).
3. Mescla com o estado do `iam_analytics.db` local.
4. Atualiza a tela.

Usuário **parado** (sem trocar aba nem filtrar) vê o estado de quando entrou /
da última ação — não recebe atualização. É aceitável: para agir sobre qualquer
item é preciso navegar/filtrar até ele, e isso já traz o dado fresco.

O `ping` de 4 s (`index.html`, keep-alive do auto-encerramento) **permanece como
está** — só keep-alive, não carrega detecção de mudança.

A tela exibe **"Resolvido por `<usuario>` em `<data>`"**.

## 6. Fluxo do Processador (dobra das interações)

Ao rodar, antes de processar os dados novos:

1. **Recuperação:** se já existe `INTERACOES_processando\` de uma execução
   anterior interrompida, processa-a primeiro.
2. Renomeia `INTERACOES\` → `INTERACOES_processando\` *(operação atômica)*.
3. Cria `INTERACOES\` nova e vazia *(usuários já escrevem aqui)*.
4. Lê todos os `.jsonl` de `INTERACOES_processando\` e grava no `iam_analytics.db`.
5. **Commit confirmado.**
6. Só então apaga `INTERACOES_processando\`.

Se cair entre 4 e 5, a pasta `_processando` sobrevive e é recuperada no passo 1
na próxima execução. Nenhuma interação é perdida.

## 7. Auto-update dos executáveis (local × rede)

Ao iniciar o **Processador** ou o **Visualizador** na máquina local:

1. Compara `<versao>` do `config.xml` **local** com o da **rede**
   (`EXECUTAVEIS\CONFIG\config.xml`).
2. Se diferentes: copia exe + config da rede para o local e **re-executa**.
3. Se a **rede estiver fora do ar: não roda** — a base está na rede, sem ela
   não há o que mostrar nem onde gravar interação.

## 8. Arquivos a criar / alterar

**Criar:**

- `src/infraestrutura/interacoes/repositorio_interacoes.py` — append e leitura
  dos `.jsonl` na rede; merge "vence o mais recente".
- `src/aplicacao/casos_de_uso/dobrar_interacoes.py` — rename atômico, dobra no
  `.db`, recuperação de `_processando`.
- `src/infraestrutura/atualizacao/auto_update.py` — compara versão local × rede,
  copia e re-executa (compartilhado por Processador e Visualizador).

**Alterar:**

- `CVC_IAM_ANALYTICS/config.xml` — caminho base da rede, pasta `INTERACOES`,
  caminhos `CONFIG\` e `REPORT\`.
- `src/infraestrutura/configuracao/leitor_config.py` — novos campos em
  `Configuracao` (rede, interações).
- `src/processador/main.py` — chamar `auto_update` no início; chamar
  `dobrar_interacoes` (rename + fold) antes do processamento.
- `CVC_IAM_ANALYTICS/EXECUTAVEIS/visualizador.py` — `auto_update` no início; copiar
  o `.db` da rede para local no startup; endpoints `POST /api/interagir`
  (append) e `GET /api/interacoes` (lê a rede); merge em `construir_db`.
- `index.html` — poll de `/api/interacoes` a cada N s; exibir
  "Resolvido por `<usuario>`".
- Reestruturar `MOCKUP\` → `EXECUTAVEIS\` (`CONFIG\`, `REPORT\`).

**Schema (`iam_analytics.db`):**

- Tabela de interações dobradas com coluna **`usuario`** (sobrevive à dobra do
  Processador; o nome do arquivo `.jsonl` não chega ao `.db`).

## 9. Decisões travadas

- Identidade do usuário = `%USERNAME%` do Windows (sem tela de login).
- Conflito "dois usuários, mesmo registro" → **vence o `data_acao` mais recente**.
- Sem campo `timestamp` separado: `data_acao` é a própria data de entrada/saída.
- Reset da pasta por **rename atômico**, nunca apagando arquivo a arquivo.
- Rede fora do ar = aplicação não roda.
- Releitura das interações é **por evento** (troca de aba / filtro); sem timer
  de atualização. Usuário parado não recebe update — aceito.
- Cada interação carrega `tipo_interacao` (hoje só `QUARENTENA`) — modelo
  extensível a novos tipos sem mudar o formato do arquivo.
