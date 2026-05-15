import sys
import os
import re
import glob
import subprocess
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# main.py -> src/visualizador -> src -> raiz do projeto
_script_dir = os.path.dirname(os.path.abspath(__file__))
_src_dir = os.path.dirname(_script_dir)
PROJECT_ROOT = os.path.dirname(_src_dir)

CONFIG_XML = os.path.join(PROJECT_ROOT, 'CVC_IAM_ANALYTICS', 'config.xml')

EXPRESSIONS_FILES = [
    os.path.join(PROJECT_ROOT, 'CVC_IAM_ANALYTICS', 'POWER_BI',
                 'CVC_IAM_Analytics.Dataset', 'definition', 'expressions.tmdl'),
    os.path.join(PROJECT_ROOT, 'CVC_IAM_ANALYTICS', 'POWER_BI_DEV',
                 'CVC_IAM_Analytics.Dataset', 'definition', 'expressions.tmdl'),
]

PBIP_FILE = os.path.join(
    PROJECT_ROOT, 'CVC_IAM_ANALYTICS', 'POWER_BI', 'CVC_IAM_Analytics.pbip'
)

_PATTERN = re.compile(r'(expression CaminhoBase = ")([^"]*)(" meta )')

_PBI_CANDIDATOS = [
    r"C:\Program Files\Microsoft Power BI Desktop\bin\PBIDesktop.exe",
    r"C:\Program Files (x86)\Microsoft Power BI Desktop\bin\PBIDesktop.exe",
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WindowsApps", "PBIDesktop.exe"),
]


# ── config.xml ────────────────────────────────────────────────────────────────

def _ler_pbi_do_xml():
    """Retorna o caminho salvo em <local><power_bi>, ou string vazia."""
    if not os.path.isfile(CONFIG_XML):
        return ""
    try:
        tree = ET.parse(CONFIG_XML)
        node = tree.getroot().find("local/power_bi")
        return (node.text or "").strip() if node is not None else ""
    except Exception:
        return ""


def _salvar_pbi_no_xml(exe_path):
    """Persiste o caminho do PBIDesktop.exe em <local><power_bi>."""
    if not os.path.isfile(CONFIG_XML):
        return
    try:
        ET.register_namespace("", "")
        tree = ET.parse(CONFIG_XML)
        root = tree.getroot()

        local = root.find("local")
        if local is None:
            local = ET.SubElement(root, "local")

        node = local.find("power_bi")
        if node is None:
            node = ET.SubElement(local, "power_bi")

        node.text = exe_path
        tree.write(CONFIG_XML, encoding="UTF-8", xml_declaration=True)
        print(f"  [XML] Caminho salvo em config.xml: {exe_path}")
    except Exception as e:
        print(f"  [AVISO] Nao foi possivel salvar no config.xml: {e}")


# ── busca do PBIDesktop.exe ───────────────────────────────────────────────────

def _buscar_pbi_no_sistema():
    """Procura PBIDesktop.exe em caminhos padrao e via where.exe."""
    for path in _PBI_CANDIDATOS:
        if os.path.isfile(path):
            return path

    for padrao in [
        r"C:\Program Files\Microsoft Power BI Desktop*\bin\PBIDesktop.exe",
        r"C:\Program Files (x86)\Microsoft Power BI Desktop*\bin\PBIDesktop.exe",
    ]:
        encontrados = glob.glob(padrao)
        if encontrados:
            return encontrados[0]

    try:
        resultado = subprocess.run(
            ["where", "PBIDesktop.exe"],
            capture_output=True, text=True, timeout=5
        )
        if resultado.returncode == 0:
            linha = resultado.stdout.strip().splitlines()[0]
            if os.path.isfile(linha):
                return linha
    except Exception:
        pass

    return None


def _resolver_pbi_exe():
    """
    1. Le o caminho do config.xml.
    2. Se valido, usa diretamente.
    3. Se invalido/vazio, busca no sistema e salva no XML.
    """
    caminho_salvo = _ler_pbi_do_xml()

    if caminho_salvo and os.path.isfile(caminho_salvo):
        print(f"  [XML] Power BI Desktop: {caminho_salvo}")
        return caminho_salvo

    if caminho_salvo:
        print(f"  [XML] Caminho salvo invalido ({caminho_salvo}) — buscando novamente...")
    else:
        print("  Caminho do Power BI nao configurado — buscando no sistema...")

    exe = _buscar_pbi_no_sistema()
    if exe:
        _salvar_pbi_no_xml(exe)
        return exe

    return None


# ── TMDL ──────────────────────────────────────────────────────────────────────

def atualizar_caminho_base():
    caminho_base = os.path.join(PROJECT_ROOT, 'CVC_IAM_ANALYTICS') + os.sep

    for tmdl in EXPRESSIONS_FILES:
        if not os.path.isfile(tmdl):
            print(f"  [AVISO] nao encontrado: {tmdl}")
            continue

        with open(tmdl, 'r', encoding='utf-8') as f:
            original = f.read()

        atualizado = _PATTERN.sub(
            lambda m: m.group(1) + caminho_base + m.group(3),
            original
        )

        if atualizado != original:
            with open(tmdl, 'w', encoding='utf-8') as f:
                f.write(atualizado)
            print(f"  [ATUALIZADO] {tmdl}")
        else:
            print(f"  [OK] {tmdl}")

    return caminho_base


# ── abertura do Power BI ──────────────────────────────────────────────────────

def abrir_power_bi():
    if not os.path.isfile(PBIP_FILE):
        print(f"  [ERRO] arquivo .pbip nao encontrado: {PBIP_FILE}")
        return

    print(f"  Arquivo: {PBIP_FILE}")

    pbi_exe = _resolver_pbi_exe()

    if pbi_exe:
        subprocess.Popen([pbi_exe, PBIP_FILE])
        return

    # fallback via PowerShell
    print("  Executavel nao localizado — abrindo via PowerShell...")
    try:
        subprocess.Popen(
            ["powershell", "-NoProfile", "-Command",
             f'Start-Process "{PBIP_FILE}"'],
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return
    except Exception:
        pass

    # ultimo recurso: associacao de arquivo do Windows
    try:
        os.startfile(PBIP_FILE)
        return
    except Exception:
        pass

    print("  [ERRO] Nao foi possivel abrir o Power BI Desktop.")
    print("  Verifique se ele esta instalado e abra manualmente:")
    print(f"  {PBIP_FILE}")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 55)
    print("  IAM Analytics - Visualizador CVC")
    print("=" * 55)
    print(f"\nRaiz do projeto: {PROJECT_ROOT}\n")

    print("Atualizando CaminhoBase nos arquivos TMDL...")
    caminho_base = atualizar_caminho_base()
    print(f"  CaminhoBase -> {caminho_base}\n")

    print("Abrindo Power BI Desktop...")
    abrir_power_bi()

    print("\nConcluido.")


if __name__ == "__main__":
    main()
