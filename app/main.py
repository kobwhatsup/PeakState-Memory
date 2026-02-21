from fastapi import FastAPI

from app.config import settings
from app.routers import memory

app = FastAPI(
    title="PeakState Memory System",
    description="PeakState AI 记忆系统 - 核心档案与手动记忆管理",
    version="0.1.0",
)

app.include_router(
    memory.router,
    prefix=f"{settings.API_PREFIX}/memory",
    tags=["memory"],
)


@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok", "service": "peakstate-memory"}
