from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..core.database import get_db
from ..core.auth import get_current_user
from ..models.park import Park
from ..models.site import Site
from ..models.score import Score
from ..models.indicator import Indicator
from ..models.user import User

router = APIRouter()


@router.get("/overview")
async def overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """数据概览"""
    total_parks = db.query(Park).count()
    total_sites = db.query(Site).count()
    total_indicators = db.query(Indicator).count()

    # 按类型统计
    type_stats = (
        db.query(Park.park_type, func.count(Park.id))
        .group_by(Park.park_type)
        .all()
    )

    # 按省份统计
    province_stats = (
        db.query(Park.province, func.count(Park.id))
        .group_by(Park.province)
        .all()
    )

    # 按批次统计
    batch_stats = (
        db.query(Park.batch, func.count(Park.id))
        .filter(Park.batch.isnot(None))
        .group_by(Park.batch)
        .all()
    )

    return {
        "total_parks": total_parks,
        "total_sites": total_sites,
        "total_indicators": total_indicators,
        "by_type": {t: c for t, c in type_stats},
        "by_province": {p: c for p, c in province_stats},
        "by_batch": {b: c for b, c in batch_stats},
    }


@router.get("/comparison")
async def comparison(
    park_ids: str = Query(..., description="公园ID列表，逗号分隔"),
    dimension: str = Query(None, description="评估维度"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """多公园对比"""
    ids = [int(x.strip()) for x in park_ids.split(",")]
    if len(ids) > 10:
        ids = ids[:10]

    parks = db.query(Park).filter(Park.id.in_(ids)).all()

    result = []
    for park in parks:
        query = (
            db.query(Score, Indicator)
            .join(Indicator, Score.indicator_id == Indicator.id)
            .filter(Score.park_id == park.id)
        )
        if dimension:
            query = query.filter(Indicator.dimension == dimension)

        scores = query.all()

        score_data = {}
        for sc, ind in scores:
            score_data[ind.code] = {
                "name": ind.name,
                "dimension": ind.dimension,
                "score": sc.normalized_score,
                "grade": sc.grade,
            }

        result.append({
            "park_id": park.id,
            "park_name": park.short_name or park.name,
            "park_type": park.park_type,
            "scores": score_data,
        })

    return result


@router.get("/dimension")
async def dimension_scores(
    park_type: str = Query(None, description="公园类型"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """各维度得分统计"""
    query = (
        db.query(
            Park.park_type,
            Indicator.dimension,
            func.avg(Score.normalized_score).label("avg_score"),
            func.count(Score.id).label("count"),
        )
        .join(Score, Park.id == Score.park_id)
        .join(Indicator, Score.indicator_id == Indicator.id)
    )

    if park_type:
        query = query.filter(Park.park_type == park_type)

    results = query.group_by(Park.park_type, Indicator.dimension).all()

    return [
        {
            "park_type": r.park_type,
            "dimension": r.dimension,
            "avg_score": round(float(r.avg_score), 2),
            "count": r.count,
        }
        for r in results
    ]


@router.get("/radar/{park_id}")
async def radar_data(
    park_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取单个公园的雷达图数据"""
    park = db.query(Park).filter(Park.id == park_id).first()
    if not park:
        return {"error": "公园不存在"}

    scores = (
        db.query(Indicator.dimension, func.avg(Score.normalized_score).label("avg"))
        .join(Score, Indicator.id == Score.indicator_id)
        .filter(Score.park_id == park_id)
        .group_by(Indicator.dimension)
        .all()
    )

    return {
        "park_name": park.short_name or park.name,
        "dimensions": [
            {"dimension": r.dimension, "score": round(float(r.avg), 2)}
            for r in scores
        ],
    }
