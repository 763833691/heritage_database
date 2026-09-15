from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from ..core.database import get_db, get_neo4j, neo4j_driver
from ..core.auth import get_current_user
from ..models.user import User
from ..models.park import Park
from ..models.score import Score
from ..models.indicator import Indicator

router = APIRouter()


def has_neo4j():
    """检查Neo4j是否可用"""
    return neo4j_driver is not None


@router.get("/stats")
async def kg_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """知识图谱统计信息"""
    if has_neo4j():
        # Neo4j模式
        with get_neo4j() as session:
            node_count = session.run("MATCH (n) RETURN count(n) as c").single()["c"]
            rel_count = session.run("MATCH ()-[r]->() RETURN count(r) as c").single()["c"]
            return {
                "total_nodes": node_count,
                "total_relations": rel_count,
                "source": "neo4j",
            }
    else:
        # SQLite模式 - 从关系数据库生成统计
        parks_count = db.query(Park).count()
        indicators_count = db.query(Indicator).count()
        scores_count = db.query(Score).count()

        return {
            "total_nodes": parks_count + indicators_count,
            "total_relations": scores_count,
            "source": "sqlite",
            "node_types": [
                {"labels": ["Park"], "count": parks_count},
                {"labels": ["Indicator"], "count": indicators_count},
            ],
            "relation_types": [
                {"type": "HAS_SCORE", "count": scores_count},
            ],
        }


@router.get("/entity/{entity_type}")
async def get_entities(
    entity_type: str,
    name: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取实体列表"""
    if has_neo4j():
        with get_neo4j() as session:
            if name:
                result = session.run(
                    f"MATCH (n:{entity_type}) WHERE n.name CONTAINS $name RETURN n LIMIT $limit",
                    name=name, limit=limit
                )
            else:
                result = session.run(f"MATCH (n:{entity_type}) RETURN n LIMIT $limit", limit=limit)
            return [dict(record["n"]) for record in result]

    # SQLite模式
    if entity_type == "Park":
        query = db.query(Park)
        if name:
            query = query.filter(Park.name.contains(name) | Park.short_name.contains(name))
        parks = query.limit(limit).all()
        return [
            {
                "name": p.name,
                "short_name": p.short_name,
                "type": p.park_type,
                "province": p.province,
                "city": p.city,
                "batch": p.batch,
                "area": p.total_area,
            }
            for p in parks
        ]

    elif entity_type == "Indicator":
        indicators = db.query(Indicator).limit(limit).all()
        return [
            {
                "code": i.code,
                "name": i.name,
                "dimension": i.dimension,
            }
            for i in indicators
        ]

    return []


@router.get("/entity/{entity_type}/{name}")
async def get_entity_detail(
    entity_type: str,
    name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取实体详情"""
    if has_neo4j():
        with get_neo4j() as session:
            result = session.run(
                f"MATCH (n:{entity_type} {{name: $name}}) OPTIONAL MATCH (n)-[r]->(m) RETURN n, collect({{relation: type(r), target: m.name}}) as relations",
                name=name
            )
            record = result.single()
            if record:
                return {"entity": dict(record["n"]), "relations": record["relations"]}
        return {"error": "实体不存在"}

    # SQLite模式
    if entity_type == "Park":
        park = db.query(Park).filter(
            (Park.name == name) | (Park.short_name == name)
        ).first()
        if park:
            scores = (
                db.query(Score, Indicator)
                .join(Indicator, Score.indicator_id == Indicator.id)
                .filter(Score.park_id == park.id)
                .all()
            )
            return {
                "entity": {
                    "name": park.name,
                    "short_name": park.short_name,
                    "type": park.park_type,
                    "province": park.province,
                },
                "relations": [
                    {
                        "relation": "HAS_SCORE",
                        "target": f"{ind.code} {ind.name}",
                        "value": sc.normalized_score,
                    }
                    for sc, ind in scores
                ],
            }

    return {"error": "实体不存在"}


@router.get("/neighbors/{name}")
async def get_neighbors(
    name: str,
    depth: int = Query(2, ge=1, le=3),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取邻居节点"""
    if has_neo4j():
        with get_neo4j() as session:
            result = session.run(
                f"MATCH path = (n {{name: $name}})-[*1..{depth}]-(m) RETURN path LIMIT 100",
                name=name
            )
            nodes = {}
            edges = []
            for record in result:
                path = record["path"]
                for node in path.nodes:
                    nid = node.element_id
                    if nid not in nodes:
                        nodes[nid] = dict(node)
                for rel in path.relationships:
                    edges.append({
                        "source": rel.start_node.get("name"),
                        "target": rel.end_node.get("name"),
                        "type": rel.type,
                    })
            return {"nodes": list(nodes.values()), "edges": edges}

    # SQLite模式 - 返回公园及其评分关系
    park = db.query(Park).filter(
        (Park.name == name) | (Park.short_name == name)
    ).first()

    if not park:
        # 返回所有公园的概览
        parks = db.query(Park).all()
        nodes = [{"name": p.short_name or p.name, "type": p.park_type, "labels": ["Park"]} for p in parks]
        edges = []

        # 同类型公园之间建立关系
        type_groups = {}
        for p in parks:
            if p.park_type not in type_groups:
                type_groups[p.park_type] = []
            type_groups[p.park_type].append(p.short_name or p.name)

        for ptype, names in type_groups.items():
            for i in range(len(names)):
                for j in range(i + 1, len(names)):
                    edges.append({"source": names[i], "target": names[j], "type": "SIMILAR_TYPE"})

        return {"nodes": nodes, "edges": edges}

    # 返回特定公园的详情
    scores = (
        db.query(Score, Indicator)
        .join(Indicator, Score.indicator_id == Indicator.id)
        .filter(Score.park_id == park.id)
        .all()
    )

    nodes = [{"name": park.short_name or park.name, "type": park.park_type, "labels": ["Park"]}]
    edges = []

    for sc, ind in scores:
        nodes.append({
            "name": f"{ind.code} {ind.name}",
            "type": "Indicator",
            "labels": ["Indicator"],
            "score": sc.normalized_score,
        })
        edges.append({
            "source": park.short_name or park.name,
            "target": f"{ind.code} {ind.name}",
            "type": "HAS_SCORE",
            "value": sc.normalized_score,
        })

    return {"nodes": nodes, "edges": edges}


@router.get("/search")
async def search_kg(
    q: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """搜索知识图谱"""
    results = []

    # 搜索公园
    parks = db.query(Park).filter(
        Park.name.contains(q) | Park.short_name.contains(q)
    ).all()
    for p in parks:
        results.append({"labels": ["Park"], "data": {"name": p.name, "short_name": p.short_name, "type": p.park_type}})

    # 搜索指标
    indicators = db.query(Indicator).filter(
        Indicator.name.contains(q) | Indicator.code.contains(q)
    ).all()
    for ind in indicators:
        results.append({"labels": ["Indicator"], "data": {"code": ind.code, "name": ind.name, "dimension": ind.dimension}})

    return results
