# 数据展示方案（交给 Kilo 执行）

> 生成日期：2026-09-28。依据两份盘点：后端数据/API 盘点、前端页面盘点（见文末「盘点结论摘要」）。
> 执行者：Kilo。工作目录：`H:\my_code\datak`。建议新开分支或 worktree 执行，逐期完成、逐期验收。

## 目标

把库里已有的真实数据展示出来。当前最大问题：**最有价值的资产——14 条 KML 轨迹、1028 张带语义描述的田野照片、1028 条调研事件——只在单个任务的工作台里可见，访客完全看不到全貌**；其次是少量前端假数据/死按钮会损害可信度。

## 执行原则

1. 所有图表必须接真实接口，禁止写死 data；确实没有的数据就删组件，不要编。
2. 后端优先做聚合接口，避免前端 N 次循环拉取（尤其照片地图，1028 个点必须一次聚合返回）。
3. 每期做完跑一遍 `backend` 的 pytest 和 `frontend` 的 playwright 测试，并人工打开页面核对数字与数据库一致。
4. 改动的文件清单和验收结果写回本文档末尾的「执行记录」。

---

## P0 田野数据总览（最高优先级，本期是重点）

### 任务 1：后端聚合接口

新增 `GET /api/track/photos/overview`（`backend/app/api/track.py`）：

- 一次性返回全部（或按筛选返回）照片点：`photo_id`、`track_id`、`park_id/公园名`、经纬度、拍摄时间、A–F 保护展示编码（来自语义分析结果）、标签、`photo_url`（复用现有 `GET /{id}/photos/{photo_id}` 的 URL 规则）。
- 支持 query 参数：`park_id`、`track_id`、`code`（A–F）、分页 `page/page_size`。
- 关联 `survey_events` 时去重（目前 1 照片 = 1 事件，数量完全一致，按 photo 出即可）。
- 顺带返回统计：照片总数、覆盖公园数、轨迹条数、各编码数量分布。

### 任务 2：新页面「田野影像总览」`/field-gallery`

新建 `frontend/src/views/FieldGallery.vue`，顶部导航加入口（`src/config/navigation.js`），包含三个区块：

1. **照片地图**：复用 `MapView.vue` 的高德适配层（`features/map/provider/AMapProvider.js`），点聚合渲染 1028 张照片，点击点位弹窗显示缩略图 + 语义地址 + 视觉描述，可跳转到所属调研任务。
2. **照片墙**：瀑布流/分页网格，缩略图懒加载，点击放大看视觉描述、图注、A–F 编码、拍摄时间。
3. **筛选栏**：按公园、轨迹任务、A–F 编码、时间范围筛选，全部走任务 1 的聚合接口。

### 任务 3：跨轨迹语义分析对比图

- 把 `GET /track/analysis/compare` 的对比结果做成独立图表区块，放在 `/field-gallery` 下方或 `/research-data` 页（二选一，推荐前者）。
- 现状：该接口只在 `SurveyWorkbench.vue` 单任务页内被调用，跨公园比较能力游客看不到。

### 任务 4：「调研覆盖」统计区块

在 `/research-data` 页顶部加一排统计卡：轨迹条数（14）、照片数（1028）、调研事件数、覆盖公园数、轨迹总里程（可由 KML 数据算，后端出）。
数据可走 `GET /statistics/overview` 扩展字段，或复用任务 1 接口的统计部分。

**P0 验收**：不登录任何任务页，从首页导航就能在地图上看到全部照片点、照片墙能翻页、筛选生效；数字与 `SELECT count(*) FROM track_photo` 一致。

---

## P1 评分与对比数据看全

### 任务 5：公园 × 指标评分热力图

- 后端新增 `GET /api/statistics/score-matrix`：返回 公园 × D1–D27 的标准化分矩阵（179 条 scores 聚合一次出）。
- 前端在 `/research-data` 加 ECharts 热力图（公园为行、指标为行，tooltip 显示原始值和依据），支持按维度（D1–D27 分组）折叠。

### 任务 6：公园详情页补「调研记录」区块

`ParkDetail.vue` 增加一个区块：该公园关联的调研任务卡片（任务名、照片数、事件数、报告状态，接 `GET /survey/tasks`）+ 「导出 Excel」按钮（`surveyApi.js` 里已封装好 `trackExportUrl`，直接接上即可，它是纯闲置封装）。

### 任务 7：对比页 CSV 导出

`Comparison.vue` 的「导出说明」按钮改为真导出：把当前对比表格数据导出 CSV（前端生成下载即可，不需要后端接口）。

**P1 验收**：热力图数字与数据库 `scores` 表抽查一致；公园详情页能看到该公园的轨迹任务并可下载 Excel。

---

## P2 假数据与死按钮修复（信任修复）

| # | 位置 | 问题 | 修法 |
|---|------|------|------|
| 8 | `kg/Processing.vue` StatCard | delta（`+5%`/`+0.06`/`+1`）和「文本覆盖率」（`70 + n/2`%）是前端编的（约 285–305 行） | 改用接口真实字段；接口没有的指标就删掉该卡 |
| 9 | `KnowledgeBase.vue` 结果栏 | 「相关性/发表时间/被引量」排序按钮无任何点击事件 | 后端 `/knowledge/search` 加 `sort` 参数并实现排序；不想做后端就删按钮 |
| 10 | `Comparison.vue`、`Bibliometrics.vue` | 「导出说明」按钮无后端 | 参照任务 7 做真导出，或删除按钮 |
| 11 | `kg/FileVault.vue` | 「下载」按钮只弹提示；详情「上传者」写死 `admin` | 后端加 `GET /api/file/{id}/download` 返回原始文件流；上传者用文件记录的真实字段（接口没有就补） |
| 12 | `KnowledgeGraph.vue`（约 312 行） | 详情面板 fallback 写死找 `label === '大明宫'` | 改为取当前图中第一个节点或空态提示 |
| 13 | `PortalHeader` 全站搜索 | 宣称搜「遗址公园、文献或指标」，实际只跳 `/parks?keyword=` | 加文献搜索：调用 `/knowledge/search`，结果分组展示，点击跳 `/library` 详情 |

**P2 验收**：全站 grep 不到写死的假 delta / 假覆盖率；上述每个按钮点击都有真实响应。

---

## P3 闲置接口盘活或清理

| # | 接口 | 处置 |
|---|------|------|
| 14 | 旧版 `/api/kg/*` 整组（stats/entity/neighbors/search） | 二选一：在知识图谱页加「实体检索」入口用它；或整组删除 router 和相关测试 |
| 15 | `GET /api/statistics/radar/{park_id}` | `ParkDetail.vue` 雷达图改用它（替代前端自行计算），或删接口 |
| 16 | `POST /api/admin/sites` | `DataManage.vue`「新增遗址点」按钮从提示文案改为真表单 |
| 17 | `GET /api/knowledge/review` | 文献库「综述生成」旁加「查看上次综述」入口 |
| 18 | `kgApi.js` 中 `getKgFile`/`getKgNodeGraph`/`searchKgGraph`/`batchRunKgProcess`、`aiModelApi.js` 中 `listAiTasks` | 随任务 14/17 一并接上，或删除死代码 |

**P3 验收**：后端每个存活接口都有前端调用点；前端每个请求封装都有使用处。

---

## 明确不做的事（本期范围外）

- `sites`、`locations`、`exhibitions`、`reviews`、`survey_answers`、`education_activities` 等 10 张表当前为空，没有可展示的数据。若后续有 Excel 数据，用 `/admin/import/*` 导入后再考虑展示（其中 `locations`/`exhibitions` 连 API 都没有，需另行设计）。
- Chroma 向量库基本空置（3 条向量）、Neo4j 未启用，不在这期处理。
- 不做 UI 大改版，只加页面/区块、修按钮。

---

## 盘点结论摘要（方案依据）

**数据库实际有数据**：15 个公园、179 条 D1–D27 评分、14 条 KML 轨迹、1028 张语义化照片（= 1028 条调研事件）、27 条指标、8 篇文献（含 18 条语义关系）、9 个 AI 模型配置、1 个 admin 账户。另有约 10 张表为空。

**前端现状**：18 个页面全部接了真实接口，无整页假数据；缺口集中在——① 1028 张照片只在单任务工作台可见，无全局视图；② 7 个闲置后端接口（旧 /kg/* 整组、radar、track 导出、admin sites POST、knowledge/review 等）；③ 8 处假数据/死按钮（Processing StatCard、文献排序按钮、导出说明、文件下载、写死「大明宫」等）；④ 8 个未使用的前端请求封装。

## 执行记录

### P0 田野数据总览（完成于 2026-09-28）

**改动文件**

- 后端 `backend/app/api/track.py`：新增 `GET /api/track/photos/overview`，返回筛选后的照片点 + 全局统计（照片/公园/轨迹/事件/里程/编码分布/公园与轨迹筛选项）；A–F 编码优先读取 `data/tracks/{id}/analysis.json`（带内存 mtime 缓存），缺失时按同一 CODEBOOK 即时计算；支持 `park_id/track_id/code/date_from/date_to/page/page_size`。
- 后端 `backend/app/api/statistics.py`：`GET /statistics/overview` 增加 `field_research` 字段（轨迹数、照片数、事件数、覆盖公园数、总里程）。
- 后端 `backend/tests/test_track.py`：新增 `test_photos_overview_aggregates_stats_and_filters`。
- 前端 `frontend/src/views/FieldGallery.vue`：新页面，含统计卡、筛选栏、照片地图（复用 `AMapProvider` 点聚合）、照片墙（懒加载+分页）、照片详情弹窗、跨轨迹语义构成对比图（接 `/track/analysis/compare`）。
- 前端 `frontend/src/utils/surveyApi.js`：新增 `getPhotosOverview`。
- 前端 `frontend/src/config/navigation.js`、`frontend/src/router/index.js`：新增 `/field-gallery` 导航与路由。
- 前端 `frontend/src/views/ResearchData.vue`：新增「田野调研覆盖」统计卡区块。
- 前端 `frontend/tests/e2e/portal.spec.js`：新增「田野影像总览」用例，并把 `/field-gallery` 纳入无侧栏巡检；修正地图用例中已失效的 `.map-filter-panel` 选择器与移动端 `/筛选/` 严格模式冲突（原为本地 MapView 重构后遗留的过期断言）。

**接口自测（真实库 `backend/data/heritage.db`）**

- `/api/track/photos/overview` → `total=1028`，`stats.photo_total=1028`、`track_count=14`、`park_count=9`、`event_count=1028`、`distance_km=86.43`；编码分布 A358 / B26 / C394 / D47 / E23 / F83 / G97（合计 1028）。
- `/api/statistics/overview.field_research` → 与上一致；`park_id=7` → 43 张、`track_id=1` → 43 张、`code=A` → 358 张。

**测试结果**

- 后端：`py -3 -m pytest -q` → **55 passed**。
- 前端：`npm run lint` 通过；`npm run build` 通过；`npx playwright test` → **14 passed**（desktop + mobile）。
- 说明：本机沙箱内高德远端脚本不可达，地图页按设计降级为「加载中/失败」明确状态，照片墙与统计不受影响。

### P1 评分与对比数据看全（完成于 2026-09-28）

**改动文件**

- 后端 `backend/app/api/statistics.py`：新增 `GET /statistics/score-matrix`，一次返回 15 个公园 × D1–D27 的 179 条标准化分，含 `parks/indicators/dimensions/cells`（cell 带 score/grade/raw_value/evidence/data_year）。
- 后端 `backend/tests/test_statistics.py`：新增概览扩展字段与评分矩阵测试。
- 前端 `frontend/src/views/ResearchData.vue`：新增 ECharts 热力图（公园为行、指标为列），支持按 4 个维度折叠，tooltip 显示原始得分、等级与评分依据。
- 前端 `frontend/src/views/ParkDetail.vue`：新增「调研记录」区块，接 `GET /survey/tasks` 过滤本公园任务（名称/日期/照片数/事件数/可用数/报告状态），并提供「导出 Excel」按钮（接 `trackExportUrl`）。
- 前端 `frontend/src/views/Comparison.vue`：「导出说明」改为真实「导出 CSV」，导出当前维度得分总览表（UTF-8 BOM，Excel 可直接打开）。
- 前端 `frontend/tests/e2e/portal.spec.js`：新增热力图与公园调研记录用例。

**自测**

- `/api/statistics/score-matrix` → parks=15、indicators=27、cells=179、dimensions=4（5/7/7/8 项）。
- 维度得分 CSV 由前端本地生成，无后端依赖。

**测试结果**

- 后端：`py -3 -m pytest -q` → **56 passed**。
- 前端：`npm run lint`、`npm run build` 通过；`npx playwright test` → **16 passed**。

### P2 假数据与死按钮修复（完成于 2026-09-28）

- #8 `kg/Processing.vue`：删除编造的「文本覆盖率」卡片与全部假 delta（`+n`/`+5%`/`+0.06`）；`StatCard` 移除 delta 展示，仅保留真实值（实体数/关系数/类型数/平均置信度由结果数据实时计算）。
- #9 `KnowledgeBase.vue` + `knowledge.py`：`/knowledge/list` 与 `/knowledge/search` 新增 `sort` 参数（relevance/year/citations），检索结果补齐 authors/journal/doc_type/citation_count；排序按钮改为可切换并真实生效。
- #10 `Comparison.vue`、`Bibliometrics.vue`：导出按钮改为真实 CSV 下载（前端本地生成，UTF-8 BOM）。
- #11 `kg/api/file.py` 新增 `GET /api/file/{id}/download` 返回原始文件流；`FileVault.vue` 下载按钮改为真下载，详情「上传者 admin」改为真实「来源」字段（`file.source`）。
- #12 `KnowledgeGraph.vue`：详情面板 fallback 由写死「大明宫」改为当前图首个节点，无节点时由面板显示空态。
- #13 `PortalHeader.vue` + `KnowledgeBase.vue`：全站搜索改为调用 `/parks` + `/knowledge/search`，结果分组展示；文献结果点击跳 `/library?lit=<id>` 并自动打开详情。

**验证**：`grep` 全站无「文本覆盖率/较上次/+5%/+0.06/delta/导出说明/暂不支持直接下载/admin 上传者」；`/knowledge/search?sort=year` 年份降序、结果含 citation_count；`/api/file/{id}/download` 返回 200 原始流，无原件返回 404。

**测试结果**：后端 **58 passed**（新增 2 个文件下载用例）；前端 lint/build 通过；`npx playwright test` → **21 passed, 1 skipped**（移动端头部无搜索入口）。

### P3 闲置接口盘活或清理（完成于 2026-09-28）

- #14 旧版 `/api/kg/*`：确认该整组早已被 `from ..kg.api import kg_router` 覆盖而**从未挂载**（实测 `/api/kg/stats`、`/api/kg/search` 均为 404）。删除死文件 `backend/app/api/kg.py`，并清理 `backend/app/api/__init__.py` 中的重复导入与重复 `/kg` 挂载。
- #15 `GET /statistics/radar/{park_id}`：`ParkDetail.vue` 雷达图改为直接使用该接口返回的维度均值，替换前端自行计算。
- #16 `POST /api/admin/sites`：`DataManage.vue`「新增遗址点」由提示文案改为真实表单（新增/编辑均接后端，保存后刷新列表）。
- #17 `GET /knowledge/review`：`KnowledgeBase.vue` 在「生成综述」旁新增「查看综述数据」入口（下拉菜单 + 侧栏快速工具），展示主题、文献数、年份跨度、高频关键词、方法论与按年脉络。顺带修复 `kb_lint.generate_literature_review` 在存在无年份文献时 `int`/`str` 混排崩溃的真实缺陷。
- #18 死代码：删除 `kgApi.js` 的 `getKgFile`/`getKgNodeGraph`/`searchKgGraph`（与本地节点筛选、全量图谱重复）与 `aiModelApi.js` 的 `listAiTasks`（与 `/ai/routes`、`/ai/status` 重复）；`batchRunKgProcess` 在文件库接上「批量处理」按钮。

**验证**

- `/api/kg/stats` → 404（旧组已清）；`/api/file/list`、`/api/graph/full`、`/api/system/status`、`/api/ai/status` → 200（新系统根路径正常）。
- `/api/statistics/radar/1` → 200；`/api/admin/sites` 新增后再删除 → 200；`/api/knowledge/review?max_lits=20` → 200（8 篇、6 组年份）。
- 前端导出封装全部有调用点（`kgApi/aiModelApi/surveyApi` 逐一核对，无 0 使用导出）。

**测试结果**：后端 **59 passed**（新增年份缺失回归用例 `tests/test_kb_review.py`）；前端 `lint`/`typecheck`/`build` 均通过；`npx playwright test` → **23 passed, 1 skipped**。
