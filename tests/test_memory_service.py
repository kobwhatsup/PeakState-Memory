"""MemoryService 单元测试。

注意: 这些测试需要 PostgreSQL 数据库支持（因为使用了 JSONB 和 ARRAY 类型）。
使用 SQLite 时 JSONB/ARRAY 不可用，此文件中的测试标记为需要 postgres。

运行方式:
    DATABASE_URL_SYNC=postgresql://... pytest tests/test_memory_service.py
"""
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.database import Base
from app.schemas.memory import ManualMemoryCreate, UserProfileCreate, UserProfileUpdate
from app.services.memory_service import MemoryService

# 检测是否配置了 PostgreSQL
_is_postgres = "postgresql" in settings.DATABASE_URL

pytestmark = pytest.mark.skipif(
    not _is_postgres,
    reason="需要 PostgreSQL 数据库 (设置 DATABASE_URL 环境变量)",
)


@pytest_asyncio.fixture
async def pg_session():
    """PostgreSQL 测试会话 fixture。"""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session_factory() as session:
        yield session

    # 清理
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
def service():
    return MemoryService()


class TestUserProfile:
    """核心档案 CRUD 测试。"""

    @pytest.mark.asyncio
    async def test_create_and_get_profile(self, pg_session, service):
        profile_data = UserProfileCreate(
            user_id=1,
            nickname="张伟",
            occupation="产品经理",
            core_goals=["提升领导力", "平衡工作与生活"],
        )
        created = await service.create_user_profile(pg_session, profile_data)
        await pg_session.commit()

        assert created.nickname == "张伟"
        assert created.user_id == 1

        fetched = await service.get_user_profile(pg_session, user_id=1)
        assert fetched is not None
        assert fetched.nickname == "张伟"

    @pytest.mark.asyncio
    async def test_update_profile(self, pg_session, service):
        await service.create_user_profile(
            pg_session, UserProfileCreate(user_id=2, nickname="李四")
        )
        await pg_session.commit()

        updated = await service.update_user_profile(
            pg_session, user_id=2, profile_data=UserProfileUpdate(nickname="李四改")
        )
        await pg_session.commit()

        assert updated is not None
        assert updated.nickname == "李四改"
        assert updated.version == 2

    @pytest.mark.asyncio
    async def test_get_or_create_profile(self, pg_session, service):
        # 不存在时自动创建
        profile = await service.get_or_create_profile(pg_session, user_id=99)
        await pg_session.commit()
        assert profile.user_id == 99

        # 再次获取返回同一个
        same = await service.get_or_create_profile(pg_session, user_id=99)
        assert same.id == profile.id


class TestManualMemory:
    """手动记忆 CRUD 测试。"""

    @pytest.mark.asyncio
    async def test_create_memory(self, pg_session, service):
        memory = await service.create_manual_memory(
            pg_session,
            user_id=1,
            memory_data=ManualMemoryCreate(
                content="每周五接女儿放学",
                memory_type="event",
                importance_score=8,
            ),
        )
        await pg_session.commit()

        assert memory.content == "每周五接女儿放学"
        assert memory.memory_type == "event"
        assert memory.importance_score == 8

    @pytest.mark.asyncio
    async def test_get_recent_memories(self, pg_session, service):
        for i in range(5):
            await service.create_manual_memory(
                pg_session,
                user_id=1,
                memory_data=ManualMemoryCreate(
                    content=f"记忆 {i}",
                    importance_score=i + 1,
                ),
            )
        await pg_session.commit()

        memories = await service.get_recent_memories(pg_session, user_id=1, limit=3)
        assert len(memories) == 3
        # 按重要性降序
        assert memories[0].importance_score >= memories[1].importance_score

    @pytest.mark.asyncio
    async def test_delete_memory(self, pg_session, service):
        memory = await service.create_manual_memory(
            pg_session,
            user_id=1,
            memory_data=ManualMemoryCreate(content="要删除的记忆"),
        )
        await pg_session.commit()

        deleted = await service.delete_memory(pg_session, memory.id, user_id=1)
        await pg_session.commit()
        assert deleted is True

        # 删除后不再出现在活跃记忆中
        memories = await service.get_recent_memories(pg_session, user_id=1)
        assert all(m.id != memory.id for m in memories)

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_false(self, pg_session, service):
        result = await service.delete_memory(pg_session, 99999, user_id=1)
        assert result is False

    @pytest.mark.asyncio
    async def test_cannot_delete_others_memory(self, pg_session, service):
        memory = await service.create_manual_memory(
            pg_session,
            user_id=1,
            memory_data=ManualMemoryCreate(content="用户1的记忆"),
        )
        await pg_session.commit()

        # 用户2无法删除用户1的记忆
        result = await service.delete_memory(pg_session, memory.id, user_id=2)
        assert result is False


class TestConversationContext:
    """对话上下文测试。"""

    @pytest.mark.asyncio
    async def test_get_context_with_data(self, pg_session, service):
        await service.create_user_profile(
            pg_session,
            UserProfileCreate(user_id=1, nickname="张伟", occupation="产品经理"),
        )
        await service.create_manual_memory(
            pg_session,
            user_id=1,
            memory_data=ManualMemoryCreate(content="喜欢跑步"),
        )
        await pg_session.commit()

        ctx = await service.get_conversation_context(pg_session, user_id=1)
        assert ctx.core_profile is not None
        assert ctx.core_profile.nickname == "张伟"
        assert len(ctx.recent_memories) == 1
        assert "张伟" in ctx.formatted_prompt
        assert "喜欢跑步" in ctx.formatted_prompt

    @pytest.mark.asyncio
    async def test_get_context_empty_user(self, pg_session, service):
        ctx = await service.get_conversation_context(pg_session, user_id=999)
        assert ctx.core_profile is None
        assert len(ctx.recent_memories) == 0
        assert "暂无" in ctx.formatted_prompt
