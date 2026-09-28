"""模型注册表与任务路由的服务层：CRUD、探活、预置播种。

不实现任何模型调用；实际推理仍由 llm_provider（文本）与 vision_client（视觉）执行。
"""
from __future__ import annotations

import os
import time
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from ..core.crypto import decrypt_secret, encrypt_secret, secret_hint
from ..core.model_router import (
    TASK_CAPABILITIES,
    TASK_LABELS,
    normalize_capability,
    required_capability,
    resolve_row_api_key,
)
from ..models.ai_model import AIModel, AIModelRoute
from .ai_presets import PRESET_MODELS

PROBE_TIMEOUT_SECONDS = 20


def serialize_model(row: AIModel) -> dict:
    env_name = (row.api_key_env or "").strip()
    env_available = bool(env_name and (os.getenv(env_name) or "").strip())
    has_key = bool(decrypt_secret(row.api_key_encrypted))
    return {
        "id": row.id,
        "alias": row.alias,
        "display_name": row.display_name or row.alias,
        "provider_type": row.provider_type,
        "capability": normalize_capability(row.capability),
        "base_url": row.base_url,
        "model": row.model,
        "api_key_env": row.api_key_env,
        "has_api_key": has_key,
        "env_key_available": env_available,
        "key_ready": has_key or env_available,
        "api_key_hint": secret_hint(row.api_key_encrypted),
        "input_modalities": row.input_modalities or [],
        "output_modalities": row.output_modalities or [],
        "enabled": bool(row.enabled),
        "is_preset": bool(row.is_preset),
        "note": row.note,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def list_models(db: Session) -> list[dict]:
    rows = db.query(AIModel).order_by(AIModel.is_preset.desc(), AIModel.id.asc()).all()
    return [serialize_model(row) for row in rows]


def capability_conflict(task: str, capability: str) -> Optional[str]:
    required = required_capability(task)
    normalized = normalize_capability(capability)
    if required != "any" and normalized not in (required, "any"):
        return f"任务「{TASK_LABELS.get(task, task)}」需要 {required} 能力，而该模型类型为 {normalized}"
    return None


def create_model(db: Session, payload: dict) -> AIModel:
    alias = (payload.get("alias") or "").strip()
    if not alias:
        raise ValueError("模型别名不能为空")
    if db.query(AIModel).filter(AIModel.alias == alias).first():
        raise ValueError(f"模型别名 '{alias}' 已存在")

    row = AIModel(alias=alias)
    _apply_payload(row, payload, allow_alias=False)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_model(db: Session, row: AIModel, payload: dict) -> AIModel:
    _apply_payload(row, payload, allow_alias=True)
    db.commit()
    db.refresh(row)
    return row


def _apply_payload(row: AIModel, payload: dict, *, allow_alias: bool) -> None:
    if allow_alias and payload.get("alias"):
        row.alias = str(payload["alias"]).strip()
    for field in ("display_name", "provider_type", "base_url", "model", "api_key_env", "note"):
        if field in payload and payload[field] is not None:
            setattr(row, field, str(payload[field]).strip())
    if payload.get("capability") is not None:
        row.capability = normalize_capability(payload["capability"])
    if payload.get("input_modalities") is not None:
        row.input_modalities = list(payload["input_modalities"])
    if payload.get("output_modalities") is not None:
        row.output_modalities = list(payload["output_modalities"])
    if payload.get("enabled") is not None:
        row.enabled = bool(payload["enabled"])
    # api_key 传空字符串表示「保持不变」，传 None 亦保持不变；传 "__clear__" 表示清空
    raw_key = payload.get("api_key")
    if raw_key == "__clear__":
        row.api_key_encrypted = None
    elif raw_key not in (None, ""):
        row.api_key_encrypted = encrypt_secret(str(raw_key))


def delete_model(db: Session, row: AIModel) -> None:
    db.delete(row)  # 关联路由由 cascade 一并删除
    db.commit()


def list_routes(db: Session) -> list[dict]:
    from ..core.model_router import resolve_model

    route_map = {route.task: route for route in db.query(AIModelRoute).all()}
    rows: list[dict] = []
    for task, capability in TASK_CAPABILITIES.items():
        route = route_map.get(task)
        model = db.get(AIModel, route.model_id) if route else None
        payload = {
            "task": task,
            "label": TASK_LABELS.get(task, task),
            "capability": capability,
            "model_id": model.id if model else None,
            "model_alias": model.alias if model else None,
            "enabled": bool(model.enabled) if model else False,
            "resolved": None,
            "error": None,
        }
        try:
            resolved = resolve_model(task)
        except ValueError as exc:
            payload["error"] = str(exc)
            resolved = None
        if resolved is not None:
            payload["resolved"] = {
                "alias": resolved.alias,
                "model": resolved.model,
                "source": resolved.source,
                "capability": resolved.capability,
            }
        rows.append(payload)
    return rows


def set_route(db: Session, task: str, model_id: Optional[int]) -> Optional[AIModelRoute]:
    if task not in TASK_CAPABILITIES:
        raise ValueError(f"未知任务 '{task}'")
    route = db.query(AIModelRoute).filter(AIModelRoute.task == task).first()
    if model_id is None:
        if route is not None:
            db.delete(route)
            db.commit()
        return None

    model = db.get(AIModel, model_id)
    if model is None:
        raise ValueError(f"模型 #{model_id} 不存在")
    conflict = capability_conflict(task, model.capability)
    if conflict:
        raise ValueError(conflict)

    if route is None:
        route = AIModelRoute(task=task, model_id=model.id)
        db.add(route)
    else:
        route.model_id = model.id
    db.commit()
    return route


def probe_model(row: AIModel, *, timeout: int = PROBE_TIMEOUT_SECONDS) -> dict:
    """连通性探活：向 /chat/completions 发一条最小请求。"""
    capability = normalize_capability(row.capability)
    if capability not in ("text", "vision", "any"):
        return {
            "ok": False,
            "supported": False,
            "message": f"类型 {capability} 暂不支持连通性测试，请用实际任务验证",
        }

    api_key = resolve_row_api_key(row)
    if not api_key:
        return {"ok": False, "supported": True, "message": "未配置 API Key"}

    url = f"{(row.base_url or '').rstrip('/')}/chat/completions"
    started = time.perf_counter()
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                url,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": row.model,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 1,
                    "temperature": 0,
                },
            )
        latency = int((time.perf_counter() - started) * 1000)
        if response.status_code >= 400:
            return {
                "ok": False,
                "supported": True,
                "latency_ms": latency,
                "message": f"HTTP {response.status_code}: {response.text[:300]}",
            }
        return {"ok": True, "supported": True, "latency_ms": latency, "message": "连接正常"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "supported": True, "message": f"请求失败: {exc}"[:300]}


def seed_presets(db: Session) -> int:
    """播种预置模型（仅新增缺失别名，不带 Key、默认停用）。"""
    existing = {row[0] for row in db.query(AIModel.alias).all()}
    created = 0
    for preset in PRESET_MODELS:
        if preset["alias"] in existing:
            continue
        db.add(
            AIModel(
                alias=preset["alias"],
                display_name=preset.get("display_name"),
                provider_type=preset.get("provider_type", "openai_compatible"),
                capability=normalize_capability(preset.get("capability", "text")),
                base_url=preset["base_url"],
                model=preset["model"],
                api_key_env=preset.get("api_key_env"),
                input_modalities=preset.get("input_modalities", []),
                output_modalities=preset.get("output_modalities", []),
                enabled=False,
                is_preset=True,
                note=preset.get("note"),
            )
        )
        created += 1
    if created:
        db.commit()
    return created
