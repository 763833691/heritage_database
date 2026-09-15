from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings

_BACKEND_DIR = Path(__file__).resolve().parents[2]


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
    NEO4J_DATABASE: str = "neo4j"

    # ===== 知识图谱子系统（文件库 / 文本解析 / 图谱构建）=====
    KG_STORAGE_DIR: str = "./data/kg"
    KG_MAX_UPLOAD_MB: int = 200
    KG_MOCK_GRAPH: bool = False

    # 扫描件 PDF OCR（可选，需 pymupdf + Pillow）
    SCANNED_PDF_ZOOM: float = 2.0
    SCANNED_PDF_MAX_PAGES: int = 0
    SCANNED_PDF_MIN_CHARS_PER_PAGE: float = 30.0
    SCANNED_PDF_TIMEOUT_SECONDS: int = 120

    # 语音转写：腾讯云录音文件识别极速版（FlashRecognizer）
    TENCENT_APP_ID: str = ""
    TENCENT_SECRET_ID: str = ""
    TENCENT_SECRET_KEY: str = ""
    ASR_ENGINE_TYPE: str = "16k_zh"
    ASR_MAX_UPLOAD_MB: int = 20

    @property
    def storage_dir(self) -> Path:
        """知识图谱子系统的数据根目录（绝对路径）。"""
        path = Path(self.KG_STORAGE_DIR)
        return path if path.is_absolute() else _BACKEND_DIR / path

    @property
    def upload_dir(self) -> Path:
        return self.storage_dir / "uploads"

    @property
    def state_file(self) -> Path:
        return self.storage_dir / "state.json"

    @property
    def max_upload_size(self) -> int:
        return self.KG_MAX_UPLOAD_MB * 1024 * 1024

    @property
    def mock_graph_enabled(self) -> bool:
        return self.KG_MOCK_GRAPH

    @property
    def neo4j_enabled(self) -> bool:
        return self.NEO4J_ENABLED

    @property
    def neo4j_uri(self) -> str:
        return self.NEO4J_URI

    @property
    def neo4j_user(self) -> str:
        return self.NEO4J_USER

    @property
    def neo4j_password(self) -> str:
        return self.NEO4J_PASSWORD

    @property
    def neo4j_database(self) -> str:
        return self.NEO4J_DATABASE

    @property
    def openai_api_key(self) -> Optional[str]:
        return self.OPENAI_API_KEY or self.DASHSCOPE_API_KEY or None

    @property
    def openai_base_url(self) -> str:
        return self.LLM_BASE_URL or "https://api.openai.com/v1"

    @property
    def openai_model(self) -> str:
        return self.AI_MODEL

    @property
    def openai_vision_model(self) -> str:
        return self.AI_MODEL

    @property
    def scanned_pdf_zoom(self) -> float:
        return self.SCANNED_PDF_ZOOM

    @property
    def scanned_pdf_max_pages(self) -> Optional[int]:
        return self.SCANNED_PDF_MAX_PAGES or None

    @property
    def scanned_pdf_min_chars_per_page(self) -> float:
        return self.SCANNED_PDF_MIN_CHARS_PER_PAGE

    @property
    def scanned_pdf_timeout_seconds(self) -> int:
        return self.SCANNED_PDF_TIMEOUT_SECONDS

    @property
    def asr_max_upload_size(self) -> int:
        return self.ASR_MAX_UPLOAD_MB * 1024 * 1024

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
