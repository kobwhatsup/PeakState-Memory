from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── UserProfile（核心档案）Schemas ───────────────────────


class UserProfileCreate(BaseModel):
    """创建用户核心档案。"""

    user_id: int
    nickname: str | None = None
    gender: str | None = None
    age_range: str | None = None
    occupation: str | None = None
    family_role: list[str] | None = None
    core_goals: list[Any] | None = Field(default_factory=list)
    core_values: list[Any] | None = Field(default_factory=list)
    health_info: dict[str, Any] | None = Field(default_factory=dict)
    important_dates: list[Any] | None = Field(default_factory=list)
    preferences: dict[str, Any] | None = Field(default_factory=dict)


class UserProfileUpdate(BaseModel):
    """更新用户核心档案（所有字段可选）。"""

    nickname: str | None = None
    gender: str | None = None
    age_range: str | None = None
    occupation: str | None = None
    family_role: list[str] | None = None
    core_goals: list[Any] | None = None
    core_values: list[Any] | None = None
    health_info: dict[str, Any] | None = None
    important_dates: list[Any] | None = None
    preferences: dict[str, Any] | None = None


class UserProfileResponse(BaseModel):
    """用户核心档案响应。"""

    model_config = {"from_attributes": True}

    id: int
    user_id: int
    nickname: str | None = None
    gender: str | None = None
    age_range: str | None = None
    occupation: str | None = None
    family_role: list[str] | None = None
    core_goals: list[Any] | None = None
    core_values: list[Any] | None = None
    health_info: dict[str, Any] | None = None
    important_dates: list[Any] | None = None
    preferences: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
    version: int


# ── DailyMemory（每日记忆）Schemas ──────────────────────


class MemoryItemSchema(BaseModel):
    """单条记忆项 Schema。"""

    category: str = "general"
    content: str
    importance: int = Field(default=5, ge=1, le=10)
    source_role: str = "user"
    extracted_at: datetime | None = None


class DailyMemoryResponse(BaseModel):
    """每日记忆响应。"""

    user_id: int
    date: str
    items: list[MemoryItemSchema] = Field(default_factory=list)
    summary: str | None = None
    conversation_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ── LongTermMemory（长期记忆）Schemas ───────────────────


class LongTermMemoryResponse(BaseModel):
    """长期记忆响应。"""

    user_id: int
    period_type: str
    period_start: str
    period_end: str
    summary: str
    key_themes: list[str] = Field(default_factory=list)
    notable_changes: list[str] = Field(default_factory=list)
    emotional_trend: str | None = None
    created_at: datetime | None = None


# ── 时间线 Schema ──────────────────────────────────────


class MemoryTimelineEntry(BaseModel):
    """时间线中的单条记录。"""

    date: str
    type: str = Field(description="daily 或 long_term")
    summary: str | None = None
    item_count: int = 0
    key_themes: list[str] = Field(default_factory=list)


class MemoryTimelineResponse(BaseModel):
    """记忆时间线响应。"""

    user_id: int
    start_date: str
    end_date: str
    entries: list[MemoryTimelineEntry] = Field(default_factory=list)


# ── 内部 API Schemas ──────────────────────────────────


class ExtractMemoryRequest(BaseModel):
    """记忆提取请求（对话结束后触发）。"""

    user_id: int
    messages: list[dict[str, str]] = Field(
        description="对话消息列表，每项包含 role 和 content"
    )


class ExtractMemoryResponse(BaseModel):
    """记忆提取响应。"""

    extracted_count: int = 0
    items: list[MemoryItemSchema] = Field(default_factory=list)


class MemoryContextResponse(BaseModel):
    """对话上下文记忆响应（供 LLM 调用使用）。"""

    core_profile: UserProfileResponse | None = None
    recent_daily_memories: list[MemoryItemSchema] = Field(default_factory=list)
    long_term_summary: str | None = None
    formatted_prompt: str = ""
