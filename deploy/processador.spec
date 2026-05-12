# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec para o Processador IAM Analytics CVC
# Executar de dentro da pasta deploy/: pyinstaller processador.spec

from pathlib import Path

SRC = str(Path("../src").resolve())

block_cipher = None

a = Analysis(
    [str(Path("../src/processador/main.py").resolve())],
    pathex=[SRC],
    binaries=[],
    datas=[],
    hiddenimports=[
        # SQLAlchemy
        "sqlalchemy.dialects.sqlite",
        "sqlalchemy.pool",
        "sqlalchemy.orm",
        # PyArrow
        "pyarrow",
        "pyarrow.pandas_compat",
        "pyarrow.lib",
        # Pandas / openpyxl
        "pandas",
        "openpyxl",
        "openpyxl.cell._writer",
        "xlrd",
        # Encoding
        "chardet",
        # Loguru
        "loguru",
        # Módulos do projeto
        "dominio",
        "dominio.entidades",
        "dominio.objetos_valor",
        "dominio.interfaces",
        "dominio.regras",
        "dominio.servicos_dominio",
        "aplicacao",
        "aplicacao.casos_de_uso",
        "infraestrutura",
        "infraestrutura.banco_dados",
        "infraestrutura.configuracao",
        "infraestrutura.escritores_arquivos",
        "infraestrutura.leitores_arquivos",
        "infraestrutura.repositorios",
        "infraestrutura.power_bi",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib", "seaborn", "IPython", "jupyter",
        "tkinter", "scipy", "sklearn",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="Processador",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
