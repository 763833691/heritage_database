"""田野调研事件与报告接口（挂在 /api/survey）。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.auth import get_current_user
from ..core.database import get_db
from ..models.survey import SurveyEvent, SurveyReport, SurveyTask
from ..models.track import TrackFile, TrackPhoto
from ..models.user import User
from ..services import report_service, track_service

router = APIRouter()


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    park_id: Optional[int] = None
    survey_date: Optional[str] = None


class EventPatch(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[list[str]] = None
    usable_for_report: Optional[bool] = None


class AutoTitleRequest(BaseModel):
    overwrite: bool = False


def _get_task(db: Session, task_id: int) -> SurveyTask:
    task = db.get(SurveyTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="调研任务不存在")
    return task


def _track_of(db: Session, task_id: int) -> TrackFile | None:
    return (
        db.query(TrackFile)
        .filter(TrackFile.survey_task_id == task_id)
        .order_by(TrackFile.id.desc())
        .first()
    )


def _event_payload(event: SurveyEvent, photo: Optional[TrackPhoto] = None) -> dict:
    try:
        tags = json.loads(event.tags) if event.tags else []
    except Exception:
        tags = []
    payload = {
        "id": event.id,
        "task_id": event.task_id,
        "event_type": event.event_type,
        "timestamp": event.timestamp.isoformat() if event.timestamp else None,
        "longitude": event.longitude,
        "latitude": event.latitude,
        "address": event.address,
        "title": event.title,
        "content": event.content,
        "source_material_id": event.source_material_id,
        "source_type": event.source_type,
        "tags": tags,
        "usable_for_report": bool(event.usable_for_report),
    }
    if photo is not None:
        payload["photo"] = {
            "id": photo.id,
            "file_name": photo.file_name,
            "thumb_url": f"/api/track/{photo.track_id}/photos/{photo.id}?thumb=true",
            "url": f"/api/track/{photo.track_id}/photos/{photo.id}",
            "download_status": photo.download_status,
            "describe_status": photo.describe_status,
        }
    return payload


def _photo_map(db: Session, events: list[SurveyEvent]) -> dict[int, TrackPhoto]:
    ids = [event.source_material_id for event in events if event.source_type == "track_photo" and event.source_material_id]
    if not ids:
        return {}
    return {photo.id: photo for photo in db.query(TrackPhoto).filter(TrackPhoto.id.in_(ids)).all()}


def _task_payload(db: Session, task: SurveyTask) -> dict:
    track = _track_of(db, task.id)
    events = db.query(SurveyEvent).filter(SurveyEvent.task_id == task.id).all()
    report = (
        db.query(SurveyReport)
        .filter(SurveyReport.task_id == task.id, SurveyReport.chapter == report_service.CHAPTER_KEY)
        .first()
    )
    return {
        "id": task.id,
        "title": task.title,
        "park_id": task.park_id,
        "survey_date": task.survey_date,
        "status": task.status,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "event_count": len(events),
        "usable_event_count": sum(1 for event in events if event.usable_for_report),
        "track_id": track.id if track else None,
        "track_status": track.status if track else None,
        "photo_count": track.photo_count if track else 0,
        "report_status": report.status if report else "empty",
        "report_version": report.version if report else 0,
    }


@router.post("/tasks")
def create_task(payload: TaskCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    task = SurveyTask(title=payload.title.strip(), park_id=payload.park_id, survey_date=payload.survey_date)
    db.add(task)
    db.commit()
    db.refresh(task)
    return _task_payload(db, task)


@router.get("/tasks")
def list_tasks(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    tasks = db.query(SurveyTask).order_by(SurveyTask.id.desc()).all()
    return {"items": [_task_payload(db, task) for task in tasks]}


@router.get("/tasks/{task_id}")
def get_task(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    task = _get_task(db, task_id)
    payload = _task_payload(db, task)
    track = _track_of(db, task_id)
    if track is not None:
        payload["track"] = {
            "id": track.id,
            "original_name": track.original_name,
            "status": track.status,
            "stage": track.stage,
            "progress_done": track.progress_done,
            "progress_total": track.progress_total,
            "track_point_count": track.track_point_count,
            "photo_count": track.photo_count,
            "start_time": track.start_time.isoformat() if track.start_time else None,
            "end_time": track.end_time.isoformat() if track.end_time else None,
            "error_message": track.error_message,
        }
    else:
        payload["track"] = None
    return payload


@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """删除调研任务，并同步清理其关联轨迹（避免外键悬空与磁盘残留）。"""
    task = _get_task(db, task_id)
    track = _track_of(db, task_id)
    if track is not None:
        db.query(TrackPhoto).filter(TrackPhoto.track_id == track.id).delete(synchronize_session=False)
        db.delete(track)
        db.commit()
        track_service.delete_track_storage(track.id)
    db.delete(task)
    db.commit()
    report_service.delete_task_reports(task_id)
    return {"deleted": task_id}


@router.get("/tasks/{task_id}/events")
def list_events(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _get_task(db, task_id)
    events = (
        db.query(SurveyEvent)
        .filter(SurveyEvent.task_id == task_id)
        .order_by(SurveyEvent.timestamp.asc().nullslast(), SurveyEvent.id.asc())
        .all()
    )
    photos = _photo_map(db, events)
    return {"items": [_event_payload(event, photos.get(event.source_material_id)) for event in events]}


@router.patch("/events/{event_id}")
def update_event(
    event_id: int,
    payload: EventPatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    event = db.get(SurveyEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="调研事件不存在")
    if payload.title is not None:
        event.title = payload.title
    if payload.content is not None:
        event.content = payload.content
    if payload.tags is not None:
        event.tags = json.dumps(payload.tags, ensure_ascii=False)
    if payload.usable_for_report is not None:
        event.usable_for_report = payload.usable_for_report
    db.commit()
    photos = _photo_map(db, [event])
    return _event_payload(event, photos.get(event.source_material_id))


@router.post("/tasks/{task_id}/events/auto-title")
async def auto_title_events(
    task_id: int,
    payload: AutoTitleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """结合调研主题，用文本大模型为时间线事件批量生成标题。"""
    _get_task(db, task_id)
    try:
        result = await track_service.auto_title_events(db, task_id, overwrite=payload.overwrite)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 - 模型调用失败按上游错误返回
        raise HTTPException(status_code=502, detail=f"标题生成失败：{exc}")

    events = (
        db.query(SurveyEvent)
        .filter(SurveyEvent.task_id == task_id)
        .order_by(SurveyEvent.timestamp.asc().nullslast(), SurveyEvent.id.asc())
        .all()
    )
    photos = _photo_map(db, events)
    return {
        **result,
        "items": [_event_payload(event, photos.get(event.source_material_id)) for event in events],
    }


@router.get("/tasks/{task_id}/timeline")
def task_timeline(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """按小时聚合的时间线线索数据，供前端时间线视图使用。"""
    _get_task(db, task_id)
    events = (
        db.query(SurveyEvent)
        .filter(SurveyEvent.task_id == task_id)
        .order_by(SurveyEvent.timestamp.asc().nullslast(), SurveyEvent.id.asc())
        .all()
    )
    photos = _photo_map(db, events)
    buckets: dict[str, dict] = {}
    for event in events:
        key = event.timestamp.strftime("%Y-%m-%dT%H:00") if event.timestamp else "unknown"
        bucket = buckets.setdefault(key, {"hour": key, "count": 0, "usable_count": 0, "events": []})
        bucket["count"] += 1
        if event.usable_for_report:
            bucket["usable_count"] += 1
        bucket["events"].append(_event_payload(event, photos.get(event.source_material_id)))
    return {"items": list(buckets.values())}


@router.post("/tasks/{task_id}/report/chapter2")
def generate_chapter2(
    task_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_task(db, task_id)
    report = report_service.get_or_create_report(db, task_id)
    report.status = "generating"
    report.error_message = None
    db.commit()
    background_tasks.add_task(report_service.run_chapter2_generation, task_id)
    return report_service.report_payload(report)


@router.get("/tasks/{task_id}/report")
def get_report(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _get_task(db, task_id)
    report = (
        db.query(SurveyReport)
        .filter(SurveyReport.task_id == task_id, SurveyReport.chapter == report_service.CHAPTER_KEY)
        .first()
    )
    return report_service.report_payload(report)


@router.get("/tasks/{task_id}/report.docx")
def download_report(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _get_task(db, task_id)
    report = (
        db.query(SurveyReport)
        .filter(SurveyReport.task_id == task_id, SurveyReport.chapter == report_service.CHAPTER_KEY)
        .first()
    )
    if report is None or not report.docx_path or not Path(report.docx_path).exists():
        raise HTTPException(status_code=404, detail="报告尚未生成")
    return FileResponse(
        report.docx_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"调研报告_第二章_{task_id}.docx",
    )
