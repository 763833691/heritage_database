# 国家考古遗址公园调研数据平台

一个面向国家考古遗址公园调研、评估、知识图谱和智能问答的一体化平台。仓库当前已经具备前后端骨架、数据库模型、统计接口、知识图谱脚本和 AI 问答雏形，适合作为课程项目、论文项目或可部署原型继续完善。

## 项目特性

- 调研数据管理：遗址公园、遗址点、评分、问卷、评论等结构化存储
- 数据分析：总览统计、分类型/分省份分布、维度对比、雷达图展示
- 知识图谱：基于关系数据库数据构建 Neo4j 图谱，支持实体、邻居和搜索
- AI 问答：基于 RAG 的问答流程，支持对比、统计、列表类问题
- 运维部署：支持本地开发和 Docker Compose 部署

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3、Element Plus、ECharts、Leaflet |
| 后端 | FastAPI、SQLAlchemy、Pydantic |
| 数据库 | PostgreSQL / SQLite（本地默认） |
| 图数据库 | Neo4j（可选） |
| 向量库 | ChromaDB（可选） |
| AI / RAG | LangChain、DashScope / OpenAI 配置、规则式本地回答 |
| 部署 | Docker、Docker Compose、Nginx |

## 目录结构

```text
datak/
├── backend/   # FastAPI 后端、模型、脚本、数据库初始化
├── frontend/  # Vue 3 前端
├── docker/    # Nginx 配置等部署文件
└── docs/      # 项目方案、数据库、字典、AI 方案、部署说明
```

## 快速开始

### 方式一：Docker Compose

1. 启动数据库服务

```bash
docker compose up -d postgres neo4j
```

2. 初始化后端数据库

```bash
docker compose run --rm backend python scripts/init_db.py
```

3. 如需构建知识图谱，先确保 `NEO4J_ENABLED=true` 已开启，再执行

```bash
docker compose run --rm backend python scripts/build_kg.py
```

4. 启动全部服务

```bash
docker compose up -d
```

5. 访问地址

- 前端：`http://localhost:3000`
- 后端文档：`http://localhost:8000/docs`
- Neo4j：`http://localhost:7474`

### 方式二：本地开发

1. 启动数据库服务

```bash
docker compose up -d postgres neo4j
```

2. 安装后端依赖并启动

```bash
cd backend
pip install -r requirements.txt
python scripts/init_db.py
uvicorn app.main:app --reload --port 8000
```

3. 安装前端依赖并启动

```bash
cd ../frontend
npm install
npm run dev
```

## 默认账号

初始化脚本会自动创建管理员账号：

- 用户名：`admin`
- 密码：`admin123`

## 配置说明

后端核心配置位于 `backend/app/core/config.py`，常用环境变量包括：

- `DB_TYPE`：`sqlite` 或 `postgres`
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`
- `NEO4J_ENABLED`
- `NEO4J_URI`
- `NEO4J_USER`
- `NEO4J_PASSWORD`
- `AI_PROVIDER`
- `DASHSCOPE_API_KEY`
- `OPENAI_API_KEY`
- `SECRET_KEY`

说明：

- 当前仓库默认支持 SQLite 本地模式，Docker 部署时推荐 PostgreSQL。
- 知识图谱构建和 Neo4j 查询需要显式开启 `NEO4J_ENABLED=true`。
- 现有 `RAGEngine` 仍以本地规则式回答为主，AI 密钥更偏向预留扩展配置。

## 文档入口

- [项目方案](docs/01-项目方案.md)
- [数据库架构设计](docs/02-数据库架构设计.md)
- [成本与周期估算](docs/03-成本与周期估算.md)
- [数据字典](docs/04-数据字典.md)
- [AI 知识图谱与聊天机器人方案](docs/05-AI知识图谱与聊天机器人方案.md)
- [部署与验收](docs/06-部署与验收.md)

## 建议阅读顺序

1. 先看 `docs/01-项目方案.md`，了解项目定位和整体架构。
2. 再看 `docs/02-数据库架构设计.md` 和 `docs/04-数据字典.md`，确认数据模型。
3. 接着看 `docs/05-AI知识图谱与聊天机器人方案.md`，理解图谱和问答链路。
4. 最后看 `docs/06-部署与验收.md` 和 `README_STARTUP.md`，完成启动和验收。
