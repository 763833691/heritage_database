#!/bin/bash

echo "=========================================="
echo "  国家考古遗址公园智能研究平台 - 启动脚本"
echo "=========================================="
echo ""

# 检查Docker
if ! command -v docker &> /dev/null; then
    echo "❌ 请先安装Docker"
    exit 1
fi

# 检查环境配置
if [ ! -f backend/.env ]; then
    echo "⚠️  未检测到环境配置文件"
    echo "   正在从示例文件创建..."
    cp backend/.env.example backend/.env
    echo "   请编辑 backend/.env 填入AI API密钥"
    echo ""
fi

# 选择启动方式
echo "请选择启动方式："
echo "1) Docker Compose (推荐，一键启动所有服务)"
echo "2) 本地开发模式 (需要分别启动前后端)"
echo ""
read -p "请输入选项 [1]: " choice
choice=${choice:-1}

if [ "$choice" = "1" ]; then
    echo ""
    echo "🚀 使用Docker Compose启动..."
    echo ""

    # 启动数据库服务
    docker-compose up -d postgres neo4j
    echo "⏳ 等待数据库启动..."
    sleep 10

    # 初始化数据库
    echo "📦 初始化数据库..."
    docker-compose run --rm backend python scripts/init_db.py

    # 构建知识图谱（仅在启用Neo4j时）
    if grep -q "NEO4J_ENABLED=true" backend/.env 2>/dev/null; then
        echo "🕸️  构建知识图谱..."
        docker-compose run --rm backend python scripts/build_kg.py
    else
        echo "ℹ️  跳过知识图谱构建（NEO4J_ENABLED 未开启）"
    fi

    # 启动所有服务
    echo "🚀 启动所有服务..."
    docker-compose up -d

    echo ""
    echo "=========================================="
    echo "✅ 启动完成！"
    echo ""
    echo "  前端地址: http://localhost:3000"
    echo "  API文档: http://localhost:8000/docs"
    echo "  Neo4j:   http://localhost:7474"
    echo ""
    echo "  默认账户: admin / admin123"
    echo "=========================================="

else
    echo ""
    echo "🚀 本地开发模式启动..."
    echo ""

    # 启动数据库
    echo "📦 启动数据库..."
    docker-compose up -d postgres neo4j
    sleep 10

    # 初始化数据库
    echo "📦 初始化数据库..."
    cd backend
    python scripts/init_db.py

    # 构建知识图谱（仅在启用Neo4j时）
    if grep -q "NEO4J_ENABLED=true" backend/.env 2>/dev/null; then
        echo "🕸️  构建知识图谱..."
        python scripts/build_kg.py
    else
        echo "ℹ️  跳过知识图谱构建（NEO4J_ENABLED 未开启）"
    fi
    cd ..

    echo ""
    echo "=========================================="
    echo "✅ 数据库初始化完成！"
    echo ""
    echo "请在两个终端中分别运行："
    echo ""
    echo "终端1 (后端):"
    echo "  cd backend"
    echo "  uvicorn app.main:app --reload --port 8000"
    echo ""
    echo "终端2 (前端):"
    echo "  cd frontend"
    echo "  npm install"
    echo "  npm run dev"
    echo ""
    echo "然后访问: http://localhost:3000"
    echo "默认账户: admin / admin123"
    echo "=========================================="
fi
