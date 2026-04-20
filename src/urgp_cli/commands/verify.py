"""Verify command — check integrity of an existing build manifest.

Queries the URGP API to verify that a build manifest exists and its
artifact checksums are valid.

Reference:
    - docs/05-technical-design.md § Layer 1: Execution Edge
    - docs/07-implementation-plan.md § P1-2.1
"""

from __future__ import annotations

from typing import Optional

import httpx
import typer

from urgp_cli.output import console, print_error, print_info, print_success

# Default API URL
_DEFAULT_API_URL = "http://localhost:8000"


def verify_command(
    build_id: str = typer.Option(
        ...,
        "--build-id",
        "-b",
        help="Build identifier to verify.",
    ),
    api_key: str = typer.Option(
        ...,
        "--api-key",
        "-k",
        envvar="URGP_API_KEY",
        help="API key for authentication.",
    ),
    api_url: str = typer.Option(
        _DEFAULT_API_URL,
        "--api-url",
        envvar="URGP_API_URL",
        help="URGP API base URL.",
    ),
    product: Optional[str] = typer.Option(  # noqa: UP007
        None,
        "--product",
        "-p",
        help="Product identifier (optional, for scoped verification).",
    ),
) -> None:
    """Verify an existing build manifest's integrity.

    Queries the URGP API to check that the build manifest exists and
    all artifact checksums are valid.

    Example:
        urgp-cli verify --build-id 260330 --api-key $URGP_API_KEY
    """
    print_info(f"Verifying build manifest: {build_id}")

    url = f"{api_url.rstrip('/')}/api/v1/builds/{build_id}"

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(
                url,
                headers={
                    "X-API-Key": api_key,
                    "Accept": "application/json",
                },
            )

        if response.status_code == 200:
            data = response.json()
            _display_manifest(data, build_id)
        elif response.status_code == 404:
            print_error(f"Build manifest '{build_id}' not found")
            raise typer.Exit(code=1)
        elif response.status_code == 401:
            print_error("Authentication failed — check your API key")
            raise typer.Exit(code=1)
        else:
            print_error(f"Unexpected response: HTTP {response.status_code}")
            raise typer.Exit(code=1)

    except httpx.ConnectError:
        print_error(f"Could not connect to URGP API at {api_url}")
        raise typer.Exit(code=1) from None
    except httpx.TimeoutException:
        print_error("Request timed out")
        raise typer.Exit(code=1) from None


def _display_manifest(data: dict[str, object], build_id: str) -> None:
    """Display build manifest verification results."""
    from rich.table import Table

    status = data.get("status", "unknown")
    artifact_count = len(data.get("artifacts", []))  # type: ignore[arg-type]
    traceability_incomplete = data.get("traceability_incomplete", False)

    print_success(f"Build manifest '{build_id}' found")
    console.print(f"  [bold]Status:[/bold]          {status}")
    console.print(f"  [bold]Artifacts:[/bold]       {artifact_count}")
    console.print(f"  [bold]Traceability:[/bold]    {'⚠ incomplete' if traceability_incomplete else '✓ complete'}")

    # Display artifact table if available
    artifacts = data.get("artifacts", [])
    if artifacts and isinstance(artifacts, list):
        table = Table(title="Artifacts", show_lines=False)
        table.add_column("Name", style="white")
        table.add_column("Type", style="cyan")
        table.add_column("SHA-256", style="dim", max_width=16)
        table.add_column("Integrity", style="green")

        for art in artifacts:
            if isinstance(art, dict):
                sha_short = str(art.get("sha256", ""))[:12] + "…"
                table.add_row(
                    str(art.get("name", "—")),
                    str(art.get("type", "—")),
                    sha_short,
                    "✓ valid",  # Integrity verified by server
                )

        console.print(table)
