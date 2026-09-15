# P-Heritage-Portal-UI-01 代码事实对齐报告

## 1. 仓库与工作区

- 工作区根目录：`H:\my_code\datak`
- Git：当前目录及其父目录均不是 Git 仓库，无法识别分支、提交或工作树改动。
- 前端实际目录：`H:\my_code\datak\frontend`
- 后端实际目录：`H:\my_code\datak\backend`
- 本轮不会执行 commit 或 push。

## 2. 前端技术栈

- 框架：Vue 3.3，Composition API，单文件组件。
- 构建工具：Vite 5。
- 包管理器：npm（存在 `package-lock.json`）。
- UI：Element Plus 2.4 与 `@element-plus/icons-vue`。
- 路由：Vue Router 4，入口为 `frontend/src/router/index.js`。
- 状态：Pinia 2，仅现有认证状态使用 `frontend/src/stores/auth.js`。
- 请求：Axios 1.6，统一实例位于 `frontend/src/utils/api.js`；SSE 使用 `frontend/src/utils/sse.js`。
- 图表：ECharts 5.4，已在数据总览、详情、对比、知识图谱、知识库和文献计量页面使用。
- 现有地图：Leaflet 1.9 + 高德公开瓦片；地图逻辑全部集中在 `frontend/src/views/MapView.vue`。
- 样式：全局 SCSS 位于 `frontend/src/assets/styles/main.scss`，页面样式主要为组件内 scoped style。
- 静态资源：`frontend/public/templates` 仅含 Excel 模板；当前没有品牌图、封面图或门户插画资产。

## 3. 实际路由与目标映射

| 现有路由 | 现有页面 | 目标路由/处理 |
| --- | --- | --- |
| `/` | `Dashboard.vue` 数据总览 | 改为门户首页；新增 `/research-data` 承载研究数据页 |
| `/parks` | `Parks.vue` | 保留 |
| `/parks/:id` | `ParkDetail.vue` | 保留 |
| `/map` | `MapView.vue` | 保留并升级为高德 JS API 2.0 |
| `/comparison` | `Comparison.vue` | 兼容保留，并新增 `/compare` 别名/重定向 |
| `/knowledge-graph` | `KnowledgeGraph.vue` | 保留 |
| `/chat` | `Chat.vue` | 兼容保留，并新增 `/assistant` 别名/重定向 |
| `/knowledge-base` | `KnowledgeBase.vue` | 兼容保留，并新增 `/library` 别名/重定向 |
| `/bibliometrics` | `Bibliometrics.vue` | 保留 |
| `/admin` | `admin/DataManage.vue` | 兼容保留，并新增 `/data-management` 别名/重定向 |
| 缺失 | 关于我们 | 新增 `/about` |
| `/login` | `Login.vue` | 保留并统一视觉 |

## 4. 实际 Layout 与导航

- 当前全局 Layout：`frontend/src/views/Layout.vue`。
- 当前全局左侧栏：直接写在 `Layout.vue` 的 `el-aside` 和 `el-menu` 中，没有独立组件。
- 当前顶部栏：直接写在 `Layout.vue`，仅显示页名和用户菜单。
- 导航配置：当前分散在 `Layout.vue` 与 router meta 中，没有单一配置源。
- 现有主内容区使用固定后台布局，地图通过 `position: fixed` 假设侧栏宽度为 220/64px。

本轮将把 `Layout.vue` 改为统一 `PortalLayout` 职责，建立单一导航配置、PortalHeader、移动端导航、PortalFooter，并移除全局侧栏。

## 5. 实际 API 与真实数据

现有前端统一使用 `/api` 前缀，经 Vite 代理至 `http://localhost:8000`。后端 FastAPI 路由包括：

- `/api/auth`：登录、注册、当前用户、用户角色。
- `/api/parks`：公园列表、详情、遗址点、评分。
- `/api/statistics`：概览、对比、维度统计、单公园雷达。
- `/api/kg`：图谱统计、实体、邻居、搜索。
- `/api/chat`：问答、流式问答、会话历史。
- `/api/knowledge`：文献列表、搜索、上传、详情、删除、引用、计量、图谱、体检、综述。
- `/api/admin`：公园、遗址点、评分、用户、Excel 导入和报告导入。

SQLite 实际数据文件为 `backend/data/heritage.db`。只读核验结果：

- 遗址公园 9 个。
- 经纬度完整的公园 9 个。
- 遗址点 0 个。
- 评价指标 27 项。
- 评分记录 179 条。

页面必须继续使用以上接口和数据库数据，不新增 Mock API、随机统计值或硬编码成功结果。

## 6. 地图事实与坐标体系

- 当前地图引擎为 Leaflet，底图为高德瓦片；使用 `L.divIcon` 生成圆点。
- 当前没有聚合、URL 筛选恢复、详情侧板、Adapter、AMap JS API、Loca、ResizeObserver 或请求取消。
- `Park.longitude` / `Park.latitude` 模型注释明确为 WGS84。
- 现有 9 个公园均有坐标，例如圆明园 `116.30, 40.01`，大明宫 `108.96, 34.29`。
- 本轮地图渲染统一为 GCJ-02；转换仅在地图 Adapter 层发生，采用标准 WGS84→GCJ-02 转换函数，并以境外坐标不转换、中国境内样例转换作为测试样例。

## 7. 鉴权事实

- 前端 `AUTH_ENABLED` 当前为 `false`，Pinia 提供本地访客管理员旁路。
- 后端 `.env.example` 同样支持 `AUTH_ENABLED=false`。
- Axios 响应拦截器当前对每个 403 都弹消息，对普通错误也逐次弹消息；并发失败会产生重复提示。
- 路由守卫在启用鉴权时会把所有非登录路由重定向到 `/login`，尚未区分公共只读页与受限操作。

本轮将增加 401 单次处理与重复消息去重，并保留后端现有权限规则和登录能力。

## 8. 测试与构建事实

- npm 脚本仅有：`npm run dev`、`npm run build`、`npm run preview`。
- 不存在前端 lint、typecheck、unit test、E2E 脚本。
- `backend/tests` 当前为空。
- 本轮将继续使用 npm，不引入第二种包管理器；补充现有技术栈可运行的关键 E2E/验收能力，并明确记录所有缺失脚本。

## 9. 现有主要问题

1. 所有业务页共享深色全局左侧导航，和门户定位冲突。
2. 首页是三个后台图表，没有产品叙事、研究入口或内容门户结构。
3. 多个页面为默认 Element Plus 卡片堆叠，缺少统一视觉层级。
4. 地图是全屏固定定位的 Leaflet 默认实现，和 Layout 强耦合。
5. 页面缺少统一加载、空、错误、403 状态；图谱失败时会伪装为“数据加载中”。
6. ECharts 实例普遍缺少 resize 和销毁处理。
7. Chat 中存在仅供调试的 SSE 测试按钮与写死 `http://localhost:8000` 的测试请求。
8. 知识库上传、删除等受限操作未在 UI 层依据权限清晰区分。
9. 页面缺少移动端门户导航和移动端地图/会话抽屉。
10. 当前没有门户品牌视觉资产和公园封面图。

## 10. 本轮计划修改的文件

- `frontend/package.json`、`frontend/package-lock.json`、`frontend/vite.config.js`
- `frontend/.env.example`
- `frontend/src/main.js`、`frontend/src/router/index.js`
- `frontend/src/assets/styles/main.scss` 及新增真实图片资产目录
- `frontend/src/config/app.js`、新增统一导航配置
- `frontend/src/utils/api.js`、新增地图服务/Adapter 与通用数据辅助模块
- `frontend/src/views/Layout.vue`
- `frontend/src/views/Dashboard.vue` 与新增研究数据、关于我们页面
- `frontend/src/views/Parks.vue`、`ParkDetail.vue`、`MapView.vue`
- `frontend/src/views/Comparison.vue`、`KnowledgeGraph.vue`、`Chat.vue`
- `frontend/src/views/KnowledgeBase.vue`、`Bibliometrics.vue`
- `frontend/src/views/admin/DataManage.vue`、`Login.vue`
- 必要的门户、公共状态、图表和地图组件
- `docs/heritage-portal-ui/screenshots/`
- `docs/heritage-portal-ui/P-Heritage-Portal-UI-01_Acceptance_Report.md`
- 项目根 `design-qa.md`

## 11. 本轮不会修改的文件或范围

- 不修改数据库表结构和现有 SQLite 数据。
- 不重写后端业务逻辑、AI 调用链、知识图谱后端或文献计量算法。
- 不修改 Excel 模板内容。
- 不提交真实高德 Key、安全密钥或其他凭据。
- 不同时引入 MapLibre/第二套地图运行时。
- 不执行 Git commit 或 push。
