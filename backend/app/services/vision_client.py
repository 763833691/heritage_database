"""公共视觉调用客户端（OpenAI 兼容 /chat/completions + image_url）。

本模块从 ``app/kg/services/scanned_pdf_extractor.py`` 中**抽取复制**视觉调用能力，
作为全平台公共的多模态入口（扫描件 OCR、田野调研照片语义描述等共用）。

原始文件 `scanned_pdf_extractor.py` 保持不变；本模块不引入任何新依赖（httpx + Pillow）。
端点配置统一读取 ``settings.openai_base_url`` / ``settings.openai_api_key`` /
``settings.openai_vision_model``，可无缝切换豆包（火山方舟）、通义千问-vl 等兼容端点。
"""
from __future__ import annotations

import base64
import io
import os

import httpx
from PIL import Image

from app.core.config import settings
from app.core.model_router import resolve_model


def load_vision_config() -> dict[str, str]:
    """读取视觉模型配置。

    优先使用模型路由 ``vision.describe``；未配置路由时回落到原有 openai_* 配置
    （与 scanned_pdf_extractor.load_vision_config 行为一致）。
    """
    resolved = resolve_model("vision.describe")
    if resolved is not None:
        if not resolved.api_key:
            raise RuntimeError(
                f"模型路由 vision.describe -> '{resolved.alias}' 未配置可用的 API Key。"
            )
        return {
            "base_url": resolved.base_url,
            "api_key": resolved.api_key,
            "model": resolved.model,
        }

    api_key = (settings.openai_api_key or os.getenv("LLM_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("未配置视觉模型 API Key。请在 .env 中设置 OPENAI_API_KEY 或 LLM_API_KEY。")

    base_url = (
        settings.openai_base_url
        or os.getenv("LLM_BASE_URL")
        or "https://api.openai.com/v1"
    ).strip().rstrip("/")
    model = (
        settings.openai_vision_model
        or os.getenv("LLM_MODEL")
        or settings.openai_model
        or "gpt-4o-mini"
    ).strip()
    return {"base_url": base_url, "api_key": api_key, "model": model}


def encode_image_to_base64(image_bytes: bytes, max_size: int = 1600) -> str:
    """将图片缩放压缩为 JPEG 并编码为 base64（复用扫描件 OCR 的缩放逻辑）。"""
    image = Image.open(io.BytesIO(image_bytes))
    if image.mode != "RGB":
        image = image.convert("RGB")
    width, height = image.size
    largest_side = max(width, height)
    if largest_side > max_size:
        scale = max_size / largest_side
        image = image.resize(
            (max(1, int(width * scale)), max(1, int(height * scale))),
            Image.Resampling.LANCZOS,
        )
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _extract_message_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "\n".join(parts)
    return str(content or "")


def describe_image(
    image_bytes: bytes,
    prompt: str,
    *,
    timeout: int = 60,
    system_prompt: str = "你是文化遗产数字化助手，只输出被要求的内容，不要输出解释性废话。",
) -> str:
    """调用多模态模型描述一张图片，返回模型文本。

    与 ``scanned_pdf_extractor.recognize_page_with_vision`` 使用同一 OpenAI 兼容通道：
    ``POST {base_url}/chat/completions``，图片以 base64 data URL 放在 ``image_url`` 中。
    """
    config = load_vision_config()
    image_base64 = encode_image_to_base64(image_bytes)
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"},
                },
            ],
        },
    ]
    with httpx.Client(timeout=timeout) as client:
        response = client.post(
            f"{config['base_url']}/chat/completions",
            headers={
                "Authorization": f"Bearer {config['api_key']}",
                "Content-Type": "application/json",
            },
            json={"model": config["model"], "messages": messages, "temperature": 0},
        )
    if response.status_code >= 400:
        raise RuntimeError(f"视觉模型请求失败 HTTP {response.status_code}: {response.text[:1000]}")

    payload = response.json()
    text = _extract_message_text(
        payload.get("choices", [{}])[0].get("message", {}).get("content", "")
    ).strip()
    if not text:
        raise RuntimeError("视觉模型返回空文本")
    return text
