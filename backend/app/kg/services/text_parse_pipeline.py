from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

from fastapi import HTTPException

from app.core.config import settings
from app.kg.services.caj_reader import decrypt_kdh, extract_pdf_text, extract_text_from_bytes
from app.kg.services.text_parse_stage_policy import (
    PARSE_MODE_LABELS,
    STAGE_LABELS,
    TEXT_PARSE_STAGES,
    build_pipeline_status,
    should_skip_stage,
)

LogCallback = Callable[[str, str | None], Awaitable[None]]


class TextParsePipeline:
    def __init__(self) -> None:
        self.workspace = settings.storage_dir / "text_parse"
        self.workspace.mkdir(parents=True, exist_ok=True)

    def _state_path(self, file_id: str) -> Path:
        return self.workspace / f"{file_id}.json"

    def _artifact_dir(self, file_id: str) -> Path:
        path = self.workspace / file_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    async def load_state(self, file_id: str) -> dict[str, Any]:
        path = self._state_path(file_id)
        if not path.exists():
            return self._empty_state(file_id)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload.setdefault("file_id", file_id)
        return payload

    async def save_state(self, state: dict[str, Any]) -> None:
        path = self._state_path(state["file_id"])
        await asyncio.to_thread(
            path.write_text,
            json.dumps(state, ensure_ascii=False, indent=2),
            "utf-8",
        )

    def _empty_state(self, file_id: str) -> dict[str, Any]:
        return {
            "file_id": file_id,
            "pipeline_status": "idle",
            "parse_mode": "auto_detect",
            "completed_stages": [],
            "skipped_stages": [],
            "stage_messages": {},
            "stage_progress": {},
            "logs": [],
            "artifacts": [],
            "char_count": 0,
            "paragraph_count": 0,
            "page_count": 0,
            "text_path": None,
            "manifest_path": None,
        }

    async def get_status(self, file_id: str) -> dict[str, Any]:
        from app.kg.services.file_service import file_service

        await file_service.get_file(file_id)
        state = await self.load_state(file_id)
        return build_pipeline_status(file_id, state)

    async def get_preview(self, file_id: str, limit: int = 2000) -> dict[str, Any]:
        state = await self.load_state(file_id)
        text = await self._load_extracted_text(state)
        paragraphs = state.get("paragraphs", [])
        return {
            "text_preview": text[:limit],
            "char_count": state.get("char_count", len(text)),
            "paragraph_count": state.get("paragraph_count", len(paragraphs)),
            "page_count": state.get("page_count", 0),
            "paragraphs": paragraphs[:20],
            "artifacts": state.get("artifacts", []),
            "parse_mode": state.get("parse_mode", "auto_detect"),
            "parse_mode_label": PARSE_MODE_LABELS.get(state.get("parse_mode", "auto_detect"), "自动检测"),
        }

    async def reset(self, file_id: str) -> None:
        state = self._empty_state(file_id)
        await self.save_state(state)
        artifact_dir = self._artifact_dir(file_id)
        if artifact_dir.exists():
            import shutil

            await asyncio.to_thread(shutil.rmtree, artifact_dir, True)

    async def run(
        self,
        file_id: str,
        *,
        progress_callback: LogCallback | None = None,
        base_progress: int = 0,
        progress_span: int = 20,
    ) -> str:
        from app.kg.services.file_service import file_service

        item = await file_service.get_file(file_id)
        state = await self.load_state(file_id)
        state.update(self._empty_state(file_id))
        state["pipeline_status"] = "running"
        await self.save_state(state)

        context: dict[str, Any] = {
            "file_id": file_id,
            "item": item,
            "path": Path(item.content_path) if item.content_path else None,
            "raw": b"",
            "text": "",
            "paragraphs": [],
            "user_parse_mode": item.parse_mode or "auto_detect",
            "parse_mode": item.parse_mode or "auto_detect",
            "page_count": 0,
        }

        async def report(step: str, log: str, stage_index: int) -> None:
            overall = base_progress + int(((stage_index + 1) / len(TEXT_PARSE_STAGES)) * progress_span)
            if progress_callback:
                await progress_callback(step, log, min(base_progress + progress_span - 1, max(base_progress + 1, overall)))

        try:
            for index, stage in enumerate(TEXT_PARSE_STAGES):
                if should_skip_stage(stage, context["parse_mode"]) or (
                    stage == "pdf_extract" and bool(context.get("text"))
                ) or (stage == "text_decode" and bool(context.get("text"))):
                    state["skipped_stages"].append(stage)
                    state["completed_stages"].append(stage)
                    state["stage_messages"][stage] = "当前格式无需执行"
                    await self._append_log(state, f"{STAGE_LABELS[stage]}：已跳过")
                    await self.save_state(state)
                    continue

                state["running_stage"] = stage
                await self._append_log(state, f"开始执行：{STAGE_LABELS[stage]}")
                await self.save_state(state)

                handler = getattr(self, f"_stage_{stage}")
                message = await asyncio.to_thread(handler, context)
                context.update(message.pop("context_updates", {}))

                state["running_stage"] = None
                state["completed_stages"].append(stage)
                state["last_completed_stage"] = stage
                state["stage_messages"][stage] = message.get("detail", "已完成")
                state["parse_mode"] = context["parse_mode"]
                state["page_count"] = context.get("page_count", 0)
                await self._append_log(state, f"{STAGE_LABELS[stage]}：{state['stage_messages'][stage]}")
                await self.save_state(state)
                await report("文本解析", state["stage_messages"][stage], index)

            text = context["text"]
            paragraphs = context["paragraphs"]
            artifact_dir = self._artifact_dir(file_id)
            text_path = artifact_dir / "extracted.txt"
            manifest_path = artifact_dir / "manifest.json"
            manifest = {
                "file_id": file_id,
                "file_name": item.name,
                "parse_mode": context["parse_mode"],
                "char_count": len(text),
                "paragraph_count": len(paragraphs),
                "page_count": context.get("page_count", 0),
                "generated_at": datetime.now().isoformat(),
                "stages": TEXT_PARSE_STAGES,
            }
            await asyncio.to_thread(text_path.write_text, text, "utf-8")
            await asyncio.to_thread(
                manifest_path.write_text,
                json.dumps(manifest, ensure_ascii=False, indent=2),
                "utf-8",
            )

            state["text_path"] = str(text_path)
            state["manifest_path"] = str(manifest_path)
            state["char_count"] = len(text)
            state["paragraph_count"] = len(paragraphs)
            state["paragraphs"] = paragraphs
            state["artifacts"] = [
                {"file_type": "extracted_text", "name": "extracted.txt", "path": str(text_path)},
                {"file_type": "parse_manifest", "name": "manifest.json", "path": str(manifest_path)},
            ]
            state["pipeline_status"] = "success"
            state["running_stage"] = None
            await self._append_log(state, f"文本解析完成：共 {len(text)} 字、{len(paragraphs)} 段")
            await self.save_state(state)

            if progress_callback:
                await progress_callback("文本解析", "文本解析流水线完成", base_progress + progress_span)

            if not text.strip():
                raise ValueError("解析结果为空")
            return text
        except Exception as exc:
            state["pipeline_status"] = "failed"
            state["failed_stage"] = state.get("running_stage")
            state["error_message"] = str(exc)
            state["running_stage"] = None
            await self._append_log(state, f"文本解析失败：{exc}")
            await self.save_state(state)
            if progress_callback:
                await progress_callback("文本解析", f"处理失败：{exc}", base_progress)
            raise

    async def _append_log(self, state: dict[str, Any], message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        state.setdefault("logs", []).append(f"{stamp} {message}")

    async def _load_extracted_text(self, state: dict[str, Any]) -> str:
        text_path = state.get("text_path")
        if text_path and Path(text_path).exists():
            return await asyncio.to_thread(Path(text_path).read_text, "utf-8")
        paragraphs = state.get("paragraphs", [])
        if paragraphs:
            return "\n".join(paragraphs)
        return ""

    def _stage_import_file(self, context: dict[str, Any]) -> dict[str, Any]:
        path = context.get("path")
        if path is None or not path.exists():
            raise ValueError("文件不存在或缺少 content_path")
        return {"detail": f"已定位文件 {path.name}", "context_updates": {"path": path}}

    def _stage_format_detect(self, context: dict[str, Any]) -> dict[str, Any]:
        path: Path = context["path"]
        suffix = path.suffix.lower()
        user_mode = context.get("user_parse_mode", "auto_detect")
        file_format = "unknown"
        if suffix in {".caj", ".kdh"}:
            file_format = "caj"
        elif suffix == ".pdf":
            file_format = "pdf"
        elif suffix in {".txt", ".md", ".markdown", ".json"}:
            file_format = "text"
        else:
            raw = path.read_bytes()[:8]
            if raw.startswith(b"KDH") or raw.startswith(b"%PDF"):
                file_format = "caj" if raw.startswith(b"KDH") else "pdf"
            else:
                file_format = "text"

        if user_mode == "scanned_pdf" and file_format == "pdf":
            parse_mode = "scanned_pdf"
        elif user_mode == "digital_pdf" and file_format == "pdf":
            parse_mode = "pdf"
        elif user_mode in {"caj", "text"}:
            parse_mode = user_mode
        else:
            parse_mode = file_format

        return {
            "detail": f"识别为 {PARSE_MODE_LABELS.get(parse_mode, parse_mode)}",
            "context_updates": {"parse_mode": parse_mode, "file_format": file_format},
        }

    def _stage_content_read(self, context: dict[str, Any]) -> dict[str, Any]:
        path: Path = context["path"]
        raw = path.read_bytes()
        if not raw:
            raise ValueError("文件内容为空")
        return {"detail": f"读取 {len(raw)} 字节", "context_updates": {"raw": raw}}

    def _stage_caj_decrypt(self, context: dict[str, Any]) -> dict[str, Any]:
        raw: bytes = context["raw"]
        if raw.startswith(b"KDH"):
            pdf_bytes = decrypt_kdh(raw)
            return {
                "detail": "KDH 解密成功",
                "context_updates": {"raw": pdf_bytes, "parse_mode": "caj"},
            }
        parsed = extract_text_from_bytes(raw)
        if parsed:
            return {
                "detail": "CAJ 内嵌 PDF 提取成功",
                "context_updates": {"text": parsed, "parse_mode": "caj"},
            }
        raise ValueError("CAJ/KDH 解密失败")

    def _stage_pdf_extract(self, context: dict[str, Any]) -> dict[str, Any]:
        if context.get("text"):
            return {"detail": "已在解密阶段得到文本"}
        raw: bytes = context["raw"]
        if not raw.startswith(b"%PDF"):
            raise ValueError("不是有效的 PDF 数据")

        import io

        from pypdf import PdfReader

        try:
            from app.kg.services.scanned_pdf_extractor import (
                extract_scanned_pdf_with_vision,
                is_sparse_pdf_text,
            )
        except Exception:  # pymupdf / Pillow 未安装时退化为纯文本提取
            extract_scanned_pdf_with_vision = None
            is_sparse_pdf_text = None

        reader = PdfReader(io.BytesIO(raw))
        page_count = len(reader.pages)
        user_mode = context.get("user_parse_mode", "auto_detect")
        parse_mode = context.get("parse_mode", "pdf")
        force_vision = user_mode == "scanned_pdf" or parse_mode == "scanned_pdf"

        if not force_vision:
            pages = [page.extract_text() or "" for page in reader.pages]
            native_text = "\n".join(pages).strip()
            sparse = is_sparse_pdf_text(native_text, page_count) if is_sparse_pdf_text else False
            if user_mode == "digital_pdf":
                if not native_text:
                    raise ValueError("PDF 未提取到文本（数字 PDF 模式）")
                return {
                    "detail": f"pypdf 提取 {page_count} 页 PDF 文本",
                    "context_updates": {"text": native_text, "page_count": page_count, "parse_mode": "pdf"},
                }
            if native_text and not sparse:
                return {
                    "detail": f"pypdf 提取 {page_count} 页 PDF 文本",
                    "context_updates": {"text": native_text, "page_count": page_count, "parse_mode": "pdf"},
                }

        if extract_scanned_pdf_with_vision is None:
            pages = [page.extract_text() or "" for page in reader.pages]
            native_text = "\n".join(pages).strip()
            if native_text:
                return {
                    "detail": f"pypdf 提取 {page_count} 页 PDF 文本（未安装 OCR 依赖）",
                    "context_updates": {"text": native_text, "page_count": page_count, "parse_mode": "pdf"},
                }
            raise ValueError("PDF 未提取到文本，且未安装 pymupdf/Pillow，无法执行扫描件 OCR")

        text, ocr_page_count = extract_scanned_pdf_with_vision(raw)
        return {
            "detail": f"视觉模型 OCR {ocr_page_count} 页，共 {len(text)} 字",
            "context_updates": {
                "text": text,
                "page_count": ocr_page_count,
                "parse_mode": "scanned_pdf",
            },
        }

    def _stage_text_decode(self, context: dict[str, Any]) -> dict[str, Any]:
        if context.get("text"):
            return {"detail": "已在上一阶段得到文本"}
        raw: bytes = context["raw"]
        decoded = raw.decode("utf-8", errors="ignore").strip()
        if not decoded:
            raise ValueError("文本解码失败")
        return {"detail": f"UTF-8 解码 {len(decoded)} 字", "context_updates": {"text": decoded, "parse_mode": "text"}}

    def _stage_text_clean(self, context: dict[str, Any]) -> dict[str, Any]:
        text: str = context.get("text", "")
        cleaned = re.sub(r"\u0000", "", text)
        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        if not cleaned:
            raise ValueError("清洗后文本为空")
        return {"detail": "空白归一化完成", "context_updates": {"text": cleaned}}

    def _stage_paragraph_split(self, context: dict[str, Any]) -> dict[str, Any]:
        text: str = context["text"]
        chunks = re.split(r"[。！？!?；;\n]+", text)
        paragraphs = [chunk.strip(" ，,") for chunk in chunks if chunk.strip(" ，,")]
        if not paragraphs:
            paragraphs = [text]
        return {
            "detail": f"切分 {len(paragraphs)} 个段落",
            "context_updates": {"paragraphs": paragraphs},
        }

    def _stage_persist_result(self, context: dict[str, Any]) -> dict[str, Any]:
        text: str = context["text"]
        paragraphs: list[str] = context.get("paragraphs", [])
        return {
            "detail": f"准备落盘 {len(text)} 字 / {len(paragraphs)} 段",
            "context_updates": {},
        }


text_parse_pipeline = TextParsePipeline()
