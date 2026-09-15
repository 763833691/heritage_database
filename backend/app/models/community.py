from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from ..core.database import Base


class Community(Base):
    __tablename__ = "communities"

    id = Column(Integer, primary_key=True, index=True)
    park_id = Column(Integer, ForeignKey("parks.id"), nullable=False, index=True)
    cooperation_type = Column(String(50), comment="合作类型")
    partner_name = Column(String(100), comment="合作方名称")
    partner_type = Column(String(50), comment="合作方类型：高校/社区/企业")
    activities = Column(Text, comment="合作活动")
    benefits = Column(Text, comment="惠民政策")
    volunteer_count = Column(Integer, comment="志愿者数量")

    park = relationship("Park", back_populates="communities")
