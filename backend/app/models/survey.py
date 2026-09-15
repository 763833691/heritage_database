from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey
from sqlalchemy.orm import relationship
from ..core.database import Base


class Survey(Base):
    __tablename__ = "surveys"

    id = Column(Integer, primary_key=True, index=True)
    park_id = Column(Integer, ForeignKey("parks.id"), nullable=False, index=True)
    survey_date = Column(String(20), comment="调查日期")
    survey_location = Column(String(100), comment="调查地点")
    total_distributed = Column(Integer, comment="发放数量")
    total_collected = Column(Integer, comment="回收数量")
    valid_count = Column(Integer, comment="有效问卷数")
    valid_rate = Column(Float, comment="有效率")
    sampling_method = Column(String(100), comment="抽样方法")

    park = relationship("Park", back_populates="surveys")
    answers = relationship("SurveyAnswer", back_populates="survey", cascade="all, delete-orphan")


class SurveyAnswer(Base):
    __tablename__ = "survey_answers"

    id = Column(Integer, primary_key=True, index=True)
    survey_id = Column(Integer, ForeignKey("surveys.id"), nullable=False, index=True)
    respondent_id = Column(String(20), comment="受访者编号")
    question_code = Column(String(20), nullable=False, comment="题目编码")
    question_text = Column(Text, comment="题目内容")
    answer_value = Column(Integer, comment="量表值(1-5)")
    answer_text = Column(Text, comment="开放题回答")
    respondent_age = Column(String(20), comment="年龄段")
    respondent_gender = Column(String(10), comment="性别")
    respondent_education = Column(String(20), comment="学历")
    visit_purpose = Column(String(50), comment="到访目的")
    visit_frequency = Column(String(20), comment="到访频次")
    transport_mode = Column(String(20), comment="交通方式")

    survey = relationship("Survey", back_populates="answers")
