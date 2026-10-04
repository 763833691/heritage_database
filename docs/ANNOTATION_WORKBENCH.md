# 标注工作台（Annotation Workbench）开发文档

> 读者：Kilo（VSCode AI 编码助手）
> 项目根目录：`H:\my_code\datak`
> 任务：在现有调研数据平台中新增"照片语义标注工作台"，支持盲标、多人独立编码、人机一致性（Cohen's Kappa）计算与结果导出。
> 约束：**只做本文档规定的功能，不要重构既有代码，不要修改与本功能无关的文件。**

---

## 1. 项目现状（已核实，直接采信）

- 后端：`backend/`，FastAPI + SQLAlchemy + SQLite（`backend/data/heritage.db`）。
  - 模型基类：`app/core/database.py` 中 `Base = declarative_base()`，会话工厂 `SessionLocal`，依赖 `get_db`。
  - 现有模型：`app/models/track.py`（`TrackFile`、`TrackPhoto`）、`app/models/survey.py`、`app/models/park.py`。
  - 路由聚合：`app/api/__init__.py` 逐个 `include_router`，挂到 `/api/<前缀>`；`app/main.py` 第 120 行 `app.include_router(api_router, prefix="/api")`。
  - **照片访问接口已存在**：`GET /api/track/{track_id}/photos/{photo_id}`（原图），加 `?thumb=true` 为缩略图。标注界面直接复用，不要另写照片服务。
  - `TrackPhoto` 关键字段：`id, track_id, seq, file_name, shot_time, longitude, latitude, description, caption, tags, download_status, describe_status, poi, address`。
  - 认证：`AUTH_ENABLED=false`（开发环境），现有接口用 `Depends(get_current_user)` 的写法可保留但会放行。
- 前端：`frontend/`，Vue 3 + Vite + Vue Router + Pinia。
  - HTTP 封装：`src/utils/api.js`（axios 实例，`baseURL: '/api'`）；领域 API 按 `src/utils/surveyApi.js` 的模式组织（`import api from '@/utils/api'`，导出各端点函数）。
  - 路由：`src/router/index.js`，懒加载，`meta: { title }`，调研相关页面放在 `src/views/survey/`。
  - UI：项目未用 Element Plus 等重型组件库，页面以原生 Vue + 自有样式为主，新页面保持同样风格（参考 `src/views/survey/SurveyWorkbench.vue` 的布局与配色）。
- 运行方式：后端 `uvicorn app.main:app`（在 `backend/` 下）；前端 `npm run dev`（在 `frontend/` 下），Vite 已代理 `/api` 到后端。

## 2. 功能需求

### 2.1 业务背景

平台中 14 段踏勘轨迹共 1028 张照片，已有两级自动语义结果：① 关键词规则分类（存于 `data/tracks/{track_id}/analysis.json` 的 `photos[].type`）；② 多模态大模型按编码手册的独立编码。现需人工标注作为金标准，计算人机一致性。编码类目为 A–G 七类：

| 编码 | 名称 | 一句话定义 |
|---|---|---|
| A | 遗址本体展示 | 遗址原生遗存本体及直接保护设施（夯土、基址、封土、柱础、遗址剖面、出土遗物、保护栈道围栏） |
| B | 复原建筑与覆罩 | 覆罩保护建筑与形象复原建筑（保护棚/罩、城楼、阙楼、仿古复原建筑） |
| C | 阐释解说设施 | 非数字阐释媒介（展板、说明牌、沙盘模型、壁画浮雕、展厅展陈、导览标识） |
| D | 数字互动展示 | 数字互动沉浸设施（互动屏、电子屏、VR/AR、全息、数字展厅） |
| E | 运营与消费场景 | 运营商业服务设施（售票、文创店、售卖机、演艺、游客中心） |
| F | 景观环境与城市关系 | 景观空间与环境（广场、绿地、步道、湿地、水面、远眺天际线） |
| G | 其他 | 无法归入以上六类 |

### 2.2 核心功能

1. **标注任务管理**：从样本 JSON 文件导入创建标注任务；任务列表页展示任务、进度、状态。
2. **盲标工作台**：编码者逐张看图编码。
   - 界面只显示：照片大图、样本编号、当前进度（如 36/142）；**绝不显示**平台分类、智能体编码、caption 等任何先验信息。
   - 七个编码按钮（A–G），带类目名称与一句话定义；支持键盘快捷键（按 A/B/C/D/E/F/G 键直接编码并自动跳下一张）。
   - 选 G 时弹出备注输入（选填）。
   - 支持回退上一张修改；支持从进度点继续（断点续标）。
   - 编码者身份：进入工作台时输入编码者代号（如 `coder1`、`coder2`），存 localStorage，随每次提交上送；同一编码者对同一张照片重复提交时覆盖原记录。
3. **结果与信度页**：任务完成后展示——
   - 各编码者完成数；平台分类 vs 智能体、人工 vs 智能体、人工 vs 平台的两两一致率与 Cohen's Kappa；
   - 分歧清单（至少两方编码不一致的条目，可查看照片与各方编码）；
   - 导出 Excel（每行：样本编号、轨迹 ID、照片 ID、平台分类、智能体编码、各人工编码、是否一致、备注）。

### 2.3 样本数据

导入文件已备好：`backend/data/annotation/sample_v1.json`，结构：

```json
{
  "task_name": "双标信度检验样本 v1",
  "codebook_version": "v1.0",
  "categories": {"A": "遗址本体展示", "...": "..."},
  "items": [
    {"sid": "S001", "track_id": 1, "photo_id": 123, "seq": 45,
     "platform_type": "C", "ai_code": "A", "caption": "……"}
  ]
}
```

共 142 条。`photo_id` 即 `track_photo` 表主键，照片 URL 用既有接口 `/api/track/{track_id}/photos/{photo_id}` 拼装。

## 3. 数据模型（新增 `app/models/annotation.py`）

```python
class AnnotationTask(Base):
    __tablename__ = "annotation_tasks"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    codebook_version = Column(String(20), default="v1.0")
    status = Column(String(20), default="open")  # open/closed
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AnnotationItem(Base):
    __tablename__ = "annotation_items"
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("annotation_tasks.id"), index=True)
    sid = Column(String(20), index=True)          # 样本编号 S001…
    track_id = Column(Integer, index=True)
    photo_id = Column(Integer, ForeignKey("track_photo.id"))
    seq = Column(Integer)                          # 任务内展示顺序
    platform_type = Column(String(2))              # 平台规则分类（盲标不下发）
    ai_code = Column(String(2))                    # 智能体编码（盲标不下发）
    caption = Column(Text)                         # 仅结果页展示

class AnnotationRecord(Base):
    __tablename__ = "annotation_records"
    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("annotation_items.id"), index=True)
    coder = Column(String(50), index=True)
    code = Column(String(2))                       # A–G
    note = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now())
    __table_args__ = (UniqueConstraint("item_id", "coder", name="uq_item_coder"),)
```

表创建方式与现有模型一致（确认 `app/core/database.py` 或 `scripts/init_db.py` 的建表机制并同样纳入；若项目用 `Base.metadata.create_all`，保证新模型被 import 即可）。

## 4. 后端接口（新增 `app/api/annotate.py`，前缀 `/annotate`，注册进 `app/api/__init__.py`）

| 方法 | 路径 | 说明 | 请求/响应要点 |
|---|---|---|---|
| POST | `/tasks/import` | 从样本 JSON 导入任务 | body: `{"name": str, "sample_path": "data/annotation/sample_v1.json"}`（服务端相对 backend 目录读取）；幂等：同名任务已存在则返回既有任务 |
| GET | `/tasks` | 任务列表 | 返回各任务 id、name、条目总数、按 coder 的完成数 |
| GET | `/tasks/{task_id}/next` | 取下一张待标（盲标） | 参数 `coder`；返回 `{item_id, sid, photo_url, progress: {done, total}}`；**响应中不得包含 platform_type / ai_code / caption**；全部完成返回 `{finished: true, progress}` |
| POST | `/items/{item_id}/code` | 提交编码 | body: `{coder, code, note?}`；校验 code ∈ A–G；同 (item, coder) 覆盖更新（upsert） |
| GET | `/items/{item_id}/photo-meta` | 盲标页照片元信息 | 只返回 `{sid, photo_url}`（与 next 同一盲标约束） |
| GET | `/tasks/{task_id}/results` | 信度结果 | 见 4.1 |
| GET | `/tasks/{task_id}/export` | 导出 Excel | openpyxl 生成，列见 2.2-3，`Content-Disposition` 附件下载 |

### 4.1 信度计算（`app/services/annotation_service.py`）

- `cohens_kappa(codes_a: list[str], codes_b: list[str]) -> float`：仅对双方都非空的配对计算；`kappa = (po - pe) / (1 - pe)`，`pe` 按 A–G 各类别边际频率计算。
- `/results` 响应结构：

```json
{
  "task": {"id": 1, "name": "...", "total": 142},
  "coders": ["coder1", "coder2"],
  "pairwise": [
    {"a": "platform", "b": "ai", "n": 141, "agree": 72, "agree_rate": 0.511, "kappa": 0.378},
    {"a": "coder1", "b": "ai", "n": 142, "agree": 0, "agree_rate": 0.0, "kappa": 0.0}
  ],
  "disagreements": [
    {"item_id": 1, "sid": "S001", "photo_url": "/api/track/1/photos/123",
     "platform": "C", "ai": "A", "human": {"coder1": "A"}, "caption": "……"}
  ]
}
```

- 分歧判定：该条目的所有非空编码（platform、ai、各 coder）不全部相同即入分歧清单。

## 5. 前端页面（新增，保持现有视觉风格）

### 5.1 路由（`src/router/index.js` 追加）

```js
{ path: 'annotate', name: 'AnnotateTasks', component: () => import('@/views/annotate/TaskList.vue'), meta: { title: '标注任务' } },
{ path: 'annotate/:id', name: 'AnnotateWorkbench', component: () => import('@/views/annotate/Workbench.vue'), meta: { title: '标注工作台', wide: true } },
{ path: 'annotate/:id/results', name: 'AnnotateResults', component: () => import('@/views/annotate/Results.vue'), meta: { title: '信度结果', wide: true } },
```

在布局导航（`Layout.vue`）中加"数据标注"入口，位置紧随"田野调研"。

### 5.2 API 封装（`src/utils/annotateApi.js`，仿 `surveyApi.js` 模式）

### 5.3 页面规格

**TaskList.vue**：任务卡片列表（名称、总条数、各 coder 进度条、状态）；每张卡片两个按钮："开始/继续标注"、"查看结果"。

**Workbench.vue**（核心，参考布局）：

```
┌──────────────────────────────────────────────┐
│ 任务名    编码者: coder1    进度 36/142  [结果页]│
├────────────────────────────┬─────────────────┤
│                            │  A 遗址本体展示    │
│                            │  B 复原建筑与覆罩  │
│         照片大图            │  C 阐释解说设施    │
│      （适应高度，居中）      │  D 数字互动展示    │
│                            │  E 运营与消费场景  │
│                            │  F 景观环境与城市  │
│                            │  G 其他           │
│                            │  [备注输入(G时)]   │
│                            │  ← 上一张          │
└────────────────────────────┴─────────────────┘
```

- 首次进入弹窗输入 coder 代号，存 localStorage；
- 键盘监听：A–G 键提交并自动取下一张；← 回退上一张（回退时把已填编码回显，允许改判重提）；
- 选中态高亮当前编码按钮；提交后按钮区闪现"已记录"反馈再跳张；
- **盲标纪律**：页面任何位置不得渲染 platform/ai/caption。

**Results.vue**：两两一致性表格（一致率+Kappa，Kappa 保留 3 位小数）；分歧清单表格（sid、缩略图、各方编码、备注）；顶部"导出 Excel"按钮（`window.open` 导出接口）。

## 6. 验收标准（必须全部通过）

1. `POST /api/annotate/tasks/import` 导入 `sample_v1.json` 后任务含 142 条目；重复导入不产生重复任务/条目。
2. 盲标接口响应 JSON 中不含 `platform_type`、`ai_code`、`caption` 字段（人工核对响应）。
3. 用两个 coder 代号各标 ≥10 条后，`/results` 能返回两两一致率与 Kappa；同一 coder 重复提交同一条目覆盖而非新增。
4. 导出 Excel 打开后列齐全、142 行。
5. 前端三页面路由可达；键盘 A–G 编码+自动跳张可用；进度断点刷新后可续标。
6. 后端启动无 import 错误；`heritage.db` 新增 3 张表。

## 7. 明确不做（Out of Scope）

- 不做登录权限体系（沿用现状 `AUTH_ENABLED=false`）；
- 不改 `track`/`survey` 既有任何接口与页面；
- 不做标注任务在前端的创建向导（导入只走接口/脚本）；
- 不做二级编码（A-a/B-b…）界面（数据模型预留也不做，下轮再说）；
- 不引入新的前端组件库/UI 框架。

## 8. 开发顺序建议

1. 模型 + 建表 → 2. 导入接口 → 3. 盲标 next/code 接口 → 4. results/Kappa → 5. export → 6. 前端 Workbench → 7. TaskList/Results → 8. 按第 6 节自测。
