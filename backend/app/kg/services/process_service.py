from __future__ import annotations

import asyncio
import json

from app.core.config import settings
from app.kg.schemas import ProcessResult
from app.kg.services.file_service import file_service
from app.kg.services.graph_repository import graph_repository
from app.kg.services.nlp_service import nlp_service
from app.kg.services.text_parse_pipeline import text_parse_pipeline
from app.kg.services.workflow_helper import text_parse_ready


class ProcessService:
    async def process_batch(self, file_ids: list[str], mode: str = "start") -> None:
        for file_id in file_ids:
            try:
                item = await file_service.get_file(file_id)
                if item.status == "created" or not item.content_path:
                    continue
                if mode == "rerun":
                    await file_service.reset_for_rerun(file_id)
                await file_service.update_status(file_id, "processing", 5, "文本解析", "批量队列：开始文本解析")
                await self.run_text_parse(file_id)
            except Exception as exc:
                await file_service.update_status(file_id, "failed", 0, "处理失败", f"批量处理失败：{exc}")

    async def process_file(self, file_id: str) -> None:
        """兼容旧入口：仅执行文本解析，等待用户确认后再进入图谱构建。"""
        await self.run_text_parse(file_id)

    async def run_text_parse(self, file_id: str) -> None:
        try:
            await file_service.get_file(file_id)
            await file_service.update_status(file_id, "processing", 2, "文本解析", "进入文本解析流水线")

            async def on_text_progress(step: str, log: str, progress: int) -> None:
                mapped = max(2, min(33, int(progress * 33 / 20)))
                await file_service.update_status(file_id, "processing", mapped, "文本解析", log)

            await text_parse_pipeline.run(
                file_id,
                progress_callback=on_text_progress,
                base_progress=0,
                progress_span=20,
            )

            await file_service.mark_text_parse_complete(file_id)
        except Exception as exc:
            await file_service.update_status(file_id, "failed", 0, "文本解析", f"文本解析失败：{exc}")
            raise

    async def run_graph_build(self, file_id: str, method: str = "entity_relation") -> None:
        try:
            item = await file_service.get_file(file_id)
            if not item.process_status.text_parse_confirmed:
                if not text_parse_ready(item):
                    raise ValueError("请先完成文本解析并确认结果")
                await file_service.confirm_text_parse(file_id)

            await file_service.set_graph_build_method(file_id, method)
            await file_service.update_status(file_id, "processing", 36, "图谱构建", f"开始图谱构建（{method}）")

            text = await file_service.read_text(file_id)
            await file_service.update_status(file_id, "processing", 48, "图谱构建", "正在识别实体")
            await asyncio.sleep(0.1)

            result = await nlp_service.extract(text, source_file=file_id)
            if method == "entity_only":
                result = ProcessResult(entities=result.entities, relations=[], graph=result.graph)
            elif method == "rule_enhanced":
                result = self._apply_rule_enhancements(result)

            await file_service.update_status(file_id, "processing", 58, "图谱构建", "实体识别完成，正在抽取关系")
            await asyncio.sleep(0.1)

            await file_service.update_status(file_id, "processing", 66, "图谱构建", "正在写入图数据库")
            file_item = await file_service.get_file(file_id)
            await graph_repository.save_file_graph(file_item, result)
            await file_service.set_graph_build_result(file_id, result)
        except Exception as exc:
            await file_service.update_status(file_id, "failed", 0, "图谱构建", f"图谱构建失败：{exc}")
            raise

    async def run_export(self, file_id: str) -> dict:
        try:
            item = await file_service.get_file(file_id)
            if not item.process_result:
                raise ValueError("请先完成图谱构建")

            await file_service.update_status(file_id, "processing", 72, "结果导出", "正在生成交付文件")
            export_dir = settings.storage_dir / "exports" / file_id
            export_dir.mkdir(parents=True, exist_ok=True)

            result = item.process_result
            payload = {
                "file_id": file_id,
                "file_name": item.name,
                "entities": [entity.model_dump(mode="json") for entity in result.entities],
                "relations": [relation.model_dump(mode="json") for relation in result.relations],
                "graph": result.graph.model_dump(mode="json"),
            }
            export_path = export_dir / "knowledge_graph.json"
            await asyncio.to_thread(export_path.write_text, json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

            await file_service.update_status(file_id, "processing", 90, "结果导出", "正在发布到图谱展示")
            graph = await graph_repository.full_graph()

            await file_service.mark_export_complete(file_id, str(export_path))
            return {
                "export_path": str(export_path),
                "graph_nodes": len(graph.nodes),
                "graph_edges": len(graph.edges),
                "published": True,
            }
        except Exception as exc:
            await file_service.update_status(file_id, "failed", 0, "结果导出", f"结果导出失败：{exc}")
            raise

    def _apply_rule_enhancements(self, result: ProcessResult) -> ProcessResult:
        from app.kg.schemas import Entity

        keywords = ("大明宫", "含元殿", "麟德殿", "太极宫", "长安城")
        entities = list(result.entities)
        existing = {entity.name for entity in entities}
        for keyword in keywords:
            if keyword not in existing:
                entities.append(Entity(id=f"rule_{keyword}", name=keyword, type="place", confidence=0.75))
        return ProcessResult(entities=entities, relations=result.relations, graph=result.graph)


process_service = ProcessService()
