"""Database seed script — rich sample data for local development.

Creates multiple products, releases, builds with artifacts, commits,
pull requests, and issues so developers can fully explore the portal.

Usage: python -m urgp.db.seed
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import logging
import random
from datetime import UTC, datetime, timedelta

logger = logging.getLogger(__name__)

# ── Deterministic random for reproducible seeds ───────────────
_rng = random.Random(42)


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


def _commit_hash(idx: int) -> str:
    return hashlib.sha1(f"commit-{idx}".encode()).hexdigest()


def _now_minus(days: int = 0, hours: int = 0) -> datetime:
    return datetime.now(UTC) - timedelta(days=days, hours=hours)


# ── Data definitions ──────────────────────────────────────────

PRODUCTS = [
    {
        "external_id": "s32-design-studio",
        "name": "S32 Design Studio",
        "description": "NXP S32 Design Studio IDE for automotive microcontrollers",
        "git_config": {
            "provider": "bitbucket",
            "repositories": ["bitbucket.org/nxp/s32k3_dev", "bitbucket.org/nxp/s32k3_drivers"],
        },
        "issue_config": {
            "tracker": "jira",
            "base_url": "https://jira.nxp.com",
            "project_key": "S32",
            "issue_regex": r"S32-\d+",
        },
    },
    {
        "external_id": "autosar-mcal",
        "name": "AUTOSAR MCAL Package",
        "description": "Microcontroller Abstraction Layer drivers for S32K3 family",
        "git_config": {
            "provider": "bitbucket",
            "repositories": ["bitbucket.org/nxp/mcal_s32k3"],
        },
        "issue_config": {
            "tracker": "jira",
            "base_url": "https://jira.nxp.com",
            "project_key": "MCAL",
            "issue_regex": r"MCAL-\d+",
        },
    },
    {
        "external_id": "vehicle-network-toolbox",
        "name": "Vehicle Network Toolbox",
        "description": "CAN/LIN/FlexRay analysis and simulation tools",
        "git_config": {
            "provider": "github",
            "repositories": ["github.com/nxp/vnt-core", "github.com/nxp/vnt-plugins"],
        },
        "issue_config": {
            "tracker": "jira",
            "base_url": "https://jira.nxp.com",
            "project_key": "VNT",
            "issue_regex": r"VNT-\d+",
        },
    },
]

RELEASES_MAP = {
    "s32-design-studio": [
        {"version": "3.6.8 RFP", "release_type": "RFP", "status": "active"},
        {"version": "3.6.7 GA", "release_type": "GA", "status": "maintenance"},
        {"version": "3.5.0 GA", "release_type": "GA", "status": "eol"},
    ],
    "autosar-mcal": [
        {"version": "4.4.0 RC1", "release_type": "RC", "status": "active"},
        {"version": "4.3.2 GA", "release_type": "GA", "status": "active"},
    ],
    "vehicle-network-toolbox": [
        {"version": "2.1.0 RFP", "release_type": "RFP", "status": "active"},
        {"version": "2.0.0 GA", "release_type": "GA", "status": "maintenance"},
    ],
}

COMMIT_AUTHORS = [
    "alice.chen",
    "bob.mueller",
    "carlos.garcia",
    "diana.novak",
    "erik.johansson",
    "fatima.ali",
    "george.kim",
    "hannah.schmidt",
]

COMMIT_MESSAGES = [
    "fix(driver): correct SPI clock phase configuration for S32K344",
    "feat(can): add CAN-FD flexible data rate support",
    "refactor(build): migrate from Ant to Gradle build system",
    "fix(memory): resolve heap overflow in DMA transfer handler",
    "feat(diag): implement UDS diagnostic session management",
    "chore(deps): update CMSIS core to v5.9.0",
    "fix(watchdog): prevent spurious timeout during deep sleep exit",
    "feat(eth): add RMII interface support for S32K396",
    "test(adc): add boundary value tests for 12-bit ADC conversion",
    "fix(flash): correct sector erase timeout calculation",
    "feat(security): integrate HSE firmware update mechanism",
    "docs(api): update REST API reference for v2 endpoints",
    "fix(uart): handle framing error recovery in DMA mode",
    "feat(ota): implement A/B partition switching for firmware OTA",
    "perf(cache): optimize L1 cache invalidation on context switch",
    "fix(i2c): resolve clock stretching timeout on high-load buses",
]

PR_TITLES = [
    "S32-1234: SPI driver clock phase fix",
    "S32-1235: CAN-FD flexible data rate",
    "S32-1236: Build system migration to Gradle",
    "MCAL-890: DMA heap overflow fix",
    "MCAL-891: UDS diagnostic session",
    "VNT-456: CMSIS dependency update",
    "VNT-457: Deep sleep watchdog fix",
    "S32-1237: RMII Ethernet support",
]

ISSUE_TITLES = {
    "S32-1234": ("SPI clock phase misconfigured on K344", "Resolved", "Critical"),
    "S32-1235": ("CAN-FD mode not activating on K358", "Resolved", "Major"),
    "S32-1236": ("Migrate build system from Ant to Gradle", "Resolved", "Normal"),
    "S32-1237": ("Add RMII support for K396", "In Progress", "Major"),
    "S32-1238": ("Flash erase timeout on large sectors", "Resolved", "Critical"),
    "S32-1239": ("HSE firmware update failure handling", "Open", "Major"),
    "MCAL-890": ("DMA buffer overflow in transfer handler", "Resolved", "Critical"),
    "MCAL-891": ("UDS session management missing", "Resolved", "Major"),
    "MCAL-892": ("ADC accuracy drift at high temperature", "Open", "Normal"),
    "VNT-456": ("Update CMSIS core dependency", "Resolved", "Minor"),
    "VNT-457": ("Watchdog timeout during sleep mode", "Resolved", "Critical"),
    "VNT-458": ("CAN frame drop under bus load >85%", "In Progress", "Major"),
}

ARTIFACT_NAMES = {
    "s32-design-studio": [
        ("S32DS_3.6_IDE_linux64.tar.gz", "binary", 850_000_000),
        ("S32DS_3.6_IDE_win64.zip", "binary", 920_000_000),
        ("S32DS_3.6_plugins.zip", "eclipse_p2", 340_000_000),
        ("S32DS_3.6_update_site.zip", "eclipse_p2", 125_000_000),
    ],
    "autosar-mcal": [
        ("MCAL_S32K3_4.4.0_RTM.zip", "binary", 78_000_000),
        ("MCAL_S32K3_drivers.jar", "maven_jar", 12_000_000),
    ],
    "vehicle-network-toolbox": [
        ("vnt-core-2.1.0.whl", "python_wheel", 5_400_000),
        ("vnt-plugins-2.1.0.tar.gz", "generic", 2_100_000),
        ("vnt-gui-2.1.0-linux.AppImage", "binary", 67_000_000),
    ],
}

BUILD_TYPES = ["nightly", "weekly", "rc", "hotfix"]
BUILD_STATUSES_FLOW = ["ingesting", "hydrating", "completed", "testing", "released"]


async def seed_database() -> None:
    """Seed the database with rich sample data."""
    from sqlalchemy import select

    from urgp.config import get_settings
    from urgp.db.session import create_engine, create_session_factory
    from urgp.models.manifest import Artifact, BuildManifest
    from urgp.models.product import Product, Release
    from urgp.models.traceability import Commit, Issue, PullRequest, build_commits, commit_issues, commit_prs

    settings = get_settings()
    engine = create_engine(settings.database_url_str)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        # Check if data already exists
        result = await session.execute(select(Product).where(Product.external_id == "s32-design-studio"))
        existing = result.scalar_one_or_none()

        if existing:
            logger.info("Seed data already exists, skipping.")
            await engine.dispose()
            return

        # ── 1. Create Products ─────────────────────────────
        products: dict[str, Product] = {}
        for pdata in PRODUCTS:
            product = Product(**pdata)
            session.add(product)
            products[str(pdata["external_id"])] = product

        await session.flush()
        logger.info("Created %d products", len(products))

        # ── 2. Create Releases ─────────────────────────────
        releases: dict[str, list[Release]] = {}
        for ext_id, release_list in RELEASES_MAP.items():
            releases[ext_id] = []
            for rdata in release_list:
                release = Release(product_id=products[ext_id].id, **rdata)
                session.add(release)
                releases[ext_id].append(release)

        await session.flush()
        logger.info("Created %d releases", sum(len(v) for v in releases.values()))

        # ── 3. Create Issues ───────────────────────────────
        issues: dict[str, Issue] = {}
        for issue_key, (title, issue_status, priority) in ISSUE_TITLES.items():
            tracker = "jira"
            url = f"https://jira.nxp.com/browse/{issue_key}"
            issue = Issue(
                external_id=issue_key,
                tracker_type=tracker,
                title=title,
                status=issue_status,
                priority=priority,
                assignee=_rng.choice(COMMIT_AUTHORS),
                url=url,
            )
            session.add(issue)
            issues[issue_key] = issue

        await session.flush()
        logger.info("Created %d issues", len(issues))

        # ── 4. Create Commits ──────────────────────────────
        all_commits: list[Commit] = []
        for commit_idx in range(40):
            repo_choices = [
                "bitbucket.org/nxp/s32k3_dev",
                "bitbucket.org/nxp/s32k3_drivers",
                "bitbucket.org/nxp/mcal_s32k3",
                "github.com/nxp/vnt-core",
            ]
            commit = Commit(
                hash=_commit_hash(commit_idx),
                repository=_rng.choice(repo_choices),
                branch=_rng.choice(["main", "develop", "feature/can-fd", "bugfix/spi-phase", "release/3.6.8"]),
                author=_rng.choice(COMMIT_AUTHORS),
                message=_rng.choice(COMMIT_MESSAGES),
                committed_at=_now_minus(days=_rng.randint(0, 60), hours=_rng.randint(0, 23)),
            )
            session.add(commit)
            all_commits.append(commit)

        await session.flush()
        logger.info("Created %d commits", len(all_commits))

        # ── 5. Create Pull Requests ────────────────────────
        prs: list[PullRequest] = []
        for idx, title in enumerate(PR_TITLES):
            repo = _rng.choice(
                ["bitbucket.org/nxp/s32k3_dev", "bitbucket.org/nxp/mcal_s32k3", "github.com/nxp/vnt-core"]
            )
            pr = PullRequest(
                external_id=str(100 + idx),
                repository=repo,
                title=title,
                author=_rng.choice(COMMIT_AUTHORS),
                source_branch=f"feature/{title.split(':')[0].lower().replace('-', '_')}",
                target_branch="develop",
                merge_timestamp=_now_minus(days=_rng.randint(1, 30)),
                url=f"https://{repo}/pull-requests/{100 + idx}",
            )
            session.add(pr)
            prs.append(pr)

        await session.flush()
        logger.info("Created %d pull requests", len(prs))

        # ── 6. Link Commits ↔ PRs, Commits ↔ Issues ───────
        for _i, commit in enumerate(all_commits):
            # Link ~60% of commits to a PR
            if _rng.random() < 0.6 and prs:
                pr = _rng.choice(prs)
                await session.execute(commit_prs.insert().values(commit_id=commit.id, pr_id=pr.id))

            # Link ~40% of commits to an issue
            if _rng.random() < 0.4 and issues:
                issue = _rng.choice(list(issues.values()))
                await session.execute(commit_issues.insert().values(commit_id=commit.id, issue_id=issue.id))

        # ── 7. Create Builds with Artifacts ────────────────
        build_count = 0
        for ext_id, product in products.items():
            product_releases = releases[ext_id]
            artifacts_defs = ARTIFACT_NAMES.get(ext_id, [])

            for release in product_releases:
                # 3-6 builds per release
                num_builds = _rng.randint(3, 6)
                for b_idx in range(num_builds):
                    build_type = _rng.choice(BUILD_TYPES)
                    # Older builds are more likely to be released
                    days_ago = (num_builds - b_idx) * _rng.randint(3, 10)

                    if b_idx < num_builds - 2:
                        status_val = "released"
                    elif b_idx == num_builds - 2:
                        status_val = _rng.choice(["completed", "testing"])
                    else:
                        status_val = _rng.choice(["ingesting", "hydrating", "completed"])

                    build_id = f"{ext_id}-{release.version.replace(' ', '-').lower()}-{build_type}-{b_idx + 1:03d}"

                    ci_meta = {
                        "jenkins_url": f"https://ci.nxp.com/job/{ext_id}/{1000 + build_count}",
                        "jenkins_build_number": 1000 + build_count,
                        "node_label": _rng.choice(["linux-build-01", "linux-build-02", "win-build-01"]),
                        "duration_seconds": _rng.randint(120, 3600),
                        "triggered_by": _rng.choice(["timer", "scm_change", "manual"]),
                    }

                    manifest = BuildManifest(
                        build_id=build_id,
                        product_id=product.id,
                        release_id=release.id,
                        build_type=build_type,
                        status=status_val,
                        traceability_incomplete=(status_val in ("ingesting", "hydrating")),
                        cli_version="0.1.0",
                        ci_metadata=ci_meta,
                        released_at=_now_minus(days=days_ago) if status_val == "released" else None,
                        signature=_sha256(build_id) if status_val == "released" else None,
                    )
                    session.add(manifest)
                    await session.flush()

                    # Add artifacts
                    for art_name, art_type, art_size in artifacts_defs:
                        # Vary size slightly per build
                        size = art_size + _rng.randint(-art_size // 20, art_size // 20)
                        artifact = Artifact(
                            manifest_id=manifest.id,
                            name=art_name,
                            type=art_type,
                            storage_uri=f"s3://urgp-artifacts/{ext_id}/{release.version}/{build_id}/{art_name}",
                            sha256_checksum=_sha256(f"{build_id}-{art_name}-{b_idx}"),
                            size_bytes=size,
                        )
                        session.add(artifact)

                    # Link 2-5 commits to this build
                    linked_commits = _rng.sample(all_commits, min(_rng.randint(2, 5), len(all_commits)))
                    for commit in linked_commits:
                        with contextlib.suppress(Exception):
                            await session.execute(
                                build_commits.insert().values(build_id=manifest.id, commit_id=commit.id)
                            )

                    build_count += 1

        await session.commit()
        logger.info(
            "Seed complete: %d products, %d releases, %d builds, %d commits, %d PRs, %d issues",
            len(products),
            sum(len(v) for v in releases.values()),
            build_count,
            len(all_commits),
            len(prs),
            len(issues),
        )

    await engine.dispose()


def main() -> None:
    """Entry point for seed script."""
    from urgp.logging import setup_logging

    setup_logging(log_level="INFO", log_format="console")
    asyncio.run(seed_database())


if __name__ == "__main__":
    main()
