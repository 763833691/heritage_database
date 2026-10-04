from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from ..core.database import Base


class AnnotationTask(Base):
    """照片语义标注任务（从一个样本 JSON 导入）。"""

    __tablename__ = "annotation_tasks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    codebook_version = Column(String(20), default="v1.0")
    status = Column(String(20), default="open")  # open/closed
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AnnotationItem(Base):
    """标注样本条目：一张照片及其先验信息（盲标时不下发）。"""

    __tablename__ = "annotation_items"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("annotation_tasks.id"), index=True)
    sid = Column(String(20), index=True)          # 样本编号 S001…
    track_id = Column(Integer, index=True)
    photo_id = Column(Integer, ForeignKey("track_photo.id"))
    seq = Column(Integer)                          # 任务内展示顺序
    platform_type = Column(String(2))              # 平台规则分类（盲标不下发）
    ai_code = Column(String(2))                    # 智能体编码（盲标不下发）
    caption = Column(Text)                         # 仅结果页展示


class AnnotationRecord(Base):
    """编码者对一个条目的编码（同一 item+coder 覆盖更新）。"""

    __tablename__ = "annotation_records"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("annotation_items.id"), index=True)
    coder = Column(String(50), index=True)
    code = Column(String(2))                       # A–G
    note = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now())
    __table_args__ = (UniqueConstraint("item_id", "coder", name="uq_item_coder"),)
