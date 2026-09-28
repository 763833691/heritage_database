"""批量导入两步路 KML 并跑完整流水线（解析→下载→逆地理→视觉描述→语义分析）。

用法（在 backend 目录下，用 Anaconda Python 运行）:
    python scripts/batch_import_tracks.py <kml_dir> [--only 文件名1 文件名2 ...] [--skip-existing]

- 按 original_name 查重：已存在且 status=done 的默认跳过（除非 --rerun）。
- 流水线完成后自动执行 semantic_analysis.analyze_track 并持久化。
- 串行逐个文件处理，打印进度，便于分段调用避开超时。
"""
from __future__ import annotations

import argparse
import asyncio
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal  # noqa: E402
from app.models.track import TrackFile  # noqa: E402
from app.services import semantic_analysis, track_service  # noqa: E402


def find_existing(db, filename: str):
    return db.query(TrackFile).filter(TrackFile.original_name == filename).first()


def import_one(kml_path: Path, rerun: bool = False) -> dict:
    filename = kml_path.name
    t0 = time.time()
    db = SessionLocal()
    try:
        track = find_existing(db, filename)
        if track is not None and track.status == "done" and not rerun:
            return {"file": filename, "track_id": track.id, "action": "skip-done"}
        if track is None:
            track = TrackFile(original_name=filename, status="pending", stage="pending", survey_task_id=None)
            db.add(track)
            db.commit()
            db.refresh(track)
        destination = track_service.source_dir(track.id) / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(kml_path, destination)
        track.kml_path = str(destination)
        track.status = "pending"
        track.stage = "pending"
        db.commit()
        track_id = track.id
    finally:
        db.close()

    # process_track 内部自建 Session，异步执行
    asyncio.run(track_service.process_track(track_id))

    db = SessionLocal()
    try:
        track = db.get(TrackFile, track_id)
        result = {
            "file": filename,
            "track_id": track_id,
            "action": "processed",
            "status": track.status,
            "stage": track.stage,
            "photo_count": track.photo_count,
            "track_point_count": track.track_point_count,
            "error": track.error_message,
            "seconds": round(time.time() - t0, 1),
        }
        if track.status == "done":
            analysis = semantic_analysis.analyze_track(db, track)
            result["analysis_clusters"] = len(analysis.get("clusters", [])) if analysis else 0
        return result
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("kml_dir", help="KML 文件所在目录")
    parser.add_argument("--only", nargs="*", default=None, help="只处理这些文件名")
    parser.add_argument("--exclude", nargs="*", default=[], help="排除这些文件名")
    parser.add_argument("--rerun", action="store_true", help="即使已 done 也重跑")
    args = parser.parse_args()

    kml_dir = Path(args.kml_dir)
    files = sorted(kml_dir.glob("*.kml"))
    if args.only:
        wanted = set(args.only)
        files = [f for f in files if f.name in wanted]
    if args.exclude:
        excluded = set(args.exclude)
        files = [f for f in files if f.name not in excluded]
    if not files:
        print("没有匹配的 KML 文件")
        return

    print(f"待处理 {len(files)} 个文件: {[f.name for f in files]}")
    results = []
    for f in files:
        print(f"\n=== [{time.strftime('%H:%M:%S')}] 开始处理 {f.name} ===", flush=True)
        try:
            r = import_one(f, rerun=args.rerun)
        except Exception as exc:  # noqa: BLE001
            r = {"file": f.name, "action": "error", "error": f"{type(exc).__name__}: {exc}"}
        results.append(r)
        print("结果:", r, flush=True)

    print("\n===== 汇总 =====")
    for r in results:
        print(r)


if __name__ == "__main__":
    main()
