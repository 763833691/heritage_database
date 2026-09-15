from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey
from sqlalchemy.orm import relationship
from ..core.database import Base


class Score(Base):
    __tablename__ = "scores"

    id = Column(Integer, primary_key=True, index=True)
    park_id = Column(Integer, ForeignKey("parks.id"), nullable=False, index=True)
    indicator_id = Column(Integer, ForeignKey("indicators.id"), nullable=False, index=True)
    raw_value = Column(Float, comment="原始值")
    normalized_score = Column(Integer, comment="标准化得分(20/40/60/80/100)")
    grade = Column(String(10), comment="等级：好/较好/一般/较差/差")
    evidence = Column(Text, comment="评分依据")
    data_year = Column(Integer, comment="数据年份")
    evaluator = Column(String(50), comment="评估人")

    park = relationship("Park", back_populates="scores")
    indicator = relationship("Indicator")
