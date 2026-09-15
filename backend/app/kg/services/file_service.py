from __future__ import annotations

import asyncio
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from app.core.config import settings
from app.kg.schemas import FileItem, ProcessResult, ProcessStatus, VaultFolder
from app.kg.services.caj_reader import extract_text_from_caj
from app.kg.services.workflow_helper import normalize_process_status


class FileService:
    def __init__(self) -> None:
        self.storage_dir = settings.storage_dir
        self.upload_dir = settings.upload_dir
        self.state_file = settings.state_file
        self.files: dict[str, FileItem] = {}
        self.folders: dict[str, VaultFolder] = {}
        self._lock = asyncio.Lock()
        self._loaded = False

    async def init(self) -> None:
        async with self._lock:
            if self._loaded:
                return
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            self.upload_dir.mkdir(parents=True, exist_ok=True)
            if self.state_file.exists():
                payload = json.loads(self.state_file.read_text(encoding="utf-8"))
                for raw_item in payload.get("files", []):
                    legacy_category = ""
                    if isinstance(raw_item, dict):
                        legacy_category = str(raw_item.pop("category", "") or "").strip()
                    item = FileItem.model_validate(raw_item)
                    normalize_process_status(item)
                    if not item.folder_id and legacy_category and legacy_category not in {"", "未分类"}:
                        folder = self._get_or_create_folder_locked(legacy_category)
                        self._apply_folder_to_item(item, folder.id)
                    self.files[item.id] = item
                for folder in payload.get("folders", []):
                    self.folders[folder["id"]] = VaultFolder.model_validate(folder)
            else:
                await self._persist_locked()
            self._loaded = True

    def _status_for(self, status: str) -> ProcessStatus:
        progress_map = {"created": 0, "uploaded": 0, "processing": 60, "processed": 100, "failed": 0}
        step_map = {
            "created": "等待上传",
            "uploaded": "等待处理",
            "processing": "关系抽取",
            "processed": "处理完成",
            "failed": "处理失败",
        }
        return ProcessStatus(
            status=status,
            progress=progress_map.get(status, 0),
            current_step=step_map.get(status, "等待处理"),
            logs=[],
        )

    async def _persist_locked(self) -> None:
        payload = {
            "files": [item.model_dump(mode="json") for item in self.files.values()],
            "folders": [folder.model_dump(mode="json") for folder in self.folders.values()],
        }
        await asyncio.to_thread(
            self.state_file.write_text,
            json.dumps(payload, ensure_ascii=False, indent=2),
            "utf-8",
        )

    def _folder_names(self) -> set[str]:
        return {folder.name for folder in self.folders.values()}

    def _folder_by_id(self, folder_id: str) -> VaultFolder | None:
        if not folder_id:
            return None
        return self.folders.get(folder_id)

    def _folder_name(self, folder_id: str) -> str | None:
        folder = self._folder_by_id(folder_id)
        return folder.name if folder else None

    def _sync_folder_tag(self, item: FileItem, old_folder_name: str | None, new_folder_name: str | None) -> None:
        tags = [tag for tag in item.tags if tag != old_folder_name]
        if new_folder_name and new_folder_name not in tags:
            tags.insert(0, new_folder_name)
        item.tags = tags

    def _apply_folder_to_item(self, item: FileItem, folder_id: str) -> None:
        old_name = self._folder_name(item.folder_id)
        item.folder_id = folder_id
        new_name = self._folder_name(folder_id)
        self._sync_folder_tag(item, old_name, new_name)

    def _get_or_create_folder_locked(self, name: str) -> VaultFolder:
        clean = name.strip()
        if not clean:
            raise HTTPException(status_code=422, detail="FOLDER_NAME_REQUIRED")
        for folder in self.folders.values():
            if folder.name == clean:
                return folder
        folder_id = f"folder_{uuid4().hex[:12]}"
        folder = VaultFolder(id=folder_id, name=clean, created_at=datetime.now())
        self.folders[folder_id] = folder
        return folder

    async def list_folders(self) -> list[VaultFolder]:
        await self.init()
        return sorted(self.folders.values(), key=lambda folder: (folder.name, folder.created_at))

    async def create_folder(self, name: str) -> VaultFolder:
        await self.init()
        async with self._lock:
            clean = name.strip()
            if not clean:
                raise HTTPException(status_code=422, detail="FOLDER_NAME_REQUIRED")
            if any(folder.name == clean for folder in self.folders.values()):
                raise HTTPException(status_code=409, detail="FOLDER_NAME_EXISTS")
            folder_id = f"folder_{uuid4().hex[:12]}"
            folder = VaultFolder(id=folder_id, name=clean, created_at=datetime.now())
            self.folders[folder_id] = folder
            await self._persist_locked()
            return folder

    async def update_folder(self, folder_id: str, *, name: str | None = None) -> VaultFolder:
        await self.init()
        async with self._lock:
            folder = self.folders.get(folder_id)
            if not folder:
                raise HTTPException(status_code=404, detail="FOLDER_NOT_FOUND")
            if name is not None:
                clean = name.strip()
                if not clean:
                    raise HTTPException(status_code=422, detail="FOLDER_NAME_REQUIRED")
                if any(item.id != folder_id and item.name == clean for item in self.folders.values()):
                    raise HTTPException(status_code=409, detail="FOLDER_NAME_EXISTS")
                old_name = folder.name
                folder.name = clean
                if old_name != clean:
                    for item in self.files.values():
                        if item.folder_id == folder_id:
                            self._sync_folder_tag(item, old_name, clean)
            await self._persist_locked()
            return folder

    async def delete_folder(self, folder_id: str) -> None:
        await self.init()
        async with self._lock:
            folder = self.folders.get(folder_id)
            if not folder:
                raise HTTPException(status_code=404, detail="FOLDER_NOT_FOUND")
            folder_name = folder.name
            for item in self.files.values():
                if item.folder_id == folder_id:
                    item.folder_id = ""
                    self._sync_folder_tag(item, folder_name, None)
            del self.folders[folder_id]
            await self._persist_locked()

    async def list_files(self) -> list[FileItem]:
        await self.init()
        return sorted(self.files.values(), key=lambda item: item.upload_time, reverse=True)

    async def get_file(self, file_id: str) -> FileItem:
        await self.init()
        item = self.files.get(file_id)
        if not item:
            raise HTTPException(status_code=404, detail="FILE_NOT_FOUND")
        normalize_process_status(item)
        return item

    async def upload_file(self, upload: UploadFile, folder_id: str = "") -> FileItem:
        await self.init()
        raw = await upload.read()
        if len(raw) > settings.max_upload_size:
            limit_mb = settings.max_upload_size // (1024 * 1024)
            raise HTTPException(status_code=413, detail=f"FILE_TOO_LARGE:{limit_mb}")
        original_name = Path(upload.filename or "untitled.txt").name
        suffix = Path(original_name).suffix.lower().lstrip(".") or "txt"
        file_id = f"file_{uuid4().hex[:12]}"
        disk_path = self.upload_dir / f"{file_id}_{original_name}"
        await asyncio.to_thread(disk_path.write_bytes, raw)
        item = FileItem(
            id=file_id,
            name=original_name,
            type=suffix,
            status="uploaded",
            size=len(raw),
            source="上传",
            upload_time=datetime.now(),
            folder_id="",
            tags=self._infer_tags(original_name, raw),
            summary="文件已上传，等待抽取实体与关系。",
            content_path=str(disk_path),
            process_status=ProcessStatus(status="uploaded", progress=0, current_step="等待处理"),
        )
        async with self._lock:
            if folder_id and folder_id not in self.folders:
                raise HTTPException(status_code=404, detail="FOLDER_NOT_FOUND")
            if folder_id:
                self._apply_folder_to_item(item, folder_id)
            self.files[file_id] = item
            await self._persist_locked()
        return item

    def _infer_tags(self, name: str, raw: bytes) -> list[str]:
        text = name + " " + raw[:2000].decode("utf-8", errors="ignore")
        tags = []
        for keyword in ["大明宫", "丝绸之路", "唐代", "长安", "考古", "贸易", "西域"]:
            if keyword in text:
                tags.append(keyword)
        return tags[:4] or ["待识别"]

    async def update_file(self, file_id: str, *, folder_id: str | None = None) -> FileItem:
        await self.init()
        async with self._lock:
            item = self.files.get(file_id)
            if not item:
                raise HTTPException(status_code=404, detail="FILE_NOT_FOUND")
            if folder_id is not None:
                if folder_id and folder_id not in self.folders:
                    raise HTTPException(status_code=404, detail="FOLDER_NOT_FOUND")
                self._apply_folder_to_item(item, folder_id)
            await self._persist_locked()
            return item

    async def create_task(
        self,
        *,
        doc_code: str,
        title: str,
        discipline: str = "",
        parse_mode: str = "auto_detect",
    ) -> FileItem:
        await self.init()
        file_id = f"file_{uuid4().hex[:12]}"
        item = FileItem(
            id=file_id,
            name=title,
            type="pending",
            status="created",
            size=0,
            source="任务创建",
            upload_time=datetime.now(),
            tags=[discipline] if discipline else ["待上传"],
            summary="文献任务已创建，请上传 PDF/CAJ/TXT 或从文件库载入。",
            doc_code=doc_code,
            discipline=discipline,
            parse_mode=parse_mode,
            process_status=ProcessStatus(status="created", progress=0, current_step="等待上传"),
        )
        async with self._lock:
            self.files[file_id] = item
            await self._persist_locked()
        return item

    async def attach_upload(self, file_id: str, upload: UploadFile) -> FileItem:
        await self.init()
        raw = await upload.read()
        if len(raw) > settings.max_upload_size:
            limit_mb = settings.max_upload_size // (1024 * 1024)
            raise HTTPException(status_code=413, detail=f"FILE_TOO_LARGE:{limit_mb}")
        original_name = Path(upload.filename or "untitled.txt").name
        suffix = Path(original_name).suffix.lower().lstrip(".") or "txt"
        disk_path = self.upload_dir / f"{file_id}_{original_name}"
        await asyncio.to_thread(disk_path.write_bytes, raw)
        page_count = await asyncio.to_thread(self._detect_page_count, disk_path, suffix, raw)
        async with self._lock:
            item = self.files.get(file_id)
            if not item:
                raise HTTPException(status_code=404, detail="FILE_NOT_FOUND")
            item.name = original_name
            item.type = suffix
            item.status = "uploaded"
            item.size = len(raw)
            item.content_path = str(disk_path)
            item.page_count = page_count
            item.summary = "文件已上传，等待文本解析与知识抽取。"
            item.process_status.status = "uploaded"
            item.process_status.progress = 0
            item.process_status.current_step = "等待处理"
            item.tags = self._infer_tags(original_name, raw)
            await self._persist_locked()
            return item

    async def import_from_library(self, file_id: str, source_file_id: str) -> FileItem:
        await self.init()
        source = await self.get_file(source_file_id)
        if not source.content_path or not Path(source.content_path).exists():
            raise HTTPException(status_code=422, detail="SOURCE_FILE_UNAVAILABLE")
        source_path = Path(source.content_path)
        target_name = source_path.name
        target_path = self.upload_dir / f"{file_id}_{target_name}"
        await asyncio.to_thread(shutil.copy2, source_path, target_path)
        suffix = target_path.suffix.lower().lstrip(".") or source.type
        raw = await asyncio.to_thread(target_path.read_bytes)
        page_count = await asyncio.to_thread(self._detect_page_count, target_path, suffix, raw)
        async with self._lock:
            item = self.files.get(file_id)
            if not item:
                raise HTTPException(status_code=404, detail="FILE_NOT_FOUND")
            item.name = source.name
            item.type = suffix
            item.status = "uploaded"
            item.size = source.size
            item.content_path = str(target_path)
            item.page_count = page_count
            item.source = "文件库载入"
            item.summary = f"已从文件库载入：{source.name}"
            item.process_status.status = "uploaded"
            item.process_status.progress = 0
            item.process_status.current_step = "等待处理"
            item.tags = list(source.tags)
            item.folder_id = source.folder_id
            await self._persist_locked()
            return item

    def _detect_page_count(self, path: Path, suffix: str, raw: bytes) -> int:
        try:
            if suffix == "pdf" or raw.startswith(b"%PDF"):
                from pypdf import PdfReader
                import io

                payload = raw if suffix != "pdf" else path.read_bytes()
                reader = PdfReader(io.BytesIO(payload))
                return len(reader.pages)
        except Exception:
            return 0
        return 0

    async def delete_file(self, file_id: str) -> None:
        await self.init()
        async with self._lock:
            if file_id not in self.files:
                raise HTTPException(status_code=404, detail="FILE_NOT_FOUND")
            item = self.files[file_id]
            if item.content_path and Path(item.content_path).exists():
                Path(item.content_path).unlink(missing_ok=True)
            del self.files[file_id]
            await self._persist_locked()

    async def reset_for_rerun(self, file_id: str) -> FileItem:
        from app.kg.services.text_parse_pipeline import text_parse_pipeline

        await self.init()
        await text_parse_pipeline.reset(file_id)
        async with self._lock:
            item = self.files.get(file_id)
            if not item:
                raise HTTPException(status_code=404, detail="FILE_NOT_FOUND")
            item.status = "uploaded"
            item.process_result = None
            item.process_status = ProcessStatus(status="uploaded", progress=0, current_step="等待处理", logs=[])
            item.summary = "已重置处理状态，等待重新运行文本解析流水线。"
            await self._persist_locked()
            return item

    async def update_status(
        self,
        file_id: str,
        status: str,
        progress: int,
        current_step: str,
        log: str | None = None,
    ) -> FileItem:
        await self.init()
        async with self._lock:
            item = self.files.get(file_id)
            if not item:
                raise HTTPException(status_code=404, detail="FILE_NOT_FOUND")
            item.status = status  # type: ignore[assignment]
            item.process_status.status = status  # type: ignore[assignment]
            item.process_status.progress = progress
            item.process_status.current_step = current_step
            if log:
                stamp = datetime.now().strftime("%H:%M:%S")
                item.process_status.logs.append(f"{stamp} {log}")
            await self._persist_locked()
            return item

    async def mark_text_parse_complete(self, file_id: str) -> FileItem:
        await self.init()
        async with self._lock:
            item = self.files.get(file_id)
            if not item:
                raise HTTPException(status_code=404, detail="FILE_NOT_FOUND")
            item.status = "uploaded"
            item.process_status.status = "uploaded"
            item.process_status.progress = 33
            item.process_status.current_step = "文本解析完成，待确认"
            item.process_status.workflow_phase = "text_parse"
            item.process_status.text_parse_confirmed = False
            item.process_status.export_ready = False
            stamp = datetime.now().strftime("%H:%M:%S")
            item.process_status.logs.append(f"{stamp} 文本解析完成，请检查预览后确认进入图谱构建")
            item.summary = "文本解析已完成，等待确认后进入图谱构建。"
            await self._persist_locked()
            return item

    async def confirm_text_parse(self, file_id: str) -> FileItem:
        await self.init()
        async with self._lock:
            item = self.files.get(file_id)
            if not item:
                raise HTTPException(status_code=404, detail="FILE_NOT_FOUND")
            item.process_status.text_parse_confirmed = True
            item.process_status.workflow_phase = "graph_build"
            item.process_status.progress = max(item.process_status.progress, 34)
            item.process_status.current_step = "待图谱构建"
            stamp = datetime.now().strftime("%H:%M:%S")
            item.process_status.logs.append(f"{stamp} 用户已确认文本解析结果，可开始图谱构建")
            item.summary = "文本解析已确认，可配置并启动图谱构建。"
            await self._persist_locked()
            return item

    async def set_graph_build_method(self, file_id: str, method: str) -> FileItem:
        await self.init()
        async with self._lock:
            item = self.files.get(file_id)
            if not item:
                raise HTTPException(status_code=404, detail="FILE_NOT_FOUND")
            item.process_status.graph_build_method = method  # type: ignore[assignment]
            await self._persist_locked()
            return item

    async def set_graph_build_result(self, file_id: str, result: ProcessResult) -> FileItem:
        await self.init()
        async with self._lock:
            item = self.files.get(file_id)
            if not item:
                raise HTTPException(status_code=404, detail="FILE_NOT_FOUND")
            item.process_result = result
            item.status = "uploaded"
            item.process_status.status = "uploaded"
            item.process_status.progress = 67
            item.process_status.current_step = "图谱构建完成，待导出"
            item.process_status.workflow_phase = "export"
            item.process_status.export_ready = True
            stamp = datetime.now().strftime("%H:%M:%S")
            item.process_status.logs.append(f"{stamp} 图谱构建完成：{len(result.entities)} 实体 / {len(result.relations)} 关系")
            item.summary = self._summarize_result(result)
            await self._persist_locked()
            return item

    async def mark_export_complete(self, file_id: str, export_path: str) -> FileItem:
        await self.init()
        async with self._lock:
            item = self.files.get(file_id)
            if not item:
                raise HTTPException(status_code=404, detail="FILE_NOT_FOUND")
            item.status = "processed"
            item.process_status.status = "processed"
            item.process_status.progress = 100
            item.process_status.current_step = "处理完成"
            item.process_status.workflow_phase = "completed"
            item.process_status.export_ready = True
            stamp = datetime.now().strftime("%H:%M:%S")
            item.process_status.logs.append(f"{stamp} 结果已导出并发布到图谱展示：{export_path}")
            await self._persist_locked()
            return item

    async def set_process_result(self, file_id: str, result: ProcessResult) -> FileItem:
        await self.init()
        async with self._lock:
            item = self.files.get(file_id)
            if not item:
                raise HTTPException(status_code=404, detail="FILE_NOT_FOUND")
            item.process_result = result
            item.status = "processed"
            item.process_status.status = "processed"
            item.process_status.progress = 100
            item.process_status.current_step = "处理完成"
            item.process_status.workflow_phase = "completed"
            item.process_status.text_parse_confirmed = True
            item.process_status.export_ready = True
            item.process_status.logs.append(datetime.now().strftime("%H:%M:%S") + " 图谱构建完成，结果已写入图数据库")
            item.summary = self._summarize_result(result)
            await self._persist_locked()
            return item

    def _summarize_result(self, result: ProcessResult) -> str:
        names = "、".join(entity.name for entity in result.entities[:6])
        return f"识别出 {len(result.entities)} 个实体、{len(result.relations)} 条关系。核心实体：{names}。"

    async def read_text(self, file_id: str) -> str:
        from app.kg.services.text_parse_pipeline import text_parse_pipeline

        item = await self.get_file(file_id)
        state = await text_parse_pipeline.load_state(file_id)
        cached = await text_parse_pipeline._load_extracted_text(state)
        if cached.strip():
            return cached
        if item.content_path and Path(item.content_path).exists():
            path = Path(item.content_path)
            raw = await asyncio.to_thread(path.read_bytes)
            suffix = path.suffix.lower()
            if suffix in {".caj", ".kdh"}:
                parsed = await asyncio.to_thread(extract_text_from_caj, path)
                if parsed and parsed.strip():
                    return parsed
            if suffix == ".pdf":
                try:
                    from pypdf import PdfReader

                    def parse_pdf() -> str:
                        reader = PdfReader(str(path))
                        return "\n".join(page.extract_text() or "" for page in reader.pages)

                    parsed = await asyncio.to_thread(parse_pdf)
                    if parsed.strip():
                        return parsed
                except Exception:
                    pass
            decoded = raw.decode("utf-8", errors="ignore")
            if decoded.strip():
                return decoded
            raise HTTPException(status_code=422, detail="FILE_CONTENT_EMPTY")
        if item.summary and item.summary.strip():
            return item.summary
        raise HTTPException(status_code=422, detail="FILE_CONTENT_UNAVAILABLE")


file_service = FileService()
