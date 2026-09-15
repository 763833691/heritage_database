from __future__ import annotations

import asyncio
import json
import math
import re
from hashlib import sha1
from typing import Any

ENTITY_TYPES = {"place", "person", "event", "concept"}

LEXICON: dict[str, str] = {
    "大明宫": "place",
    "长安": "place",
    "长安城": "place",
    "唐长安城": "place",
    "西安": "place",
    "含元殿": "place",
    "宣政殿": "place",
    "紫宸殿": "place",
    "丹凤门": "place",
    "太液池": "place",
    "兴庆宫": "place",
    "太极宫": "place",
    "西市": "place",
    "东市": "place",
    "西域": "place",
    "中亚": "place",
    "西亚": "place",
    "河西走廊": "place",
    "玉门关": "place",
    "唐太宗": "person",
    "唐高宗": "person",
    "武则天": "person",
    "唐玄宗": "person",
    "栗特人": "person",
    "商队": "person",
    "胡商": "person",
    "丝绸之路": "concept",
    "朝贡体系": "concept",
    "宫殿建筑": "concept",
    "里坊制度": "concept",
    "贸易": "concept",
    "文献": "concept",
    "遗址": "concept",
    "考古": "concept",
    "唐朝": "concept",
    "唐代": "concept",
    "严少飞": "person",
    "未央宫": "place",
    "汉未央宫遗址": "place",
    "唐大明宫遗址": "place",
    "大雁塔": "place",
    "小雁塔": "place",
    "兴教寺塔": "place",
    "龙首原": "place",
    "麟德殿": "place",
    "蓬莱殿": "place",
    "大福殿": "place",
    "三清殿": "place",
    "夹城": "place",
    "东内苑": "place",
    "西安": "place",
    "天山廊道": "place",
    "哈萨克斯坦": "place",
    "吉尔吉斯斯坦": "place",
    "世界遗产": "concept",
    "遗产点位": "concept",
    "古迹登录": "concept",
    "保护传承": "concept",
    "国家遗址公园": "place",
    "曲江": "place",
    "申遗": "event",
    "保护管理": "concept",
    "贸易交流": "event",
    "文化交流": "event",
    "考古发现": "event",
    "开元盛世": "event",
    "贞观之治": "event",
    "建造": "event",
    "扩建": "event",
}


def entity_id(name: str) -> str:
    return "entity_" + sha1(name.encode("utf-8")).hexdigest()[:12]


def normalize_type(value: str | None) -> str:
    if not value:
        return "concept"
    lowered = value.lower()
    aliases = {
        "地点": "place",
        "place": "place",
        "person": "person",
        "人物": "person",
        "event": "event",
        "事件": "event",
        "concept": "concept",
        "概念": "concept",
        "time": "concept",
        "时间": "concept",
        "机构": "concept",
        "文物": "concept",
    }
    return aliases.get(lowered, "concept")


def clean_text(text: str) -> list[str]:
    compact = re.sub(r"\s+", " ", text or "").strip()
    if not compact:
        return []
    chunks = re.split(r"[。！？!?；;\n]+", compact)
    return [chunk.strip(" ，,") for chunk in chunks if chunk.strip(" ，,")]


def count_mentions(text: str, name: str) -> tuple[int, int]:
    mention_count = text.count(name)
    sentences = clean_text(text)
    sentence_hits = sum(1 for sentence in sentences if name in sentence)
    return mention_count, sentence_hits


def compute_entity_confidence(
    text: str,
    name: str,
    *,
    source_kind: str,
) -> tuple[float, int, int]:
    mention_count, sentence_hits = count_mentions(text, name)
    total_sentences = max(len(clean_text(text)), 1)

    frequency_factor = min(1.0, 0.45 + 0.12 * math.log1p(mention_count))
    coverage_factor = min(1.0, sentence_hits / min(total_sentences, 30))

    base_by_kind = {
        "lexicon": 0.58,
        "quoted": 0.5,
        "relation_endpoint": 0.42,
    }
    base = base_by_kind.get(source_kind, 0.5)
    confidence = base + 0.22 * frequency_factor + 0.2 * coverage_factor
    if source_kind == "quoted" and mention_count <= 1:
        confidence -= 0.05
    if mention_count == 0:
        confidence = min(confidence, 0.55)

    return round(min(0.98, max(0.35, confidence)), 2), mention_count, sentence_hits


def compute_relation_weight(
    *,
    relation: str,
    evidence_sentences: int,
    explicit_rule: bool,
) -> float:
    if explicit_rule:
        weight = 0.68 + min(0.28, 0.07 * evidence_sentences)
    elif relation == "相关":
        weight = 0.42 + min(0.28, 0.05 * evidence_sentences)
    else:
        weight = 0.55 + min(0.3, 0.06 * evidence_sentences)
    return round(min(0.98, max(0.35, weight)), 2)


def extract_entities(text: str, source_file: str | None = None) -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for name, kind in sorted(LEXICON.items(), key=lambda item: len(item[0]), reverse=True):
        if name in text:
            confidence, mention_count, sentence_hits = compute_entity_confidence(
                text, name, source_kind="lexicon"
            )
            found[name] = {
                "id": entity_id(name),
                "name": name,
                "type": normalize_type(kind),
                "description": (
                    f"{name}在原文中出现 {mention_count} 次，分布于 {sentence_hits} 个句段。"
                ),
                "source_file": source_file,
                "confidence": confidence,
                "mention_count": mention_count,
            }
    quoted = re.findall(r"《([^》]{2,30})》", text)
    for title in quoted:
        if title in found:
            continue
        confidence, mention_count, sentence_hits = compute_entity_confidence(
            text, title, source_kind="quoted"
        )
        found[title] = {
            "id": entity_id(title),
            "name": title,
            "type": "concept",
            "description": f"文献《{title}》在原文出现 {mention_count} 次，分布于 {sentence_hits} 个句段。",
            "source_file": source_file,
            "confidence": confidence,
            "mention_count": mention_count,
        }
    return list(found.values())


def _co_occurs(sentence: str, left: str, right: str) -> bool:
    return left in sentence and right in sentence and left != right


def extract_relations(text: str, entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sentences = clean_text(text)
    names = [entity["name"] for entity in entities]
    relations: dict[tuple[str, str, str], dict[str, Any]] = {}

    def add(
        source: str,
        relation: str,
        target: str,
        *,
        explicit_rule: bool = False,
        evidence: int = 1,
    ) -> None:
        if source == target:
            return
        if source not in names:
            names.append(source)
        if target not in names:
            names.append(target)
        key = (source, relation, target)
        existing = relations.get(key)
        total_evidence = (existing or {}).get("evidence_sentences", 0) + evidence
        explicit = explicit_rule or (existing or {}).get("explicit_rule", False)
        relations[key] = {
            "source": source,
            "relation": relation,
            "target": target,
            "evidence_sentences": total_evidence,
            "explicit_rule": explicit,
            "weight": compute_relation_weight(
                relation=relation,
                evidence_sentences=total_evidence,
                explicit_rule=explicit,
            ),
        }

    for sentence in sentences:
        if _co_occurs(sentence, "大明宫", "长安城") or _co_occurs(sentence, "大明宫", "长安"):
            add("大明宫", "位于", "长安城" if "长安城" in sentence else "长安", explicit_rule=True)
        if "丝绸之路" in sentence and ("起点" in sentence or "东方起点" in sentence):
            target = "长安城" if "长安城" in sentence else "长安"
            add("丝绸之路", "起点", target, explicit_rule=True)
        if "唐朝" in sentence and "大明宫" in sentence:
            add("唐朝", "建造", "大明宫", explicit_rule=True)
        if "唐代" in sentence and "大明宫" in sentence:
            add("大明宫", "属于", "唐代", explicit_rule=True)
        if "唐高宗" in sentence and "大明宫" in sentence:
            add("唐高宗", "扩建", "大明宫", explicit_rule=True)
        if "武则天" in sentence and "大明宫" in sentence:
            add("武则天", "活动于", "大明宫", explicit_rule=True)
        if "唐玄宗" in sentence and "大明宫" in sentence:
            add("唐玄宗", "活动于", "大明宫", explicit_rule=True)
        for palace in ["含元殿", "宣政殿", "紫宸殿", "丹凤门", "太液池"]:
            if palace in sentence and "大明宫" in sentence:
                add("大明宫", "包含", palace, explicit_rule=True)
        for region in ["西域", "中亚", "西亚", "河西走廊"]:
            if region in sentence and "丝绸之路" in sentence:
                add("丝绸之路", "连接", region, explicit_rule=True)
        if "贸易" in sentence and "丝绸之路" in sentence:
            add("丝绸之路", "促进", "贸易交流", explicit_rule=True)
        if "考古" in sentence and "遗址" in sentence:
            add("考古发现", "揭示", "遗址", explicit_rule=True)
        if "大明宫" in sentence and "丝绸之路" in sentence:
            add("大明宫", "属于", "丝绸之路", explicit_rule=True)
        if "未央宫" in sentence and "丝绸之路" in sentence:
            add("未央宫", "属于", "丝绸之路", explicit_rule=True)
        if "大雁塔" in sentence and "丝绸之路" in sentence:
            add("大雁塔", "属于", "丝绸之路", explicit_rule=True)
        if "小雁塔" in sentence and "丝绸之路" in sentence:
            add("小雁塔", "属于", "丝绸之路", explicit_rule=True)
        if "兴教寺塔" in sentence and "丝绸之路" in sentence:
            add("兴教寺塔", "属于", "丝绸之路", explicit_rule=True)
        if "严少飞" in sentence and ("遗产" in sentence or "保护" in sentence):
            add("严少飞", "研究", "遗产点位", explicit_rule=True)
        if "世界遗产" in sentence and "西安" in sentence:
            add("世界遗产", "包含", "西安", explicit_rule=True)
        if "龙首原" in sentence and "大明宫" in sentence:
            add("大明宫", "位于", "龙首原", explicit_rule=True)
        if "麟德殿" in sentence and "大明宫" in sentence:
            add("大明宫", "包含", "麟德殿", explicit_rule=True)
        if "国家遗址公园" in sentence and "大明宫" in sentence:
            add("国家遗址公园", "保护", "大明宫", explicit_rule=True)

        present = [name for name in names if name in sentence]
        for index, source in enumerate(present[:6]):
            for target in present[index + 1 : 6]:
                add(source, "相关", target)

    if not relations and len(names) >= 2:
        for source, target in zip(names, names[1:]):
            add(source, "相关", target)

    return [
        {
            "source": relation["source"],
            "relation": relation["relation"],
            "target": relation["target"],
            "weight": relation["weight"],
        }
        for relation in relations.values()
    ]


def build_graph(entities: list[dict[str, Any]], relations: list[dict[str, Any]], text: str = "") -> dict[str, Any]:
    entity_by_name = {entity["name"]: entity for entity in entities}
    for relation in relations:
        for endpoint in [relation["source"], relation["target"]]:
            if endpoint in entity_by_name:
                continue
            confidence, mention_count, sentence_hits = compute_entity_confidence(
                text, endpoint, source_kind="relation_endpoint"
            )
            entity_by_name[endpoint] = {
                "id": entity_id(endpoint),
                "name": endpoint,
                "type": "concept",
                "description": f"{endpoint}由关系端点补全，原文出现 {mention_count} 次。",
                "source_file": None,
                "confidence": confidence,
                "mention_count": mention_count,
            }
    nodes = [
        {
            "data": {
                "id": entity["id"],
                "label": entity["name"],
                "name": entity["name"],
                "type": entity["type"],
                "description": entity.get("description", ""),
                "source_file": entity.get("source_file"),
            }
        }
        for entity in entity_by_name.values()
    ]
    name_to_id = {entity["name"]: entity["id"] for entity in entity_by_name.values()}
    edges = [
        {
            "data": {
                "id": f"rel_{name_to_id[relation['source']]}_{name_to_id[relation['target']]}_{relation['relation']}",
                "source": name_to_id[relation["source"]],
                "target": name_to_id[relation["target"]],
                "label": relation["relation"],
                "relation": relation["relation"],
                "weight": relation.get("weight", 0.85),
            }
        }
        for relation in relations
    ]
    return {"nodes": nodes, "edges": edges}


def _strip_json_fence(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip() or "{}"


async def _llm_extract(text: str, source_file: str | None = None) -> dict[str, Any] | None:
    from app.core.config import settings

    api_key = settings.openai_api_key
    if not api_key:
        return None
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key, base_url=settings.openai_base_url)
        prompt = (
            "从以下历史文本中抽取实体和关系，实体类型只能是 place/person/event/concept。"
            "返回 JSON，格式为 {\"entities\":[{\"id\":\"\",\"name\":\"\",\"type\":\"place|person|event|concept\"}],"
            "\"relations\":[{\"source\":\"\",\"relation\":\"\",\"target\":\"\",\"weight\":0.85}]}。"
            f"\n文本：{text[:6000]}"
        )
        try:
            response = await client.chat.completions.create(
                model=settings.openai_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                response_format={"type": "json_object"},
            )
        except Exception:
            response = await client.chat.completions.create(
                model=settings.openai_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
        content = response.choices[0].message.content or "{}"
        payload = json.loads(_strip_json_fence(content))
        entities = []
        for item in payload.get("entities", []):
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            entities.append(
                {
                    "id": item.get("id") or entity_id(name),
                    "name": name,
                    "type": normalize_type(item.get("type")),
                    "description": item.get("description") or f"{name}由 LLM 抽取识别。",
                    "source_file": source_file,
                    "confidence": float(item.get("confidence", 0.9)),
                }
            )
        relations = []
        for item in payload.get("relations", []):
            source = str(item.get("source", "")).strip()
            target = str(item.get("target", "")).strip()
            relation = str(item.get("relation", "相关")).strip() or "相关"
            if source and target:
                relations.append(
                    {
                        "source": source,
                        "relation": relation,
                        "target": target,
                        "weight": float(item.get("weight", item.get("confidence", 0.85))),
                    }
                )
        if not entities:
            return None
        graph = build_graph(entities, relations, text)
        return {"entities": entities, "relations": relations, "graph": graph}
    except Exception:
        return None


async def process_text(text: str, source_file: str | None = None) -> dict[str, Any]:
    llm_payload = await _llm_extract(text, source_file=source_file)
    if llm_payload:
        return llm_payload
    cleaned = "。".join(clean_text(text))
    entities = extract_entities(cleaned, source_file=source_file)
    relations = extract_relations(cleaned, entities)
    graph = build_graph(entities, relations, cleaned)
    return {"entities": entities, "relations": relations, "graph": graph}


def process_text_sync(text: str, source_file: str | None = None) -> dict[str, Any]:
    return asyncio.run(process_text(text, source_file=source_file))
