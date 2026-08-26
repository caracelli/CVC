"""Sobe o visualizador como servidor HTTP (sem abrir navegador)
para validacao via curl/requests."""
import os
import sys
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parent.parent
RAIZ_APP = RAIZ_PROJETO / "CVC_IAM_ANALYTICS"

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
vm.DB_PATH = vm.BANCO_LOCAL
vm.LOG_PATH = str(RAIZ_APP / "DADOS" / "LOGS" / "visualizador_dev.log")
vm.REDE_RAIZ, vm.BANCO_SUB, vm.SISTEMA, vm.QUAR_DIAS, vm.META_ACESSOS_DESLIG, vm.CONFIG_SRC = vm.carregar_config()

os.environ["VISUALIZADOR_NOBROWSER"] = "1"
sys.argv = ["visualizador"]
sys.exit(vm.main())
