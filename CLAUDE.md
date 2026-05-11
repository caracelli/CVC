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

```
CVC_IAM_ANALYTICS/          # Pasta do usuário (rede do cliente)
  01_EXECUTAVEIS/            # Executáveis para cópia local
  02_CONFIGURACAO/           # config.xml com parâmetros de todos os sistemas
  03_ENTRADA_ARQUIVOS/       # Arquivos que o usuário deposita
  04_POWER_BI/               # Arquivo .pbix para cópia local
  05_SAIDAS/                 # Relatórios e divergências gerados
  06_DADOS_PROJETO/          # Banco SQLite, Parquet, arquivos processados

src/                         # Código-fonte (DDD)
  dominio/                   # Entidades, objetos de valor, regras, interfaces
  aplicacao/                 # Casos de uso, DTOs
  infraestrutura/            # Leitores CSV/XLSX, repositórios SQLite, Parquet
  processador/main.py        # Entry point do Processador
  visualizador/main.py       # Entry point do Visualizador

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
`CVC_IAM_ANALYTICS/02_CONFIGURACAO/config.xml`

## Cronograma

26 cards — 11/05/2026 a 11/08/2026.
Detalhes em `.claude/projects/.../memory/project_cronograma.md`.

## Observações

- Arquivos de dados do cliente **não são versionados** (ver `.gitignore`)
- Pasta `Arquivos_origem/` contém os arquivos de referência iniciais — também fora do versionamento
- Python 3.10+, dependências em `requirements.txt`
