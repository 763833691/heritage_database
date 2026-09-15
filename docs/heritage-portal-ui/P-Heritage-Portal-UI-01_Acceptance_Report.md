# P-Heritage-Portal-UI-01 验收报告

## 1. 实际修改范围

- 将原后台式 Vue 3 前端重构为统一门户型前端。
- 重做首页、研究数据、遗址公园、详情、地图、对比、知识图谱、AI 助手、知识库、文献计量、关于我们、数据管理和登录页。
- 新增统一设计 Token、PortalHeader、PortalFooter、PageHero、StatusState 和单一导航配置。
- 使用内置图像生成能力制作门户 Hero、AI 助手 Hero 和遗址公园封面，并转换为 WebP。
- 将 Leaflet 地图替换为高德地图 JavaScript API 2.0 + Loca 2.0 适配层。
- 增加 ESLint、Vue Typecheck、Vitest、Playwright E2E 和生产构建脚本。
- 未修改后端业务逻辑、数据库结构、SQLite 数据或知识库算法。

## 2. 页面路由映射

| 路由 | 页面 | 说明 |
| --- | --- | --- |
| `/` | 门户首页 | 平台叙事、真实统计、研究入口、知识与公园内容 |
| `/research-data` | 研究数据 | 真实概览、维度、类型和区域图表 |
| `/parks` | 遗址公园 | 类型、省份、批次、关键词筛选和列表 |
| `/parks/:id` | 公园详情 | 基础档案、评分、图表和相关入口 |
| `/map` | 地图浏览 | 高德适配、筛选、选中详情、URL 状态 |
| `/compare` | 对比分析 | 2—5 个公园真实评分对比 |
| `/knowledge-graph` | 知识图谱 | 真实实体、关系与搜索 |
| `/assistant` | AI 助手 | 对话、推荐问题和能力说明 |
| `/library` | 知识库 | 搜索、文献详情、引用、上传和工具入口 |
| `/bibliometrics` | 文献计量 | 趋势、类型、关键词、作者和机构分析 |
| `/about` | 关于我们 | 平台定位、数据边界和研究价值 |
| `/data-management` | 数据管理 | 公园、遗址点、评分、用户和导入管理 |

兼容重定向保留：`/comparison`、`/chat`、`/knowledge-base`、`/admin`。

## 3. 删除的旧 Layout / Sidebar

- 删除 `Layout.vue` 中固定的 `el-aside` 和深色全局菜单。
- 删除地图对 220/64px 左侧栏宽度及固定定位的依赖。
- 所有目标页面均通过同一 PortalHeader 进入；页面内部的地图筛选、知识图谱详情、AI 会话和知识库工具栏仍作为业务工作区存在，不属于全局导航。
- 浏览器验收的十个桌面路由和三个移动路由均未发现全局左侧栏。

## 4. 新 PortalLayout 说明

- `Layout.vue` 负责 PortalHeader、主内容路由出口和条件式 PortalFooter。
- `src/config/navigation.js` 是桌面导航、移动导航和激活状态的单一来源。
- 桌面端显示横向导航、全站搜索入口和用户菜单；移动端折叠菜单。
- 全局样式定义品牌蓝、文本、表面、边框、圆角、阴影、页面最大宽度和响应式断点。
- 首页使用“平台价值—核心数据—研究工具—知识内容—公园精选—行动入口”的完整门户叙事。

## 5. 地图技术实现

- 运行时：`@amap/amap-jsapi-loader` 加载高德 JavaScript API 2.0。
- 插件：`AMap.MarkerCluster` 与 Loca 2.0。
- 适配层：`src/features/map/provider/AMapProvider.js` 统一挂载、点位、选择态、视图、缩放、ResizeObserver 和销毁。
- 数据层：`parkPointAdapter.js` 将 `/api/parks` 结果转换为地图点，不生成随机点或伪造点。
- 交互：类型、省份、批次、最低分筛选；URL 查询同步；选中详情；移动端筛选抽屉；地图加载、缺 Key、失败三类状态。
- 未配置 Key 时明确显示错误状态，绝不回退为假地图或旧 Leaflet 瓦片。

## 6. 坐标体系说明

- 数据库 `Park.longitude` / `latitude` 按现有模型注释视为 WGS84。
- 地图 Adapter 只在渲染边界执行 WGS84 → GCJ-02 转换。
- 中国境外坐标保持不变；中国境内使用标准偏移公式。
- Vitest 已覆盖境内转换、境外不转换和非法坐标拒绝三类样例。

## 7. 环境变量说明

配置模板：`frontend/.env.example`。

```env
VITE_AMAP_JS_KEY=
VITE_AMAP_SECURITY_CODE=
VITE_AMAP_MAP_STYLE=
```

- `VITE_AMAP_JS_KEY`：高德 Web 端 JavaScript API Key，必填后才加载真实地图。
- `VITE_AMAP_SECURITY_CODE`：安全密钥，可选，按高德控制台配置。
- `VITE_AMAP_MAP_STYLE`：样式 ID 或 `amap://styles/...`；留空使用 `whitesmoke`。
- 本轮没有写入真实 Key 或安全密钥。

## 8. API 复用情况

- 公园与详情：`/api/parks`。
- 统计与对比：`/api/statistics/overview`、`dimension`、`comparison`、`radar/{id}`。
- 知识图谱：`/api/kg/stats`、`entity`、`neighbors`、`search`。
- AI 会话：沿用 `/api/chat` 与现有 SSE 流。
- 知识库与计量：沿用 `/api/knowledge` 下的列表、搜索、详情、引用、上传、图谱、体检、综述和 `bibliometrics`。
- 数据管理：沿用 `/api/admin`。
- 未新增 Mock API、随机统计或硬编码成功数据。

## 9. 是否修改数据库

否。未修改表结构、迁移、SQLite 文件或任何真实记录。

## 10. 真实数据验证

本地 FastAPI + SQLite 实际验证结果：

- 遗址公园：9 个；9 个均有经纬度。
- 省级区域：4 个。
- 遗址点：0 个，页面显示真实空状态。
- 评价指标：27 项。
- 评分记录：179 条。
- 文献计量：当前 8 篇文献、18 条知识关联、8 个作者节点、6 个机构、3 种文献类型。
- 对比页：公园 ID 1、2、3 可生成 2 个图表和 3 行真实对比表。

## 11. 测试命令与结果

在 `frontend` 目录执行：

| 命令 | 结果 |
| --- | --- |
| `npm run lint` | 通过，0 error / 0 warning |
| `npm run typecheck` | 通过 |
| `npm run test` | 通过，1 个测试文件、3 个测试 |
| `npm run build` | 通过 |
| `npm run test:e2e` | 通过，12/12 |

## 12. E2E 结果

- 桌面 `1440 × 900` 与移动 `390 × 844` 两个项目均通过。
- 覆盖顶部导航、移动菜单、无全局左侧栏、真实公园筛选、详情打开、地图服务/缺 Key 状态、桌面地图筛选、移动地图筛选抽屉、真实对比图表与表格、知识库搜索和 AI 输入框。
- 高德 Key 未配置，因此点位点击的真实底图分支未执行；数据 Adapter、默认选中详情和缺 Key 降级已验证。
- 现有 `AUTH_ENABLED=false` 保留，因此“未登录管理页拦截”和启用鉴权时的 401 跳转未在本次运行态触发；Axios 已实现单次跳转锁和 2.5 秒重复提示去重。

## 13. 构建结果

- Vite 生产构建成功，2536 个模块完成转换。
- 生成资产包括优化后的 `portal-hero.webp`、`assistant-hero.webp` 和 `park-cover-fallback.webp`。
- 已按 Vue/Element Plus/ECharts 分组，但 ECharts、Element Plus、Markdown 相关 chunk 仍超过 500KB；这是已知性能优化项，不阻塞功能验收。
- Sass 报告 legacy JS API 弃用警告，来自当前 Vite/Sass 工具链，不影响构建结果。

## 14. 截图路径

目录：`docs/heritage-portal-ui/screenshots/`

桌面截图：

- `desktop-home-1440x900.png`
- `desktop-research-data-1440x900.png`
- `desktop-parks-1440x900.png`
- `desktop-map-1440x900.png`
- `desktop-compare-1440x900.png`
- `desktop-knowledge-graph-1440x900.png`
- `desktop-assistant-1440x900.png`
- `desktop-library-1440x900.png`
- `desktop-bibliometrics-1440x900.png`
- `desktop-data-management-1440x900.png`

移动截图：

- `mobile-home-390x844.png`
- `mobile-map-390x844.png`
- `mobile-assistant-390x844.png`

设计 QA 证据：

- `design-qa-all-pages-comparison.png`
- `design-qa-comparison-home.png`
- `design-qa-desktop-contact-sheet.png`
- `design-qa-mobile-contact-sheet.png`

## 15. 已知问题

1. 本地未配置 `VITE_AMAP_JS_KEY`，地图当前显示明确配置错误；填入合法 Key 后启用真实底图和点位。
2. 知识库当前只有 8 篇文献、遗址点为 0，相关页面密度低于参考图，但没有伪造数据。
3. 构建仍有大 chunk 与 Sass legacy API 警告。
4. `npm audit` 报告 5 个依赖漏洞（3 moderate、2 high）；未执行可能引入破坏性升级的 `npm audit fix --force`。
5. 当前工作区不是 Git 仓库，无法提供差异状态和提交哈希。

## 16. 回滚方式

- 当前工作区没有 Git 元数据，无法使用 `git revert` 或 `git checkout` 精确回滚。
- 如需回滚，应从用户已有的工作区备份或版本管理副本恢复 `frontend` 和本报告目录。
- 不建议直接删除整个前端目录；生成资产、测试和配置可按本报告列出的修改范围逐项恢复。

## 17. Git 状态

`H:\my_code\datak` 及父目录不是 Git 仓库，`git rev-parse --show-toplevel` 返回失败。因此没有可报告的 branch、diff 或 worktree 状态。

## 18. Commit Hash

未执行 commit；用户未要求提交，并且当前工作区不是 Git 仓库。
