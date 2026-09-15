from fastapi import APIRouter

from app.kg.api import asr, file, graph, nlp, process, system

kg_router = APIRouter()
kg_router.include_router(file.router, prefix="/file", tags=["知识图谱-文件库"])
kg_router.include_router(process.router, prefix="/process", tags=["知识图谱-处理流程"])
kg_router.include_router(graph.router, prefix="/graph", tags=["知识图谱-图谱数据"])
kg_router.include_router(nlp.router, prefix="/nlp", tags=["知识图谱-实体关系抽取"])
kg_router.include_router(system.router, prefix="/system", tags=["知识图谱-系统状态"])
kg_router.include_router(asr.router, prefix="/asr", tags=["知识图谱-语音转写"])
