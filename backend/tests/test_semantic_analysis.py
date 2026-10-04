"""轨迹语义分析测试：编码表归类 / 双格式 KML 解析回归 / 指标接口 / 点位簇。

网络调用（照片下载、逆地理编码、多模态描述）全部 mock，离线可跑。
``api`` fixture 的写法参照 ``tests/test_track.py``。

运行：
    cd backend
    python -m pytest tests/test_semantic_analysis.py -q
"""
from __future__ import annotations

import io
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.database import Base, get_db
from app.models.track import TrackPhoto
from app.services import track_service
from app.services.kml_service import parse_kml_bytes
from app.services.semantic_analysis import (
    build_sequence_analysis,
    build_spatial_analysis,
    classify_text,
    cluster_photos,
)

LOCAL_TZ = ZoneInfo("Asia/Shanghai")

# ===== 编码表用例（分类输入文本 → 期望类型）=====
CLASSIFY_CASES = [
    ("夯土墩台与门道遗址", "A"),
    ("复原城楼斗栱外观", "B"),
    ("隋唐洛阳城平面布局展板", "C"),
    ("互动触摸屏趣味问答", "D"),
    ("售票处票价牌", "E"),
    ("天街石板大道与两侧绿化", "F"),
    ("", "G"),
]

# 旧版格式：无 <Point>，坐标在 ExtendedData（Longtitude 拼写变体），时间为 13 位毫秒 epoch
_OLD_EPOCH_MS = int(datetime(2026, 9, 8, 10, 45, tzinfo=LOCAL_TZ).timestamp() * 1000)

OLD_KML = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2" xmlns:gx="http://www.google.com/kml/ext/2.2">
  <Document>
    <name>旧版格式轨迹</name>
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
      <name>起点</name>
      <description><![CDATA[<div>经度：115.900100</div><div>纬度：28.700100</div>]]></description>
      <ExtendedData>
        <Data name="Longtitude"><value>115.900100</value></Data>
        <Data name="Latitude"><value>28.700100</value></Data>
      </ExtendedData>
    </Placemark>
    <Placemark>
      <name>旧版照片A</name>
      <description><![CDATA[<img src="https://cdn.example.com/old1.jpg"/>]]></description>
      <ExtendedData>
        <Data name="Longtitude"><value>115.900200</value></Data>
        <Data name="Latitude"><value>28.700200</value></Data>
        <Data name="Time"><value>{_OLD_EPOCH_MS}</value></Data>
      </ExtendedData>
    </Placemark>
  </Document>
</kml>
"""

# 新版格式：Point + TimeStamp/when（UTC）
NEW_KML = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>新版格式轨迹</name>
    <Placemark>
      <name>轨迹</name>
      <LineString><coordinates>115.900100,28.700100,20 115.900200,28.700200,21</coordinates></LineString>
    </Placemark>
    <Placemark>
      <name>新版照片B</name>
      <description><![CDATA[<img src="https://cdn.example.com/new1.jpg"/>]]></description>
      <TimeStamp><when>2026-09-08T02:45:00Z</when></TimeStamp>
      <Point><coordinates>115.900300,28.700300,23.0</coordinates></Point>
    </Placemark>
  </Document>
</kml>
"""

# 上传管道用 fixture KML（与 test_track.py 同口径，2 张照片）
FIXTURE_KML = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2" xmlns:gx="http://www.google.com/kml/ext/2.2">
  <Document>
    <name>语义分析测试轨迹</name>
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
      </ExtendedData>
    </Placemark>
    <Placemark>
      <name>照片2</name>
      <Point><coordinates>115.900300,28.700300,23.0</coordinates></Point>
      <ExtendedData>
        <Data name="photo_url"><value>https://cdn.example.com/photo2.jpg</value></Data>
        <Data name="time"><value>2026-09-08T10:50:00Z</value></Data>
      </ExtendedData>
    </Placemark>
  </Document>
</kml>
"""

GEOCODE_RESULT = {
    "province": "河南省",
    "city": "洛阳市",
    "district": "洛龙区",
    "street": "隋唐洛阳城国家遗址公园",
    "poi": "天街遗址",
    "address": "河南省洛阳市洛龙区隋唐洛阳城国家遗址公园天街遗址",
}


def _jpeg(color=(120, 140, 160), size=(80, 60)) -> bytes:
    image = Image.new("RGB", size, color)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


@pytest.fixture()
def api(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test_semantic.db'}",
        connect_args={"check_same_thread": False},
    )
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    monkeypatch.setattr(settings, "TRACK_STORAGE_DIR", str(tmp_path / "tracks"))
    monkeypatch.setattr(settings, "SURVEY_REPORT_DIR", str(tmp_path / "reports"))
    monkeypatch.setattr(track_service, "SessionLocal", testing_session)
    monkeypatch.setattr(track_service, "_GEOCODE_CACHE", None)

    async def fake_download(url, *, timeout=60):  # noqa: ANN001, ARG001
        return _jpeg()

    def fake_geocode(latitude, longitude):  # noqa: ANN001, ARG001
        return dict(GEOCODE_RESULT)

    def fake_describe(image_bytes, prompt, *, timeout=60, **kwargs):  # noqa: ANN001, ARG001
        return json.dumps(
            {
                "description": "画面为隋唐洛阳城遗址展示区，可见夯土墩台与介绍展板，游客沿天街步道参观。",
                "caption": "隋唐洛阳城遗址展示区",
                "tags": ["隋唐洛阳城", "遗址本体", "展板"],
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(track_service, "download_image", fake_download)
    monkeypatch.setattr(track_service, "geocode", fake_geocode)
    monkeypatch.setattr(track_service, "describe_image", fake_describe)

    app = FastAPI()
    from app.api.track import router as track_router

    app.include_router(track_router, prefix="/api/track")

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client, testing_session


@pytest.mark.parametrize("text,expected", CLASSIFY_CASES)
def test_classify_text_cases(text, expected):
    assert classify_text(text) == expected


def test_classify_priority_digital_over_restoration():
    # D 优先于 B：既含「复原建筑」又含「互动触摸屏」时归 D
    assert classify_text("复原建筑内的互动触摸屏") == "D"


def test_parse_old_format_kml_photo():
    result = parse_kml_bytes(OLD_KML.encode("utf-8"))

    assert len(result.points) == 3
    # 起点标注无照片 URL，不计入照片点
    assert len(result.photos) == 1
    photo = result.photos[0]
    assert photo.url == "https://cdn.example.com/old1.jpg"
    assert photo.longitude == pytest.approx(115.900200)
    assert photo.latitude == pytest.approx(28.700200)
    assert photo.shot_time is not None
    assert photo.shot_time.day == 8
    assert photo.shot_time.hour == 10
    assert photo.shot_time.minute == 45


def test_parse_new_format_kml_photo():
    result = parse_kml_bytes(NEW_KML.encode("utf-8"))

    assert len(result.points) == 2
    assert len(result.photos) == 1
    photo = result.photos[0]
    assert photo.url == "https://cdn.example.com/new1.jpg"
    assert photo.longitude == pytest.approx(115.900300)
    assert photo.latitude == pytest.approx(28.700300)
    # gx:when 的 UTC(02:45Z) 换算到 Asia/Shanghai 后为 10:45
    assert photo.shot_time is not None and photo.shot_time.hour == 10


def test_cluster_photos_splits_on_time_gap():
    base = datetime(2026, 9, 8, 10, 0, 0)
    photos = [
        TrackPhoto(track_id=1, seq=0, shot_time=base, longitude=115.9000, latitude=28.7000),
        TrackPhoto(track_id=1, seq=1, shot_time=base + timedelta(minutes=2), longitude=115.9002, latitude=28.7002),
        TrackPhoto(track_id=1, seq=2, shot_time=base + timedelta(minutes=12), longitude=115.9002, latitude=28.7002),
    ]

    clusters = cluster_photos(photos)

    assert len(clusters) == 2
    assert [len(group) for group in clusters] == [2, 1]


def _upload(client: TestClient) -> int:
    response = client.post(
        "/api/track/upload",
        files={"file": ("语义分析.kml", FIXTURE_KML.encode("utf-8"), "application/vnd.google-earth.kml+xml")},
    )
    assert response.status_code == 200, response.text
    return response.json()["track_id"]


def test_analysis_endpoints_and_persistence(api, tmp_path):
    client, _ = api
    track_id = _upload(client)

    analyzed = client.post(f"/api/track/{track_id}/analyze")
    assert analyzed.status_code == 200, analyzed.text
    payload = analyzed.json()

    photo_count = payload["photo_count"]
    assert photo_count == 2
    assert sum(item["count"] for item in payload["composition"]) == photo_count
    assert len(payload["spacetime"]) == photo_count
    assert payload["clusters"]
    assert payload["photo_density_per_km"] is not None and payload["photo_density_per_km"] > 0

    analysis_file = Path(settings.track_storage_dir) / str(track_id) / "analysis.json"
    assert analysis_file.exists()

    cached = client.get(f"/api/track/{track_id}/analysis")
    assert cached.status_code == 200
    assert cached.json()["generated_at"] == payload["generated_at"]

    csv_response = client.get(f"/api/track/{track_id}/analysis.csv")
    assert csv_response.status_code == 200
    lines = csv_response.content.decode("utf-8-sig").strip().splitlines()
    assert len(lines) == photo_count + 1

    compared = client.get(f"/api/track/analysis/compare?ids={track_id}")
    assert compared.status_code == 200, compared.text
    body = compared.json()
    assert body["items"]
    assert body["items"][0]["track_id"] == track_id
    assert body["items"][0]["composition"]


def _photo_with_type(seq: int, code: str, shot_time: datetime | None = None) -> TrackPhoto:
    """构造带运行期语义类型的照片对象（build_sequence_analysis 读取 _semantic_type）。"""
    photo = TrackPhoto(track_id=1, seq=seq, shot_time=shot_time)
    photo._semantic_type = code  # noqa: SLF001
    return photo


def test_build_sequence_analysis_counts_and_entropy():
    base = datetime(2026, 9, 8, 10, 0, 0)
    photos = [
        _photo_with_type(0, "A", base),
        _photo_with_type(1, "A", base + timedelta(minutes=1)),
        _photo_with_type(2, "C", base + timedelta(minutes=2)),
        _photo_with_type(3, "C", base + timedelta(minutes=3)),
        _photo_with_type(4, "A", base + timedelta(minutes=4)),
        _photo_with_type(5, "A", base + timedelta(minutes=5)),
    ]

    result = build_sequence_analysis(photos)

    assert result["order"] == ["A", "B", "C", "D", "E", "F", "G"]
    # 守恒：转移次数 = 照片数 - 1
    assert sum(sum(row) for row in result["counts"]) == len(photos) - 1
    assert result["counts"][0][0] == 2      # A→A
    assert result["counts"][0][2] == 1      # A→C
    assert result["counts"][2][2] == 1      # C→C
    assert result["counts"][2][0] == 1      # C→A
    # 行概率：非零行和为 1，零行为 None（B 从未作为起点）
    assert sum(result["probs"][0]) == pytest.approx(1, abs=0.01)
    assert result["probs"][1] is None
    # 分布 A=4/6, C=2/6 的 Shannon 熵
    assert result["entropy_bits"] == pytest.approx(0.92, abs=0.01)
    # 优势路径：prob 为条件概率 P(to|from)，排除自转移
    transitions = {(item["from"], item["to"]): item["prob"] for item in result["top_transitions"]}
    assert transitions[("C", "A")] == pytest.approx(0.5, abs=0.001)
    assert transitions[("A", "C")] == pytest.approx(0.333, abs=0.001)


def test_build_sequence_analysis_single_type_zero_entropy():
    base = datetime(2026, 9, 8, 10, 0, 0)
    photos = [_photo_with_type(i, "A", base + timedelta(minutes=i)) for i in range(5)]

    result = build_sequence_analysis(photos)

    assert result["entropy_bits"] == 0.0
    assert result["counts"][0][0] == 4
    assert result["top_transitions"] == []  # 仅自转移，无优势跨类路径


def test_build_spatial_analysis_clustered_points():
    # 20 个点：4 组各 5 点，组内约 1 m、组间约 500 m → 凸包面域大、实测最近邻极小，强集聚
    photos = []
    seq = 0
    for d_lon, d_lat in ((0.0, 0.0), (0.0052, 0.0), (0.0, 0.0045), (0.0052, 0.0045)):
        for i in range(5):
            photos.append(
                TrackPhoto(
                    track_id=1,
                    seq=seq,
                    longitude=115.9000 + d_lon + i * 0.00001,
                    latitude=28.7000 + d_lat + i * 0.00001,
                )
            )
            seq += 1

    result = build_spatial_analysis(photos)

    assert result["point_count"] == 20
    assert result["hull_area_km2"] > 0
    assert result["mean_nn_distance_m"] is not None and result["mean_nn_distance_m"] < 5
    assert result["nni"] is not None and 0 < result["nni"] < 0.5
    assert result["dbscan_clusters"] == 4
    assert result["noise_ratio"] == 0.0


def test_build_spatial_analysis_two_dbscan_groups():
    # 两组各 4 点，组内间距约 10 m，组间约 1 km
    photos = []
    for group, offset in enumerate((0.0, 0.0100)):
        for i in range(4):
            photos.append(
                TrackPhoto(
                    track_id=1,
                    seq=group * 4 + i,
                    longitude=115.9000 + offset + i * 0.0001,
                    latitude=28.7000 + offset,
                )
            )

    result = build_spatial_analysis(photos)

    assert result["dbscan_eps_m"] == 100.0
    assert result["dbscan_min_samples"] == 3
    assert result["dbscan_clusters"] == 2
    assert result["noise_ratio"] == 0.0


def test_build_spatial_analysis_too_few_points_returns_null_nni():
    photos = [
        TrackPhoto(track_id=1, seq=i, longitude=115.9000 + i * 0.0001, latitude=28.7000)
        for i in range(3)
    ]

    result = build_spatial_analysis(photos)

    assert result["nni"] is None   # 点位数 < 4，NNI 不定义
    assert result["dbscan_clusters"] == 1  # 三点互相在 100 m 内，成一个簇
    assert result["mean_nn_distance_m"] == pytest.approx(9.8, abs=0.2)  # 相邻点约 9.8 m


def test_analysis_requires_photos(api):
    client, testing_session = api

    # 无照片轨迹：直接构造一条空轨迹记录
    from app.models.track import TrackFile

    db = testing_session()
    empty = TrackFile(original_name="empty.kml", status="done", photo_count=0)
    db.add(empty)
    db.commit()
    empty_id = empty.id
    db.close()

    response = client.post(f"/api/track/{empty_id}/analyze")
    assert response.status_code == 400
    assert "无法分析" in response.json()["detail"]
