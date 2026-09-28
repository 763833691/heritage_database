"""田野调研 S1~S3 测试：KML 解析 / 模型落库 / 上传处理接口 / 报告 docx。

网络调用（照片下载、逆地理编码、多模态描述、LLM）全部 mock，离线可跑。

运行：
    cd backend
    python -m pytest tests/test_track.py -q
"""
from __future__ import annotations

import asyncio
import io
import json
import re
import threading
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.database import Base, get_db
from app.models.survey import SurveyEvent, SurveyReport, SurveyTask
from app.models.track import TrackFile, TrackPhoto
from app.services import report_service, track_service
from app.services.kml_service import parse_kml_bytes

FIXTURE_KML = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2" xmlns:gx="http://www.google.com/kml/ext/2.2">
  <Document>
    <name>刘贺主墓调研</name>
    <Placemark>
      <name>轨迹</name>
      <gx:Track>
        <when>2026-09-08T02:44:00Z</when>
        <gx:coord>115.900100 28.700100 20.0</gx:coord>
        <when>2026-09-08T02:46:00Z</when>
        <gx:coord>115.900200 28.700200 21.0</gx:coord>
        <when>2026-09-08T02:50:00Z</when>
        <gx:coord>115.900400 28.700400 22.0</gx:coord>
      </gx:Track>
    </Placemark>
    <Placemark>
      <name>IMG_0001</name>
      <description><![CDATA[<img src="https://cdn.example.com/photo1.jpg"/>]]></description>
      <Point><coordinates>115.900200,28.700200,22.5</coordinates></Point>
      <ExtendedData>
        <Data name="time"><value>2026-09-08 10:45:00</value></Data>
        <Data name="speed"><value>1.2</value></Data>
        <Data name="accuracy"><value>5</value></Data>
      </ExtendedData>
    </Placemark>
    <Placemark>
      <name>照片2</name>
      <Point><coordinates>115.900300,28.700300,23.0</coordinates></Point>
      <ExtendedData>
        <Data name="photo_url"><value>https://cdn.example.com/photo2.jpg</value></Data>
        <Data name="time"><value>2026-09-08T10:50:00Z</value></Data>
        <Data name="altitude"><value>23</value></Data>
      </ExtendedData>
    </Placemark>
  </Document>
</kml>
"""

GEOCODE_RESULT = {
    "province": "江西省",
    "city": "南昌市",
    "district": "新建区",
    "street": "海昏侯国遗址公园步道",
    "poi": "刘贺主墓",
    "address": "江西省南昌市新建区海昏侯国遗址公园刘贺主墓",
}


def _jpeg(color=(120, 140, 160), size=(80, 60)) -> bytes:
    image = Image.new("RGB", size, color)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


class _FakeProvider:
    """返回带 [EV:id] 引用标记的合法 JSON，模拟现有 llm_provider。"""

    async def chat(self, messages):  # noqa: ANN001
        text = messages[-1]["content"]
        ids = re.findall(r"\[EV:(\d+)\]", text)
        first = ids[0] if ids else ""
        return json.dumps(
            {
                "time": "本次调研于 2026 年 9 月 8 日上午开展。",
                "method": "采用实地踏勘方式，同步记录 GPS 轨迹并采集现场影像。",
                "route": f"调研组自起点进入遗址公园，沿参观步道完成踏勘并记录关键点位[EV:{first}]。",
            },
            ensure_ascii=False,
        )


@pytest.fixture()
def api(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test_track.db'}",
        connect_args={"check_same_thread": False},
    )
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    monkeypatch.setattr(settings, "TRACK_STORAGE_DIR", str(tmp_path / "tracks"))
    monkeypatch.setattr(settings, "SURVEY_REPORT_DIR", str(tmp_path / "reports"))
    monkeypatch.setattr(track_service, "SessionLocal", testing_session)
    monkeypatch.setattr(report_service, "SessionLocal", testing_session)
    monkeypatch.setattr(track_service, "_GEOCODE_CACHE", None)

    async def fake_download(url, *, timeout=60):  # noqa: ANN001, ARG001
        return _jpeg()

    def fake_geocode(latitude, longitude):  # noqa: ANN001, ARG001
        return dict(GEOCODE_RESULT)

    def fake_describe(image_bytes, prompt, *, timeout=60, **kwargs):  # noqa: ANN001, ARG001
        return json.dumps(
            {
                "description": "画面为刘贺主墓保护展示区，可见封土与参观步道，现场设有说明标识牌。",
                "caption": "刘贺主墓保护展示区",
                "tags": ["刘贺主墓", "保护展示", "参观步道"],
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(track_service, "download_image", fake_download)
    monkeypatch.setattr(track_service, "geocode", fake_geocode)
    monkeypatch.setattr(track_service, "describe_image", fake_describe)
    monkeypatch.setattr(report_service, "get_llm_provider", lambda: _FakeProvider())

    app = FastAPI()
    from app.api.survey import router as survey_router
    from app.api.track import router as track_router

    app.include_router(track_router, prefix="/api/track")
    app.include_router(survey_router, prefix="/api/survey")

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client, testing_session


def test_parse_two_step_kml():
    result = parse_kml_bytes(FIXTURE_KML.encode("utf-8"))

    assert result.name == "刘贺主墓调研"
    assert len(result.points) == 3
    # gx:when 为 UTC(02:44Z)，统一换算到 Asia/Shanghai 后为 10:44，与 ExtendedData 本地时间同口径
    assert result.points[0].time is not None and result.points[0].time.hour == 10
    assert result.points[0].longitude == pytest.approx(115.900100)
    assert result.points[0].altitude == pytest.approx(20.0)

    assert len(result.photos) == 2
    first, second = result.photos
    assert first.url == "https://cdn.example.com/photo1.jpg"
    assert first.speed == pytest.approx(1.2)
    assert first.accuracy == pytest.approx(5.0)
    assert first.shot_time is not None and first.shot_time.day == 8
    assert first.file_name == "IMG_0001"
    assert second.url == "https://cdn.example.com/photo2.jpg"
    assert second.altitude == pytest.approx(23.0)


def test_download_url_guard_blocks_internal_hosts():
    from app.services.track_service import _is_public_http_url

    assert _is_public_http_url("http://127.0.0.1:8000/api/track/list") is False
    assert _is_public_http_url("http://localhost/photo.jpg") is False
    assert _is_public_http_url("http://10.0.0.5/photo.jpg") is False
    assert _is_public_http_url("http://169.254.169.254/latest/meta-data") is False
    assert _is_public_http_url("file:///etc/passwd") is False
    assert _is_public_http_url("http://93.184.216.34/photo.jpg") is True


def test_models_persist(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'models.db'}")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()

    track = TrackFile(original_name="demo.kml", status="done", track_point_count=3, photo_count=1)
    session.add(track)
    session.commit()

    task = SurveyTask(title="demo", status="processing")
    session.add(task)
    session.commit()

    photo = TrackPhoto(track_id=track.id, seq=0, latitude=28.7, longitude=115.9, address="南昌市新建区")
    session.add(photo)
    session.commit()

    event = SurveyEvent(
        task_id=task.id,
        event_type="photo",
        source_type="track_photo",
        source_material_id=photo.id,
        title="图注",
        tags=json.dumps(["标签"], ensure_ascii=False),
    )
    session.add(event)
    session.commit()

    stored = session.query(SurveyEvent).filter_by(task_id=task.id).one()
    assert stored.event_type == "photo"
    assert json.loads(stored.tags) == ["标签"]
    assert stored.usable_for_report is True
    session.close()


def _run_upload(client: TestClient) -> int:
    response = client.post(
        "/api/track/upload",
        files={"file": ("刘贺主墓.kml", FIXTURE_KML.encode("utf-8"), "application/vnd.google-earth.kml+xml")},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] in ("pending", "parsing", "downloading", "geocoding", "describing", "done")
    return payload["track_id"]


def test_upload_pipeline_creates_photos_events_and_exports(api):
    client, testing_session = api
    track_id = _run_upload(client)

    status = client.get(f"/api/track/{track_id}/status").json()
    assert status["status"] == "done", status
    assert status["track_point_count"] == 3
    assert status["photo_count"] == 2
    assert status["failed_count"] == 0

    detail = client.get(f"/api/track/{track_id}").json()
    assert detail["geojson"]["features"][0]["geometry"]["type"] == "LineString"
    assert len(detail["photos"]) == 2
    for photo in detail["photos"]:
        assert photo["download_status"] == "success"
        assert photo["describe_status"] == "success"
        assert photo["address"] == GEOCODE_RESULT["address"]
        assert photo["description"]

    db = testing_session()
    track = db.get(TrackFile, track_id)
    assert track.survey_task_id is not None
    task = db.get(SurveyTask, track.survey_task_id)
    assert task is not None and task.title == "刘贺主墓"
    events = db.query(SurveyEvent).filter_by(task_id=task.id).all()
    assert len(events) == 2
    assert all(event.address for event in events)
    db.close()

    events_response = client.get(f"/api/survey/tasks/{track.survey_task_id}/events").json()
    assert len(events_response["items"]) == 2
    assert events_response["items"][0]["photo"]["thumb_url"].endswith("thumb=true")
    timeline = client.get(f"/api/survey/tasks/{track.survey_task_id}/timeline").json()
    assert sum(bucket["count"] for bucket in timeline["items"]) == 2

    for suffix in ("export.xlsx", "export.zip"):
        export = client.get(f"/api/track/{track_id}/{suffix}")
        assert export.status_code == 200, suffix
        assert len(export.content) > 0
    assert client.get(f"/api/track/{track_id}/photos/1").status_code == 200


def test_patch_event_and_generate_report_docx(api):
    client, testing_session = api
    track_id = _run_upload(client)
    db = testing_session()
    track = db.get(TrackFile, track_id)
    task_id = track.survey_task_id
    db.close()

    events = client.get(f"/api/survey/tasks/{task_id}/events").json()["items"]
    event_id = events[0]["id"]
    patched = client.patch(
        f"/api/survey/events/{event_id}",
        json={"title": "人工校对图注", "tags": ["校对", "刘贺主墓"], "usable_for_report": True},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["title"] == "人工校对图注"
    assert patched.json()["tags"] == ["校对", "刘贺主墓"]

    generated = client.post(f"/api/survey/tasks/{task_id}/report/chapter2")
    assert generated.status_code == 200, generated.text

    report = client.get(f"/api/survey/tasks/{task_id}/report").json()
    assert report["status"] == "done", report
    assert report["content"]["title"] == "二、调研过程"
    assert report["content"]["sections"][0]["heading"] == "（一）调研时间"
    assert report["content"]["figures"], "应自动挑选代表性照片"
    assert report["content"]["figures"][0]["no"] == "图 2.1"
    citation_ids = {item["event_id"] for item in report["citations"]}
    assert event_id in citation_ids

    docx = client.get(f"/api/survey/tasks/{task_id}/report.docx")
    assert docx.status_code == 200
    assert docx.content[:2] == b"PK"

    db = testing_session()
    stored = db.query(SurveyReport).filter_by(task_id=task_id).one()
    assert stored.version == 1
    assert Path(stored.docx_path).exists()
    db.close()


def test_rerun_preserves_manual_review_edits(api):
    client, testing_session = api
    track_id = _run_upload(client)
    db = testing_session()
    task_id = db.get(TrackFile, track_id).survey_task_id
    db.close()

    event_id = client.get(f"/api/survey/tasks/{task_id}/events").json()["items"][0]["id"]
    client.patch(
        f"/api/survey/events/{event_id}",
        json={"title": "人工校对标题", "tags": ["人工校对"], "usable_for_report": True},
    )

    asyncio.run(track_service.process_track(track_id))

    events = client.get(f"/api/survey/tasks/{task_id}/events").json()["items"]
    edited = next(item for item in events if item["id"] == event_id)
    assert edited["title"] == "人工校对标题"
    assert edited["tags"] == ["人工校对"]


def test_rerun_refreshes_fallback_titles_after_describe_recovers(api, monkeypatch):
    """语义描述首次失败会写入「{地点}现场影像」占位标题；恢复后重跑应刷新为真实图注。"""
    client, testing_session = api

    def broken_describe(*args, **kwargs):  # noqa: ANN002, ANN003, ARG001
        raise RuntimeError("The read operation timed out")

    monkeypatch.setattr(track_service, "describe_image", broken_describe)
    track_id = _run_upload(client)

    db = testing_session()
    task_id = db.get(TrackFile, track_id).survey_task_id
    stale = db.query(SurveyEvent).filter_by(task_id=task_id).all()
    assert stale and all(event.title == "刘贺主墓现场影像" for event in stale), "首次失败应为降级占位标题"
    db.close()

    def recovered_describe(image_bytes, prompt, *, timeout=60, **kwargs):  # noqa: ANN001, ANN003, ARG001
        return json.dumps(
            {
                "description": "画面为刘贺主墓保护展示区，可见封土与参观步道，现场设有说明标识牌。",
                "caption": "刘贺主墓保护展示区",
                "tags": ["刘贺主墓", "保护展示", "参观步道"],
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(track_service, "describe_image", recovered_describe)
    asyncio.run(track_service.process_track(track_id))

    db = testing_session()
    refreshed = db.query(SurveyEvent).filter_by(task_id=task_id).all()
    assert all(event.title == "刘贺主墓保护展示区" for event in refreshed), "恢复后应刷新占位标题"
    assert all("保护展示区" in (event.content or "") for event in refreshed)
    db.close()


def test_describe_photos_runs_concurrently(api, monkeypatch):
    """语义描述按 TRACK_DESCRIBE_CONCURRENCY 并发执行，而非逐张串行。"""
    client, testing_session = api
    track_id = _run_upload(client)

    monkeypatch.setattr(settings, "TRACK_DESCRIBE_CONCURRENCY", 4)
    guard = threading.Lock()
    active = 0
    peak = 0

    def slow_describe(image_bytes, prompt, *, timeout=60, **kwargs):  # noqa: ANN001, ANN003, ARG001
        nonlocal active, peak
        with guard:
            active += 1
            peak = max(peak, active)
        time.sleep(0.2)
        with guard:
            active -= 1
        return json.dumps({"description": "描述", "caption": "图注", "tags": ["主题"]}, ensure_ascii=False)

    monkeypatch.setattr(track_service, "describe_image", slow_describe)

    db = testing_session()
    db.query(TrackPhoto).filter_by(track_id=track_id).update(
        {TrackPhoto.describe_status: "pending"}, synchronize_session=False
    )
    db.commit()
    track = db.get(TrackFile, track_id)
    asyncio.run(track_service._describe_photos(db, track))
    db.close()

    assert peak == 2, f"2 张照片应同时描述，实际峰值并发 {peak}"


def test_auto_title_uses_llm_and_skips_manual_edits(api, monkeypatch):
    """AI 批量生成标题：结合调研主题改标题，默认保留人工校对过的标题。"""
    client, testing_session = api
    track_id = _run_upload(client)
    db = testing_session()
    task_id = db.get(TrackFile, track_id).survey_task_id
    db.close()

    events = client.get(f"/api/survey/tasks/{task_id}/events").json()["items"]
    manual_id = events[0]["id"]
    client.patch(f"/api/survey/events/{manual_id}", json={"title": "人工校对标题"})

    captured: dict[str, str] = {}

    class _TitleProvider:
        async def chat(self, messages):  # noqa: ANN001
            captured["prompt"] = messages[-1]["content"]
            ids = re.findall(r"ID (\d+)", messages[-1]["content"])
            return json.dumps([{"id": int(eid), "title": f"主题标题{eid}"} for eid in ids], ensure_ascii=False)

    monkeypatch.setattr(track_service, "get_llm_provider", lambda: _TitleProvider())

    result = client.post(f"/api/survey/tasks/{task_id}/events/auto-title", json={"overwrite": False}).json()
    assert result["updated"] == 1 and result["skipped"] == 1
    assert "调研主题" in captured["prompt"]

    items = {item["id"]: item for item in result["items"]}
    assert items[manual_id]["title"] == "人工校对标题", "默认不得覆盖人工标题"
    generated_id = next(eid for eid in items if eid != manual_id)
    assert items[generated_id]["title"] == f"主题标题{generated_id}"

    forced = client.post(f"/api/survey/tasks/{task_id}/events/auto-title", json={"overwrite": True}).json()
    assert forced["updated"] == 2 and forced["skipped"] == 0


def test_retry_force_describe_reruns_with_theme_prompt(api, monkeypatch):
    """force_describe=True 时重置语义描述，使带调研主题的新提示词重新生效。"""
    client, testing_session = api
    track_id = _run_upload(client)

    calls: list[str] = []

    def counting_describe(image_bytes, prompt, *, timeout=60, **kwargs):  # noqa: ANN001, ANN003, ARG001
        calls.append(prompt)
        return json.dumps({"description": "画面描述", "caption": "新图注", "tags": ["主题"]}, ensure_ascii=False)

    monkeypatch.setattr(track_service, "describe_image", counting_describe)

    # 默认重跑：已成功的照片不再描述
    assert client.post(f"/api/track/{track_id}/retry").json()["force_describe"] is False
    assert calls == []

    # 强制重跑：全部照片按带主题的提示词重新描述
    assert client.post(f"/api/track/{track_id}/retry", params={"force_describe": True}).json()["force_describe"] is True
    assert len(calls) == 2
    assert all("本次调研主题：" in prompt for prompt in calls)

    db = testing_session()
    photos = db.query(TrackPhoto).filter_by(track_id=track_id).all()
    assert all(photo.caption == "新图注" for photo in photos)
    db.close()


def test_photos_overview_aggregates_stats_and_filters(api):
    """聚合接口一次返回照片点、全局统计与筛选结果，供全域照片页使用。"""
    client, testing_session = api
    track_id = _run_upload(client)

    body = client.get("/api/track/photos/overview").json()
    assert body["total"] == 2
    assert len(body["items"]) == 2
    assert body["stats"]["photo_total"] == 2
    assert body["stats"]["track_count"] == 1
    assert body["stats"]["event_count"] == 2
    assert sum(row["count"] for row in body["stats"]["by_code"].values()) == 2

    item = body["items"][0]
    assert item["track_id"] == track_id
    assert item["thumb_url"].endswith("thumb=true")
    assert item["code"] in list("ABCDEFG")
    assert item["code_name"]
    assert item["tags"] is None or isinstance(item["tags"], list)

    by_code = next(code for code, row in body["stats"]["by_code"].items() if row["count"] > 0)
    filtered = client.get("/api/track/photos/overview", params={"code": by_code}).json()
    assert filtered["total"] >= 1
    assert all(row["code"] == by_code for row in filtered["items"])

    paged = client.get("/api/track/photos/overview", params={"page": 2, "page_size": 1}).json()
    assert paged["page"] == 2 and paged["page_size"] == 1 and len(paged["items"]) == 1

    assert client.get("/api/track/photos/overview", params={"code": "Z"}).status_code == 400


def test_delete_track_cleans_up_events_and_auto_task(api):
    client, testing_session = api
    track_id = _run_upload(client)
    db = testing_session()
    task_id = db.get(TrackFile, track_id).survey_task_id
    db.close()

    assert client.delete(f"/api/track/{track_id}").status_code == 200

    db = testing_session()
    assert db.query(SurveyEvent).filter_by(task_id=task_id).count() == 0
    assert db.get(SurveyTask, task_id) is None
    assert db.get(TrackFile, track_id) is None
    db.close()
