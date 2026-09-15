from __future__ import annotations

import os

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.config import settings
from app.kg.response import ok
from app.kg.services.asr_service import AsrError, recognize, resolve_voice_format

router = APIRouter()

ALLOWED_MIME_TYPES = {
    "audio/mp4",
    "audio/m4a",
    "audio/x-m4a",
    "audio/mpeg",
    "audio/mp3",
}


@router.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    """音频转写（m4a / mp3，最大 20MB），返回识别文本。"""
    filename = file.filename or ""
    voice_format = resolve_voice_format(filename)
    content_type = (file.content_type or "").lower()

    if voice_format is None:
        raise HTTPException(status_code=400, detail="仅支持 m4a / mp3 音频文件")
    if content_type and content_type not in ALLOWED_MIME_TYPES and not content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="仅支持 m4a / mp3 音频文件")

    raw = await file.read()
    if len(raw) > settings.asr_max_upload_size:
        raise HTTPException(
            status_code=413,
            detail=f"文件过大，最大允许 {settings.ASR_MAX_UPLOAD_MB}MB",
        )

    try:
        result = await recognize(raw, voice_format)
    except AsrError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message) from exc

    return ok(
        {
            "success": True,
            "text": result["text"],
            "audio_duration_ms": result["audio_duration_ms"],
            "request_id": result["request_id"],
            "filename": os.path.basename(filename),
            "size": len(raw),
            "voice_format": voice_format,
            "engine_type": settings.ASR_ENGINE_TYPE,
            "flash_result": result["flash_result"],
        }
    )
