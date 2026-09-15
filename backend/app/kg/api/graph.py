from __future__ import annotations

from fastapi import APIRouter, Query

from app.kg.response import ok
from app.kg.services.graph_repository import graph_repository

router = APIRouter()


@router.get("/full")
async def full_graph():
    graph = await graph_repository.full_graph()
    return ok(graph.model_dump(mode="json"))


@router.get("/node/{node_id}")
async def node_graph(node_id: str):
    graph = await graph_repository.node_subgraph(node_id)
    return ok(graph.model_dump(mode="json"))


@router.get("/search")
async def search_graph(q: str = Query(default="")):
    nodes = await graph_repository.search(q)
    return ok({"nodes": nodes})
