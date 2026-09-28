"""统计接口测试：数据概览扩展字段与公园 × 指标评分矩阵。

运行：
    cd backend
    python -m pytest tests/test_statistics.py -q
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.models.indicator import Indicator
from app.models.park import Park
from app.models.score import Score
from app.models.survey import SurveyEvent, SurveyTask
from app.models.track import TrackFile, TrackPhoto


def _build_client(tmp_path) -> TestClient:
    engine = create_engine(f"sqlite:///{tmp_path / 'statistics.db'}")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)

    db = session_factory()
    park = Park(name="测试公园", short_name="测试", park_type="城市型", province="河南省", city="洛阳市")
    db.add(park)
    db.commit()
    indicators = [
        Indicator(code="D1", name="遗址本体展示", dimension="遗址展示效果"),
        Indicator(code="D2", name="周边环境协调度", dimension="遗址展示效果"),
    ]
    db.add_all(indicators)
    db.commit()
    db.add_all([
        Score(park_id=park.id, indicator_id=indicators[0].id, normalized_score=80, grade="好", evidence="依据一"),
        Score(park_id=park.id, indicator_id=indicators[1].id, normalized_score=60, grade="一般"),
    ])
    task = SurveyTask(title="测试任务", park_id=park.id)
    db.add(task)
    db.commit()
    track = TrackFile(original_name="a.kml", status="done", survey_task_id=task.id, photo_count=2, distance_meters=1500.0)
    db.add(track)
    db.commit()
    db.add_all([TrackPhoto(track_id=track.id, seq=0), TrackPhoto(track_id=track.id, seq=1)])
    db.add(SurveyEvent(task_id=task.id, title="事件"))
    db.commit()
    db.close()

    app = FastAPI()
    from app.api.statistics import router

    app.include_router(router, prefix="/api/statistics")

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_overview_field_research_and_score_matrix(tmp_path):
    client = _build_client(tmp_path)

    overview = client.get("/api/statistics/overview").json()
    assert overview["field_research"] == {
        "track_count": 1,
        "photo_count": 2,
        "event_count": 1,
        "park_count": 1,
        "track_distance_km": 1.5,
    }

    matrix = client.get("/api/statistics/score-matrix").json()
    assert len(matrix["parks"]) == 1 and len(matrix["indicators"]) == 2
    assert len(matrix["cells"]) == 2
    assert matrix["dimensions"] == [{"dimension": "遗址展示效果", "codes": ["D1", "D2"]}]
    first = next(cell for cell in matrix["cells"] if cell["indicator_id"] == 1)
    assert first["score"] == 80 and first["grade"] == "好" and first["evidence"] == "依据一"
