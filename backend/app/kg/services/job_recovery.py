from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.kg.schemas import ProcessStatus
from app.kg.services.file_service import file_service


def _recover_text_parse_state(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        state: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    changed = False
    if state.get("pipeline_status") == "running":
        state["pipeline_status"] = "idle"
        state["running_stage"] = None
        state.setdefault("logs", []).append(
            f"{datetime.now().strftime('%H:%M:%S')} 服务重启，文本解析已中断"
        )
        changed = True
    if changed:
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return changed


async def recover_interrupted_work() -> dict[str, int]:
    await file_service.init()
    stamp = datetime.now().strftime("%H:%M:%S")
    reset_files = 0
    reset_text_states = 0

    async with file_service._lock:
        for item in file_service.files.values():
            if item.status != "processing":
                continue
            item.status = "uploaded"
            logs = list(item.process_status.logs)
            logs.append(f"{stamp} 处理已中断，请重新运行")
            item.process_status = ProcessStatus(
                status="uploaded",
                progress=0,
                current_step="等待处理",
                logs=logs[-50:],
            )
            reset_files += 1
        if reset_files:
            await file_service._persist_locked()

    text_parse_root = settings.storage_dir / "text_parse"
    if text_parse_root.exists():
        for state_path in text_parse_root.glob("*.json"):
            if await asyncio.to_thread(_recover_text_parse_state, state_path):
                reset_text_states += 1

    return {
        "reset_files": reset_files,
        "reset_text_states": reset_text_states,
    }
