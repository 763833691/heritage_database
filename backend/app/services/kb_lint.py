"""
知识库健康检查 + 自动综述生成
"""
import json
import re
from typing import Dict, Any, List
from collections import Counter


def lint_knowledge_base(db_session) -> Dict[str, Any]:
    """知识库健康检查"""
    from ..models.literature import Literature, Citation, LitRelation

    lits = db_session.query(Literature).all()
    citations = db_session.query(Citation).all()
    relations = db_session.query(LitRelation).all()

    issues = []
    stats = {"total": len(lits), "citations": len(citations), "relations": len(relations)}

    if not lits:
        return {"stats": stats, "issues": [], "summary": "知识库为空"}

    titles = [l.title for l in lits]
    title_counter = Counter(titles)

    for lit in lits:
        # 1. 重复标题检查
        if title_counter.get(lit.title, 0) > 1:
            issues.append({
                "level": "warning",
                "lit_id": lit.id,
                "title": lit.title,
                "message": f"标题重复（出现 {title_counter[lit.title]} 次）",
            })

        # 2. 缺失元数据
        kws = json.loads(lit.keywords) if lit.keywords else []
        authors = json.loads(lit.authors) if lit.authors else []
        if not kws:
            issues.append({
                "level": "info",
                "lit_id": lit.id,
                "title": lit.title,
                "message": "缺少关键词",
            })
        if not authors:
            issues.append({
                "level": "info",
                "lit_id": lit.id,
                "title": lit.title,
                "message": "缺少作者信息",
            })
        if not lit.abstract or len(lit.abstract.strip()) < 20:
            issues.append({
                "level": "info",
                "lit_id": lit.id,
                "title": lit.title,
                "message": "摘要缺失或过短",
            })

        # 3. 孤岛文献（无引文、无关系）
        has_citation = any(c.source_id == lit.id or c.target_id == lit.id for c in citations)
        has_relation = any(r.source_id == lit.id or r.target_id == lit.id for r in relations)
        if not has_citation and not has_relation and len(lits) > 3:
            issues.append({
                "level": "info",
                "lit_id": lit.id,
                "title": lit.title,
                "message": "孤岛文献：无引用或关联关系",
            })

        # 4. 年份异常
        if lit.year and (lit.year < 1900 or lit.year > 2026):
            issues.append({
                "level": "warning",
                "lit_id": lit.id,
                "title": lit.title,
                "message": f"年份异常: {lit.year}",
            })

    # 5. 相互矛盾的观点检测（基于 relation type）
    contradictions = [r for r in relations if r.relation_type == "contradicts"]
    if contradictions:
        for r in contradictions[:5]:
            source = db_session.query(Literature).filter(Literature.id == r.source_id).first()
            target = db_session.query(Literature).filter(Literature.id == r.target_id).first()
            if source and target:
                issues.append({
                    "level": "warning",
                    "lit_id": r.source_id,
                    "title": source.title,
                    "message": f"与 [{target.title}] 存在矛盾观点: {r.explanation or '(无说明)'}",
                })

    # 6. 参考文献完整度
    lit_with_refs = sum(1 for l in lits if any(c.source_id == l.id for c in citations))
    if len(lits) > 5 and lit_with_refs < len(lits) * 0.3:
        issues.append({
            "level": "info",
            "lit_id": None,
            "title": "(全局)",
            "message": f"仅 {lit_with_refs}/{len(lits)} 篇文献有引用记录，建议补充",
        })

    # 按严重程度排序
    severity_order = {"warning": 0, "info": 1}
    issues.sort(key=lambda x: severity_order.get(x["level"], 2))

    summary = f"共 {len(lits)} 篇文献，发现 {len(issues)} 个问题（{sum(1 for i in issues if i['level']=='warning')} 个警告，{sum(1 for i in issues if i['level']=='info')} 个提示）"

    return {"stats": stats, "issues": issues, "summary": summary}


def generate_literature_review(db_session, topic: str = "", max_lits: int = 20) -> Dict[str, Any]:
    """基于知识库生成文献综述所需的结构化数据"""
    from ..models.literature import Literature

    query = db_session.query(Literature)
    if topic:
        like = f"%{topic}%"
        query = query.filter(
            Literature.title.like(like) |
            Literature.abstract.like(like) |
            Literature.keywords.like(like)
        )
    lits = query.order_by(Literature.year.desc()).limit(max_lits).all()

    if not lits:
        return {"error": "未找到相关文献", "lits": []}

    # 提取综述结构
    years = sorted(set(l.year for l in lits if l.year))
    all_keywords = []
    for l in lits:
        kws = json.loads(l.keywords) if l.keywords else []
        all_keywords.extend(kws)
    top_kws = [kw for kw, _ in Counter(all_keywords).most_common(15)]

    # 按年份分组
    by_year = {}
    for l in lits:
        y = l.year or "未知"
        if y not in by_year:
            by_year[y] = []
        by_year[y].append({
            "id": l.id,
            "title": l.title,
            "authors": json.loads(l.authors) if l.authors else [],
            "core_argument": l.core_argument or "",
        })

    # 方法论统计
    methods = Counter()
    for l in lits:
        if l.methodology:
            for m in re.split(r'[,;，；、]', l.methodology):
                m = m.strip()
                if m:
                    methods[m] += 1

    return {
        "topic": topic or "全部",
        "total_found": len(lits),
        "years_range": [min(years), max(years)] if years else [],
        "top_keywords": top_kws,
        "methods": [{"name": k, "count": v} for k, v in methods.most_common(10)],
        "by_year": [{"year": y, "papers": papers} for y, papers in sorted(by_year.items(), reverse=True)],
        "lits": [
            {
                "id": l.id,
                "title": l.title,
                "year": l.year,
                "authors": json.loads(l.authors) if l.authors else [],
                "keywords": json.loads(l.keywords) if l.keywords else [],
                "abstract": (l.abstract or "")[:300],
                "core_argument": l.core_argument or "",
                "methodology": l.methodology or "",
            }
            for l in lits
        ],
    }
