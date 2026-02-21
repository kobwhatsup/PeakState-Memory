"""API 端点集成测试。

注意: 由于 SQLite 不支持 PostgreSQL 特有的 JSONB 和 ARRAY 类型，
这些测试需要 PostgreSQL 数据库。SQLite fixture 仅用于路由注册验证。

运行方式:
    DATABASE_URL=postgresql+asyncpg://... pytest tests/test_api.py
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.database import Base, get_db
from app.main import app

_is_postgres = "postgresql" in settings.DATABASE_URL

pytestmark = pytest.mark.skipif(
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
        assert resp.json()["status"] == "ok"


class TestProfileAPI:
    """核心档案 API 测试。"""

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
        # 先创建
        await pg_client.get(
            "/api/v1/memory/profile",
            headers={"X-User-Id": "1"},
        )

        # 更新
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


class TestManualMemoryAPI:
    """手动记忆 API 测试。"""

    @pytest.mark.asyncio
    async def test_create_memory(self, pg_client):
        resp = await pg_client.post(
            "/api/v1/memory/manual",
            headers={"X-User-Id": "1"},
            json={
                "content": "每周五下午接女儿放学",
                "memory_type": "event",
                "importance_score": 8,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["content"] == "每周五下午接女儿放学"
        assert data["memory_type"] == "event"

    @pytest.mark.asyncio
    async def test_get_recent_memories(self, pg_client):
        # 创建几条记忆
        for i in range(3):
            await pg_client.post(
                "/api/v1/memory/manual",
                headers={"X-User-Id": "1"},
                json={"content": f"记忆 {i}"},
            )

        resp = await pg_client.get(
            "/api/v1/memory/manual/recent?limit=10",
            headers={"X-User-Id": "1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3

    @pytest.mark.asyncio
    async def test_delete_memory(self, pg_client):
        # 创建
        create_resp = await pg_client.post(
            "/api/v1/memory/manual",
            headers={"X-User-Id": "1"},
            json={"content": "要删除的记忆"},
        )
        memory_id = create_resp.json()["id"]

        # 删除
        resp = await pg_client.delete(
            f"/api/v1/memory/manual/{memory_id}",
            headers={"X-User-Id": "1"},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_404(self, pg_client):
        resp = await pg_client.delete(
            "/api/v1/memory/manual/99999",
            headers={"X-User-Id": "1"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_create_memory_validation(self, pg_client):
        # 空内容应该返回 422
        resp = await pg_client.post(
            "/api/v1/memory/manual",
            headers={"X-User-Id": "1"},
            json={"content": ""},
        )
        assert resp.status_code == 422

        # importance_score 超范围应该返回 422
        resp = await pg_client.post(
            "/api/v1/memory/manual",
            headers={"X-User-Id": "1"},
            json={"content": "test", "importance_score": 11},
        )
        assert resp.status_code == 422


class TestContextAPI:
    """记忆上下文 API 测试。"""

    @pytest.mark.asyncio
    async def test_get_context(self, pg_client):
        resp = await pg_client.get("/api/v1/memory/context?user_id=1")
        assert resp.status_code == 200
        data = resp.json()
        assert "formatted_prompt" in data
        assert "core_profile" in data
        assert "recent_memories" in data
