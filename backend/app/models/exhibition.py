from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey
from sqlalchemy.orm import relationship
from ..core.database import Base


class Exhibition(Base):
    __tablename__ = "exhibitions"

    id = Column(Integer, primary_key=True, index=True)
    park_id = Column(Integer, ForeignKey("parks.id"), nullable=False, unique=True)

    # 硬件设施
    signage_system = Column(Text, comment="标识系统描述")
    signage_count = Column(Integer, comment="标识牌数量")
    museum_count = Column(Integer, comment="博物馆数量")
    museum_area = Column(Float, comment="博物馆面积(平方米)")
    protection_facilities = Column(Text, comment="保护展示设施")

    # 软件载体
    media_types = Column(Text, comment="传播媒介类型JSON")
    media_count = Column(Integer, comment="传播媒介数量")
    online_media = Column(Text, comment="线上媒介")
    offline_media = Column(Text, comment="线下媒介")
    cooperation_media = Column(Text, comment="合作媒介")

    # 数字化
    digital_projects = Column(Text, comment="数字化项目")
    vr_ar_projects = Column(Text, comment="VR/AR项目")

    # 叙事
    narrative_theme = Column(Text, comment="叙事主题")
    hot_words = Column(Text, comment="网络热词")

    # 文创
    product_count = Column(Integer, comment="文创产品数量")
    product_categories = Column(Text, comment="产品类别")

    # 评分
    d6_score = Column(Integer, comment="遗址信息丰富度")
    d7_score = Column(Integer, comment="遗址文化吸引力")
    d8_score = Column(Integer, comment="传播媒介丰富度")
    d9_score = Column(Integer, comment="展示设施阐释力")

    park = relationship("Park", back_populates="exhibition")
