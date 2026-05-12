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
| SYSTUR | Sistema de Turismo | XLSX |
| IC | Integrador Contábil | XLSX |
| ORACLE_EBS | Oracle EBS | — (Card 11) |
| SIG | SIG | — (Card 12) |

## Estrutura do repositório

A pasta `CVC_IAM_ANALYTICS/` é organizada em duas fases:

**Fase 1 — Cliente** (o que o usuário copia ou deposita):
```
CVC_IAM_ANALYTICS/
  config.xml                 # Parâmetros de todos os sistemas (na raiz)
  EXECUTAVEIS/               # Processador.exe e Visualizador.exe para cópia local
  POWER_BI/                  # Arquivo .pbix para cópia local
  ENTRADA/                   # Arquivos que o usuário deposita
    RH/ATIVOS/               # Base de funcionários ativos
    RH/DESLIGADOS/           # Base de desligados
    SISTEMAS/SIGOT/          # Extratos de acesso por sistema
    SISTEMAS/SICA_RA/
    SISTEMAS/SICA_ESFERA/
    SISTEMAS/SYSTUR/
    SISTEMAS/IC/
    MATRIZES/ORGANIZACIONAL/
    MATRIZES/PERFIS_SISTEMAS/
```

**Fase 2 — Aplicativo** (gerenciado pelo Processador/Visualizador):
```
  DADOS/
    BANCO/                   # SQLite (iam_analytics.db)
    PARQUET/                 # Parquet para consumo do Power BI
      ACESSOS/               # Um subdiretório por sistema
      DIVERGENCIAS/
      HISTORICO/
      RH/
    SAIDAS/                  # Relatórios gerados
      DIVERGENCIAS/
      DESLIGADOS/
      TRANSFERIDOS/
      AUDITORIA/
    PROCESSADOS/             # Arquivos já importados (movidos após leitura)
    ERROS/                   # Arquivos rejeitados na importação
    LOGS/                    # Logs de execução
    SNAPSHOTS/               # Snapshots históricos
```

**Código-fonte:**
```
src/                         # Código-fonte (DDD)
  dominio/                   # Entidades, objetos de valor, regras, interfaces
  aplicacao/                 # Casos de uso, DTOs
  infraestrutura/            # Leitores CSV/XLSX, repositórios SQLite, Parquet
  processador/main.py        # Entry point do Processador (roda na rede)
  visualizador/main.py       # Entry point do Visualizador (roda localmente)

tests/                       # Testes automatizados
docs/                        # Documentação técnica
scripts/                     # Scripts utilitários
deploy/                      # Empacotamento dos executáveis
```

## Camada de domínio

- **Entidades:** `Funcionario`, `FuncionarioAtivo`, `FuncionarioDesligado`, `PerfilAcesso`, `PerfilEsperado`, `Divergencia`, `Transferido`
- **Objetos de valor:** `Cargo`, `Sistema` (enum), `NivelAcesso` (enum), `TipoDivergencia` (enum)
- **Regras:** `RegraAcessoDesligado`, `RegraAcessoTransferido`, `RegraPerfilInvalido`
- **Serviço:** `ServicoAnaliseDivergencias`

## Configuração

Todos os parâmetros de caminhos, colunas e sistemas estão em:
`CVC_IAM_ANALYTICS/config.xml`

## Cronograma

26 cards — 11/05/2026 a 11/08/2026.
Detalhes em `.claude/projects/.../memory/project_cronograma.md`.

## Observações

- Arquivos de dados do cliente **não são versionados** (ver `.gitignore`)
- Pasta `Arquivos_origem/` contém os arquivos de referência iniciais — também fora do versionamento
- Python 3.10+, dependências em `requirements.txt`
