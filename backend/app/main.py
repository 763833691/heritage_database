from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import text

from .core.config import settings
from .core.database import engine, Base
from .api import api_router
from .kg.services.file_service import file_service
from .kg.services.graph_repository import graph_repository
from .kg.services.job_recovery import recover_interrupted_work


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 注意：数据库表创建由 scripts/init_db.py 负责
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("[OK] Database connection verified")
    except Exception as e:
        print(f"[WARN] Database connection failed: {e}")

    # 知识图谱子系统：文件库状态、图谱仓库与中断任务恢复
    try:
        await file_service.init()
        await recover_interrupted_work()
        await graph_repository.init()
        print(f"[OK] Knowledge graph subsystem ready (storage: {settings.storage_dir})")
    except Exception as e:
        print(f"[WARN] Knowledge graph subsystem init failed: {e}")

    yield

    try:
        await graph_repository.close()
    except Exception:
        pass
    print("[INFO] Application shutdown")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="国家考古遗址公园智能研究平台API",
    lifespan=lifespan,
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(api_router, prefix="/api")


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
