from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey
from sqlalchemy.orm import relationship
from ..core.database import Base


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    park_id = Column(Integer, ForeignKey("parks.id"), nullable=False, index=True)
    platform = Column(String(20), nullable=False, comment="平台：携程/美团/小红书/微博")
    review_date = Column(String(20), comment="评论日期")
    review_text = Column(Text, comment="评论内容")
    rating = Column(Float, comment="评分")
    sentiment_score = Column(Float, comment="情感得分(-1到1)")
    sentiment_label = Column(String(10), comment="情感标签")
    keywords = Column(Text, comment="关键词")
    source_url = Column(Text, comment="原文链接")

    park = relationship("Park", back_populates="reviews")
