"""文献与引文关系模型"""
from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..core.database import Base


class Literature(Base):
    __tablename__ = "literatures"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False, comment="标题")
    authors = Column(Text, comment="JSON: [{\"name\":\"...\",\"institution\":\"...\"}]")
    year = Column(Integer, index=True, comment="出版年份")
    journal = Column(String(200), comment="期刊/来源")
    keywords = Column(Text, comment="JSON: [\"kw1\",\"kw2\"]")
    abstract = Column(Text, comment="摘要")
    doc_type = Column(String(30), comment="文献类型")
    funding = Column(String(200), comment="基金信息")
    methodology = Column(Text, comment="研究方法")
    core_argument = Column(Text, comment="核心论点")
    file_path = Column(String(500), comment="原始文件路径")
    wiki_path = Column(String(500), comment="知识页路径")
    raw_metadata = Column(Text, comment="LLM返回的完整JSON")
    vector_id = Column(String(100), comment="ChromaDB向量ID")
    citation_count = Column(Integer, default=0, comment="被引次数(库内)")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关系
    citations_from = relationship(
        "Citation",
        foreign_keys="Citation.source_id",
        back_populates="source",
        cascade="all, delete-orphan",
    )
    citations_to = relationship(
        "Citation",
        foreign_keys="Citation.target_id",
        back_populates="target",
    )


class Citation(Base):
    __tablename__ = "citations"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("literatures.id"), nullable=False, index=True)
    target_title = Column(String(500), comment="被引文献标题")
    target_author = Column(String(100), comment="被引文献作者")
    target_year = Column(Integer, comment="被引文献年份")
    target_id = Column(Integer, ForeignKey("literatures.id"), nullable=True, index=True,
                      comment="如果被引文献也在库中，记录其ID")

    source = relationship("Literature", foreign_keys=[source_id], back_populates="citations_from")
    target = relationship("Literature", foreign_keys=[target_id], back_populates="citations_to")


class LitRelation(Base):
    """文献间语义关系"""
    __tablename__ = "lit_relations"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("literatures.id"), nullable=False)
    target_id = Column(Integer, ForeignKey("literatures.id"), nullable=False)
    relation_type = Column(String(30), comment="cites/supports/contradicts/complements/shares_topic")
    strength = Column(Float, default=0.5)
    explanation = Column(Text)
