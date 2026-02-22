"""MemoryService 单元测试。

核心档案测试需要 PostgreSQL 数据库支持（JSONB 和 ARRAY 类型）。
MongoDB 相关测试使用 mock 对象。

运行方式:
    DATABASE_URL_SYNC=postgresql://... pytest tests/test_memory_service.py
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.database import Base
from app.models.memory import DailyMemory, MemoryCategory, MemoryItem
from app.schemas.memory import UserProfileCreate, UserProfileUpdate
from app.services.memory_service import MemoryService

# 检测是否配置了 PostgreSQL
_is_postgres = "postgresql" in settings.DATABASE_URL

pytestmark_postgres = pytest.mark.skipif(
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

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
def service():
    return MemoryService()


class TestUserProfile:
    """核心档案 CRUD 测试（PostgreSQL）。"""

    pytestmark = pytestmark_postgres

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
        profile = await service.get_or_create_profile(pg_session, user_id=99)
        await pg_session.commit()
        assert profile.user_id == 99

        same = await service.get_or_create_profile(pg_session, user_id=99)
        assert same.id == profile.id


class TestDailyMemory:
    """每日记忆测试（Mock MongoDB）。"""

    @pytest.mark.asyncio
    async def test_add_memory_items(self, service, mock_mongo_db):
        items = [
            MemoryItem(
                category=MemoryCategory.PREFERENCE,
                content="喜欢跑步",
                importance=6,
            ),
            MemoryItem(
                category=MemoryCategory.HEALTH,
                content="对花生过敏",
                importance=9,
            ),
        ]

        await service.add_memory_items(
            user_id=1, date="2026-02-22", items=items, mongo_db=mock_mongo_db
        )

        mock_mongo_db.daily_memories.update_one.assert_called_once()
        call_args = mock_mongo_db.daily_memories.update_one.call_args
        assert call_args[0][0] == {"user_id": 1, "date": "2026-02-22"}

    @pytest.mark.asyncio
    async def test_add_empty_items_is_noop(self, service, mock_mongo_db):
        await service.add_memory_items(
            user_id=1, date="2026-02-22", items=[], mongo_db=mock_mongo_db
        )
        mock_mongo_db.daily_memories.update_one.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_daily_memory_found(self, service, mock_mongo_db):
        mock_mongo_db.daily_memories.find_one = AsyncMock(return_value={
            "user_id": 1,
            "date": "2026-02-22",
            "items": [
                {
                    "category": "preference",
                    "content": "喜欢跑步",
                    "importance": 6,
                    "source_role": "user",
                    "extracted_at": datetime.now(timezone.utc).isoformat(),
                }
            ],
            "summary": None,
            "conversation_count": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })

        result = await service.get_daily_memory(1, "2026-02-22", mongo_db=mock_mongo_db)
        assert result is not None
        assert result.date == "2026-02-22"
        assert len(result.items) == 1
        assert result.items[0].content == "喜欢跑步"

    @pytest.mark.asyncio
    async def test_get_daily_memory_not_found(self, service, mock_mongo_db):
        result = await service.get_daily_memory(1, "2026-02-22", mongo_db=mock_mongo_db)
        assert result is None

    @pytest.mark.asyncio
    async def test_update_daily_summary(self, service, mock_mongo_db):
        await service.update_daily_summary(
            user_id=1,
            date="2026-02-22",
            summary="今天用户提到喜欢跑步和对花生过敏",
            mongo_db=mock_mongo_db,
        )
        mock_mongo_db.daily_memories.update_one.assert_called_once()


class TestLongTermMemory:
    """长期记忆测试（Mock MongoDB）。"""

    @pytest.mark.asyncio
    async def test_create_long_term_memory(self, service, mock_mongo_db):
        from app.models.memory import LongTermMemory

        memory = LongTermMemory(
            user_id=1,
            period_type="weekly",
            period_start="2026-02-10",
            period_end="2026-02-16",
            summary="本周用户重点关注健康和运动",
            key_themes=["健康", "运动"],
            notable_changes=["开始关注睡眠质量"],
            emotional_trend="积极向上",
        )
        await service.create_long_term_memory(memory, mongo_db=mock_mongo_db)
        mock_mongo_db.long_term_memories.insert_one.assert_called_once()


class TestMemoryExtraction:
    """记忆提取测试（Mock LLM API）。"""

    @pytest.mark.asyncio
    async def test_extract_and_store(self, service, mock_mongo_db):
        mock_items = [
            MemoryItem(
                category=MemoryCategory.PREFERENCE,
                content="喜欢跑步",
                importance=6,
            ),
        ]

        with patch.object(
            service._extractor,
            "extract_from_conversation",
            return_value=mock_items,
        ):
            result = await service.extract_and_store(
                user_id=1,
                messages=[{"role": "user", "content": "我喜欢跑步"}],
                mongo_db=mock_mongo_db,
            )

        assert len(result) == 1
        assert result[0].content == "喜欢跑步"
        mock_mongo_db.daily_memories.update_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_empty_messages(self, service, mock_mongo_db):
        result = await service.extract_and_store(
            user_id=1, messages=[], mongo_db=mock_mongo_db
        )
        assert len(result) == 0
