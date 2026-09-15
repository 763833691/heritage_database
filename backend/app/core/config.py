from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # 应用配置
    APP_NAME: str = "国家考古遗址公园智能研究平台"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # 数据库 - 默认使用SQLite（无需Docker）
    DB_TYPE: str = "sqlite"  # sqlite / postgres
    SQLITE_PATH: str = "./data/heritage.db"

    # PostgreSQL（如果DB_TYPE=postgres）
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "heritage"
    POSTGRES_PASSWORD: str = "heritage123"
    POSTGRES_DB: str = "heritage_db"

    @property
    def DATABASE_URL(self) -> str:
        if self.DB_TYPE == "sqlite":
            return f"sqlite:///{self.SQLITE_PATH}"
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Neo4j（可选）
    NEO4J_ENABLED: bool = False
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "heritage123"

    # AI配置
    AI_PROVIDER: str = "mock"  # dashscope / openai / mock
    DASHSCOPE_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    AI_MODEL: str = "qwen-plus"
    AI_MAX_TOKENS: int = 2048
    AI_TEMPERATURE: float = 0.7
    AI_FALLBACK_TO_MOCK: bool = True
    AI_STREAMING_ENABLED: bool = True
    LLM_BASE_URL: str = ""  # OpenAI兼容接口地址（留空使用默认）

    @property
    def ai_available(self) -> bool:
        """检查是否配置了有效的 AI 提供商（排除占位符key）"""
        if self.AI_PROVIDER == "mock":
            return False
        if self.AI_PROVIDER == "dashscope":
            key = self.DASHSCOPE_API_KEY
            if not key or "your_" in key or not key.startswith("sk-"):
                return False
        if self.AI_PROVIDER == "openai":
            key = self.OPENAI_API_KEY
            if not key or "your_" in key or not key.startswith("sk-"):
                return False
        return True

    # 登录开关：False 跳过登录验证，True 恢复登录
    AUTH_ENABLED: bool = False

    # JWT认证
    SECRET_KEY: str = "heritage-park-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # ChromaDB
    CHROMA_PERSIST_DIR: str = "./data/chroma"
    CHROMA_COLLECTION: str = "heritage_docs"

    # 文件上传
    UPLOAD_DIR: str = "./data/uploads"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
