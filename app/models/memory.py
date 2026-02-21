from datetime import datetime

from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


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


class ManualMemory(Base):
    """手动记忆模型。

    存储用户通过 "楷，请记住..." 等指令主动告知的信息，
    按重要性评分排序后注入 AI 对话上下文。
    """

    __tablename__ = "manual_memories"
    __table_args__ = (
        CheckConstraint(
            "importance_score BETWEEN 1 AND 10",
            name="check_importance_score",
        ),
        Index("idx_manual_memories_user_id", "user_id"),
        Index("idx_manual_memories_status", "status"),
        Index("idx_manual_memories_created_at", "created_at", postgresql_using="btree"),
        Index(
            "idx_manual_memories_importance",
            "importance_score",
            postgresql_using="btree",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # 记忆内容
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # 记忆类型: general, preference, goal, health, event, relationship
    memory_type: Mapped[str] = mapped_column(
        String(50), server_default="'general'"
    )

    # 重要性评分 1-10
    importance_score: Mapped[int] = mapped_column(Integer, server_default="5")

    # 来源
    source: Mapped[str] = mapped_column(
        String(100), server_default="'user_instruction'"
    )
    source_message_id: Mapped[str | None] = mapped_column(String(100))

    # 状态: active, archived, deleted
    status: Mapped[str] = mapped_column(String(20), server_default="'active'")

    # 元数据
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    access_count: Mapped[int] = mapped_column(Integer, server_default="0")

    # 过期时间
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
