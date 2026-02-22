from collections.abc import AsyncGenerator

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# ── PostgreSQL ─────────────────────────────────────────

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖注入：提供 PostgreSQL 数据库会话。"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── MongoDB ────────────────────────────────────────────

_mongo_client: AsyncIOMotorClient | None = None
_mongo_db: AsyncIOMotorDatabase | None = None


async def connect_mongo() -> None:
    """初始化 MongoDB 连接。在应用启动时调用。"""
    global _mongo_client, _mongo_db
    _mongo_client = AsyncIOMotorClient(settings.MONGODB_URL)
    _mongo_db = _mongo_client[settings.MONGODB_DB_NAME]

    # 创建索引
    await _mongo_db.daily_memories.create_index(
        [("user_id", 1), ("date", -1)], unique=True
    )
    await _mongo_db.long_term_memories.create_index(
        [("user_id", 1), ("period_start", -1)]
    )
    await _mongo_db.long_term_memories.create_index(
        [("user_id", 1), ("period_type", 1)]
    )


async def close_mongo() -> None:
    """关闭 MongoDB 连接。在应用关闭时调用。"""
    global _mongo_client, _mongo_db
    if _mongo_client:
        _mongo_client.close()
        _mongo_client = None
        _mongo_db = None


def get_mongo_db() -> AsyncIOMotorDatabase:
    """获取 MongoDB 数据库实例。"""
    if _mongo_db is None:
        raise RuntimeError("MongoDB 未连接。请先调用 connect_mongo()。")
    return _mongo_db
