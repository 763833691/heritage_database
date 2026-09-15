from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter

from app.kg.response import ok
from app.kg.services.nlp_service import nlp_service

router = APIRouter()


class ExtractRequest(BaseModel):
    text: str


@router.post("/extract")
async def extract(request: ExtractRequest):
    result = await nlp_service.extract(request.text)
    return ok(result.model_dump(mode="json"))
