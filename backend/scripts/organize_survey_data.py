"""整理网站数据库：补录调研覆盖的 6 个遗址公园、规范调研任务标题并关联公园、更新任务状态。

只增不改用户既有数据（不删任何记录）。坐标取对应轨迹照片的重心。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal  # noqa: E402
from app.models.park import Park  # noqa: E402
from app.models.survey import SurveyTask  # noqa: E402
from app.models.track import TrackFile, TrackPhoto  # noqa: E402

# 新增公园（第二批 2013：海昏侯、南旺、鲁国故城；第一批 2010：良渚、鸿山；第三批 2017：西夏陵）
NEW_PARKS = [
    dict(name="南昌汉代海昏侯国国家考古遗址公园", short_name="海昏侯", park_type="郊野型", batch=2,
         province="江西", city="南昌", district="新建区", world_heritage=0, aaa_level="4A", open_year=2020,
         description="汉代海昏侯国都城与墓园遗址，出土文物数量与等级罕见"),
    dict(name="良渚国家考古遗址公园", short_name="良渚", park_type="郊野型", batch=1,
         province="浙江", city="杭州", district="余杭区", world_heritage=1, aaa_level=None, open_year=2019,
         description="良渚古城遗址，中华五千年文明史实证，2019年列入世界遗产"),
    dict(name="鸿山国家考古遗址公园", short_name="鸿山", park_type="郊野型", batch=1,
         province="江苏", city="无锡", district="新吴区", world_heritage=0, aaa_level=None, open_year=None,
         description="春秋战国时期越国贵族墓地群，与湿地公园复合共生"),
    dict(name="大运河南旺枢纽国家考古遗址公园", short_name="南旺", park_type="郊野型", batch=2,
         province="山东", city="济宁", district="汶上县", world_heritage=1, aaa_level=None, open_year=None,
         description="京杭大运河南旺分水枢纽遗址，大运河世界遗产点"),
    dict(name="鲁国故城国家考古遗址公园", short_name="鲁国故城", park_type="城市型", batch=2,
         province="山东", city="济宁", district="曲阜市", world_heritage=0, aaa_level=None, open_year=None,
         description="两周时期鲁国都城遗址，儒家文化发源地的重要物质载体"),
    dict(name="西夏陵国家考古遗址公园", short_name="西夏陵", park_type="郊野型", batch=3,
         province="宁夏", city="银川", district="西夏区", world_heritage=1, aaa_level="4A", open_year=None,
         description="西夏王朝皇家陵寝，2025年列入世界遗产"),
]

# 任务 → (公园short_name, 规范标题)
TASK_MAP = {
    2: ("统万城", "统万城遗址调研"),
    3: ("殷墟", "殷墟调研（一）"),
    4: ("良渚", "良渚博物院调研"),
    5: ("海昏侯", "海昏侯博物馆调研"),
    6: ("海昏侯", "海昏侯刘贺主墓调研"),
    7: ("良渚", "良渚遗址公园调研"),
    8: ("鸿山", "鸿山遗址博物馆调研"),
    9: ("鸿山", "鸿山湿地公园调研"),
    10: ("南旺", "南旺枢纽调研（一）"),
    11: ("南旺", "南旺枢纽调研（二）"),
    12: ("殷墟", "殷墟调研（二）"),
    13: ("鲁国故城", "鲁国故城调研"),
    14: ("隋唐洛阳城", "隋唐洛阳城调研"),
    15: ("西夏陵", "西夏陵调研"),
}


def main() -> None:
    db = SessionLocal()
    try:
        # 1) 补录公园
        park_by_short = {p.short_name: p for p in db.query(Park).all()}
        for spec in NEW_PARKS:
            if spec["short_name"] in park_by_short:
                print(f"公园已存在，跳过: {spec['short_name']}")
                continue
            park = Park(**spec)
            db.add(park)
            db.flush()
            park_by_short[spec["short_name"]] = park
            print(f"新增公园: {park.name} (id={park.id})")
        db.commit()

        # 2) 用轨迹照片重心回填新公园坐标
        for task_id, (short, _title) in TASK_MAP.items():
            park = park_by_short.get(short)
            if park is None or (park.longitude and park.latitude):
                continue
            tracks = db.query(TrackFile).filter(TrackFile.survey_task_id == task_id).all()
            for tr in tracks:
                photos = db.query(TrackPhoto).filter(
                    TrackPhoto.track_id == tr.id,
                    TrackPhoto.longitude.isnot(None),
                ).all()
                if photos:
                    park.longitude = round(sum(p.longitude for p in photos) / len(photos), 5)
                    park.latitude = round(sum(p.latitude for p in photos) / len(photos), 5)
                    print(f"回填坐标 {short}: ({park.longitude}, {park.latitude})  来自 {len(photos)} 张照片")
                    break
        db.commit()

        # 3) 规范任务标题、关联公园、状态置 ready
        for task_id, (short, title) in TASK_MAP.items():
            task = db.get(SurveyTask, task_id)
            if task is None:
                print(f"任务不存在: {task_id}")
                continue
            park = park_by_short.get(short)
            task.title = title
            task.park_id = park.id if park else None
            task.status = "ready"
            print(f"任务 {task_id}: {title} -> 公园 {short} (id={task.park_id}), status=ready")
        db.commit()
        print("\n整理完成")
    finally:
        db.close()


if __name__ == "__main__":
    main()
