from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.memory import (
    ManualMemoryCreate,
    ManualMemoryResponse,
    MemoryContextResponse,
    UserProfileCreate,
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
    # 确保档案存在
    await memory_service.get_or_create_profile(db, x_user_id)

    profile = await memory_service.update_user_profile(db, x_user_id, profile_data)
    if not profile:
        raise HTTPException(status_code=404, detail="用户档案不存在")
    return UserProfileResponse.model_validate(profile)


# ── 手动记忆 API ─────────────────────────────────────────


@router.post("/manual", response_model=ManualMemoryResponse, status_code=201)
async def create_manual_memory(
    memory_data: ManualMemoryCreate,
    x_user_id: int = Header(..., alias="X-User-Id"),
    db: AsyncSession = Depends(get_db),
) -> ManualMemoryResponse:
    """创建一条手动记忆。"""
    memory = await memory_service.create_manual_memory(db, x_user_id, memory_data)
    return ManualMemoryResponse.model_validate(memory)


@router.get("/manual/recent", response_model=list[ManualMemoryResponse])
async def get_recent_memories(
    x_user_id: int = Header(..., alias="X-User-Id"),
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> list[ManualMemoryResponse]:
    """获取用户最近的手动记忆列表。"""
    memories = await memory_service.get_recent_memories(db, x_user_id, limit=limit)
    return [ManualMemoryResponse.model_validate(m) for m in memories]


@router.delete("/manual/{memory_id}")
async def delete_manual_memory(
    memory_id: int,
    x_user_id: int = Header(..., alias="X-User-Id"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """删除一条手动记忆（软删除）。"""
    deleted = await memory_service.delete_memory(db, memory_id, x_user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="记忆不存在或无权删除")
    return {"success": True}


# ── 记忆上下文 API（内部使用） ────────────────────────────


@router.get("/context", response_model=MemoryContextResponse)
async def get_memory_context(
    user_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
) -> MemoryContextResponse:
    """获取对话上下文记忆（供 LLM 服务内部调用）。

    返回核心档案 + 最近记忆 + 格式化的提示词文本。
    """
    return await memory_service.get_conversation_context(db, user_id)
