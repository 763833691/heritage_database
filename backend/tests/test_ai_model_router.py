"""模型注册表与任务路由测试：加密、播种、DB 优先解析、CRUD/路由/探活接口。

运行：
    cd backend
    python -m pytest tests/test_ai_model_router.py -q
"""
from __future__ import annotations

import json
import types

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core import crypto, model_router
from app.core.config import settings
from app.core.database import Base, get_db
from app.core.model_router import resolve_model
from app.models.ai_model import AIModel, AIModelRoute
from app.services import ai_model_service, vision_client

TEXT_MODEL = {
    "alias": "unit-text",
    "display_name": "单测文本模型",
    "provider_type": "openai_compatible",
    "capability": "text",
    "base_url": "https://text.example.com/v1",
    "model": "unit-text-1",
    "api_key": "sk-unit-text-1234",
    "enabled": True,
}
VISION_MODEL = {
    "alias": "unit-vision",
    "display_name": "单测视觉模型",
    "provider_type": "openai_compatible",
    "capability": "vision",
    "base_url": "https://vision.example.com/v1",
    "model": "unit-vision-1",
    "api_key": "sk-unit-vision-5678",
    "enabled": True,
}


@pytest.fixture()
def ai_env(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'ai.db'}",
        connect_args={"check_same_thread": False},
    )
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    monkeypatch.setattr(model_router, "SessionLocal", testing_session)
    monkeypatch.setattr(settings, "MODEL_REGISTRY", "")
    monkeypatch.setattr(settings, "MODEL_ROUTES", "")

    from app.api.ai_models import router as ai_router

    app = FastAPI()
    app.include_router(ai_router, prefix="/api/ai")

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client, testing_session


def _db_session(testing_session):
    return testing_session()


def _add_model(db, payload: dict) -> AIModel:
    row = ai_model_service.create_model(db, dict(payload))
    return row


# ==================== 加密 ====================


def test_crypto_roundtrip_hint_and_plaintext_compat():
    secret = "sk-abcdefghijklmnop"
    encrypted = crypto.encrypt_secret(secret)
    assert encrypted.startswith("enc:v1:")
    assert secret not in encrypted
    assert crypto.decrypt_secret(encrypted) == secret
    assert crypto.secret_hint(encrypted) == "****mnop"

    # 历史明文（无前缀）按原样读取
    assert crypto.decrypt_secret("sk-plain") == "sk-plain"
    # 空值与坏密文
    assert crypto.encrypt_secret("") == ""
    assert crypto.decrypt_secret("enc:v1:not-a-token") == ""


# ==================== 播种 ====================


def test_seed_presets_is_idempotent(ai_env):
    _, testing_session = ai_env
    db = _db_session(testing_session)
    first = ai_model_service.seed_presets(db)
    assert first > 0
    assert ai_model_service.seed_presets(db) == 0

    rows = db.query(AIModel).all()
    assert len(rows) == first
    assert all(not row.enabled for row in rows), "预置模型必须默认停用"
    assert all(not row.api_key_encrypted for row in rows), "预置模型不得带密钥"
    db.close()


# ==================== DB 路由优先 ====================


def test_db_route_takes_precedence_over_settings(ai_env, monkeypatch):
    _, testing_session = ai_env
    monkeypatch.setattr(
        settings,
        "MODEL_REGISTRY",
        json.dumps({"env-model": {"type": "text", "base_url": "https://env.example.com/v1", "model": "env-1", "api_key": "sk-env"}}),
    )
    monkeypatch.setattr(settings, "MODEL_ROUTES", json.dumps({"text.chat": "env-model"}))

    db = _db_session(testing_session)
    model = _add_model(db, TEXT_MODEL)
    ai_model_service.set_route(db, "text.chat", model.id)
    db.close()

    resolved = resolve_model("text.chat")
    assert resolved is not None
    assert resolved.source == "db"
    assert resolved.alias == "unit-text"
    assert resolved.model == "unit-text-1"
    assert resolved.api_key == "sk-unit-text-1234"


def test_settings_route_used_when_no_db_route(ai_env, monkeypatch):
    monkeypatch.setattr(
        settings,
        "MODEL_REGISTRY",
        json.dumps({"env-model": {"type": "text", "base_url": "https://env.example.com/v1", "model": "env-1", "api_key": "sk-env"}}),
    )
    monkeypatch.setattr(settings, "MODEL_ROUTES", json.dumps({"text.chat": "env-model"}))
    resolved = resolve_model("text.chat")
    assert resolved is not None and resolved.source == "settings"


def test_disabled_model_route_raises(ai_env):
    _, testing_session = ai_env
    db = _db_session(testing_session)
    model = _add_model(db, {**TEXT_MODEL, "enabled": False})
    ai_model_service.set_route(db, "text.chat", model.id)
    db.close()

    with pytest.raises(ValueError, match="未启用"):
        resolve_model("text.chat")


def test_route_requires_matching_capability(ai_env):
    _, testing_session = ai_env
    db = _db_session(testing_session)
    text_model = _add_model(db, TEXT_MODEL)
    with pytest.raises(ValueError, match="需要 vision 能力"):
        ai_model_service.set_route(db, "vision.describe", text_model.id)

    vision_model = _add_model(db, VISION_MODEL)
    ai_model_service.set_route(db, "vision.describe", vision_model.id)
    assert resolve_model("vision.describe").alias == "unit-vision"
    db.close()


def test_list_routes_reports_error_for_unusable_route(ai_env):
    _, testing_session = ai_env
    db = _db_session(testing_session)
    model = _add_model(db, {**VISION_MODEL, "api_key": ""})
    ai_model_service.set_route(db, "vision.describe", model.id)
    rows = ai_model_service.list_routes(db)
    vision_row = next(row for row in rows if row["task"] == "vision.describe")
    assert vision_row["error"] and "API Key" in vision_row["error"]
    assert vision_row["resolved"] is None
    db.close()


def test_env_backed_key_is_usable_and_reported_ready(ai_env, monkeypatch):
    _, testing_session = ai_env
    monkeypatch.delenv("UNIT_VISION_KEY", raising=False)
    db = _db_session(testing_session)
    model = _add_model(db, {**VISION_MODEL, "api_key": "", "api_key_env": "UNIT_VISION_KEY"})
    ai_model_service.set_route(db, "vision.describe", model.id)

    # 环境变量未设置：不可用，且序列化标记未就绪
    assert ai_model_service.serialize_model(model)["key_ready"] is False
    with pytest.raises(ValueError, match="API Key"):
        resolve_model("vision.describe")

    # 设置环境变量后即可用
    monkeypatch.setenv("UNIT_VISION_KEY", "sk-from-env")
    payload = ai_model_service.serialize_model(model)
    assert payload["key_ready"] is True
    assert payload["env_key_available"] is True
    assert payload["has_api_key"] is False
    assert resolve_model("vision.describe").api_key == "sk-from-env"
    db.close()


def test_vision_client_picks_up_db_route(ai_env):
    _, testing_session = ai_env
    db = _db_session(testing_session)
    model = _add_model(db, VISION_MODEL)
    ai_model_service.set_route(db, "vision.describe", model.id)
    db.close()

    config = vision_client.load_vision_config()
    assert config["model"] == "unit-vision-1"
    assert config["base_url"] == "https://vision.example.com/v1"
    assert config["api_key"] == "sk-unit-vision-5678"


def test_scanned_pdf_extractor_picks_up_ocr_route(ai_env):
    _, testing_session = ai_env
    db = _db_session(testing_session)
    model = _add_model(db, VISION_MODEL)
    ai_model_service.set_route(db, "vision.ocr", model.id)
    db.close()

    scanned_pdf = pytest.importorskip("app.kg.services.scanned_pdf_extractor")
    config = scanned_pdf.load_vision_config()
    assert config["model"] == "unit-vision-1"
    assert config["base_url"] == "https://vision.example.com/v1"
    assert config["api_key"] == "sk-unit-vision-5678"


# ==================== 接口 ====================


def test_api_crud_masks_key_and_keeps_on_empty_patch(ai_env):
    client, _ = ai_env
    created = client.post("/api/ai/models", json=TEXT_MODEL)
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["alias"] == "unit-text"
    assert body["has_api_key"] is True
    assert body["api_key_hint"] == "****1234"
    assert "sk-unit-text-1234" not in created.text, "接口不得回传明文 Key"

    # 重复别名
    assert client.post("/api/ai/models", json=TEXT_MODEL).status_code == 409

    # 空 api_key 表示保持不变
    patched = client.patch(f"/api/ai/models/{body['id']}", json={"display_name": "改名", "api_key": ""})
    assert patched.status_code == 200
    assert patched.json()["display_name"] == "改名"
    assert patched.json()["has_api_key"] is True

    # __clear__ 清空
    cleared = client.patch(f"/api/ai/models/{body['id']}", json={"api_key": "__clear__"})
    assert cleared.json()["has_api_key"] is False

    listed = client.get("/api/ai/models").json()["items"]
    assert any(item["alias"] == "unit-text" for item in listed)
    assert client.delete(f"/api/ai/models/{body['id']}").status_code == 200
    assert client.get("/api/ai/models").json()["items"] == []


def test_api_route_assignment_and_status(ai_env):
    client, _ = ai_env
    seed = client.post("/api/ai/models/seed")
    assert seed.status_code == 200 and seed.json()["created"] > 0
    models = client.get("/api/ai/models").json()["items"]
    text_model = next(item for item in models if item["capability"] == "text")

    # 未配 Key 时启用并路由：状态里应给出明确错误
    client.patch(f"/api/ai/models/{text_model['id']}", json={"enabled": True})
    assigned = client.put("/api/ai/routes/text.chat", json={"model_id": text_model["id"]})
    assert assigned.status_code == 200, assigned.text

    status = client.get("/api/ai/status").json()
    task_row = next(row for row in status["items"] if row["task"] == "text.chat")
    assert task_row["error"] and "API Key" in task_row["error"]

    # 补上 Key 后即可解析
    client.patch(f"/api/ai/models/{text_model['id']}", json={"api_key": "sk-seeded-key"})
    status = client.get("/api/ai/status").json()
    task_row = next(row for row in status["items"] if row["task"] == "text.chat")
    assert task_row["alias"] == text_model["alias"]
    assert task_row["source"] == "db"

    # 能力不匹配的路由被拒绝
    vision_model = next(item for item in models if item["capability"] == "vision")
    conflict = client.put("/api/ai/routes/text.chat", json={"model_id": vision_model["id"]})
    assert conflict.status_code == 422

    # 清空路由
    assert client.put("/api/ai/routes/text.chat", json={"model_id": None}).status_code == 200


def test_api_model_probe(ai_env, monkeypatch):
    client, _ = ai_env

    class _FakeResponse:
        status_code = 200
        text = "{}"

    class _FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, *args, **kwargs):
            return _FakeResponse()

    monkeypatch.setattr(ai_model_service, "httpx", types.SimpleNamespace(Client=_FakeClient))

    created = client.post("/api/ai/models", json=TEXT_MODEL).json()
    result = client.post(f"/api/ai/models/{created['id']}/test").json()
    assert result["ok"] is True and result["supported"] is True
    assert "latency_ms" in result


def test_database_route_absent_returns_none(ai_env):
    # 未配置任何 DB 路由且无 env JSON 时，保持旧行为（返回 None）
    assert resolve_model("text.chat") is None
    assert resolve_model("vision.describe") is None
