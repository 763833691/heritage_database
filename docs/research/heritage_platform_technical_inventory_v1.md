# 国家考古遗址公园/文化遗产调研与语义化平台 — 技术资产盘点（v1）

> 盘点日期：2026-09-23
> 判定原则：**只依据当前仓库代码、数据库 Schema 与真实数据、配置文件、测试、运行脚本**。
> README 中的规划、TODO、设计文档、Mock 能力一律不计入"已实现"。
> 状态标记：`IMPLEMENTED`＝已有代码且能够实际运行；`PARTIAL`＝已有部分代码或原型；`PLANNED`＝仅存在设计/文档；`UNKNOWN`＝无法判断。
>
> 本报告中的数据来自对 `backend/data/heritage.db` 的直接查询、`backend/data/**` 落盘产物和本轮实跑测试。

---

## 一、总体技术架构

### 组件 → 技术 → 代码路径 → 当前状态

| 组件 | 技术/版本 | 代码路径 | 状态 |
|---|---|---|---|
| 前端 SPA | Vue 3.3.8、Vite 5、Pinia 2.1、vue-router 4.2、axios 1.6 | `frontend/src` | IMPLEMENTED |
| 前端 UI | Element Plus 2.4.3、@element-plus/icons-vue、lucide-vue-next | `frontend/src/components`、`views` | IMPLEMENTED |
| 图表 | ECharts 5.4.3 | `frontend/src/views/Dashboard.vue`、`Comparison.vue` | IMPLEMENTED |
| 3D 图谱 | Three.js 0.170、d3-force-3d 3.0.6 | `frontend/src/features/kg/graph3d` | IMPLEMENTED |
| 地图 GIS | @amap/amap-jsapi-loader 1.0.1（高德 JS API，**非 Leaflet**）+ WGS84↔GCJ-02 换算 | `frontend/src/features/map` | IMPLEMENTED |
| 后端 API | FastAPI 0.104.1、Uvicorn 0.24、Pydantic 2.5 | `backend/app` | IMPLEMENTED |
| ORM | SQLAlchemy 2.0.23（declarative） | `backend/app/models`、`app/core/database.py` | IMPLEMENTED |
| 数据库（默认） | SQLite 3.50，文件 `backend/data/heritage.db`（2,322,432 B） | `app/core/config.py:28-29` | IMPLEMENTED |
| 数据库（可选） | PostgreSQL 15-alpine（docker-compose） | `docker-compose.yml:5-22` | PARTIAL（配置就绪，未在真实运行验证） |
| PostGIS | 无任何代码/依赖/配置 | — | PLANNED |
| 图数据库 | Neo4j 5.14 驱动 + 5.0-community 容器；默认 `NEO4J_ENABLED=false`，实际落盘 JSON | `app/kg/services/graph_repository.py` | PARTIAL |
| 向量库 | ChromaDB 0.4.18（PersistentClient，2 个 collection） | `app/core/database.py:70-94` | PARTIAL |
| 本地向量检索 | jieba 0.42 + scikit-learn TF-IDF 余弦（**sklearn 未写入 requirements**） | `app/services/kb_indexer.py` | PARTIAL |
| KML 解析 | Python 标准库 `xml.etree.ElementTree` | `app/services/kml_service.py` | IMPLEMENTED |
| VLM 调用 | OpenAI 兼容 `/chat/completions` + base64 image_url（httpx + Pillow） | `app/services/vision_client.py` | IMPLEMENTED |
| 文本 LLM | `get_llm_provider`（OpenAI 兼容 / DashScope SDK / Mock） | `app/services/llm_provider.py` | IMPLEMENTED |
| 模型路由 | 任务名→模型别名（`text.chat`/`vision.describe`/`vision.ocr`），DB 优先+配置回退 | `app/core/model_router.py`、`app/models/ai_model.py` | IMPLEMENTED |
| RAG 问答 | 规则意图 + DB 查询 + 文献检索 + 可选 LLM，SSE | `app/services/rag_engine.py`、`app/api/chat.py` | PARTIAL |
| KG 子系统 | 文件库→文本解析→图谱构建→导出，本地 JSON 状态机 | `backend/app/kg` | IMPLEMENTED |
| OCR | pymupdf 渲染 + 视觉模型识别 | `app/kg/services/scanned_pdf_extractor.py` | PARTIAL |
| 语音转写 | 腾讯云 FlashRecognizer（HMAC-SHA1） | `app/kg/services/asr_service.py` | PARTIAL |
| 文件存储 | 本地文件系统（`data/tracks`、`data/kg`、`data/chroma`），DB 存路径 | `track_service.py`、`kg/services/file_service.py` | IMPLEMENTED |
| 后台工作流 | FastAPI BackgroundTasks + asyncio 管道（**无 LangGraph/通用 Agent Runtime**） | `api/track.py:129`、`track_service.py:845` | PARTIAL |
| 部署 | Docker Compose（postgres/neo4j/backend/frontend/nginx）+ `start.bat` | 根目录、`docker/` | IMPLEMENTED |
| CI/CD | 无 `.github/`、无 `.gitlab-ci.yml` | — | PLANNED |

**依赖声明与实际使用的偏差（真实发现）**：`requirements.txt` 声明 `langchain==0.0.350` 但全仓库无任何 `langchain` 引用；声明 `alembic` 但无迁移目录（建表用 `create_all`）；`kb_indexer` 使用 `sklearn`、`doc_parser` 使用 `PyPDF2`，二者均未在 requirements 中声明（当前 Anaconda 环境恰好可用）。README 写"Leaflet / PostgreSQL 主库"，实际前端用高德、默认库是 SQLite。

---

## 二、数据库真实情况

- **实际数据库**：SQLite 3.50.3，文件 `backend/data/heritage.db`（另有 2026-09-20 备份）。PostgreSQL 15 仅在 Docker 配置中可选。
- **ORM/驱动**：SQLAlchemy 2.0.23；驱动 `sqlite3` / `psycopg2-binary 2.9.9`。
- **是否使用 PostGIS / MySQL / Neo4j**：PostGIS＝否；MySQL＝否；SQLite＝是（默认）；PostgreSQL＝可选；Neo4j＝驱动与容器就绪但默认关闭、真实图谱以 JSON 落盘。
- **迁移**：无 Alembic 版本目录；由 `Base.metadata.create_all` + `scripts/init_db.py` 建表与播种。

### 核心数据表、用途与关键字段

| 表 | 行数 | 用途 | 关键字段 |
|---|---:|---|---|
| `parks` | 15 | 遗址公园主数据 | name, park_type, province, city, longitude/latitude(Float), total_area, batch |
| `sites` | 0 | 遗址点 | park_id FK, site_name, coordinates(Text 声明 GeoJSON) |
| `locations` | 0 | 城市/经济/交通 | park_id FK(unique), nearby_facilities(Text JSON) |
| `exhibitions` | 0 | 展示设施 | park_id FK(unique), digital_projects(Text) |
| `indicators` | 27 | D1–D27 指标 | code(unique), dimension, sub_dimension, weight_urban/suburb/rural |
| `scores` | 179 | 评分 | park_id FK, indicator_id FK, normalized_score, grade, evidence |
| `surveys` | 8 | 问卷汇总（1-4 与 5-8 完全重复，种子数据） | park_id FK, total_distributed, valid_count |
| `survey_answers` | 0 | 问卷逐题 | survey_id FK, question_code, answer_value |
| `survey_tasks` | 15 | 调研任务 | title, park_id FK(可空), status(draft/processing/review/ready) |
| `survey_events` | 1028 | 语义化调研事件 | task_id FK, timestamp, lon/lat, address, title, content, source_material_id, tags(Text JSON), usable_for_report |
| `survey_report` | 0 | 报告实例（第二章） | task_id+chapter(unique), content(Text JSON), docx_path, status |
| `track_file` | 14 | KML 上传与状态 | original_name, kml_path, geojson_path, survey_task_id FK, status/stage, track_point_count, photo_count, distance_meters, start/end_time, start/end_address |
| `track_photo` | 1028 | 照片点+语义 | track_id FK, seq, file_path/thumb_path/source_url, shot_time, lon/lat/altitude/speed/accuracy, province/city/district/street/poi/address, description(Text), caption, tags(Text JSON), download_status, describe_status |
| `literatures` | 8 | 文献元数据 | title, authors/keywords/raw_metadata(Text JSON), methodology, core_argument, vector_id |
| `citations` | 0 | 文献引用 | source_id FK, target_title, target_id FK |
| `lit_relations` | 18 | 文献语义关系 | source_id/target_id FK, relation_type, strength |
| `ai_model` | 9 | 模型注册表 | alias(unique), provider_type, capability, base_url, model, api_key_encrypted, api_key_env, input/output_modalities(**JSON**), enabled, is_preset |
| `ai_model_route` | 3 | 任务→模型路由 | task(unique), model_id FK(cascade) |
| `reviews` | 0 | 游客评论情感 | platform, rating, sentiment_score/label |
| `education_activities` | 0 | 教育活动 | park_id FK, participant_count |
| `communities` | 0 | 社区共建 | park_id FK, volunteer_count |
| `users` | 1 | 用户 | username/email(unique), hashed_password, role |

- **JSON/JSONB 字段**：仅 `ai_model.input_modalities`、`ai_model.output_modalities` 使用 SQLAlchemy `JSON` 类型。其余 JSON 数据（tags、keywords、authors、raw_metadata、report content）以 `TEXT` 存字符串。
- **Geometry/经纬度字段**：`parks.longitude/latitude`、`track_photo.longitude/latitude/altitude`、`survey_events.longitude/latitude` 均为普通 `FLOAT`；`sites.coordinates` 为 `TEXT`（0 行）。**无 GEOMETRY/GEOGRAPHY 列，无空间索引**。
- **索引/外键**：各表主键 index；外键与过滤列建索引（`track_photo.track_id`、`track_file.status/survey_task_id`、`survey_events.task_id/event_type/timestamp`、`scores.park_id/indicator_id`、`literatures.year`、`ai_model_route.task` 等，共 50+ 条）。外键链见 JSON 清单。
- **实体关系数据存储方式**：主业务关系用关系库外键；知识图谱关系**不在关系库**，而在 `backend/data/kg/graph.json`（或可选 Neo4j）中。

### 可验证的真实统计

| 指标 | 数量 |
|---|---:|
| 遗址公园 | 15 |
| 轨迹（KML） | 14 |
| 轨迹点合计 | 10,004 |
| 照片 | 1,028（下载成功 1,028） |
| 照片语义成功 | 1,014（失败 14，成功率 98.6%） |
| 有语义描述/图注的照片 | 1,028 |
| 有语义地址的照片 | 1,027 |
| 语义标注记录（survey_events） | 1,028 |
| 照片去重标签 | 1,121 |
| 已持久化分析结果 | 14 份 analysis.json |
| 文献 | 8（原始 PDF 8 篇） |
| 文献关系 | 18（citations 0） |
| 问卷汇总 | 8（含 4 条重复） |
| 问卷逐题/评论/遗址点/活动 | 0 |
| 评分 | 179（覆盖 8 个公园） |
| 知识图谱实体/关系 | 19 / 114 |

> 说明：`surveys` 1–4 与 5–8 数值完全相同，属 `init_db.py` 种子数据；`scores` 覆盖公园 1、2、3、5、6、7、8、9。以上均为可查询验证值，未做估计。

---

## 三、KML 轨迹处理流水线

| 问题 | 结论 |
|---|---|
| 1. 解析库 | Python 标准库 `xml.etree.ElementTree`，命名空间"本地名匹配"通配，**未引入任何第三方 KML 库** |
| 2. 支持结构 | `gx:Track`（`when`+`gx:coord`）、`LineString/coordinates`、`Placemark/Point/coordinates`、`ExtendedData`（`Data`/`SimpleData`）、旧版 description 内嵌 div、`TimeStamp/when` |
| 3. 提取字段 | 轨迹点：time/lon/lat/alt；照片点：lon/lat/alt/shot_time/speed/accuracy/url/file_name/name |
| 4. 经纬度解析 | `coordinates` 为 `lon,lat[,alt]`；`gx:coord` 为空格分隔 `lon lat alt`；坐标三级回退 Point→ExtendedData→description 正则 |
| 5. 时间戳解析 | 13 位毫秒 epoch、ISO8601（`Z` 转 `Asia/Shanghai` 后去 tzinfo）、6 种 `strptime` 格式；三级回退 |
| 6. 坐标系 | WGS84（前端展示时经 `coordinates.js` 转 GCJ-02 供高德使用） |
| 7. GeoJSON | 是。写 `data/tracks/{id}/track.geojson`（LineString + 起终点 Point） |
| 8. 入库 | 写 `track_file`（点数/照片数/里程/起止时间/起终点地址）与 `track_photo`（按 `seq` 幂等 upsert） |
| 9. 异常轨迹 | 单照片失败仅置该项 `failed`，不中断；整条异常置 `status=failed`；重启时 `recover_interrupted_tracks()` 将未终态标记 failed 供重试 |
| 10. 测试 | 有：`test_parse_two_step_kml`、`test_parse_old_format_kml_photo`、`test_parse_new_format_kml_photo` |

- **代码路径**：`backend/app/services/kml_service.py`
- **核心函数/类**：`parse_kml_bytes`、`parse_kml_file`、`_parse_gx_tracks`、`_parse_linestrings`、`_parse_photo_placemarks`、`parse_datetime`、`TrackPoint`、`PhotoPoint`、`KmlParseResult`
- **输入→输出**：KML `bytes` → `KmlParseResult(name, points[], photos[])`
- **真实样例**：`tongwancheng.kml` → track_id=1，轨迹点 1,207，照片 43，里程 13,583.2 m，起止 2026-07-30 09:08–10:49。

---

## 四、轨迹—照片自动空间关联

1. **照片空间信息从哪来**：来自 **KML Placemark 自带坐标**（Point / ExtendedData / description）。**未解析 EXIF GPS，未使用文件名推断位置，未使用人工标注定位**。全仓库 grep 无 `exif`/`_getexif`。
2. **如何与轨迹关联**：同一 KML 内按 `seq` 顺序**直接绑定**到 `track_file`（`track_id`+`seq`）；照片坐标与轨迹点坐标各自独立。
3. **最近邻？** 既不是时间最近邻，也不是空间最近邻——**无匹配算法，直接绑定**。
4. **是否同时用时间与距离？** 绑定阶段不用；仅在"停留簇"划分阶段同时用时间差与距离。
5. **阈值**：绑定无阈值；簇切分阈值 时间差 > 5 分钟 或 间距 > 150 米。
6. **插值**：无。
7. **无法匹配时**：无坐标且无 URL 的 Placemark 直接跳过；无 URL 记 `skipped`；下载失败记 `failed` 并保留 error_message。
8. **confidence**：无 `confidence` 字段。
9. **人工校核**：仅在 `survey_events` 层支持改标题/正文/标签/可用性；**不回写** `track_photo` 语义字段。
10. **准确率**：**当前未形成量化准确率**（无人工核验数据集、无评估代码）。

---

## 五、停留簇与轨迹行为算法

- **是否实现停留点/簇识别**：是（`IMPLEMENTED`）。
- **算法**：按拍摄顺序扫描 + 时间差/间距阈值切簇；**不是** DBSCAN / 时空 DBSCAN / KMeans。
- **阈值**：距离 150 m、时间 5 min。
- **输入字段**：`shot_time`、`longitude`、`latitude`、`seq`。
- **输出字段**：`cluster`、`count`、`time_start/end`、`stay_minutes`、`composition`、`center_lat/lon`。
- **关键节点识别**：无独立关键节点检测；以"点位簇 + 停留时长 + 语义构成"作为行为代理指标。
- **跨遗址比较**：已实现，`GET /api/track/analysis/compare?ids=...`。
- **代码位置**：`backend/app/services/semantic_analysis.py:87-113`（`cluster_photos`）、`analyze_track`、`compare_tracks`。
- **真实输出**：14 条轨迹全部生成 `analysis.json`。例：track 13 隋唐洛阳城 110 张照片 → 16 个簇；track 7 鸿山 140 张照片 → 2 个簇；track 10 南旺 21 张照片 → 2 个簇。

---

## 六、照片多模态语义化 Pipeline

```text
Input Image (KML 内嵌 URL)
  → 解析坐标/时间 (kml_service)
  → 下载 (SSRF 防护 + 重试 + 缩略图)
  → 逆地理编码 (bigdatacloud/nominatim + 本地缓存)
  → VLM 多模态描述 (vision_client.describe_image)
  → 结构化解析 (parse_vision_result，JSON 优先/正则兜底)
  → 降级模板 (fallback_vision_result)
  → 生成调研事件 (survey_events)
  → 人工审核 (survey_events PATCH)
  → A–F 语义分类与簇分析 (semantic_analysis)
  → 数据库
```

| 问题 | 结论 |
|---|---|
| 1. 实际调用的 VLM | `doubao-seed-2-0-mini-260428`（`ai_model_route.vision.describe`） |
| 2. Provider | volcengine 火山方舟（OpenAI 兼容 `ark.cn-beijing.volces.com/api/v3`） |
| 3. 模型版本 | `doubao-seed-2-0-mini-260428`；文本 `text.chat` = `doubao-seed-2-1-pro-260628` |
| 4. Prompt 位置 | `backend/app/services/track_service.py:40-51` `PHOTO_PROMPT`（代码内联，非独立文件） |
| 5. 输出 JSON Schema | `{"description": "2-4句画面描述", "caption": "≤20字图注", "tags": ["主题标签"]}` |
| 6. 提取的语义字段 | 仅 `description`（自由文本）、`caption`（自由文本）、`tags`（松散标签）三项 |
| 7. 是否结构化识别 | 遗址对象/展示设施/场景类型/展示方式/空间环境/文化内容 **均无独立字段**；仅隐含于自由描述、tags，以及事后的 A–F 关键词归类（PARTIAL） |
| 8. confidence | 无 |
| 9. 人工修改 | 支持，在 `survey_events` 层（title/content/tags/usable_for_report） |
| 10. 修改回写 | 写回 `survey_events`；**不回写** `track_photo` |
| 11. 失败重试 | 下载每张重试 2 次；描述失败置 failed 并写降级模板；`POST /api/track/{id}/retry?force_describe=true` 全量重跑；服务重启自动恢复中断任务 |
| 12. 真实处理量 | **1,028 张**，语义成功 **1,014**，失败 14（98.6%） |

**失败原因（真实）**：读超时 6 张、`cannot identify image file` 7 张、早期 401 鉴权 7 张（修复后重跑成功，但 `error_message` 未清空，属数据清理瑕疵）。

**脱敏真实输出样例**（photo_id=1，统万城，`describe_status=success`）：

```json
{
  "photo_id": 1,
  "track_id": 1,
  "file_name": "1658655578",
  "shot_time": "2026-07-30 09:08:06",
  "longitude": 108.851442,
  "latitude": 37.984855,
  "province": "陕西省",
  "city": "榆林市",
  "address": "陕西省榆林市亚洲",
  "description": "画面主体为放置在入口瓷砖地面上的立式金属展架公示牌……该公示牌为统万城遗址博物馆文物安全直接责任公示牌，牌面清晰列明博物馆名称、管理单位、安全责任人、管理人、行政主管部门信息及对应联系、监督举报电话。",
  "caption": "统万城遗址博物馆文物安全责任公示牌",
  "tags": ["统万城遗址博物馆", "文物安全", "责任公示", "文保管理", "田野调研"],
  "describe_status": "success"
}
```

---

## 七、知识图谱

- **实体类型（真实）**：`place`、`person`、`event`、`concept`、`file`（声明类型仅前 4 类）。
- **关系类型（真实）**：`CONTAINS`、`相关`、`包含`、`位于`、`属于`、`连接`、`起点`、`扩建`（共 8 种，其中 84/114 条为 `CONTAINS`）。
- **属性**：实体 id/label/name/type/description/source_file；关系 id/source/target/label/weight。
- **数据来源**：`backend/data/kg/uploads` 下 **7 份内容完全相同的示例文本《大明宫资料.txt》**（5 句合成文本）。
- **存储方式**：本地 JSON `graph.json`；`NEO4J_ENABLED=true` 时写 Neo4j（`File`/`Entity`，`CONTAINS`/`RELATED_TO`）。
- **Ontology**：无。**CIDOC CRM**：无。**GIS 空间关系**：无（图中无坐标）。**证据来源**：仅文件级 `source_file`，无句级证据。**实体去重/Entity Linking**：仅按实体名 `sha1` 生成 id（同名合并），无消歧。
- **图查询**：`GET /api/graph/full`、`/api/graph/node/{id}`、`/api/graph/search`、`POST /api/nlp/extract`、`GET /api/kg/*`。
- **前端图谱展示**：有，`KnowledgeGraph.vue` + Three.js 3D（J-space 点云 / Jarvis 主题、四种布局）。

**真实统计**：`entity_count=19`，`relation_count=114`，`entity_type_count=5`，`relation_type_count=8`。

**真实小图谱示例**（均来自 graph.json，非虚构）：

```text
大明宫 --包含--> 含元殿
大明宫 --位于--> 长安城
大明宫 --属于--> 唐代
大明宫 --包含--> 宣政殿
丝绸之路 --起点--> 长安
丝绸之路 --连接--> 西域
```

> 注意：仓库中**不存在** `belongs_to` / `located_at` / `supported_by` 关系标签；"含元殿"与"大明宫"的真实关系是 `包含`。

---

## 八、语义世界模型（SWM）能力核查

对以下概念全仓库检索（代码 + Markdown）：**均无任何实现或设计落地**。

| 概念 | 判定 | 依据 |
|---|---|---|
| SemanticObject | PLANNED | 无该类/表/字段；最近似为 `track_photo` 语义描述与 `survey_events` |
| SemanticRelation | PLANNED | KG 有 relation，但非 SWM 语义关系模型 |
| SemanticState | PLANNED | 无 |
| SemanticAction | PLANNED | 无 |
| EvidenceBinding | PLANNED | 无证据绑定表；仅 KG `source_file` 与报告 `[EV:{id}]` 引用 |
| FeedbackEvent | PLANNED | 无；`survey_events` 人工编辑是最近似交互，但不构成反馈事件流 |
| Capability | PLANNED | 无 |
| WorkflowRun | PLANNED | 无持久化运行记录；仅 `track_file.status/stage` 与 `file_state.workflow_phase` |
| NodeRun | PLANNED | 无 |
| WorldState | PLANNED | 无 |
| Snapshot | PLANNED | 无 |

**关键确认**：
- Action 执行后**不会**改变 State（无 State 模型）。
- WorkflowRun 结束后**不会**回写语义状态（无语义状态）。
- Evidence **不可**语义级追溯（仅材料级 `source_material_id` + 报告引用标记）。
- Feedback **不会**进入系统（无反馈事件表/闭环）。

---

## 九、Agent 与工作流

**当前真实可运行的工作流**：

| 工作流 | Input | Nodes | Models | Output | DB 写入 | 失败处理 |
|---|---|---|---|---|---|---|
| KML 照片语义化 | KML ≤50MB | parsing→downloading→geocoding→describing→event | doubao VLM | track/photo/events/analysis/geojson | 是 | 逐项隔离+重试+重启恢复 |
| 文本解析→图谱→导出 | PDF/CAJ/TXT | text_parse→confirm→graph_build→export | LLM(可选)/OCR | state.json/graph.json/export | 否(本地 JSON) | 阶段 failed+恢复 |
| 报告第二章生成 | events+轨迹统计 | 事件整理→LLM 正文→图注→docx | text.chat | survey_report + docx | 是 | LLM 失败落模板 |
| 事件批量标题 | 任务事件 | 主题→LLM→回写 | text.chat | events.title | 是 | 502 |
| RAG 问答 | 问题 | 意图→DB→文献检索→生成 | text.chat | answer/sources/chart(SSE) | 否 | 落模板 |
| 文献元数据+关系 | 文献文件 | 抽取→LLM→引文/关系→索引 | text.chat | literatures/citations/lit_relations | 是 | 正则优先+LLM 兜底 |
| 语音转写 | mp3/m4a | 签名→腾讯云 | 腾讯 ASR | 文本 | 否 | 明确错误码 |

**统一性核查**：
- 统一 LLM Client：**PARTIAL**（`llm_provider` 统一文本；`nlp_extractor._llm_extract` 直接用 openai SDK，绕过路由）。
- Tool Calling：**无**。RAG：**PARTIAL**（规则意图 + TF-IDF/关键词）。向量检索：**PARTIAL**（ChromaDB 已初始化，embedding 模型未就绪时回退 sklearn TF-IDF）。
- Agent Planner：**无**。运行日志：**PARTIAL**（阶段日志只有 KG state.json / track progress，无通用日志）。
- WorkflowRun / NodeRun 持久化：**无**。

---

## 十、AI 算法资产（仅列已有代码者）

| 算法/模型 | 用途 | 输入 | 输出 | 代码路径 | 状态 | 有测试 |
|---|---|---|---|---|---|---|
| VLM 图像语义描述 | 照片 description/caption/tags | JPEG+prompt | JSON 文本 | `services/vision_client.py` | IMPLEMENTED | 是 |
| 文本 LLM 生成/抽取 | 报告/标题/文献/KG/问答 | messages | text/JSON | `services/llm_provider.py` | IMPLEMENTED | 是 |
| 模型路由 | 按任务分配模型 | task | ResolvedModel | `core/model_router.py` | IMPLEMENTED | 是 |
| TF-IDF+jieba 检索 | 文献语义搜索 | query | top-N+相似度 | `services/kb_indexer.py` | PARTIAL | 否 |
| 词典+规则实体/关系抽取 | KG 抽取 | text | entities/relations | `kg/services/nlp_extractor.py` | IMPLEMENTED | 是 |
| LLM 实体关系抽取(可选) | KG 增强 | text | JSON | `nlp_extractor.py:_llm_extract` | PARTIAL | 否 |
| 关键词编码分类 A–F | 照片语义归类 | 文本 | A–F/G | `services/semantic_analysis.py` | IMPLEMENTED | 是 |
| 停留簇切分 | 行为代理指标 | time/坐标 | clusters | `semantic_analysis.cluster_photos` | IMPLEMENTED | 是 |
| Haversine 距离/里程 | 里程与簇间距 | lat/lon | 米 | `track_service`、`semantic_analysis` | IMPLEMENTED | 是 |
| WGS84↔GCJ-02 | 地图纠偏 | lng/lat | lng/lat | `frontend/src/features/map/coordinates.js` | IMPLEMENTED | 是 |
| 逆地理编码 | 语义地址 | lat/lon | 省市区街道POI | `track_service.geocode` | IMPLEMENTED | 否 |
| Embedding 专用模型 / Reranker / 通用 NER / 图文对齐 / 多模态对齐 / 空间编码与轨迹深度学习 | — | — | — | — | PLANNED | — |

### 附：核心后端 API

| Method | Route | Purpose | 状态 |
|---|---|---|---|
| POST | `/api/track/upload` | KML 上传并异步处理 | IMPLEMENTED |
| GET | `/api/track/{id}` | 轨迹 GeoJSON + 照片语义点 | IMPLEMENTED |
| POST | `/api/track/{id}/retry` | 重试 / 强制重描述 | IMPLEMENTED |
| POST | `/api/track/{id}/analyze` | A–F 编码 + 簇分析并持久化 | IMPLEMENTED |
| GET | `/api/track/{id}/analysis` / `.csv` | 分析读取 / CSV 导出 | IMPLEMENTED |
| GET | `/api/track/analysis/compare` | 跨轨迹（跨公园）比较 | IMPLEMENTED |
| GET | `/api/track/{id}/export.xlsx / .zip` | 照片汇总导出 | IMPLEMENTED |
| — | 独立"照片上传"接口 | 不存在（照片仅来自 KML） | PLANNED |
| PATCH | `/api/survey/events/{id}` | 人工审核事件 | IMPLEMENTED |
| POST | `/api/survey/tasks/{id}/events/auto-title` | LLM 批量标题 | IMPLEMENTED |
| POST | `/api/survey/tasks/{id}/report/chapter2` | 生成报告第二章 | IMPLEMENTED |
| POST | `/api/file/upload` | 文件库上传 | IMPLEMENTED |
| POST | `/api/process/{file_id}/graph-build/run` | 图谱构建 | IMPLEMENTED |
| POST | `/api/nlp/extract` | 实体关系抽取 | IMPLEMENTED |
| GET | `/api/graph/full|node/{id}|search` | 图谱查询 | IMPLEMENTED |
| GET | `/api/kg/stats|entity|neighbors|search` | 关系库图谱查询 | PARTIAL |
| POST | `/api/chat` `/api/chat/stream` | RAG 问答 | IMPLEMENTED |
| GET | `/api/statistics/overview|comparison|dimension|radar/{id}` | 统计/对比 | IMPLEMENTED |
| POST | `/api/knowledge/upload` / `GET /search` | 文献上传/检索 | IMPLEMENTED |
| POST | `/api/asr/transcribe` | 语音转写 | PARTIAL |
| GET/PUT | `/api/ai/models|routes|tasks|status` | 模型路由管理 | IMPLEMENTED |
| POST | `/api/admin/import/*` / `/upload/report` | 数据导入 / 报告解析 | PARTIAL |

（后端共约 123 个路由装饰器，覆盖 `/api` 与 KG 子系统。）

---

## 十一、测试与性能

| 层 | 框架 | 用例/运行 | 结果 | 命令 |
|---|---|---:|---|---|
| 后端 | pytest 8.4.2 | 5 文件 54 用例 | **54 passed / 0 failed** | `cd backend && py -m pytest tests -q` |
| 前端单元 | Vitest 4.1.10 | 1 文件 2 用例 | **2 passed / 0 failed** | `cd frontend && npm test` |
| E2E | Playwright 1.61（桌面+移动） | 6 用例 × 2 = 12 运行 | **9 passed / 3 failed** | `cd frontend && npx playwright test` |
| CI | — | — | 无 CI 配置 | — |

后端用例分布：`test_ai_model_router.py` 14、`test_semantic_analysis.py` 13、`test_track.py` 11、`test_model_router.py` 10、`test_kg_system.py` 6。

**E2E 已知失败项**（本轮实跑）：
1. `[desktop] 地图明确展示真实服务或配置错误状态`（高德容器未就绪且降级文案未出现，与环境/地图服务可用性相关）
2. `[mobile] 地图明确展示真实服务或配置错误状态`（同上）
3. `[mobile] 研究工具和管理页均无全局侧栏`

**性能信息**：**仓库无任何性能基准/计时埋点**。因此：KML 解析耗时、100/1000 张照片处理耗时、VLM 单次调用耗时、接口响应时间 **均无数据，不做推测**。唯一可验证的效率指标是语义化成功率 **1,014/1,028 = 98.6%**（真实数据统计）。

---

## 十二、数据资产清单（按遗址公园）

`trajectory_count` 按 `survey_task.park_id` 关联统计；`gis_count` 取该园照片地理点数。

| site_name | trajectory_count | trajectory_points | photo_count | semantic_photo_count | gis_count | document_count | questionnaire_count | review_count |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 统万城国家考古遗址公园 | 1 | 1207 | 43 | 36 | 43 | 0 | 0 | 0 |
| 殷墟国家考古遗址公园 | 2 | 1537 | 100 | 100 | 100 | 0 | 2 | 0 |
| 良渚国家考古遗址公园 | 2 | 630 | 122 | 121 | 122 | 0 | 0 | 0 |
| 南昌汉代海昏侯国国家考古遗址公园 | 2 | 420 | 143 | 143 | 143 | 0 | 0 | 0 |
| 鸿山国家考古遗址公园 | 2 | 516 | 187 | 181 | 187 | 0 | 0 | 0 |
| 大运河南旺枢纽国家考古遗址公园 | 2 | 753 | 99 | 99 | 99 | 0 | 0 | 0 |
| 鲁国故城国家考古遗址公园 | 1 | 1354 | 78 | 78 | 78 | 0 | 0 | 0 |
| 隋唐洛阳城国家考古遗址公园 | 1 | 1748 | 110 | 110 | 110 | 0 | 2 | 0 |
| 西夏陵国家考古遗址公园 | 1 | 1839 | 146 | 146 | 146 | 0 | 0 | 0 |
| 圆明园国家考古遗址公园 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 |
| 汉长安城未央宫国家考古遗址公园 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 杜陵国家考古遗址公园 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 |
| 周口店国家考古遗址公园 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 屈家岭国家考古遗址公园 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| **合计** | **14** | **10004** | **1028** | **1014** | **1028** | **8（文献库）** | **8（含重复）** | **0** |

### 大明宫国家考古遗址公园（单独统计）

| 指标 | 值 |
|---|---:|
| trajectory_count | **0** |
| trajectory_points | **0** |
| photo_count | **0** |
| semantic_photo_count | **0** |
| gis_count | **0** |
| scores | 27 |
| document_count | 0（KG 示例文本《大明宫资料.txt》不计入文献库） |
| questionnaire_count | 0 |
| review_count | 0 |
| KG 相关实体 | 大明宫、含元殿、宣政殿、唐长安城、长安城、唐高宗等（示例图） |

> 结论：**大明宫在本平台中当前没有田野 KML/照片/语义事件数据**，仅有 27 条评估评分和由 7 份合成示例文本构建的示例知识图谱。

---

## 十三、可作为申报材料的截图清单

> 本盘点工具**不具备浏览器截图能力**，未生成本次新截图。已存在的历史截图位于 `docs/heritage-portal-ui/screenshots/`（14 张桌面/移动页面）与 `docs/前端修改/`、`docs/audit-joinquant-2026-07-21/`、`docs/design-refinement-2026-07-21/`。已建立目录 `docs/research/evidence/screenshots/` 供后续补充。

| # | 建议截图页面 | 运行路径 |
|---|---|---|
| 1 | 数据管理平台 | `/data-management` |
| 2 | KML 轨迹地图 + 照片点 | `/survey` → 任务 → `/survey/{id}`（调研工作台） |
| 3 | 轨迹—照片空间关联（地图+时间线） | `/survey/{id}` 时间线视图 |
| 4 | 照片 AI 语义标注（描述/图注/标签） | `/survey/{id}` 事件卡片 / 分析面板 |
| 5 | 人工审核（编辑标题/正文/标签） | `/survey/{id}` 时间线编辑 |
| 6 | 知识图谱（3D） | `/knowledge-graph` |
| 7 | GIS/空间数据 | `/map` |
| 8 | 跨园分析 | `/survey/{id}` → 跨轨迹比较（`/api/track/analysis/compare`） |
| 9 | 工作流/Agent | `/kg/processing`（文本解析→图谱构建→导出） |
| 10 | 实际输出结果 | 轨迹 `export.xlsx` / `analysis.csv`、报告 `report.docx`、`data/kg/exports/.../knowledge_graph.json` |

---

## 十四、"已有基础 — 下一步研究"差距表

| 已有能力 | 当前成熟度 | 证据 | 本项目下一步新增能力 |
|---|---|---|---|
| 多模态照片语义化 | IMPLEMENTED | 1,028 张真实照片、1,014 成功；`vision_client`+`track_service`+测试 | 从单照片语义标注升级到 **World State Encoder** |
| KML 轨迹解析与 GeoJSON | IMPLEMENTED | 14 条真实轨迹、10,004 点；`kml_service`+测试 | 轨迹时空特征向量化，支撑游客状态建模 |
| 轨迹停留簇与跨园比较 | IMPLEMENTED | `cluster_photos`(5min/150m)、compare API、14 份 analysis.json | 引入时空聚类与关键节点识别 |
| 知识图谱（文件驱动） | PARTIAL | 规则/词典抽取、19 节点/114 边示例图、3D 展示 | 升级为显式世界状态 Gt，接入 GIS 空间关系与句级证据溯源 |
| Agent 工作流 | PARTIAL | BackgroundTasks 管道 + 阶段状态机，无 Tool Calling/Planner/Run 记录 | 接入 **Critic** 与 **World Model Planner** |
| 统一 LLM/模型路由 | IMPLEMENTED | `model_router` + 9 模型 3 路由 + 14 项测试 | 扩展为多智能体模型编排 |
| RAG 问答 | PARTIAL | 规则意图 + TF-IDF/关键词，无真向量 embedding | World Model 检索增强 |
| 人工审核闭环 | PARTIAL | `survey_events` 编辑 + 重跑保留（有测试） | 反馈进入 World Model 闭环学习 |
| 问卷/评论/遗址点数据 | PLANNED（表存在 0 行） | `survey_answers`/`reviews`/`sites` 均 0 行 | 采集真实游客数据构建 (St, At, St+1) 数据集 |

### 目前尚未实现的核心能力（**不得写成已有成果**）

- Visitor Cognitive State（游客认知状态）
- (St, At, St+1) 干预数据集
- Action-conditioned Transition Model（动作条件转移模型）
- JEPA 式预测模型
- Fast Critic
- Model-based Planner
- World Model 闭环反馈学习

---

## 十五、项目现有技术基础总结（用于陕西省重点研发计划申报书，≤1500 字）

本项目已建成一套面向国家考古遗址公园调研、语义化与知识组织的可运行一体化平台原型，具备真实数据基础与工程闭环，而非仅有设计蓝图。

**数据与平台基础。** 平台采用 Vue 3 + Element Plus 前端、FastAPI + SQLAlchemy 后端、默认 SQLite（可选 PostgreSQL）与本地文件存储，支持 Docker Compose 与本地一键启动。数据库已定义 parks、sites、scores、surveys、survey_events、track_file、track_photo、literatures、ai_model 等 21 张表；知识图谱与模型路由相关表、索引、外键齐备。现网真实数据包括：15 个国家考古遗址公园、14 条实际田野 KML 轨迹、10,004 个轨迹点、1,028 张现场照片、1,028 条语义化调研事件、179 条评估评分、8 篇文献与 18 条文献关系；其中 1,014 张照片由多模态模型完成语义标注（成功率 98.6%），覆盖统万城、殷墟、良渚、海昏侯、鸿山、南旺、鲁国故城、隋唐洛阳城、西夏陵等 9 处遗址公园。

**已实现的关键技术能力。** 一是 KML 轨迹处理流水线：以标准库解析两步路 gx:Track/LineString/Placemark，完成经纬度与时间戳多级解析、GeoJSON 生成、里程计算、入库与失败恢复；二是照片语义化流水线：公网安全下载、逆地理编码、VLM 图像理解、结构化 JSON 解析、降级模板与重试恢复，并生成调研事件时间线；三是轨迹—照片分析与停留簇算法：以 5 分钟/150 米阈值切分点位簇，输出语义类型构成、拍摄密度、停留时长与跨园比较；四是知识图谱子系统："文件库→文本解析（含 PDF/CAJ/OCR）→规则与可选 LLM 实体关系抽取→图谱构建→3D 展示→导出"全流程可运行，图谱具备实体与关系类型、权重与文件级来源；五是统一 AI 模型路由与多模型接入：已注册 9 个模型、3 条任务路由，支持文本/视觉分离与在线切换；六是 RAG 问答、报告第二章自动生成（带 [EV:id] 引用）、文献元数据抽取与文献关系发现、腾讯云语音转写等应用能力，并有 54 项后端测试、2 项前端单元测试与 12 项 E2E 运行验证。

**当前边界（客观陈述）。** 平台目前是"感知—标注—组织—展示"的数字化基础，尚未形成世界模型闭环：照片语义仍以自由文本+标签为主，无结构化语义对象与置信度；知识图谱规模小、为文件驱动、无本体与句级证据溯源；无人机反馈事件流，无 WorkflowRun/NodeRun 运行记录，无 Tool Calling 与 Planner；问卷、评论、遗址点等表为空，缺少真实游客行为数据。Visitor Cognitive State、(St, At, St+1) 干预数据集、Action-conditioned Transition Model、JEPA 式预测模型、Fast Critic、Model-based Planner 与 World Model 闭环反馈学习均尚未实现。

**下一步研究定位。** 本平台可直接作为"世界模型"研究的真实数据底座与语义感知层：依托已积累的 KML 轨迹、照片多模态语义、GIS 空间关系与知识图谱，构建显式的世界状态编码器与世界状态 Gt，采集游客认知状态与干预数据，训练动作条件转移模型与预测模型，引入 Fast Critic 与 Model-based Planner，实现从"语义标注平台"到"可预测、可干预、可反馈的文化遗产游客行为世界模型"的升级，为遗址公园保护展示利用提供智能决策支撑。

---

### 附：证据可复现命令

```powershell
# 后端测试（54 通过）
cd backend; py -m pytest tests -q
# 前端单元测试（2 通过）
cd frontend; npm test
# E2E（12 运行 / 9 通过 / 3 失败）
cd backend; py -m uvicorn app.main:app --port 8001   # 另开窗口
cd frontend; npx playwright test
# 数据库真实统计
py -c "import sqlite3;c=sqlite3.connect(r'backend/data/heritage.db');print(c.execute('select count(*) from track_photo').fetchone())"
```
