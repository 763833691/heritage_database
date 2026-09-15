from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from ..core.database import Base


class EducationActivity(Base):
    __tablename__ = "education_activities"

    id = Column(Integer, primary_key=True, index=True)
    park_id = Column(Integer, ForeignKey("parks.id"), nullable=False, index=True)
    activity_name = Column(String(200), nullable=False, comment="活动名称")
    activity_type = Column(String(50), comment="类型：研学/展览/节庆/讲座")
    start_date = Column(String(20), comment="开始日期")
    end_date = Column(String(20), comment="结束日期")
    frequency = Column(String(50), comment="频次")
    target_audience = Column(String(100), comment="目标受众")
    participant_count = Column(Integer, comment="参与人数")
    description = Column(Text)

    park = relationship("Park", back_populates="education_activities")
