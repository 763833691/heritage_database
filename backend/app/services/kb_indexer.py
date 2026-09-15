"""
知识库向量索引 + 语义搜索服务
- 使用 jieba + TF-IDF 做本地向量化（无需下载模型，秒级可用）
- 上传文献时自动索引
- 支持批量重建索引
- ChromaDB 作为向量存储后端（如有ONNX模型则用，否则纯本地TF-IDF）
"""
import json
import numpy as np
from typing import List, Dict, Optional


# ============ TF-IDF 引擎（纯本地，无网络依赖）============

_tfidf_vectorizer = None
_tfidf_matrix = None
_tfidf_doc_ids = []
_tfidf_ready = False


def _get_tfidf_vectorizer():
    """懒加载 TF-IDF + jieba 分词器"""
    global _tfidf_vectorizer
    if _tfidf_vectorizer is None:
        import jieba
        from sklearn.feature_extraction.text import TfidfVectorizer

        def jieba_cut(text):
            return " ".join(jieba.cut(text))

        _tfidf_vectorizer = TfidfVectorizer(
            tokenizer=jieba_cut,
            max_features=5000,
            ngram_range=(1, 2),
        )
    return _tfidf_vectorizer


def _build_tfidf_index(db_session):
    """从数据库构建 TF-IDF 索引"""
    global _tfidf_matrix, _tfidf_doc_ids, _tfidf_ready

    from ..models.literature import Literature

    lits = db_session.query(Literature).all()
    if not lits:
        _tfidf_matrix = None
        _tfidf_doc_ids = []
        _tfidf_ready = True
        return

    vectorizer = _get_tfidf_vectorizer()
    documents = []
    ids = []

    for lit in lits:
        kws = json.loads(lit.keywords) if lit.keywords else []
        kw_text = " ".join(kws) if kws else ""
        doc_text = f"{lit.title} {kw_text} {lit.abstract or ''}"
        documents.append(doc_text)
        ids.append(lit.id)

    _tfidf_matrix = vectorizer.fit_transform(documents)
    _tfidf_doc_ids = ids
    _tfidf_ready = True
    print(f"[KB Indexer] TF-IDF 索引已构建: {len(ids)} 篇文献, 词汇量 {_tfidf_matrix.shape[1]}")


def _ensure_tfidf_ready(db_session):
    """确保 TF-IDF 索引已初始化"""
    global _tfidf_ready
    if not _tfidf_ready:
        _build_tfidf_index(db_session)


def invalidate_tfidf_cache():
    """使 TF-IDF 缓存失效（上传/删除文献后调用）"""
    global _tfidf_ready, _tfidf_matrix, _tfidf_doc_ids, _tfidf_vectorizer
    _tfidf_ready = False
    _tfidf_matrix = None
    _tfidf_doc_ids = []
    _tfidf_vectorizer = None


# ============ ChromaDB 索引（可选，有ONNX模型时启用）============

def _chroma_available() -> bool:
    """检查 ChromaDB + ONNX 模型是否可用"""
    try:
        from ..core.database import get_literature_chroma
        collection = get_literature_chroma()
        if collection is None:
            return False
        # 检查是否能真正做 embedding（不触发下载，只测试已有模型）
        import os
        cache_dir = os.path.expanduser("~/.cache/chroma/onnx_models/all-MiniLM-L6-v2")
        onnx_file = os.path.join(cache_dir, "onnx.tar.gz")
        if os.path.exists(onnx_file) and os.path.getsize(onnx_file) > 70_000_000:
            return True
        # 模型未下载完成，不使用 ChromaDB embedding
        return False
    except Exception:
        return False


def index_literature(lit_id: int, title: str, abstract: str, keywords: List[str]) -> bool:
    """将单篇文献索引到 ChromaDB（如果可用）"""
    invalidate_tfidf_cache()

    if not _chroma_available():
        return False  # 静默跳过，TF-IDF 会处理搜索

    from ..core.database import get_literature_chroma

    collection = get_literature_chroma()
    if collection is None:
        return False

    kw_text = "、".join(keywords) if keywords else ""
    doc_text = f"{title}\n关键词：{kw_text}\n{abstract}" if abstract else title

    try:
        collection.upsert(
            ids=[str(lit_id)],
            documents=[doc_text],
            metadatas=[{
                "title": title,
                "keywords": json.dumps(keywords, ensure_ascii=False) if keywords else "",
                "lit_id": lit_id,
            }],
        )
        return True
    except Exception as e:
        print(f"[KB Indexer] ChromaDB 索引文献 {lit_id} 失败: {e}")
        return False


def delete_index(lit_id: int) -> bool:
    """从索引中删除文献"""
    invalidate_tfidf_cache()

    if _chroma_available():
        from ..core.database import get_literature_chroma
        collection = get_literature_chroma()
        if collection:
            try:
                collection.delete(ids=[str(lit_id)])
            except Exception:
                pass
    return True


def rebuild_index(db_session) -> Dict:
    """全量重建索引"""
    invalidate_tfidf_cache()
    _build_tfidf_index(db_session)

    chroma_ok = False
    if _chroma_available():
        from ..core.database import get_literature_chroma
        from ..models.literature import Literature

        collection = get_literature_chroma()
        lits = db_session.query(Literature).all()

        if lits:
            ids = []
            documents = []
            metadatas = []

            for lit in lits:
                kws = json.loads(lit.keywords) if lit.keywords else []
                kw_text = "、".join(kws)
                doc_text = f"{lit.title}\n关键词：{kw_text}\n{lit.abstract or ''}"
                ids.append(str(lit.id))
                documents.append(doc_text)
                metadatas.append({
                    "title": lit.title,
                    "keywords": json.dumps(kws, ensure_ascii=False),
                    "lit_id": lit.id,
                })

            try:
                try:
                    collection.delete(ids=[str(lit.id) for lit in lits])
                except Exception:
                    pass
                collection.add(ids=ids, documents=documents, metadatas=metadatas)
                chroma_ok = True
            except Exception as e:
                print(f"[KB Indexer] ChromaDB 重建失败: {e}")

    return {
        "success": True,
        "indexed": len(_tfidf_doc_ids) if _tfidf_ready else 0,
        "engine": "ChromaDB+TF-IDF" if chroma_ok else "TF-IDF (本地)",
    }


def semantic_search(query: str, limit: int = 10, db_session=None) -> List[Dict]:
    """
    语义搜索文献
    优先 ChromaDB（如果模型已下载），否则用本地 TF-IDF + jieba
    """
    # 先尝试 ChromaDB
    if _chroma_available():
        result = _chroma_search(query, limit, db_session)
        if result:
            return result

    # 回退到本地 TF-IDF
    return _tfidf_search(query, limit, db_session)


def _chroma_search(query: str, limit: int, db_session) -> List[Dict]:
    """ChromaDB 语义搜索"""
    from ..core.database import get_literature_chroma

    collection = get_literature_chroma()
    if collection is None:
        return []

    try:
        results = collection.query(query_texts=[query], n_results=limit)
        if not results or not results.get("ids") or not results["ids"][0]:
            return []
        return _format_results(results, db_session)
    except Exception as e:
        print(f"[KB Indexer] ChromaDB 搜索失败: {e}")
        return []


def _tfidf_search(query: str, limit: int, db_session) -> List[Dict]:
    """本地 TF-IDF + jieba 语义搜索"""
    if not db_session:
        return _sql_fallback(query, limit, db_session)

    _ensure_tfidf_ready(db_session)

    if _tfidf_matrix is None or len(_tfidf_doc_ids) == 0:
        return _sql_fallback(query, limit, db_session)

    import jieba
    vectorizer = _get_tfidf_vectorizer()

    # 向量化查询
    query_vec = vectorizer.transform([" ".join(jieba.cut(query))])

    # 计算余弦相似度
    from sklearn.metrics.pairwise import cosine_similarity
    similarities = cosine_similarity(query_vec, _tfidf_matrix)[0]

    # 取 top-N
    top_indices = np.argsort(similarities)[::-1][:limit]

    from ..models.literature import Literature

    result_ids = [_tfidf_doc_ids[i] for i in top_indices if similarities[i] > 0]
    if not result_ids:
        return _sql_fallback(query, limit, db_session)

    lits = db_session.query(Literature).filter(
        Literature.id.in_(result_ids)
    ).all()
    lit_map = {l.id: l for l in lits}

    output = []
    for i in top_indices[:limit]:
        lit_id = _tfidf_doc_ids[i]
        lit = lit_map.get(lit_id)
        sim = float(similarities[i])
        if sim <= 0:
            continue
        output.append({
            "id": lit_id,
            "title": lit.title if lit else "",
            "year": lit.year if lit else None,
            "abstract": (lit.abstract or "")[:300] if lit else "",
            "keywords": json.loads(lit.keywords) if lit and lit.keywords else [],
            "similarity": round(sim, 4),
        })

    return output


def _format_results(chroma_results, db_session) -> List[Dict]:
    """格式化 ChromaDB 返回结果"""
    lit_ids = []
    for id_str in chroma_results["ids"][0]:
        try:
            lit_ids.append(int(id_str))
        except (ValueError, TypeError):
            pass

    if not lit_ids:
        return []

    from ..models.literature import Literature
    lits = db_session.query(Literature).filter(
        Literature.id.in_(lit_ids)
    ).all() if db_session else []

    lit_map = {l.id: l for l in lits}

    output = []
    for i, id_str in enumerate(chroma_results["ids"][0]):
        lit_id = int(id_str) if id_str.lstrip('-').isdigit() else None
        lit = lit_map.get(lit_id) if lit_id else None
        distance = chroma_results.get("distances", [[]])[0][i] if chroma_results.get("distances") else None
        output.append({
            "id": lit_id,
            "title": lit.title if lit else chroma_results["metadatas"][0][i].get("title", ""),
            "year": lit.year if lit else None,
            "abstract": (lit.abstract or "")[:300] if lit else "",
            "keywords": json.loads(lit.keywords) if lit and lit.keywords else [],
            "similarity": round(1 - distance, 4) if distance is not None else None,
        })

    return output


def _sql_fallback(query: str, limit: int, db_session) -> List[Dict]:
    """SQL LIKE 降级搜索"""
    if not db_session:
        return []
    from ..models.literature import Literature

    like = f"%{query}%"
    results = db_session.query(Literature).filter(
        Literature.title.like(like) |
        Literature.abstract.like(like) |
        Literature.keywords.like(like)
    ).limit(limit).all()

    return [
        {
            "id": r.id,
            "title": r.title,
            "year": r.year,
            "abstract": (r.abstract or "")[:300],
            "keywords": json.loads(r.keywords) if r.keywords else [],
            "similarity": None,
        }
        for r in results
    ]
