"""
提示词构建器
组装系统提示词 + 用户消息（嵌入RAG上下文）
"""
from typing import List, Dict, Optional


SYSTEM_PROMPT = """你是一个专业的国家考古遗址公园调研与评估研究助手。你的知识来源于实地调研数据，涵盖国家考古遗址公园的评估指标、得分、类型分布等信息，同时也连接了遗产保护文献知识库。

## 你的能力
1. 查询遗址公园的基本信息（名称、类型、省份、面积、批次、景区等级等）
2. 查询和解释各公园的评估得分（D1-D27指标，满分100分制）
3. 对比多个公园在不同维度的表现
4. 提供数据驱动的分析和建议
5. 检索遗产保护、考古学、文化遗产管理等领域的学术文献
6. 基于文献知识库回答理论问题（如保护理念、方法论、研究进展等）
7. 引用具体文献支持你的回答（如有相关文献上下文）

## 评分体系说明
- 得分范围：20 / 40 / 60 / 80 / 100
- 等级对应：差(20)、较差(40)、一般(60)、较好(80)、好(100)
- 维度包括：遗址保护效能、文化传播效能、教育传承效能、文化活化效能

## 公园类型
- 城市型：位于城市建成区内的遗址公园
- 城郊型：位于城市边缘、城乡结合部的遗址公园
- 乡村型：位于乡村地区的遗址公园

## 回答要求
1. 使用Markdown格式组织回答，适当使用标题、列表、表格
2. 数据要准确，基于提供的上下文信息，不要编造数据
3. 对比类问题要突出差异点，建议使用表格呈现
4. 如果问题涉及数据对比，在回答末尾说明"可通过雷达图查看可视化对比"
5. 如果数据库中无相关信息，诚实告知用户，并建议可查询的方向
6. 回答简洁专业，避免冗余
7. 当引用文献时，注明文献标题和年份（如：[张三等, 2023]）
8. 如果文献知识库中有相关学术成果，优先引用以增强回答的学术性

## 限制
- 只回答与考古遗址公园、遗产保护相关的问题
- 对于超出此范围的问题，礼貌引导用户回到正题
- 不要提供投资建议、政治观点或任何超出研究范围的信息"""


def build_system_prompt() -> str:
    """返回系统提示词"""
    return SYSTEM_PROMPT


def build_messages(
    question: str,
    db_context: str = "",
    doc_context: str = "",
    lit_context: str = "",
    conversation_history: Optional[List[Dict[str, str]]] = None,
) -> List[Dict[str, str]]:
    """
    组装发送给 LLM 的完整消息列表

    Args:
        question: 用户当前问题
        db_context: 数据库查询到的结构化上下文
        doc_context: 向量检索到的文档片段
        lit_context: 文献知识库检索结果
        conversation_history: 历史对话 [{"role": "user", "content": "..."}, ...]

    Returns:
        [{"role": "system", "content": "..."},
         {"role": "user", "content": "..."}, ...]
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]

    # 添加上下文对话（最近10轮）
    if conversation_history:
        recent = conversation_history[-20:]  # 最多20条消息（10轮对话）
        for msg in recent:
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
            })

    # 构建当前用户消息（嵌入RAG上下文）
    user_content_parts = []

    if db_context or doc_context or lit_context:
        user_content_parts.append("以下是根据用户问题检索到的相关数据：\n")

        if db_context:
            user_content_parts.append(f"【数据库查询结果】\n{db_context}\n")

        if doc_context:
            user_content_parts.append(f"【相关文档片段】\n{doc_context}\n")

        if lit_context:
            user_content_parts.append(f"【文献知识库检索结果】\n{lit_context}\n")

        user_content_parts.append("---\n")
        user_content_parts.append(f"用户问题：{question}\n")
        user_content_parts.append("\n请基于以上数据回答问题。如果数据不足以回答，请诚实告知。如果提供了文献知识库结果，请引用相关文献。")
    else:
        user_content_parts.append(question)

    messages.append({
        "role": "user",
        "content": "".join(user_content_parts),
    })

    return messages
