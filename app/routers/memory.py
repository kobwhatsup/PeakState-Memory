"""记忆系统 API 路由。

提供核心档案（PostgreSQL）、每日记忆、长期记忆（MongoDB）
以及内部 API（记忆提取、上下文构建）的 REST 接口。
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, get_mongo_db
from app.schemas.memory import (
    DailyMemoryResponse,
    ExtractMemoryRequest,
    ExtractMemoryResponse,
    LongTermMemoryResponse,
    MemoryContextResponse,
    MemoryItemSchema,
    MemoryTimelineEntry,
    MemoryTimelineResponse,
    UserProfileResponse,
    UserProfileUpdate,
)
from app.services.memory_service import MemoryService

router = APIRouter()
memory_service = MemoryService()


# ── 核心档案 API ─────────────────────────────────────────


@router.get("/profile", response_model=UserProfileResponse)
async def get_user_profile(
    x_user_id: int = Header(..., alias="X-User-Id"),
    db: AsyncSession = Depends(get_db),
) -> UserProfileResponse:
    """获取用户核心档案。如果不存在则自动创建空档案。"""
    profile = await memory_service.get_or_create_profile(db, x_user_id)
    return UserProfileResponse.model_validate(profile)


@router.put("/profile", response_model=UserProfileResponse)
async def update_user_profile(
    profile_data: UserProfileUpdate,
    x_user_id: int = Header(..., alias="X-User-Id"),
    db: AsyncSession = Depends(get_db),
) -> UserProfileResponse:
    """更新用户核心档案。仅更新请求中包含的字段。"""
    await memory_service.get_or_create_profile(db, x_user_id)

    profile = await memory_service.update_user_profile(db, x_user_id, profile_data)
    if not profile:
        raise HTTPException(status_code=404, detail="用户档案不存在")
    return UserProfileResponse.model_validate(profile)


# ── 每日记忆 API ─────────────────────────────────────────


@router.get("/daily", response_model=DailyMemoryResponse)
async def get_daily_memory(
    x_user_id: int = Header(..., alias="X-User-Id"),
    date: str = Query(
        default=None,
        description="日期 YYYY-MM-DD，默认今天",
    ),
) -> DailyMemoryResponse:
    """获取指定日期的每日记忆。"""
    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    daily = await memory_service.get_daily_memory(x_user_id, date)
    if daily is None:
        return DailyMemoryResponse(user_id=x_user_id, date=date)
    return DailyMemoryResponse(**daily.model_dump(mode="json"))


@router.get("/daily/recent", response_model=list[DailyMemoryResponse])
async def get_recent_daily_memories(
    x_user_id: int = Header(..., alias="X-User-Id"),
    days: int = Query(default=7, ge=1, le=90, description="最近天数"),
) -> list[DailyMemoryResponse]:
    """获取最近 N 天的每日记忆。"""
    memories = await memory_service.get_recent_daily_memories(x_user_id, days=days)
    return [DailyMemoryResponse(**m.model_dump(mode="json")) for m in memories]


# ── 长期记忆 API ─────────────────────────────────────────


@router.get("/long-term", response_model=list[LongTermMemoryResponse])
async def get_long_term_memories(
    x_user_id: int = Header(..., alias="X-User-Id"),
    since: str | None = Query(default=None, description="起始日期 YYYY-MM-DD"),
    limit: int = Query(default=10, ge=1, le=50),
) -> list[LongTermMemoryResponse]:
    """获取长期记忆列表。"""
    memories = await memory_service.get_long_term_memories(
        x_user_id, since=since, limit=limit
    )
    return [LongTermMemoryResponse(**m.model_dump(mode="json")) for m in memories]


# ── 记忆时间线 API ───────────────────────────────────────


@router.get("/timeline", response_model=MemoryTimelineResponse)
async def get_memory_timeline(
    x_user_id: int = Header(..., alias="X-User-Id"),
    start: str = Query(
        default=None,
        description="起始日期 YYYY-MM-DD，默认30天前",
    ),
    end: str = Query(
        default=None,
        description="结束日期 YYYY-MM-DD，默认今天",
    ),
) -> MemoryTimelineResponse:
    """获取记忆时间线。"""
    now = datetime.now(timezone.utc)
    if end is None:
        end = now.strftime("%Y-%m-%d")
    if start is None:
        start = (now - timedelta(days=30)).strftime("%Y-%m-%d")

    entries = await memory_service.get_memory_timeline(x_user_id, start, end)
    return MemoryTimelineResponse(
        user_id=x_user_id,
        start_date=start,
        end_date=end,
        entries=[MemoryTimelineEntry(**e) for e in entries],
    )


# ── 内部 API ─────────────────────────────────────────────


@router.post("/internal/extract", response_model=ExtractMemoryResponse)
async def extract_memories(
    request: ExtractMemoryRequest,
) -> ExtractMemoryResponse:
    """从对话中提取记忆（对话结束后由系统内部调用）。"""
    items = await memory_service.extract_and_store(
        request.user_id, request.messages
    )
    return ExtractMemoryResponse(
        extracted_count=len(items),
        items=[
            MemoryItemSchema(
                category=item.category.value,
                content=item.content,
                importance=item.importance,
                source_role=item.source_role,
                extracted_at=item.extracted_at,
            )
            for item in items
        ],
    )


@router.get("/internal/context", response_model=MemoryContextResponse)
async def get_memory_context(
    user_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
) -> MemoryContextResponse:
    """获取 LLM 对话上下文（LLM 调用前获取）。

    整合核心档案 + 近期记忆 + 长期记忆，生成格式化提示词。
    """
    return await memory_service.build_context_for_llm(db, user_id)
