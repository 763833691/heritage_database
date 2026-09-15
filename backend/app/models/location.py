from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey
from sqlalchemy.orm import relationship
from ..core.database import Base


class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    park_id = Column(Integer, ForeignKey("parks.id"), nullable=False, unique=True)

    # 城市空间
    city_population = Column(Float, comment="城区常住人口(万人)")
    spatial_pattern = Column(String(200), comment="空间结构特征")
    urban_function = Column(String(200), comment="主导功能")

    # 文化设施
    nearby_facilities = Column(Text, comment="周边文化设施JSON")
    facility_density = Column(String(50), comment="设施密度评价")

    # 经济
    tertiary_gdp = Column(Float, comment="第三产业GDP(亿元)")
    tourism_gdp = Column(Float, comment="遗址推动文旅GDP(亿元)")
    cultural_projects = Column(Text, comment="文创产业项目")

    # 交通
    metro_stations = Column(Text, comment="地铁站")
    bus_routes = Column(Text, comment="公交线路")
    parking_info = Column(Text, comment="停车场信息")
    transport_score = Column(String(50), comment="交通便利性评价")

    # 旅游联动
    linked_attractions = Column(Text, comment="联动景区")
    marketing_mechanism = Column(Text, comment="联合营销机制")

    # 小结
    coordination_comment = Column(Text, comment="协调性小结")

    park = relationship("Park", back_populates="location")
