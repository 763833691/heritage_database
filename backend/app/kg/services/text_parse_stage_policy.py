from __future__ import annotations

from typing import Any, Literal

StageStatus = Literal["pending", "running", "success", "failed", "skipped"]

TEXT_PARSE_STAGES = [
    "import_file",
    "format_detect",
    "content_read",
    "caj_decrypt",
    "pdf_extract",
    "text_decode",
    "text_clean",
    "paragraph_split",
    "persist_result",
]

STAGE_LABELS: dict[str, str] = {
    "import_file": "文件导入",
    "format_detect": "格式检测",
    "content_read": "内容读取",
    "caj_decrypt": "CAJ/KDH 解密",
    "pdf_extract": "PDF 文本提取",
    "text_decode": "文本解码",
    "text_clean": "文本清洗",
    "paragraph_split": "段落切分",
    "persist_result": "成果落盘",
}

STAGE_HINTS: dict[str, str] = {
    "import_file": "校验上传文件是否就绪",
    "format_detect": "识别 PDF / CAJ / TXT / MD 等格式",
    "content_read": "读取原始字节流",
    "caj_decrypt": "对 CAJ/KDH 执行解密并提取内嵌 PDF",
    "pdf_extract": "PDF 文本提取（pypdf / 视觉模型 OCR）",
    "text_decode": "对纯文本文件执行 UTF-8 解码",
    "text_clean": "归一化空白与噪声字符",
    "paragraph_split": "按句段切分结构化段落",
    "persist_result": "写入 extracted.txt 与 manifest.json",
}

PARSE_MODE_LABELS: dict[str, str] = {
    "auto_detect": "自动检测",
    "digital_pdf": "数字 PDF",
    "scanned_pdf": "扫描 PDF",
    "caj": "CAJ/KDH",
    "pdf": "PDF",
    "text": "纯文本",
    "unknown": "未知格式",
}


def stage_index(stage: str) -> int:
    try:
        return TEXT_PARSE_STAGES.index(stage)
    except ValueError:
        return -1


def next_stage(stage: str) -> str | None:
    index = stage_index(stage)
    if index < 0 or index >= len(TEXT_PARSE_STAGES) - 1:
        return None
    return TEXT_PARSE_STAGES[index + 1]


def should_skip_stage(stage: str, parse_mode: str) -> bool:
    if stage == "caj_decrypt":
        return parse_mode not in {"caj", "auto_detect"}
    if stage == "pdf_extract":
        return parse_mode not in {"pdf", "caj", "scanned_pdf"}
    if stage == "text_decode":
        return parse_mode not in {"text", "unknown"}
    return False


def derive_stage_status(stage: str, state: dict[str, Any]) -> dict[str, Any]:
    completed = set(state.get("completed_stages", []))
    running_stage = state.get("running_stage")
    failed_stage = state.get("failed_stage")
    parse_mode = state.get("parse_mode", "auto_detect")
    skipped = set(state.get("skipped_stages", []))

    if stage in skipped or (stage in completed and state.get("stage_results", {}).get(stage) == "skipped"):
        return _stage_payload(stage, "skipped", 100, "已跳过", True, None)

    if failed_stage == stage:
        message = state.get("error_message") or "阶段执行失败"
        return _stage_payload(stage, "failed", 0, message, True, None)

    if running_stage == stage:
        progress = int(state.get("stage_progress", {}).get(stage, 30))
        return _stage_payload(stage, "running", progress, "执行中", False, None)

    if stage in completed:
        detail = state.get("stage_messages", {}).get(stage, "已完成")
        return _stage_payload(stage, "success", 100, detail, True, None)

    blocked_reason = _blocked_reason(stage, state, completed, skipped, parse_mode)
    can_run = blocked_reason is None
    return _stage_payload(stage, "pending", 0, "等待中", can_run, blocked_reason)


def _blocked_reason(
    stage: str,
    state: dict[str, Any],
    completed: set[str],
    skipped: set[str],
    parse_mode: str,
) -> str | None:
    if state.get("running_stage"):
        return "其他阶段正在运行"
    index = stage_index(stage)
    if index <= 0:
        return None
    for previous in TEXT_PARSE_STAGES[:index]:
        if previous in skipped:
            continue
        if previous not in completed:
            return f"需先完成「{STAGE_LABELS[previous]}」"
    if should_skip_stage(stage, parse_mode) and stage not in completed:
        return None
    return None


def _stage_payload(
    stage: str,
    status: StageStatus,
    progress: int,
    message: str,
    can_run: bool,
    blocked_reason: str | None,
) -> dict[str, Any]:
    return {
        "stage": stage,
        "label": STAGE_LABELS[stage],
        "hint": STAGE_HINTS[stage],
        "status": status,
        "progress": progress,
        "message": message,
        "can_run": can_run,
        "blocked_reason": blocked_reason,
        "is_rerunnable": status in {"success", "failed", "skipped"},
        "action_label": "运行阶段" if status != "running" else "运行中",
    }


def build_pipeline_status(file_id: str, state: dict[str, Any]) -> dict[str, Any]:
    stages = [derive_stage_status(stage, state) for stage in TEXT_PARSE_STAGES]
    completed_count = sum(1 for stage in stages if stage["status"] == "success")
    skipped_count = sum(1 for stage in stages if stage["status"] == "skipped")
    overall = int(((completed_count + skipped_count) / len(TEXT_PARSE_STAGES)) * 100)
    if state.get("running_stage"):
        running = derive_stage_status(state["running_stage"], state)
        overall = min(99, overall + max(1, running["progress"] // 10))

    return {
        "file_id": file_id,
        "current_stage": state.get("running_stage") or state.get("last_completed_stage"),
        "overall_progress": overall,
        "parse_mode": state.get("parse_mode", "auto_detect"),
        "parse_mode_label": PARSE_MODE_LABELS.get(state.get("parse_mode", "auto_detect"), "自动检测"),
        "char_count": state.get("char_count", 0),
        "paragraph_count": state.get("paragraph_count", 0),
        "page_count": state.get("page_count", 0),
        "stages": stages,
        "logs": state.get("logs", [])[-200:],
        "artifacts": state.get("artifacts", []),
        "status": state.get("pipeline_status", "idle"),
    }
