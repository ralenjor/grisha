"""
Database Session Management

Provides synchronous and asynchronous session factories for database operations.
"""

from contextlib import contextmanager, asynccontextmanager
from typing import Generator, AsyncGenerator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from .config import get_database_config, INIT_SQL, ENUM_SQL
from .models import Base

from server.logging_config import get_logger, LOGGER_DATABASE

logger = get_logger(LOGGER_DATABASE)


# Global engine instances
_engine: Optional[object] = None
_async_engine: Optional[object] = None
_session_factory: Optional[sessionmaker] = None
_async_session_factory: Optional[async_sessionmaker] = None


def get_engine():
    """Get or create the synchronous database engine"""
    global _engine
    if _engine is None:
        config = get_database_config()
        _engine = create_engine(
            config.get_url(async_driver=False),
            pool_size=config.pool_size,
            max_overflow=config.max_overflow,
            pool_timeout=config.pool_timeout,
            pool_recycle=config.pool_recycle,
            echo=config.echo,
            echo_pool=config.echo_pool,
        )
    return _engine


def get_async_engine():
    """Get or create the asynchronous database engine"""
    global _async_engine
    if _async_engine is None:
        config = get_database_config()
        _async_engine = create_async_engine(
            config.get_url(async_driver=True),
            pool_size=config.pool_size,
            max_overflow=config.max_overflow,
            pool_timeout=config.pool_timeout,
            pool_recycle=config.pool_recycle,
            echo=config.echo,
            echo_pool=config.echo_pool,
        )
    return _async_engine


def get_session_factory() -> sessionmaker:
    """Get the synchronous session factory"""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _session_factory


def get_async_session_factory() -> async_sessionmaker:
    """Get the asynchronous session factory"""
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            bind=get_async_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_factory


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Get a synchronous database session (context manager)

    Usage:
        with get_session() as session:
            session.query(...)
    """
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Get an asynchronous database session (async context manager)

    Usage:
        async with get_async_session() as session:
            await session.execute(...)
    """
    factory = get_async_session_factory()
    session = factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


class DatabaseSession:
    """Dependency injection class for FastAPI"""

    def __init__(self):
        self.factory = get_session_factory()

    def __call__(self) -> Generator[Session, None, None]:
        session = self.factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


def init_database(create_tables: bool = True, drop_existing: bool = False) -> None:
    """Initialize the database schema

    Args:
        create_tables: If True, create all tables
        drop_existing: If True, drop existing tables first (DANGEROUS!)
    """
    logger.info("Initializing database schema")
    engine = get_engine()

    with engine.connect() as conn:
        # Create schema and enable PostGIS
        for statement in INIT_SQL.split(";"):
            statement = statement.strip()
            if statement:
                try:
                    conn.execute(text(statement))
                except Exception as e:
                    # Schema/extension might already exist
                    logger.debug(f"Schema init note: {e}")
        conn.commit()

        # Create enum types
        for statement in ENUM_SQL.split(";"):
            statement = statement.strip()
            if statement:
                try:
                    conn.execute(text(statement))
                except Exception as e:
                    # Types might already exist
                    if "already exists" not in str(e):
                        logger.debug(f"Enum type note: {e}")
        conn.commit()

    if drop_existing:
        logger.warning("Dropping existing tables")
        Base.metadata.drop_all(bind=engine)

    if create_tables:
        logger.info("Creating database tables")
        Base.metadata.create_all(bind=engine)

    logger.info("Database schema initialized successfully")


async def init_database_async(create_tables: bool = True, drop_existing: bool = False) -> None:
    """Initialize the database schema asynchronously

    Args:
        create_tables: If True, create all tables
        drop_existing: If True, drop existing tables first (DANGEROUS!)
    """
    logger.info("Initializing database schema (async)")
    engine = get_async_engine()

    async with engine.begin() as conn:
        # Create schema and enable PostGIS
        for statement in INIT_SQL.split(";"):
            statement = statement.strip()
            if statement:
                try:
                    await conn.execute(text(statement))
                except Exception as e:
                    logger.debug(f"Schema init note: {e}")

        # Create enum types
        for statement in ENUM_SQL.split(";"):
            statement = statement.strip()
            if statement:
                try:
                    await conn.execute(text(statement))
                except Exception as e:
                    if "already exists" not in str(e):
                        logger.debug(f"Enum type note: {e}")

    if drop_existing:
        logger.warning("Dropping existing tables")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    if create_tables:
        logger.info("Creating database tables")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    logger.info("Database schema initialized successfully")


def close_database() -> None:
    """Close database connections and reset global state"""
    global _engine, _async_engine, _session_factory, _async_session_factory

    logger.info("Closing database connections")

    if _engine is not None:
        _engine.dispose()
        _engine = None

    if _async_engine is not None:
        # Note: async engine disposal should be done in async context
        _async_engine = None

    _session_factory = None
    _async_session_factory = None
    logger.debug("Database connections closed")


async def close_database_async() -> None:
    """Close database connections asynchronously"""
    global _engine, _async_engine, _session_factory, _async_session_factory

    logger.info("Closing database connections (async)")

    if _engine is not None:
        _engine.dispose()
        _engine = None

    if _async_engine is not None:
        await _async_engine.dispose()
        _async_engine = None

    _session_factory = None
    _async_session_factory = None
    logger.debug("Database connections closed")
