# -*- coding: utf-8 -*-
"""Nenhum pacote pode levar artefato de DEV da maquina de build.

Achado em 26/08/2026: o `UPDATE_EXECUTAVEIS_v1.3.4.zip` **entregue** continha
`EXECUTAVEIS/DADOS/LOGS/visualizador.log`, `EXECUTAVEIS/visualizador_log.txt`
e `EXECUTAVEIS/launcher_dev/main.py`.

Por que importa:
  - os logs traziam 35 linhas com o caminho absoluto da nossa maquina (o
    OneDrive do desenvolvedor) — a arvore de diretorios de quem constroi nao
    e' assunto do cliente, e o log nao tem uso nenhum na maquina dele;
  - `launcher_dev/main.py` e' uma copia ANTIGA do fonte do painel (10/07):
    codigo-fonte desatualizado viajando junto do exe so cria confusao.

Nao e' erro de um script isolado: a lista de `ignore_patterns` e' copiada de um
build para o outro. Por isso o teste varre `deploy/` inteiro e cobra todos —
inclusive os que forem criados depois.
"""
import re
import unittest
from pathlib import Path

DEPLOY = Path(__file__).resolve().parent.parent / "deploy"

# padrao que tem de ser ignorado -> por que nao pode viajar
PROIBIDOS = {
    "*.log": "log da maquina de build",
    "visualizador_log.txt": "log da maquina de build",
    "launcher_dev": "copia antiga do fonte do painel",
    "__pycache__": "bytecode da maquina de build",
    "jira.xml": "CREDENCIAL",
}


def _builds_que_copiam_executaveis():
    """Scripts de deploy que copiam a arvore EXECUTAVEIS/ para o pacote."""
    return [p for p in sorted(DEPLOY.glob("build_*.py"))
            if "ignore_patterns" in p.read_text(encoding="utf-8")]


class PacoteNaoLevaArtefatoDeDev(unittest.TestCase):

    def test_ha_builds_para_conferir(self):
        """Guarda contra o teste virar no-op se o padrao de copia mudar."""
        self.assertGreaterEqual(len(_builds_que_copiam_executaveis()), 2)

    def test_todo_build_ignora_os_artefatos(self):
        faltas = []
        for p in _builds_que_copiam_executaveis():
            txt = p.read_text(encoding="utf-8")
            # so conta o que esta DENTRO de ignore_patterns(...)
            listas = " ".join(re.findall(r"ignore_patterns\((.*?)\)", txt, re.S))
            for padrao, motivo in PROIBIDOS.items():
                if f'"{padrao}"' not in listas and f"'{padrao}'" not in listas:
                    faltas.append(f"{p.name}: falta {padrao!r} ({motivo})")
        self.assertEqual(faltas, [], "\n".join(faltas))


if __name__ == "__main__":
    unittest.main()
