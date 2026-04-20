"""Database seed script — sample data for local development.

Creates a sample product (S32 Design Studio) and release train (3.6.8 RFP)
so developers can test the portal immediately after docker compose up.

Usage: python -m urgp.db.seed
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


async def seed_database() -> None:
    """Seed the database with sample data."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from urgp.config import get_settings
    from urgp.db.session import create_engine, create_session_factory
    from urgp.models.product import Product, Release

    settings = get_settings()
    engine = create_engine(settings.database_url_str)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        session: AsyncSession

        # Check if product already exists
        result = await session.execute(
            select(Product).where(Product.name == "S32 Design Studio")
        )
        existing = result.scalar_one_or_none()

        if existing:
            logger.info("Seed data already exists, skipping.")
            await engine.dispose()
            return

        # Create sample product
        product = Product(
            name="S32 Design Studio",
            description="NXP S32 Design Studio IDE for automotive microcontrollers",
            git_config={
                "provider": "bitbucket",
                "repositories": [
                    "bitbucket.org/nxp/s32k3_dev",
                    "bitbucket.org/nxp/s32k3_drivers",
                ],
            },
            issue_config={
                "tracker": "jira",
                "base_url": "https://jira.nxp.com",
                "project_key": "S32",
                "issue_regex": r"S32-\d+",
            },
        )
        session.add(product)
        await session.flush()

        # Create sample release train
        release = Release(
            product_id=product.id,
            version="3.6.8 RFP",
            release_type="RFP",
            status="active",
        )
        session.add(release)
        await session.commit()

        logger.info("Seed data created: product '%s', release '%s'", product.name, release.version)

    await engine.dispose()


def main() -> None:
    """Entry point for seed script."""
    from urgp.logging import setup_logging
    setup_logging(log_level="INFO", log_format="console")
    asyncio.run(seed_database())


if __name__ == "__main__":
    main()
