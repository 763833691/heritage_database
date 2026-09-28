"""AI 模型路由测试：按任务分配模型、能力校验、旧配置回落。

运行：
    cd backend
    python -m pytest tests/test_model_router.py -q
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core import model_router
from app.core.config import settings
from app.core.database import Base
from app.core.model_router import describe_routes, resolve_model, validate_routes
from app.services import llm_provider, vision_client

TEXT_MODEL = {"type": "text", "base_url": "https://text.example.com/v1", "model": "deepseek-chat", "api_key": "sk-text"}
VISION_MODEL = {
    "type": "vision",
    "base_url": "https://vision.example.com/compatible-mode/v1",
    "model": "qwen-vl-max",
    "api_key_env": "TEST_VISION_KEY",
}


@pytest.fixture(autouse=True)
def _isolate_routes(tmp_path, monkeypatch):
    """隔离数据库路由：DB 优先级高于 .env，避免开发库里已配置的路由干扰断言。"""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'model_router.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(model_router, "SessionLocal", sessionmaker(autocommit=False, autoflush=False, bind=engine))

    monkeypatch.setattr(settings, "MODEL_REGISTRY", "")
    monkeypatch.setattr(settings, "MODEL_ROUTES", "")
    monkeypatch.delenv("TEST_VISION_KEY", raising=False)


def _configure(monkeypatch, registry: dict, routes: dict) -> None:
    monkeypatch.setattr(settings, "MODEL_REGISTRY", json.dumps(registry))
    monkeypatch.setattr(settings, "MODEL_ROUTES", json.dumps(routes))


def test_unconfigured_router_keeps_legacy_behavior():
    assert resolve_model("text.chat") is None
    assert resolve_model("vision.describe") is None
    assert validate_routes() == []
    assert all(row["alias"] is None for row in describe_routes())


def test_routes_text_and_vision_to_different_models(monkeypatch):
    monkeypatch.setenv("TEST_VISION_KEY", "sk-vision")
    _configure(
        monkeypatch,
        {"deepseek": TEXT_MODEL, "qwen-vl": VISION_MODEL},
        {"text.chat": "deepseek", "vision.describe": "qwen-vl"},
    )

    text = resolve_model("text.chat")
    assert text is not None
    assert (text.alias, text.model, text.capability) == ("deepseek", "deepseek-chat", "text")
    assert text.api_key == "sk-text"

    vision = resolve_model("vision.describe")
    assert vision is not None
    assert (vision.alias, vision.model) == ("qwen-vl", "qwen-vl-max")
    assert vision.api_key == "sk-vision"

    issues = validate_routes()
    assert issues == []


def test_route_by_capability_name(monkeypatch):
    _configure(monkeypatch, {"qwen-vl": VISION_MODEL}, {"vision": "qwen-vl"})
    resolved = resolve_model("vision.describe")
    assert resolved is not None and resolved.alias == "qwen-vl"
    assert resolve_model("text.chat") is None


def test_capability_mismatch_raises(monkeypatch):
    _configure(monkeypatch, {"deepseek": TEXT_MODEL}, {"vision.describe": "deepseek"})
    with pytest.raises(ValueError, match="需要 vision 能力"):
        resolve_model("vision.describe")
    assert any("vision.describe" in issue for issue in validate_routes())


def test_unknown_alias_raises(monkeypatch):
    _configure(monkeypatch, {"deepseek": TEXT_MODEL}, {"text.chat": "missing"})
    with pytest.raises(ValueError, match="未注册的模型别名"):
        resolve_model("text.chat")


def test_multimodal_model_serves_both_tasks(monkeypatch):
    model = {"type": "multimodal", "base_url": "https://multi.example.com/v1", "model": "gpt-4o-mini", "api_key": "sk-multi"}
    _configure(monkeypatch, {"multi": model}, {"text.chat": "multi", "vision.describe": "multi"})
    assert resolve_model("text.chat").alias == "multi"
    assert resolve_model("vision.describe").alias == "multi"


def test_vision_client_uses_router(monkeypatch):
    _configure(monkeypatch, {"qwen-vl": VISION_MODEL}, {"vision.describe": "qwen-vl"})
    monkeypatch.setenv("TEST_VISION_KEY", "sk-vision")
    config = vision_client.load_vision_config()
    assert config["model"] == "qwen-vl-max"
    assert config["base_url"] == "https://vision.example.com/compatible-mode/v1"
    assert config["api_key"] == "sk-vision"


def test_llm_provider_uses_text_route(monkeypatch):
    _configure(monkeypatch, {"deepseek": TEXT_MODEL}, {"text.chat": "deepseek"})
    provider = llm_provider.get_llm_provider()
    assert isinstance(provider, llm_provider.OpenAIProvider)
    assert provider.model == "deepseek-chat"
    assert provider.base_url == "https://text.example.com/v1"


def test_describe_routes_does_not_leak_api_key(monkeypatch):
    monkeypatch.setenv("TEST_VISION_KEY", "sk-secret-value")
    _configure(
        monkeypatch,
        {"deepseek": TEXT_MODEL, "qwen-vl": VISION_MODEL},
        {"text.chat": "deepseek", "vision.describe": "qwen-vl"},
    )
    rows = describe_routes()
    assert all("sk-secret-value" not in json.dumps(row, ensure_ascii=False) for row in rows)
    vision_row = next(row for row in rows if row["task"] == "vision.describe")
    assert vision_row["key_set"] is True
    assert vision_row["base_url"] == "vision.example.com"


def test_validate_routes_flags_registry_without_routes(monkeypatch):
    monkeypatch.setattr(settings, "MODEL_REGISTRY", json.dumps({"deepseek": TEXT_MODEL}))
    issues = validate_routes()
    assert any("MODEL_ROUTES" in issue for issue in issues)
