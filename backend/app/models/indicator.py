from sqlalchemy import Column, Integer, String, Float, Text
from ..core.database import Base


class Indicator(Base):
    __tablename__ = "indicators"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(10), unique=True, nullable=False, comment="指标编码D1-D27")
    name = Column(String(100), nullable=False, comment="指标名称")
    dimension = Column(String(50), nullable=False, comment="所属维度")
    sub_dimension = Column(String(50), comment="子维度")
    unit = Column(String(20), comment="单位")
    scoring_standard = Column(Text, comment="评分标准")
    weight_urban = Column(Float, comment="城市型权重")
    weight_suburb = Column(Float, comment="城郊型权重")
    weight_rural = Column(Float, comment="乡村型权重")
    data_source = Column(String(100), comment="数据来源")
    calculation_method = Column(Text, comment="计算方法")
