"""Build script for URGP CLI single-binary distribution.

Wraps PyInstaller to build platform-specific binaries.
Requires PyInstaller to be installed: pip install pyinstaller

Usage:
    python scripts/build_cli.py

Output:
    dist/urgp-cli       (Linux)
    dist/urgp-cli.exe   (Windows)

Reference:
    - docs/07-implementation-plan.md § P1-2.6
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    """Build the URGP CLI binary using PyInstaller."""
    project_root = Path(__file__).resolve().parent.parent
    spec_file = project_root / "urgp-cli.spec"

    if not spec_file.exists():
        print(f"ERROR: PyInstaller spec file not found at {spec_file}")
        sys.exit(1)

    print("=" * 60)
    print("URGP CLI — Binary Build")
    print(f"  Platform:  {sys.platform}")
    print(f"  Python:    {sys.version}")
    print(f"  Spec file: {spec_file}")
    print("=" * 60)

    # Verify PyInstaller is available
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("\nERROR: PyInstaller is not installed.")
        print("  Install it with: pip install pyinstaller")
        sys.exit(1)

    # Run PyInstaller
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        str(spec_file),
        "--clean",
        "--noconfirm",
    ]

    print(f"\nRunning: {' '.join(cmd)}\n")

    result = subprocess.run(cmd, cwd=str(project_root))

    if result.returncode != 0:
        print(f"\nERROR: PyInstaller failed with exit code {result.returncode}")
        sys.exit(result.returncode)

    # Report output
    dist_dir = project_root / "dist"
    exe_name = "urgp-cli.exe" if sys.platform == "win32" else "urgp-cli"
    exe_path = dist_dir / exe_name

    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"\nSUCCESS: Binary built at {exe_path}")
        print(f"  Size: {size_mb:.1f} MB")
        print(f"\nTest with: {exe_path} --version")
    else:
        print(f"\nWARNING: Expected binary not found at {exe_path}")
        print("  Check the dist/ directory for output.")


if __name__ == "__main__":
    main()
