from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── UserProfile Schemas ──────────────────────────────────────────


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


# ── ManualMemory Schemas ─────────────────────────────────────────


class ManualMemoryCreate(BaseModel):
    """创建手动记忆。"""

    content: str = Field(..., min_length=1, max_length=2000)
    memory_type: str = Field(default="general")
    importance_score: int = Field(default=5, ge=1, le=10)
    source: str = Field(default="user_instruction")
    source_message_id: str | None = None


class ManualMemoryResponse(BaseModel):
    """手动记忆响应。"""

    model_config = {"from_attributes": True}

    id: int
    user_id: int
    content: str
    memory_type: str
    importance_score: int
    source: str
    source_message_id: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime
    last_accessed_at: datetime | None = None
    access_count: int
    expires_at: datetime | None = None


# ── MemoryContext Schema ─────────────────────────────────────────


class MemoryContextResponse(BaseModel):
    """对话上下文记忆响应（供 LLM 调用使用）。"""

    core_profile: UserProfileResponse | None = None
    recent_memories: list[ManualMemoryResponse] = Field(default_factory=list)
    formatted_prompt: str = ""
