# 软著材料可追溯性报告

## 功能到证据的映射

| 功能 | 主要代码证据 | 手册证据 | 截图证据 |
|---|---|---|---|
| 门户首页 | `frontend/src/views/Dashboard.vue`、`frontend/src/router/index.js` | 五、门户首页 | 首页 |
| 研究数据总览 | `frontend/src/views/ResearchData.vue`、`backend/app/api/statistics.py` | 六、研究数据总览 | 研究数据页 |
| 遗址公园检索 | `backend/app/api/parks.py`、`frontend/src/router/index.js` | 七、遗址公园检索 | 遗址公园列表页 |
| 遗址公园详情 | `frontend/src/views/ParkDetail.vue`、`backend/app/api/parks.py` | 八、遗址公园详情 | 代码与手册文字 |
| 地图浏览 | `frontend/src/views/MapView.vue`、`backend/app/api/parks.py` | 九、地图浏览 | 地图浏览 |
| 对比分析 | `frontend/src/views/Comparison.vue`、`backend/app/api/statistics.py` | 十、对比分析 | 对比分析 |
| 知识图谱 | `backend/app/api/kg.py` | 十一、知识图谱 | 知识图谱 |
| 智能助手 | `backend/app/api/chat.py`、`backend/app/services/rag_engine.py` | 十二、智能助手 | AI 助手 |
| 文献知识库 | `backend/app/api/knowledge.py` | 十三、文献知识库 | 知识库 |
| 文献计量 | `backend/app/api/knowledge.py` | 十四、文献计量 | 文献计量 |
| 登录与权限 | `frontend/src/router/index.js`、`frontend/src/views/admin/DataManage.vue` | 十五、登录与权限 | 代码与手册文字 |
| 数据管理与报告导入 | `frontend/src/views/admin/DataManage.vue`、`frontend/src/views/admin/ReportImport.vue` | 十六、数据管理与报告导入 | 代码与手册文字 |

## 申请事实到证据的映射

| 申请事实 | 状态 | 追溯来源 |
|---|---|---|
| 软件全称与版本 | confirmed | 登记截图、申请表确认稿、正式文件页眉 |
| 合作开发 | confirmed | 登记截图、申请表确认稿 |
| 5 名共同著作权人 | confirmed | 登记截图、用户修正后的申请表确认稿 |
| 已发表及首次发表信息 | confirmed | 登记截图、申请表确认稿 |
| 功能与技术特点 | confirmed | 项目源码、业务理解稿、操作手册 |
| 代码真实性 | validated | 正式代码段与 15 个已确认源码文件逐行匹配 |

## 版式与文件追溯

- 代码页数记录：`软件著作权申请资料/校验预览/代码物理分页校验.json`
- 页面渲染记录：`软件著作权申请资料/校验预览/`
- 操作手册自检：`软件著作权申请资料/草稿/操作手册自检记录.md`
- 权属登记截图：`软件著作权申请资料/权属证明/合作开发登记截图.png`
