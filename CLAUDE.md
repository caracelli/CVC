# CVC IAM Analytics

Projeto de análise e governança de acessos (IAM) para a CVC Corp.

## Objetivo

Processar bases de RH e extratos de acesso dos sistemas corporativos, cruzar com matrizes de perfis esperados e gerar relatórios de divergências para o cliente CVC.

## Sistemas integrados

| ID | Sistema | Tipo de arquivo |
|----|---------|----------------|
| SIGOT | Sistema de Gestão de Operações e Turismo | CSV |
| SICA_RA | Controle de Acesso — Rede Agência | CSV |
| SICA_ESFERA | Controle de Acesso — Esfera | CSV |
| SYSTUR | Sistema de Turismo | CSV |
| IC | Integrador Contábil | XLSX |
| ORACLE_EBS | Oracle EBS | CSV |
| SIG | SIG | XLSX |

Os 7 estão com `<ativo>true</ativo>` no `config.xml`. O `OPERA_OPERACIONAL`
existe no config com `ativo=false` — fora de escopo.

## Dois aplicativos

- **Processador** (`Processador.exe`) — lê as bases de `ENTRADA`, padroniza, cruza com as matrizes, grava o banco `iam_analytics.db` e gera os relatórios Excel. Roda sob demanda.
- **Visualizador** (`visualizador.exe`) — servidor local que abre o painel (`REPORT/index.html`) no navegador, lendo o banco ao vivo. Fonte: `src/visualizador/main.py` (Python stdlib puro, sem dependências — o
  painel é standalone e o spec não empacota o resto do `src/`).

## Arquitetura multiusuário

A base e os dados ficam numa **raiz de rede** (`<rede><raiz>` no config). Vários usuários abrem o Visualizador ao mesmo tempo:

- O Processador grava o `iam_analytics.db` na rede; cada Visualizador **copia o banco para um cache local** no startup (mais rápido, sem ler durante a escrita).
- As interações da quarentena são gravadas em `INTERACOES/` — um arquivo `.jsonl` append-only **por usuário** (um escritor por arquivo, seguro sobre SMB).
- O Processador, a cada execução, **consolida (dobra)** os `.jsonl` no banco e reseta a pasta `INTERACOES/` por rename atômico.
- Os exes **se auto-atualizam**: comparam a `<versao>` do config local com a da rede e se copiam da rede se diferente.

Detalhes em `docs/ARQUITETURA_MULTIUSUARIO_FASE1.md`.

## Estrutura da pasta de rede (`CVC_IAM_ANALYTICS/`)

```
CVC_IAM_ANALYTICS/
  ENTRADA/                   # arquivos depositados pelo cliente
    RH/ATIVOS/, RH/DESLIGADOS/
    SISTEMAS/{SIGOT,SICA_RA,SICA_ESFERA,SYSTUR,IC,ORACLE_EBS,SIG}/
    MATRIZES/{ORGANIZACIONAL,PERFIS_SISTEMAS}/
  DADOS/
    BANCO/                   # iam_analytics.db (SQLite)
    SAIDAS/{DIVERGENCIAS,DESLIGADOS,TRANSFERIDOS,AUDITORIA}/
    PROCESSADOS/             # arquivos já importados
    ERROS/                   # arquivos rejeitados na importação
    LOGS/
  EXECUTAVEIS/
    CONFIG/config.xml        # configuração única do projeto
    CONFIG/jira.xml          # credencial do Jira — NÃO versionado, fica só na rede
    REPORT/index.html        # painel do Visualizador
    Processador.exe, visualizador.exe, launcher/
  INTERACOES/                # interações multiusuário (.jsonl por usuário)
```

## Código-fonte

```
src/                         # código do Processador (DDD)
  dominio/                   # entidades, objetos de valor, regras, interfaces
  aplicacao/casos_de_uso/    # casos de uso
  infraestrutura/            # leitores CSV/XLSX, repositórios SQLite,
                             # configuração, interações, auto-update
  processador/main.py        # entry point do Processador
  visualizador/main.py       # o Visualizador inteiro (standalone, stdlib pura)

tests/                       # testes automatizados
docs/                        # documentação técnica
scripts/                     # scripts utilitários
deploy/                      # empacotamento (build_processador.py, build_visualizador.py)
```

## Camada de domínio

- **Entidades:** `Funcionario`, `FuncionarioAtivo`, `FuncionarioDesligado`, `PerfilAcesso`, `PerfilEsperado`, `Divergencia`, `Transferido`
- **Objetos de valor:** `Cargo`, `Sistema` (enum), `NivelAcesso` (enum), `TipoDivergencia` (enum)
- **Regras:** `RegraAcessoDesligado`, `RegraAcessoTransferido`, `RegraPerfilInvalido`
- **Serviço:** `ServicoAnaliseDivergencias`

## Configuração

Tudo — raiz de rede, caminhos, colunas, sistemas, escopo do Visualizador — está em:
`CVC_IAM_ANALYTICS/EXECUTAVEIS/CONFIG/config.xml`

## Cronograma

26 cards — 11/05/2026 a 11/08/2026.
Detalhes em `.claude/projects/.../memory/project_cronograma.md`.

## Observações

- Arquivos de dados do cliente **não são versionados** (ver `.gitignore`)
- Pasta `Arquivos_origem/` contém os arquivos de referência iniciais — também fora do versionamento
- Pasta `OLD/` guarda artefatos obsoletos (Power BI, POC) — fora do versionamento
- Python 3.10+, dependências em `requirements.txt`
