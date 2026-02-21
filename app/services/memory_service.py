from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.memory import ManualMemory, UserProfile
from app.schemas.memory import (
    ManualMemoryCreate,
    ManualMemoryResponse,
    MemoryContextResponse,
    UserProfileCreate,
    UserProfileResponse,
    UserProfileUpdate,
)


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


def _format_recent_memories(memories: list[ManualMemory]) -> str:
    """将最近记忆格式化为 LLM 可读的提示词文本。"""
    if not memories:
        return "暂无记忆记录"

    lines: list[str] = []
    now = datetime.now(timezone.utc)

    for mem in memories:
        created = mem.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        delta = now - created
        if delta.days == 0:
            time_label = "今天"
        elif delta.days == 1:
            time_label = "昨天"
        elif delta.days < 7:
            time_label = f"{delta.days}天前"
        else:
            time_label = f"{delta.days // 7}周前"

        lines.append(f"- [{time_label}] {mem.content}")

    return "\n".join(lines)


MEMORY_CONTEXT_TEMPLATE = """# 用户核心信息
{core_profile}

# 最近的重要记忆
{recent_memories}

请在回复中自然地使用这些信息，而不是生硬地复述。"""


class MemoryService:
    """记忆管理核心服务。"""

    # ── 核心档案 ──────────────────────────────────────────

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

    # ── 手动记忆 ──────────────────────────────────────────

    async def create_manual_memory(
        self,
        db: AsyncSession,
        user_id: int,
        memory_data: ManualMemoryCreate,
    ) -> ManualMemory:
        """创建手动记忆。"""
        memory = ManualMemory(
            user_id=user_id,
            **memory_data.model_dump(),
        )
        db.add(memory)
        await db.flush()
        await db.refresh(memory)
        return memory

    async def get_recent_memories(
        self,
        db: AsyncSession,
        user_id: int,
        limit: int | None = None,
        status: str = "active",
    ) -> list[ManualMemory]:
        """获取用户最近的手动记忆，按重要性和时间排序。"""
        if limit is None:
            limit = settings.MAX_RECENT_MEMORIES

        result = await db.execute(
            select(ManualMemory)
            .where(
                ManualMemory.user_id == user_id,
                ManualMemory.status == status,
            )
            .order_by(
                ManualMemory.importance_score.desc(),
                ManualMemory.created_at.desc(),
            )
            .limit(limit)
        )
        return list(result.scalars().all())

    async def delete_memory(
        self, db: AsyncSession, memory_id: int, user_id: int
    ) -> bool:
        """软删除记忆（将状态设为 deleted）。"""
        result = await db.execute(
            update(ManualMemory)
            .where(
                ManualMemory.id == memory_id,
                ManualMemory.user_id == user_id,
            )
            .values(status="deleted", updated_at=datetime.now(timezone.utc))
        )
        return result.rowcount > 0

    # ── 对话上下文 ────────────────────────────────────────

    async def get_conversation_context(
        self, db: AsyncSession, user_id: int
    ) -> MemoryContextResponse:
        """获取对话上下文：核心档案 + 最近记忆 + 格式化提示词。"""
        profile = await self.get_user_profile(db, user_id)
        memories = await self.get_recent_memories(db, user_id)

        # 更新访问计数
        for mem in memories:
            mem.access_count += 1
            mem.last_accessed_at = datetime.now(timezone.utc)

        # 格式化提示词
        profile_text = _format_core_profile(profile) if profile else "暂无核心档案信息"
        memories_text = _format_recent_memories(memories)
        formatted = MEMORY_CONTEXT_TEMPLATE.format(
            core_profile=profile_text,
            recent_memories=memories_text,
        )

        return MemoryContextResponse(
            core_profile=UserProfileResponse.model_validate(profile) if profile else None,
            recent_memories=[ManualMemoryResponse.model_validate(m) for m in memories],
            formatted_prompt=formatted,
        )
