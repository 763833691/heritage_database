import json
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from ..core.database import get_db, get_neo4j, get_chroma_collection
from ..core.auth import get_current_user
from ..models.user import User
from ..schemas.chat import ChatRequest, ChatResponse, ConversationMeta, ConversationListResponse
from ..services.rag_engine import RAGEngine

router = APIRouter()

# 存储会话（内存），包含元数据
conversation_store: dict = {}
MAX_CONVERSATIONS = 100


def _get_or_create_conversation(conversation_id: str, first_message: str = "") -> str:
    """获取或创建会话，返回 conversation_id"""
    if not conversation_id:
        conversation_id = str(uuid.uuid4())

    if conversation_id not in conversation_store:
        if len(conversation_store) >= MAX_CONVERSATIONS:
            oldest_key = next(iter(conversation_store))
            del conversation_store[oldest_key]
        conversation_store[conversation_id] = {
            "id": conversation_id,
            "title": first_message[:30] if first_message else "新对话",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_active": datetime.now(timezone.utc).isoformat(),
            "messages": [],
        }
    else:
        conversation_store[conversation_id]["last_active"] = datetime.now(timezone.utc).isoformat()

    return conversation_id


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """聊天接口（非流式）"""
    conversation_id = _get_or_create_conversation(request.conversation_id, request.message)
    conv = conversation_store[conversation_id]
    history = conv["messages"]

    neo4j_session = get_neo4j()
    rag = RAGEngine(db=db, neo4j_session=neo4j_session, chroma=get_chroma_collection())

    result = await rag.query(
        question=request.message,
        conversation_history=history,
    )

    history.append({"role": "user", "content": request.message})
    history.append({"role": "assistant", "content": result["answer"]})

    if len(history) > 20:
        conv["messages"] = history[-20:]

    conv["title"] = conv["title"] or request.message[:30]
    conv["last_active"] = datetime.now(timezone.utc).isoformat()

    return ChatResponse(
        message=result["answer"],
        conversation_id=conversation_id,
        sources=result.get("sources", []),
        chart_data=result.get("chart_data"),
    )


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """流式聊天接口 (SSE)"""
    conversation_id = _get_or_create_conversation(request.conversation_id, request.message)
    conv = conversation_store[conversation_id]
    history = conv["messages"]

    neo4j_session = get_neo4j()
    rag = RAGEngine(db=db, neo4j_session=neo4j_session, chroma=get_chroma_collection())

    async def event_generator():
        full_answer = ""
        try:
            async for event in rag.stream_query(
                question=request.message,
                conversation_history=history,
            ):
                event_type = event["type"]
                event_data = event["data"]

                if event_type == "token":
                    full_answer += event_data
                    yield {"event": "token", "data": json.dumps({"token": event_data}, ensure_ascii=False)}
                elif event_type == "chart_data":
                    yield {"event": "chart_data", "data": json.dumps(event_data, ensure_ascii=False)}
                elif event_type == "sources":
                    yield {"event": "sources", "data": json.dumps(event_data, ensure_ascii=False)}
                elif event_type == "done":
                    yield {"event": "done", "data": "{}"}

            # 保存对话历史
            history.append({"role": "user", "content": request.message})
            history.append({"role": "assistant", "content": full_answer})

            if len(history) > 20:
                conv["messages"] = history[-20:]

            conv["last_active"] = datetime.now(timezone.utc).isoformat()

        except Exception as e:
            yield {"event": "error", "data": json.dumps({"detail": str(e)}, ensure_ascii=False)}

    return EventSourceResponse(
        event_generator(),
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    current_user: User = Depends(get_current_user),
):
    """获取所有会话列表"""
    convs = []
    for cid, cdata in conversation_store.items():
        convs.append(ConversationMeta(
            id=cdata["id"],
            title=cdata["title"],
            message_count=len(cdata["messages"]),
            created_at=cdata["created_at"],
            last_active=cdata["last_active"],
        ))
    convs.sort(key=lambda x: x.last_active, reverse=True)
    return ConversationListResponse(conversations=convs)


@router.get("/history/{conversation_id}")
async def get_history(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
):
    """获取会话历史"""
    conv = conversation_store.get(conversation_id)
    if not conv:
        return []
    return conv["messages"]


@router.delete("/conversation/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
):
    """删除会话"""
    if conversation_id in conversation_store:
        del conversation_store[conversation_id]
    return {"message": "对话已删除"}


@router.delete("/history/{conversation_id}")
async def clear_history(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
):
    """清空会话历史（兼容旧接口）"""
    if conversation_id in conversation_store:
        del conversation_store[conversation_id]
    return {"message": "对话历史已清除"}
