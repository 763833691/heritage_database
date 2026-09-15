# 启动与部署说明

本文档用于把项目从“克隆仓库”快速推进到“可访问、可验证”的状态。当前仓库支持两种使用方式：

- Docker Compose 部署：适合演示、答辩和统一环境
- 本地开发模式：适合调试前后端和数据库脚本

## 1. 启动前准备

### 必需环境

- Docker Desktop
- Python 3.10+
- Node.js 18+

### 建议配置

- PostgreSQL 和 Neo4j 通过 Docker 启动
- 后端优先使用 `backend/.env` 或系统环境变量管理配置

## 2. Docker Compose 部署

### 2.1 启动数据库

```bash
docker compose up -d postgres neo4j
```

### 2.2 初始化数据库

初始化脚本会创建表结构、管理员账号和示例数据：

```bash
docker compose run --rm backend python scripts/init_db.py
```

默认管理员账号：

- 用户名：`admin`
- 密码：`admin123`

### 2.3 如需构建知识图谱

知识图谱构建脚本依赖 Neo4j。请先确保环境变量中开启：

```bash
NEO4J_ENABLED=true
```

然后执行：

```bash
docker compose run --rm backend python scripts/build_kg.py
```

### 2.4 启动全部服务

```bash
docker compose up -d
```

### 2.5 访问地址

- 前端：`http://localhost:3000`
- 后端 OpenAPI：`http://localhost:8000/docs`
- Neo4j Browser：`http://localhost:7474`

## 3. 本地开发模式

### 3.1 启动数据库

```bash
docker compose up -d postgres neo4j
```

### 3.2 后端

```bash
cd backend
pip install -r requirements.txt
python scripts/init_db.py
uvicorn app.main:app --reload --port 8000
```

### 3.3 前端

```bash
cd frontend
npm install
npm run dev
```

## 4. 关键环境变量

后端配置见 `backend/app/core/config.py`，常用变量如下：

```bash
DB_TYPE=postgres
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=heritage
POSTGRES_PASSWORD=heritage123
POSTGRES_DB=heritage_db

NEO4J_ENABLED=true
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=heritage123

AI_PROVIDER=mock
DASHSCOPE_API_KEY=
OPENAI_API_KEY=
```

说明：

- `DB_TYPE=sqlite` 时，后端会退回到本地 `backend/data/heritage.db`。
- `AI_PROVIDER` 目前更多是预留扩展位，现有问答引擎仍以本地规则式 RAG 为主。
- 如果不打算构建知识图谱，可以不执行 `build_kg.py`。

## 5. 验收清单

启动完成后，建议依次确认：

1. `http://localhost:8000/health` 返回 `{"status":"ok"}`
2. `/docs` 能打开 FastAPI 文档页
3. 前端登录页可以正常访问
4. 使用 `admin/admin123` 登录成功
5. `数据总览` 页能加载统计数据
6. `知识图谱` 和 `AI 助手` 页面至少能返回基础结果或降级提示

## 6. 常见问题

### 6.1 登录失败

- 确认是否已经执行 `python scripts/init_db.py`
- 确认账号是否为 `admin/admin123`

### 6.2 知识图谱构建失败

- 检查 `NEO4J_ENABLED=true` 是否已设置
- 检查 Neo4j 服务是否已启动
- 检查 `NEO4J_URI`、用户名和密码是否正确

### 6.3 前端请求 401

- 确认是否已登录
- 确认本地存储中的 token 是否过期

### 6.4 AI 问答只有模板式回答

- 这是当前实现的正常行为
- 现有 `RAGEngine` 仍以本地检索 + 规则式生成结果为主

