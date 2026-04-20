# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for URGP CLI single-binary distribution.

Builds a standalone executable for Linux and Windows.

Usage:
    python -m PyInstaller urgp-cli.spec

Output:
    dist/urgp-cli       (Linux)
    dist/urgp-cli.exe   (Windows)

Reference:
    - docs/07-implementation-plan.md § P1-2.6
"""

import sys
from pathlib import Path

block_cipher = None

# Determine platform-specific settings
is_windows = sys.platform == "win32"
exe_name = "urgp-cli.exe" if is_windows else "urgp-cli"


a = Analysis(
    ["src/urgp_cli/main.py"],
    pathex=["src"],
    binaries=[],
    datas=[],
    hiddenimports=[
        "urgp_cli",
        "urgp_cli.adapters",
        "urgp_cli.adapters.generic",
        "urgp_cli.adapters.eclipse_p2",
        "urgp_cli.adapters.registry",
        "urgp_cli.checksum",
        "urgp_cli.commands",
        "urgp_cli.commands.push",
        "urgp_cli.commands.verify",
        "urgp_cli.contracts",
        "urgp_cli.contracts.data_contract",
        "urgp_cli.transport",
        "urgp_cli.transport.client",
        "urgp_cli.output",
        # Typer dependencies
        "typer",
        "click",
        "rich",
        # HTTP client
        "httpx",
        "httpcore",
        "certifi",
        "h11",
        # Pydantic
        "pydantic",
        "pydantic_core",
        "annotated_types",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude server-side dependencies not needed by CLI
        "fastapi",
        "uvicorn",
        "sqlalchemy",
        "asyncpg",
        "alembic",
        "aio_pika",
        "redis",
        "structlog",
        "pydantic_settings",
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
    name=exe_name,
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
)
