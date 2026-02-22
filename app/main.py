from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.database import close_mongo, connect_mongo
from app.routers import memory


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动/关闭时的资源初始化与清理。"""
    await connect_mongo()
    yield
    await close_mongo()


app = FastAPI(
    title="PeakState Memory System",
    description="PeakState AI 记忆系统 - 核心档案、自动记忆提取与长期记忆",
    version="0.2.0",
    lifespan=lifespan,
)

app.include_router(
    memory.router,
    prefix=f"{settings.API_PREFIX}/memory",
    tags=["memory"],
)


@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok", "service": "peakstate-memory", "version": "0.2.0"}
