from __future__ import annotations

import base64
import io
import os
from typing import Callable

import fitz
import httpx
from PIL import Image

from app.core.config import settings

HERITAGE_PAGE_PROMPT = """你是文物遗产与历史文献数字化助手。

任务：识别图片中的全部正文内容，并输出原文 Markdown。

要求：
1. 不要翻译，保持原文语言（通常为中文）。
2. 保留标题层级、章节编号、列表与表格结构。
3. 不要擅自补充图片中不存在的内容。
4. 无法识别的内容用 [unclear] 标记。
5. 数字、单位、符号必须忠实保留。
6. 只输出 Markdown 正文，不要输出解释性废话。

这是文档第 {page_num} 页（共 {total_pages} 页）。"""

SYSTEM_PROMPT = "你是文献数字化助手。只输出原文 Markdown，不要翻译。"


def load_vision_config() -> dict[str, str]:
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


def encode_image_bytes_to_base64(png_bytes: bytes, max_size: int = 1600) -> str:
    image = Image.open(io.BytesIO(png_bytes))
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


def render_pdf_pages(
    pdf_bytes: bytes,
    *,
    zoom: float = 2.0,
    max_pages: int | None = None,
) -> list[bytes]:
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        total_pages = document.page_count
        page_limit = min(total_pages, max_pages) if max_pages else total_pages
        matrix = fitz.Matrix(zoom, zoom)
        images: list[bytes] = []
        for page_index in range(page_limit):
            page = document.load_page(page_index)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            images.append(pixmap.tobytes("png"))
        return images
    finally:
        document.close()


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


def recognize_page_with_vision(
    config: dict[str, str],
    page_png: bytes,
    *,
    page_num: int,
    total_pages: int,
    timeout: int | None = None,
) -> str:
    image_base64 = encode_image_bytes_to_base64(page_png)
    prompt = HERITAGE_PAGE_PROMPT.format(page_num=page_num, total_pages=total_pages)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
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
    request_timeout = timeout or settings.scanned_pdf_timeout_seconds
    with httpx.Client(timeout=request_timeout) as client:
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


def is_sparse_pdf_text(text: str, page_count: int, min_chars_per_page: float | None = None) -> bool:
    cleaned = text.strip()
    if not cleaned:
        return True
    threshold = min_chars_per_page if min_chars_per_page is not None else settings.scanned_pdf_min_chars_per_page
    pages = max(1, page_count)
    return len(cleaned) / pages < threshold


def extract_scanned_pdf_with_vision(
    pdf_bytes: bytes,
    *,
    zoom: float | None = None,
    max_pages: int | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> tuple[str, int]:
    config = load_vision_config()
    resolved_zoom = zoom if zoom is not None else settings.scanned_pdf_zoom
    resolved_max_pages = max_pages if max_pages is not None else settings.scanned_pdf_max_pages
    page_images = render_pdf_pages(pdf_bytes, zoom=resolved_zoom, max_pages=resolved_max_pages)
    if not page_images:
        raise ValueError("PDF 无有效页面")

    total_pages = len(page_images)
    page_texts: list[str] = []
    for index, page_png in enumerate(page_images, start=1):
        if progress_callback:
            progress_callback(index, total_pages)
        page_texts.append(
            recognize_page_with_vision(
                config,
                page_png,
                page_num=index,
                total_pages=total_pages,
            )
        )

    text = "\n\n".join(chunk.strip() for chunk in page_texts if chunk.strip()).strip()
    if not text:
        raise ValueError("视觉模型未识别到文本")
    return text, total_pages
