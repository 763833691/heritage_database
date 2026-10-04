# 语义序列与空间集聚分析函数 开发文档

> 读者：workbuddy（编码助手）
> 项目根目录：`H:\my_code\datak`
> 任务：在轨迹语义分析模块中补充两类空间分析——①语义序列转移矩阵与序列熵；②最近邻指数（NNI）与 DBSCAN 空间聚类——并接入单轨分析与跨轨比较结果。
> 约束：**只新增，不改既有函数行为；不要重构 `semantic_analysis.py` 中已有代码；不要动前端（本轮只做后端数据）。**

---

## 1. 项目现状（已核实，直接采信）

- 目标文件：`backend/app/services/semantic_analysis.py`（约 250 行），关键现有件：
  - `analyze_track(db, track, persist=True) -> dict`：第 127 行，返回结果字典并持久化到 `data/tracks/{track_id}/analysis.json`；结果含 `photos`（每项有 `id/seq/shot_time/type(A–G)/cluster`）、`clusters`、`composition`、`distance_km`、`photo_density_per_km` 等。
  - 照片类型在运行期挂接：`photo._semantic_type = classify_text(photo_text(photo))`（不入库）。
  - `compare_tracks(db, track_ids) -> dict`：第 230 行，返回 `{"codebook_version", "type_names", "items": [...]}`，每个 item 含 `track_id/name/photo_count/distance_km/photo_density_per_km/cluster_count/composition`。
  - 模块内已有 `haversine_m(lon1, lat1, lon2, lat2)`（米）。
  - `track_service.ordered_photos(db, track_id)` 返回按序照片（`TrackPhoto` 有 `longitude/latitude/shot_time/seq`）。
- API 层：`app/api/track.py` 已有 `POST /{track_id}/analyze`、`GET /{track_id}/analysis`、`GET /analysis/compare`，无需新增端点，只需让返回的分析字典带上新字段。
- 运行环境：无 numpy/scipy 强制依赖要求，**优先纯标准库实现**（math/json/collections 即可）；如确需 numpy 可用（项目环境已装）。

## 2. 功能一：语义序列转移矩阵与序列熵

### 2.1 定义

- 对单条轨迹：照片按 `(shot_time, seq)` 排序，得到类目序列 `t1, t2, …, tn`（ti ∈ A–G，**沿用现有 `_semantic_type`，含 G**）。
- **转移计数矩阵** `counts[i][j]` = 序列中"类目 i 后面紧跟类目 j"的出现次数（i, j ∈ A–G，7×7）。
- **转移概率矩阵** `probs[i][j]` = `counts[i][j] / sum_j counts[i][j]`（行和为 0 时整行置 null）。
- **展示序列熵**：将整条类目序列视为离散分布 `p(c) = count(c)/n`，计算 Shannon 熵 `H = -Σ p(c)·log2 p(c)`，单位 bit，保留 2 位小数。
- **优势路径**：按 `counts[i][j]`（i≠j，排除自转移）降序取 Top-5，每项 `{from, to, count, prob}`。

### 2.2 集成位置

在 `analyze_track` 的 `result` 字典中新增一个键：

```python
"sequence": {
    "order": ["A","B","C","D","E","F","G"],
    "counts": [[...], ...],        # 7×7 整数矩阵
    "probs": [[...], ...],         # 7×7 浮点矩阵（3 位小数），零行用 null
    "entropy_bits": 2.31,          # 序列 Shannon 熵
    "top_transitions": [
        {"from": "A", "to": "C", "count": 18, "prob": 0.42}, ...
    ],
}
```

实现为模块内新函数 `build_sequence_analysis(photos) -> dict`，在 `analyze_track` 中调用（放在现有第 168 行"动线时空序列"之后、组装 `result` 之前，把结果放进 `result`）。

### 2.3 跨轨比较集成

`compare_tracks` 的每个 item 新增两个字段：

```python
"entropy_bits": 2.31,                       # 该轨迹的序列熵
"top_transition": {"from": "A", "to": "C", "prob": 0.42},   # 最强的一条转移
```

## 3. 功能二：最近邻指数（NNI）与 DBSCAN 空间聚类

### 3.1 NNI（最近邻指数）

- 输入：一条轨迹中所有带坐标的照片点（`longitude/latitude` 非空）。
- 计算：每个点到其最近邻点的球面距离（用现有 `haversine_m`），取均值 `d_obs`；
- 期望距离：`d_exp = 0.5 / sqrt(n / A)`，其中 `A` 为点位集的面积（km²）——**用点位凸包（convex hull）面积**，凸包顶点用经纬度转平面近似坐标（以点位中心为原点，`x = lon差 × cos(中心纬度) × 111.32 km`，`y = lat差 × 110.57 km`）后用 Shoelace 公式求面积；凸包算法用 Andrew monotone chain（约 20 行标准库实现），点位数 < 4 或凸包面积 ≈ 0 时返回 `nni: null`；
- `nni = d_obs(km) / d_exp(km)`，保留 3 位小数。NNI < 1 集聚、≈1 随机、>1 离散。

### 3.2 DBSCAN 空间聚类

- 纯标准库实现 DBSCAN（点位 ≤150 个，O(n²) 可接受）；
- 参数：`eps = 100 m`，`min_samples = 3`；
- 输出：簇数 `dbscan_clusters`（噪声不计）、噪声点占比 `noise_ratio`（2 位小数）。

### 3.3 集成位置

`analyze_track` 的 `result` 新增：

```python
"spatial": {
    "nni": 0.83,
    "point_count": 110,
    "hull_area_km2": 2.94,
    "dbscan_eps_m": 100,
    "dbscan_min_samples": 3,
    "dbscan_clusters": 9,
    "noise_ratio": 0.12,
}
```

实现为新函数 `build_spatial_analysis(photos) -> dict`。

`compare_tracks` 的每个 item 新增：`"nni"`、`"dbscan_clusters"`。

## 4. 验收标准（必须全部通过）

在 `backend/` 下用项目 Python 环境（`E:\software\install\Anaconda\python.exe`）运行并核对：

1. **重跑全部分析**：对数据库中全部 14 条轨迹执行 `analyze_track`（参考既有调用方式：`db.query(TrackFile).all()` 逐条跑，persist=True），14 个 `analysis.json` 均含 `sequence` 与 `spatial` 两个新键。
2. **守恒校验**：每条轨迹 `sequence.counts` 全部元素之和 == 该轨迹 `photo_count - 1`；`probs` 每行元素之和为 1（±0.01）或为 null。
3. **熵值合理性**：`entropy_bits` ∈ (0, log2(7)≈2.81)；单类目主导的轨迹熵显著低于多类目均衡的轨迹。
4. **NNI 合理性**：博物馆段（如 track 3 良渚博物院、track 7 鸿山遗址博物馆）NNI 应显著小于遗址区长距离段（如 track 1 统万城）；所有 NNI > 0。
5. **比较接口**：调用 `compare_tracks(db, [1..14])`，每个 item 含 `entropy_bits/top_transition/nni/dbscan_clusters` 四字段。
6. **API 冒烟**：启动 `uvicorn app.main:app` 后 `GET /api/track/13/analysis` 返回中含 `sequence` 与 `spatial`（注意 `GET /analysis` 端点有缓存逻辑：若 `load_analysis` 命中已持久化文件则直接返回——重跑分析后缓存文件已被覆盖，无需额外处理）。
7. 不破坏既有键：`composition/clusters/spacetime/photos` 的字段与语义保持不变（用 track 13 前后 diff 验证仅有新增键）。

## 5. 输出物与汇报

完成后汇报：每条轨迹的 `entropy_bits`、`nni`、`dbscan_clusters`、最强转移路径（`from→to, prob`）共 14 行的汇总表；验收标准 1–7 逐项结果。

## 6. 明确不做

- 不做前端展示（图谱可视化下轮再说）；
- 不改 `classify_text`/CODEBOOK/聚类参数等既有逻辑；
- 不引入 pandas/scipy/sklearn（纯标准库；若用 numpy 仅限数值计算）；
- 不做二级编码（A-a/B-b…）相关分析。
