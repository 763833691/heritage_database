"""照片语义标注工作台接口（挂在 /api/annotate）。"""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.auth import get_current_user
from ..core.database import get_db
from ..models.annotation import AnnotationItem
from ..models.user import User
from ..services import annotation_service

router = APIRouter()


class ImportPayload(BaseModel):
    name: str | None = None
    sample_path: str = "data/annotation/sample_v1.json"


class CodePayload(BaseModel):
    coder: str
    code: str
    note: str | None = ""


def _get_task_or_404(db: Session, task_id: int):
    task = annotation_service.get_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="标注任务不存在")
    return task


@router.post("/tasks/import")
def import_task(
    payload: ImportPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """从样本 JSON 导入标注任务；同名任务已存在时返回既有任务（幂等）。"""
    try:
        task, created = annotation_service.import_task(db, payload.name, payload.sample_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 - 样本格式错误
        raise HTTPException(status_code=400, detail=f"样本导入失败：{exc}")
    summary = annotation_service._task_summary(db, task)
    summary["created"] = created
    return summary


@router.get("/tasks")
def list_tasks(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return {"items": annotation_service.list_tasks(db)}


@router.get("/tasks/{task_id}/next")
def next_item(
    task_id: int,
    coder: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """取下一张待标（盲标）：响应不包含 platform_type / ai_code / caption。"""
    _get_task_or_404(db, task_id)
    return annotation_service.next_item(db, task_id, coder.strip())


@router.post("/items/{item_id}/code")
def submit_code(
    item_id: int,
    payload: CodePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """提交编码；同 (item, coder) 覆盖更新。"""
    try:
        record = annotation_service.submit_code(db, item_id, payload.coder, payload.code, payload.note or "")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    item = db.get(AnnotationItem, item_id)
    progress = annotation_service._progress(db, item.task_id, record.coder) if item else None
    return {
        "item_id": item_id,
        "coder": record.coder,
        "code": record.code,
        "note": record.note,
        "progress": progress,
    }


@router.get("/items/{item_id}/photo-meta")
def photo_meta(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """盲标页照片元信息：仅返回 {sid, photo_url}。"""
    try:
        return annotation_service.photo_meta(db, item_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/tasks/{task_id}/results")
def task_results(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_task_or_404(db, task_id)
    return annotation_service.results(db, task_id)


@router.get("/tasks/{task_id}/export")
def export_results(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = _get_task_or_404(db, task_id)
    content = annotation_service.build_xlsx(db, task_id)
    filename = f"{task.name}_标注结果.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename=\"annotation.xlsx\"; filename*=UTF-8''{quote(filename)}"
        },
    )
