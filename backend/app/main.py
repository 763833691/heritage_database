from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import text

from .core.config import settings
from .core.database import engine, Base
from .api import api_router
from . import models  # noqa: F401 - 注册全部模型，便于启动时补齐缺失表
from .kg.services.file_service import file_service
from .kg.services.graph_repository import graph_repository
from .kg.services.job_recovery import recover_interrupted_work
from .services.track_service import recover_interrupted_tracks
from .services.report_service import recover_interrupted_reports
from .core.model_router import describe_routes, validate_routes


def _ensure_new_columns() -> None:
    """SQLite 轻量迁移：create_all 不会给既有表补列，这里按需 ALTER（幂等）。"""
    if engine.dialect.name != "sqlite":
        return
    migrations = {
        "parks": {
            "cover_image": "VARCHAR(300)",
            "cover_source": "VARCHAR(200)",
        },
    }
    with engine.begin() as conn:
        for table, columns in migrations.items():
            existing = {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")}
            for name, ddl in columns.items():
                if existing and name not in existing:
                    conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # scripts/init_db.py 负责初始数据；启动时补齐缺失表（create_all 幂等，不改动既有表）
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        Base.metadata.create_all(bind=engine)
        _ensure_new_columns()
        print("[OK] Database connection verified (schema ensured)")
    except Exception as e:
        print(f"[WARN] Database connection failed: {e}")

    # 田野调研：恢复因服务重启而中断的轨迹处理与报告生成
    try:
        stale_tracks = recover_interrupted_tracks()
        stale_reports = recover_interrupted_reports()
        if stale_tracks or stale_reports:
            print(f"[INFO] Recovered interrupted survey work: {stale_tracks} tracks, {stale_reports} reports")
    except Exception as e:
        print(f"[WARN] Survey recovery failed: {e}")

    # AI 模型路由：播种预置模型，并输出解析结果与配置问题
    try:
        if settings.AI_MODEL_SEED_PRESETS:
            from .core.database import SessionLocal
            from .services.ai_model_service import seed_presets

            db = SessionLocal()
            try:
                created = seed_presets(db)
                if created:
                    print(f"[INFO] Seeded {created} preset AI models")
            finally:
                db.close()

        for issue in validate_routes():
            print(f"[WARN] Model route: {issue}")
        for route in describe_routes():
            if route["error"]:
                print(f"[WARN] Model route {route['task']}: {route['error']}")
            elif route["alias"]:
                print(
                    f"[INFO] Model route {route['task']} -> {route['alias']} "
                    f"({route['model']} @ {route['base_url']}, source={route['source']})"
                )
    except Exception as e:
        print(f"[WARN] Model route validation failed: {e}")

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
