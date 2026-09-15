"""
文献计量分析引擎
- 发文趋势、关键词共现、作者合作网络、引文网络、突现词检测
"""
import json
from collections import Counter, defaultdict
from typing import Dict, List, Any


def compute_all(db_session) -> Dict[str, Any]:
    """计算全部文献计量指标"""
    from ..models.literature import Literature, Citation, LitRelation

    lits = db_session.query(Literature).order_by(Literature.year).all()
    citations = db_session.query(Citation).all()
    relations = db_session.query(LitRelation).all()

    if not lits:
        return {
            "total_docs": 0, "total_citations": 0, "total_relations": 0,
            "yearly_trend": [],
            "keyword_cooccurrence": {"keywords": [], "matrix": []},
            "author_network": {"nodes": [], "edges": []},
            "institution_stats": [],
            "top_cited": [],
            "doc_type_distribution": [],
            "burst_keywords": [],
            "topic_clusters": [],
        }

    return {
        "total_docs": len(lits),
        "total_citations": len(citations),
        "total_relations": len(relations),
        "yearly_trend": _yearly_trend(lits),
        "keyword_cooccurrence": _keyword_cooccurrence(lits),
        "author_network": _author_network(lits),
        "institution_stats": _institution_stats(lits),
        "top_cited": _top_cited(lits, citations),
        "doc_type_distribution": _doc_type_distribution(lits),
        "burst_keywords": _burst_keywords(lits),
        "topic_clusters": _topic_clusters(lits),
    }


def _yearly_trend(lits: List) -> List[Dict]:
    """发文量年度趋势"""
    counter = Counter(l.year for l in lits if l.year)
    return [
        {"year": y, "count": counter.get(y, 0)}
        for y in range(min(counter.keys() or [2020]), max(counter.keys() or [2024]) + 1)
    ]


def _keyword_cooccurrence(lits: List) -> Dict:
    """关键词共现矩阵 (Top 20)"""
    all_keywords = []
    doc_keywords = []
    for l in lits:
        kws = _parse_json_field(l.keywords, [])
        all_keywords.extend(kws)
        doc_keywords.append(set(kws))

    top_kws = [kw for kw, _ in Counter(all_keywords).most_common(20)]
    n = len(top_kws)
    matrix = [[0] * n for _ in range(n)]

    kw_index = {kw: i for i, kw in enumerate(top_kws)}
    for dk in doc_keywords:
        dk_top = dk & set(top_kws)
        for k1 in dk_top:
            for k2 in dk_top:
                if k1 != k2:
                    matrix[kw_index[k1]][kw_index[k2]] += 1

    return {"keywords": top_kws, "matrix": matrix}


def _author_network(lits: List) -> Dict:
    """作者合作网络"""
    edges = Counter()
    nodes = set()

    for l in lits:
        authors = _parse_json_field(l.authors, [])
        author_names = [a.get("name", "") for a in authors if isinstance(a, dict) and a.get("name")]
        nodes.update(author_names)
        for i in range(len(author_names)):
            for j in range(i + 1, len(author_names)):
                edge = tuple(sorted([author_names[i], author_names[j]]))
                edges[edge] += 1

    return {
        "nodes": [{"name": n} for n in nodes],
        "edges": [{"source": s, "target": t, "weight": w} for (s, t), w in edges.most_common(100)],
    }


def _institution_stats(lits: List) -> List[Dict]:
    """机构发文统计"""
    counter = Counter()
    for l in lits:
        authors = _parse_json_field(l.authors, [])
        for a in authors:
            if isinstance(a, dict) and a.get("institution"):
                counter[a["institution"]] += 1
    return [{"name": k, "count": v} for k, v in counter.most_common(20)]


def _top_cited(lits: List, citations: List) -> List[Dict]:
    """高被引文献"""
    cite_count = Counter(c.target_title for c in citations if c.target_title)
    ranked = []
    for l in lits:
        count = cite_count.get(l.title, 0)
        if count > 0:
            ranked.append({"id": l.id, "title": l.title, "year": l.year, "citations": count})
    ranked.sort(key=lambda x: x["citations"], reverse=True)
    return ranked[:20]


def _doc_type_distribution(lits: List) -> List[Dict]:
    """文献类型分布"""
    counter = Counter(l.doc_type or "未分类" for l in lits)
    return [{"type": k, "count": v} for k, v in counter.most_common()]


def _burst_keywords(lits: List) -> List[Dict]:
    """突现词检测 (简化版：按年份比较关键词频率变化)"""
    year_kws = defaultdict(list)
    for l in lits:
        kws = _parse_json_field(l.keywords, [])
        if l.year:
            year_kws[l.year].extend(kws)

    years = sorted(year_kws.keys())
    if len(years) < 2:
        return []

    bursts = []
    for i in range(1, len(years)):
        prev_year = years[i - 1]
        curr_year = years[i]
        prev_counter = Counter(year_kws[prev_year])
        curr_counter = Counter(year_kws[curr_year])

        for kw in curr_counter:
            prev_count = prev_counter.get(kw, 0)
            curr_count = curr_counter[kw]
            if prev_count == 0 and curr_count >= 2:
                bursts.append({
                    "keyword": kw,
                    "year": curr_year,
                    "type": "new",
                    "count": curr_count,
                })
            elif prev_count > 0 and curr_count >= prev_count * 2:
                bursts.append({
                    "keyword": kw,
                    "year": curr_year,
                    "type": "rising",
                    "count": curr_count,
                })

    bursts.sort(key=lambda x: x["year"])
    return bursts


def _topic_clusters(lits: List) -> List[Dict]:
    """研究主题聚类 (基于关键词共现的简单聚类)"""
    keyword_groups = defaultdict(set)
    for l in lits:
        kws = _parse_json_field(l.keywords, [])
        for kw in kws:
            keyword_groups[kw].update(kws)

    clusters = Counter()
    for l in lits:
        kws = _parse_json_field(l.keywords, [])
        for kw in kws:
            cluster_name = max(keyword_groups.keys(),
                key=lambda k: len(keyword_groups[k] & keyword_groups[kw]) if k != kw else 0)
            if len(keyword_groups[cluster_name] & keyword_groups[kw]) > 1:
                clusters[cluster_name] += 1

    return [{"topic": k, "count": v} for k, v in clusters.most_common(15)]


def _parse_json_field(val, default=None):
    """解析 JSON 字段"""
    if not val:
        return default or []
    if isinstance(val, list):
        return val
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return default or []
