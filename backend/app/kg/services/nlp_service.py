from __future__ import annotations

from app.kg.schemas import ProcessResult
from app.kg.services.nlp_extractor import process_text


class NlpService:
    """实体/关系抽取服务：优先调用 LLM，失败时回落到领域词典 + 规则抽取。"""

    async def extract(self, text: str, source_file: str | None = None) -> ProcessResult:
        payload = await process_text(text, source_file=source_file)
        return ProcessResult.model_validate(payload)


nlp_service = NlpService()
