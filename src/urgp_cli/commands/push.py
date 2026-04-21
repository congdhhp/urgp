"""Push command -- collect build metadata and transmit to URGP Event Gateway.

Orchestrates the full CLI pipeline:
    1. Validate parameters
    2. Load adapter
    3. For each artifact: extract metadata + compute SHA-256 checksum
    4. Construct Data Contract payload
    5. Transmit to URGP API (with retry and fallback)
    6. Report results

Reference:
    - docs/05-technical-design.md - Layer 1: Execution Edge (Data Flow)
    - docs/07-implementation-plan.md - P1-2.1, P1-2.5
    - Requirements: R3.1 to R3.11
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import typer
from rich.progress import BarColumn, Progress, TextColumn, TimeRemainingColumn

from urgp_cli import __version__
from urgp_cli.adapters.registry import get_adapter, list_adapters
from urgp_cli.checksum import compute_sha256, should_report_progress
from urgp_cli.contracts.data_contract import (
    ArtifactPayload,
    ArtifactTypeEnum,
    BuildEventPayload,
    BuildTypeEnum,
    CIMetadata,
    CommitHash,
)
from urgp_cli.output import (
    console,
    print_adapter_result,
    print_artifact_summary,
    print_error,
    print_info,
    print_payload_summary,
    print_push_result,
    print_step,
    print_success,
)
from urgp_cli.transport.client import URGPClient

# Default API URL (can be overridden)
_DEFAULT_API_URL = "http://localhost:8000"


def _resolve_artifact_type(adapter_type: str) -> ArtifactTypeEnum:
    """Resolve an adapter type to the corresponding artifact enum."""
    normalized = adapter_type.strip().lower()
    try:
        return ArtifactTypeEnum(normalized)
    except ValueError as exc:
        available = ", ".join(artifact_type.value for artifact_type in ArtifactTypeEnum)
        msg = f"Adapter reported unsupported artifact type '{adapter_type}'. Supported types: {available}"
        raise ValueError(msg) from exc


def _build_storage_uri(artifact_path: Path, storage_uri_prefix: str) -> str:
    """Build a valid storage URI for an artifact."""
    if not storage_uri_prefix:
        return artifact_path.resolve().as_uri()

    normalized_prefix = storage_uri_prefix.strip()
    if not normalized_prefix.endswith("/"):
        normalized_prefix = f"{normalized_prefix}/"

    return f"{normalized_prefix}{quote(artifact_path.name)}"


def push_command(
    product: str = typer.Option(
        ...,
        "--product",
        "-p",
        help="Product identifier (e.g., 'S32_IDE').",
    ),
    release: str = typer.Option(
        ...,
        "--release",
        "-r",
        help="Release train version (e.g., '3.6.8-RFP').",
    ),
    build_type: BuildTypeEnum = typer.Option(
        ...,
        "--build-type",
        "-t",
        help="Build type classification.",
        case_sensitive=False,
    ),
    build_id: str = typer.Option(
        ...,
        "--build-id",
        "-b",
        help="Unique build identifier (e.g., '260330').",
    ),
    adapter: str = typer.Option(
        "generic",
        "--adapter",
        "-a",
        help=f"Artifact adapter type. Available: {', '.join(list_adapters())}.",
    ),
    artifact: list[str] = typer.Option(
        ...,
        "--artifact",
        help="Path to artifact file (can be specified multiple times).",
    ),
    commit_repo: list[str] = typer.Option(
        ...,
        "--commit-repo",
        help="Repository identifier for commit (paired with --commit-hash).",
    ),
    commit_hash: list[str] = typer.Option(
        ...,
        "--commit-hash",
        help="Commit hash (paired with --commit-repo).",
    ),
    api_key: str = typer.Option(
        ...,
        "--api-key",
        "-k",
        envvar="URGP_API_KEY",
        help="API key for authentication. Can also be set via URGP_API_KEY env var.",
    ),
    api_url: str = typer.Option(
        _DEFAULT_API_URL,
        "--api-url",
        envvar="URGP_API_URL",
        help="URGP API base URL.",
    ),
    storage_uri_prefix: str = typer.Option(
        "",
        "--storage-uri-prefix",
        help="Prefix for artifact storage URIs (e.g., 'https://artifacts.example.com/'). "
        "Artifact filename is appended automatically.",
    ),
    commit_branch: Optional[str] = typer.Option(  # noqa: UP007
        None,
        "--commit-branch",
        help="Branch name for all commits (optional).",
    ),
    ci_system: Optional[str] = typer.Option(  # noqa: UP007
        None,
        "--ci-system",
        envvar="CI_SYSTEM",
        help="CI system name (e.g., 'Jenkins').",
    ),
    pipeline_url: Optional[str] = typer.Option(  # noqa: UP007
        None,
        "--pipeline-url",
        envvar="BUILD_URL",
        help="URL to the CI/CD pipeline run.",
    ),
    triggered_by: Optional[str] = typer.Option(  # noqa: UP007
        None,
        "--triggered-by",
        help="User or trigger that initiated the build.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Construct payload but do not transmit. Prints JSON to stdout.",
    ),
) -> None:
    """Push build data to the URGP Event Gateway.

    Collects artifact metadata, computes SHA-256 checksums, constructs
    a Data Contract payload, and transmits it to the URGP API.

    Example:
        urgp-cli push \\\\
          --product S32_IDE \\\\
          --release 3.6.8-RFP \\\\
          --build-type nightly \\\\
          --build-id 260330 \\\\
          --adapter eclipse_p2 \\\\
          --artifact ./target/s32-ide.zip \\\\
          --commit-repo bitbucket.org/nxp/s32k3_dev \\\\
          --commit-hash abc123def456789012345678901234567890abcd \\\\
          --api-key $URGP_API_KEY
    """
    total_steps = 5 if not dry_run else 4

    # -- Step 1: Validate parameters ------------------------------------
    print_step(1, total_steps, "Validating parameters...")

    # Validate commit repo/hash pairing
    if len(commit_repo) != len(commit_hash):
        print_error(
            f"--commit-repo and --commit-hash must be specified the same number of times. "
            f"Got {len(commit_repo)} repos and {len(commit_hash)} hashes."
        )
        raise typer.Exit(code=2)

    # Validate artifact paths exist
    artifact_paths: list[Path] = []
    for art_path_str in artifact:
        art_path = Path(art_path_str)
        if not art_path.exists():
            print_error(f"Artifact file not found: {art_path}")
            raise typer.Exit(code=2)
        if not art_path.is_file():
            print_error(f"Artifact path is not a file: {art_path}")
            raise typer.Exit(code=2)
        artifact_paths.append(art_path)

    # Validate adapter type
    try:
        adapter_instance = get_adapter(adapter)
    except ValueError as exc:
        print_error(str(exc))
        raise typer.Exit(code=2) from exc

    invalid_artifacts = [art_path for art_path in artifact_paths if not adapter_instance.validate_artifact(art_path)]
    if invalid_artifacts:
        for invalid_artifact in invalid_artifacts:
            print_error(f"Artifact failed {adapter} adapter validation: {invalid_artifact}")
        raise typer.Exit(code=2)

    try:
        artifact_type = _resolve_artifact_type(adapter_instance.adapter_type)
    except ValueError as exc:
        print_error(str(exc))
        raise typer.Exit(code=2) from exc

    print_success(f"Parameters valid ({len(artifact_paths)} artifact(s), {len(commit_repo)} commit(s))")

    # -- Step 2: Extract metadata + compute checksums -------------------
    print_step(2, total_steps, "Processing artifacts...")

    artifact_payloads: list[ArtifactPayload] = []
    for art_path in artifact_paths:
        # Extract adapter metadata
        adapter_result = adapter_instance.extract_metadata(art_path)
        print_adapter_result(adapter, adapter_result)

        # Compute SHA-256 checksum
        if should_report_progress(art_path):
            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                task_id = progress.add_task(f"  SHA-256: {art_path.name}", total=art_path.stat().st_size)
                _tid = task_id  # bind for closure

                def _progress_cb(bytes_read: int, total: int, *, _t: object = _tid) -> None:
                    progress.update(_t, completed=bytes_read)  # type: ignore[arg-type]

                sha256 = compute_sha256(art_path, progress_callback=_progress_cb)
        else:
            sha256 = compute_sha256(art_path)

        # Build storage URI
        storage_uri = _build_storage_uri(art_path, storage_uri_prefix)

        # Construct artifact payload
        artifact_payload = ArtifactPayload(
            name=art_path.name,
            type=artifact_type,
            storage_uri=storage_uri,
            sha256=sha256,
            size_bytes=art_path.stat().st_size,
            metadata=adapter_result.metadata if adapter_result.metadata else None,
        )
        artifact_payloads.append(artifact_payload)

    print_artifact_summary(artifact_payloads)

    # -- Step 3: Construct commit hashes --------------------------------
    print_step(3, total_steps, "Building commit list...")

    commit_entries = [
        CommitHash(repository=repo, hash=hash_val, branch=commit_branch)
        for repo, hash_val in zip(commit_repo, commit_hash, strict=True)
    ]

    print_success(f"{len(commit_entries)} commit(s) across {len(set(commit_repo))} repo(s)")

    # -- Step 4: Construct full payload ---------------------------------
    print_step(4, total_steps, "Constructing Data Contract payload...")

    ci_metadata = None
    if ci_system or pipeline_url or triggered_by:
        ci_metadata = CIMetadata(
            ci_system=ci_system,
            pipeline_url=pipeline_url,
            triggered_by=triggered_by,
        )

    try:
        payload = BuildEventPayload(
            product_id=product,
            release=release,
            build_type=build_type,
            build_id=build_id,
            cli_version=__version__,
            commit_hashes=commit_entries,
            artifacts=artifact_payloads,
            timestamp=datetime.datetime.now(tz=datetime.UTC),
            ci_metadata=ci_metadata,
        )
    except Exception as exc:
        print_error(f"Failed to construct payload: {exc}")
        raise typer.Exit(code=2) from exc

    print_payload_summary(payload)

    # -- Dry run: print JSON and exit -----------------------------------
    if dry_run:
        import json

        print_info("Dry run -- payload not transmitted")
        console.print_json(json.dumps(payload.to_json_dict(), default=str))
        raise typer.Exit(code=0)

    # -- Step 5: Transmit to URGP API -----------------------------------
    print_step(5, total_steps, f"Transmitting to {api_url}...")

    client = URGPClient(api_url)
    result = client.push(payload, api_key)
    print_push_result(result)

    if not result.success:
        raise typer.Exit(code=1)

    print_success("Build data pushed successfully")
