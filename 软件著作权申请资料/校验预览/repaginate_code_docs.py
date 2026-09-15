from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(r"H:\my_code\datak")
WORKDIR = ROOT / "软件著作权申请资料"
SKILL_SCRIPT = Path(
    r"C:\Users\zhang\.codex\skills\software-copyright-materials\scripts\build_docx_from_md.py"
)
SOFFICE = Path(r"C:\Program Files\LibreOffice\program\soffice.exe")
SOFTWARE_NAME = "考古遗址公园文化价值智能数字化阐释平台"
VERSION = "V1.0"

FRONT_MD = WORKDIR / "草稿" / "代码-前30页.md"
BACK_MD = WORKDIR / "草稿" / "代码-后30页.md"
FINAL_DIR = WORKDIR / "正式资料"
PREVIEW_DIR = WORKDIR / "校验预览"
PROBE_DIR = PREVIEW_DIR / "代码分页探测"


def load_builder():
    sys.path.insert(0, str(SKILL_SCRIPT.parent))
    spec = importlib.util.spec_from_file_location("softcopy_builder", SKILL_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载生成脚本：{SKILL_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_single_stream_md(path: Path, start_page: int, lines: list[str]) -> None:
    body = [f"## 第 {start_page} 页", "", "```text", *lines, "```", ""]
    path.write_text("\n".join(body), encoding="utf-8")


def convert_to_pdf(docx_path: Path, pdf_path: Path) -> int:
    if pdf_path.exists():
        pdf_path.unlink()
    profile = Path(tempfile.mkdtemp(prefix="codex-softcopy-lo-"))
    try:
        result = subprocess.run(
            [
                str(SOFFICE),
                f"-env:UserInstallation={profile.as_uri()}",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(pdf_path.parent),
                str(docx_path),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        generated = pdf_path.parent / f"{docx_path.stem}.pdf"
        if result.returncode != 0 or not generated.exists():
            raise RuntimeError(
                f"LibreOffice 转换失败：exit={result.returncode}\n"
                f"{result.stdout}\n{result.stderr}"
            )
        if generated != pdf_path:
            if pdf_path.exists():
                pdf_path.unlink()
            generated.replace(pdf_path)
        return len(PdfReader(str(pdf_path)).pages)
    finally:
        shutil.rmtree(profile, ignore_errors=True)


def find_max_lines_for_30_pages(
    builder,
    all_lines: list[str],
    *,
    from_tail: bool,
    start_page: int,
    label: str,
) -> tuple[int, int]:
    low = 1
    high = len(all_lines)
    best_n = 0
    best_pages = 0
    md_path = PROBE_DIR / f"{label}.md"
    docx_path = PROBE_DIR / f"{label}.docx"
    pdf_path = PROBE_DIR / f"{label}.pdf"

    while low <= high:
        mid = (low + high) // 2
        selected = all_lines[-mid:] if from_tail else all_lines[:mid]
        write_single_stream_md(md_path, start_page, selected)
        builder.build_code_docx_python(
            md_path, docx_path, SOFTWARE_NAME, VERSION
        )
        pages = convert_to_pdf(docx_path, pdf_path)
        print(f"{label}: lines={mid}, pages={pages}")
        if pages <= 30:
            best_n = mid
            best_pages = pages
            low = mid + 1
        else:
            high = mid - 1

    if best_n == 0:
        raise RuntimeError(f"{label} 无法生成不超过30页的文档")
    return best_n, best_pages


def main() -> None:
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    PROBE_DIR.mkdir(parents=True, exist_ok=True)
    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    builder = load_builder()
    original_set_run_font = builder.set_run_font
    original_set_normal_font = builder.set_normal_font

    def set_run_font_min_8(run, name: str, size_pt: float) -> None:
        original_set_run_font(run, name, max(8.0, size_pt))

    def set_normal_font_min_8(document, name: str = "SimSun", size_pt: float = 10.5) -> None:
        original_set_normal_font(document, name, max(8.0, size_pt))

    builder.set_run_font = set_run_font_min_8
    builder.set_normal_font = set_normal_font_min_8

    parsed = builder.parse_code_pages(FRONT_MD) + builder.parse_code_pages(BACK_MD)
    all_lines = [line for _, lines in parsed for line in lines]
    if not all_lines:
        raise RuntimeError("未解析到代码材料")

    front_n, _ = find_max_lines_for_30_pages(
        builder,
        all_lines,
        from_tail=False,
        start_page=1,
        label="front_probe",
    )
    back_n, _ = find_max_lines_for_30_pages(
        builder,
        all_lines,
        from_tail=True,
        start_page=31,
        label="back_probe",
    )
    if front_n + back_n > len(all_lines):
        raise RuntimeError("前后材料发生重叠，无法满足连续首尾材料要求")

    front_stream = PROBE_DIR / "front_final.md"
    back_stream = PROBE_DIR / "back_final.md"
    write_single_stream_md(front_stream, 1, all_lines[:front_n])
    write_single_stream_md(back_stream, 31, all_lines[-back_n:])

    front_out = FINAL_DIR / f"{SOFTWARE_NAME}-代码(前30页).docx"
    back_out = FINAL_DIR / f"{SOFTWARE_NAME}-代码(后30页).docx"
    builder.build_code_docx_python(
        front_stream, front_out, SOFTWARE_NAME, VERSION
    )
    builder.build_code_docx_python(
        back_stream, back_out, SOFTWARE_NAME, VERSION
    )

    front_pdf = PREVIEW_DIR / f"{front_out.stem}.pdf"
    back_pdf = PREVIEW_DIR / f"{back_out.stem}.pdf"
    front_pages = convert_to_pdf(front_out, front_pdf)
    back_pages = convert_to_pdf(back_out, back_pdf)
    if front_pages != 30 or back_pages != 30:
        raise RuntimeError(
            f"最终页数不符合要求：前段={front_pages}，后段={back_pages}"
        )

    report = {
        "source_material_lines": len(all_lines),
        "front_selected_lines": front_n,
        "back_selected_lines": back_n,
        "omitted_middle_lines": len(all_lines) - front_n - back_n,
        "front_rendered_pages": front_pages,
        "back_rendered_pages": back_pages,
        "code_font_size_pt": 8.0,
        "source_text_changed": False,
        "note": "仅取消草稿中的预设分页，按LibreOffice物理页重新截取已确认代码的首30页和末30页。",
    }
    (PREVIEW_DIR / "代码物理分页校验.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
