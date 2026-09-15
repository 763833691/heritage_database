r"""知识图谱子系统接口测试：文件库 → 文本解析 → 图谱构建 → 图谱查询 → 语音转写。

运行：
    cd backend
    python -m pytest tests/test_kg_system.py -v
"""

from __future__ import annotations

import asyncio
import importlib
import os
import tempfile
from pathlib import Path

# 必须在导入 app.* 之前指定隔离存储目录（服务在导入时解析路径）
_TMP_STORAGE = tempfile.mkdtemp(prefix="kg-test-")
os.environ["KG_STORAGE_DIR"] = _TMP_STORAGE
os.environ["NEO4J_ENABLED"] = "0"
os.environ["OPENAI_API_KEY"] = ""
os.environ.pop("LLM_API_KEY", None)

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.kg.api import kg_router  # noqa: E402
from app.kg.services.file_service import file_service  # noqa: E402
from app.kg.services.graph_repository import graph_repository  # noqa: E402

SAMPLE_TEXT = (
    "大明宫位于唐长安城北部，是唐代重要宫殿。"
    "大明宫包含含元殿和宣政殿。"
    "丝绸之路以长安为起点，连接西域和中亚。"
    "唐高宗扩建大明宫。"
)


def build_client() -> TestClient:
    app = FastAPI()
    app.include_router(kg_router, prefix="/api")
    asyncio.run(file_service.init())
    asyncio.run(graph_repository.init())
    return TestClient(app)


def unwrap(payload: dict):
    assert payload["code"] in (0, 2), payload
    return payload["data"]


def test_nlp_extract_returns_entities_and_relations():
    client = build_client()
    response = client.post("/api/nlp/extract", json={"text": SAMPLE_TEXT})
    assert response.status_code == 200
    data = unwrap(response.json())
    names = {entity["name"] for entity in data["entities"]}
    assert "大明宫" in names
    assert data["relations"], "应至少抽取出一条关系"


def test_file_vault_and_graph_flow():
    client = build_client()

    created = unwrap(client.post("/api/file/tasks", json={"doc_code": "KG-001", "title": "大明宫资料"}).json())
    file_id = created["file_id"]
    assert created["status"] == "created"

    upload = client.post(
        f"/api/file/{file_id}/upload",
        files={"file": ("大明宫资料.txt", SAMPLE_TEXT.encode("utf-8"), "text/plain")},
    )
    assert upload.status_code == 200
    assert unwrap(upload.json())["status"] == "uploaded"

    listing = unwrap(client.get("/api/file/list").json())
    assert any(item["id"] == file_id for item in listing["files"])

    pipeline = unwrap(client.get(f"/api/process/{file_id}/text-pipeline").json())
    assert pipeline["parse_mode"] in {"text", "unknown", "auto_detect"}

    assert unwrap(client.post(f"/api/process/{file_id}").json())["phase"] == "text_parse"
    status = unwrap(client.get(f"/api/process/{file_id}/status").json())
    assert status["progress"] >= 33, status
    assert status["workflow_phase"] == "text_parse"
    assert status["text_parse_confirmed"] is False

    confirmed = unwrap(client.post(f"/api/process/{file_id}/confirm-text-parse").json())
    assert confirmed["status"] == "confirmed"

    build = unwrap(client.post(f"/api/process/{file_id}/graph-build/run", json={"method": "entity_relation"}).json())
    assert build["phase"] == "graph_build"

    result = unwrap(client.get(f"/api/process/{file_id}/result").json())
    assert result["entities"], "图谱构建应产出实体"
    assert result["graph"]["nodes"]

    full_graph = unwrap(client.get("/api/graph/full").json())
    assert len(full_graph["nodes"]) >= len(result["entities"])
    assert full_graph["edges"]

    search = unwrap(client.get("/api/graph/search", params={"q": "大明宫"}).json())
    assert any("大明宫" in node.get("name", "") for node in search["nodes"])

    node_id = result["graph"]["nodes"][0]["data"]["id"]
    subgraph = unwrap(client.get(f"/api/graph/node/{node_id}").json())
    assert subgraph["nodes"]


def test_system_status_reports_local_storage():
    client = build_client()
    data = unwrap(client.get("/api/system/status").json())
    assert data["storage_mode"] == "local"
    assert data["graph_nodes"] >= 0
    assert data["file_count"] >= 0
    assert data["max_upload_mb"] > 0


def test_asr_transcribe_requires_credentials():
    client = build_client()
    response = client.post(
        "/api/asr/transcribe",
        files={"file": ("voice.mp3", b"fake-audio-bytes", "audio/mpeg")},
    )
    assert response.status_code == 500
    assert "腾讯云凭证未配置" in response.json()["detail"]


def test_asr_rejects_unsupported_format():
    client = build_client()
    response = client.post(
        "/api/asr/transcribe",
        files={"file": ("voice.wav", b"fake-audio-bytes", "audio/wav")},
    )
    assert response.status_code == 400


def test_recover_interrupted_endpoint():
    client = build_client()
    data = unwrap(client.post("/api/system/recover-interrupted").json())
    assert "reset_files" in data
    assert Path(_TMP_STORAGE).exists()
