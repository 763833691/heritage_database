from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks

from app.kg.response import ok
from app.kg.schemas import BatchProcessRequest, GraphBuildRequest
from app.kg.services.file_service import file_service
from app.kg.services.process_service import process_service
from app.kg.services.text_parse_pipeline import text_parse_pipeline
from app.kg.services.workflow_helper import text_parse_ready

router = APIRouter()


@router.post("/{file_id}")
async def start_process(file_id: str, background_tasks: BackgroundTasks):
    await file_service.get_file(file_id)
    await file_service.update_status(file_id, "processing", 5, "文本解析", "已进入文本解析队列")
    background_tasks.add_task(process_service.run_text_parse, file_id)
    return ok({"status": "processing", "phase": "text_parse"})


@router.post("/{file_id}/confirm-text-parse")
async def confirm_text_parse(file_id: str):
    item = await file_service.get_file(file_id)
    if not text_parse_ready(item):
        return ok({"status": "blocked", "message": "请先完成文本解析"}, code=1)
    item = await file_service.confirm_text_parse(file_id)
    return ok({"status": "confirmed", "workflow_phase": item.process_status.workflow_phase})


@router.post("/{file_id}/graph-build/run")
async def run_graph_build(file_id: str, payload: GraphBuildRequest, background_tasks: BackgroundTasks):
    await file_service.get_file(file_id)
    background_tasks.add_task(process_service.run_graph_build, file_id, payload.method)
    return ok({"status": "processing", "phase": "graph_build", "method": payload.method})


@router.post("/{file_id}/export/run")
async def run_export(file_id: str, background_tasks: BackgroundTasks):
    item = await file_service.get_file(file_id)
    if not item.process_result:
        return ok({"status": "blocked", "message": "请先完成图谱构建"}, code=1)

    async def export_job() -> None:
        await process_service.run_export(file_id)

    background_tasks.add_task(export_job)
    return ok({"status": "processing", "phase": "export"})


@router.get("/{file_id}/status")
async def get_process_status(file_id: str):
    item = await file_service.get_file(file_id)
    return ok(item.process_status.model_dump(mode="json"), code=2 if item.status == "processing" else 0)


@router.get("/{file_id}/result")
async def get_process_result(file_id: str):
    item = await file_service.get_file(file_id)
    result = item.process_result
    if result is None:
        return ok({"entities": [], "relations": [], "graph": {"nodes": [], "edges": []}})
    return ok(result.model_dump(mode="json"))


@router.get("/{file_id}/text-pipeline")
async def get_text_pipeline_status(file_id: str):
    status = await text_parse_pipeline.get_status(file_id)
    return ok(status)


@router.get("/{file_id}/text-preview")
async def get_text_preview(file_id: str):
    preview = await text_parse_pipeline.get_preview(file_id)
    return ok(preview)


@router.post("/{file_id}/text-pipeline/run")
async def run_text_pipeline(file_id: str, background_tasks: BackgroundTasks):
    await file_service.get_file(file_id)
    background_tasks.add_task(process_service.run_text_parse, file_id)
    return ok({"status": "processing", "phase": "text_parse"})


@router.post("/{file_id}/rerun")
async def rerun_process(file_id: str, background_tasks: BackgroundTasks):
    await file_service.get_file(file_id)
    await file_service.reset_for_rerun(file_id)
    await file_service.update_status(file_id, "processing", 5, "文本解析", "已重置，重新进入文本解析队列")
    background_tasks.add_task(process_service.run_text_parse, file_id)
    return ok({"status": "processing", "phase": "text_parse"})


@router.post("/batch-run")
async def batch_run(payload: BatchProcessRequest, background_tasks: BackgroundTasks):
    if not payload.file_ids:
        return ok({"status": "empty", "message": "未选择任何文献"})
    background_tasks.add_task(process_service.process_batch, payload.file_ids, payload.mode)
    return ok({"status": "queued", "count": len(payload.file_ids), "mode": payload.mode})
