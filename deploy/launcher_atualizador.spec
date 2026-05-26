# launcher_atualizador.exe — vive em EXECUTAVEIS/launcher/.
# Engine de update + splash HTML. Chamado pelo principal quando precisa.
from pathlib import Path

SRC = str(Path("../src").resolve())

a = Analysis(
    [str(Path("../src/launcher/atualizador.py").resolve())],
    pathex=[SRC],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    excludes=["matplotlib", "seaborn", "IPython", "jupyter", "tkinter",
              "scipy", "sklearn", "pandas", "openpyxl", "pyarrow"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data)
exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name="launcher_atualizador",
    debug=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
)
