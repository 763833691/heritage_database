from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..core.database import Base


class TrackFile(Base):
    """一次田野调研上传的 KML 轨迹文件。"""

    __tablename__ = "track_file"

    id = Column(Integer, primary_key=True, index=True)
    original_name = Column(String(255), nullable=False, comment="原始 KML 文件名")
    kml_path = Column(String(500), comment="KML 原始文件落盘路径")
    geojson_path = Column(String(500), comment="轨迹 GeoJSON 落盘路径")
    survey_task_id = Column(Integer, ForeignKey("survey_tasks.id"), nullable=True, index=True, comment="关联调研任务")

    status = Column(String(20), default="pending", index=True,
                    comment="pending/parsing/downloading/geocoding/describing/done/failed")
    stage = Column(String(30), default="pending", comment="当前阶段，前端进度展示用")
    progress_done = Column(Integer, default=0, comment="当前阶段已完成数")
    progress_total = Column(Integer, default=0, comment="当前阶段总数")

    track_point_count = Column(Integer, default=0, comment="轨迹点数")
    photo_count = Column(Integer, default=0, comment="照片点数")
    distance_meters = Column(Float, comment="轨迹总里程(米)")
    start_time = Column(DateTime, comment="轨迹起始时间")
    end_time = Column(DateTime, comment="轨迹结束时间")
    start_address = Column(String(500), comment="起点语义地址")
    end_address = Column(String(500), comment="终点语义地址")
    error_message = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    photos = relationship("TrackPhoto", back_populates="track", cascade="all, delete-orphan")


class TrackPhoto(Base):
    """KML 中的照片标注点及其语义化结果。"""

    __tablename__ = "track_photo"

    id = Column(Integer, primary_key=True, index=True)
    track_id = Column(Integer, ForeignKey("track_file.id"), nullable=False, index=True)
    seq = Column(Integer, default=0, comment="在 KML 中的顺序，用于重试时复用记录")

    file_name = Column(String(255), comment="原始文件名")
    file_path = Column(String(500), comment="原图本地路径")
    thumb_path = Column(String(500), comment="缩略图本地路径")
    source_url = Column(String(1000), comment="照片下载 URL")

    shot_time = Column(DateTime, comment="拍摄时间")
    longitude = Column(Float)
    latitude = Column(Float)
    altitude = Column(Float, comment="海拔(米)")
    speed = Column(Float, comment="速度")
    accuracy = Column(Float, comment="定位精度")

    province = Column(String(50))
    city = Column(String(50))
    district = Column(String(50))
    street = Column(String(100))
    poi = Column(String(200), comment="附近 POI")
    address = Column(String(500), comment="完整语义地址")

    description = Column(Text, comment="多模态模型生成的中文语义描述")
    caption = Column(String(500), comment="报告图注短句")
    tags = Column(Text, default="[]", comment="主题标签 JSON 数组")

    download_status = Column(String(20), default="pending", comment="pending/success/failed/skipped")
    describe_status = Column(String(20), default="pending", comment="pending/success/failed/skipped")
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    track = relationship("TrackFile", back_populates="photos")
