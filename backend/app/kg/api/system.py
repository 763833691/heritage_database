from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.kg.response import ok
from app.kg.services.file_service import file_service
from app.kg.services.job_recovery import recover_interrupted_work
from app.kg.services.graph_repository import graph_repository

router = APIRouter()


@router.get("/status")
async def system_status():
    graph = await graph_repository.full_graph()
    files = await file_service.list_files()
    storage_mode = "neo4j" if settings.neo4j_enabled else "local"
    return ok(
        {
            "storage_mode": storage_mode,
            "neo4j_enabled": settings.neo4j_enabled,
            "mock_enabled": settings.mock_graph_enabled,
            "graph_nodes": len(graph.nodes),
            "graph_edges": len(graph.edges),
            "file_count": len(files),
            "max_upload_mb": settings.max_upload_size // (1024 * 1024),
        }
    )


@router.post("/recover-interrupted")
async def recover_interrupted():
    result = await recover_interrupted_work()
    return ok(result)
