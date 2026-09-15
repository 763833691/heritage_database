from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey
from sqlalchemy.orm import relationship
from ..core.database import Base


class Site(Base):
    __tablename__ = "sites"

    id = Column(Integer, primary_key=True, index=True)
    park_id = Column(Integer, ForeignKey("parks.id"), nullable=False, index=True)
    site_name = Column(String(100), nullable=False, comment="遗址点名称")
    site_type = Column(String(50), comment="类型：建筑基址/墓葬/窑址/水系等")
    period = Column(String(50), comment="所属时期")
    discovery_year = Column(Integer, comment="发现年份")
    excavation_year = Column(Integer, comment="发掘年份")
    area = Column(Float, comment="面积(平方米)")
    integrity_score = Column(Integer, comment="完整性评分(20-100)")
    safety_score = Column(Integer, comment="安全性评分(20-100)")
    description = Column(Text)
    coordinates = Column(Text, comment="坐标GeoJSON")

    park = relationship("Park", back_populates="sites")
