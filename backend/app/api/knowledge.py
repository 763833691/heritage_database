"""知识库 API — 含 ChromaDB 索引、语义搜索、GB/T 7714 导出、健康检查、综述生成"""
import os
import json
import asyncio
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.auth import get_current_user, get_admin_user
from ..models.user import User
from ..models.literature import Literature, Citation, LitRelation
from ..services.kb_processor import extract_metadata, discover_relations
from ..services.kb_indexer import index_literature, delete_index, rebuild_index, semantic_search
from ..services.kb_lint import lint_knowledge_base, generate_literature_review

router = APIRouter()

# 存储路径
KB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "knowledge_base")


def _ensure_kb_dirs():
    os.makedirs(os.path.join(KB_DIR, "raw"), exist_ok=True)
    os.makedirs(os.path.join(KB_DIR, "wiki"), exist_ok=True)


def _get_rel_target_title(db, rel, lit_id: int) -> str:
    """获取关系目标文献的标题，安全处理不存在的情况"""
    target_id = rel.target_id if rel.source_id == lit_id else rel.source_id
    if not target_id:
        return "未知"
    target = db.query(Literature).filter(Literature.id == target_id).first()
    return target.title if target else "未知"


# ==================== 上传文献 ====================

@router.post("/upload")
async def upload_literature(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """上传文献并自动提取元数据 + 向量索引"""
    _ensure_kb_dirs()

    ext = file.filename.lower().rsplit('.', 1)[-1] if '.' in file.filename else ''
    if ext not in ('pdf', 'docx', 'doc', 'txt', 'md'):
        raise HTTPException(400, "仅支持 .pdf / .docx / .doc / .txt / .md")

    content = await file.read()
    if len(content) > 100 * 1024 * 1024:
        raise HTTPException(400, "文件不能超过 100MB")

    # 提取文本
    from ..services.doc_parser import extract_text
    text = extract_text(content, file.filename)
    if not text or len(text.strip()) < 50:
        raise HTTPException(400, "文件内容为空或无法识别")

    # 保存原文
    safe_name = file.filename.replace(" ", "_")
    raw_path = os.path.join(KB_DIR, "raw", safe_name)
    with open(raw_path, "wb") as f:
        f.write(content)

    # LLM 提取元数据（线程池避免阻塞）
    loop = asyncio.get_running_loop()
    try:
        metadata = await asyncio.wait_for(
            loop.run_in_executor(None, extract_metadata, text),
            timeout=180.0,
        )
    except asyncio.TimeoutError:
        metadata = {
            "title": file.filename, "year": 2024, "doc_type": "其他",
            "authors": [], "journal": "", "keywords": [], "abstract": text[:500],
            "funding": "", "methodology": "", "core_argument": "",
            "references": [], "parks_mentioned": [], "concepts_mentioned": [],
        }

    # 保存数据库
    lit = Literature(
        title=metadata.get("title", file.filename),
        authors=json.dumps(metadata.get("authors", []), ensure_ascii=False),
        year=metadata.get("year", 2024),
        journal=metadata.get("journal", ""),
        keywords=json.dumps(metadata.get("keywords", []), ensure_ascii=False),
        abstract=metadata.get("abstract", ""),
        doc_type=metadata.get("doc_type", "其他"),
        funding=metadata.get("funding", ""),
        methodology=metadata.get("methodology", ""),
        core_argument=metadata.get("core_argument", ""),
        file_path=raw_path,
        wiki_path="",
        raw_metadata=json.dumps(metadata, ensure_ascii=False),
    )
    db.add(lit)
    db.flush()

    # 保存引文关系
    refs = metadata.get("references", [])
    for ref in refs:
        if isinstance(ref, dict):
            existing = db.query(Literature).filter(
                Literature.title == ref.get("title", "")
            ).first()
            citation = Citation(
                source_id=lit.id,
                target_title=ref.get("title", ""),
                target_author=ref.get("author", ""),
                target_year=ref.get("year"),
                target_id=existing.id if existing else None,
            )
            db.add(citation)

    db.commit()
    db.refresh(lit)

    # 向量索引
    kws = metadata.get("keywords", [])
    index_literature(lit.id, lit.title, lit.abstract or "", kws)

    # 异步发现与已有文献的关系
    try:
        existing = db.query(Literature).filter(Literature.id != lit.id).all()
        existing_data = [
            {"id": e.id, "title": e.title, "year": e.year, "abstract": (e.abstract or "")[:200]}
            for e in existing[:20]
        ]
        new_data = {"id": lit.id, "title": lit.title, "year": lit.year, "abstract": lit.abstract or ""}
        relations = await asyncio.wait_for(
            loop.run_in_executor(None, discover_relations, new_data, existing_data),
            timeout=120.0,
        )

        for rel in relations:
            target_title = rel.get("target_title", "")
            if not target_title:
                continue
            target = db.query(Literature).filter(Literature.title == target_title).first()
            if target:
                db.add(LitRelation(
                    source_id=lit.id,
                    target_id=target.id,
                    relation_type=rel.get("type", "shares_topic"),
                    strength=rel.get("strength", 0.5),
                    explanation=rel.get("explanation", ""),
                ))
        db.commit()
    except (asyncio.TimeoutError, Exception) as e:
        print(f"[KB] 关系发现跳过: {str(e)[:80]}")

    return {
        "id": lit.id,
        "title": lit.title,
        "year": lit.year,
        "keywords": metadata.get("keywords", []),
        "abstract": (lit.abstract or "")[:200],
        "citations_found": len(refs),
    }


# ==================== 文献列表 ====================

@router.get("/list")
async def list_literature(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    year_from: int = Query(None),
    year_to: int = Query(None),
    doc_type: str = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出文献"""
    query = db.query(Literature)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            Literature.title.like(like) |
            Literature.abstract.like(like) |
            Literature.keywords.like(like)
        )
    if year_from:
        query = query.filter(Literature.year >= year_from)
    if year_to:
        query = query.filter(Literature.year <= year_to)
    if doc_type:
        query = query.filter(Literature.doc_type == doc_type)

    total = query.count()
    items = query.order_by(Literature.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "items": [
            {
                "id": l.id,
                "title": l.title,
                "authors": json.loads(l.authors) if l.authors else [],
                "year": l.year,
                "journal": l.journal,
                "keywords": json.loads(l.keywords) if l.keywords else [],
                "abstract": (l.abstract or "")[:300],
                "doc_type": l.doc_type,
                "citation_count": l.citation_count,
                "created_at": str(l.created_at),
            }
            for l in items
        ],
    }


# ==================== 文献详情 ====================

@router.get("/detail/{lit_id}")
async def get_literature_detail(
    lit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """文献详情 + 关联文献"""
    lit = db.query(Literature).filter(Literature.id == lit_id).first()
    if not lit:
        raise HTTPException(404, "文献不存在")

    citations_from = db.query(Citation).filter(Citation.source_id == lit_id).all()
    citations_to = db.query(Citation).filter(Citation.target_id == lit_id).all()

    relations = db.query(LitRelation).filter(
        (LitRelation.source_id == lit_id) | (LitRelation.target_id == lit_id)
    ).all()

    kws = json.loads(lit.keywords) if lit.keywords else []
    related = []
    if kws:
        conditions = [Literature.keywords.like(f"%{kw}%") for kw in kws[:5]]
        from sqlalchemy import or_
        related = db.query(Literature).filter(
            Literature.id != lit_id,
            or_(*conditions),
        ).limit(10).all()

    return {
        "id": lit.id,
        "title": lit.title,
        "authors": json.loads(lit.authors) if lit.authors else [],
        "year": lit.year,
        "journal": lit.journal,
        "keywords": kws,
        "abstract": lit.abstract,
        "doc_type": lit.doc_type,
        "funding": lit.funding,
        "methodology": lit.methodology,
        "core_argument": lit.core_argument,
        "citation_count": lit.citation_count,
        "created_at": str(lit.created_at),
        "citations_from": [
            {"title": c.target_title, "author": c.target_author, "year": c.target_year, "in_db": bool(c.target_id)}
            for c in citations_from
        ],
        "cited_by": [
            {"title": c.source.title, "year": c.source.year} if c.source else {"title": "未知"}
            for c in citations_to
        ],
        "relations": [
            {
                "target_title": _get_rel_target_title(db, r, lit_id),
                "type": r.relation_type,
                "explanation": r.explanation,
            }
            for r in relations
        ],
        "related": [
            {"id": r.id, "title": r.title, "year": r.year}
            for r in related
        ],
    }


# ==================== 删除文献 ====================

@router.delete("/delete/{lit_id}")
async def delete_literature(
    lit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """删除文献"""
    lit = db.query(Literature).filter(Literature.id == lit_id).first()
    if not lit:
        raise HTTPException(404, "文献不存在")
    if lit.file_path and os.path.exists(lit.file_path):
        os.remove(lit.file_path)
    db.delete(lit)
    db.commit()
    # 删除向量索引
    delete_index(lit_id)
    return {"message": "已删除"}


# ==================== 文献计量 ====================

@router.get("/bibliometrics")
async def get_bibliometrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取全库文献计量指标"""
    from ..services.bibliometrics import compute_all
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, compute_all, db)


# ==================== 语义搜索（ChromaDB 优先，SQL 兜底）====================

@router.get("/search")
async def search_literature(
    q: str = Query(...),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """语义搜索（ChromaDB 向量检索优先，SQL LIKE 兜底）"""
    results = semantic_search(q, limit, db)
    return {"query": q, "results": results, "mode": "semantic" if any(r.get("similarity") for r in results) else "sql"}


# ==================== 向量索引管理 ====================

@router.post("/reindex")
async def reindex_knowledge_base(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """全量重建文献向量索引"""
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, rebuild_index, db)
    return result


# ==================== GB/T 7714 引用格式导出 ====================

@router.get("/cite/{lit_id}")
async def get_citation_gbt7714(
    lit_id: int,
    style: str = Query("gbt7714", description="引用格式: gbt7714 | apa | mla"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取 GB/T 7714 / APA / MLA 格式引用"""
    lit = db.query(Literature).filter(Literature.id == lit_id).first()
    if not lit:
        raise HTTPException(404, "文献不存在")

    authors = json.loads(lit.authors) if lit.authors else []
    formatted = _format_citation(lit, authors, style)
    return {"lit_id": lit_id, "style": style, "citation": formatted}


@router.post("/cite/batch")
async def batch_citation(
    lit_ids: List[int],
    style: str = Query("gbt7714"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量生成引用"""
    lits = db.query(Literature).filter(Literature.id.in_(lit_ids)).all()
    id_map = {l.id: l for l in lits}
    results = []
    for lid in lit_ids:
        lit = id_map.get(lid)
        if lit:
            authors = json.loads(lit.authors) if lit.authors else []
            results.append({
                "lit_id": lid,
                "title": lit.title,
                "citation": _format_citation(lit, authors, style),
            })
    return {"style": style, "citations": results}


def _format_citation(lit, authors: list, style: str) -> str:
    """格式化引用"""
    author_str = ""
    if authors:
        names = [a.get("name", "") for a in authors[:3] if isinstance(a, dict)]
        if names:
            author_str = ", ".join(names)
            if len(authors) > 3:
                author_str += ", 等" if style == "gbt7714" else " et al."

    year = str(lit.year) if lit.year else ""
    title = lit.title or ""

    if style == "gbt7714":
        # GB/T 7714-2015
        parts = []
        if author_str:
            parts.append(author_str + ".")
        parts.append(f"{title}[{lit.doc_type or 'J'}].")
        if lit.journal:
            parts.append(f"{lit.journal}.")
        if year:
            parts.append(f"{year}.")
        return " ".join(parts)

    elif style == "apa":
        parts = []
        if author_str:
            parts.append(f"{author_str} ({year}).")
        else:
            parts.append(f"({year}).")
        parts.append(f"{title}.")
        if lit.journal:
            parts.append(f"*{lit.journal}*.")
        return " ".join(parts)

    elif style == "mla":
        parts = []
        if author_str:
            parts.append(f'{author_str}. "{title}."')
        else:
            parts.append(f'"{title}."')
        if lit.journal:
            parts.append(f"*{lit.journal}*")
        if year:
            parts.append(f"{year}.")
        return " ".join(parts)

    return f"{author_str}. {title}. {year}."


# ==================== 知识库图谱数据 ====================

@router.get("/graph")
async def get_knowledge_graph(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取文献知识图谱数据（引用网络 + 语义关系 + 关键词关联）"""
    lits = db.query(Literature).all()
    citations = db.query(Citation).all()
    relations = db.query(LitRelation).all()

    nodes = []
    edges = []
    lit_ids = {l.id for l in lits}

    # 文献节点
    for l in lits:
        kws = json.loads(l.keywords) if l.keywords else []
        authors = json.loads(l.authors) if l.authors else []
        author_names = [a.get("name", "") for a in authors[:2] if isinstance(a, dict)]
        nodes.append({
            "id": f"lit_{l.id}",
            "label": l.title[:30],
            "type": "literature",
            "year": l.year,
            "doc_type": l.doc_type,
            "keywords": kws[:5],
            "authors": author_names,
            "symbolSize": 20 + len(kws) * 2,
        })

    # 关键词节点（高频）
    kw_counter = {}
    for l in lits:
        kws = json.loads(l.keywords) if l.keywords else []
        for kw in kws:
            if kw not in kw_counter:
                kw_counter[kw] = {"count": 0, "lits": []}
            kw_counter[kw]["count"] += 1
            kw_counter[kw]["lits"].append(l.id)

    top_kws = sorted(kw_counter.items(), key=lambda x: x[1]["count"], reverse=True)[:30]
    for kw, info in top_kws:
        nodes.append({
            "id": f"kw_{kw}",
            "label": kw,
            "type": "keyword",
            "count": info["count"],
            "symbolSize": 10 + info["count"] * 3,
        })
        # 关键词 → 文献边
        for lit_id in info["lits"]:
            edges.append({
                "source": f"kw_{kw}",
                "target": f"lit_{lit_id}",
                "type": "has_keyword",
            })

    # 引用边
    for c in citations:
        if c.source_id in lit_ids:
            edges.append({
                "source": f"lit_{c.source_id}",
                "target": f"lit_{c.target_id}" if c.target_id and c.target_id in lit_ids else f"lit_{c.source_id}",
                "type": "cites",
                "label": f"[{c.target_year or '?'}] {c.target_title[:20]}",
            })

    # 语义关系边
    for r in relations:
        if r.source_id in lit_ids and r.target_id in lit_ids:
            edges.append({
                "source": f"lit_{r.source_id}",
                "target": f"lit_{r.target_id}",
                "type": r.relation_type,
                "label": r.relation_type,
            })

    return {"nodes": nodes, "edges": edges, "total": len(nodes)}


# ==================== 知识库健康检查 ====================

@router.get("/lint")
async def lint_kb(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """知识库健康检查"""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lint_knowledge_base, db)


# ==================== 自动综述 ====================

@router.get("/review")
async def get_literature_review(
    topic: str = Query("", description="综述主题，为空则全库综述"),
    max_lits: int = Query(20, ge=5, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """生成文献综述结构化数据"""
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, generate_literature_review, db, topic, max_lits)
    return result


@router.post("/review/generate")
async def generate_review_with_llm(
    topic: str = Query("", description="综述主题"),
    max_lits: int = Query(20, ge=5, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """使用 LLM 生成完整文献综述"""
    from ..core.config import settings

    if not settings.ai_available:
        raise HTTPException(400, "需要配置 AI API key 才能生成综述")

    # 先获取结构化数据
    data = generate_literature_review(db, topic, max_lits)
    if "error" in data:
        return data

    # 拼接 LLM 提示词
    lit_texts = []
    for lit in data["lits"]:
        authors = ", ".join([a.get("name", "") for a in lit["authors"][:3]])
        lit_texts.append(
            f"- [{lit['year']}] {authors}. {lit['title']}. "
            f"论点: {lit.get('core_argument', '')}. 方法: {lit.get('methodology', '')}"
        )

    top_kws = ", ".join(data.get("top_keywords", [])[:10])
    methods = ", ".join([m["name"] for m in data.get("methods", [])[:5]])

    prompt = f"""你是文化遗产保护研究领域的资深学者。请根据以下文献数据，撰写一篇学术综述。

## 综述主题
{topic or "文化遗产保护研究"}

## 文献概况
- 相关文献: {data['total_found']} 篇
- 时间跨度: {data.get('years_range', [])}
- 高频关键词: {top_kws}
- 常用方法: {methods}

## 文献列表
{chr(10).join(lit_texts)}

## 要求
1. 按研究脉络分段：研究缘起 → 主要议题 → 方法论演进 → 前沿趋势 → 研究展望
2. 使用学术语言，标注引用（如 [1]、[2]）
3. 指出研究空白和方法论局限
4. 1500-2500字
5. 使用Markdown格式"""

    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=settings.DASHSCOPE_API_KEY,
            base_url=settings.LLM_BASE_URL or "https://dashscope.aliyuncs.com/compatible-mode/v1",
            timeout=120.0,
        )
        response = client.chat.completions.create(
            model=settings.AI_MODEL,
            messages=[
                {"role": "system", "content": "你是文化遗产保护研究领域的资深学者，擅长撰写文献综述。"},
                {"role": "user", "content": prompt},
            ],
            max_tokens=4096,
            temperature=0.7,
        )
        review_text = response.choices[0].message.content

        return {
            "topic": topic or "文化遗产保护",
            "lits_referenced": data["total_found"],
            "review": review_text,
            "references": [
                {"id": lit["id"], "title": lit["title"], "year": lit["year"]}
                for lit in data["lits"]
            ],
        }
    except Exception as e:
        raise HTTPException(500, f"综述生成失败: {str(e)}")
