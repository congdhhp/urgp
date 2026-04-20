"""SQLAlchemy database connection and session management."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


def create_engine(database_url: str, pool_size: int = 10, pool_overflow: int = 20) -> AsyncEngine:  # type: ignore[name-defined]  # noqa: F821
    """Create an async SQLAlchemy engine.

    Args:
        database_url: PostgreSQL async connection URL.
        pool_size: Connection pool size.
        pool_overflow: Max overflow connections.

    Returns:
        AsyncEngine: Configured async engine.
    """
    from sqlalchemy.ext.asyncio import create_async_engine as _create

    return _create(
        database_url,
        pool_size=pool_size,
        max_overflow=pool_overflow,
        pool_pre_ping=True,
        echo=False,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:  # type: ignore[name-defined]  # noqa: F821
    """Create an async session factory.

    Args:
        engine: SQLAlchemy async engine.

    Returns:
        async_sessionmaker: Session factory bound to the engine.
    """
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


async def get_session(session_factory: async_sessionmaker[AsyncSession]) -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields an async database session.

    Usage with FastAPI:
        @app.get("/items")
        async def list_items(session: AsyncSession = Depends(get_session)):
            ...
    """
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
