from __future__ import annotations

import asyncio
import json
from typing import Any

from app.core.config import settings
from app.kg.schemas import FileItem, GraphData, GraphEdge, GraphNode, ProcessResult
from app.kg.services.sample_helper import entity_id


class InMemoryGraphRepository:
    def __init__(self) -> None:
        self.graph_file = settings.storage_dir / "graph.json"
        self.nodes: dict[str, dict[str, Any]] = {}
        self.edges: dict[str, dict[str, Any]] = {}
        self.file_contains: set[tuple[str, str]] = set()
        self._loaded = False

    async def init(self) -> None:
        if self._loaded:
            return
        settings.storage_dir.mkdir(parents=True, exist_ok=True)
        if self.graph_file.exists():
            payload = json.loads(self.graph_file.read_text(encoding="utf-8"))
            self.nodes = {node["id"]: node for node in payload.get("nodes", [])}
            self.edges = {edge["id"]: edge for edge in payload.get("edges", [])}
            self.file_contains = {
                tuple(item) for item in payload.get("file_contains", []) if len(item) == 2
            }
        self._loaded = True

    async def _persist(self) -> None:
        payload = {
            "nodes": list(self.nodes.values()),
            "edges": list(self.edges.values()),
            "file_contains": [list(item) for item in self.file_contains],
        }
        await asyncio.to_thread(
            self.graph_file.write_text,
            json.dumps(payload, ensure_ascii=False, indent=2),
            "utf-8",
        )

    async def reset_graph(self) -> None:
        self.nodes = {}
        self.edges = {}
        self.file_contains = set()
        if self.graph_file.exists():
            self.graph_file.unlink()
        self._loaded = True

    async def save_file_graph(self, file_item: FileItem, result: ProcessResult) -> None:
        self.nodes.setdefault(
            file_item.id,
            {
                "id": file_item.id,
                "label": file_item.name,
                "name": file_item.name,
                "type": "file",
                "description": file_item.summary,
            },
        )
        for entity in result.entities:
            node_id = entity.id or entity_id(entity.name)
            existing = self.nodes.get(node_id, {})
            self.nodes[node_id] = {
                **existing,
                "id": node_id,
                "label": entity.name,
                "name": entity.name,
                "type": entity.type,
                "description": entity.description,
                "source_file": file_item.id,
            }
            contains_id = f"contains_{file_item.id}_{node_id}"
            self.edges[contains_id] = {
                "id": contains_id,
                "source": file_item.id,
                "target": node_id,
                "label": "CONTAINS",
                "relation": "CONTAINS",
                "weight": 1.0,
            }
            self.file_contains.add((file_item.id, node_id))
        name_to_id = {node["name"]: node["id"] for node in self.nodes.values() if "name" in node}
        for relation in result.relations:
            source_id = name_to_id.get(relation.source) or entity_id(relation.source)
            target_id = name_to_id.get(relation.target) or entity_id(relation.target)
            for node_id, name in [(source_id, relation.source), (target_id, relation.target)]:
                self.nodes.setdefault(
                    node_id,
                    {
                        "id": node_id,
                        "label": name,
                        "name": name,
                        "type": "concept",
                        "description": f"{name}由关系抽取自动补全。",
                        "source_file": file_item.id,
                    },
                )
            edge_id = f"rel_{source_id}_{target_id}_{relation.relation}"
            self.edges[edge_id] = {
                "id": edge_id,
                "source": source_id,
                "target": target_id,
                "label": relation.relation,
                "relation": relation.relation,
                "weight": relation.weight,
            }
        await self._persist()

    async def full_graph(self) -> GraphData:
        return GraphData(
            nodes=[GraphNode(data=node) for node in self.nodes.values()],
            edges=[GraphEdge(data=edge) for edge in self.edges.values()],
        )

    async def node_subgraph(self, node_id: str) -> GraphData:
        if node_id not in self.nodes:
            matches = [node for node in self.nodes.values() if node.get("name") == node_id]
            if not matches:
                return GraphData()
            node_id = matches[0]["id"]
        related_edges = [
            edge for edge in self.edges.values() if edge["source"] == node_id or edge["target"] == node_id
        ]
        node_ids = {node_id}
        for edge in related_edges:
            node_ids.add(edge["source"])
            node_ids.add(edge["target"])
        return GraphData(
            nodes=[GraphNode(data=self.nodes[nid]) for nid in node_ids if nid in self.nodes],
            edges=[GraphEdge(data=edge) for edge in related_edges],
        )

    async def search(self, keyword: str) -> list[dict[str, Any]]:
        if not keyword:
            return list(self.nodes.values())[:20]
        return [node for node in self.nodes.values() if keyword.lower() in node.get("name", "").lower()][:50]


class Neo4jGraphRepository:
    def __init__(self) -> None:
        self._driver = None
        self._fallback = InMemoryGraphRepository()

    async def init(self) -> None:
        if not settings.neo4j_enabled:
            await self._fallback.init()
            return
        try:
            from neo4j import AsyncGraphDatabase

            self._driver = AsyncGraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
            )
            async with self._driver.session(database=settings.neo4j_database) as session:
                await session.run(
                    "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE"
                )
                await session.run(
                    "CREATE CONSTRAINT file_id_unique IF NOT EXISTS FOR (f:File) REQUIRE f.id IS UNIQUE"
                )
                await session.run("CREATE INDEX entity_name_index IF NOT EXISTS FOR (e:Entity) ON (e.name)")
                await session.run("CREATE INDEX entity_type_index IF NOT EXISTS FOR (e:Entity) ON (e.type)")
        except Exception:
            self._driver = None
            await self._fallback.init()

    async def close(self) -> None:
        if self._driver:
            await self._driver.close()

    async def save_file_graph(self, file_item: FileItem, result: ProcessResult) -> None:
        if not self._driver:
            await self._fallback.save_file_graph(file_item, result)
            return
        async with self._driver.session(database=settings.neo4j_database) as session:
            await session.execute_write(self._write_file_graph, file_item, result)

    @staticmethod
    async def _write_file_graph(tx: Any, file_item: FileItem, result: ProcessResult) -> None:
        await tx.run(
            """
            MERGE (f:File {id: $id})
            SET f.name = $name,
                f.type = $type,
                f.status = $status,
                f.upload_time = datetime($upload_time)
            """,
            id=file_item.id,
            name=file_item.name,
            type=file_item.type,
            status=file_item.status,
            upload_time=file_item.upload_time.isoformat(),
        )
        for entity in result.entities:
            await tx.run(
                """
                MERGE (e:Entity {id: $id})
                SET e.name = $name,
                    e.type = $type,
                    e.description = $description,
                    e.source_file = $source_file
                WITH e
                MATCH (f:File {id: $file_id})
                MERGE (f)-[:CONTAINS]->(e)
                """,
                id=entity.id,
                name=entity.name,
                type=entity.type,
                description=entity.description,
                source_file=file_item.id,
                file_id=file_item.id,
            )
        entity_names = {entity.name for entity in result.entities}
        for relation in result.relations:
            for name in [relation.source, relation.target]:
                if name not in entity_names:
                    await tx.run(
                        """
                        MERGE (e:Entity {id: $id})
                        SET e.name = $name,
                            e.type = coalesce(e.type, "concept"),
                            e.description = coalesce(e.description, ""),
                            e.source_file = coalesce(e.source_file, $source_file)
                        """,
                        id=entity_id(name),
                        name=name,
                        source_file=file_item.id,
                    )
            await tx.run(
                """
                MATCH (a:Entity {name: $source})
                MATCH (b:Entity {name: $target})
                MERGE (a)-[r:RELATED_TO]->(b)
                SET r.type = $relation,
                    r.weight = $weight
                """,
                source=relation.source,
                target=relation.target,
                relation=relation.relation,
                weight=relation.weight,
            )

    async def full_graph(self) -> GraphData:
        if not self._driver:
            return await self._fallback.full_graph()
        query = """
        MATCH (n)-[r]->(m)
        RETURN n, r, m
        LIMIT 2000
        """
        return await self._read_graph(query)

    async def node_subgraph(self, node_id: str) -> GraphData:
        if not self._driver:
            return await self._fallback.node_subgraph(node_id)
        query = """
        MATCH (n:Entity)-[r]-(m)
        WHERE n.id = $node_id OR n.name = $node_id
        RETURN n, r, m
        LIMIT 500
        """
        return await self._read_graph(query, node_id=node_id)

    async def search(self, keyword: str) -> list[dict[str, Any]]:
        if not self._driver:
            return await self._fallback.search(keyword)
        async with self._driver.session(database=settings.neo4j_database) as session:
            result = await session.run(
                """
                MATCH (e:Entity)
                WHERE toLower(e.name) CONTAINS toLower($keyword)
                RETURN e
                LIMIT 50
                """,
                keyword=keyword,
            )
            rows = await result.data()
        return [dict(row["e"]) for row in rows]

    async def _read_graph(self, query: str, **params: Any) -> GraphData:
        nodes: dict[str, dict[str, Any]] = {}
        edges: dict[str, dict[str, Any]] = {}
        async with self._driver.session(database=settings.neo4j_database) as session:
            result = await session.run(query, **params)
            async for record in result:
                left = dict(record["n"])
                right = dict(record["m"])
                rel = record["r"]
                source_id = left.get("id") or entity_id(left.get("name", str(rel.start_node.id)))
                target_id = right.get("id") or entity_id(right.get("name", str(rel.end_node.id)))
                nodes[source_id] = {
                    "id": source_id,
                    "label": left.get("name", left.get("id", "未知")),
                    "name": left.get("name", left.get("id", "未知")),
                    "type": left.get("type", "concept"),
                    "description": left.get("description", ""),
                    "source_file": left.get("source_file"),
                }
                nodes[target_id] = {
                    "id": target_id,
                    "label": right.get("name", right.get("id", "未知")),
                    "name": right.get("name", right.get("id", "未知")),
                    "type": right.get("type", "concept"),
                    "description": right.get("description", ""),
                    "source_file": right.get("source_file"),
                }
                edge_id = f"{rel.element_id}"
                edges[edge_id] = {
                    "id": edge_id,
                    "source": source_id,
                    "target": target_id,
                    "label": rel.get("type", rel.type),
                    "relation": rel.get("type", rel.type),
                    "weight": rel.get("weight", 1.0),
                }
        return GraphData(
            nodes=[GraphNode(data=node) for node in nodes.values()],
            edges=[GraphEdge(data=edge) for edge in edges.values()],
        )


graph_repository = Neo4jGraphRepository()
