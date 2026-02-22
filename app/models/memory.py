from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field
from sqlalchemy import (
    ARRAY,
    DateTime,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


# ── PostgreSQL ORM 模型 ──────────────────────────────────


class UserProfile(Base):
    """用户核心档案模型。

    存储用户的基本信息、核心目标、健康信息等结构化数据，
    在 AI 对话时作为上下文注入。
    """

    __tablename__ = "user_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_profiles_user_id"),
        Index("idx_user_profiles_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # 基本信息
    nickname: Mapped[str | None] = mapped_column(String(100))
    gender: Mapped[str | None] = mapped_column(String(20))
    age_range: Mapped[str | None] = mapped_column(String(20))
    occupation: Mapped[str | None] = mapped_column(String(200))
    family_role: Mapped[list[str] | None] = mapped_column(ARRAY(String))

    # 核心目标与价值观
    core_goals: Mapped[dict | None] = mapped_column(
        JSONB, server_default="'[]'::jsonb"
    )
    core_values: Mapped[dict | None] = mapped_column(
        JSONB, server_default="'[]'::jsonb"
    )

    # 健康信息
    health_info: Mapped[dict | None] = mapped_column(
        JSONB, server_default="'{}'::jsonb"
    )

    # 重要日期
    important_dates: Mapped[dict | None] = mapped_column(
        JSONB, server_default="'[]'::jsonb"
    )

    # 个人偏好
    preferences: Mapped[dict | None] = mapped_column(
        JSONB, server_default="'{}'::jsonb"
    )

    # 元数据
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    version: Mapped[int] = mapped_column(Integer, server_default="1")


# ── MongoDB 文档模型 ─────────────────────────────────────


class MemoryCategory(str, Enum):
    """记忆分类枚举。"""

    PREFERENCE = "preference"
    GOAL = "goal"
    HEALTH = "health"
    EVENT = "event"
    RELATIONSHIP = "relationship"
    EMOTION = "emotion"
    INSIGHT = "insight"
    GENERAL = "general"


class MemoryItem(BaseModel):
    """单条记忆项（嵌入在 DailyMemory 中）。"""

    category: MemoryCategory = MemoryCategory.GENERAL
    content: str
    importance: int = Field(default=5, ge=1, le=10)
    source_role: str = Field(default="user", description="消息来源: user 或 assistant")
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DailyMemory(BaseModel):
    """每日记忆文档模型（MongoDB: daily_memories 集合）。

    每个用户每天一份文档，包含当天从对话中提取的所有记忆项。
    """

    user_id: int
    date: str = Field(description="日期字符串 YYYY-MM-DD")
    items: list[MemoryItem] = Field(default_factory=list)
    summary: str | None = Field(
        default=None, description="当天记忆摘要（每晚生成）"
    )
    conversation_count: int = Field(default=0, description="当天对话轮数")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LongTermMemory(BaseModel):
    """长期记忆文档模型（MongoDB: long_term_memories 集合）。

    对 DailyMemory 的周/月级别汇总，保留关键模式和变化趋势。
    """

    user_id: int
    period_type: str = Field(description="周期类型: weekly 或 monthly")
    period_start: str = Field(description="周期起始日期 YYYY-MM-DD")
    period_end: str = Field(description="周期结束日期 YYYY-MM-DD")
    summary: str = Field(description="周期总结")
    key_themes: list[str] = Field(default_factory=list, description="关键主题")
    notable_changes: list[str] = Field(
        default_factory=list, description="显著变化"
    )
    emotional_trend: str | None = Field(
        default=None, description="情绪趋势描述"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
