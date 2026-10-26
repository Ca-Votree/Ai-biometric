"""
Database Session Management
Quản lý kết nối database bằng SQLAlchemy async.
"""
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from loguru import logger

from app.config import settings
from app.database.models import Base


# Tạo async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)

@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if "sqlite" in settings.DATABASE_URL:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

# Session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """Dependency injection cho FastAPI - tạo session mới cho mỗi request."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Tạo bảng và bổ sung cột mới cho database SQLite hiện hữu."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if "sqlite" in settings.DATABASE_URL:
            columns = await conn.exec_driver_sql("PRAGMA table_info(sessions)")
            existing = {row[1] for row in columns.fetchall()}
            if "status" not in existing:
                await conn.exec_driver_sql("ALTER TABLE sessions ADD COLUMN status VARCHAR(20) DEFAULT 'open'")
    logger.info("✅ Database đã được khởi tạo")


async def close_db():
    """Đóng kết nối database."""
    await engine.dispose()
    logger.info("Database connection đã được đóng")
