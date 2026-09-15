import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from .config import settings

# ============ 确保数据目录存在 ============
import os as _os
_BASE_DIR = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
if settings.DB_TYPE == "sqlite":
    # 将相对路径转为绝对路径，避免工作目录变化导致的问题
    sqlite_path = settings.SQLITE_PATH
    if not _os.path.isabs(sqlite_path):
        sqlite_path = _os.path.join(_BASE_DIR, sqlite_path.lstrip("./"))
    _os.makedirs(_os.path.dirname(sqlite_path), exist_ok=True)
else:
    _os.makedirs(".", exist_ok=True)

# ============ 数据库引擎 ============
if settings.DB_TYPE == "sqlite":
    engine = create_engine(
        f"sqlite:///{sqlite_path}",
        connect_args={"check_same_thread": False},
        echo=False,
    )
else:
    engine = create_engine(
        settings.DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============ Neo4j（可选）============
neo4j_driver = None

if settings.NEO4J_ENABLED:
    try:
        from neo4j import GraphDatabase
        neo4j_driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
        )
        print("[OK] Neo4j connected")
    except Exception as e:
        print(f"[WARN] Neo4j connection failed: {e}")


def get_neo4j():
    """获取Neo4j会话"""
    if neo4j_driver:
        return neo4j_driver.session()
    return None


# ============ ChromaDB（可选）============
chroma_client = None
chroma_collection = None
literature_chroma_collection = None

try:
    import chromadb
    os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
    chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
    chroma_collection = chroma_client.get_or_create_collection(
        name=settings.CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )
    literature_chroma_collection = chroma_client.get_or_create_collection(
        name="literature_kb",
        metadata={"hnsw:space": "cosine"},
    )
    print("[OK] ChromaDB initialized (2 collections)")
except Exception as e:
    print(f"[WARN] ChromaDB not available: {e}")


def get_chroma_collection():
    """获取ChromaDB集合"""
    return chroma_collection


def get_literature_chroma():
    """获取文献知识库 ChromaDB 集合"""
    return literature_chroma_collection
