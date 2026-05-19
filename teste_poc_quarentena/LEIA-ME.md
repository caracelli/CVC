# POC Quarentena — Teste de Gravação na Máquina do Cliente

Objetivo: provar, na máquina real da CVC, se a arquitetura
**botão → servidor Python local → SQLite** funciona, e descobrir o que a
política de segurança da estação bloqueia. A prova vai para o git.

## O que tem nesta pasta

| Arquivo | O quê |
|---|---|
| `ServidorPOC.exe` | Servidor local (Python embutido, sem instalar nada). Stdlib só. **Roda sem janela de terminal.** |
| `config.xml` | Parametriza o **caminho do banco** (local ou rede). |
| `servidor_poc.py` | Código-fonte do exe (transparência/auditoria). |
| `index.html` | Página de teste (cópia do que o exe serve embutido). |
| `LEIA-ME.md` | Este guia. |

Ao rodar, o exe cria (na pasta do banco — ver `config.xml`):
- `teste.db` — banco SQLite com os registros (prova binária).
- `registros.txt` — mesma info em texto (prova legível no `git diff`).
- `poc_log.txt` — log do diagnóstico (na pasta do exe). Como **não há
  janela de terminal**, é aqui que fica o registro do que aconteceu
  (útil se algo for bloqueado).

## Parametrizar o banco — `config.xml`

```xml
<config>
  <banco caminho="teste.db" />
</config>
```

- Caminho **relativo** → resolvido na pasta do `ServidorPOC.exe`.
- Caminho **absoluto** → usado como está, incluindo **rede UNC**:
  `\\servidorcvc\share\IAM\teste.db` (assim testa SQLite sobre SMB).
- `registros.txt` é sempre gravado **na mesma pasta do banco**.
- Sem `config.xml` ou XML inválido → cai no padrão `teste.db` (pasta do exe).
- A página mostra em **Origem config** de onde veio o caminho.

## Passo a passo na máquina do cliente

1. (Opcional) Ajuste `config.xml` se quiser o banco em outro lugar
   (ex.: pasta de rede). Padrão = `teste.db` na pasta do exe.
2. **Dê duplo clique em `ServidorPOC.exe`.** (Não abre janela de terminal —
   é normal.)
3. O navegador abre sozinho em `http://127.0.0.1:8799/`.
   - Se não abrir, abra o navegador e digite esse endereço.
   - ⚠️ Se algo **bloquear** (AppLocker, EDR, SmartScreen, "Windows protegeu
     seu PC", antivírus removeu o exe): **anote/print a mensagem**. Isso É o
     resultado do teste. Confira também o `poc_log.txt` na pasta do exe.
4. Na página: confira o painel **Diagnóstico** — caminho do banco,
   **Origem config**, e **Permissão escrita** (deve estar verde "OK").
5. Digite **qualquer texto** e clique **Enviar**. Faça 3–4 vezes
   com textos diferentes (ex.: "teste 1 estacao CVC", "teste 2", ...).
6. Cada envio aparece na tabela "Registros gravados".
7. **Para encerrar: basta fechar a aba/navegador.** O servidor detecta que a
   página sumiu e **se fecha sozinho** (na hora via sendBeacon, ou ~15s pelo
   watchdog). Não há janela para fechar.
   - Obs.: se a página nunca abriu (exe/navegador bloqueado), o servidor
     **fica vivo** de propósito — veja o `poc_log.txt` para o diagnóstico.

## Enviar a prova de volta (git, da máquina do cliente)

Na pasta do repositório, na máquina do cliente:

```
git add -f teste_poc_quarentena/teste.db teste_poc_quarentena/registros.txt teste_poc_quarentena/poc_log.txt
git commit -m "POC quarentena: executado na estacao CVC"
git push
```

(`-f` é só garantia, caso algum filtro de `.gitignore` pegue o `.db`.)
Se o banco foi para uma **pasta de rede** via `config.xml`, copie o
`teste.db`/`registros.txt` de lá para dentro de `teste_poc_quarentena/`
antes do `git add` — ou só mande o `poc_log.txt` (já prova o caminho usado).

Avise que subiu — puxamos aqui e verificamos `registros.txt` (mostra
data/hora, **nome da máquina** e **usuário** do cliente = prova de que rodou lá).

## Recomendado: testar nos DOIS cenários

O exe grava sempre **ao lado de si mesmo**, então o teste se adapta ao lugar:

1. **Cópia local** (ex.: `C:\Temp\teste_poc_quarentena\`) — cenário do
   Visualizador rodando localmente.
2. **Pasta de rede** (o share onde ficam os dados) — testa dois riscos extras:
   GPO que bloqueia executar `.exe` de caminho de rede, e SQLite sobre SMB.

Rodar nos dois e comparar é o que dá o retrato completo de viabilidade.

## O que cada resultado significa

| Resultado na estação CVC | Conclusão |
|---|---|
| Exe roda, navegador abre, grava OK | Arquitetura viável como está |
| Exe não executa (AppLocker/EDR/SmartScreen) | Precisa assinar exe / allowlist / embutir no Visualizador já aprovado |
| Roda mas "permissão escrita FALHOU" | Usuário não grava ali → usar fila local + Processador aplica |
| Navegador não abre `localhost` | Política de browser/proxy → ajustar bypass 127.0.0.1 |
| Rede falha mas local funciona | Manter dados/escrita local; rede só leitura |
