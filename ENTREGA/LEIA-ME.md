# Entrega — CVC IAM Analytics (Fase 1 — SYSTUR) — v1.0.0

Primeira versão de entrega. Um **único pacote**: `ENTREGA_REDE.zip`.

O zip contém a pasta `CVC_IAM_ANALYTICS/` completa (programa + dados),
espelhando a arquitetura do produto. O `config.xml` já vem com
`<raiz>Z:\CVC\CVC_IAM_ANALYTICS</raiz>` e `<versao>1.0.0</versao>`.

> Um `LEIA-ME.txt` com o passo a passo completo (rede, máquina-usuário,
> primeiro processamento, multiusuário, auto-update) vai **dentro** do zip,
> na raiz de `CVC_IAM_ANALYTICS/`.

## O que vem no zip

```
CVC_IAM_ANALYTICS/
  EXECUTAVEIS/
    Processador.exe              (motor — gera o banco)
    visualizador.exe             (painel — lê o banco)
    visualizador.py              (código-fonte, auditoria)
    CONFIG/config.xml            (<raiz>=Z:\CVC\CVC_IAM_ANALYTICS, versao 1.0.0)
    REPORT/index.html            (painel) + chart.umd.min.js
    launcher/                    (launcher_atualizador / _visualizador / _processador)
    LEIA-ME.md
  ENTRADA/                       (4 arquivos prontos para o 1º processamento)
    RH/ATIVOS/PROJETOIAM (8).CSV
    MATRIZES/ORGANIZACIONAL/Mapeamento CCO_CSC (1).xlsx
    MATRIZES/PERFIS_SISTEMAS/MATRIZ DE PERFIL DE ACESSO SYSTUR.xlsx
    SISTEMAS/SYSTUR/relatorio systur 30.04.xlsx
  DADOS/BANCO/                   (VAZIO — o Processador gera o iam_analytics.db)
  INTERACOES/                    (vazia — escrita pelos visualizadores)
  LEIA-ME.txt
```

## Instalação (resumo)

1. **Na rede (uma vez):** extrair o zip e copiar a pasta `CVC_IAM_ANALYTICS`
   para `Z:\CVC\` (fica `Z:\CVC\CVC_IAM_ANALYTICS\`).
2. **Em cada máquina-usuário:** copiar a pasta `EXECUTAVEIS` para um local
   (ex.: `C:\CVC\EXECUTAVEIS`) e rodar o `visualizador.exe` de lá — ele lê/grava
   os dados na rede (Z:) e se auto-atualiza pela `<versao>` do config.
3. **Primeiro processamento (responsável):** rodar o `Processador.exe` da sua
   pasta local → gera o banco em `Z:\CVC\CVC_IAM_ANALYTICS\DADOS\BANCO\iam_analytics.db`.

A base nasce **vazia**: o `iam_analytics.db` é gerado pelo Processador a partir
dos 4 arquivos de ENTRADA. Nenhum dado de teste acompanha a entrega.

## Escopo da Fase 1 (travado por config)

Só **SYSTUR** (inclusão/alteração). Desligados, terceiros e os demais sistemas
estão fora — desligados/terceiros são ignorados pelo motor mesmo se aparecerem
nas pastas (`rh/desligados/processar=false`, `rh/ativos/processar_terceiros=false`),
e os outros sistemas estão com `ativo=false`. Reativar por fase no `config.xml`.

## Como regerar o zip

```
cd deploy
python build_processador.py     # gera Processador.exe (PyInstaller)
python build_visualizador.py    # gera visualizador.exe (PyInstaller)
python build_entrega_rede.py    # monta ENTREGA_REDE.zip em ENTREGA/
```

Os exes só precisam ser rebuildados se o **código** mudar. Para mudar apenas a
**versão** ou a `<raiz>`, basta rodar `build_entrega_rede.py` — ele reaproveita os
exes existentes e grava um `config.xml` novo (a versão é lida em runtime, não
compilada). Versionado via Git LFS.
