# POC Quarentena — Teste de Gravação na Máquina do Cliente

Objetivo: provar, na máquina real da CVC, se a arquitetura
**botão → servidor Python local → SQLite** funciona, e descobrir o que a
política de segurança da estação bloqueia. A prova vai para o git.

## O que tem nesta pasta

| Arquivo | O quê |
|---|---|
| `ServidorPOC.exe` | Servidor local (Python embutido, sem instalar nada). Stdlib só. |
| `servidor_poc.py` | Código-fonte do exe (transparência/auditoria). |
| `index.html` | Página de teste (cópia do que o exe serve embutido). |
| `LEIA-ME.md` | Este guia. |

Ao rodar, o exe cria **na própria pasta**:
- `teste.db` — banco SQLite com os registros (prova binária).
- `registros.txt` — mesma info em texto (prova legível no `git diff`).

## Passo a passo na máquina do cliente

1. Copie a pasta `teste_poc_quarentena` inteira para a máquina do cliente
   (ou rode direto do repositório clonado lá).
2. **Dê duplo clique em `ServidorPOC.exe`.**
3. Observe a **janela preta (console)**: ela mostra pasta, caminho do banco,
   máquina, usuário e se a pasta é gravável.
   - ⚠️ Se algo **bloquear** (AppLocker, EDR, SmartScreen, "Windows protegeu
     seu PC", antivírus removeu o exe): **anote a mensagem exata e tire print**.
     Isso É o resultado do teste — não é falha sua.
4. O navegador deve abrir sozinho em `http://127.0.0.1:8799/`.
   - Se não abrir, abra o navegador e digite esse endereço.
5. Na página: confira o painel **Diagnóstico** (permissão de escrita deve
   estar verde "OK").
6. Digite **qualquer texto** na caixa e clique **Enviar**. Faça 3–4 vezes
   com textos diferentes (ex.: "teste 1 estacao CVC", "teste 2", ...).
7. Cada envio deve aparecer na tabela "Registros gravados".
8. **Para encerrar: basta fechar a aba/navegador.** O servidor detecta que a
   página sumiu e **se fecha sozinho** (na hora via sendBeacon, ou em ~15s
   pelo watchdog de heartbeat). A janela preta fecha junto. Também funciona
   fechar a janela preta direto ou Ctrl+C.
   - Obs.: se o navegador/exe foi bloqueado e a página nunca abriu, o
     servidor **fica vivo** de propósito (pra você ler a mensagem do console).

## Enviar a prova de volta (git, da máquina do cliente)

Na pasta do repositório, na máquina do cliente:

```
git add -f teste_poc_quarentena/teste.db teste_poc_quarentena/registros.txt
git commit -m "POC quarentena: executado na estacao CVC"
git push
```

(`-f` é só garantia, caso algum filtro de `.gitignore` pegue o `.db`.)

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
