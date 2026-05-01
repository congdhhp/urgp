"""Platform query and administration services."""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.base import ExecutableOption

from urgp.models.enums import BuildStatus
from urgp.models.manifest import Artifact, BuildManifest
from urgp.models.product import Product, Release
from urgp.models.traceability import Commit, Issue, PullRequest
from urgp.schemas.platform import (
    ActivityResponse,
    ActivityTotalsResponse,
    ArtifactResponse,
    BuildArtifactsResponse,
    BuildComparisonResponse,
    BuildDetailResponse,
    BuildListResponse,
    BuildSearchResponse,
    BuildStatusTransitionRequest,
    BuildSummaryResponse,
    BuildTraceabilityResponse,
    BuildVerificationArtifactResponse,
    BuildVerificationResponse,
    CommitTraceabilityResponse,
    IssueResponse,
    ProductCreateRequest,
    ProductListResponse,
    ProductSummaryResponse,
    PullRequestResponse,
    ReleaseCreateRequest,
    ReleaseListResponse,
    ReleaseSummaryResponse,
    TraceabilityRepositoryResponse,
)
from urgp.services.lifecycle import BuildLifecycleService


class BuildNotFoundError(LookupError):
    """Raised when a build reference cannot be resolved."""


class AmbiguousBuildReferenceError(LookupError):
    """Raised when a build_id matches more than one product-scoped manifest."""


class ProductNotFoundError(LookupError):
    """Raised when a product cannot be resolved."""


@dataclass(frozen=True)
class BuildStatusTransitionResult:
    """Lifecycle transition response plus notification context."""

    build: BuildDetailResponse
    manifest_id: uuid.UUID
    product_id: str
    status: BuildStatus


def _manifest_load_options() -> tuple[ExecutableOption, ...]:
    return cast(
        "tuple[ExecutableOption, ...]",
        (
            selectinload(BuildManifest.product),
            selectinload(BuildManifest.release),
            selectinload(BuildManifest.artifacts),
            selectinload(BuildManifest.notifications),
            selectinload(BuildManifest.commits).selectinload(Commit.pull_requests),
            selectinload(BuildManifest.commits).selectinload(Commit.issues),
        ),
    )


def _artifact_to_response(artifact: Artifact) -> ArtifactResponse:
    return ArtifactResponse.model_validate(
        {
            "id": artifact.id,
            "name": artifact.name,
            "type": artifact.type,
            "storage_uri": artifact.storage_uri,
            "sha256_checksum": artifact.sha256_checksum,
            "size_bytes": artifact.size_bytes,
            "metadata_": artifact.metadata_,
        }
    )


def _pull_request_to_response(pull_request: PullRequest) -> PullRequestResponse:
    return PullRequestResponse(
        external_id=pull_request.external_id,
        title=pull_request.title,
        author=pull_request.author,
        source_branch=pull_request.source_branch,
        target_branch=pull_request.target_branch,
        merge_timestamp=pull_request.merge_timestamp,
        url=pull_request.url,
    )


def _issue_to_response(issue: Issue) -> IssueResponse:
    return IssueResponse(
        external_id=issue.external_id,
        tracker_type=issue.tracker_type,
        title=issue.title,
        status=issue.status,
        priority=issue.priority,
        assignee=issue.assignee,
        labels=issue.labels,
        url=issue.url,
    )


def _build_summary(manifest: BuildManifest) -> BuildSummaryResponse:
    product = manifest.product
    release = manifest.release
    pull_request_count = len({pull_request.id for commit in manifest.commits for pull_request in commit.pull_requests})
    issue_count = len({issue.id for commit in manifest.commits for issue in commit.issues})

    return BuildSummaryResponse(
        id=manifest.id,
        build_id=manifest.build_id,
        product_id=product.external_id,
        product_name=product.name,
        release=release.version if release is not None else None,
        build_type=manifest.build_type,
        status=manifest.status,
        traceability_incomplete=manifest.traceability_incomplete,
        created_at=manifest.created_at,
        updated_at=manifest.updated_at,
        released_at=manifest.released_at,
        cli_version=manifest.cli_version,
        signature=manifest.signature,
        artifact_count=len(manifest.artifacts),
        commit_count=len(manifest.commits),
        pull_request_count=pull_request_count,
        issue_count=issue_count,
        notification_count=len(manifest.notifications),
    )


class PlatformQueryService:
    """Owns read models and platform management operations."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._lifecycle = BuildLifecycleService()

    async def list_products(self) -> ProductListResponse:
        async with self._session_factory() as session:
            result = await session.scalars(
                select(Product)
                .options(
                    selectinload(Product.releases),
                    selectinload(Product.manifests),
                )
                .order_by(Product.name.asc())
            )
            products = list(result.all())

        items: list[ProductSummaryResponse] = []
        for product in products:
            last_manifest = max(product.manifests, key=lambda item: item.created_at, default=None)
            items.append(
                ProductSummaryResponse(
                    external_id=product.external_id,
                    name=product.name,
                    description=product.description,
                    release_count=len(product.releases),
                    build_count=len(product.manifests),
                    last_build_id=last_manifest.build_id if last_manifest is not None else None,
                    last_build_status=last_manifest.status if last_manifest is not None else None,
                    last_build_at=last_manifest.created_at if last_manifest is not None else None,
                )
            )

        return ProductListResponse(items=items, total=len(items))

    async def create_product(self, payload: ProductCreateRequest) -> ProductSummaryResponse:
        async with self._session_factory() as session:
            existing = await session.scalar(
                select(Product).where(or_(Product.external_id == payload.external_id, Product.name == payload.name))
            )
            if existing is None:
                product = Product(
                    external_id=payload.external_id,
                    name=payload.name,
                    description=payload.description,
                    git_config=payload.git_config,
                    issue_config=payload.issue_config,
                )
                session.add(product)
                await session.commit()
                await session.refresh(product)
            else:
                product = existing

        return ProductSummaryResponse(
            external_id=product.external_id,
            name=product.name,
            description=product.description,
            release_count=0,
            build_count=0,
        )

    async def list_releases(self, product_external_id: str) -> ReleaseListResponse:
        async with self._session_factory() as session:
            product = await session.scalar(
                select(Product)
                .options(selectinload(Product.releases).selectinload(Release.manifests))
                .where(Product.external_id == product_external_id)
            )
            if product is None:
                msg = f"Product '{product_external_id}' was not found."
                raise ProductNotFoundError(msg)

        items: list[ReleaseSummaryResponse] = []
        for release in sorted(product.releases, key=lambda item: item.version, reverse=True):
            last_manifest = max(release.manifests, key=lambda item: item.created_at, default=None)
            items.append(
                ReleaseSummaryResponse(
                    version=release.version,
                    release_type=release.release_type,
                    status=release.status,
                    build_count=len(release.manifests),
                    last_build_id=last_manifest.build_id if last_manifest is not None else None,
                    last_build_status=last_manifest.status if last_manifest is not None else None,
                    last_build_at=last_manifest.created_at if last_manifest is not None else None,
                )
            )

        return ReleaseListResponse(
            product_id=product.external_id,
            product_name=product.name,
            items=items,
            total=len(items),
        )

    async def create_release(self, product_external_id: str, payload: ReleaseCreateRequest) -> ReleaseSummaryResponse:
        async with self._session_factory() as session:
            product = await session.scalar(select(Product).where(Product.external_id == product_external_id))
            if product is None:
                msg = f"Product '{product_external_id}' was not found."
                raise ProductNotFoundError(msg)

            existing = await session.scalar(
                select(Release).where(Release.product_id == product.id, Release.version == payload.version)
            )
            if existing is None:
                release = Release(
                    product_id=product.id,
                    version=payload.version,
                    release_type=payload.release_type,
                    status=payload.status,
                )
                session.add(release)
                await session.commit()
                await session.refresh(release)
            else:
                release = existing

        return ReleaseSummaryResponse(
            version=release.version,
            release_type=release.release_type,
            status=release.status,
            build_count=0,
        )

    async def get_activity(self, *, recent_limit: int = 8) -> ActivityResponse:
        products = await self.list_products()
        builds = await self.list_builds(limit=recent_limit)

        async with self._session_factory() as session:
            totals = ActivityTotalsResponse(
                products=cast("int", await session.scalar(select(func.count(Product.id))) or 0),
                releases=cast("int", await session.scalar(select(func.count(Release.id))) or 0),
                builds=cast("int", await session.scalar(select(func.count(BuildManifest.id))) or 0),
                released_builds=cast(
                    "int",
                    await session.scalar(
                        select(func.count(BuildManifest.id)).where(BuildManifest.status == BuildStatus.RELEASED)
                    )
                    or 0,
                ),
                incomplete_builds=cast(
                    "int",
                    await session.scalar(
                        select(func.count(BuildManifest.id)).where(BuildManifest.traceability_incomplete.is_(True))
                    )
                    or 0,
                ),
            )

        return ActivityResponse(
            generated_at=datetime.now(tz=UTC),
            totals=totals,
            recent_builds=builds.items,
            products=products.items,
        )

    async def list_builds(
        self,
        *,
        product_id: str | None = None,
        release: str | None = None,
        status: BuildStatus | None = None,
        traceability_incomplete: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> BuildListResponse:
        async with self._session_factory() as session:
            base_stmt = self._build_list_statement(
                product_id=product_id,
                release=release,
                status=status,
                traceability_incomplete=traceability_incomplete,
            )
            total = cast(
                "int",
                await session.scalar(select(func.count()).select_from(base_stmt.order_by(None).subquery())) or 0,
            )
            result = await session.scalars(base_stmt.options(*_manifest_load_options()).offset(offset).limit(limit))
            manifests = list(result.all())

        return BuildListResponse(
            items=[_build_summary(manifest) for manifest in manifests],
            total=total,
        )

    async def get_build(self, build_ref: str, *, product_id: str | None = None) -> BuildDetailResponse:
        async with self._session_factory() as session:
            manifest = await self._resolve_manifest(session, build_ref, product_id=product_id)
        summary = _build_summary(manifest)
        return BuildDetailResponse(**summary.model_dump(), ci_metadata=manifest.ci_metadata)

    async def get_artifacts(self, build_ref: str, *, product_id: str | None = None) -> BuildArtifactsResponse:
        async with self._session_factory() as session:
            manifest = await self._resolve_manifest(session, build_ref, product_id=product_id)
        return BuildArtifactsResponse(
            build_id=manifest.build_id,
            product_id=manifest.product.external_id,
            artifacts=[_artifact_to_response(artifact) for artifact in manifest.artifacts],
        )

    async def get_traceability(self, build_ref: str, *, product_id: str | None = None) -> BuildTraceabilityResponse:
        async with self._session_factory() as session:
            manifest = await self._resolve_manifest(session, build_ref, product_id=product_id)

        repositories: dict[str, list[Commit]] = defaultdict(list)
        for commit in sorted(manifest.commits, key=lambda item: (item.repository, item.hash)):
            repositories[commit.repository].append(commit)

        repository_items: list[TraceabilityRepositoryResponse] = []
        total_pull_requests = 0
        total_issues = 0
        for repository, commits in repositories.items():
            commit_items = [
                CommitTraceabilityResponse(
                    repository=commit.repository,
                    hash=commit.hash,
                    branch=commit.branch,
                    author=commit.author,
                    message=commit.message,
                    committed_at=commit.committed_at,
                    pull_requests=[_pull_request_to_response(item) for item in commit.pull_requests],
                    issues=[_issue_to_response(item) for item in commit.issues],
                )
                for commit in commits
            ]
            repository_pull_requests = len(
                {pull_request.id for commit in commits for pull_request in commit.pull_requests}
            )
            repository_issues = len({issue.id for commit in commits for issue in commit.issues})
            total_pull_requests += repository_pull_requests
            total_issues += repository_issues
            repository_items.append(
                TraceabilityRepositoryResponse(
                    repository=repository,
                    commit_count=len(commits),
                    pull_request_count=repository_pull_requests,
                    issue_count=repository_issues,
                    commits=commit_items,
                )
            )

        return BuildTraceabilityResponse(
            build_id=manifest.build_id,
            product_id=manifest.product.external_id,
            status=manifest.status,
            traceability_incomplete=manifest.traceability_incomplete,
            commit_count=len(manifest.commits),
            pull_request_count=total_pull_requests,
            issue_count=total_issues,
            repositories=repository_items,
        )

    async def compare_builds(
        self,
        start_ref: str,
        end_ref: str,
        *,
        product_id: str | None = None,
    ) -> BuildComparisonResponse:
        async with self._session_factory() as session:
            start_manifest = await self._resolve_manifest(session, start_ref, product_id=product_id)
            end_manifest = await self._resolve_manifest(session, end_ref, product_id=product_id)

        start_commit_hashes = {commit.hash for commit in start_manifest.commits}
        unique_commits = sorted(
            commit.hash for commit in end_manifest.commits if commit.hash not in start_commit_hashes
        )

        start_pull_request_keys = {
            (pull_request.repository, pull_request.external_id)
            for commit in start_manifest.commits
            for pull_request in commit.pull_requests
        }
        unique_pull_requests = [
            _pull_request_to_response(pull_request)
            for pull_request in {
                pull_request
                for commit in end_manifest.commits
                for pull_request in commit.pull_requests
                if (pull_request.repository, pull_request.external_id) not in start_pull_request_keys
            }
        ]
        unique_pull_requests.sort(key=lambda item: item.external_id)

        start_issue_keys = {
            (issue.tracker_type, issue.external_id) for commit in start_manifest.commits for issue in commit.issues
        }
        unique_issues = [
            _issue_to_response(issue)
            for issue in {
                issue
                for commit in end_manifest.commits
                for issue in commit.issues
                if (issue.tracker_type, issue.external_id) not in start_issue_keys
            }
        ]
        unique_issues.sort(key=lambda item: item.external_id)

        return BuildComparisonResponse(
            start_build_id=start_manifest.build_id,
            end_build_id=end_manifest.build_id,
            unique_commits=unique_commits,
            unique_pull_requests=unique_pull_requests,
            unique_issues=unique_issues,
        )

    async def find_builds_by_commit(self, commit_hash: str) -> BuildSearchResponse:
        async with self._session_factory() as session:
            result = await session.scalars(
                select(BuildManifest)
                .join(BuildManifest.commits)
                .where(Commit.hash == commit_hash)
                .options(*_manifest_load_options())
                .order_by(BuildManifest.created_at.desc())
            )
            manifests = list(result.unique().all())

        return BuildSearchResponse(
            query=commit_hash,
            items=[_build_summary(manifest) for manifest in manifests],
            total=len(manifests),
        )

    async def find_builds_by_issue(self, issue_id: str) -> BuildSearchResponse:
        async with self._session_factory() as session:
            result = await session.scalars(
                select(BuildManifest)
                .join(BuildManifest.commits)
                .join(Commit.issues)
                .where(Issue.external_id == issue_id)
                .options(*_manifest_load_options())
                .order_by(BuildManifest.created_at.desc())
            )
            manifests = list(result.unique().all())

        return BuildSearchResponse(
            query=issue_id,
            items=[_build_summary(manifest) for manifest in manifests],
            total=len(manifests),
        )

    async def transition_build_status(
        self,
        build_ref: str,
        payload: BuildStatusTransitionRequest,
        *,
        product_id: str | None = None,
    ) -> BuildStatusTransitionResult:
        async with self._session_factory() as session:
            manifest = await self._resolve_manifest(session, build_ref, product_id=product_id)
            self._lifecycle.transition(manifest, payload.status, allow_noop=False)
            await session.commit()
            await session.refresh(manifest)

        summary = _build_summary(manifest)
        return BuildStatusTransitionResult(
            build=BuildDetailResponse(**summary.model_dump(), ci_metadata=manifest.ci_metadata),
            manifest_id=manifest.id,
            product_id=manifest.product.external_id,
            status=manifest.status,
        )

    async def verify_build_integrity(
        self,
        build_ref: str,
        *,
        product_id: str | None = None,
    ) -> BuildVerificationResponse:
        async with self._session_factory() as session:
            manifest = await self._resolve_manifest(session, build_ref, product_id=product_id)

        seen_checksums: set[str] = set()
        artifact_items: list[BuildVerificationArtifactResponse] = []
        overall_valid = manifest.signature is not None and manifest.status not in {
            BuildStatus.INGESTING,
            BuildStatus.HYDRATING,
        }

        for artifact in manifest.artifacts:
            detail = "Artifact metadata is internally consistent."
            integrity_status = "valid"
            if len(artifact.sha256_checksum) != 64:
                integrity_status = "invalid"
                detail = "Stored checksum is malformed."
                overall_valid = False
            elif artifact.sha256_checksum in seen_checksums:
                integrity_status = "invalid"
                detail = "Duplicate checksum detected within the manifest."
                overall_valid = False

            seen_checksums.add(artifact.sha256_checksum)
            artifact_items.append(
                BuildVerificationArtifactResponse(
                    name=artifact.name,
                    type=artifact.type,
                    sha256=artifact.sha256_checksum,
                    integrity_status=integrity_status,
                    detail=detail,
                )
            )

        return BuildVerificationResponse(
            build_id=manifest.build_id,
            product_id=manifest.product.external_id,
            integrity_status="valid" if overall_valid else "invalid",
            traceability_incomplete=manifest.traceability_incomplete,
            artifacts=artifact_items,
            verification_timestamp=datetime.now(tz=UTC),
        )

    def _build_list_statement(
        self,
        *,
        product_id: str | None,
        release: str | None,
        status: BuildStatus | None,
        traceability_incomplete: bool | None,
    ) -> Select[tuple[BuildManifest]]:
        stmt = select(BuildManifest).join(BuildManifest.product).outerjoin(BuildManifest.release)
        if product_id:
            stmt = stmt.where(Product.external_id == product_id)
        if release:
            stmt = stmt.where(Release.version == release)
        if status is not None:
            stmt = stmt.where(BuildManifest.status == status)
        if traceability_incomplete is not None:
            stmt = stmt.where(BuildManifest.traceability_incomplete.is_(traceability_incomplete))
        return stmt.order_by(BuildManifest.created_at.desc())

    async def _resolve_manifest(
        self,
        session: AsyncSession,
        build_ref: str,
        *,
        product_id: str | None,
    ) -> BuildManifest:
        manifest_uuid = _try_parse_uuid(build_ref)
        if manifest_uuid is not None:
            manifest = await session.scalar(
                select(BuildManifest).where(BuildManifest.id == manifest_uuid).options(*_manifest_load_options())
            )
            if manifest is None:
                msg = f"Build '{build_ref}' was not found."
                raise BuildNotFoundError(msg)
            return manifest

        stmt = (
            select(BuildManifest)
            .join(BuildManifest.product)
            .where(BuildManifest.build_id == build_ref)
            .options(*_manifest_load_options())
            .order_by(BuildManifest.created_at.desc())
        )
        if product_id:
            stmt = stmt.where(Product.external_id == product_id)

        result = await session.scalars(stmt)
        manifests = list(result.all())
        if not manifests:
            msg = f"Build '{build_ref}' was not found."
            raise BuildNotFoundError(msg)
        if len(manifests) > 1:
            msg = f"Build reference '{build_ref}' matches multiple products. Provide product_id to disambiguate."
            raise AmbiguousBuildReferenceError(msg)
        return manifests[0]


def _try_parse_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


__all__ = [
    "AmbiguousBuildReferenceError",
    "BuildNotFoundError",
    "BuildStatusTransitionResult",
    "PlatformQueryService",
    "ProductNotFoundError",
]
