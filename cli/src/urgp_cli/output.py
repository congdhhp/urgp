"""Console output formatting for URGP CLI.

Provides styled terminal output using Rich (bundled with Typer[all])
for progress bars, status messages, tables, and error formatting.

Reference:
    - docs/07-implementation-plan.md § P1-2.1
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

if TYPE_CHECKING:
    from urgp_cli.adapters.base import AdapterResult
    from urgp_cli.contracts.data_contract import ArtifactPayload, BuildEventPayload
    from urgp_cli.transport.client import PushResult

# Shared console instances
console = Console()
err_console = Console(stderr=True)


def print_banner(version: str) -> None:
    """Print the CLI banner with version info."""
    console.print(
        Panel(
            f"[bold cyan]URGP CLI[/bold cyan] v{version}",
            subtitle="Universal Release Governance Platform",
            border_style="cyan",
        )
    )


def print_artifact_summary(artifacts: list[ArtifactPayload]) -> None:
    """Print a summary table of processed artifacts."""
    table = Table(title="Artifacts", show_lines=False)
    table.add_column("Name", style="white", no_wrap=True)
    table.add_column("Type", style="cyan")
    table.add_column("SHA-256", style="dim", max_width=16)
    table.add_column("Size", style="green", justify="right")

    for art in artifacts:
        size_str = _format_bytes(art.size_bytes) if art.size_bytes else "—"
        sha_short = art.sha256[:12] + "…"
        table.add_row(art.name, art.type.value, sha_short, size_str)

    console.print(table)


def print_payload_summary(payload: BuildEventPayload) -> None:
    """Print a summary of the constructed payload."""
    console.print()
    console.print(f"  [bold]Product:[/bold]     {payload.product_id}")
    console.print(f"  [bold]Release:[/bold]     {payload.release}")
    console.print(f"  [bold]Build ID:[/bold]    {payload.build_id}")
    console.print(f"  [bold]Build Type:[/bold]  {payload.build_type.value}")
    console.print(f"  [bold]Commits:[/bold]     {len(payload.commit_hashes)}")
    console.print(f"  [bold]Artifacts:[/bold]   {len(payload.artifacts)}")
    console.print()


def print_push_result(result: PushResult) -> None:
    """Print the result of a push operation."""
    if result.success:
        console.print(f"[bold green]✓[/bold green] {result.message}")
    else:
        err_console.print(f"[bold red]✗[/bold red] {result.message}")
        if result.fallback_path:
            err_console.print(f"  [dim]Fallback file: {result.fallback_path}[/dim]")


def print_adapter_result(adapter_type: str, result: AdapterResult) -> None:
    """Print adapter extraction results."""
    if result.errors:
        for error in result.errors:
            err_console.print(f"  [yellow]⚠[/yellow] [{adapter_type}] {error}")


def print_error(message: str) -> None:
    """Print an error message to stderr."""
    err_console.print(f"[bold red]Error:[/bold red] {message}")


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[bold green]✓[/bold green] {message}")


def print_info(message: str) -> None:
    """Print an informational message."""
    console.print(f"[dim]i[/dim] {message}")


def print_step(step: int, total: int, message: str) -> None:
    """Print a progress step indicator."""
    console.print(f"  [cyan][{step}/{total}][/cyan] {message}")


def _format_bytes(size: int | None) -> str:
    """Format a byte count as a human-readable string."""
    if size is None:
        return "—"
    for unit in ("B", "KB", "MB", "GB"):
        if abs(size) < 1024.0:
            return f"{size:.1f} {unit}"
        size = int(size / 1024)
    return f"{size:.1f} TB"
