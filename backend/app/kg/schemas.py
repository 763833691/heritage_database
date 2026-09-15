from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


EntityType = Literal["place", "person", "event", "concept"]
FileStatus = Literal["created", "uploaded", "processing", "processed", "failed"]
WorkflowPhase = Literal["text_parse", "graph_build", "export", "completed"]
GraphBuildMethod = Literal["entity_relation", "entity_only", "rule_enhanced"]


class VaultFolder(BaseModel):
    id: str
    name: str
    created_at: datetime


class ApiEnvelope(BaseModel):
    code: int = 0
    message: str = "success"
    data: Any = Field(default_factory=dict)


class Entity(BaseModel):
    id: str
    name: str
    type: EntityType
    description: str = ""
    source_file: str | None = None
    confidence: float = 0.9
    mention_count: int = 0


class Relation(BaseModel):
    source: str
    relation: str
    target: str
    weight: float = 0.85


class GraphNode(BaseModel):
    data: dict[str, Any]


class GraphEdge(BaseModel):
    data: dict[str, Any]


class GraphData(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class ProcessResult(BaseModel):
    entities: list[Entity] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)
    graph: GraphData = Field(default_factory=GraphData)


class ProcessStatus(BaseModel):
    progress: int = 0
    status: FileStatus = "uploaded"
    current_step: str = "等待处理"
    workflow_phase: WorkflowPhase = "text_parse"
    text_parse_confirmed: bool = False
    graph_build_method: GraphBuildMethod = "entity_relation"
    export_ready: bool = False
    logs: list[str] = Field(default_factory=list)


class GraphBuildRequest(BaseModel):
    method: GraphBuildMethod = "entity_relation"


class ExportResultPayload(BaseModel):
    export_path: str | None = None
    graph_nodes: int = 0
    graph_edges: int = 0
    published: bool = False


class FileItem(BaseModel):
    id: str
    name: str
    type: str
    status: FileStatus
    size: int = 0
    source: str = "上传"
    upload_time: datetime
    folder_id: str = ""
    tags: list[str] = Field(default_factory=list)
    summary: str = ""
    content_path: str | None = None
    doc_code: str = ""
    discipline: str = ""
    parse_mode: str = "auto_detect"
    page_count: int = 0
    process_status: ProcessStatus = Field(default_factory=ProcessStatus)
    process_result: ProcessResult | None = None


class CreateFileTaskRequest(BaseModel):
    doc_code: str
    title: str
    discipline: str = ""
    parse_mode: str = "auto_detect"


class CreateFolderRequest(BaseModel):
    name: str


class UpdateFolderRequest(BaseModel):
    name: str | None = None


class UpdateFileRequest(BaseModel):
    folder_id: str | None = None


class BatchProcessRequest(BaseModel):
    file_ids: list[str] = Field(default_factory=list)
    mode: Literal["start", "rerun"] = "start"
