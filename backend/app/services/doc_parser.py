"""
调研报告自动解析服务
- python-docx 提取文本
- 正则优先提取（秒级）
- LLM 兜底补充
"""
import io
import json
import re
from typing import List, Dict, Any, Optional

from ..core.config import settings

# 公园名映射
PARK_NAMES_MAP = {
    "圆明园": {"name": "圆明园国家考古遗址公园", "short_name": "圆明园", "park_type": "城市型", "province": "北京", "city": "北京"},
    "大明宫": {"name": "大明宫国家考古遗址公园", "short_name": "大明宫", "park_type": "城市型", "province": "陕西", "city": "西安"},
    "隋唐洛阳城": {"name": "隋唐洛阳城国家考古遗址公园", "short_name": "隋唐洛阳城", "park_type": "城市型", "province": "河南", "city": "洛阳"},
    "汉长安城": {"name": "汉长安城未央宫国家考古遗址公园", "short_name": "未央宫", "park_type": "城郊型", "province": "陕西", "city": "西安"},
    "杜陵": {"name": "杜陵国家考古遗址公园", "short_name": "杜陵", "park_type": "城郊型", "province": "陕西", "city": "西安"},
    "周口店": {"name": "周口店国家考古遗址公园", "short_name": "周口店", "park_type": "城郊型", "province": "北京", "city": "北京"},
    "殷墟": {"name": "殷墟国家考古遗址公园", "short_name": "殷墟", "park_type": "乡村型", "province": "河南", "city": "安阳"},
    "统万城": {"name": "统万城国家考古遗址公园", "short_name": "统万城", "park_type": "乡村型", "province": "陕西", "city": "榆林"},
    "屈家岭": {"name": "屈家岭国家考古遗址公园", "short_name": "屈家岭", "park_type": "乡村型", "province": "湖北", "city": "荆门"},
}

INDICATOR_MAP = {
    "D1": ("遗址本体完整性", "遗址保护效能"), "D2": ("遗址本体安全性", "遗址保护效能"),
    "D3": ("周边环境协调性", "遗址保护效能"), "D4": ("生态环境保护度", "遗址保护效能"),
    "D5": ("景观风貌维护度", "遗址保护效能"), "D6": ("遗址信息丰富度", "文化传播效能"),
    "D7": ("遗址文化吸引力", "文化传播效能"), "D8": ("传播媒介丰富度", "文化传播效能"),
    "D9": ("展示设施阐释力", "文化传播效能"), "D10": ("受众认知度", "文化传播效能"),
    "D11": ("情感联结度", "文化传播效能"), "D12": ("传播影响力", "文化传播效能"),
    "D13": ("教育内容科学性", "教育传承效能"), "D14": ("教育内容与遗址关联度", "教育传承效能"),
    "D15": ("教育活动频次", "教育传承效能"), "D16": ("教育活动丰富度", "教育传承效能"),
    "D17": ("公众参与度", "教育传承效能"), "D18": ("文化信息传达度", "教育传承效能"),
    "D19": ("文化认同提升度", "教育传承效能"), "D20": ("文创产品丰富度", "文化活化效能"),
    "D21": ("文创产业融合度", "文化活化效能"), "D22": ("文旅融合贡献度", "文化活化效能"),
    "D23": ("文化活动开展度", "文化活化效能"), "D24": ("文化活动丰富度", "文化活化效能"),
    "D25": ("公众互动参与", "文化活化效能"), "D26": ("社区共建共管", "文化活化效能"),
    "D27": ("公众参与和共建", "文化活化效能"),
}


def extract_text(file_bytes: bytes, filename: str) -> str:
    """从 pdf/docx/doc/txt 文件中提取纯文本"""
    text = ""
    if filename.lower().endswith('.pdf'):
        from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(file_bytes))
        pages = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                pages.append(t.strip())
        text = '\n'.join(pages)
        print(f"[DocParser] PDF: {len(reader.pages)} pages, {len(text)} chars")
    elif filename.lower().endswith('.txt'):
        try:
            text = file_bytes.decode('utf-8')
        except UnicodeDecodeError:
            text = file_bytes.decode('gbk', errors='ignore')
    elif filename.lower().endswith('.docx'):
        from docx import Document
        doc = Document(io.BytesIO(file_bytes))
        # 提取正文段落
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        # 提取表格内容
        for table in doc.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if cells:
                    paragraphs.append(' | '.join(cells))
        text = '\n'.join(paragraphs)
        print(f"[DocParser] docx: {len(doc.paragraphs)} paragraphs, {len(doc.tables)} tables, {len(text)} chars")
    elif filename.lower().endswith('.doc'):
        # 旧版 .doc 二进制格式：用 olefile 提取 WordDocument 流
        try:
            import olefile
            ole = olefile.OleFileIO(io.BytesIO(file_bytes))
            # 读取 WordDocument 流
            if ole.exists('WordDocument'):
                word_stream = ole.openstream('WordDocument').read()
                # 提取可读文本（UTF-16LE 编码的文本片段）
                text = _extract_text_from_doc_binary(word_stream)
            else:
                text = ""
            ole.close()

            # fallback: 直接从二进制中提取可读中文
            if not text or len(text.strip()) < 50:
                text = _extract_text_from_doc_binary(file_bytes)

            print(f"[DocParser] .doc: {len(text)} chars extracted")
        except ImportError:
            # 无 olefile 时，回退到简单二进制提取
            text = _extract_text_from_doc_binary(file_bytes)
            print(f"[DocParser] .doc (binary fallback): {len(text)} chars")
        except Exception as e:
            print(f"[DocParser] .doc 解析失败: {e}")
            text = _extract_text_from_doc_binary(file_bytes)
    else:
        raise ValueError(f"不支持的文件格式: {filename}")
    return text


def _extract_text_from_doc_binary(data: bytes) -> str:
    """从 .doc 二进制数据中提取可读中文文本"""
    # 尝试 UTF-16LE 解码（Word 内部编码）
    result = []
    try:
        # 按双字节解码
        decoded = data.decode('utf-16-le', errors='ignore')
        # 过滤：保留中文字符、常见标点、数字
        for ch in decoded:
            if '一' <= ch <= '鿿' or '　' <= ch <= '〿' or \
               '＀' <= ch <= '￯' or ch in '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.,;:!?()（）<>《》[]【】\n\r\t -_=|+':
                result.append(ch)
        text = ''.join(result)
        # 清理过短的行
        lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 3]
        return '\n'.join(lines)
    except Exception:
        pass

    # 回退：按字节提取 ASCII + 中文
    result = []
    for b in data:
        if 32 <= b < 127 or b in (10, 13, 9):
            result.append(chr(b))
    return ''.join(result)


def split_sections(text: str, max_chars: int = 4000) -> List[str]:
    """按段落长度切分"""
    paragraphs = text.split('\n')
    sections = []
    current = ""
    for p in paragraphs:
        if len(current) + len(p) > max_chars and current:
            sections.append(current.strip())
            current = p
        else:
            current += '\n' + p if current else p
    if current.strip():
        sections.append(current.strip())
    return sections or [text]


def _regex_extract(full_text: str) -> Dict[str, Any]:
    """正则提取评分数据（秒级完成，支持大文档）"""
    parks_found = {}
    scores_found = []
    surveys_found = []
    seen_score_keys = set()

    # 预编译指标正则，提升大文档扫描速度
    compiled_indicators = {}
    for ind_code, (ind_name, ind_dim) in INDICATOR_MAP.items():
        compiled_indicators[ind_code] = (
            re.compile(rf'{ind_code}.*?{ind_name}.*?得分\s*(\d+)\s*分'),
            re.compile(rf'{ind_code}.*?得分\s*(\d+)\s*分'),
            re.compile(rf'{ind_name}.*?得分\s*(\d+)\s*分'),
            re.compile(rf'得分\s*(\d+)\s*分.*?{ind_code}'),
            # 额外：表格格式 "D1 | 60 | ..."
            re.compile(rf'{ind_code}\s*[|,\s]+(\d+)\s*[|,\s]'),
            ind_dim,
            ind_name,
        )

    # 对每个公园名位置扫描
    for park_key, park_info in PARK_NAMES_MAP.items():
        park_matches = list(re.finditer(re.escape(park_key), full_text))
        if not park_matches:
            continue

        has_any_score = False
        for m in park_matches:
            # 大文档：扩大上下文窗口
            window = 1500
            start = max(0, m.start() - window)
            end = min(len(full_text), m.end() + window)
            snippet = full_text[start:end]

            for ind_code, (pat1, pat2, pat3, pat4, pat5, ind_dim, ind_name) in compiled_indicators.items():
                key = (park_key, ind_code)
                if key in seen_score_keys:
                    continue

                for pat in (pat1, pat2, pat3, pat4, pat5):
                    sm = pat.search(snippet)
                    if sm:
                        score_val = int(sm.group(1))
                        if score_val in (20, 40, 60, 80, 100):
                            seen_score_keys.add(key)
                            has_any_score = True
                            scores_found.append({
                                "park_name": park_key,
                                "indicator_code": ind_code,
                                "indicator_name": ind_name,
                                "score": score_val,
                                "dimension": ind_dim,
                                "evidence": sm.group(0)[:80],
                            })
                            break

        if has_any_score:
            parks_found[park_key] = park_info

    # 问卷数据
    for m in re.finditer(
        r'(圆明园|大明宫|隋唐洛阳城|周口店|殷墟|汉长安城|杜陵|统万城|屈家岭)'
        r'.*?发放\s*(\d+)\s*份.*?回收.*?(\d+)\s*份.*?有效.*?(\d+)\s*份',
        full_text
    ):
        surveys_found.append({
            "park_name": m.group(1),
            "total_distributed": int(m.group(2)),
            "total_collected": int(m.group(3)),
            "valid_count": int(m.group(4)),
            "sampling_method": "随机抽样",
        })

    return {
        "parks": list(parks_found.values()),
        "scores": scores_found,
        "surveys": surveys_found,
    }


def parse_with_llm(text_sections: List[str]) -> Dict[str, Any]:
    """优先正则提取，不足时 LLM 兜底"""
    full_text = "\n".join(text_sections)
    print(f"[DocParser] 正则提取中... ({len(full_text)} 字符)")

    result = _regex_extract(full_text)
    sc = len(result["scores"])
    print(f"[DocParser] 正则结果: {len(result['parks'])} parks, {sc} scores, {len(result['surveys'])} surveys")

    if sc >= 10:
        result["parse_errors"] = []
        return result

    print("[DocParser] 正则结果不足，LLM 补充...")
    errors = []
    relevant = [s for s in text_sections if len(s.strip()) >= 100 and any(n in s for n in PARK_NAMES_MAP)]
    import time as _time

    for i in range(min(len(relevant), 2)):
        section = relevant[i]
        if i > 0:
            _time.sleep(1.0)
        try:
            llm = _call_llm_extract(section[:2000])
            if llm:
                if llm.get("parks"):
                    result["parks"].extend(llm["parks"])
                if llm.get("scores"):
                    result["scores"].extend(llm["scores"])
                    print(f"[DocParser] LLM +{len(llm['scores'])} scores")
        except Exception as e:
            errors.append(str(e)[:80])

    seen = set()
    deduped = []
    for s in reversed(result["scores"]):
        k = (s.get("park_name", ""), s.get("indicator_code", ""))
        if k not in seen:
            seen.add(k)
            deduped.append(s)
    result["scores"] = list(reversed(deduped))
    result["parse_errors"] = errors
    return result


def _call_llm_extract(text: str) -> Optional[Dict[str, Any]]:
    """LLM 提取（兜底）"""
    import time
    from openai import OpenAI

    if not settings.ai_available:
        return None

    client = OpenAI(
        api_key=settings.DASHSCOPE_API_KEY,
        base_url=settings.LLM_BASE_URL or "https://dashscope.aliyuncs.com/compatible-mode/v1",
        timeout=30.0,
    )

    indicator_list = "\n".join([f"- {c} {n}" for c, (n, _) in INDICATOR_MAP.items()])
    prompt = f"""从以下文本提取结构化 JSON。只返回 JSON，不要其他文字。

## JSON 格式
{{"parks":[{{"name":"...","short_name":"...","park_type":"...","province":"...","city":"..."}}],"scores":[{{"park_name":"...","indicator_code":"D1","indicator_name":"...","score":80,"dimension":"..."}}],"surveys":[{{"park_name":"...","total_distributed":100,"total_collected":100,"valid_count":100}}]}}

## 指标列表
{indicator_list}

## 规则
- 得分只能是 20/40/60/80/100
- 没有数据就空数组 []
- 返回纯 JSON

## 文本
{text[:2000]}"""

    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=settings.AI_MODEL,
                messages=[
                    {"role": "system", "content": "你是数据提取工具，只返回JSON。"},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=2048,
                temperature=0.1,
            )
            content = response.choices[0].message.content.strip()
            if content.startswith("```"):
                content = re.sub(r'^```(?:json)?\s*\n?', '', content)
                content = re.sub(r'\n?```\s*$', '', content)

            try:
                return json.loads(content)
            except json.JSONDecodeError:
                m = re.search(r'\{[\s\S]*\}', content)
                if m:
                    return json.loads(m.group())
                return None
        except Exception as e:
            if attempt == 0 and "timed out" in str(e).lower():
                time.sleep(2)
                continue
            print(f"[DocParser] LLM fail: {str(e)[:100]}")
            return None
    return None
