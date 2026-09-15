from sqlalchemy import Column, Integer, String, Float, Text, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..core.database import Base


class Park(Base):
    __tablename__ = "parks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="公园全称")
    short_name = Column(String(50), comment="简称")
    park_type = Column(String(20), nullable=False, index=True, comment="类型：城市型/城郊型/乡村型")
    batch = Column(Integer, comment="评定批次(1-5)")

    # 地理信息
    province = Column(String(20), nullable=False, index=True)
    city = Column(String(30), nullable=False)
    district = Column(String(30))
    address = Column(String(200))
    longitude = Column(Float, comment="经度WGS84")
    latitude = Column(Float, comment="纬度WGS84")

    # 面积
    total_area = Column(Float, comment="总面积(平方公里)")
    core_area = Column(Float, comment="核心保护区面积")
    buffer_area = Column(Float, comment="缓冲区面积")

    # 保护级别
    protection_level = Column(String(100), comment="文保级别")
    heritage_level = Column(String(100), comment="遗产级别")
    world_heritage = Column(Integer, default=0, comment="是否世界遗产")
    aaa_level = Column(String(10), comment="A级景区")

    # 时间
    open_year = Column(Integer, comment="开园年份")
    establishment_date = Column(String(20), comment="立项日期")

    # 其他
    official_url = Column(String(200))
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 关系
    sites = relationship("Site", back_populates="park", cascade="all, delete-orphan")
    location = relationship("Location", back_populates="park", uselist=False)
    exhibition = relationship("Exhibition", back_populates="park", uselist=False)
    scores = relationship("Score", back_populates="park", cascade="all, delete-orphan")
    surveys = relationship("Survey", back_populates="park", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="park", cascade="all, delete-orphan")
    education_activities = relationship("EducationActivity", back_populates="park", cascade="all, delete-orphan")
    communities = relationship("Community", back_populates="park", cascade="all, delete-orphan")
