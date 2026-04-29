"""Runtime resource container for API and worker processes."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from urgp.config import URGPSettings
from urgp.db.session import create_engine, create_session_factory
from urgp.logging import setup_logging
from urgp.messaging.connection import create_rabbitmq_connection
from urgp.messaging.topology import setup_topology
from urgp.services.publisher import EventPublisher

logger = logging.getLogger(__name__)

RedisType = aioredis.Redis


@dataclass(slots=True)
class AppResources:
    """Shared runtime resources owned by one process."""

    settings: URGPSettings
    engine: AsyncEngine | None = None
    session_factory: async_sessionmaker[AsyncSession] | None = None
    redis: RedisType | None = None
    publisher: EventPublisher | None = None

    async def open(
        self,
        *,
        with_database: bool = True,
        with_redis: bool = True,
        with_publisher: bool = True,
        ensure_rabbitmq_topology: bool = True,
    ) -> None:
        """Initialize runtime resources for a process."""
        setup_logging(
            log_level=self.settings.log_level,
            log_format=self.settings.log_format,
        )

        if with_database and self.engine is None:
            self.engine = create_engine(
                self.settings.database_url_str,
                pool_size=self.settings.database_pool_size,
                pool_overflow=self.settings.database_pool_overflow,
            )
            self.session_factory = create_session_factory(self.engine)
            logger.info("Database engine initialized")

        if ensure_rabbitmq_topology:
            await self._ensure_rabbitmq_topology()

        if with_redis and self.redis is None:
            await self._open_redis()

        if with_publisher and self.publisher is None:
            await self._open_publisher()

    async def close(self) -> None:
        """Close all initialized resources."""
        if self.publisher is not None:
            try:
                await self.publisher.close()
                logger.info("EventPublisher closed")
            except Exception:
                logger.warning("Error closing EventPublisher", exc_info=True)
            finally:
                self.publisher = None

        if self.redis is not None:
            try:
                aclose = getattr(self.redis, "aclose", None)
                if callable(aclose):
                    await aclose()
                else:
                    await self.redis.close()
                logger.info("Redis client closed")
            except Exception:
                logger.warning("Error closing Redis client", exc_info=True)
            finally:
                self.redis = None

        if self.engine is not None:
            try:
                await self.engine.dispose()
                logger.info("Database engine disposed")
            except Exception:
                logger.warning("Error disposing database engine", exc_info=True)
            finally:
                self.engine = None
                self.session_factory = None

    def require_session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Return the initialized session factory or raise clearly."""
        if self.session_factory is None:
            msg = "Database session factory is not initialized."
            raise RuntimeError(msg)
        return self.session_factory

    async def _ensure_rabbitmq_topology(self) -> None:
        try:
            connection = await create_rabbitmq_connection(self.settings.rabbitmq_url)
            try:
                await setup_topology(connection)
            finally:
                await connection.close()
            logger.info("RabbitMQ topology initialized")
        except Exception:
            logger.warning(
                "Could not initialize RabbitMQ topology; broker-dependent features will retry later",
                exc_info=True,
            )

    async def _open_redis(self) -> None:
        try:
            redis_client = aioredis.from_url(  # type: ignore[no-untyped-call]
                str(self.settings.redis_url),
                decode_responses=False,
                socket_timeout=5,
            )
            await redis_client.ping()
            self.redis = redis_client
            logger.info("Redis client initialized")
        except Exception:
            logger.warning(
                "Could not connect to Redis; rate limiting and idempotency may fail",
                exc_info=True,
            )
            self.redis = None

    async def _open_publisher(self) -> None:
        try:
            publisher = EventPublisher(self.settings.rabbitmq_url)
            await publisher.connect()
            self.publisher = publisher
            logger.info("EventPublisher initialized")
        except Exception:
            logger.warning(
                "Could not initialize EventPublisher; ingestion will fail until broker recovers",
                exc_info=True,
            )
            self.publisher = None
