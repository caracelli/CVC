import sys
import os
import re
import subprocess
import glob

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# main.py → src/visualizador → src → raiz do projeto
_script_dir = os.path.dirname(os.path.abspath(__file__))
_src_dir = os.path.dirname(_script_dir)
PROJECT_ROOT = os.path.dirname(_src_dir)

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


def atualizar_caminho_base():
    caminho_base = os.path.join(PROJECT_ROOT, 'CVC_IAM_ANALYTICS') + os.sep

    for tmdl in EXPRESSIONS_FILES:
        if not os.path.isfile(tmdl):
            print(f"  [AVISO] não encontrado: {tmdl}")
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
            print(f"  [SEM ALTERAÇÃO] {tmdl}")

    return caminho_base


_PBI_CANDIDATOS = [
    r"C:\Program Files\Microsoft Power BI Desktop\bin\PBIDesktop.exe",
    r"C:\Program Files (x86)\Microsoft Power BI Desktop\bin\PBIDesktop.exe",
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WindowsApps", "PBIDesktop.exe"),
]


def _encontrar_pbi():
    for path in _PBI_CANDIDATOS:
        if os.path.isfile(path):
            return path
    # busca em Program Files (cobre versoes com sufixo de versão)
    for padrao in [
        r"C:\Program Files\Microsoft Power BI Desktop*\bin\PBIDesktop.exe",
        r"C:\Program Files (x86)\Microsoft Power BI Desktop*\bin\PBIDesktop.exe",
    ]:
        encontrados = glob.glob(padrao)
        if encontrados:
            return encontrados[0]
    # busca via where.exe (PATH do sistema)
    try:
        resultado = subprocess.run(
            ["where", "PBIDesktop.exe"], capture_output=True, text=True, timeout=5
        )
        if resultado.returncode == 0:
            linha = resultado.stdout.strip().splitlines()[0]
            if os.path.isfile(linha):
                return linha
    except Exception:
        pass
    return None


def abrir_power_bi():
    if not os.path.isfile(PBIP_FILE):
        print(f"  [ERRO] arquivo .pbip nao encontrado: {PBIP_FILE}")
        return

    print(f"  Arquivo: {PBIP_FILE}")

    # tenta abrir diretamente pelo executável
    pbi_exe = _encontrar_pbi()
    if pbi_exe:
        print(f"  Power BI Desktop: {pbi_exe}")
        subprocess.Popen([pbi_exe, PBIP_FILE])
        return

    # fallback via PowerShell Start-Process (mais confiável que os.startfile no Windows)
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

    # último recurso: associação de arquivo do Windows
    try:
        os.startfile(PBIP_FILE)
        return
    except Exception as e:
        pass

    print("  [ERRO] Nao foi possivel abrir o Power BI Desktop.")
    print("  Verifique se ele esta instalado e abra manualmente:")
    print(f"  {PBIP_FILE}")


def main():
    print("=" * 55)
    print("  IAM Analytics — Visualizador CVC")
    print("=" * 55)

    print(f"\nRaiz do projeto: {PROJECT_ROOT}\n")

    print("Atualizando CaminhoBase nos arquivos TMDL...")
    caminho_base = atualizar_caminho_base()
    print(f"  CaminhoBase -> {caminho_base}\n")

    print("Abrindo Power BI Desktop...")
    abrir_power_bi()

    print("\nConcluído.")


if __name__ == "__main__":
    main()
