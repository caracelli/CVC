"""Roda o selftest do visualizador apontando para o banco do projeto.

O visualizador resolve caminhos relativos a EXECUTAVEIS/. Em dev usamos
monkeypatch das constantes globais antes de chamar main().
"""
import os
import sys
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parent.parent
RAIZ_APP = RAIZ_PROJETO / "CVC_IAM_ANALYTICS"

# Monkeypatch das constantes do visualizador antes do main()
sys.path.insert(0, str(RAIZ_PROJETO / "src"))
import visualizador.main as vm

vm.BASE_EXE = str(RAIZ_APP / "EXECUTAVEIS" / "launcher")
vm.BASE_APP = str(RAIZ_APP / "EXECUTAVEIS")
vm.RAIZ_APP = str(RAIZ_APP)
vm.REPORT_DIR = str(RAIZ_APP / "EXECUTAVEIS" / "REPORT")
vm.DADOS_DIR = str(RAIZ_APP / "DADOS")
vm.BANCO_LOCAL = str(RAIZ_APP / "DADOS" / "BANCO" / "iam_analytics.db")
vm.INDEX_PATH = str(RAIZ_APP / "EXECUTAVEIS" / "REPORT" / "index.html")
vm.CONFIG_PATH = str(RAIZ_APP / "EXECUTAVEIS" / "CONFIG" / "config.xml")
vm.BASE = vm.BASE_APP
vm.DB_PATH = vm.BANCO_LOCAL  # alias usado em alguns lugares
vm.LOG_PATH = str(RAIZ_APP / "DADOS" / "LOGS" / "visualizador_dev.log")

# Carrega config do XML real
vm.REDE_RAIZ, vm.BANCO_SUB, vm.SISTEMA, vm.QUAR_DIAS, vm.CONFIG_SRC = vm.carregar_config()
print(f"Config carregado de {vm.CONFIG_PATH}")
print(f"  rede_raiz={vm.REDE_RAIZ!r}")
print(f"  banco_sub={vm.BANCO_SUB!r}")
print(f"  sistema={vm.SISTEMA!r}")
print(f"  quarentena_dias={vm.QUAR_DIAS}")
print()

# Roda selftest
sys.argv = ["visualizador", "selftest"]
sys.exit(vm.main())
