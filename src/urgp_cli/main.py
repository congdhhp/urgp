"""URGP CLI — Build Data Collection Tool.

Main Typer application defining the ``urgp-cli`` command-line interface.
Commands:
    - ``push``: Collect build metadata and transmit to URGP Event Gateway
    - ``verify``: Verify an existing build manifest's integrity

Reference:
    - docs/05-technical-design.md § Layer 1: Execution Edge
    - docs/07-implementation-plan.md § P1-2.1
    - Requirements: R3.1, R3.2, R3.10, R19.4
"""

from __future__ import annotations

from typing import Optional

import typer

from urgp_cli import __version__

# Data contract schema version (independent of CLI version)
_DATA_CONTRACT_VERSION = "v1"

app = typer.Typer(
    name="urgp-cli",
    help="URGP CLI — Build Data Collection Tool for the Universal Release Governance Platform.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=True,
    pretty_exceptions_show_locals=False,
)


def _version_callback(value: bool) -> None:
    """Print version information and exit."""
    if value:
        typer.echo(f"urgp-cli v{__version__} (data-contract: {_DATA_CONTRACT_VERSION})")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(  # noqa: UP007
        None,
        "--version",
        "-V",
        help="Show CLI version and data contract schema version.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """URGP CLI — Build Data Collection Tool.

    Collects build metadata, computes artifact checksums, and transmits
    structured payloads to the URGP Event Gateway for centralized release
    governance and traceability.
    """


# ── Register sub-commands ──────────────────────────────────────────

# Import commands after app is created to avoid circular imports
from urgp_cli.commands.push import push_command  # noqa: E402
from urgp_cli.commands.verify import verify_command  # noqa: E402

app.command(name="push", help="Push build data to URGP Event Gateway.")(push_command)
app.command(name="verify", help="Verify an existing build manifest.")(verify_command)
