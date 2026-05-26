# Principal: visualizador.exe no top level de EXECUTAVEIS/ — entry point
# clicado pelo usuario. Le config, decide se atualiza, spawna o core.
from pathlib import Path

SRC = str(Path("../src").resolve())

a = Analysis(
    [str(Path("../src/launcher/principal.py").resolve())],
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
    name="visualizador",
    debug=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=False,                # noconsole — clica e abre, sem terminal
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
)
