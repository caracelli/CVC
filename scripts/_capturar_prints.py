# -*- coding: utf-8 -*-
"""Sobe o Visualizador em thread (banco do cliente) e captura PNG das 6 telas
via Edge headless. Saida: docs/prints_painel/*.png  (usado pelo gerador do .docx)."""
import os, sys, time, shutil, tempfile, threading
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
import visualizador.main as vm

tmp = tempfile.mkdtemp(prefix="cvc_print_")
db = os.path.join(tmp, "iam.db")
shutil.copy(str(RAIZ / "Arquivos_origem" / "DADOS" / "BANCO" / "iam_analytics.db"), db)
vm.DB_PATH = db
vm.SISTEMA = ""
vm._BASE = None
vm._SEM_BANCO = False
vm.PASTA_INTERACOES = os.path.join(tmp, "INTERACOES")
os.makedirs(vm.PASTA_INTERACOES, exist_ok=True)
report = RAIZ / "CVC_IAM_ANALYTICS" / "EXECUTAVEIS" / "REPORT"
vm.REPORT_DIR = str(report)
vm.INDEX_PATH = str(report / "index.html")
vm.garantir_estrutura(force=True)

srv = vm.ThreadingHTTPServer((vm.HOST, vm.PORT), vm.H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
time.sleep(1.0)
print("servidor no ar em 127.0.0.1:8800")

from selenium import webdriver
from selenium.webdriver.edge.options import Options

opt = Options()
opt.add_argument("--headless=new")
opt.add_argument("--window-size=1500,1150")
opt.add_argument("--hide-scrollbars")
opt.add_argument("--force-device-scale-factor=1")
drv = webdriver.Edge(options=opt)
drv.set_window_size(1500, 1150)
drv.get("http://127.0.0.1:8800/")
time.sleep(4.0)

out = RAIZ / "docs" / "prints_painel"
out.mkdir(parents=True, exist_ok=True)
tabs = [("vg", "01_visao_geral"), ("consulta", "02_consulta"),
        ("incl", "03_pendencias"), ("conf", "04_aderentes"),
        ("hist", "05_historico"), ("quar", "06_quarentena")]
for tab, nome in tabs:
    try:
        drv.execute_script(
            "var e=document.querySelector('[data-tab=\"%s\"]'); if(e)e.click();" % tab)
        time.sleep(2.8)
        drv.execute_script("window.scrollTo(0,0);")
        time.sleep(0.3)
        drv.save_screenshot(str(out / (nome + ".png")))
        print("print:", nome, "OK")
    except Exception as e:
        print("print:", nome, "FALHOU", repr(e))

drv.quit()
srv.shutdown()
print("CONCLUIDO ->", out)
