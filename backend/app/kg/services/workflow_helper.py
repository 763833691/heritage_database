from __future__ import annotations

from app.kg.schemas import FileItem, ProcessStatus


TEXT_PARSE_DONE_MARKERS = ("文本解析完成", "原文已就绪", "泰标流水线执行完成", "阶段 mineru_text_recognition 执行完成")


def normalize_process_status(item: FileItem) -> ProcessStatus:
    ps = item.process_status

    if item.status == "processed" and item.process_result:
        ps.workflow_phase = "completed"
        ps.text_parse_confirmed = True
        ps.export_ready = True
        if ps.progress < 100:
            ps.progress = 100
        if ps.current_step in {"等待处理", "关系抽取", "实体识别", "图谱构建"}:
            ps.current_step = "处理完成"
        return ps

    if item.process_result and ps.text_parse_confirmed:
        ps.workflow_phase = "export"
        ps.export_ready = True
        if ps.progress < 67:
            ps.progress = max(ps.progress, 67)
        return ps

    if ps.text_parse_confirmed:
        ps.workflow_phase = "graph_build"
        if ps.progress < 34:
            ps.progress = 34
        return ps

    if ps.progress >= 33 or any(marker in ps.current_step for marker in TEXT_PARSE_DONE_MARKERS):
        ps.workflow_phase = "text_parse"
        if ps.progress < 33:
            ps.progress = 33
        if ps.current_step in {"等待处理", "等待调度"}:
            ps.current_step = "文本解析完成，待确认"
        return ps

    ps.workflow_phase = "text_parse"
    return ps


def text_parse_ready(item: FileItem) -> bool:
    ps = normalize_process_status(item)
    return ps.progress >= 33 or any(marker in ps.current_step for marker in TEXT_PARSE_DONE_MARKERS)
