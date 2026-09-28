from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..core.database import Base


class Survey(Base):
    __tablename__ = "surveys"

    id = Column(Integer, primary_key=True, index=True)
    park_id = Column(Integer, ForeignKey("parks.id"), nullable=False, index=True)
    survey_date = Column(String(20), comment="调查日期")
    survey_location = Column(String(100), comment="调查地点")
    total_distributed = Column(Integer, comment="发放数量")
    total_collected = Column(Integer, comment="回收数量")
    valid_count = Column(Integer, comment="有效问卷数")
    valid_rate = Column(Float, comment="有效率")
    sampling_method = Column(String(100), comment="抽样方法")

    park = relationship("Park", back_populates="surveys")
    answers = relationship("SurveyAnswer", back_populates="survey", cascade="all, delete-orphan")


class SurveyAnswer(Base):
    __tablename__ = "survey_answers"

    id = Column(Integer, primary_key=True, index=True)
    survey_id = Column(Integer, ForeignKey("surveys.id"), nullable=False, index=True)
    respondent_id = Column(String(20), comment="受访者编号")
    question_code = Column(String(20), nullable=False, comment="题目编码")
    question_text = Column(Text, comment="题目内容")
    answer_value = Column(Integer, comment="量表值(1-5)")
    answer_text = Column(Text, comment="开放题回答")
    respondent_age = Column(String(20), comment="年龄段")
    respondent_gender = Column(String(10), comment="性别")
    respondent_education = Column(String(20), comment="学历")
    visit_purpose = Column(String(50), comment="到访目的")
    visit_frequency = Column(String(20), comment="到访频次")
    transport_mode = Column(String(20), comment="交通方式")

    survey = relationship("Survey", back_populates="answers")


class SurveyTask(Base):
    """田野调研任务：一次调研 = 一个任务 = 一篇报告。"""

    __tablename__ = "survey_tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, comment="调研任务标题")
    park_id = Column(Integer, ForeignKey("parks.id"), nullable=True, index=True, comment="关联遗址公园(可空)")
    survey_date = Column(String(20), comment="调研日期")
    status = Column(String(20), default="draft", index=True, comment="draft/processing/review/ready")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    events = relationship("SurveyEvent", back_populates="task", cascade="all, delete-orphan")
    reports = relationship("SurveyReport", back_populates="task", cascade="all, delete-orphan")


class SurveyEvent(Base):
    """调研事件：语义化后的统一单元（MVP 主要为轨迹照片事件）。"""

    __tablename__ = "survey_events"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("survey_tasks.id"), nullable=False, index=True)
    event_type = Column(String(20), default="photo", index=True, comment="photo/audio/literature")
    timestamp = Column(DateTime, index=True, comment="事件时间戳")
    longitude = Column(Float)
    latitude = Column(Float)
    address = Column(String(500), comment="语义地址（省市区街道POI）")
    title = Column(String(300), comment="标题/图注短句")
    content = Column(Text, comment="正文/语义描述")
    source_material_id = Column(Integer, comment="来源材料 id（track_photo.id）")
    source_type = Column(String(30), default="track_photo", comment="来源材料类型")
    tags = Column(Text, default="[]", comment="主题标签 JSON 数组")
    usable_for_report = Column(Boolean, default=True, comment="是否可用于报告")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    task = relationship("SurveyTask", back_populates="events")


class SurveyReport(Base):
    """调研报告实例：MVP 只生成第二章「调研过程」。"""

    __tablename__ = "survey_report"
    __table_args__ = (UniqueConstraint("task_id", "chapter", name="uq_survey_report_task_chapter"),)

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("survey_tasks.id"), nullable=False, index=True)
    chapter = Column(String(30), default="chapter2", index=True, comment="章节标识")
    content = Column(Text, comment="章节内容 JSON")
    citations = Column(Text, comment="引用清单 JSON")
    docx_path = Column(String(500), comment="导出的 docx 路径")
    status = Column(String(20), default="draft", comment="draft/generating/done/failed")
    version = Column(Integer, default=1)
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    task = relationship("SurveyTask", back_populates="reports")
