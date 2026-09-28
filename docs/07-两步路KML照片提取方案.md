# 两步路 KML 轨迹照片提取与语义化功能方案

> 版本：v1.0 · 2026-09-17 · 状态：待评审

## 1. 需求概述

用户上传两步路 App 导出的 KML 轨迹文件（如 `2026-09-08 10_44 刘贺主墓 南昌新建区.kml`），系统：

1. 解析 KML，提取轨迹（Track Point）与含照片标注点（如 `landmark`、`photo` 类 Placemark，含经纬度、海拔、拍摄时间、速度、定位精度、照片 URL）。
2. 批量下载照片原图，本地持久化。
3. 将每张照片的坐标逆地理编码为语义地址（省 / 市 / 区县 / 街道 / 附近 POI），并结合轨迹起止点、相邻标注点生成语义描述。
4. 前端地图可视化（轨迹 + 照片点位），表格浏览，导出 Excel 汇总表与 ZIP 照片包。

## 2. 可行性结论（已实测验证）

| 验证项 | 结论 | 依据 |
|---|---|---|
| KML 解析 | ✅ | 实测解析 264 个轨迹点、57 张照片点，字段完整（坐标 / 海拔 / 时间 / 速度 / 精度） |
| 照片下载 | ✅ | 照片 URL 为两步路 CDN 直链，无需登录态，httpx 可直拉（测试 498KB JPEG） |
| 逆地理编码 | ✅ | BigDataCloud 免费无 Key、有中文结果；Nominatim 作备选（需 UA 头与限速） |
| 技术栈匹配 | ✅ | 后端 FastAPI + pandas/openpyxl/httpx 全在现有 requirements；前端 Leaflet/Element Plus 已集成 |

> 双格式兼容已于 2026-09-20 实装并验证（新版 TimeStamp 格式 + 旧版 ExtendedData/description 格式）。

风险与对策：

- **照片 URL 失效**：下载失败时保留记录并标记 `download_status=failed`，表格中显示占位图，不阻塞整体流程。
- **逆地理编码限流**：队列串行 + 0.3s 间隔 + 失败重试 2 次 + 本地缓存（同一坐标 6 位小数直接复用）。
- **截图类 KML 无坐标**：解析时校验坐标字段，缺失则在结果中标注"无坐标信息"，提示用户。
- **境内部署合规**：若部署在境内且用 BigDataCloud/Nominatim 有访问波动，可切换高德 Web 服务 API（需 Key，每天有免费配额），做成 Provider 可配置。

## 3. 总体架构

```
┌────────────┐  POST /api/track/upload (KML)   ┌──────────────────────────────┐
│  Vue3 前端  │ ──────────────────────────────▶ │  FastAPI                     │
│  上传组件   │ ◀─ task_id / WebSocket 进度 ─── │  track 模块                  │
│  Leaflet 图 │                                  │  ① KML 解析 (fastkml/自解析)  │
│  表格+导出  │  GET  /api/track/{id}/result    │  ② 照片下载队列 (httpx,异步)  │
└────────────┘  GET  /api/track/{id}/export     │  ③ 逆地理编码 (provider 可插拔)│
                     (xlsx / zip / photo文件)   │  ④ 结果落库 (SQLAlchemy)      │
                                                └──────────┬───────────────────┘
                                                           │
                                              ┌────────────┴────────────┐
                                              │ 存储                    │
                                              │  DB: track_file / photo │
                                              │  磁盘: uploads/tracks/  │
                                              │        {id}/photos/*.jpg│
                                              └─────────────────────────┘
```

### 处理流程（异步任务）

1. **上传**：前端上传 KML → 后端保存原始文件、创建 `track_file` 记录（状态 `pending`）→ 立即返回 `task_id`，前端轮询 `/api/track/{id}/status`（或复用项目已有 SSE/WebSocket 能力推进度）。
2. **解析**：提取轨迹点序列与照片点列表；计算轨迹起止点语义（首个/末个轨迹点同样逆编码）。
3. **下载**：照片逐个异步下载（并发 3-5），写盘 `uploads/tracks/{track_id}/photos/{拍摄时间}_{序号}.jpg`，同时生成缩略图（Pillow，宽 400px，用于表格预览）。
4. **逆地理编码**：逐照片反解省市区街道 + 最近 POI；结合轨迹语义生成一句话描述，如「摄于海昏侯墓园参观步道，距轨迹起点约 320 m，海拔 -12 m」。
5. **完成**：状态置 `done`，前端展示地图 + 表格。

## 4. 数据模型（新增两张表）

```text
track_file
  id, 原文件名, 上传时间, 状态(pending/parsing/downloading/geocoding/done/failed),
  轨迹点数, 照片数, 起点语义, 终点语义, 错误信息

track_photo
  id, track_file_id, 文件名, 缩略图路径, 拍摄时间, 纬度, 经度, 海拔,
  速度, 定位精度, 省, 市, 区县, 街道, 附近POI, 语义描述,
  下载状态, 下载URL, 创建时间
```

SQLite 本地模式直接建表；PostgreSQL 模式走 alembic 迁移（与项目现有规范一致）。

## 5. 后端实现要点

新增 `backend/app/api/track.py` + `backend/app/services/track_service.py`：

| 端点 | 说明 |
|---|---|
| `POST /api/track/upload` | 上传 KML，返回 `{track_id, status}` |
| `GET  /api/track/{id}/status` | 处理进度（阶段 + 已完成/总数） |
| `GET  /api/track/{id}` | 轨迹 GeoJSON + 照片点列表（含语义） |
| `GET  /api/track/{id}/photos/{photo_id}` | 返回原图 / 缩略图文件 |
| `GET  /api/track/{id}/export.xlsx` | Excel 汇总表（照片缩略图内嵌 + 全部字段） |
| `GET  /api/track/{id}/export.zip` | 照片原图打包下载 |
| `GET  /api/track/list` | 历史上传列表 / 删除 |

依赖增量（都很轻量）：

```
httpx            # 已有，照片下载 + 逆地理编码 HTTP 客户端
Pillow           # 已有，缩略图
openpyxl         # 已有，Excel 导出
```

- KML 解析不引入第三方库（`xml.etree` 即可，两步路 KML 结构固定，实测过）；如要兼容通用 KML 可换 `fastkml`。
- 逆地理编码封装为 `GeoProvider` 接口，配置项 `GEOCODER_PROVIDER=bigdatacloud|nominatim|amap` + `AMAP_API_KEY`，默认 bigdatacloud（免 Key）。
- 大文件与批量下载采用 `asyncio` + `httpx.AsyncClient`，后台任务用 FastAPI `BackgroundTasks` 起步；若后续要排队/重试，可平滑换 Celery/RQ（本期不做）。
- 配置项（写入 `core/config.py`）：`TRACK_UPLOAD_DIR`、`TRACK_MAX_UPLOAD_MB=50`、`TRACK_DOWNLOAD_CONCURRENCY=4`、`GEOCODER_*`。

## 6. 前端实现要点

新增页面 `/track`（路由 + 顶部导航入口，风格对齐现有页面）：

1. **上传区**：拖拽/选择 KML，显示解析进度条（阶段提示：解析中 → 下载照片 x/57 → 逆地理编码 x/57）。
2. **地图视图**（Leaflet，项目已有）：底图用天地图/OSM；轨迹 polyline + 起终点 marker；照片点用小图钉 marker，点击弹出 popup（缩略图 + 拍摄时间 + 语义地址 + 海拔/速度）。
3. **表格视图**（Element Plus `el-table`）：照片缩略图、拍摄时间、经纬度、海拔、速度、精度、省市区街道、POI、语义描述；支持按区县/POI 筛选。
4. **导出按钮**：Excel 汇总、ZIP 照片包、GeoJSON（可选，便于 GIS 软件使用）。
5. **历史记录页签**：已处理的 KML 列表，可重新打开查看/删除。

## 7. 与现有系统的结合点（可选项，本期可不做）

- **知识图谱**：照片语义地址（省/市/POI）可入库后作为「遗址点—地理位置」证据，未来挂到 Neo4j 图谱（`track_photo.省市区` 关联遗址公园所在行政区）。
- **遗址公园档案**：`track_file` 增加 `park_id` 外键，可把某次调研轨迹归档到具体公园，作为客流/到访路径数据。
- **AI 问答**：RAG 入口可检索照片语义描述（如"刘贺主墓调研拍过哪些点位"）。

## 8. 里程碑与工作量估算

| 阶段 | 内容 | 预估 |
|---|---|---|
| M1 后端解析链路 | 上传→解析→下载→逆地理→落库→status 接口 | 2 人日 |
| M2 导出 | xlsx（内嵌缩略图）+ zip | 0.5 人日 |
| M3 前端 | 上传、进度、地图、表格、导出 | 2 人日 |
| M4 联调验收 | 用刘贺主墓 KML 全流程验收 + 边界用例 | 0.5 人日 |

合计约 **5 人日**，单机 SQLite 模式即可跑通，无需新增基础设施。

## 9. 验收标准

1. 上传示例 KML（57 张照片），全流程自动完成，前端进度可视。
2. 57 张照片全部本地下载成功（任一失败有明确标记且不中断）。
3. 每张照片有逆地理语义地址与语义描述；抽样 10 张人工核对地址正确。
4. Excel 导出：缩略图 + 全部字段，记录数与照片数一致；ZIP 可正常解压。
5. 地图轨迹与照片点位与两步路 App 显示一致。
6. 服务重启后历史任务结果不丢失，可重新打开。
