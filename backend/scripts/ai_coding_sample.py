"""智能体独立编码：对双标抽样的 142 张盲标照片按《语义编码手册 v1.0》进行 A–G 分类。

- 使用项目配置的 doubao 视觉模型（vision_client 同一通道）；
- 每张照片独立编码 3 次（重复性检验，对齐刘颂等信度规格）；
- 输出 Excel：每次编码结果 + 多数表决终判 + 理由 + 自一致性。
"""
from __future__ import annotations

import concurrent.futures as cf
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.vision_client import describe_image  # noqa: E402

SAMPLE_DIR = Path(r"E:\BaiduSyncdisk\研究生参与项目资料\国家考古遗址公园高质量调研\论文\空间图谱论文\双标抽样\照片_盲标")
OUT_XLSX = Path(r"E:\BaiduSyncdisk\研究生参与项目资料\国家考古遗址公园高质量调研\论文\空间图谱论文\双标抽样\智能体编码结果_v2.xlsx")

SYSTEM_PROMPT = "你是文化遗产展示研究的专业编码员，严格按编码手册对照片分类，只输出规定格式，不输出任何多余内容。"

CODE_PROMPT_V11 = """请按照《遗址阐释与展示照片语义编码手册 v1.1》对这张照片进行分类。

【类目定义】
A 遗址本体展示：遗址原生遗存本体及直接保护设施。如夯土、墩台、柱础、基址、封土、城墙遗址、遗址剖面、出土遗物、保护栈道围栏。**出土遗物（陶片、器物等）无论在遗址原位还是博物馆展柜中，一律归A**。
B 复原建筑与覆罩：覆罩保护建筑与形象复原建筑。如保护棚、保护罩、城楼、阙楼、仿古复原建筑。**仅当复原建筑为画面主体且可辨识复原性质时归B；仅作为远景或环境风貌出现时归F**。
C 阐释解说设施：以图文媒介为主体的阐释设施。如图文展板、说明牌、介绍牌、沙盘模型、壁画浮雕、展厅展陈（不含出土实物）、导览标识。
D 数字互动展示：数字技术媒介的互动沉浸展示。如互动触摸屏、电子展示屏、VR/AR、全息、数字展厅。
E 运营与消费场景：运营商业与服务设施。如售票处、文创商店、售卖机、演艺舞台、游客中心、餐饮。
F 景观环境与城市关系：景观空间与环境风貌。如天街、广场、绿地、湿地、水面、步道、停车场、远眺城市天际线、遗址区大环境。
G 其他：**以下情形必须归G**——监控立杆、消防安防标识、禁止类告示、环卫设施等管理设施；施工或考古发掘作业现场；照片过暗模糊无法辨认；确实无法归入A–F的情形。**允许且鼓励使用G，不要强行归类**。

【编码规则】
1. 每张照片只选一个类目，按照片主体内容及其在遗址阐释系统中的功能判定；
2. 多类元素共存时以拍摄主体为准；
3. 按功能而非字面特征归类（如印文物图案的售卖机仍是E）；
4. A/C边界看信息载体：实物遗存归A，图文媒介归C，与摆放在哪里无关。

【输出格式】只输出一行：编码字母|一句话理由
示例：C|照片主体为介绍遗址布局的图文展板"""

LETTER_RE = re.compile(r"^\s*([A-G])\s*[|｜]")


def code_one(path: Path) -> tuple[str, str]:
    """返回 (编码字母, 理由)。失败返回 ('', 错误信息)。"""
    try:
        text = describe_image(path.read_bytes(), CODE_PROMPT_V11, timeout=90, system_prompt=SYSTEM_PROMPT)
    except Exception as exc:  # noqa: BLE001
        return "", f"{type(exc).__name__}: {exc}"
    m = LETTER_RE.search(text.strip())
    if m:
        return m.group(1), text.strip()
    # 兼容未按格式输出：找第一个独立字母
    m2 = re.search(r"\b([A-G])\b", text)
    if m2:
        return m2.group(1), text.strip()[:120]
    return "", f"无法解析: {text[:120]}"


def main() -> None:
    import argparse
    import json
    from collections import Counter

    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", default="1", help="本轮执行哪些 run，如 1 或 2,3")
    args = parser.parse_args()
    wanted = [int(x) for x in args.runs.split(",")]

    state_path = OUT_XLSX.parent / "智能体编码_runs_v2.json"
    results: dict[str, list[tuple[str, str]]] = {}
    if state_path.exists():
        results = {k: [tuple(x) for x in v] for k, v in json.loads(state_path.read_text(encoding="utf-8")).items()}

    photos = sorted(SAMPLE_DIR.glob("S*.jpg"))
    for p in photos:
        results.setdefault(p.stem, [])

    for run in wanted:
        # 只跑尚未完成该 run 的照片
        need = [p for p in photos if len(results[p.stem]) < run]
        if not need:
            print(f"run{run} 已完成，跳过", flush=True)
            continue
        print(f"run{run}: 待编码 {len(need)} 张", flush=True)
        t0 = time.time()
        with cf.ThreadPoolExecutor(max_workers=12) as ex:
            futures = {ex.submit(code_one, p): p.stem for p in need}
            done = 0
            for fut in cf.as_completed(futures):
                stem = futures[fut]
                while len(results[stem]) < run:
                    results[stem].append(("", ""))
                results[stem][run - 1] = fut.result()
                done += 1
                if done % 40 == 0:
                    print(f"  run{run}: {done}/{len(need)}", flush=True)
        state_path.write_text(json.dumps(results, ensure_ascii=False), encoding="utf-8")
        print(f"run{run} 完成，耗时 {time.time()-t0:.0f}s，已落盘", flush=True)

    # 汇总写出 Excel
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = "智能体编码"
    ws.append(["样本编号", "run1", "run2", "run3", "三次一致", "终判(多数表决)", "run1理由"])
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="085399")
    agree_n = 0
    final_codes = {}
    for stem in sorted(results):
        runs = results[stem]
        codes = [c for c, _ in runs]
        valid = [c for c in codes if c]
        unanimous = len(valid) == 3 and len(set(valid)) == 1
        final = Counter(valid).most_common(1)[0][0] if valid else ""
        final_codes[stem] = final
        agree_n += 1 if unanimous else 0
        ws.append([stem, *codes, "一致" if unanimous else "不一致", final, (runs[0][1] if runs else "")[:80]])
    for col, w in zip("ABCDEFG", [10, 7, 7, 7, 9, 14, 70]):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A2"
    wb.save(OUT_XLSX)

    total = len(results)
    print(f"\n三次完全一致率: {agree_n}/{total} = {agree_n/total*100:.1f}%")
    print("终判分布:", dict(Counter(final_codes.values())))
    print("已保存:", OUT_XLSX)


if __name__ == "__main__":
    main()
