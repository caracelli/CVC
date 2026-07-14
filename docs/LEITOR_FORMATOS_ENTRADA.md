# Leitor de arquivos de entrada — formatos aceitos

Documenta como o Processador lê os arquivos de `ENTRADA/`, quais formatos são
aceitos e como o formato/encoding é detectado. Atualizado em **14/07/2026**.

## Princípio: um leitor único, tolerante a formato

Todos os leitores de sistema passam pela mesma função
`ler_tabela(...)` em [`src/infraestrutura/leitores_arquivos/leitor_base.py`](../src/infraestrutura/leitores_arquivos/leitor_base.py).
Ela aceita, para **qualquer** sistema, os seguintes formatos — o cliente pode
mandar em qualquer um deles que o arquivo é importado:

| Formato | Como é lido | Detecção |
|---------|-------------|----------|
| **XLSX / XLS** | `pandas.read_excel` (1ª aba) | pela extensão |
| **CSV delimitado** (`,` `;` ou tab) | `pandas.read_csv` | separador contado na linha do cabeçalho |
| **CSV largura-fixa** (colunas alinhadas por espaços, **sem** delimitador) | `pandas.read_fwf` (infere colunas por posição) | quando **nenhum** delimitador é encontrado |

### Regras de precedência (importante)

1. **`.xlsx`/`.xls`** → sempre Excel (não passa por detecção de CSV).
2. **`encoding`/`separador` explícitos** (configurados por sistema em
   `configs_sistemas.py`) têm prioridade e **nunca** caem em largura-fixa —
   se o sistema já declara o separador, o formato é conhecido.
3. **`separador` não definido (`None`)** → auto-detecção:
   - conta `,`, `;`, tab na linha real do cabeçalho (`skiprows+header`);
   - se achar algum → CSV delimitado;
   - se **não** achar nenhum → **largura-fixa** (`read_fwf`).
4. **`encoding` não definido** → auto-detecção via `chardet`.

> O fallback de largura-fixa foi adicionado em 14/07/2026 para o extrato novo do
> **IC** (`view_IC_*`), que vem com colunas alinhadas por espaços. Como está no
> leitor compartilhado, vale para **todos** os sistemas com `separador=None`.

## Configuração por sistema

De [`configs_sistemas.py`](../src/infraestrutura/leitores_arquivos/configs_sistemas.py):

| Sistema | separador | encoding | skiprows | Observação |
|---------|-----------|----------|----------|------------|
| SYSTUR | auto | auto (chardet) | 0 | |
| SICA_RA | auto | auto (chardet) | 4 | |
| SIGOT | auto | `cp1252` | 2 | acentos garantidos |
| IC | auto | auto (chardet) | 0 | aceita largura-fixa **e** `;` |
| SICA_ESFERA | auto | `cp1252` | 4 | acentos garantidos |
| ORACLE_EBS | auto | auto (chardet) | 0 | |
| SIG | leitor próprio (`leitor_sig`) | — | — | formato matricial (despivot) |

Como **nenhum** sistema fixa `separador`, todos aceitam automaticamente
XLSX / `,` / `;` / tab / largura-fixa.

## Convenção nova de pastas e nomes (extratos diários)

A partir de 07/2026 o cliente passou a entregar **snapshots diários** em CSV,
organizados em subpastas por mês dentro da pasta do sistema:

```
ENTRADA/SISTEMAS/<SISTEMA>/
    MM-AAAA/                       # ex.: 07-2026
        view_<sistema>_<DD>_<MM>_<AAAA>_<HH>-<MM>.csv
        PROCESSADOS/               # arquivos já importados (ignorada na varredura)
```

- O leitor **varre recursivamente** a pasta do sistema, mas **ignora** as
  subpastas `PROCESSADOS`, `ERROS` e `INVALIDOS`
  (`LeitorArquivoBase._SUBPASTAS_IGNORADAS`).
- Para **reprocessar do zero** um arquivo já movido, tire-o de `PROCESSADOS`
  e coloque-o de volta na pasta base do sistema.
- **Modo de gravação**: extratos de sistema são **substituição** (o último
  arquivo lido define o estado). Já o **RH ativos é incremental** (merge) — para
  reconstruir a base do zero é preciso **todos** os arquivos de RH que a
  formaram (funcionários `PROJETOIAM` + terceiros `QuickReport`), não só o mais
  recente.

## Colunas por sistema (variações antigo × novo)

Os nomes de coluna críticos (usuário, nome, CPF, e-mail, perfil) são estáveis
entre o formato antigo (XLSX) e o novo (CSV `view_*`). Uma exceção conhecida:

- **IC**: status vem como `ST_HABILITACAO` no XLSX antigo e como `S` (truncado)
  no CSV largura-fixa novo. Quando não casa, a situação cai no default `ATIVO`.

## Como validar após mudança no leitor

1. `python -m pytest -q` (suíte de regressão).
2. Teste pontual de leitura em cada formato (antigo XLSX, CSV delimitado, CSV
   largura-fixa) chamando `ler_tabela(...)` direto e conferindo `len(df)` e as
   colunas.
3. Rodar o Processador sobre um `ENTRADA/` real e conferir no log a contagem de
   linhas por sistema (`=== <SISTEMA>: N arquivo(s) ... M acessos ===`).
