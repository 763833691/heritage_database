# VSCode AI 开发指令：田野调研 MVP（S1~S4）

> 用法：把本文件全文粘贴给 VSCode 的 AI 编程助手（Copilot Agent / Cursor / Continue 等），让它在本仓库（H:\my_code\datak）内执行。
> 开始前必须先读两份设计文档：`docs/07-两步路KML照片提取方案.md` 和 `docs/08-田野调研语义化与报告生成工作流.md`（尤其第 5、5.2、8 节）。

---

## 角色

你是本仓库（FastAPI + Vue 3 的「国家考古遗址公园调研数据平台」）的全栈开发。现在要实现「田野调研」功能的 MVP：上传两步路 KML → 下载轨迹照片 → 逆地理编码 → 多模态模型生成照片语义描述 → 组织为调研事件 → 自动生成报告「调研过程」章节并导出 docx。

## 铁律（不可违反）

1. **不新建平行系统**：AI 能力只复用/下沉到现有三个 service——语音 `backend/app/kg/services/asr_service.py`、文本 LLM `backend/app/services/llm_provider.py`、视觉调用 `backend/app/kg/services/scanned_pdf_extractor.py`（OpenAI 兼容 `/chat/completions` + `image_url`，base_url/key/model 从 `app/core/config.py` 的 `settings.openai_base_url` / `openai_api_key` / `openai_vision_model` 读）。不引入第二个向量库、第二套知识库存储。
2. **不破坏现有功能**：所有改动为新增文件 + 最小侵入式注册（路由、导航、配置项），不得修改现有接口行为。KG 子系统、RAG、ASR 现有代码一行不动，视觉公共模块只能从 `scanned_pdf_extractor.py` 中**抽取复制**出新文件，原文件保持不变。
3. **依赖最小化**：后端只允许使用 `requirements.txt` 中已有的包（httpx、pandas、openpyxl、Pillow、python-docx、SQLAlchemy 等）。KML 解析用标准库 `xml.etree.ElementTree`，不引第三方 KML 库。前端只用项目已有依赖（Element Plus、Leaflet、ECharts、Pinia）。
4. **风格对齐**：后端模型写法参照 `backend/app/models/park.py`（SQLAlchemy declarative，`..core.database.Base`）；路由注册参照 `backend/app/api/__init__.py`（`include_router` 挂到 `api_router`，前缀 `/survey`）；配置项加到 `app/core/config.py` 的 `Settings`（pydantic-settings）。
5. 数据库表由 `scripts/init_db.py` 负责创建——检查该脚本并把你新增的模型纳入建表流程（与现有模型同等方式）。

## 实现步骤（按顺序，每步可独立验证）

### S1 后端：视觉公共模块 + KML 管道

1. **新建 `backend/app/services/vision_client.py`**：从 `kg/services/scanned_pdf_extractor.py` 抽取 OpenAI 兼容视觉调用为公共函数 `describe_image(image_bytes: bytes, prompt: str, *, timeout: int = 60) -> str`（图片转 base64 JPEG、复用其缩放压缩逻辑；端点从 `settings.openai_base_url` / `openai_api_key` / `openai_vision_model` 取）。不动原文件。
2. **新建 `backend/app/services/kml_service.py`**：解析两步路 KML（命名空间用通配匹配）→ 提取轨迹点序列（时间/经纬度/海拔）与照片标注点（经纬度/海拔/拍摄时间/速度/定位精度/照片 URL/原始文件名）。
3. **新建 `backend/app/services/track_service.py`**：照片下载（httpx 异步、并发 4、失败重试 2 次并标记 `download_status`，不中断整体）；逆地理编码 Provider 可配置（`GEOCODER_PROVIDER=bigdatacloud|nominatim`，默认 bigdatacloud，串行 + 同坐标缓存到本地 JSON）；调用 `vision_client.describe_image` 生成每张照片的「中文语义描述 + 报告图注」（prompt 参考 docs/08 第 3.3 节）。
4. **新建模型 `backend/app/models/track.py`**：`TrackFile`（原文件名、状态、轨迹点数、照片数、起终点语义、错误信息）、`TrackPhoto`（文件名/路径/缩略图路径、拍摄时间、经纬度、海拔、速度、定位精度、省/市/区县/街道/POI、语义描述、图注、下载状态）。
5. 缩略图用 Pillow 生成（宽 400px JPEG），存 `backend/data/tracks/{track_id}/photos/` 与 `thumbs/`。
6. **新建 `backend/app/api/track.py`** 路由（挂在 `/api/track`）：
   - `POST /upload` 上传 KML（multipart，上限 50MB），返回 `{track_id, status}`
   - `GET /{id}/status` 处理进度（阶段 + done/total）
   - `GET /{id}` 轨迹 GeoJSON + 照片点列表（含全部语义字段）
   - `GET /{id}/photos/{photo_id}` 返回原图或缩略图
   - `GET /{id}/export.xlsx` 照片汇总表（pandas + openpyxl，内嵌缩略图）
   - `GET /{id}/export.zip` 原图打包（zipfile）
   - `GET /list`、`DELETE /{id}`
   - 处理任务用 FastAPI `BackgroundTasks` 异步执行，状态持久化到 DB，服务重启后 status 接口返回真实状态、不丢结果。

**验收**：用仓库根目录可获取的示例 KML（`2026-09-08 10_44 刘贺主墓 南昌新建区.kml`，如不在仓库则跳过实跑，用 pytest 构造 fixture KML）——解析 264 轨迹点 + 57 照片点；照片全部下载入库；每张有逆地理地址与语义描述。写 `backend/tests/test_track.py`（解析、模型、接口至少各 1 个用例，网络调用 mock）。

### S2 调研事件模型

1. **新建 `backend/app/models/survey.py`**：`SurveyTask`（标题、遗址公园 id 可空、调研日期、状态、创建时间）、`SurveyEvent`（task_id、事件类型 photo、时间戳、经纬度、语义地址、标题、正文/描述、来源 material_id、主题标签 JSON、可用于报告 bool）。
2. 上传 KML 时关联/自动创建 SurveyTask（标题取文件名），处理完成后每张照片生成一条 SurveyEvent（时间=拍摄时间，地点=逆地理结果，标题=图注短句，正文=语义描述）。
3. **API 挂在 `/api/survey`**：`POST /tasks` 建任务、`GET /tasks`、`GET /tasks/{id}/events`（按时间排序）、`PATCH /events/{id}`（人工校对标题/标签/可用于报告）、`GET /tasks/{id}/timeline`（按小时聚合的线索数据，给前端时间线用）。

### S3 报告生成器 v1（只生成「调研过程」章）

1. **新建 `backend/app/services/report_service.py`**：
   - 输入某 SurveyTask 的事件列表 + 轨迹数据，调 `llm_provider`（复用现有 provider，不新接 SDK）生成「二、调研过程」章节正文：调研时间（来自轨迹起止时间）、调研方式（自动写明：实地踏勘+轨迹记录+影像采集）、实地踏勘（按时间顺序叙述踏勘路线与关键点位，引用事件）、踏勘照片（自动挑选 ≤8 张代表性照片，位置就近插入）。
   - LLM 输出要求带引用标记 `[EV:{event_id}]`。
2. **docx 渲染**：用 python-docx 按 docs/08 第 5.2 节默认模板渲染：标题层级「二、调研过程 /（一）调研时间…」、图编号「图 2.1…」自动连续、图注「{编号}：{标题}（拍摄时间：{时间}，{语义地址}）」、图片来源自动标「（来源：本次调研拍摄）」、文末「材料溯源表」（章节 → 引用事件清单）、参考文献暂不涉及。图片通栏宽 14cm。
3. **API**：`POST /api/survey/tasks/{id}/report/chapter2`（生成/重新生成）、`GET /api/survey/tasks/{id}/report`（章节内容+引用清单）、`GET /api/survey/tasks/{id}/report.docx`（下载）。章节内容与引用关系存 DB（`survey_report` 表：task_id、章节 json、引用清单 json、docx 路径、状态、版本），可重复生成覆盖旧版本。

### S4 前端：一个 Tab + 报告工作台最小界面

1. `frontend/src/router/index.js` children 下新增（挂 `Layout` 内，`meta.wide` 与 KG 一致）：
   - `/survey` 任务列表页
   - `/survey/:id` 任务详情工作台（**一个页面内用 Element Plus `el-steps` 做三步：材料接入 → 时间线校对 → 报告生成**，MVP 不拆四个路由）
2. `frontend/src/views/Layout.vue` 顶部导航在「处理流程」后加「田野调研」一项。
3. 新页面 `frontend/src/views/survey/SurveyWorkbench.vue`（MVP 单文件 + 必要子组件）：
   - **步骤一 材料接入**：KML 拖拽上传，轮询 `/api/track/{id}/status` 显示阶段进度条（解析中 → 下载照片 x/57 → 语义提取 x/57），失败项红色标记可重试（重新触发后端处理）。
   - **步骤二 时间线校对**：`el-table` 按时间列出事件（缩略图、时间、语义地址、标题可编辑、标签可编辑、「可用于报告」开关），全部确认后才可下一步（前端校验）。
   - **步骤三 报告生成**：「生成调研过程章节」按钮 → 显示生成状态 → 章节预览（标题/正文/图注/引用清单渲染成 HTML）→ 「重新生成」与「导出 docx」按钮。
4. 地图轨迹可视化 MVP 阶段可省略（S1 接口已返回 GeoJSON，后续增量再加 Leaflet）。

## 完成定义（DoD）

- `cd backend && python -m pytest tests/test_track.py -q` 全绿；`python -m pytest tests/` 无新增失败。
- `cd backend && uvicorn app.main:app --port 8000` 启动无报错，`/docs` 可见 `/api/track`、`/api/survey` 全部端点。
- `cd frontend && npm run dev` 启动无报错；顶部出现「田野调研」；走完三步可导出含图文与溯源表的 docx。
- 实机验收（有网络与示例 KML 时）：刘贺主墓 KML 全流程跑通，57 张照片入库，docx 章节图注编号正确、来源表完整。

## 禁止事项提醒

- 禁止改动 `backend/app/kg/**` 下任何现有文件、禁止改动现有路由行为、禁止新增 npm/pip 依赖、禁止把视觉/语音/LLM 能力复制第二份到 survey 模块里。
- 报告生成必须走「事件 → 引用标记 → 溯源表」链路，不允许 LLM 无引用自由发挥；无事件支撑的句子不允许出现在溯源表中。
