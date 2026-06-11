# Como gerar os executáveis (CVC IAM Analytics)

> Guia auto-suficiente. Um assistente (Claude Code etc.) ou um dev pode ler
> este arquivo e gerar os executáveis sem mais contexto.

## Visão geral

O projeto entrega **2 aplicativos**, empacotados em **5 executáveis**:

| Exe | Pasta | Papel |
|-----|-------|-------|
| `Processador.exe` | `CVC_IAM_ANALYTICS/EXECUTAVEIS/` | atalho clicável do motor |
| `visualizador.exe` | `CVC_IAM_ANALYTICS/EXECUTAVEIS/` | atalho clicável do painel |
| `launcher/launcher_atualizador.exe` | `.../EXECUTAVEIS/launcher/` | auto-update + splash |
| `launcher/launcher_visualizador.exe` | `.../EXECUTAVEIS/launcher/` | painel real (servidor local) |
| `launcher/launcher_processador.exe` | `.../EXECUTAVEIS/launcher/` | motor real (pandas/openpyxl, ~80 MB) |

Os exes **não são versionados** (estão no `.gitignore`) — sempre são gerados a
partir do código.

## Pré-requisitos

1. **Python 3.10+** instalado e no PATH.
2. Dependências do projeto (inclui o PyInstaller):
   ```
   pip install -r requirements.txt
   ```
   (Se preferir só o necessário para buildar: `pip install pyinstaller pandas numpy openpyxl sqlalchemy loguru`.)

## Gerar TODOS os executáveis (recomendado)

Da raiz do projeto:

```
cd deploy
python build_all.py
```

Isso compila os 5 exes (via PyInstaller, usando os `.spec` da pasta `deploy/`)
e os coloca em `CVC_IAM_ANALYTICS/EXECUTAVEIS/` (e `.../launcher/`). Ao final,
imprime o resumo com os tamanhos. Leva alguns minutos (o
`launcher_processador.exe` é o maior).

### Gerar individualmente (opcional)

```
cd deploy
python build_processador.py     # só o motor
python build_visualizador.py    # só o painel
```

## Empacotar para entrega

Depois de buildar, há dois empacotadores prontos:

- **Instalação nova** (estrutura completa, banco vazio):
  ```
  cd deploy && python build_entrega_rede.py     # gera ENTREGA/ENTREGA_REDE.zip
  ```
- **Atualização in-place** (só a pasta `EXECUTAVEIS/`, preserva dados do cliente):
  ```
  cd deploy && python build_update_executaveis.py   # gera ENTREGA/UPDATE_EXECUTAVEIS_vX.zip
  ```
  No cliente: copiar **apenas** `EXECUTAVEIS/` por cima da rede; **não** tocar em
  `DADOS/` nem `INTERACOES/`.

## Versão (importante)

A `<versao>` fica em `CVC_IAM_ANALYTICS/EXECUTAVEIS/CONFIG/config.xml` e segue o
esquema `MAJOR.PROCESSADOR.VISUALIZADOR`. Ela é **lida em runtime** (não é
compilada nos exes), e governa o auto-update local × rede.

- Mudou **só a versão** ou a `<raiz>` de rede? **Não precisa rebuildar** —
  basta rodar `build_entrega_rede.py` / `build_update_executaveis.py`, que
  reaproveitam os exes existentes.
- Mudou **código** (src/)? Rebuildar com `build_all.py` antes de empacotar.

Ao subir a versão, ajuste nos dois lugares:
- `CVC_IAM_ANALYTICS/EXECUTAVEIS/CONFIG/config.xml`
- `deploy/build_entrega_rede.py` e `deploy/build_update_executaveis.py` (constantes de versão)

## Conferência rápida pós-build

Os exes devem ter data/hora recente em
`CVC_IAM_ANALYTICS/EXECUTAVEIS/` e `.../launcher/`. Para um teste local da base,
rode o `Processador.exe` (gera/atualiza o `iam_analytics.db`) e depois o
`visualizador.exe` (abre o painel em `http://127.0.0.1:8800/`).
