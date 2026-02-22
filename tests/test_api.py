"""API 端点集成测试。

核心档案 API 需要 PostgreSQL。
MongoDB 相关 API 使用 mock。

运行方式:
    DATABASE_URL=postgresql+asyncpg://... pytest tests/test_api.py
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.database import Base, get_db
from app.main import app

_is_postgres = "postgresql" in settings.DATABASE_URL

pytestmark_postgres = pytest.mark.skipif(
    not _is_postgres,
    reason="需要 PostgreSQL 数据库 (设置 DATABASE_URL 环境变量)",
)


@pytest_asyncio.fixture
async def pg_client():
    """PostgreSQL 测试客户端 fixture。"""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db():
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

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


class TestHealthCheck:
    """健康检查端点测试（不依赖数据库）。"""

    @pytest.mark.asyncio
    async def test_health(self):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as ac:
            resp = await ac.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.2.0"


class TestProfileAPI:
    """核心档案 API 测试。"""

    pytestmark = pytestmark_postgres

    @pytest.mark.asyncio
    async def test_get_profile_creates_empty(self, pg_client):
        resp = await pg_client.get(
            "/api/v1/memory/profile",
            headers={"X-User-Id": "1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == 1

    @pytest.mark.asyncio
    async def test_update_profile(self, pg_client):
        await pg_client.get(
            "/api/v1/memory/profile",
            headers={"X-User-Id": "1"},
        )

        resp = await pg_client.put(
            "/api/v1/memory/profile",
            headers={"X-User-Id": "1"},
            json={
                "nickname": "张伟",
                "core_goals": ["提升领导力"],
                "health_info": {"caffeine_sensitivity": "high"},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["nickname"] == "张伟"
        assert data["core_goals"] == ["提升领导力"]


class TestDailyMemoryAPI:
    """每日记忆 API 测试（Mock MongoDB）。"""

    @pytest.mark.asyncio
    async def test_get_daily_memory_empty(self):
        with patch("app.routers.memory.memory_service") as mock_service:
            mock_service.get_daily_memory = AsyncMock(return_value=None)

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as ac:
                resp = await ac.get(
                    "/api/v1/memory/daily?date=2026-02-22",
                    headers={"X-User-Id": "1"},
                )

            assert resp.status_code == 200
            data = resp.json()
            assert data["user_id"] == 1
            assert data["date"] == "2026-02-22"
            assert data["items"] == []

    @pytest.mark.asyncio
    async def test_get_recent_daily_memories(self):
        with patch("app.routers.memory.memory_service") as mock_service:
            mock_service.get_recent_daily_memories = AsyncMock(return_value=[])

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as ac:
                resp = await ac.get(
                    "/api/v1/memory/daily/recent?days=7",
                    headers={"X-User-Id": "1"},
                )

            assert resp.status_code == 200
            assert resp.json() == []


class TestInternalAPI:
    """内部 API 测试（Mock）。"""

    @pytest.mark.asyncio
    async def test_extract_memories(self):
        from app.models.memory import MemoryCategory, MemoryItem

        mock_items = [
            MemoryItem(
                category=MemoryCategory.PREFERENCE,
                content="喜欢跑步",
                importance=6,
            ),
        ]

        with patch("app.routers.memory.memory_service") as mock_service:
            mock_service.extract_and_store = AsyncMock(return_value=mock_items)

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as ac:
                resp = await ac.post(
                    "/api/v1/memory/internal/extract",
                    json={
                        "user_id": 1,
                        "messages": [
                            {"role": "user", "content": "我喜欢跑步"},
                        ],
                    },
                )

            assert resp.status_code == 200
            data = resp.json()
            assert data["extracted_count"] == 1
            assert data["items"][0]["content"] == "喜欢跑步"
