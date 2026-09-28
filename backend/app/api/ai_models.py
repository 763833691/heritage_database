"""AI 模型注册表与任务路由接口（挂在 /api/ai）。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.auth import get_admin_user, get_current_user
from ..core.database import get_db
from ..core.model_router import TASK_CAPABILITIES, TASK_LABELS, describe_routes
from ..models.ai_model import AIModel
from ..models.user import User
from ..services import ai_model_service

router = APIRouter()


class ModelPayload(BaseModel):
    alias: str = Field(min_length=1, max_length=80)
    display_name: Optional[str] = None
    provider_type: Optional[str] = None
    capability: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    api_key_env: Optional[str] = None
    input_modalities: Optional[list[str]] = None
    output_modalities: Optional[list[str]] = None
    enabled: Optional[bool] = None
    note: Optional[str] = None


class ModelPatch(BaseModel):
    alias: Optional[str] = Field(default=None, max_length=80)
    display_name: Optional[str] = None
    provider_type: Optional[str] = None
    capability: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    api_key_env: Optional[str] = None
    input_modalities: Optional[list[str]] = None
    output_modalities: Optional[list[str]] = None
    enabled: Optional[bool] = None
    note: Optional[str] = None


class RoutePayload(BaseModel):
    model_id: Optional[int] = None


def _get_model(db: Session, model_id: int) -> AIModel:
    row = db.get(AIModel, model_id)
    if row is None:
        raise HTTPException(status_code=404, detail="模型不存在")
    return row


@router.get("/tasks")
def list_tasks(current_user: User = Depends(get_current_user)):
    """可选任务清单（供界面做路由下拉）。"""
    return {
        "items": [
            {"task": task, "label": TASK_LABELS.get(task, task), "capability": capability}
            for task, capability in TASK_CAPABILITIES.items()
        ]
    }


@router.get("/models")
def list_models(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return {"items": ai_model_service.list_models(db)}


@router.post("/models")
def create_model(
    payload: ModelPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    data = payload.model_dump()
    if not (data.get("base_url") or "").strip() or not (data.get("model") or "").strip():
        raise HTTPException(status_code=422, detail="base_url 与 model 为必填项")
    try:
        row = ai_model_service.create_model(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return ai_model_service.serialize_model(row)


@router.patch("/models/{model_id}")
def update_model(
    model_id: int,
    payload: ModelPatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    row = _get_model(db, model_id)
    try:
        row = ai_model_service.update_model(db, row, payload.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return ai_model_service.serialize_model(row)


@router.delete("/models/{model_id}")
def delete_model(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    row = _get_model(db, model_id)
    ai_model_service.delete_model(db, row)
    return {"deleted": model_id}


@router.post("/models/{model_id}/test")
def test_model(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    row = _get_model(db, model_id)
    return ai_model_service.probe_model(row)


@router.post("/models/seed")
def seed_models(db: Session = Depends(get_db), current_user: User = Depends(get_admin_user)):
    created = ai_model_service.seed_presets(db)
    return {"created": created, "items": ai_model_service.list_models(db)}


@router.get("/routes")
def list_routes(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return {"items": ai_model_service.list_routes(db)}


@router.put("/routes/{task}")
def set_route(
    task: str,
    payload: RoutePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    try:
        ai_model_service.set_route(db, task, payload.model_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"items": ai_model_service.list_routes(db)}


@router.get("/status")
def router_status(current_user: User = Depends(get_current_user)):
    """当前生效的路由解析结果（含来源 db/settings 与错误原因）。"""
    rows = describe_routes()
    return {
        "items": rows,
        "resolved_count": sum(1 for row in rows if row.get("alias")),
        "error_count": sum(1 for row in rows if row.get("error")),
    }
