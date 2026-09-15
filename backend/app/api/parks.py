from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List

from ..core.database import get_db
from ..core.auth import get_current_user
from ..models.park import Park
from ..models.score import Score
from ..models.indicator import Indicator
from ..schemas.park import ParkResponse, ParkListResponse, ScoreInfo

router = APIRouter()


def build_park_response(park, db):
    """构建公园响应数据"""
    scores = (
        db.query(Score, Indicator)
        .join(Indicator, Score.indicator_id == Indicator.id)
        .filter(Score.park_id == park.id)
        .all()
    )
    score_list = [
        ScoreInfo(
            indicator_code=ind.code,
            indicator_name=ind.name,
            dimension=ind.dimension,
            score=sc.normalized_score,
            grade=sc.grade,
        )
        for sc, ind in scores
    ]

    return ParkResponse(
        id=park.id,
        name=park.name,
        short_name=park.short_name,
        park_type=park.park_type,
        batch=park.batch,
        province=park.province,
        city=park.city,
        district=park.district,
        longitude=park.longitude,
        latitude=park.latitude,
        total_area=park.total_area,
        core_area=park.core_area,
        world_heritage=park.world_heritage or 0,
        aaa_level=park.aaa_level,
        open_year=park.open_year,
        description=park.description,
        scores=score_list,
    )


@router.get("", response_model=ParkListResponse)
async def list_parks(
    park_type: Optional[str] = Query(None),
    province: Optional[str] = Query(None),
    batch: Optional[int] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Park)

    if park_type:
        query = query.filter(Park.park_type == park_type)
    if province:
        query = query.filter(Park.province == province)
    if batch:
        query = query.filter(Park.batch == batch)
    if keyword:
        query = query.filter(
            Park.name.contains(keyword) | Park.short_name.contains(keyword)
        )

    total = query.count()
    parks = query.offset((page - 1) * page_size).limit(page_size).all()

    result = [build_park_response(park, db) for park in parks]

    return ParkListResponse(total=total, items=result)


@router.get("/{park_id}", response_model=ParkResponse)
async def get_park(park_id: int, db: Session = Depends(get_db)):
    park = db.query(Park).filter(Park.id == park_id).first()
    if not park:
        raise HTTPException(status_code=404, detail="遗址公园不存在")
    return build_park_response(park, db)


@router.get("/{park_id}/sites")
async def get_park_sites(park_id: int, db: Session = Depends(get_db)):
    from ..models.site import Site
    park = db.query(Park).filter(Park.id == park_id).first()
    if not park:
        raise HTTPException(status_code=404, detail="遗址公园不存在")
    sites = db.query(Site).filter(Site.park_id == park_id).all()
    return [
        {
            "id": s.id, "site_name": s.site_name, "site_type": s.site_type,
            "period": s.period, "integrity_score": s.integrity_score,
            "safety_score": s.safety_score, "description": s.description,
        }
        for s in sites
    ]


@router.get("/{park_id}/scores")
async def get_park_scores(park_id: int, db: Session = Depends(get_db)):
    park = db.query(Park).filter(Park.id == park_id).first()
    if not park:
        raise HTTPException(status_code=404, detail="遗址公园不存在")

    scores = (
        db.query(Score, Indicator)
        .join(Indicator, Score.indicator_id == Indicator.id)
        .filter(Score.park_id == park_id)
        .order_by(Indicator.code)
        .all()
    )
    return [
        {
            "code": ind.code,
            "name": ind.name,
            "dimension": ind.dimension,
            "sub_dimension": ind.sub_dimension,
            "score": sc.normalized_score,
            "grade": sc.grade,
            "evidence": sc.evidence,
        }
        for sc, ind in scores
    ]
