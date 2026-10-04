"""公园封面上传/读取/删除测试。

运行：
    cd backend
    python -m pytest tests/test_park_cover.py -q
"""
from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 - 注册全部模型
from app.api.admin import router as admin_router
from app.api.parks import router as parks_router
from app.core.auth import get_admin_user
from app.core.config import settings
from app.core.database import Base, get_db
from app.models.park import Park

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"kilo-cover-test"


def _build_client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "PARK_COVER_DIR", str(tmp_path / "parks"))
    engine = create_engine(f"sqlite:///{tmp_path / 'cover.db'}")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)

    db = session_factory()
    park = Park(name="封面测试公园", short_name="封面", park_type="城市型", province="河南省", city="洛阳市")
    db.add(park)
    db.commit()
    park_id = park.id
    db.close()

    app = FastAPI()
    app.include_router(admin_router, prefix="/api/admin")
    app.include_router(parks_router, prefix="/api/parks")
    app.dependency_overrides[get_db] = lambda: session_factory()
    app.dependency_overrides[get_admin_user] = lambda: SimpleNamespace(id=1, username="admin")
    return TestClient(app), session_factory, park_id


def test_upload_serve_and_delete_cover(tmp_path, monkeypatch):
    client, session_factory, park_id = _build_client(tmp_path, monkeypatch)

    upload = client.post(
        f"/api/admin/parks/{park_id}/cover",
        files={"file": ("cover.png", PNG_BYTES, "image/png")},
    )
    assert upload.status_code == 200
    assert f"/api/parks/{park_id}/cover" in upload.json()["cover_image"]

    db = session_factory()
    park = db.query(Park).filter(Park.id == park_id).first()
    assert park.cover_image == f"{park_id}/cover.png"
    assert (settings.park_cover_dir / park.cover_image).exists()
    db.close()

    served = client.get(f"/api/parks/{park_id}/cover")
    assert served.status_code == 200
    assert served.content == PNG_BYTES

    public = client.get("/api/parks", params={"page_size": 1}).json()
    assert public["items"][0]["cover_image"]  # 列表接口暴露封面 URL

    removed = client.delete(f"/api/admin/parks/{park_id}/cover")
    assert removed.status_code == 200
    assert client.get(f"/api/parks/{park_id}/cover").status_code == 404


def test_upload_rejects_non_image(tmp_path, monkeypatch):
    client, _, park_id = _build_client(tmp_path, monkeypatch)
    response = client.post(
        f"/api/admin/parks/{park_id}/cover",
        files={"file": ("notes.txt", b"not an image", "text/plain")},
    )
    assert response.status_code == 400
