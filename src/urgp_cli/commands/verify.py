"""Verify command - request server-side artifact integrity verification.

Uses the verification API for a build and renders the returned integrity
status without inventing success states client-side.

Reference:
    - docs/05-technical-design.md Section Layer 1: Execution Edge
    - docs/07-implementation-plan.md Section P2-2.2
"""

from __future__ import annotations

from typing import Any, Optional

import httpx
import typer

from urgp_cli.output import console, print_error, print_info, print_success

# Default API URL
_DEFAULT_API_URL = "http://localhost:8000"

_VALID_STATES = {"valid", "verified", "ok", "pass", "passed", "success"}
_INVALID_STATES = {"invalid", "failed", "mismatch", "corrupt", "error"}


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
        help="Optional product identifier to scope verification requests.",
    ),
) -> None:
    """Verify artifact integrity for a build via the URGP API."""
    print_info(f"Requesting artifact integrity verification for build: {build_id}")

    url = f"{api_url.rstrip('/')}/api/v1/builds/{build_id}/verify"

    request_kwargs: dict[str, Any] = {
        "headers": {
            "X-API-Key": api_key,
            "Accept": "application/json",
        },
    }
    if product is not None:
        request_kwargs["json"] = {"product_id": product}

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, **request_kwargs)

        if response.status_code == 200:
            data = _parse_json_object(response, context="verification response")
            is_verified = _display_verification_result(data, build_id)
            if not is_verified:
                raise typer.Exit(code=1)
            return

        detail = _extract_error_detail(response)

        if response.status_code == 401:
            print_error("Authentication failed - check your API key")
            raise typer.Exit(code=1)

        if response.status_code == 404:
            if detail.strip().lower() == "not found":
                print_error("Integrity verification endpoint is not available on this server")
            else:
                print_error(f"Build '{build_id}' was not found: {detail}")
            raise typer.Exit(code=1)

        if response.status_code in {405, 501}:
            print_error("Integrity verification endpoint is not available on this server")
            raise typer.Exit(code=1)

        if response.status_code == 422:
            print_error(f"Verification request was rejected: {detail}")
            raise typer.Exit(code=1)

        print_error(f"Unexpected response from verification API: HTTP {response.status_code} - {detail}")
        raise typer.Exit(code=1)

    except httpx.ConnectError:
        print_error(f"Could not connect to URGP API at {api_url}")
        raise typer.Exit(code=1) from None
    except httpx.TimeoutException:
        print_error("Verification request timed out")
        raise typer.Exit(code=1) from None
    except ValueError as exc:
        print_error(str(exc))
        raise typer.Exit(code=1) from exc


def _parse_json_object(response: httpx.Response, *, context: str) -> dict[str, Any]:
    """Parse a JSON object response or raise a clear validation error."""
    try:
        payload = response.json()
    except ValueError as exc:
        msg = f"{context} was not valid JSON"
        raise ValueError(msg) from exc

    if not isinstance(payload, dict):
        msg = f"{context} must be a JSON object"
        raise ValueError(msg)

    return payload


def _extract_error_detail(response: httpx.Response) -> str:
    """Extract a human-readable error detail from an HTTP response."""
    try:
        payload = response.json()
    except ValueError:
        text = response.text.strip()
        return text or "No error details returned"

    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail.strip()

    text = response.text.strip()
    return text or "No error details returned"


def _display_verification_result(data: dict[str, Any], build_id: str) -> bool:
    """Display verification results and return whether integrity passed."""
    from rich.table import Table

    overall_state = _extract_integrity_state(data)
    is_verified = overall_state in _VALID_STATES
    artifact_count = _extract_artifact_count(data.get("artifacts"))
    traceability_incomplete = bool(data.get("traceability_incomplete", False))

    if is_verified:
        print_success(f"Integrity verification passed for build '{build_id}'")
    elif overall_state in _INVALID_STATES:
        print_error(f"Integrity verification failed for build '{build_id}'")
    else:
        print_error(f"Integrity verification returned an inconclusive result for build '{build_id}'")

    console.print(f"  [bold]Integrity:[/bold]       {overall_state}")
    console.print(f"  [bold]Artifacts:[/bold]       {artifact_count}")
    console.print(f"  [bold]Traceability:[/bold]    {'⚠ incomplete' if traceability_incomplete else '✓ complete'}")

    artifacts = data.get("artifacts")
    if isinstance(artifacts, list) and artifacts:
        table = Table(title="Artifacts", show_lines=False)
        table.add_column("Name", style="white")
        table.add_column("Type", style="cyan")
        table.add_column("SHA-256", style="dim", max_width=16)
        table.add_column("Integrity", style="green")
        table.add_column("Details", style="yellow")

        for artifact in artifacts:
            if not isinstance(artifact, dict):
                continue

            artifact_state = _extract_integrity_state(artifact)
            sha_value = _extract_sha_value(artifact)
            details = _extract_artifact_details(artifact)

            table.add_row(
                str(artifact.get("name", "-")),
                str(artifact.get("type", "-")),
                f"{sha_value[:12]}..." if sha_value else "-",
                artifact_state,
                details,
            )

        console.print(table)

    return is_verified


def _extract_artifact_count(value: object) -> int:
    """Return the artifact count from an artifacts payload field."""
    if isinstance(value, list):
        return len(value)
    return 0


def _extract_integrity_state(data: dict[str, Any]) -> str:
    """Extract a normalized integrity state from a verification payload."""
    for key in ("integrity_status", "verification_status"):
        value = data.get(key)
        if isinstance(value, str):
            return _normalize_integrity_state(value)

    for key in ("verified", "valid", "integrity_valid"):
        value = data.get(key)
        if isinstance(value, bool):
            return "valid" if value else "invalid"

    status_value = data.get("status")
    if isinstance(status_value, str):
        normalized_status = _normalize_integrity_state(status_value)
        if normalized_status != "unknown":
            return normalized_status

    return "unknown"


def _normalize_integrity_state(value: str) -> str:
    """Normalize variant status strings into stable display values."""
    normalized = value.strip().lower()

    if normalized in _VALID_STATES:
        return "valid"
    if normalized in _INVALID_STATES:
        return "invalid"
    if normalized:
        return normalized
    return "unknown"


def _extract_sha_value(artifact: dict[str, Any]) -> str:
    """Extract the most useful SHA value from an artifact verification result."""
    for key in ("sha256", "expected_sha256", "actual_sha256"):
        value = artifact.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _extract_artifact_details(artifact: dict[str, Any]) -> str:
    """Extract a concise detail string for artifact verification results."""
    for key in ("detail", "message", "error"):
        value = artifact.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    expected_sha = artifact.get("expected_sha256")
    actual_sha = artifact.get("actual_sha256")
    if isinstance(expected_sha, str) and isinstance(actual_sha, str) and expected_sha and actual_sha:
        return "expected/actual checksum returned"

    return "-"
