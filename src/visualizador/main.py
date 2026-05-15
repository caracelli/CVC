import sys
import os
import re
import glob
import subprocess
import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# main.py -> src/visualizador -> src -> raiz do projeto
_script_dir = os.path.dirname(os.path.abspath(__file__))
_src_dir    = os.path.dirname(_script_dir)
PROJECT_ROOT = os.path.dirname(_src_dir)

# Log salvo ao lado do proprio script para facil acesso
_LOG_FILE = os.path.join(_script_dir, 'visualizador_log.txt')
_log_lines = []

def _print(msg=""):
    """Imprime no terminal e acumula para o arquivo de log."""
    print(msg)
    _log_lines.append(msg)

def _salvar_log():
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(_LOG_FILE, 'w', encoding='utf-8') as f:
            f.write(f"=== Log gerado em {ts} ===\n\n")
            f.write("\n".join(_log_lines))
            f.write("\n")
        _print(f"\nLog salvo em: {_LOG_FILE}")
    except Exception as e:
        print(f"Nao foi possivel salvar log: {e}")

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
        _print(f"  [CACHE] Caminho salvo em .pbi_local: {exe_path}")
    except Exception as e:
        _print(f"  [AVISO] Nao foi possivel salvar cache: {e}")


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
        _print(f"  [DEBUG] AppxPackage falhou: {e}")

    return None


def _resolver_pbi_exe():
    caminho = _ler_cache_pbi()

    if caminho and os.path.isfile(caminho):
        _print(f"  [CACHE] Power BI Desktop: {caminho}")
        return caminho

    if caminho:
        _print(f"  [CACHE] Caminho invalido ({caminho}) — rebuscando...")
    else:
        _print("  Power BI nao configurado — buscando no sistema...")

    exe = _buscar_pbi()
    if exe:
        _salvar_cache_pbi(exe)
        return exe

    _print("  [AVISO] PBIDesktop.exe nao encontrado em nenhum caminho padrao.")
    return None


# ── lancamento do Power BI ────────────────────────────────────────────────────

def abrir_power_bi():
    if not os.path.isfile(PBIP_FILE):
        _print(f"  [ERRO] .pbip nao encontrado: {PBIP_FILE}")
        return

    _print(f"  Arquivo: {PBIP_FILE}")
    pbi_exe = _resolver_pbi_exe()

    if pbi_exe:
        _print(f"  Executavel: {pbi_exe}")

    # T1: exe direto — mais confiavel para instalacao tradicional (Program Files)
    if pbi_exe and "WindowsApps" not in pbi_exe:
        try:
            import time
            proc = subprocess.Popen([pbi_exe, PBIP_FILE])
            _print(f"  [T1] Processo iniciado. PID={proc.pid}")
            time.sleep(4)
            rc = proc.poll()
            if rc is None:
                _print("  [OK] Power BI aberto (exe direto) — processo ativo.")
                return
            else:
                _print(f"  [T1] Processo encerrou rapidamente. Codigo={rc}")
        except Exception as e:
            _print(f"  [T1] Popen falhou: {e}")

    # T2: cmd /c start (usa associacao de arquivo .pbip do Windows)
    try:
        r = subprocess.run(
            ['cmd', '/c', 'start', '', PBIP_FILE],
            capture_output=True, text=True, timeout=10
        )
        if r.returncode == 0:
            _print("  [OK] Power BI aberto (cmd start).")
            return
        _print(f"  [T2] cmd start retornou {r.returncode}: {r.stderr.strip()}")
    except Exception as e:
        _print(f"  [T2] cmd start falhou: {e}")

    # T3: os.startfile (ShellExecuteEx — equivale a duplo clique)
    try:
        os.startfile(PBIP_FILE)
        _print("  [OK] Power BI aberto (startfile).")
        return
    except Exception as e:
        _print(f"  [T3] startfile falhou: {e}")

    # T4: AppxPackage via PowerShell (Store app)
    _print("  Tentando via AppxPackage + PowerShell...")
    pbip_q = PBIP_FILE.replace("'", "''")
    ps_appx = (
        "$pkg = Get-AppxPackage *MicrosoftPowerBIDesktop* | Select-Object -First 1; "
        "if ($pkg) { "
        "  $exe = Join-Path $pkg.InstallLocation 'bin\\PBIDesktop.exe'; "
        f"  Start-Process -FilePath $exe -ArgumentList '\"{pbip_q}\"'; "
        "  exit 0 } else { Write-Error 'PBI nao encontrado via Store'; exit 1 }"
    )
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_appx],
        capture_output=True, text=True, timeout=20
    )
    if r.returncode == 0:
        _print("  [OK] Power BI aberto via AppxPackage.")
        return
    _print(f"  [T4 STDERR] {r.stderr.strip()}")

    _print("\n  [ERRO] Nenhuma estrategia funcionou.")
    _print("  Certifique-se de que o Power BI Desktop esta instalado.")
    _print(f"  Tente abrir manualmente: {PBIP_FILE}")


# ── TMDL ──────────────────────────────────────────────────────────────────────

def atualizar_caminho_base():
    caminho_base = os.path.join(PROJECT_ROOT, 'CVC_IAM_ANALYTICS') + os.sep

    for tmdl in EXPRESSIONS_FILES:
        if not os.path.isfile(tmdl):
            _print(f"  [AVISO] nao encontrado: {tmdl}")
            continue
        with open(tmdl, 'r', encoding='utf-8') as f:
            original = f.read()
        atualizado = _PATTERN.sub(
            lambda m: m.group(1) + caminho_base + m.group(3), original
        )
        if atualizado != original:
            with open(tmdl, 'w', encoding='utf-8') as f:
                f.write(atualizado)
            _print(f"  [ATUALIZADO] {tmdl}")
        else:
            _print(f"  [OK] {tmdl}")

    return caminho_base


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    _print("=" * 55)
    _print("  IAM Analytics - Visualizador CVC")
    _print("=" * 55)
    _print(f"\nRaiz do projeto: {PROJECT_ROOT}\n")

    _print("Atualizando CaminhoBase nos arquivos TMDL...")
    caminho_base = atualizar_caminho_base()
    _print(f"  CaminhoBase -> {caminho_base}\n")

    _print("Abrindo Power BI Desktop...")
    abrir_power_bi()

    _print("\nConcluido.")
    _salvar_log()


if __name__ == "__main__":
    main()
