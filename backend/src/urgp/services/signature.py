"""Deterministic manifest signature generation for immutable build records."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC
from typing import Any

from urgp.schemas.ingest import IngestPayload


class ManifestSignatureService:
    """Generate and verify HMAC-SHA256 signatures for build payloads."""

    def __init__(self, signing_key: str) -> None:
        self._signing_key = signing_key.encode("utf-8")

    def sign_payload(self, payload: IngestPayload) -> str:
        """Create a deterministic signature from the semantic payload content."""
        canonical_payload = self._canonicalize_payload(payload)
        encoded = json.dumps(
            canonical_payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hmac.new(self._signing_key, encoded, hashlib.sha256).hexdigest()

    def verify_payload(self, payload: IngestPayload, signature: str) -> bool:
        """Verify a payload against a previously generated signature."""
        expected = self.sign_payload(payload)
        return hmac.compare_digest(expected, signature)

    def _canonicalize_payload(self, payload: IngestPayload) -> dict[str, Any]:
        ci_metadata = payload.ci_metadata.model_dump(mode="json") if payload.ci_metadata else None

        artifacts = sorted(
            (
                {
                    "name": artifact.name,
                    "type": artifact.type.value,
                    "storage_uri": artifact.storage_uri,
                    "sha256": artifact.sha256,
                    "size_bytes": artifact.size_bytes,
                    "metadata": artifact.metadata,
                }
                for artifact in payload.artifacts
            ),
            key=lambda item: (
                str(item["type"]),
                str(item["name"]),
                str(item["sha256"]),
                str(item["storage_uri"]),
            ),
        )

        commits = sorted(
            (
                {
                    "repository": commit.repository,
                    "hash": commit.hash,
                    "branch": commit.branch,
                }
                for commit in payload.commit_hashes
            ),
            key=lambda item: (
                str(item["repository"]),
                str(item["hash"]),
                str(item["branch"]),
            ),
        )

        return {
            "product_id": payload.product_id,
            "release": payload.release,
            "build_type": payload.build_type.value,
            "build_id": payload.build_id,
            "cli_version": payload.cli_version,
            "timestamp": payload.timestamp.astimezone(UTC).isoformat(),
            "commit_hashes": commits,
            "artifacts": artifacts,
            "ci_metadata": ci_metadata,
        }
