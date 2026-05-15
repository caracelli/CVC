import sys
import os
import re
import glob
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# main.py -> src/visualizador -> src -> raiz do projeto
_script_dir = os.path.dirname(os.path.abspath(__file__))
_src_dir    = os.path.dirname(_script_dir)
PROJECT_ROOT = os.path.dirname(_src_dir)

# Arquivo local (gitignored) que guarda o caminho do PBIDesktop.exe desta maquina
_LOCAL_PBI_CACHE = os.path.join(PROJECT_ROOT, 'CVC_IAM_ANALYTICS', '.pbi_local')

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


# ── cache local do PBIDesktop.exe (gitignored) ───────────────────────────────

def _ler_cache_pbi():
    try:
        if os.path.isfile(_LOCAL_PBI_CACHE):
            return open(_LOCAL_PBI_CACHE, encoding='utf-8').read().strip()
    except Exception:
        pass
    return ""


def _salvar_cache_pbi(exe_path):
    try:
        with open(_LOCAL_PBI_CACHE, 'w', encoding='utf-8') as f:
            f.write(exe_path)
        print(f"  [CACHE] Caminho salvo em .pbi_local: {exe_path}")
    except Exception as e:
        print(f"  [AVISO] Nao foi possivel salvar cache: {e}")


# ── busca do PBIDesktop.exe ───────────────────────────────────────────────────

_CANDIDATOS_FIXOS = [
    r"C:\Program Files\Microsoft Power BI Desktop\bin\PBIDesktop.exe",
    r"C:\Program Files (x86)\Microsoft Power BI Desktop\bin\PBIDesktop.exe",
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WindowsApps", "PBIDesktop.exe"),
]


def _buscar_pbi():
    """Tenta todas as estrategias para localizar PBIDesktop.exe."""

    # 1) caminhos fixos
    for path in _CANDIDATOS_FIXOS:
        if os.path.isfile(path):
            return path

    # 2) glob com sufixo de versao
    for padrao in [
        r"C:\Program Files\Microsoft Power BI Desktop*\bin\PBIDesktop.exe",
        r"C:\Program Files (x86)\Microsoft Power BI Desktop*\bin\PBIDesktop.exe",
    ]:
        hits = glob.glob(padrao)
        if hits:
            return hits[0]

    # 3) where.exe (PATH do sistema)
    try:
        r = subprocess.run(["where", "PBIDesktop.exe"],
                           capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            linha = r.stdout.strip().splitlines()[0]
            if os.path.isfile(linha):
                return linha
    except Exception:
        pass

    # 4) Microsoft Store — Get-AppxPackage (WindowsApps nao acessivel por glob)
    try:
        ps = ("(Get-AppxPackage *MicrosoftPowerBIDesktop* "
              "| Select-Object -First 1).InstallLocation")
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=15
        )
        install_dir = r.stdout.strip()
        if r.returncode == 0 and install_dir:
            exe = os.path.join(install_dir, "bin", "PBIDesktop.exe")
            # Store apps existem mas o os.path.isfile pode retornar False por permissao
            # tenta de qualquer forma e deixa o subprocess lidar com o erro
            return exe
    except Exception as e:
        print(f"  [DEBUG] AppxPackage falhou: {e}")

    return None


def _resolver_pbi_exe():
    caminho = _ler_cache_pbi()

    if caminho and os.path.isfile(caminho):
        print(f"  [CACHE] Power BI Desktop: {caminho}")
        return caminho

    if caminho:
        print(f"  [CACHE] Caminho invalido ({caminho}) — rebuscando...")
    else:
        print("  Power BI nao configurado — buscando no sistema...")

    exe = _buscar_pbi()
    if exe:
        _salvar_cache_pbi(exe)
        return exe

    print("  [AVISO] PBIDesktop.exe nao encontrado em nenhum caminho padrao.")
    return None


# ── lancamento do Power BI ────────────────────────────────────────────────────

def abrir_power_bi():
    if not os.path.isfile(PBIP_FILE):
        print(f"  [ERRO] .pbip nao encontrado: {PBIP_FILE}")
        return

    print(f"  Arquivo: {PBIP_FILE}")
    pbi_exe = _resolver_pbi_exe()

    if pbi_exe:
        print(f"  Executavel: {pbi_exe}")

        # Tentativa 1: shell=True usa cmd.exe — funciona para Store e Program Files
        try:
            cmd_str = f'"{pbi_exe}" "{PBIP_FILE}"'
            subprocess.Popen(cmd_str, shell=True)
            print("  [OK] Power BI aberto (shell).")
            return
        except Exception as e:
            print(f"  [T1] shell falhou: {e}")

        # Tentativa 2: cmd /c start (garante abertura via shell do Windows)
        try:
            subprocess.Popen(
                ['cmd', '/c', 'start', '', pbi_exe, PBIP_FILE],
                shell=False
            )
            print("  [OK] Power BI aberto (cmd start).")
            return
        except Exception as e:
            print(f"  [T2] cmd start falhou: {e}")

    # Tentativa 3: AppxPackage via PowerShell
    print("  Tentando via AppxPackage + PowerShell...")
    pbip_q = PBIP_FILE.replace("'", "''")
    ps_appx = (
        "$pkg = Get-AppxPackage *MicrosoftPowerBIDesktop* | Select-Object -First 1; "
        "if ($pkg) { "
        "  $exe = Join-Path $pkg.InstallLocation 'bin\\PBIDesktop.exe'; "
        f"  Start-Process -FilePath $exe -ArgumentList '\"{pbip_q}\"'; "
        "  exit 0 } else { Write-Error 'PBI nao instalado via Store'; exit 1 }"
    )
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_appx],
        capture_output=True, text=True, timeout=20
    )
    if r.returncode == 0:
        print("  [OK] Power BI aberto via AppxPackage.")
        return
    if r.stderr.strip():
        print(f"  [T3 STDERR] {r.stderr.strip()}")

    # Tentativa 4: Start-Process com o .pbip (associacao de arquivo)
    print("  Tentando abertura por associacao de arquivo (.pbip)...")
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         f"Start-Process -FilePath '{PBIP_FILE}'"],
        capture_output=True, text=True, timeout=10
    )
    if r.returncode == 0:
        print("  [OK] Arquivo aberto por associacao.")
        return
    if r.stderr.strip():
        print(f"  [T4 STDERR] {r.stderr.strip()}")

    # Tentativa 5: os.startfile
    try:
        os.startfile(PBIP_FILE)
        print("  [OK] Arquivo aberto via startfile.")
        return
    except Exception as e:
        print(f"  [T5] startfile falhou: {e}")

    print("\n  [ERRO] Nao foi possivel abrir o Power BI Desktop.")
    print("  Certifique-se de que o Power BI Desktop esta instalado.")
    print(f"  Abra manualmente: {PBIP_FILE}")


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
            lambda m: m.group(1) + caminho_base + m.group(3), original
        )
        if atualizado != original:
            with open(tmdl, 'w', encoding='utf-8') as f:
                f.write(atualizado)
            print(f"  [ATUALIZADO] {tmdl}")
        else:
            print(f"  [OK] {tmdl}")

    return caminho_base


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
