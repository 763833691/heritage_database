"""AI 模型路由：按任务把请求解析到不同模型。

设计约束（对齐 docs/08「不臃肿三原则」）：
- 本模块只做**配置解析 + 路由解析**，不实现任何 AI 调用；
- 文本对话仍由 ``services/llm_provider.py`` 执行，视觉仍由 ``services/vision_client.py`` 执行；
- 未配置 ``MODEL_ROUTES`` 时 ``resolve_model()`` 返回 ``None``，调用方保持原有行为完全不变。

配置示例（写入 .env）::

    MODEL_REGISTRY={"deepseek": {"type": "text",  "base_url": "https://api.deepseek.com", "model": "deepseek-v4-pro", "api_key_env": "OPENAI_API_KEY"},
                    "qwen-vl": {"type": "vision", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-vl-max", "api_key_env": "DASHSCOPE_API_KEY"}}
    MODEL_ROUTES={"text.chat": "deepseek", "vision.describe": "qwen-vl"}
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

from .config import settings
from .database import SessionLocal

# 任务名 -> 所需能力。新增任务在此登记即可被路由覆盖。
TASK_CAPABILITIES: dict[str, str] = {
    "text.chat": "text",          # 报告撰写、要点抽取、实体关系抽取等文本任务
    "vision.describe": "vision",  # 照片语义描述 + 报告图注
    "vision.ocr": "vision",       # 扫描件 OCR（text_parse_pipeline 的 pdf_extract 阶段）
}

TASK_LABELS: dict[str, str] = {
    "text.chat": "文本对话（报告撰写 / 要点抽取）",
    "vision.describe": "照片语义描述与图注",
    "vision.ocr": "扫描件 OCR（PDF 图片识别）",
}

# 能力别名归一化：multimodal/any 表示文本与视觉皆可
_CAPABILITY_ALIASES = {
    "text": "text",
    "llm": "text",
    "chat": "text",
    "vision": "vision",
    "vl": "vision",
    "image": "vision",
    "multimodal": "any",
    "any": "any",
}


def normalize_capability(value: object) -> str:
    """归一化模型能力名：text / vision / any（multimodal 视为两者皆可）。"""
    text = str(value or "").strip().lower()
    return _CAPABILITY_ALIASES.get(text, text or "any")


def required_capability(task: str) -> str:
    return TASK_CAPABILITIES.get(task, "any")


@dataclass
class ResolvedModel:
    task: str
    alias: str
    capability: str
    base_url: str
    api_key: str
    model: str
    timeout: Optional[int] = None
    source: str = "settings"  # db / settings


def _entry_api_key(alias: str, entry: dict) -> str:
    explicit = str(entry.get("api_key") or "").strip()
    if explicit:
        return explicit
    env_name = str(entry.get("api_key_env") or "").strip()
    if env_name:
        return (os.getenv(env_name) or "").strip()
    return (settings.openai_api_key or "").strip()


def _alias_for(task: str, routes: dict) -> Optional[str]:
    """任务名优先，其次按能力名（text/vision）路由。"""
    capability = required_capability(task)
    for key in (task, capability):
        alias = routes.get(key)
        if isinstance(alias, str) and alias.strip():
            return alias.strip()
    return None


def resolve_row_api_key(row) -> str:
    """解析数据库模型行的 API Key：显式加密 Key 优先，其次 api_key_env 指定的环境变量。

    刻意**不**回落到全局 ``openai_api_key``，避免把别家厂商的 Key 用到当前模型上。
    """
    from .crypto import decrypt_secret

    explicit = decrypt_secret(row.api_key_encrypted)
    if explicit:
        return explicit
    env_name = (row.api_key_env or "").strip()
    if env_name:
        return (os.getenv(env_name) or "").strip()
    return ""


def _model_from_row(task: str, row) -> ResolvedModel:
    capability = normalize_capability(row.capability)
    required = required_capability(task)
    if required != "any" and capability not in (required, "any"):
        raise ValueError(f"任务 '{task}' 需要 {required} 能力，但模型 '{row.alias}' 类型为 {capability}")
    if not row.enabled:
        raise ValueError(f"任务 '{task}' 路由到模型 '{row.alias}'，但该模型未启用")

    base_url = (row.base_url or "").strip().rstrip("/")
    if not base_url:
        raise ValueError(f"模型 '{row.alias}' 未配置 base_url")

    api_key = resolve_row_api_key(row)
    if not api_key:
        raise ValueError(f"模型 '{row.alias}' 未配置 API Key")

    return ResolvedModel(
        task=task,
        alias=row.alias,
        capability=capability,
        base_url=base_url,
        api_key=api_key,
        model=row.model,
        source="db",
    )


def _db_resolution(task: str) -> Optional[ResolvedModel]:
    """从数据库解析任务路由（任务名优先，其次能力名）。无记录返回 None。"""
    db = SessionLocal()
    try:
        from ..models.ai_model import AIModel, AIModelRoute

        route = db.query(AIModelRoute).filter(AIModelRoute.task == task).first()
        if route is None:
            capability = required_capability(task)
            if capability != "any":
                route = db.query(AIModelRoute).filter(AIModelRoute.task == capability).first()
        if route is None:
            return None
        row = db.get(AIModel, route.model_id)
        if row is None:
            raise ValueError(f"任务 '{task}' 的路由指向不存在的模型 #{route.model_id}")
        return _model_from_row(task, row)
    except ValueError:
        raise
    except Exception:
        # 表尚未创建等场景：视为未配置，保持旧行为
        return None
    finally:
        db.close()


def resolve_model(task: str) -> Optional[ResolvedModel]:
    """解析某任务应使用的模型。

    优先级：数据库路由 → ``MODEL_ROUTES`` 配置 → ``None``（调用方使用原有默认配置）。
    已配置但启用状态/类型/字段非法时抛出 ``ValueError``，避免静默走错模型。
    """
    resolved = _db_resolution(task)
    if resolved is not None:
        return resolved

    routes = settings.model_routes
    if not routes:
        return None
    alias = _alias_for(task, routes)
    if alias is None:
        return None

    registry = settings.model_registry
    entry = registry.get(alias)
    if not isinstance(entry, dict):
        raise ValueError(f"MODEL_ROUTES 引用了未注册的模型别名 '{alias}'")

    model = str(entry.get("model") or "").strip()
    if not model:
        raise ValueError(f"模型 '{alias}' 未配置 model")

    capability = normalize_capability(entry.get("type", "any"))
    required = required_capability(task)
    if required != "any" and capability not in (required, "any"):
        raise ValueError(
            f"任务 '{task}' 需要 {required} 能力，但模型 '{alias}' 类型为 {capability}"
        )

    base_url = str(entry.get("base_url") or settings.openai_base_url or "").strip().rstrip("/")
    if not base_url:
        raise ValueError(f"模型 '{alias}' 未配置 base_url")

    timeout_raw = entry.get("timeout")
    timeout = int(timeout_raw) if isinstance(timeout_raw, (int, float, str)) and str(timeout_raw).strip().isdigit() else None

    return ResolvedModel(
        task=task,
        alias=alias,
        capability=capability,
        base_url=base_url,
        api_key=_entry_api_key(alias, entry),
        model=model,
        timeout=timeout,
        source="settings",
    )


def validate_routes() -> list[str]:
    """启动时校验配置，返回问题列表（不抛异常，便于日志输出）。"""
    issues: list[str] = []
    routes = settings.model_routes
    registry = settings.model_registry
    if routes and not registry:
        issues.append("MODEL_ROUTES 已配置但 MODEL_REGISTRY 为空")
    if registry and not routes:
        issues.append("MODEL_REGISTRY 已配置但 MODEL_ROUTES 为空，路由不会生效")
    for alias, entry in registry.items():
        if not isinstance(entry, dict):
            issues.append(f"MODEL_REGISTRY['{alias}'] 必须是对象")
            continue
        if not str(entry.get("model") or "").strip():
            issues.append(f"MODEL_REGISTRY['{alias}'] 缺少 model")
        if not str(entry.get("base_url") or "").strip() and not settings.openai_base_url:
            issues.append(f"MODEL_REGISTRY['{alias}'] 缺少 base_url")
    for task in TASK_CAPABILITIES:
        try:
            resolved = resolve_model(task)
        except ValueError as exc:
            issues.append(str(exc))
            continue
        if resolved is not None and not resolved.api_key:
            issues.append(f"任务 '{task}' 路由到 '{resolved.alias}'，但未解析到 API Key")
    return issues


def describe_routes() -> list[dict]:
    """返回各任务的路由解析结果（API Key 不返回明文），用于启动日志/诊断。"""
    rows: list[dict] = []
    for task in TASK_CAPABILITIES:
        row = {"task": task, "capability": required_capability(task), "label": TASK_LABELS.get(task, task),
               "alias": None, "model": None, "base_url": None, "key_set": False, "source": None, "error": None}
        try:
            resolved = resolve_model(task)
        except ValueError as exc:
            row["error"] = str(exc)
            rows.append(row)
            continue
        if resolved is not None:
            row.update(
                alias=resolved.alias,
                model=resolved.model,
                base_url=urlparse(resolved.base_url).hostname or resolved.base_url,
                key_set=bool(resolved.api_key),
                source=resolved.source,
            )
        rows.append(row)
    return rows
