from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..core.database import Base


class AIModel(Base):
    """可调用的模型（厂商 + 端点 + 上游模型 id + 加密凭证）。"""

    __tablename__ = "ai_model"

    id = Column(Integer, primary_key=True, index=True)
    alias = Column(String(80), nullable=False, unique=True, index=True, comment="模型别名，任务路由引用它")
    display_name = Column(String(200), comment="显示名")
    provider_type = Column(String(50), default="openai_compatible", comment="厂商类型")
    capability = Column(String(20), default="text", comment="text/vision/multimodal/image/video")
    base_url = Column(String(500), nullable=False, comment="OpenAI 兼容端点根地址")
    model = Column(String(200), nullable=False, comment="上游模型 id")
    api_key_encrypted = Column(Text, comment="Fernet 加密后的 API Key（enc:v1: 前缀）")
    api_key_env = Column(String(100), comment="可选：从环境变量读取 Key（优先级低于显式 Key）")
    input_modalities = Column(JSON, default=list)
    output_modalities = Column(JSON, default=list)
    enabled = Column(Boolean, default=False, comment="启用后才可被任务路由使用")
    is_preset = Column(Boolean, default=False, comment="是否为预置模型")
    note = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    routes = relationship("AIModelRoute", back_populates="model", cascade="all, delete-orphan")


class AIModelRoute(Base):
    """任务 -> 模型 的路由绑定。"""

    __tablename__ = "ai_model_route"
    __table_args__ = (UniqueConstraint("task", name="uq_ai_model_route_task"),)

    id = Column(Integer, primary_key=True, index=True)
    task = Column(String(80), nullable=False, index=True, comment="任务名，如 text.chat / vision.describe")
    model_id = Column(Integer, ForeignKey("ai_model.id", ondelete="CASCADE"), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    model = relationship("AIModel", back_populates="routes")
