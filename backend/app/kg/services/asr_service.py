"""语音转写：腾讯云「录音文件识别极速版」FlashRecognizer。

原实现为独立的 Node/Express 服务（asr-service），此处按官方协议以 Python 重写，
保持相同的云端接口、签名算法（HMAC-SHA1）与返回结构，便于与 FastAPI 一起部署。

文档：https://cloud.tencent.com/document/product/1093/52097
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from typing import Any

import httpx

from app.core.config import settings

ASR_HOST = "asr.cloud.tencent.com"
SUPPORTED_FORMATS = {"mp3", "m4a"}


class AsrError(Exception):
    def __init__(self, message: str, *, status: int = 500, code: str = "ASR_ERROR") -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code


def _assert_credentials() -> None:
    missing = [
        name
        for name, value in (
            ("TENCENT_APP_ID", settings.TENCENT_APP_ID),
            ("TENCENT_SECRET_ID", settings.TENCENT_SECRET_ID),
            ("TENCENT_SECRET_KEY", settings.TENCENT_SECRET_KEY),
        )
        if not value
    ]
    if missing:
        raise AsrError(
            f"腾讯云凭证未配置，请在 .env 中填写：{', '.join(missing)}",
            status=500,
            code="CREDENTIALS_MISSING",
        )


def build_signed_request(voice_format: str) -> tuple[str, str]:
    """返回 (请求 URL, Authorization 签名)。"""
    _assert_credentials()
    params = {
        "secretid": settings.TENCENT_SECRET_ID,
        "engine_type": settings.ASR_ENGINE_TYPE,
        "voice_format": voice_format,
        "timestamp": str(int(time.time())),
        "convert_num_mode": "1",
        "filter_dirty": "0",
        "filter_modal": "0",
        "filter_punc": "0",
        "first_channel_only": "1",
        "speaker_diarization": "0",
        "word_info": "0",
    }
    query = "&".join(f"{key}={params[key]}" for key in sorted(params))
    path_with_query = f"/asr/flash/v1/{settings.TENCENT_APP_ID}?{query}"
    sign_str = f"POST{ASR_HOST}{path_with_query}"
    digest = hmac.new(
        settings.TENCENT_SECRET_KEY.encode("utf-8"),
        sign_str.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    return f"https://{ASR_HOST}{path_with_query}", base64.b64encode(digest).decode("ascii")


def resolve_voice_format(filename: str) -> str | None:
    suffix = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    if suffix == ".mp3":
        return "mp3"
    if suffix == ".m4a":
        return "m4a"
    return None


def extract_text(flash_result: Any) -> str:
    if not isinstance(flash_result, list) or not flash_result:
        return ""
    return "\n".join(
        channel.get("text", "") for channel in flash_result if isinstance(channel, dict) and channel.get("text")
    ).strip()


async def recognize(audio_bytes: bytes, voice_format: str) -> dict[str, Any]:
    if voice_format not in SUPPORTED_FORMATS:
        raise AsrError("仅支持 m4a / mp3 音频文件", status=400, code="UNSUPPORTED_EXTENSION")
    if not audio_bytes:
        raise AsrError("音频数据为空", status=400, code="EMPTY_AUDIO")

    url, authorization = build_signed_request(voice_format)

    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=20.0)) as client:
        response = await client.post(
            url,
            content=audio_bytes,
            headers={
                "Host": ASR_HOST,
                "Authorization": authorization,
                "Content-Type": "application/octet-stream",
                "Content-Length": str(len(audio_bytes)),
            },
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise AsrError(
            f"腾讯云返回非 JSON 响应（HTTP {response.status_code}）",
            status=502,
            code="INVALID_UPSTREAM_RESPONSE",
        ) from exc

    if response.status_code >= 400 or data.get("code") != 0:
        raise AsrError(
            data.get("message") or f"腾讯云识别失败（code={data.get('code', response.status_code)}）",
            status=502,
            code="TENCENT_ASR_ERROR",
        )

    return {
        "text": extract_text(data.get("flash_result")),
        "audio_duration_ms": data.get("audio_duration"),
        "request_id": data.get("request_id"),
        "flash_result": data.get("flash_result") or [],
    }
