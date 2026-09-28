"""田野调研：KML 轨迹上传、处理进度、照片语义与导出接口（挂在 /api/track）。"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from ..core.auth import get_current_user
from ..core.config import settings
from ..core.database import get_db
from ..models.park import Park
from ..models.survey import SurveyEvent, SurveyReport, SurveyTask
from ..models.track import TrackFile, TrackPhoto
from ..models.user import User
from ..services import report_service, semantic_analysis, track_service

router = APIRouter()

_UPLOAD_CHUNK = 1024 * 1024

# 照片 id -> 语义编码的内存缓存：{track_id: (analysis.json mtime, {photo_id: code})}
_ANALYSIS_CODE_CACHE: dict[int, tuple[float, dict[int, str]]] = {}


def _track_code_map(track_id: int) -> dict[int, str] | None:
    """读取已持久化的语义分析结果，返回 照片id -> A–F 编码；缺失或损坏返回 None。"""
    path = semantic_analysis.analysis_path(track_id)
    if not path.exists():
        return None
    mtime = path.stat().st_mtime
    cached = _ANALYSIS_CODE_CACHE.get(track_id)
    if cached and cached[0] == mtime:
        return cached[1]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        mapping = {
            int(item["id"]): item.get("type")
            for item in data.get("photos", [])
            if item.get("id") is not None
        }
    except Exception:  # noqa: BLE001 - 分析文件损坏时回退为即时计算
        return None
    _ANALYSIS_CODE_CACHE[track_id] = (mtime, mapping)
    return mapping


def _photo_semantic_code(track_id: int, photo: TrackPhoto, mapping: dict[int, str] | None) -> str:
    """优先取持久化分析编码，缺失时按同一编码表即时计算。"""
    if mapping and photo.id in mapping and mapping[photo.id]:
        return mapping[photo.id]
    return semantic_analysis.classify_text(semantic_analysis.photo_text(photo))


def _parse_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
        return value if isinstance(value, list) else []
    except Exception:  # noqa: BLE001
        return []


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _track_park_rows(db: Session) -> dict[int, dict]:
    """一次查询得到 轨迹id -> 关联公园（经调研任务）信息。"""
    rows = (
        db.query(TrackFile.id, SurveyTask.park_id, Park.id, Park.short_name, Park.name)
        .outerjoin(SurveyTask, TrackFile.survey_task_id == SurveyTask.id)
        .outerjoin(Park, SurveyTask.park_id == Park.id)
        .all()
    )
    result: dict[int, dict] = {}
    for track_id, task_park_id, park_id, short_name, name in rows:
        result[track_id] = {
            "park_id": park_id if park_id is not None else task_park_id,
            "park_name": (short_name or name) if park_id is not None else None,
        }
    return result


def _photo_payload(photo: TrackPhoto) -> dict:
    return {
        "id": photo.id,
        "seq": photo.seq,
        "file_name": photo.file_name,
        "shot_time": photo.shot_time.isoformat() if photo.shot_time else None,
        "longitude": photo.longitude,
        "latitude": photo.latitude,
        "altitude": photo.altitude,
        "speed": photo.speed,
        "accuracy": photo.accuracy,
        "province": photo.province,
        "city": photo.city,
        "district": photo.district,
        "street": photo.street,
        "poi": photo.poi,
        "address": photo.address,
        "description": photo.description,
        "caption": photo.caption,
        "tags": photo.tags,
        "download_status": photo.download_status,
        "describe_status": photo.describe_status,
        "error_message": photo.error_message,
        "thumb_url": f"/api/track/{photo.track_id}/photos/{photo.id}?thumb=true",
        "url": f"/api/track/{photo.track_id}/photos/{photo.id}",
    }


def _track_summary(track: TrackFile) -> dict:
    return {
        "id": track.id,
        "original_name": track.original_name,
        "survey_task_id": track.survey_task_id,
        "status": track.status,
        "stage": track.stage,
        "progress_done": track.progress_done,
        "progress_total": track.progress_total,
        "track_point_count": track.track_point_count,
        "photo_count": track.photo_count,
        "distance_meters": track.distance_meters,
        "start_time": track.start_time.isoformat() if track.start_time else None,
        "end_time": track.end_time.isoformat() if track.end_time else None,
        "start_address": track.start_address,
        "end_address": track.end_address,
        "created_at": track.created_at.isoformat() if track.created_at else None,
    }


def _get_track(db: Session, track_id: int) -> TrackFile:
    track = db.get(TrackFile, track_id)
    if track is None:
        raise HTTPException(status_code=404, detail="轨迹文件不存在")
    return track


@router.post("/upload")
async def upload_kml(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    survey_task_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """上传两步路 KML 文件（上限 50MB），返回 track_id 并异步处理。"""
    filename = Path(file.filename or "track.kml").name
    if not filename.lower().endswith(".kml"):
        raise HTTPException(status_code=400, detail="仅支持 .kml 文件")

    max_size = settings.track_max_upload_size
    if file.size is not None and file.size > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"文件超过大小限制（最大 {settings.TRACK_MAX_UPLOAD_MB} MB）",
        )

    chunks = bytearray()
    while True:
        chunk = await file.read(_UPLOAD_CHUNK)
        if not chunk:
            break
        chunks.extend(chunk)
        if len(chunks) > max_size:
            raise HTTPException(
                status_code=413,
                detail=f"文件超过大小限制（最大 {settings.TRACK_MAX_UPLOAD_MB} MB）",
            )
    data = bytes(chunks)
    if not data:
        raise HTTPException(status_code=400, detail="上传文件为空")

    if survey_task_id is not None and db.get(SurveyTask, survey_task_id) is None:
        raise HTTPException(status_code=404, detail="调研任务不存在")

    track = TrackFile(original_name=filename, status="pending", stage="pending", survey_task_id=survey_task_id)
    db.add(track)
    db.commit()
    db.refresh(track)

    destination = track_service.source_dir(track.id) / filename
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    track.kml_path = str(destination)
    db.commit()

    background_tasks.add_task(track_service.process_track, track.id)
    return {"track_id": track.id, "status": track.status, "survey_task_id": track.survey_task_id}


@router.get("/list")
def list_tracks(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    tracks = db.query(TrackFile).order_by(TrackFile.id.desc()).all()
    return {"items": [_track_summary(track) for track in tracks]}


@router.get("/{track_id}/status")
def track_status(track_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    track = _get_track(db, track_id)
    failed = (
        db.query(TrackPhoto)
        .filter(TrackPhoto.track_id == track_id, TrackPhoto.download_status == "failed")
        .count()
    )
    return {
        "track_id": track.id,
        "status": track.status,
        "stage": track.stage,
        "done": track.progress_done,
        "total": track.progress_total,
        "track_point_count": track.track_point_count,
        "photo_count": track.photo_count,
        "failed_count": failed,
        "error_message": track.error_message,
    }


@router.post("/{track_id}/retry")
def retry_track(
    track_id: int,
    background_tasks: BackgroundTasks,
    force_describe: bool = Query(False, alias="force_describe", description="重置语义描述并按新提示词重新生成"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """重新触发处理（默认仅重试失败/未完成的照片；force_describe=True 时重跑全部语义描述）。"""
    track = _get_track(db, track_id)
    if force_describe:
        db.query(TrackPhoto).filter(TrackPhoto.track_id == track_id).update(
            {TrackPhoto.describe_status: "pending"}, synchronize_session=False
        )
    track.status = "pending"
    track.stage = "pending"
    db.commit()
    background_tasks.add_task(track_service.process_track, track.id)
    return {"track_id": track.id, "status": track.status, "force_describe": force_describe}


@router.get("/{track_id}/export.xlsx")
def export_xlsx(track_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    track = _get_track(db, track_id)
    content = track_service.build_xlsx(db, track)
    filename = f"{Path(track.original_name).stem}_照片汇总.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename=\"photos.xlsx\"; filename*=UTF-8''{quote(filename)}"
        },
    )


@router.get("/{track_id}/export.zip")
def export_zip(track_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    track = _get_track(db, track_id)
    content = track_service.build_zip(db, track)
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="track_{track_id}_photos.zip"'},
    )


@router.get("/{track_id}/photos/{photo_id}")
def get_photo(
    track_id: int,
    photo_id: int,
    thumb: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    photo = (
        db.query(TrackPhoto)
        .filter(TrackPhoto.id == photo_id, TrackPhoto.track_id == track_id)
        .first()
    )
    if photo is None:
        raise HTTPException(status_code=404, detail="照片不存在")
    path = photo.thumb_path if thumb and photo.thumb_path else photo.file_path
    if not path or not Path(path).exists():
        raise HTTPException(status_code=404, detail="照片文件不存在")
    return FileResponse(path, media_type="image/jpeg", filename=Path(path).name)


@router.get("/photos/overview")
def photos_overview(
    park_id: Optional[int] = Query(None, description="按关联公园筛选"),
    track_id: Optional[int] = Query(None, description="按轨迹筛选"),
    code: Optional[str] = Query(None, description="按 A–F 保护展示编码筛选（G 为未归类）"),
    date_from: Optional[str] = Query(None, description="拍摄起始日期 YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="拍摄截止日期 YYYY-MM-DD"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=2000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """全量田野照片聚合视图：筛选 + 分页 + 全局统计，供 /field-gallery 一次拉取。

    照片不经前端循环请求：轨迹/公园关联与 A–F 语义编码均在此聚合返回。
    """
    code_filter = code.strip().upper() if code else None
    if code_filter and code_filter not in semantic_analysis.TYPE_NAMES:
        raise HTTPException(status_code=400, detail="code 应为 A–G 之一")
    try:
        start_date = date.fromisoformat(date_from) if date_from else None
        end_date = date.fromisoformat(date_to) if date_to else None
    except ValueError:
        raise HTTPException(status_code=400, detail="date_from/date_to 格式应为 YYYY-MM-DD")

    track_rows = {
        track.id: track for track in db.query(TrackFile).all()
    }
    park_by_track = _track_park_rows(db)

    photo_query = db.query(TrackPhoto).order_by(
        TrackPhoto.shot_time.asc().nullslast(), TrackPhoto.id.asc()
    )
    if track_id is not None:
        photo_query = photo_query.filter(TrackPhoto.track_id == track_id)
    photos = photo_query.all()

    code_maps: dict[int, dict[int, str] | None] = {}
    all_items: list[dict] = []
    code_counter: dict[str, int] = {key: 0 for key in semantic_analysis.TYPE_NAMES}
    park_counts: dict[int, int] = {}
    track_counts: dict[int, int] = {}
    park_meta: dict[int, str] = {}
    track_meta: dict[int, dict] = {}

    for photo in photos:
        track = track_rows.get(photo.track_id)
        if photo.track_id not in code_maps:
            code_maps[photo.track_id] = _track_code_map(photo.track_id)
        semantic_code = _photo_semantic_code(photo.track_id, photo, code_maps[photo.track_id])
        code_counter[semantic_code] = code_counter.get(semantic_code, 0) + 1

        park = park_by_track.get(photo.track_id) or {"park_id": None, "park_name": None}
        if park["park_id"] is not None:
            park_counts[park["park_id"]] = park_counts.get(park["park_id"], 0) + 1
            park_meta[park["park_id"]] = park["park_name"] or f"公园 {park['park_id']}"
        track_counts[photo.track_id] = track_counts.get(photo.track_id, 0) + 1
        track_name = Path(track.original_name).stem if track else None
        track_meta[photo.track_id] = {
            "track_id": photo.track_id,
            "track_name": track_name,
            "park_id": park["park_id"],
            "park_name": park["park_name"],
        }

        all_items.append({
            "photo_id": photo.id,
            "track_id": photo.track_id,
            "track_name": track_name,
            "survey_task_id": track.survey_task_id if track else None,
            "park_id": park["park_id"],
            "park_name": park["park_name"],
            "longitude": photo.longitude,
            "latitude": photo.latitude,
            "shot_time": photo.shot_time.isoformat() if photo.shot_time else None,
            "code": semantic_code,
            "code_name": semantic_analysis.TYPE_NAMES.get(semantic_code),
            "caption": photo.caption,
            "description": photo.description,
            "address": photo.address,
            "province": photo.province,
            "city": photo.city,
            "district": photo.district,
            "poi": photo.poi,
            "tags": _parse_tags(photo.tags),
            "photo_url": f"/api/track/{photo.track_id}/photos/{photo.id}",
            "thumb_url": f"/api/track/{photo.track_id}/photos/{photo.id}?thumb=true",
            "download_status": photo.download_status,
            "describe_status": photo.describe_status,
        })

    filtered = [
        item for item in all_items
        if (park_id is None or item["park_id"] == park_id)
        and (track_id is None or item["track_id"] == track_id)
        and (code_filter is None or item["code"] == code_filter)
        and (start_date is None or (item["shot_time"] and date.fromisoformat(item["shot_time"][:10]) >= start_date))
        and (end_date is None or (item["shot_time"] and date.fromisoformat(item["shot_time"][:10]) <= end_date))
    ]

    total_distance = sum(
        (track.distance_meters or 0.0) for track in track_rows.values()
    )
    stats = {
        "photo_total": len(all_items),
        "event_count": db.query(SurveyEvent).count(),
        "park_count": len(park_counts),
        "track_count": len(track_counts),
        "distance_km": round(total_distance / 1000, 2),
        "by_code": {
            key: {"name": semantic_analysis.TYPE_NAMES[key], "count": code_counter.get(key, 0)}
            for key in ["A", "B", "C", "D", "E", "F", "G"]
        },
        "parks": [
            {"park_id": pid, "park_name": park_meta.get(pid, f"公园 {pid}"), "photo_count": count}
            for pid, count in sorted(park_counts.items(), key=lambda pair: -pair[1])
        ],
        "tracks": [
            {**track_meta[tid], "photo_count": count}
            for tid, count in sorted(track_counts.items(), key=lambda pair: -pair[1])
        ],
    }

    start = (page - 1) * page_size
    return {
        "items": filtered[start:start + page_size],
        "total": len(filtered),
        "page": page,
        "page_size": page_size,
        "stats": stats,
    }


@router.get("/analysis/compare")
def compare_analysis(
    ids: str = Query(..., description="逗号分隔的轨迹ID，如 1,2,3"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """跨轨迹（跨公园）语义构成比较。"""
    try:
        track_ids = [int(part) for part in ids.split(",") if part.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="ids 格式应为逗号分隔的整数")
    if not track_ids:
        raise HTTPException(status_code=400, detail="ids 不能为空")
    return semantic_analysis.compare_tracks(db, track_ids)


@router.post("/{track_id}/analyze")
def run_analysis(
    track_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """执行语义编码与指标分析（A–F 编码表 + 点位簇 + 密度/构成指标），结果持久化。"""
    track = _get_track(db, track_id)
    if not track_service.ordered_photos(db, track_id):
        raise HTTPException(status_code=400, detail="该轨迹暂无照片，无法分析")
    return semantic_analysis.analyze_track(db, track)


@router.get("/{track_id}/analysis")
def get_analysis(
    track_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """读取已生成的分析结果；不存在则即时计算（不持久化）。"""
    track = _get_track(db, track_id)
    cached = semantic_analysis.load_analysis(track_id)
    if cached is not None:
        return cached
    if not track_service.ordered_photos(db, track_id):
        raise HTTPException(status_code=400, detail="该轨迹暂无照片，无法分析")
    return semantic_analysis.analyze_track(db, track, persist=False)


@router.get("/{track_id}/analysis.csv")
def export_analysis_csv(
    track_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """导出语义编码结果 CSV（Excel 可直接打开筛选）。"""
    track = _get_track(db, track_id)
    analysis = semantic_analysis.load_analysis(track_id)
    if analysis is None:
        if not track_service.ordered_photos(db, track_id):
            raise HTTPException(status_code=400, detail="该轨迹暂无照片，无法分析")
        analysis = semantic_analysis.analyze_track(db, track)
    content = semantic_analysis.build_analysis_csv(analysis)
    filename = f"{Path(track.original_name).stem}_语义编码.csv"
    return Response(
        content=content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=\"analysis.csv\"; filename*=UTF-8''{quote(filename)}"
        },
    )


@router.get("/{track_id}")
def get_track(track_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """返回轨迹 GeoJSON + 照片点列表（含全部语义字段）。"""
    track = _get_track(db, track_id)
    photos = track_service.ordered_photos(db, track_id)
    return {
        "track": _track_summary(track),
        "geojson": track_service.load_track_geojson(track),
        "photos": [_photo_payload(photo) for photo in photos],
    }


@router.delete("/{track_id}")
def delete_track(track_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """删除轨迹及其照片文件；同时清理由该轨迹照片派生的调研事件，避免悬空引用。"""
    track = _get_track(db, track_id)
    photo_ids = [row[0] for row in db.query(TrackPhoto.id).filter(TrackPhoto.track_id == track_id).all()]
    if photo_ids:
        db.query(SurveyEvent).filter(
            SurveyEvent.source_type == "track_photo",
            SurveyEvent.source_material_id.in_(photo_ids),
        ).delete(synchronize_session=False)
    task = db.get(SurveyTask, track.survey_task_id) if track.survey_task_id else None
    db.query(TrackPhoto).filter(TrackPhoto.track_id == track_id).delete(synchronize_session=False)
    db.delete(track)
    db.commit()

    if task is not None:
        remaining = db.query(SurveyEvent).filter(SurveyEvent.task_id == task.id).count()
        if remaining == 0:
            # 清理已失效的报告文件；仅当该任务确为本次 KML 自动创建时一并删除任务
            report_service.delete_task_reports(task.id)
            db.query(SurveyReport).filter(SurveyReport.task_id == task.id).delete(synchronize_session=False)
            db.commit()
            if task.title == Path(track.original_name or "").stem:
                db.delete(task)
                db.commit()

    track_service.delete_track_storage(track_id)
    return {"deleted": track_id}
