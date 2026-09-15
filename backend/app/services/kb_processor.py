"""
知识库处理器：LLM 驱动的文献结构化提取 + 关系发现
"""
import json
import re
import time
from typing import Dict, Any, List, Optional

from ..core.config import settings


EXTRACTION_PROMPT = """你是文化遗产文献分析助手。请从以下文献中提取结构化信息。特别注意提取所有参考文献。

返回 JSON：
{
  "title": "完整标题",
  "authors": [{"name": "作者名", "institution": "机构名"}],
  "year": 年份数字,
  "journal": "期刊/出版社",
  "keywords": ["关键词1", "关键词2"],
  "abstract": "200字摘要",
  "doc_type": "期刊论文|学位论文|会议论文|政策报告|著作|其他",
  "funding": "基金信息，没有则为空字符串",
  "methodology": "研究方法简述",
  "core_argument": "一句话核心论点",
  "references": [
    {"author": "作者", "title": "标题", "year": 年份}
  ],
  "parks_mentioned": ["提到的遗址公园名"],
  "concepts_mentioned": ["提到的学术概念"]
}

## 规则
- 只提取文中明确出现的信息，不要编造
- 关键词 3-8 个
- references 只提取文末参考文献列表中的条目
- 返回纯 JSON，不要有其他文字

## 文献文本
"""

RELATION_PROMPT = """新文献已入库。请分析它和以下已有文献的关系。

新文献：{new_title}（{new_year}）
摘要：{new_abstract}

已有文献：
{existing_list}

对每篇已有文献，判断关系类型并解释：
- cites: 新文献引用了已有文献
- shares_topic: 共享研究主题
- supports: 新文献支持已有文献的观点
- contradicts: 新文献与已有文献观点矛盾
- complements: 互补关系
- none: 无明显关系

返回 JSON：
{{"relations": [{{"target_title": "...", "type": "...", "explanation": "..."}}]}}"""


def _call_llm(prompt: str, max_tokens: int = 4096) -> Optional[str]:
    """调用 LLM，返回文本"""
    if not settings.ai_available:
        return None

    from openai import OpenAI
    client = OpenAI(
        api_key=settings.DASHSCOPE_API_KEY,
        base_url=settings.LLM_BASE_URL or "https://dashscope.aliyuncs.com/compatible-mode/v1",
        timeout=60.0,
    )

    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=settings.AI_MODEL,
                messages=[
                    {"role": "system", "content": "你是文化遗产研究的数据提取工具，只返回JSON。"},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                temperature=0.1,
            )
            return response.choices[0].message.content
        except Exception as e:
            if attempt == 0 and "timed out" in str(e).lower():
                time.sleep(2)
                continue
            print(f"[KB] LLM call failed: {str(e)[:100]}")
            return None
    return None


def _parse_json_response(content: str) -> Optional[Dict]:
    """从 LLM 回复中解析 JSON"""
    if not content:
        return None
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r'^```(?:json)?\s*\n?', '', content)
        content = re.sub(r'\n?```\s*$', '', content)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        m = re.search(r'\{[\s\S]*\}', content)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
        print(f"[KB] JSON parse failed: {content[:200]}")
        return None


def extract_metadata(text: str) -> Dict[str, Any]:
    """从文献文本中提取结构化元数据"""
    if not settings.ai_available:
        return _fallback_extract(text)

    prompt = EXTRACTION_PROMPT + text[:6000]
    content = _call_llm(prompt, max_tokens=4096)
    result = _parse_json_response(content)

    if not result:
        return _fallback_extract(text)

    return {
        "title": result.get("title", ""),
        "authors": result.get("authors", []),
        "year": result.get("year", 2024),
        "journal": result.get("journal", ""),
        "keywords": result.get("keywords", []),
        "abstract": result.get("abstract", ""),
        "doc_type": result.get("doc_type", "其他"),
        "funding": result.get("funding", ""),
        "methodology": result.get("methodology", ""),
        "core_argument": result.get("core_argument", ""),
        "references": result.get("references", []),
        "parks_mentioned": result.get("parks_mentioned", []),
        "concepts_mentioned": result.get("concepts_mentioned", []),
    }


def discover_relations(new_lit: Dict, existing_lits: List[Dict]) -> List[Dict]:
    """发现新文献与已有文献的关系"""
    if not existing_lits or not settings.ai_available:
        return []

    existing_str = "\n".join([
        f"- [{e.get('year','?')}] {e.get('title','')} (摘要: {e.get('abstract','')[:120]})"
        for e in existing_lits[:15]
    ])

    prompt = RELATION_PROMPT.format(
        new_title=new_lit.get("title", ""),
        new_year=new_lit.get("year", ""),
        new_abstract=new_lit.get("abstract", "")[:300],
        existing_list=existing_str,
    )

    content = _call_llm(prompt, max_tokens=2048)
    result = _parse_json_response(content)
    return result.get("relations", []) if result else []


def _fallback_extract(text: str) -> Dict[str, Any]:
    """无 LLM 时的基本提取"""
    title_match = re.search(r'^(.+?)[\n\r]', text)
    return {
        "title": title_match.group(1)[:200] if title_match else "未命名文献",
        "authors": [],
        "year": 2024,
        "journal": "",
        "keywords": [],
        "abstract": text[:500],
        "doc_type": "其他",
        "funding": "",
        "methodology": "",
        "core_argument": "",
        "references": [],
        "parks_mentioned": [],
        "concepts_mentioned": [],
    }
