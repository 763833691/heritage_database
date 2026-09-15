"""
RAG 问答引擎
- 保留本地模板模式作为降级方案
- 当配置了真实 AI key 时，调用 LLM API 生成回答
- 支持流式 (SSE) 输出
- 集成知识库文献检索
"""
import json
from typing import List, Dict, Any, Optional, AsyncGenerator

from ..core.config import settings
from .llm_provider import get_llm_provider, MockProvider
from .prompt_builder import build_messages


class RAGEngine:
    """基于知识图谱的RAG问答引擎"""

    def __init__(self, db, neo4j_session=None, chroma=None):
        self.db = db
        self.neo4j = neo4j_session
        self.chroma = chroma
        self.llm = get_llm_provider()

    async def query(
        self,
        question: str,
        conversation_history: List[Dict] = None,
    ) -> Dict[str, Any]:
        """处理用户查询"""
        # 1-4: RAG 管线（与本地模式共用）
        intent = self._classify_intent(question)
        db_context = self._query_database(question, intent)
        doc_context = self._query_vector_store(question) if self.chroma else ""
        lit_context = self._query_knowledge_base(question)
        context = self._assemble_context(db_context, doc_context, lit_context)
        chart_data = self._generate_chart_data(question, intent)

        sources = ["调研数据库", "知识图谱"]
        if lit_context:
            sources.append("文献知识库")

        # 5: 生成回答 — 分支：AI / 本地模板
        if settings.ai_available and not isinstance(self.llm, MockProvider):
            try:
                messages = build_messages(
                    question=question,
                    db_context=db_context,
                    doc_context=doc_context,
                    lit_context=lit_context,
                    conversation_history=conversation_history,
                )
                answer = await self.llm.chat(messages)
                if not answer:
                    answer = self._generate_answer(question, context, intent)
            except Exception as e:
                print(f"[RAG] AI 调用失败，回退到本地模板: {e}")
                answer = self._generate_answer(question, context, intent)
        else:
            answer = self._generate_answer(question, context, intent)

        return {
            "answer": answer,
            "sources": sources,
            "chart_data": chart_data,
        }

    async def stream_query(
        self,
        question: str,
        conversation_history: List[Dict] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式查询
        逐 token yield，格式: {"type": "token"|"chart_data"|"sources"|"done", "data": ...}
        """
        intent = self._classify_intent(question)
        db_context = self._query_database(question, intent)
        doc_context = self._query_vector_store(question) if self.chroma else ""
        lit_context = self._query_knowledge_base(question)
        chart_data = self._generate_chart_data(question, intent)

        sources = ["调研数据库", "知识图谱"]
        if lit_context:
            sources.append("文献知识库")

        if settings.ai_available and not isinstance(self.llm, MockProvider):
            try:
                messages = build_messages(
                    question=question,
                    db_context=db_context,
                    doc_context=doc_context,
                    lit_context=lit_context,
                    conversation_history=conversation_history,
                )
                full_answer = ""
                async for token in self.llm.chat_stream(messages):
                    full_answer += token
                    yield {"type": "token", "data": token}

                if not full_answer:
                    fallback = self._generate_answer(question,
                        self._assemble_context(db_context, doc_context, lit_context), intent)
                    for i in range(0, len(fallback), 10):
                        yield {"type": "token", "data": fallback[i:i+10]}

            except Exception as e:
                print(f"[RAG] 流式 AI 调用失败，回退到本地模板: {e}")
                fallback = self._generate_answer(question,
                    self._assemble_context(db_context, doc_context, lit_context), intent)
                for i in range(0, len(fallback), 10):
                    yield {"type": "token", "data": fallback[i:i+10]}
        else:
            answer = self._generate_answer(question,
                self._assemble_context(db_context, doc_context, lit_context), intent)
            for i in range(0, len(answer), 10):
                yield {"type": "token", "data": answer[i:i+10]}

        if chart_data:
            yield {"type": "chart_data", "data": chart_data}
        yield {"type": "sources", "data": sources}
        yield {"type": "done", "data": {}}

    # ====== 以下方法保持不变 ======

    def _classify_intent(self, question: str) -> str:
        """意图识别"""
        keywords_map = {
            "comparison": ["对比", "比较", "相比", "哪个更", "差异", "区别"],
            "statistics": ["统计", "多少", "数量", "总共", "平均", "最高", "最低", "排名"],
            "visualization": ["图表", "雷达图", "柱状图"],
            "score": ["得分", "评分", "指标", "效能", "评估"],
            "list": ["有哪些", "列出", "所有"],
        }
        for intent, keywords in keywords_map.items():
            if any(kw in question for kw in keywords):
                return intent
        return "factual"

    def _query_database(self, question: str, intent: str) -> str:
        """查询关系数据库"""
        from ..models.park import Park
        from ..models.score import Score
        from ..models.indicator import Indicator

        results = []

        parks = self.db.query(Park).all()
        mentioned_parks = [p for p in parks if (p.short_name and p.short_name in question) or p.name in question]

        if not mentioned_parks and any(kw in question for kw in ["哪些", "所有", "全部", "列出"]):
            mentioned_parks = parks

        for park in mentioned_parks[:5]:
            scores = (
                self.db.query(Score, Indicator)
                .join(Indicator, Score.indicator_id == Indicator.id)
                .filter(Score.park_id == park.id)
                .all()
            )

            results.append(f"\n【{park.name}】")
            results.append(f"  类型: {park.park_type}")
            results.append(f"  位置: {park.province} {park.city or ''}")
            results.append(f"  面积: {park.total_area if park.total_area else '未知'}平方公里")
            if park.aaa_level:
                results.append(f"  景区等级: {park.aaa_level}")

            if scores:
                results.append("  评估得分:")
                for sc, ind in scores:
                    results.append(f"    {ind.code} {ind.name}: {sc.normalized_score}分({sc.grade})")

        if not results:
            if intent == "list":
                results.append("已收录的国家考古遗址公园：")
                for p in parks:
                    results.append(f"  - {p.name}（{p.park_type}，{p.province}）")

        return "\n".join(results) if results else ""

    def _query_vector_store(self, question: str) -> str:
        """查询向量数据库"""
        if not self.chroma:
            return ""
        try:
            results = self.chroma.query(query_texts=[question], n_results=3)
            if results and results["documents"]:
                return "\n".join([f"相关文档: {doc[:300]}" for doc in results["documents"][0]])
        except Exception:
            pass
        return ""

    def _query_knowledge_base(self, question: str) -> str:
        """
        查询文献知识库
        判断用户问题是否涉及学术/遗产保护理论，若是则检索文献
        同时拉取每篇文献的引用和关联关系
        """
        # 判断是否需要检索文献知识库
        academic_keywords = [
            "理论", "研究", "文献", "论文", "学者", "学术",
            "保护", "遗产", "遗址", "考古", "文物", "文化",
            "方法", "综述", "进展", "趋势", "前沿", "历史",
            "什么是", "如何", "原因", "为什么", "有哪些",
            "定义", "概念", "观点", "认为", "提出",
        ]
        should_search_kb = any(kw in question for kw in academic_keywords)

        if not should_search_kb:
            return ""

        try:
            from .kb_indexer import semantic_search
            from ..models.literature import Literature, Citation, LitRelation

            results = semantic_search(question, limit=5, db_session=self.db)
            if not results:
                return ""

            parts = []
            for i, r in enumerate(results):
                lit_id = r.get("id")
                authors_str = ""
                if r.get("authors"):
                    authors_str = ", ".join([a.get("name", "") for a in r["authors"][:2]])
                kws = r.get("keywords", []) if r.get("keywords") else []
                kws_str = "、".join(kws[:5])

                parts.append(
                    f"[文献{i+1}] {r['title']} ({r.get('year', '')}) "
                    f"{authors_str}\n"
                    f"  关键词: {kws_str}\n"
                    f"  摘要: {r.get('abstract', '')[:200]}"
                )

                # 拉取该文献的引用和关联关系
                if lit_id:
                    # 引用的文献
                    citations = self.db.query(Citation).filter(
                        Citation.source_id == lit_id
                    ).limit(8).all()
                    if citations:
                        cite_strs = []
                        for c in citations:
                            cite_strs.append(f"{c.target_author or '?'} ({c.target_year or '?'}) {c.target_title[:40]}")
                        parts.append(f"  引用: {'; '.join(cite_strs)}")

                    # 被引用
                    cited_by = self.db.query(Citation).filter(
                        Citation.target_id == lit_id
                    ).limit(5).all()
                    if cited_by:
                        cb_strs = []
                        for c in cited_by:
                            src_title = c.source.title if c.source else "?"
                            cb_strs.append(f"{src_title[:40]} ({c.source.year if c.source else '?'})")
                        # 更新被引计数
                        try:
                            lit = self.db.query(Literature).filter(Literature.id == lit_id).first()
                            if lit:
                                lit.citation_count = len(cited_by)
                                self.db.commit()
                        except Exception:
                            pass
                        parts.append(f"  被引于: {'; '.join(cb_strs)}")

                    # 语义关系
                    relations = self.db.query(LitRelation).filter(
                        (LitRelation.source_id == lit_id) | (LitRelation.target_id == lit_id)
                    ).limit(8).all()
                    if relations:
                        rel_parts = []
                        for rel in relations:
                            other_id = rel.target_id if rel.source_id == lit_id else rel.source_id
                            other_lit = self.db.query(Literature).filter(Literature.id == other_id).first()
                            other_title = other_lit.title if other_lit else "未知文献"
                            rel_type = {"supports": "支持", "contradicts": "矛盾", "complements": "互补",
                                        "shares_topic": "同主题", "cites": "引用"}.get(rel.relation_type, rel.relation_type)
                            rel_parts.append(f"{rel_type}→{other_title[:30]}")
                        parts.append(f"  关系: {'; '.join(rel_parts)}")

                    # 共享关键词的关联文献
                    if kws:
                        from sqlalchemy import or_
                        conditions = [Literature.keywords.like(f"%{kw}%") for kw in kws[:3]]
                        related = self.db.query(Literature).filter(
                            Literature.id != lit_id,
                            or_(*conditions),
                        ).limit(5).all()
                        if related:
                            rel_strs = [f"{rl.title[:35]} ({rl.year})" for rl in related]
                            parts.append(f"  同主题文献: {'; '.join(rel_strs)}")

            return "\n\n".join(parts)
        except Exception as e:
            print(f"[RAG] 文献检索失败: {e}")
            return ""

    def _assemble_context(self, db_context: str, doc_context: str, lit_context: str = "") -> str:
        """组装上下文"""
        parts = []
        if db_context:
            parts.append(db_context)
        if doc_context:
            parts.append(doc_context)
        if lit_context:
            parts.append(f"【文献知识库】\n{lit_context}")
        return "\n\n".join(parts)

    def _generate_answer(self, question: str, context: str, intent: str) -> str:
        """生成回答（本地模板模式）"""
        from ..models.park import Park

        if not context:
            parks = self.db.query(Park).all()
            park_list = "、".join([p.short_name or p.name for p in parks[:9]])
            return f"抱歉，我暂时无法找到与您问题直接相关的数据。\n\n目前已收录的遗址公园有：{park_list}。\n\n您可以尝试询问这些公园的基本信息、评估得分等。"

        if intent == "list":
            return f"根据调研数据库，以下是相关信息：\n\n{context}"

        if intent == "comparison":
            return f"以下是对比分析结果：\n\n{context}\n\n> 提示：如需更详细的对比分析，请使用对比分析功能页面。"

        if intent == "score":
            return f"根据文化效能评估数据：\n\n{context}\n\n评分标准：好(≥80) / 较好(60-79) / 一般(40-59) / 较差(20-39) / 差(<20)"

        return f"根据调研数据，以下是相关信息：\n\n{context}\n\n> 提示：当前为本地演示模式，配置AI API密钥后可获得更智能的回答。"

    def _generate_chart_data(self, question: str, intent: str) -> Optional[Dict]:
        """生成图表数据"""
        from ..models.park import Park
        from ..models.score import Score
        from ..models.indicator import Indicator

        parks = self.db.query(Park).all()
        mentioned = [p for p in parks if (p.short_name and p.short_name in question)]

        if intent == "comparison" and len(mentioned) >= 2:
            chart = {"type": "radar", "data": []}
            for park in mentioned[:5]:
                scores = (
                    self.db.query(Indicator.dimension, Score.normalized_score)
                    .join(Score, Indicator.id == Score.indicator_id)
                    .filter(Score.park_id == park.id)
                    .all()
                )
                if scores:
                    dim_scores = {}
                    for dim, score in scores:
                        if dim not in dim_scores:
                            dim_scores[dim] = []
                        dim_scores[dim].append(score)
                    chart["data"].append({
                        "name": park.short_name or park.name,
                        "values": {dim: round(sum(v)/len(v)) for dim, v in dim_scores.items()},
                    })
            return chart if chart["data"] else None

        return None
