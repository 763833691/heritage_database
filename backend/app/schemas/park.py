from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class ParkCreate(BaseModel):
    name: str
    short_name: Optional[str] = None
    park_type: str
    batch: Optional[int] = None
    province: str
    city: str
    district: Optional[str] = None
    address: Optional[str] = None
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    total_area: Optional[float] = None
    core_area: Optional[float] = None
    buffer_area: Optional[float] = None
    protection_level: Optional[str] = None
    heritage_level: Optional[str] = None
    world_heritage: int = 0
    aaa_level: Optional[str] = None
    open_year: Optional[int] = None
    description: Optional[str] = None


class ParkUpdate(BaseModel):
    name: Optional[str] = None
    short_name: Optional[str] = None
    park_type: Optional[str] = None
    batch: Optional[int] = None
    province: Optional[str] = None
    city: Optional[str] = None
    total_area: Optional[float] = None
    aaa_level: Optional[str] = None
    description: Optional[str] = None


class ScoreInfo(BaseModel):
    indicator_code: str
    indicator_name: str
    dimension: str
    score: Optional[int]
    grade: Optional[str]

    class Config:
        from_attributes = True


class ParkResponse(BaseModel):
    id: int
    name: str
    short_name: Optional[str]
    park_type: str
    batch: Optional[int]
    province: str
    city: str
    district: Optional[str]
    longitude: Optional[float]
    latitude: Optional[float]
    total_area: Optional[float]
    core_area: Optional[float]
    world_heritage: int
    aaa_level: Optional[str]
    open_year: Optional[int]
    description: Optional[str]
    scores: List[ScoreInfo] = []

    class Config:
        from_attributes = True


class ParkListResponse(BaseModel):
    total: int
    items: List[ParkResponse]
