# Entrega — Visualizador CVC IAM Analytics

`Projeto CVC.zip` — pacote de teste para o cliente. **Autossuficiente**:
não precisa instalar nada nem ter o projeto montado.

Conteúdo do zip (extrai numa pasta só, `Projeto CVC/`):

- `APLICATIVO/` — o programa: `visualizador.exe` + `index.html` + `config.xml`
  + `chart.umd.min.js` + `visualizador.py` (código-fonte, para auditoria).
- `BANCO/` — a base de dados `iam_analytics.db` (cenário atual).
- `LEIA-ME.txt` — instruções de uso para o cliente.

O cliente extrai e roda `APLICATIVO/visualizador.exe`. O `config.xml` aponta
para `..\BANCO\iam_analytics.db` — funciona desde que as pastas `APLICATIVO/`
e `BANCO/` fiquem lado a lado.
