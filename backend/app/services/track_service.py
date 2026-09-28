"""KML 轨迹照片处理管道：下载 → 逆地理编码 → 视觉语义描述 → 调研事件。

设计原则（对齐 docs/08）：
- AI 能力只复用现有公共模块：``vision_client.describe_image``；
- 状态全部持久化到 DB（``track_file`` / ``track_photo``），服务重启后不丢结果；
- 任一照片失败只标记该项，不中断整体流程，可通过 ``retry_track`` 重试。
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import functools
import io
import ipaddress
import json
import math
import re
import shutil
import socket
import time as time_module
import zipfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx
import pandas as pd
from PIL import Image
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.database import SessionLocal
from ..models.park import Park
from ..models.survey import SurveyEvent, SurveyTask
from ..models.track import TrackFile, TrackPhoto
from .kml_service import KmlParseResult, TrackPoint, parse_kml_bytes
from .llm_provider import get_llm_provider
from .vision_client import describe_image

PHOTO_PROMPT = """你是文化遗产田野调研助手。请结合本次调研主题观察这张照片，用中文输出**严格 JSON**（不要 markdown 代码块、不要多余说明）：
{{"description": "2-4 句画面描述", "caption": "不超过20字的一句话图注", "tags": ["主题标签", "..."]}}

本次调研主题：{theme}

要求：
1. description：描述画面内容、遗址要素（墓葬/城墙/建筑基址/展陈/标识牌/游客行为/环境风貌等）、可见的保护与利用现状，并点明它与调研主题的关联。
2. caption：用于调研报告配图的一句话说明；须结合调研主题提炼，突出该拍摄对象对主题的说明价值，避免「现场影像」这类空泛措辞。
3. tags：3-6 个围绕调研主题的主题标签，便于时间线检索。
4. 只描述画面中能确认的内容，不要编造。

补充信息：拍摄时间 {shot_time}；位置 {address}；海拔 {altitude}。"""


def track_dir(track_id: int) -> Path:
    return settings.track_storage_dir / str(track_id)


def photos_dir(track_id: int) -> Path:
    return track_dir(track_id) / "photos"


def thumbs_dir(track_id: int) -> Path:
    return track_dir(track_id) / "thumbs"


def source_dir(track_id: int) -> Path:
    return track_dir(track_id) / "source"


def ordered_photos(db: Session, track_id: int) -> list[TrackPhoto]:
    return (
        db.query(TrackPhoto)
        .filter(TrackPhoto.track_id == track_id)
        .order_by(TrackPhoto.seq, TrackPhoto.id)
        .all()
    )


def _safe_stem(value: str | None, fallback: str) -> str:
    stem = Path(value or "").stem or fallback
    stem = re.sub(r"[\\/:*?\"<>|\s]+", "_", stem).strip("_.")
    return stem[:60] or fallback


def _save_as_jpeg(data: bytes, path: Path, *, quality: int = 88) -> bool:
    """把下载到的图片统一保存为 JPEG；Pillow 无法解码时原样落盘。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        image = Image.open(io.BytesIO(data))
        if image.mode != "RGB":
            image = image.convert("RGB")
        image.save(path, format="JPEG", quality=quality)
        return True
    except Exception:
        try:
            path.write_bytes(data)
            return True
        except Exception:
            return False


def generate_thumbnail(image_bytes: bytes, width: int = 400) -> bytes:
    """生成指定宽度的 JPEG 缩略图（保持宽高比）。"""
    image = Image.open(io.BytesIO(image_bytes))
    if image.mode != "RGB":
        image = image.convert("RGB")
    original_width, original_height = image.size
    if original_width > width:
        height = max(1, int(original_height * width / original_width))
        image = image.resize((width, height), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=82)
    return buffer.getvalue()


_REDIRECT_STATUS = {301, 302, 303, 307, 308}
_MAX_REDIRECTS = 3


def _is_public_http_url(url: str) -> bool:
    """校验 URL：仅允许 http/https，且目标主机的所有解析地址均为公网地址。

    防止 KML 中的照片 URL 触发 SSRF（内网、回环、链路本地、云元数据等）。
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(parsed.hostname, None)}
    except Exception:
        return False
    if not addresses:
        return False
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            return False
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return False
    return True


async def download_image(url: str, *, timeout: int = 60) -> bytes:
    """下载一张照片（异步）。

    安全约束：仅允许公网 http/https、手动跟随重定向并逐跳校验、限制单张字节数。
    测试中通过 patch 本函数避免真实网络请求。
    """
    max_bytes = settings.track_max_photo_size
    current_url = url
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        for _ in range(_MAX_REDIRECTS + 1):
            if not _is_public_http_url(current_url):
                raise RuntimeError(f"照片 URL 不被允许（非公网 http/https）: {current_url[:200]}")
            async with client.stream(
                "GET",
                current_url,
                headers={"User-Agent": "Mozilla/5.0 (heritage-park-platform field survey)"},
            ) as response:
                if response.status_code in _REDIRECT_STATUS:
                    location = response.headers.get("location")
                    if not location:
                        raise RuntimeError("重定向缺少 Location 头")
                    current_url = str(httpx.URL(current_url).join(location))
                    continue
                response.raise_for_status()
                buffer = bytearray()
                async for chunk in response.aiter_bytes():
                    buffer.extend(chunk)
                    if len(buffer) > max_bytes:
                        raise RuntimeError(f"照片超过大小限制（最大 {settings.TRACK_MAX_PHOTO_MB} MB）")
                if not buffer:
                    raise RuntimeError("照片内容为空")
                return bytes(buffer)
    raise RuntimeError("照片下载重定向次数过多")


# ==================== 逆地理编码 ====================

_GEOCODE_CACHE: dict[str, dict] | None = None


def _geocode_cache_file() -> Path:
    root = settings.track_storage_dir
    root.mkdir(parents=True, exist_ok=True)
    return root / "geocode_cache.json"


def _load_geocode_cache() -> dict[str, dict]:
    global _GEOCODE_CACHE
    if _GEOCODE_CACHE is None:
        path = _geocode_cache_file()
        try:
            _GEOCODE_CACHE = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        except Exception:
            _GEOCODE_CACHE = {}
    return _GEOCODE_CACHE


def _save_geocode_cache(cache: dict[str, dict]) -> None:
    try:
        _geocode_cache_file().write_text(
            json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


def _join_address(*parts: str | None) -> str:
    seen: list[str] = []
    for part in parts:
        text = (part or "").strip()
        if text and text not in seen:
            seen.append(text)
    return "".join(seen)


def _geocode_bigdatacloud(latitude: float, longitude: float) -> dict:
    with httpx.Client(timeout=settings.GEOCODER_TIMEOUT_SECONDS) as client:
        response = client.get(
            "https://api.bigdatacloud.net/data/reverse-geocode-client",
            params={"latitude": latitude, "longitude": longitude, "localityLanguage": "zh"},
        )
        response.raise_for_status()
        payload = response.json()

    province = payload.get("principalSubdivision") or ""
    city = payload.get("city") or ""
    locality = payload.get("locality") or ""
    locality_info = payload.get("localityInfo") or {}
    administrative = locality_info.get("administrative") or []
    informative = locality_info.get("informative") or []

    district = locality
    street = ""
    for item in administrative:
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or "").strip()
        order = item.get("adminLevel") or item.get("order") or 0
        if order == 4 and name:
            district = name
        if name and any(key in name for key in ("街道", "镇", "乡", "路", "街")):
            street = name
    poi = ""
    if informative and isinstance(informative[0], dict):
        poi = (informative[0].get("name") or "").strip()

    return {
        "province": province,
        "city": city,
        "district": district,
        "street": street,
        "poi": poi,
        "address": _join_address(province, city, district, street, poi),
    }


def _geocode_nominatim(latitude: float, longitude: float) -> dict:
    with httpx.Client(timeout=settings.GEOCODER_TIMEOUT_SECONDS) as client:
        response = client.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={
                "format": "json",
                "lat": latitude,
                "lon": longitude,
                "accept-language": "zh-CN",
            },
            headers={"User-Agent": "heritage-park-platform/1.0 (field survey)"},
        )
        response.raise_for_status()
        payload = response.json()

    address = payload.get("address") or {}
    province = address.get("state") or address.get("province") or ""
    city = address.get("city") or address.get("municipality") or address.get("state_district") or ""
    district = address.get("county") or address.get("district") or address.get("city_district") or ""
    street = address.get("suburb") or address.get("road") or address.get("neighbourhood") or ""
    poi = address.get("tourism") or address.get("amenity") or address.get("attraction") or ""
    full = payload.get("display_name") or _join_address(province, city, district, street)
    return {
        "province": province,
        "city": city,
        "district": district,
        "street": street,
        "poi": poi,
        "address": full,
    }


def geocode(latitude: float, longitude: float) -> dict:
    """逆地理编码（串行调用 + 同坐标本地 JSON 缓存）。测试中通过 patch 本函数避免网络。"""
    key = f"{float(latitude):.6f},{float(longitude):.6f}"
    cache = _load_geocode_cache()
    if key in cache:
        return cache[key]

    provider = settings.geocoder_provider
    if provider == "nominatim":
        result = _geocode_nominatim(latitude, longitude)
    else:
        result = _geocode_bigdatacloud(latitude, longitude)

    cache[key] = result
    _save_geocode_cache(cache)
    time_module.sleep(max(0.0, settings.GEOCODER_INTERVAL_SECONDS))
    return result


# ==================== 视觉语义描述 ====================


def parse_vision_result(text: str) -> dict:
    """解析视觉模型返回；优先 JSON，失败则回退整段文本作为描述。"""
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()

    data: dict | None = None
    try:
        candidate = json.loads(cleaned)
        if isinstance(candidate, dict):
            data = candidate
    except Exception:
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            try:
                candidate = json.loads(match.group(0))
                if isinstance(candidate, dict):
                    data = candidate
            except Exception:
                data = None

    if data is None:
        description = cleaned
        caption = re.split(r"[。！？\n]", cleaned)[0][:60] if cleaned else ""
        tags: list[str] = []
    else:
        description = str(data.get("description") or data.get("描述") or "").strip()
        caption = str(data.get("caption") or data.get("图注") or "").strip()
        raw_tags = data.get("tags") or data.get("标签") or []
        if isinstance(raw_tags, str):
            raw_tags = [part for part in re.split(r"[,，、;；\s]+", raw_tags) if part]
        tags = [str(tag).strip() for tag in raw_tags if str(tag).strip()]
        if not description:
            description = cleaned
        if not caption:
            caption = re.split(r"[。！？\n]", description)[0][:60] if description else ""

    return {"description": description[:2000], "caption": caption[:200], "tags": tags[:8]}


def fallback_vision_result(photo: TrackPhoto) -> dict:
    place = photo.poi or photo.district or photo.city or photo.province or "调研点位"
    time_text = photo.shot_time.strftime("%Y-%m-%d %H:%M") if photo.shot_time else "时间未知"
    description = f"照片摄于{place}，拍摄时间{time_text}。画面记录了本次田野踏勘的现场情况。"
    tags = [tag for tag in [photo.poi, photo.district, "实地踏勘"] if tag]
    return {"description": description, "caption": f"{place}现场影像", "tags": tags}


# ==================== AI 批量生成标题 ====================

AUTO_TITLE_PROMPT = """你是文化遗产田野调研报告编辑。以下是同一次田野调研（调研主题：{theme}）按时间排序的照片语义记录。
请为每条记录重新拟定一个**结合调研主题、可用于时间线校对与报告配图**的中文标题。

要求：
1. 每条标题不超过 20 字，彼此不重复，突出该照片对调研主题的说明价值（拍摄对象、遗址要素、保护利用现状、人物行为等）。
2. 不要使用「现场影像」「调研照片」「记录」这类空泛措辞，也不要照抄整段描述。
3. 只输出 JSON 数组（不要 markdown 代码块、不要解释文字），元素形如 {{"id": 记录 id, "title": "标题"}}。

照片记录：
{records}"""


def _parse_title_payload(text: str) -> dict[int, str]:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()

    data: object = None
    try:
        candidate = json.loads(cleaned)
    except Exception:
        match = re.search(r"\[[\s\S]*\]", cleaned)
        candidate = None
        if match:
            try:
                candidate = json.loads(match.group(0))
            except Exception:
                candidate = None
    if isinstance(candidate, list):
        data = candidate
    elif isinstance(candidate, dict):
        data = candidate.get("items") or candidate.get("titles")
    if not isinstance(data, list):
        raise ValueError("模型未返回可解析的标题 JSON 数组")

    titles: dict[int, str] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            event_id = int(item.get("id"))
        except (TypeError, ValueError):
            continue
        title = str(item.get("title") or "").strip()
        if title:
            titles[event_id] = title[:60]
    if not titles:
        raise ValueError("模型未返回任何有效标题")
    return titles


def _title_record(event: SurveyEvent, photo: TrackPhoto) -> str:
    time_text = event.timestamp.strftime("%Y-%m-%d %H:%M") if event.timestamp else "时间未知"
    description = (photo.description or photo.caption or "").replace("\n", " ").strip()[:200]
    return f"ID {event.id}｜{time_text}｜{event.address or photo.address or '位置未知'}｜{description}"


async def auto_title_events(db: Session, task_id: int, *, overwrite: bool = False) -> dict:
    """用文本大模型结合调研主题批量生成事件标题。

    默认跳过人工校对过的标题（与照片图注不一致的）；``overwrite=True`` 时全部重写。
    """
    task = db.get(SurveyTask, task_id)
    if task is None:
        raise ValueError("调研任务不存在")
    track = (
        db.query(TrackFile)
        .filter(TrackFile.survey_task_id == task_id)
        .order_by(TrackFile.id.desc())
        .first()
    )
    events = (
        db.query(SurveyEvent)
        .filter(SurveyEvent.task_id == task_id, SurveyEvent.source_type == "track_photo")
        .order_by(SurveyEvent.timestamp.asc().nullslast(), SurveyEvent.id.asc())
        .all()
    )
    if not events:
        raise ValueError("该任务暂无可生成标题的调研事件")

    photo_ids = [event.source_material_id for event in events if event.source_material_id]
    photos = {
        photo.id: photo for photo in db.query(TrackPhoto).filter(TrackPhoto.id.in_(photo_ids)).all()
    }

    candidates: list[tuple[SurveyEvent, TrackPhoto]] = []
    skipped = 0
    for event in events:
        photo = photos.get(event.source_material_id)
        if photo is None or not (photo.description or photo.caption):
            skipped += 1
            continue
        if not overwrite and event.title and photo.caption and event.title != photo.caption:
            skipped += 1  # 已被人工校对
            continue
        candidates.append((event, photo))
    if not candidates:
        return {"updated": 0, "skipped": skipped, "total": len(events)}

    theme = _survey_theme(db, track) if track is not None else task.title
    records = "\n".join(_title_record(event, photo) for event, photo in candidates)
    provider = get_llm_provider()
    text = await provider.chat(
        [{"role": "user", "content": AUTO_TITLE_PROMPT.format(theme=theme, records=records)}]
    )
    titles = _parse_title_payload(text)

    updated = 0
    for event, _photo in candidates:
        title = titles.get(event.id)
        if title:
            event.title = title
            updated += 1
    db.commit()
    return {"updated": updated, "skipped": skipped + (len(candidates) - updated), "total": len(events)}


# ==================== 管道主体 ====================


def _set_stage(db: Session, track: TrackFile, stage: str, done: int, total: int) -> None:
    track.stage = stage
    track.progress_done = done
    track.progress_total = total
    if stage not in ("pending", "done", "failed"):
        track.status = stage
    db.commit()


def _haversine_meters(a: TrackPoint, b: TrackPoint) -> float:
    radius = 6371000.0
    lat1, lat2 = math.radians(a.latitude), math.radians(b.latitude)
    dlat = lat2 - lat1
    dlon = math.radians(b.longitude - a.longitude)
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * radius * math.asin(min(1.0, math.sqrt(h)))


def compute_distance_meters(points: list[TrackPoint]) -> float:
    total = 0.0
    for previous, current in zip(points, points[1:]):
        total += _haversine_meters(previous, current)
    return round(total, 1)


def _write_geojson(track: TrackFile, points: list[TrackPoint]) -> Path:
    coordinates = [[point.longitude, point.latitude, point.altitude or 0] for point in points]
    features = []
    if coordinates:
        features.append(
            {
                "type": "Feature",
                "properties": {"kind": "track", "name": track.original_name},
                "geometry": {"type": "LineString", "coordinates": coordinates},
            }
        )
        for label, point in (("start", points[0]), ("end", points[-1])):
            features.append(
                {
                    "type": "Feature",
                    "properties": {"kind": label},
                    "geometry": {
                        "type": "Point",
                        "coordinates": [point.longitude, point.latitude, point.altitude or 0],
                    },
                }
            )
    collection = {"type": "FeatureCollection", "features": features}
    path = track_dir(track.id) / "track.geojson"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(collection, ensure_ascii=False), encoding="utf-8")
    return path


def _sync_photo_rows(db: Session, track: TrackFile, result: KmlParseResult) -> None:
    existing = {photo.seq: photo for photo in ordered_photos(db, track.id)}
    for index, point in enumerate(result.photos):
        photo = existing.get(index)
        if photo is None:
            photo = TrackPhoto(track_id=track.id, seq=index)
            db.add(photo)
        if photo.longitude is None:
            photo.longitude = point.longitude
        if photo.latitude is None:
            photo.latitude = point.latitude
        photo.altitude = point.altitude if photo.altitude is None else photo.altitude
        photo.shot_time = photo.shot_time or point.shot_time
        photo.speed = point.speed if photo.speed is None else photo.speed
        photo.accuracy = point.accuracy if photo.accuracy is None else photo.accuracy
        photo.source_url = photo.source_url or point.url
        if not photo.file_name:
            photo.file_name = point.file_name or f"photo_{index + 1:03d}.jpg"
    db.commit()


def ensure_survey_task(db: Session, track: TrackFile) -> SurveyTask:
    if track.survey_task_id:
        task = db.get(SurveyTask, track.survey_task_id)
        if task is not None:
            return task
    title = Path(track.original_name or "未命名调研").stem or "未命名调研"
    task = SurveyTask(
        title=title,
        survey_date=track.start_time.strftime("%Y-%m-%d") if track.start_time else None,
        status="processing",
    )
    db.add(task)
    db.flush()
    track.survey_task_id = task.id
    db.commit()
    return task


def _survey_theme(db: Session, track: TrackFile) -> str:
    """调研主题：任务标题 + 关联遗址公园 + 调研区域，用于引导语义生成。"""
    task = db.get(SurveyTask, track.survey_task_id) if track.survey_task_id else None
    parts: list[str] = []
    if task is not None:
        parts.append(task.title)
        if task.park_id:
            park = db.get(Park, task.park_id)
            if park is not None:
                parts.append(park.name)
    else:
        parts.append(Path(track.original_name or "未命名调研").stem or "未命名调研")
    if track.start_address:
        parts.append(track.start_address)
    return " · ".join(dict.fromkeys(part for part in parts if part)) or "田野调研"


async def _download_photos(db: Session, track: TrackFile) -> None:
    photos = ordered_photos(db, track.id)
    limit = settings.TRACK_MAX_PHOTOS_PER_TRACK
    if limit and len(photos) > limit:
        for photo in photos[limit:]:
            photo.download_status = "skipped"
            photo.error_message = f"超过单轨迹照片上限（{limit}）"
        photos = photos[:limit]
        db.commit()
    total = len(photos)
    _set_stage(db, track, "downloading", 0, total)
    if not photos:
        return

    semaphore = asyncio.Semaphore(max(1, settings.TRACK_DOWNLOAD_CONCURRENCY))
    lock = asyncio.Lock()
    done = 0
    retries = max(0, settings.TRACK_DOWNLOAD_RETRIES)

    async def worker(photo: TrackPhoto) -> None:
        nonlocal done
        if not (photo.download_status == "success" and photo.file_path and Path(photo.file_path).exists()):
            if not photo.source_url:
                photo.download_status = "skipped"
                photo.error_message = "KML 中无照片 URL"
            else:
                last_error: Exception | None = None
                for attempt in range(retries + 1):
                    try:
                        async with semaphore:
                            data = await download_image(photo.source_url)
                        stem = _safe_stem(photo.file_name, f"photo_{photo.seq + 1:03d}")
                        filename = f"{stem}_{photo.seq + 1:03d}.jpg"
                        path = photos_dir(track.id) / filename
                        saved = await asyncio.to_thread(_save_as_jpeg, data, path)
                        if not saved:
                            raise RuntimeError("照片写入磁盘失败")
                        thumb = thumbs_dir(track.id) / filename
                        try:
                            thumb_bytes = await asyncio.to_thread(
                                generate_thumbnail, data, settings.TRACK_THUMB_WIDTH
                            )
                            thumb.parent.mkdir(parents=True, exist_ok=True)
                            thumb.write_bytes(thumb_bytes)
                        except Exception:
                            pass
                        photo.file_path = str(path)
                        photo.thumb_path = str(thumb) if thumb.exists() else None
                        photo.download_status = "success"
                        photo.error_message = None
                        break
                    except Exception as exc:  # noqa: BLE001 - 单项失败不影响整体
                        last_error = exc
                        if attempt < retries:
                            await asyncio.sleep(0.5 * (attempt + 1))
                else:
                    photo.download_status = "failed"
                    photo.error_message = f"下载失败: {last_error}"[:500]
        async with lock:
            done += 1
            track.progress_done = done
            db.commit()

    await asyncio.gather(*(worker(photo) for photo in photos))


def _apply_geocode(photo: TrackPhoto, info: dict) -> None:
    photo.province = info.get("province") or photo.province
    photo.city = info.get("city") or photo.city
    photo.district = info.get("district") or photo.district
    photo.street = info.get("street") or photo.street
    photo.poi = info.get("poi") or photo.poi
    photo.address = info.get("address") or photo.address


async def _geocode_track_endpoints(db: Session, track: TrackFile, result: KmlParseResult) -> None:
    for label, point in (("start", result.points[0] if result.points else None),
                         ("end", result.points[-1] if result.points else None)):
        if point is None:
            continue
        try:
            info = await asyncio.to_thread(geocode, point.latitude, point.longitude)
        except Exception:
            continue
        if label == "start":
            track.start_address = info.get("address") or track.start_address
        else:
            track.end_address = info.get("address") or track.end_address
    db.commit()


async def _geocode_photos(db: Session, track: TrackFile) -> None:
    photos = ordered_photos(db, track.id)
    _set_stage(db, track, "geocoding", 0, len(photos))
    for index, photo in enumerate(photos, start=1):
        if photo.latitude is not None and photo.longitude is not None and not photo.address:
            try:
                info = await asyncio.to_thread(geocode, photo.latitude, photo.longitude)
                _apply_geocode(photo, info)
                if photo.download_status == "success":
                    photo.error_message = None
            except Exception as exc:  # noqa: BLE001
                photo.error_message = f"逆地理编码失败: {exc}"[:500]
        track.progress_done = index
        db.commit()


async def _describe_photos(db: Session, track: TrackFile) -> None:
    photos = [photo for photo in ordered_photos(db, track.id) if photo.file_path and Path(photo.file_path).exists()]
    pending = [photo for photo in photos if photo.describe_status != "success"]
    _set_stage(db, track, "describing", len(photos) - len(pending), len(photos))
    if not pending:
        return

    theme = _survey_theme(db, track)
    concurrency = max(1, settings.TRACK_DESCRIBE_CONCURRENCY)
    semaphore = asyncio.Semaphore(concurrency)
    lock = asyncio.Lock()
    done = len(photos) - len(pending)
    # describe_image 是同步阻塞调用：必须用与并发度匹配的专用线程池，
    # 否则会受 asyncio 默认线程池（约 32 个 worker）限制。
    loop = asyncio.get_running_loop()
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="vision")

    async def worker(photo: TrackPhoto) -> None:
        nonlocal done
        prompt = PHOTO_PROMPT.format(
            theme=theme,
            shot_time=photo.shot_time.strftime("%Y-%m-%d %H:%M:%S") if photo.shot_time else "未知",
            address=photo.address or "未知",
            altitude=f"{photo.altitude:.0f} 米" if photo.altitude is not None else "未知",
        )
        try:
            image_bytes = await asyncio.to_thread(Path(photo.file_path).read_bytes)
            async with semaphore:
                text = await loop.run_in_executor(
                    executor,
                    functools.partial(
                        describe_image, image_bytes, prompt, timeout=settings.VISION_TIMEOUT_SECONDS
                    ),
                )
            parsed = parse_vision_result(text)
            photo.description = parsed["description"]
            photo.caption = parsed["caption"]
            photo.tags = json.dumps(parsed["tags"], ensure_ascii=False)
            photo.describe_status = "success"
        except Exception as exc:  # noqa: BLE001 - 无 key 或调用失败时降级为模板描述
            parsed = fallback_vision_result(photo)
            photo.description = photo.description or parsed["description"]
            photo.caption = photo.caption or parsed["caption"]
            photo.tags = photo.tags or json.dumps(parsed["tags"], ensure_ascii=False)
            photo.describe_status = "failed"
            photo.error_message = f"语义描述失败: {exc}"[:500]
        async with lock:
            done += 1
            track.progress_done = done
            db.commit()

    try:
        await asyncio.gather(*(worker(photo) for photo in pending))
    finally:
        executor.shutdown(wait=True)


def _tags_equal(stored: str | None, expected: list[str]) -> bool:
    try:
        parsed = json.loads(stored or "[]")
    except Exception:
        return False
    return isinstance(parsed, list) and parsed == expected


def _create_events(db: Session, track: TrackFile) -> None:
    task = ensure_survey_task(db, track)
    for photo in ordered_photos(db, track.id):
        if not photo.description and not photo.caption:
            continue
        event = (
            db.query(SurveyEvent)
            .filter(
                SurveyEvent.task_id == task.id,
                SurveyEvent.source_type == "track_photo",
                SurveyEvent.source_material_id == photo.id,
            )
            .first()
        )
        if event is None:
            event = SurveyEvent(task_id=task.id, source_type="track_photo", source_material_id=photo.id)
            db.add(event)
        # 重新处理时保留「时间线校对」阶段的人工编辑：只补齐空字段，
        # 或覆盖此前语义描述失败时写入的降级模板占位内容。
        fallback = fallback_vision_result(photo)
        described = photo.describe_status == "success"
        if not event.event_type:
            event.event_type = "photo"
        if event.timestamp is None:
            event.timestamp = photo.shot_time
        if event.longitude is None:
            event.longitude = photo.longitude
        if event.latitude is None:
            event.latitude = photo.latitude
        if not event.address:
            event.address = photo.address
        if not event.title or (described and photo.caption and event.title == fallback["caption"]):
            event.title = photo.caption or (photo.file_name or "调研照片")
        if not event.content or (described and photo.description and event.content == fallback["description"]):
            event.content = photo.description
        if not event.tags or event.tags == "[]" or (described and _tags_equal(event.tags, fallback["tags"])):
            try:
                event.tags = json.dumps(json.loads(photo.tags or "[]"), ensure_ascii=False)
            except Exception:
                event.tags = photo.tags or "[]"
    db.commit()


async def _run_pipeline(db: Session, track: TrackFile) -> None:
    _set_stage(db, track, "parsing", 0, 0)
    kml_bytes = await asyncio.to_thread(Path(track.kml_path).read_bytes)
    result = await asyncio.to_thread(parse_kml_bytes, kml_bytes)

    track.track_point_count = len(result.points)
    track.photo_count = len(result.photos)
    times = [point.time for point in result.points if point.time]
    if times:
        track.start_time = min(times)
        track.end_time = max(times)
    track.distance_meters = compute_distance_meters(result.points)
    track.geojson_path = str(await asyncio.to_thread(_write_geojson, track, result.points))
    _sync_photo_rows(db, track, result)
    ensure_survey_task(db, track)
    await _geocode_track_endpoints(db, track, result)
    db.commit()

    await _download_photos(db, track)
    await _geocode_photos(db, track)
    await _describe_photos(db, track)
    _create_events(db, track)


async def process_track(track_id: int) -> None:
    """后台处理入口：解析 → 下载 → 逆地理 → 语义描述 → 生成调研事件。"""
    db = SessionLocal()
    try:
        track = db.get(TrackFile, track_id)
        if track is None or not track.kml_path:
            return
        track.error_message = None
        try:
            await _run_pipeline(db, track)
            track.status = "done"
            track.stage = "done"
            track.progress_done = track.progress_total
        except Exception as exc:  # noqa: BLE001
            track.status = "failed"
            track.stage = "failed"
            track.error_message = str(exc)[:2000]
        db.commit()
    finally:
        db.close()


# ==================== 导出 ====================


def build_xlsx(db: Session, track: TrackFile) -> bytes:
    from openpyxl import Workbook
    from openpyxl.drawing.image import Image as XlsxImage
    from openpyxl.utils import get_column_letter

    photos = ordered_photos(db, track.id)
    columns = [
        "序号", "文件名", "拍摄时间", "经度", "纬度", "海拔(m)", "速度", "定位精度",
        "省", "市", "区县", "街道", "附近POI", "语义地址", "语义描述", "报告图注", "下载状态",
    ]
    records = [
        {
            "序号": index,
            "文件名": photo.file_name or "",
            "拍摄时间": photo.shot_time.strftime("%Y-%m-%d %H:%M:%S") if photo.shot_time else "",
            "经度": photo.longitude,
            "纬度": photo.latitude,
            "海拔(m)": photo.altitude,
            "速度": photo.speed,
            "定位精度": photo.accuracy,
            "省": photo.province or "",
            "市": photo.city or "",
            "区县": photo.district or "",
            "街道": photo.street or "",
            "附近POI": photo.poi or "",
            "语义地址": photo.address or "",
            "语义描述": photo.description or "",
            "报告图注": photo.caption or "",
            "下载状态": photo.download_status or "",
        }
        for index, photo in enumerate(photos, start=1)
    ]
    frame = pd.DataFrame(records)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "照片汇总"
    sheet.append(["缩略图", *columns])
    sheet.column_dimensions["A"].width = 20
    for column_index in range(2, len(columns) + 2):
        sheet.column_dimensions[get_column_letter(column_index)].width = 18

    for row_index, (_, record) in enumerate(frame.iterrows(), start=2):
        for column_index, column in enumerate(columns, start=2):
            sheet.cell(row=row_index, column=column_index, value=record[column])
        sheet.row_dimensions[row_index].height = 80
        thumb_path = photos[row_index - 2].thumb_path
        if thumb_path and Path(thumb_path).exists():
            try:
                image = XlsxImage(thumb_path)
                ratio = image.height / image.width if image.width else 0.75
                image.width = 110
                image.height = max(1, int(110 * ratio))
                sheet.add_image(image, f"A{row_index}")
            except Exception:
                pass

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def build_zip(db: Session, track: TrackFile) -> bytes:
    photos = ordered_photos(db, track.id)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        if track.kml_path and Path(track.kml_path).exists():
            archive.write(track.kml_path, arcname=f"kml/{Path(track.kml_path).name}")
        for photo in photos:
            if photo.file_path and Path(photo.file_path).exists():
                archive.write(photo.file_path, arcname=f"photos/{Path(photo.file_path).name}")
    return buffer.getvalue()


NON_TERMINAL_STAGES = ("pending", "parsing", "downloading", "geocoding", "describing")


def recover_interrupted_tracks() -> int:
    """服务启动时把因重启而中断的轨迹标记为 failed，供用户重试（结果不丢）。"""
    db = SessionLocal()
    try:
        tracks = db.query(TrackFile).filter(TrackFile.status.in_(NON_TERMINAL_STAGES)).all()
        for track in tracks:
            track.status = "failed"
            track.stage = "failed"
            track.error_message = "服务重启导致处理中断，请点击重试"
        db.commit()
        return len(tracks)
    except Exception:
        db.rollback()
        return 0
    finally:
        db.close()


def delete_track_storage(track_id: int) -> None:
    path = track_dir(track_id)
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


def load_track_geojson(track: TrackFile) -> dict:
    if track.geojson_path and Path(track.geojson_path).exists():
        try:
            return json.loads(Path(track.geojson_path).read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"type": "FeatureCollection", "features": []}
