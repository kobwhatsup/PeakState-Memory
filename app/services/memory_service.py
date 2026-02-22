"""记忆管理核心服务。

整合 PostgreSQL（核心档案）和 MongoDB（每日记忆、长期记忆）,
提供统一的记忆读写和上下文构建能力。
"""

import logging
from datetime import datetime, timedelta, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_mongo_db
from app.models.memory import (
    DailyMemory,
    LongTermMemory,
    MemoryItem,
    UserProfile,
)
from app.schemas.memory import (
    MemoryContextResponse,
    MemoryItemSchema,
    UserProfileCreate,
    UserProfileResponse,
    UserProfileUpdate,
)
from app.services.memory_extractor import MemoryExtractor

logger = logging.getLogger(__name__)


def _format_core_profile(profile: UserProfile) -> str:
    """将核心档案格式化为 LLM 可读的提示词文本。"""
    lines: list[str] = []

    if profile.nickname:
        lines.append(f"- 昵称: {profile.nickname}")
    if profile.gender:
        lines.append(f"- 性别: {profile.gender}")
    if profile.occupation:
        lines.append(f"- 职业: {profile.occupation}")
    if profile.family_role:
        lines.append(f"- 家庭角色: {', '.join(profile.family_role)}")
    if profile.core_goals:
        goals = ", ".join(str(g) for g in profile.core_goals)
        lines.append(f"- 核心目标: {goals}")
    if profile.core_values:
        values = ", ".join(str(v) for v in profile.core_values)
        lines.append(f"- 核心价值观: {values}")
    if profile.health_info:
        for key, value in profile.health_info.items():
            lines.append(f"- 健康信息 - {key}: {value}")
    if profile.preferences:
        for key, value in profile.preferences.items():
            lines.append(f"- 偏好 - {key}: {value}")

    return "\n".join(lines) if lines else "暂无核心档案信息"


def _format_daily_memories(items: list[dict]) -> str:
    """将近期每日记忆格式化为 LLM 可读文本。"""
    if not items:
        return "暂无近期记忆"

    lines: list[str] = []
    now = datetime.now(timezone.utc)

    for item in items:
        extracted_at = item.get("extracted_at")
        if isinstance(extracted_at, str):
            try:
                extracted_at = datetime.fromisoformat(extracted_at)
            except (ValueError, TypeError):
                extracted_at = now

        if extracted_at and extracted_at.tzinfo is None:
            extracted_at = extracted_at.replace(tzinfo=timezone.utc)

        if extracted_at:
            delta = now - extracted_at
            if delta.days == 0:
                time_label = "今天"
            elif delta.days == 1:
                time_label = "昨天"
            elif delta.days < 7:
                time_label = f"{delta.days}天前"
            else:
                time_label = f"{delta.days // 7}周前"
        else:
            time_label = "未知时间"

        content = item.get("content", "")
        category = item.get("category", "general")
        lines.append(f"- [{time_label}][{category}] {content}")

    return "\n".join(lines)


MEMORY_CONTEXT_TEMPLATE = """# 用户核心信息
{core_profile}

# 近期记忆
{daily_memories}

# 长期记忆摘要
{long_term_summary}

请在回复中自然地使用这些信息，而不是生硬地复述。"""


class MemoryService:
    """记忆管理核心服务。

    整合 PostgreSQL（核心档案）和 MongoDB（每日记忆、长期记忆），
    提供完整的记忆管理和上下文构建功能。
    """

    def __init__(self) -> None:
        self._extractor = MemoryExtractor()

    # ── 核心档案（PostgreSQL） ────────────────────────────

    async def get_user_profile(
        self, db: AsyncSession, user_id: int
    ) -> UserProfile | None:
        """获取用户核心档案。"""
        result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create_user_profile(
        self, db: AsyncSession, profile_data: UserProfileCreate
    ) -> UserProfile:
        """创建用户核心档案。"""
        profile = UserProfile(**profile_data.model_dump())
        db.add(profile)
        await db.flush()
        await db.refresh(profile)
        return profile

    async def update_user_profile(
        self, db: AsyncSession, user_id: int, profile_data: UserProfileUpdate
    ) -> UserProfile | None:
        """更新用户核心档案（仅更新传入的字段）。"""
        profile = await self.get_user_profile(db, user_id)
        if not profile:
            return None

        update_data = profile_data.model_dump(exclude_unset=True)
        if not update_data:
            return profile

        update_data["updated_at"] = datetime.now(timezone.utc)
        update_data["version"] = profile.version + 1

        await db.execute(
            update(UserProfile)
            .where(UserProfile.user_id == user_id)
            .values(**update_data)
        )
        await db.refresh(profile)
        return profile

    async def get_or_create_profile(
        self, db: AsyncSession, user_id: int
    ) -> UserProfile:
        """获取用户档案，不存在则创建空档案。"""
        profile = await self.get_user_profile(db, user_id)
        if not profile:
            profile = await self.create_user_profile(
                db, UserProfileCreate(user_id=user_id)
            )
        return profile

    # ── 每日记忆（MongoDB） ─────────────────────────────

    async def get_daily_memory(
        self, user_id: int, date: str, mongo_db: AsyncIOMotorDatabase | None = None
    ) -> DailyMemory | None:
        """获取指定日期的每日记忆文档。"""
        db = mongo_db or get_mongo_db()
        doc = await db.daily_memories.find_one(
            {"user_id": user_id, "date": date}
        )
        if doc:
            doc.pop("_id", None)
            return DailyMemory(**doc)
        return None

    async def get_recent_daily_memories(
        self, user_id: int, days: int = 7, mongo_db: AsyncIOMotorDatabase | None = None
    ) -> list[DailyMemory]:
        """获取最近 N 天的每日记忆。"""
        db = mongo_db or get_mongo_db()
        today = datetime.now(timezone.utc)
        start_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")

        cursor = db.daily_memories.find(
            {"user_id": user_id, "date": {"$gte": start_date}}
        ).sort("date", -1)

        results: list[DailyMemory] = []
        async for doc in cursor:
            doc.pop("_id", None)
            results.append(DailyMemory(**doc))
        return results

    async def add_memory_items(
        self,
        user_id: int,
        date: str,
        items: list[MemoryItem],
        mongo_db: AsyncIOMotorDatabase | None = None,
    ) -> None:
        """向指定日期添加记忆项。文档不存在则自动创建。"""
        if not items:
            return

        db = mongo_db or get_mongo_db()
        items_data = [item.model_dump(mode="json") for item in items]

        await db.daily_memories.update_one(
            {"user_id": user_id, "date": date},
            {
                "$push": {"items": {"$each": items_data}},
                "$inc": {"conversation_count": 1},
                "$set": {"updated_at": datetime.now(timezone.utc).isoformat()},
                "$setOnInsert": {
                    "user_id": user_id,
                    "date": date,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            },
            upsert=True,
        )

    async def update_daily_summary(
        self, user_id: int, date: str, summary: str,
        mongo_db: AsyncIOMotorDatabase | None = None,
    ) -> None:
        """更新每日记忆的摘要。"""
        db = mongo_db or get_mongo_db()
        await db.daily_memories.update_one(
            {"user_id": user_id, "date": date},
            {"$set": {
                "summary": summary,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )

    # ── 长期记忆（MongoDB） ─────────────────────────────

    async def create_long_term_memory(
        self,
        memory: LongTermMemory,
        mongo_db: AsyncIOMotorDatabase | None = None,
    ) -> None:
        """创建长期记忆文档。"""
        db = mongo_db or get_mongo_db()
        await db.long_term_memories.insert_one(memory.model_dump(mode="json"))

    async def get_long_term_memories(
        self,
        user_id: int,
        since: str | None = None,
        limit: int = 10,
        mongo_db: AsyncIOMotorDatabase | None = None,
    ) -> list[LongTermMemory]:
        """获取长期记忆列表。"""
        db = mongo_db or get_mongo_db()
        query: dict = {"user_id": user_id}
        if since:
            query["period_start"] = {"$gte": since}

        cursor = (
            db.long_term_memories.find(query)
            .sort("period_start", -1)
            .limit(limit)
        )

        results: list[LongTermMemory] = []
        async for doc in cursor:
            doc.pop("_id", None)
            results.append(LongTermMemory(**doc))
        return results

    # ── 记忆提取（从对话中自动提取） ────────────────────

    async def extract_and_store(
        self, user_id: int, messages: list[dict[str, str]],
        mongo_db: AsyncIOMotorDatabase | None = None,
    ) -> list[MemoryItem]:
        """从对话中提取记忆并存储到 MongoDB。

        Args:
            user_id: 用户 ID。
            messages: 对话消息列表。

        Returns:
            提取的记忆项列表。
        """
        items = await self._extractor.extract_from_conversation(messages)
        if items:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            await self.add_memory_items(user_id, today, items, mongo_db=mongo_db)
            logger.info(
                "为用户 %d 提取了 %d 条记忆", user_id, len(items)
            )
        return items

    # ── 上下文构建 ──────────────────────────────────────

    async def build_context_for_llm(
        self,
        db: AsyncSession,
        user_id: int,
        mongo_db: AsyncIOMotorDatabase | None = None,
    ) -> MemoryContextResponse:
        """构建 LLM 对话上下文。

        整合三层记忆：核心档案 + 近期每日记忆 + 长期记忆摘要。

        Args:
            db: PostgreSQL 会话。
            user_id: 用户 ID。

        Returns:
            包含完整上下文的响应对象。
        """
        # 1. 核心档案
        profile = await self.get_user_profile(db, user_id)
        profile_text = _format_core_profile(profile) if profile else "暂无核心档案信息"

        # 2. 近期每日记忆（最近 7 天）
        recent_memories = await self.get_recent_daily_memories(
            user_id, days=7, mongo_db=mongo_db
        )
        all_items: list[dict] = []
        for daily in recent_memories:
            for item in daily.items:
                item_dict = item.model_dump(mode="json")
                all_items.append(item_dict)

        # 按重要性排序，取 top N
        all_items.sort(key=lambda x: x.get("importance", 5), reverse=True)
        top_items = all_items[: settings.MAX_RECENT_MEMORIES]
        daily_text = _format_daily_memories(top_items)

        # 3. 长期记忆摘要（最近 4 条）
        long_term = await self.get_long_term_memories(
            user_id, limit=4, mongo_db=mongo_db
        )
        if long_term:
            lt_lines = [f"- [{m.period_start}~{m.period_end}] {m.summary}" for m in long_term]
            lt_text = "\n".join(lt_lines)
        else:
            lt_text = "暂无长期记忆"

        # 4. 格式化完整上下文
        formatted = MEMORY_CONTEXT_TEMPLATE.format(
            core_profile=profile_text,
            daily_memories=daily_text,
            long_term_summary=lt_text,
        )

        return MemoryContextResponse(
            core_profile=(
                UserProfileResponse.model_validate(profile) if profile else None
            ),
            recent_daily_memories=[
                MemoryItemSchema(**item) for item in top_items
            ],
            long_term_summary=lt_text if long_term else None,
            formatted_prompt=formatted,
        )

    # ── 时间线 ──────────────────────────────────────────

    async def get_memory_timeline(
        self,
        user_id: int,
        start_date: str,
        end_date: str,
        mongo_db: AsyncIOMotorDatabase | None = None,
    ) -> list[dict]:
        """获取记忆时间线。

        Args:
            user_id: 用户 ID。
            start_date: 起始日期 YYYY-MM-DD。
            end_date: 结束日期 YYYY-MM-DD。

        Returns:
            时间线条目列表。
        """
        db = mongo_db or get_mongo_db()
        entries: list[dict] = []

        # 每日记忆
        cursor = db.daily_memories.find({
            "user_id": user_id,
            "date": {"$gte": start_date, "$lte": end_date},
        }).sort("date", -1)

        async for doc in cursor:
            entries.append({
                "date": doc["date"],
                "type": "daily",
                "summary": doc.get("summary"),
                "item_count": len(doc.get("items", [])),
                "key_themes": [],
            })

        # 长期记忆
        lt_cursor = db.long_term_memories.find({
            "user_id": user_id,
            "period_start": {"$gte": start_date},
            "period_end": {"$lte": end_date},
        }).sort("period_start", -1)

        async for doc in lt_cursor:
            entries.append({
                "date": doc["period_start"],
                "type": "long_term",
                "summary": doc.get("summary"),
                "item_count": 0,
                "key_themes": doc.get("key_themes", []),
            })

        # 按日期排序
        entries.sort(key=lambda x: x["date"], reverse=True)
        return entries
