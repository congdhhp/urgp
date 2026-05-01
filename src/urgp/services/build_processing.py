"""Build event processing and persistence for the control plane."""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from urgp.config import URGPSettings
from urgp.integrations.git import create_git_provider
from urgp.integrations.git.base import GitProvider
from urgp.integrations.issues import create_issue_tracker
from urgp.integrations.issues.base import IssueTracker
from urgp.models.enums import BuildStatus
from urgp.models.manifest import Artifact, BuildManifest
from urgp.models.product import Product, Release
from urgp.models.traceability import Commit, build_commits
from urgp.schemas.ingest import IngestPayload
from urgp.services.cache import CacheService
from urgp.services.lifecycle import BuildLifecycleService
from urgp.services.signature import ManifestSignatureService
from urgp.services.traceability import TraceabilityHydrator


@dataclass(frozen=True)
class PersistedBuildResult:
    """Outcome of persisting a build event into the control plane."""

    manifest_id: uuid.UUID
    product_id: uuid.UUID
    release_id: uuid.UUID
    signature: str
    created: bool
    traceability_incomplete: bool


class BuildPersistenceService:
    """Persist validated build payloads into the relational control plane."""

    def __init__(self, session: AsyncSession, signer: ManifestSignatureService) -> None:
        self._session = session
        self._signer = signer

    async def persist_payload(self, payload: IngestPayload) -> PersistedBuildResult:
        """Persist the build payload idempotently using database constraints."""
        product_id = await self._ensure_product(payload.product_id)
        release_id = await self._ensure_release(product_id, payload.release)

        manifest_insert = (
            insert(BuildManifest)
            .values(
                build_id=payload.build_id,
                product_id=product_id,
                release_id=release_id,
                build_type=payload.build_type,
                status=BuildStatus.INGESTING,
                traceability_incomplete=True,
                cli_version=payload.cli_version,
                ci_metadata=payload.ci_metadata.model_dump(mode="json") if payload.ci_metadata else None,
                signature=self._signer.sign_payload(payload),
            )
            .on_conflict_do_nothing(
                index_elements=["product_id", "build_id"],
            )
            .returning(
                BuildManifest.id,
                BuildManifest.signature,
                BuildManifest.traceability_incomplete,
            )
        )

        created_manifest = (await self._session.execute(manifest_insert)).one_or_none()
        if created_manifest is None:
            existing_manifest = (
                await self._session.execute(
                    select(
                        BuildManifest.id,
                        BuildManifest.release_id,
                        BuildManifest.signature,
                        BuildManifest.traceability_incomplete,
                    ).where(
                        BuildManifest.product_id == product_id,
                        BuildManifest.build_id == payload.build_id,
                    )
                )
            ).one()

            return PersistedBuildResult(
                manifest_id=existing_manifest.id,
                product_id=product_id,
                release_id=existing_manifest.release_id,
                signature=existing_manifest.signature or self._signer.sign_payload(payload),
                created=False,
                traceability_incomplete=existing_manifest.traceability_incomplete,
            )

        manifest_id = created_manifest.id
        await self._persist_commits(manifest_id, payload)
        await self._persist_artifacts(manifest_id, payload)

        return PersistedBuildResult(
            manifest_id=manifest_id,
            product_id=product_id,
            release_id=release_id,
            signature=created_manifest.signature,
            created=True,
            traceability_incomplete=created_manifest.traceability_incomplete,
        )

    async def get_manifest_for_processing(self, manifest_id: uuid.UUID) -> BuildManifest:
        manifest = await self._session.scalar(
            select(BuildManifest)
            .options(
                selectinload(BuildManifest.product),
                selectinload(BuildManifest.release),
                selectinload(BuildManifest.commits).selectinload(Commit.pull_requests),
                selectinload(BuildManifest.commits).selectinload(Commit.issues),
                selectinload(BuildManifest.artifacts),
                selectinload(BuildManifest.notifications),
            )
            .where(BuildManifest.id == manifest_id)
        )
        if manifest is None:
            msg = f"Manifest '{manifest_id}' could not be loaded for processing."
            raise RuntimeError(msg)
        return manifest

    async def _ensure_product(self, product_external_id: str) -> uuid.UUID:
        statement = (
            insert(Product)
            .values(
                external_id=product_external_id,
                name=_build_default_product_name(product_external_id),
            )
            .on_conflict_do_nothing(index_elements=["external_id"])
            .returning(Product.id)
        )
        created_id = (await self._session.execute(statement)).scalar_one_or_none()
        if created_id is not None:
            return created_id

        existing_id = await self._session.scalar(select(Product.id).where(Product.external_id == product_external_id))
        if existing_id is None:
            msg = f"Product '{product_external_id}' could not be resolved."
            raise RuntimeError(msg)
        return existing_id

    async def _ensure_release(self, product_id: uuid.UUID, version: str) -> uuid.UUID:
        statement = (
            insert(Release)
            .values(
                product_id=product_id,
                version=version,
                release_type=_infer_release_type(version),
                status="active",
            )
            .on_conflict_do_nothing(index_elements=["product_id", "version"])
            .returning(Release.id)
        )
        created_id = (await self._session.execute(statement)).scalar_one_or_none()
        if created_id is not None:
            return created_id

        existing_id = await self._session.scalar(
            select(Release.id).where(
                Release.product_id == product_id,
                Release.version == version,
            )
        )
        if existing_id is None:
            msg = f"Release '{version}' for product '{product_id}' could not be resolved."
            raise RuntimeError(msg)
        return existing_id

    async def _persist_commits(self, manifest_id: uuid.UUID, payload: IngestPayload) -> None:
        seen: set[tuple[str, str]] = set()
        for commit in payload.commit_hashes:
            identity = (commit.repository, commit.hash)
            if identity in seen:
                continue
            seen.add(identity)

            commit_id = await self._ensure_commit(
                repository=commit.repository,
                commit_hash=commit.hash,
                branch=commit.branch,
            )
            await self._session.execute(
                insert(build_commits)
                .values(
                    build_id=manifest_id,
                    commit_id=commit_id,
                )
                .on_conflict_do_nothing()
            )

    async def _ensure_commit(
        self,
        *,
        repository: str,
        commit_hash: str,
        branch: str | None,
    ) -> uuid.UUID:
        statement = (
            insert(Commit)
            .values(
                repository=repository,
                hash=commit_hash,
                branch=branch,
            )
            .on_conflict_do_nothing(index_elements=["repository", "hash"])
            .returning(Commit.id)
        )
        commit_id = (await self._session.execute(statement)).scalar_one_or_none()
        if commit_id is not None:
            return commit_id

        existing_commit_id = await self._session.scalar(
            select(Commit.id).where(
                Commit.repository == repository,
                Commit.hash == commit_hash,
            )
        )
        if existing_commit_id is None:
            msg = f"Commit '{repository}@{commit_hash}' could not be resolved."
            raise RuntimeError(msg)
        return existing_commit_id

    async def _persist_artifacts(self, manifest_id: uuid.UUID, payload: IngestPayload) -> None:
        artifact_rows = [
            {
                "manifest_id": manifest_id,
                "name": artifact.name,
                "type": artifact.type,
                "storage_uri": artifact.storage_uri,
                "sha256_checksum": artifact.sha256,
                "size_bytes": artifact.size_bytes,
                "metadata_": artifact.metadata,
            }
            for artifact in payload.artifacts
        ]
        if artifact_rows:
            await self._session.execute(insert(Artifact).values(artifact_rows))


class BuildEventProcessor:
    """Application service that owns transaction boundaries for build processing."""

    def __init__(
        self,
        session_factory_provider: Callable[[], async_sessionmaker[AsyncSession]],
        signer: ManifestSignatureService,
        settings: URGPSettings,
        *,
        cache: CacheService | None = None,
        git_provider: GitProvider | None = None,
        issue_tracker: IssueTracker | None = None,
    ) -> None:
        self._session_factory_provider = session_factory_provider
        self._signer = signer
        self._settings = settings
        self._cache = cache
        self._default_git_provider = git_provider
        self._default_issue_tracker = issue_tracker

    async def process(self, payload: IngestPayload) -> PersistedBuildResult:
        """Persist one build payload in a single transaction."""
        session_factory = self._session_factory_provider()
        async with session_factory() as session:
            async with session.begin():
                service = BuildPersistenceService(session, self._signer)
                result = await service.persist_payload(payload)
                if result.created:
                    manifest = await service.get_manifest_for_processing(result.manifest_id)
                    lifecycle = BuildLifecycleService()
                    lifecycle.transition(manifest, BuildStatus.HYDRATING, allow_noop=False)
                    git_provider = self._resolve_git_provider(manifest.product.git_config)
                    issue_tracker = self._resolve_issue_tracker(manifest.product.issue_config)
                    hydrator = TraceabilityHydrator(
                        session,
                        self._settings,
                        git_provider=git_provider,
                        issue_tracker=issue_tracker,
                    )
                    hydration = await hydrator.hydrate(manifest, payload)
                    manifest.traceability_incomplete = hydration.traceability_incomplete
                    lifecycle.transition(manifest, BuildStatus.COMPLETED, allow_noop=False)
                    result = PersistedBuildResult(
                        manifest_id=result.manifest_id,
                        product_id=result.product_id,
                        release_id=result.release_id,
                        signature=result.signature,
                        created=result.created,
                        traceability_incomplete=manifest.traceability_incomplete,
                    )
            return result

    def _resolve_git_provider(self, git_config: dict[str, Any] | None) -> GitProvider | None:
        return (
            create_git_provider(
                git_config,
                cache=self._cache,
                default_provider=self._settings.default_git_provider,
            )
            or self._default_git_provider
        )

    def _resolve_issue_tracker(self, issue_config: dict[str, Any] | None) -> IssueTracker | None:
        return (
            create_issue_tracker(
                issue_config,
                cache=self._cache,
                default_tracker=self._settings.default_issue_tracker,
            )
            or self._default_issue_tracker
        )


def _build_default_product_name(product_external_id: str) -> str:
    normalized = re.sub(r"[-_]+", " ", product_external_id.strip())
    tokens = normalized.split()
    if not tokens:
        return product_external_id

    def _normalize_token(token: str) -> str:
        if token.isupper() or any(char.isdigit() for char in token):
            return token.upper()
        return token.capitalize()

    return " ".join(_normalize_token(token) for token in tokens)


def _infer_release_type(version: str) -> str | None:
    match = re.search(r"[-_]?([A-Za-z]{2,10})$", version.strip())
    if match is None:
        return None
    return match.group(1).upper()
