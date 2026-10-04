"""保护展示语义编码与空间指标分析。

把一条轨迹的照片语义化结果（视觉描述 / 图注 / 地址等文本）按统一编码表
归入 6 类保护展示语义类型，并计算可跨公园比较的量化指标：

- 语义类型构成比（A–F 各类数量与占比）
- 拍摄密度（照片数 / 轨迹里程）
- 点位簇（按时间差 / 间距自动切分）及其构成与停留时长
- 动线时空序列（供前端 ECharts 散点图）
- 语义序列转移矩阵、序列熵与优势转移路径（A–G 一阶马尔可夫口径）
- 空间集聚指标：最近邻指数 NNI（凸包面积为面域）与 DBSCAN 点位簇

编码表与指标口径来自课题组已验证的实地分析流程（隋唐洛阳城试点），
结果持久化到 ``data/tracks/{track_id}/analysis.json``，不改动数据库结构。
"""
from __future__ import annotations

import csv
import io
import json
import math
from collections import Counter, OrderedDict
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from ..models.track import TrackFile, TrackPhoto
from . import track_service

# ---------------------------------------------------------------------------
# 编码表（v1）：优先级自上而下，首个命中即归类
# 数字互动与运营证据稀缺性最高，优先保留
# ---------------------------------------------------------------------------
CODEBOOK: "OrderedDict[str, list[str]]" = OrderedDict([
    ("D", ["互动触摸屏", "电子展示屏", "AI绘画", "VR", "数字展陈", "问答", "互动屏", "AR", "全息", "数字"]),
    ("E", ["票价", "售票", "文创", "演艺", "舞台", "节目单", "售卖机", "消费", "争霸赛", "入口场景",
           "商店", "收银", "游客中心", "演出", "门票"]),
    ("A", ["夯土", "墩台", "砖铺", "柱础", "柱坑", "遗址层", "车辙", "蹄印", "遗存", "遗址本体",
           "门道", "发掘", "出土", "墓冢", "封土", "城墙遗址", "基址", "剖面", "陶片", "瓦当"]),
    ("C", ["展板", "沙盘", "说明牌", "介绍牌", "模型", "浮雕", "壁画", "标识墙", "主题墙", "分布图",
           "布局图", "路线图", "疆域图", "剖面图", "形制", "展厅", "展陈", "展品", "陈列", "讲解员",
           "导览", "解说", "博物馆"]),
    ("B", ["城楼", "阙楼", "金殿", "天堂", "穹顶", "大棚", "覆罩", "斗栱", "檐部", "木塔", "高塔",
           "复原建筑", "外观", "对景", "回望", "复原", "仿唐", "仿古", "保护棚", "保护罩"]),
    ("F", ["天街", "广场", "俯瞰", "远眺", "绿化", "城市", "立交", "草坪", "城区", "天际线",
           "通廊", "步道", "里坊绿地", "停车场", "道路", "农田", "村庄", "景观", "水面", "湿地"]),
])

TYPE_NAMES = {
    "A": "遗址本体展示",
    "B": "复原建筑与覆罩",
    "C": "阐释解说设施",
    "D": "数字互动展示",
    "E": "运营与消费场景",
    "F": "景观环境与城市关系",
    "G": "其他",
}

# 时间差超过该分钟数或间距超过该米数即切分新簇（与课题组实地分析口径一致）
CLUSTER_GAP_MINUTES = 5.0
CLUSTER_GAP_METERS = 150.0

# 语义序列与空间集聚分析参数
SEQUENCE_ORDER = ["A", "B", "C", "D", "E", "F", "G"]  # 转移矩阵行列固定次序（含 G）
TOP_TRANSITION_LIMIT = 5
DBSCAN_EPS_M = 100.0       # DBSCAN 邻域半径（米）：展厅内连续拍摄的相邻点位尺度
DBSCAN_MIN_SAMPLES = 3     # 核心点邻域内最少样本数（含自身）
_KM_PER_DEG_LAT = 110.57   # 纬度 1° 对应公里数
_KM_PER_DEG_LON_EQUATOR = 111.32  # 赤道处经度 1° 对应公里数


def classify_text(text: str) -> str:
    """按编码表对单条文本归类，返回类型编码（A–F，未命中为 G）。"""
    if not text:
        return "G"
    for code, keywords in CODEBOOK.items():
        if any(keyword in text for keyword in keywords):
            return code
    return "G"


def photo_text(photo: TrackPhoto) -> str:
    """拼合照片的全部可用语义文本作为分类输入。"""
    parts = [photo.description, photo.caption, photo.poi, photo.address, photo.file_name]
    return "；".join(p for p in parts if p)


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    radius = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def cluster_photos(photos: list[TrackPhoto]) -> list[list[TrackPhoto]]:
    """按拍摄顺序，时间差 > CLUSTER_GAP_MINUTES 或间距 > CLUSTER_GAP_METERS 切簇。"""
    timed = sorted(photos, key=lambda p: (p.shot_time or datetime.max, p.seq))
    clusters: list[list[TrackPhoto]] = []
    current: list[TrackPhoto] = []
    prev: TrackPhoto | None = None
    for photo in timed:
        start_new = False
        if prev is not None and current:
            gap_min = None
            if photo.shot_time and prev.shot_time:
                gap_min = (photo.shot_time - prev.shot_time).total_seconds() / 60
            dist = None
            if None not in (photo.longitude, photo.latitude, prev.longitude, prev.latitude):
                dist = haversine_m(prev.longitude, prev.latitude, photo.longitude, photo.latitude)
            if (gap_min is not None and gap_min > CLUSTER_GAP_MINUTES) or (
                dist is not None and dist > CLUSTER_GAP_METERS
            ):
                start_new = True
        if start_new:
            clusters.append(current)
            current = []
        current.append(photo)
        prev = photo
    if current:
        clusters.append(current)
    return clusters


# ---------------------------------------------------------------------------
# 语义序列：一阶转移矩阵、序列熵、优势转移路径
# ---------------------------------------------------------------------------
def build_sequence_analysis(photos: list[TrackPhoto]) -> dict:
    """按拍摄顺序把照片类目序列化，计算 7×7 转移计数/概率矩阵与序列熵。

    - 排序口径与动线时空序列一致：``(shot_time, seq)``，缺失时间排末尾；
    - ``probs`` 行和为 0 时整行置 ``None``（该类目从未作为起点出现）；
    - ``top_transitions`` 的 ``prob`` 为条件概率 P(to|from)，排除自转移。
    """
    ordered = sorted(photos, key=lambda p: (p.shot_time or datetime.max, p.seq))
    codes = [
        getattr(p, "_semantic_type", None) or classify_text(photo_text(p))  # noqa: SLF001
        for p in ordered
    ]
    size = len(SEQUENCE_ORDER)
    index = {code: i for i, code in enumerate(SEQUENCE_ORDER)}
    counts = [[0] * size for _ in range(size)]
    for current, following in zip(codes, codes[1:]):
        if current in index and following in index:
            counts[index[current]][index[following]] += 1

    probs = []
    for row in counts:
        row_total = sum(row)
        probs.append(None if row_total == 0 else [round(value / row_total, 3) for value in row])

    total = len(codes)
    counter = Counter(codes)
    entropy = None
    if total:
        entropy = round(
            -sum((count / total) * math.log2(count / total) for count in counter.values() if count),
            2,
        )

    transitions = []
    for i, source in enumerate(SEQUENCE_ORDER):
        row_total = sum(counts[i])
        if not row_total:
            continue
        for j, target in enumerate(SEQUENCE_ORDER):
            if i == j or not counts[i][j]:
                continue
            transitions.append({
                "from": source,
                "to": target,
                "count": counts[i][j],
                "prob": round(counts[i][j] / row_total, 3),
            })
    transitions.sort(key=lambda item: (-item["count"], item["from"], item["to"]))

    return {
        "order": list(SEQUENCE_ORDER),
        "counts": counts,
        "probs": probs,
        "entropy_bits": entropy,
        "top_transitions": transitions[:TOP_TRANSITION_LIMIT],
    }


# ---------------------------------------------------------------------------
# 空间集聚：凸包面积 → 最近邻指数 NNI；DBSCAN 点位簇
# ---------------------------------------------------------------------------
def _project_km(
    lon: float, lat: float, lon0: float, lat0: float
) -> tuple[float, float]:
    """以点位集中心为原点的局部平面近似坐标（单位 km）。"""
    x = (lon - lon0) * math.cos(math.radians(lat0)) * _KM_PER_DEG_LON_EQUATOR
    y = (lat - lat0) * _KM_PER_DEG_LAT
    return x, y


def _convex_hull(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Andrew monotone chain 凸包，返回逆时针顶点序列（已投影平面坐标）。"""
    unique = sorted(set(points))
    if len(unique) <= 2:
        return unique

    def cross(o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[tuple[float, float]] = []
    for point in unique:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    upper: list[tuple[float, float]] = []
    for point in reversed(unique):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def _polygon_area_km2(hull: list[tuple[float, float]]) -> float:
    """Shoelace 公式求多边形面积（顶点为 km 平面坐标）。"""
    if len(hull) < 3:
        return 0.0
    total = 0.0
    for i in range(len(hull)):
        x1, y1 = hull[i]
        x2, y2 = hull[(i + 1) % len(hull)]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2


def _dbscan_labels(
    points: list[tuple[float, float]], eps_m: float, min_samples: int
) -> list[int]:
    """纯标准库 DBSCAN（O(n²)，点位规模 ≤ 数百可接受）。

    返回与 ``points`` 等长的标签：``-1`` 噪声，``>=0`` 簇编号。
    """
    n = len(points)
    labels = [None] * n  # None 未访问；-1 噪声；>=0 簇号
    neighbors: list[list[int]] = [[] for _ in range(n)]
    for i in range(n):
        lon1, lat1 = points[i]
        for j in range(i + 1, n):
            lon2, lat2 = points[j]
            if haversine_m(lon1, lat1, lon2, lat2) <= eps_m:
                neighbors[i].append(j)
                neighbors[j].append(i)

    cluster_id = 0
    for i in range(n):
        if labels[i] is not None:
            continue
        if len(neighbors[i]) + 1 < min_samples:
            labels[i] = -1
            continue
        cluster_id += 1
        labels[i] = cluster_id
        seeds = list(neighbors[i])
        cursor = 0
        while cursor < len(seeds):
            point_index = seeds[cursor]
            cursor += 1
            if labels[point_index] == -1:
                labels[point_index] = cluster_id  # 边界点并入当前簇
                continue
            if labels[point_index] is not None:
                continue
            labels[point_index] = cluster_id
            if len(neighbors[point_index]) + 1 >= min_samples:
                seeds.extend(neighbors[point_index])
    return [label if label is not None else -1 for label in labels]


def build_spatial_analysis(photos: list[TrackPhoto]) -> dict:
    """计算带坐标照片点的最近邻指数（NNI）与 DBSCAN 空间聚类结果。

    NNI = 实测最近邻平均距离 / 随机分布期望距离，期望距离取 ``0.5/sqrt(n/A)``，
    面域 A 用点位凸包面积（km²）。点位数 < 4 或凸包面积退化时 ``nni`` 为 ``None``。
    ``mean_nn_distance_m`` 为实测最近邻平均距离本身（米），点位数 < 2 时为 ``None``。
    """
    points = [
        (p.longitude, p.latitude)
        for p in photos
        if p.longitude is not None and p.latitude is not None
    ]
    n = len(points)
    result = {
        "nni": None,
        "point_count": n,
        "hull_area_km2": None,
        "mean_nn_distance_m": None,
        "dbscan_eps_m": DBSCAN_EPS_M,
        "dbscan_min_samples": DBSCAN_MIN_SAMPLES,
        "dbscan_clusters": 0,
        "noise_ratio": None,
    }
    if n == 0:
        return result

    # DBSCAN：噪声不计入簇数
    labels = _dbscan_labels(points, DBSCAN_EPS_M, DBSCAN_MIN_SAMPLES)
    clusters = {label for label in labels if label >= 0}
    result["dbscan_clusters"] = len(clusters)
    result["noise_ratio"] = round(sum(1 for label in labels if label < 0) / n, 2)

    # 实测最近邻平均距离：每个点到其余点的最小球面距离取均值
    observed_km = None
    if n >= 2:
        observed = 0.0
        for i, (lon1, lat1) in enumerate(points):
            nearest = min(
                haversine_m(lon1, lat1, lon2, lat2)
                for j, (lon2, lat2) in enumerate(points)
                if j != i
            )
            observed += nearest
        observed_km = observed / n / 1000
        result["mean_nn_distance_m"] = round(observed / n, 1)

    # 凸包面积（面域 A）
    lat0 = sum(lat for _, lat in points) / n
    lon0 = sum(lon for lon, _ in points) / n
    projected = [_project_km(lon, lat, lon0, lat0) for lon, lat in points]
    hull = _convex_hull(projected)
    area = _polygon_area_km2(hull)
    result["hull_area_km2"] = round(area, 3)

    if observed_km is None or n < 4 or area <= 0:
        return result

    expected_km = 0.5 / math.sqrt(n / area)
    result["nni"] = round(observed_km / expected_km, 3) if expected_km > 0 else None
    return result


def analysis_path(track_id: int) -> Path:
    return track_service.track_dir(track_id) / "analysis.json"


def load_analysis(track_id: int) -> dict | None:
    path = analysis_path(track_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def analyze_track(db: Session, track: TrackFile, persist: bool = True) -> dict:
    """对一条轨迹执行语义编码与指标计算，返回分析结果字典。"""
    photos = track_service.ordered_photos(db, track.id)
    for photo in photos:
        photo._semantic_type = classify_text(photo_text(photo))  # noqa: SLF001 运行期挂接，不入库

    # 1. 类型构成
    counter = Counter(p._semantic_type for p in photos)  # noqa: SLF001
    total = len(photos) or 1
    composition = [
        {"code": code, "name": TYPE_NAMES[code], "count": counter.get(code, 0),
         "percent": round(counter.get(code, 0) / total * 100, 1)}
        for code in ["A", "B", "C", "D", "E", "F", "G"]
        if counter.get(code, 0) or code != "G"
    ]

    # 2. 轨迹与密度
    distance_m = track.distance_meters or 0.0
    distance_km = round(distance_m / 1000, 2)
    density = round(len(photos) / (distance_m / 1000), 1) if distance_m > 0 else None

    # 3. 点位簇
    clusters_raw = cluster_photos(photos)
    clusters = []
    for index, members in enumerate(clusters_raw, start=1):
        times = [p.shot_time for p in members if p.shot_time]
        stay = round((max(times) - min(times)).total_seconds() / 60) if len(times) > 1 else 0
        comp = Counter(p._semantic_type for p in members)  # noqa: SLF001
        lats = [p.latitude for p in members if p.latitude is not None]
        lons = [p.longitude for p in members if p.longitude is not None]
        clusters.append({
            "cluster": f"C{index:02d}",
            "count": len(members),
            "time_start": min(times).isoformat() if times else None,
            "time_end": max(times).isoformat() if times else None,
            "stay_minutes": stay,
            "composition": {code: comp.get(code, 0) for code in ["A", "B", "C", "D", "E", "F", "G"] if comp.get(code)},
            "center_lat": round(sum(lats) / len(lats), 6) if lats else None,
            "center_lon": round(sum(lons) / len(lons), 6) if lons else None,
        })

    # 4. 动线时空序列（前端散点图：x=相对分钟，y=纬度，色=语义类型）
    timed = [p for p in photos if p.shot_time]
    t0 = min((p.shot_time for p in timed), default=None)
    spacetime = [
        {
            "id": p.id,
            "t_min": round((p.shot_time - t0).total_seconds() / 60, 1) if t0 else None,
            "lat": p.latitude,
            "lon": p.longitude,
            "type": p._semantic_type,  # noqa: SLF001
            "type_name": TYPE_NAMES[p._semantic_type],  # noqa: SLF001
            "caption": p.caption or p.file_name,
            "thumb_url": f"/api/track/{track.id}/photos/{p.id}?thumb=true",
        }
        for p in sorted(photos, key=lambda x: (x.shot_time or datetime.max, x.seq))
    ]

    # 5. 语义序列：一阶转移矩阵 + 序列熵 + 优势转移路径
    sequence = build_sequence_analysis(photos)

    # 6. 空间集聚：最近邻指数 NNI + DBSCAN 点位簇
    spatial = build_spatial_analysis(photos)

    result = {
        "track_id": track.id,
        "original_name": track.original_name,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "codebook_version": "v1",
        "photo_count": len(photos),
        "track_point_count": track.track_point_count,
        "distance_km": distance_km,
        "photo_density_per_km": density,
        "duration_minutes": (
            round((track.end_time - track.start_time).total_seconds() / 60)
            if track.start_time and track.end_time else None
        ),
        "composition": composition,
        "clusters": clusters,
        "spacetime": spacetime,
        "sequence": sequence,
        "spatial": spatial,
        "photos": [
            {"id": p.id, "seq": p.seq, "file_name": p.file_name,
             "shot_time": p.shot_time.isoformat() if p.shot_time else None,
             "type": p._semantic_type, "type_name": TYPE_NAMES[p._semantic_type],  # noqa: SLF001
             "caption": p.caption, "cluster": next(
                 (c["cluster"] for c, members in zip(clusters, clusters_raw) if p in members), None)}
            for p in photos
        ],
    }
    if persist:
        path = analysis_path(track.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return result


def build_analysis_csv(analysis: dict) -> bytes:
    """语义编码结果导出 CSV（UTF-8 BOM，Excel 可直接打开）。"""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["照片ID", "序号", "文件名", "拍摄时间", "语义类型编码", "语义类型", "点位簇", "图注"])
    for photo in analysis.get("photos", []):
        writer.writerow([
            photo["id"], photo["seq"], photo["file_name"], photo["shot_time"],
            photo["type"], photo["type_name"], photo["cluster"], photo["caption"] or "",
        ])
    return buffer.getvalue().encode("utf-8-sig")


def compare_tracks(db: Session, track_ids: list[int]) -> dict:
    """跨轨迹（跨公园）语义构成比较：优先读已持久化的分析，缺失则即时计算。"""
    items = []
    for track_id in track_ids:
        track = db.get(TrackFile, track_id)
        if track is None:
            continue
        analysis = load_analysis(track_id) or analyze_track(db, track)
        sequence = analysis.get("sequence") or {}
        spatial = analysis.get("spatial") or {}
        top_transition = (sequence.get("top_transitions") or [None])[0]
        items.append({
            "track_id": track.id,
            "name": Path(track.original_name).stem,
            "photo_count": analysis["photo_count"],
            "distance_km": analysis["distance_km"],
            "photo_density_per_km": analysis["photo_density_per_km"],
            "cluster_count": len(analysis["clusters"]),
            "composition": analysis["composition"],
            "entropy_bits": sequence.get("entropy_bits"),
            "top_transition": top_transition,
            "nni": spatial.get("nni"),
            "mean_nn_distance_m": spatial.get("mean_nn_distance_m"),
            "dbscan_clusters": spatial.get("dbscan_clusters"),
        })
    return {
        "codebook_version": "v1",
        "type_names": TYPE_NAMES,
        "items": items,
    }
