import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app

# 测试用 SQLite 内存数据库（不支持 JSONB/ARRAY，仅用于 API 集成测试骨架）
# 完整的数据库测试需要 PostgreSQL
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """为所有测试共享一个事件循环。"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_engine():
    """创建测试用数据库引擎。"""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """创建测试用数据库会话。"""
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def mock_mongo_db():
    """创建 Mock MongoDB 数据库对象。"""
    db = MagicMock()

    # 模拟集合
    for collection_name in ["daily_memories", "long_term_memories"]:
        collection = MagicMock()

        # 模拟 find_one
        collection.find_one = AsyncMock(return_value=None)

        # 模拟 update_one / insert_one
        collection.update_one = AsyncMock()
        collection.insert_one = AsyncMock()

        # 模拟 find (返回可异步迭代的游标)
        mock_cursor = MagicMock()
        mock_cursor.sort = MagicMock(return_value=mock_cursor)
        mock_cursor.limit = MagicMock(return_value=mock_cursor)
        mock_cursor.__aiter__ = AsyncMock(return_value=iter([]))

        collection.find = MagicMock(return_value=mock_cursor)

        # 模拟 distinct
        collection.distinct = AsyncMock(return_value=[])

        setattr(db, collection_name, collection)

    return db


@pytest_asyncio.fixture
async def client(db_engine) -> AsyncGenerator[AsyncClient, None]:
    """创建测试用 HTTP 客户端。"""
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
