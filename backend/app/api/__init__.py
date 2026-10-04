from fastapi import APIRouter
from .auth import router as auth_router
from .parks import router as parks_router
from .chat import router as chat_router
from .statistics import router as stats_router
from .admin import router as admin_router
from .knowledge import router as knowledge_router
from .track import router as track_router
from .survey import router as survey_router
from .annotate import router as annotate_router
from .ai_models import router as ai_models_router
from ..kg.api import kg_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["认证"])
api_router.include_router(parks_router, prefix="/parks", tags=["遗址公园"])
api_router.include_router(chat_router, prefix="/chat", tags=["AI问答"])
api_router.include_router(stats_router, prefix="/statistics", tags=["统计分析"])
api_router.include_router(admin_router, prefix="/admin", tags=["数据管理"])
api_router.include_router(knowledge_router, prefix="/knowledge", tags=["知识库"])
api_router.include_router(track_router, prefix="/track", tags=["轨迹照片"])
api_router.include_router(survey_router, prefix="/survey", tags=["田野调研"])
api_router.include_router(annotate_router, prefix="/annotate", tags=["数据标注"])
api_router.include_router(ai_models_router, prefix="/ai", tags=["模型路由"])
api_router.include_router(kg_router, tags=["知识图谱系统"])
