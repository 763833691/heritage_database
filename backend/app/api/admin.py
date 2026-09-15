from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
import pandas as pd
import io

from ..core.database import get_db
from ..core.auth import get_admin_user
from ..models.user import User
from ..models.park import Park
from ..models.site import Site
from ..models.indicator import Indicator
from ..models.score import Score
from ..models.survey import Survey, SurveyAnswer
from ..models.review import Review
from ..models.exhibition import Exhibition
from ..models.location import Location
from ..models.education import EducationActivity
from ..models.community import Community

router = APIRouter()


# ==================== 遗址公园管理 ====================

@router.get("/parks")
async def admin_list_parks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    parks = db.query(Park).all()
    return [
        {
            "id": p.id, "name": p.name, "short_name": p.short_name,
            "park_type": p.park_type, "batch": p.batch,
            "province": p.province, "city": p.city,
        }
        for p in parks
    ]


@router.post("/parks")
async def create_park(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    scores_data = data.pop("scores", None) or []
    park = Park(**data)
    db.add(park)
    db.flush()

    if scores_data:
        grade_map = {100: "好", 80: "较好", 60: "一般", 40: "较差", 20: "差"}
        for item in scores_data:
            indicator_id = item.get("indicator_id")
            if not indicator_id and item.get("indicator_code"):
                indicator = db.query(Indicator).filter(
                    Indicator.code == item["indicator_code"]
                ).first()
                indicator_id = indicator.id if indicator else None
            if not indicator_id:
                continue
            score_val = item.get("normalized_score")
            db.add(Score(
                park_id=park.id,
                indicator_id=indicator_id,
                normalized_score=score_val,
                grade=grade_map.get(score_val, "一般"),
                evidence=item.get("evidence"),
                data_year=item.get("data_year"),
            ))

    db.commit()
    db.refresh(park)
    return {"id": park.id, "message": "创建成功"}


@router.put("/parks/{park_id}")
async def update_park(
    park_id: int,
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    park = db.query(Park).filter(Park.id == park_id).first()
    if not park:
        raise HTTPException(404, "遗址公园不存在")
    for key, value in data.items():
        if hasattr(park, key):
            setattr(park, key, value)
    db.commit()
    return {"message": "更新成功"}


@router.delete("/parks/{park_id}")
async def delete_park(
    park_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    park = db.query(Park).filter(Park.id == park_id).first()
    if not park:
        raise HTTPException(404, "遗址公园不存在")
    db.delete(park)
    db.commit()
    return {"message": "删除成功"}


# ==================== 遗址点管理 ====================

@router.get("/parks/{park_id}/sites")
async def admin_list_sites(
    park_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    return db.query(Site).filter(Site.park_id == park_id).all()


@router.post("/sites")
async def create_site(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    site = Site(**data)
    db.add(site)
    db.commit()
    db.refresh(site)
    return {"id": site.id, "message": "创建成功"}


@router.put("/sites/{site_id}")
async def update_site(
    site_id: int,
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(404, "遗址点不存在")
    for key, value in data.items():
        if hasattr(site, key):
            setattr(site, key, value)
    db.commit()
    return {"message": "更新成功"}


@router.delete("/sites/{site_id}")
async def delete_site(
    site_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(404, "遗址点不存在")
    db.delete(site)
    db.commit()
    return {"message": "删除成功"}


# ==================== 评分管理 ====================

@router.get("/scores")
async def admin_list_scores(
    park_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    query = db.query(Score, Indicator, Park).join(
        Indicator, Score.indicator_id == Indicator.id
    ).join(Park, Score.park_id == Park.id)

    if park_id:
        query = query.filter(Score.park_id == park_id)

    results = query.all()
    return [
        {
            "id": sc.id, "park_id": sc.park_id, "park_name": p.name,
            "indicator_id": sc.indicator_id, "indicator_code": ind.code,
            "indicator_name": ind.name, "dimension": ind.dimension,
            "normalized_score": sc.normalized_score, "grade": sc.grade,
            "evidence": sc.evidence, "data_year": sc.data_year,
        }
        for sc, ind, p in results
    ]


@router.post("/scores")
async def create_score(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    # 自动计算等级
    score_val = data.get("normalized_score")
    if score_val:
        grade_map = {100: "好", 80: "较好", 60: "一般", 40: "较差", 20: "差"}
        data["grade"] = grade_map.get(score_val, "一般")

    score = Score(**data)
    db.add(score)
    db.commit()
    db.refresh(score)
    return {"id": score.id, "message": "创建成功"}


@router.put("/scores/{score_id}")
async def update_score(
    score_id: int,
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    score = db.query(Score).filter(Score.id == score_id).first()
    if not score:
        raise HTTPException(404, "评分记录不存在")

    score_val = data.get("normalized_score")
    if score_val:
        grade_map = {100: "好", 80: "较好", 60: "一般", 40: "较差", 20: "差"}
        data["grade"] = grade_map.get(score_val, "一般")

    for key, value in data.items():
        if hasattr(score, key):
            setattr(score, key, value)
    db.commit()
    return {"message": "更新成功"}


@router.delete("/scores/{score_id}")
async def delete_score(
    score_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    score = db.query(Score).filter(Score.id == score_id).first()
    if not score:
        raise HTTPException(404, "评分记录不存在")
    db.delete(score)
    db.commit()
    return {"message": "删除成功"}


# ==================== 批量导入 ====================

@router.post("/import/scores")
async def import_scores(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """从Excel批量导入评分数据"""
    content = await file.read()
    df = pd.read_excel(io.BytesIO(content))

    # 预期列名: park_name, indicator_code, score, evidence, data_year
    required_cols = {"park_name", "indicator_code", "score"}
    if not required_cols.issubset(set(df.columns)):
        raise HTTPException(400, f"Excel需要包含列: {required_cols}")

    grade_map = {100: "好", 80: "较好", 60: "一般", 40: "较差", 20: "差"}
    success = 0
    errors = []

    for _, row in df.iterrows():
        try:
            park = db.query(Park).filter(
                (Park.name == row["park_name"]) | (Park.short_name == row["park_name"])
            ).first()
            if not park:
                errors.append(f"公园不存在: {row['park_name']}")
                continue

            indicator = db.query(Indicator).filter(Indicator.code == row["indicator_code"]).first()
            if not indicator:
                errors.append(f"指标不存在: {row['indicator_code']}")
                continue

            score_val = int(row["score"])
            score = Score(
                park_id=park.id,
                indicator_id=indicator.id,
                normalized_score=score_val,
                grade=grade_map.get(score_val, "一般"),
                evidence=row.get("evidence", ""),
                data_year=int(row.get("data_year", 2025)),
                evaluator="批量导入",
            )
            db.add(score)
            success += 1
        except Exception as e:
            errors.append(f"行 {_}: {str(e)}")

    db.commit()
    return {"success": success, "errors": errors}


@router.post("/import/parks")
async def import_parks(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """从Excel批量导入遗址公园"""
    content = await file.read()
    df = pd.read_excel(io.BytesIO(content))

    success = 0
    errors = []

    for _, row in df.iterrows():
        try:
            park = Park(
                name=row["name"],
                short_name=row.get("short_name", ""),
                park_type=row.get("park_type", ""),
                batch=int(row["batch"]) if pd.notna(row.get("batch")) else None,
                province=row.get("province", ""),
                city=row.get("city", ""),
                district=row.get("district", ""),
                longitude=float(row["longitude"]) if pd.notna(row.get("longitude")) else None,
                latitude=float(row["latitude"]) if pd.notna(row.get("latitude")) else None,
                total_area=float(row["total_area"]) if pd.notna(row.get("total_area")) else None,
                world_heritage=int(row.get("world_heritage", 0)),
                aaa_level=row.get("aaa_level", ""),
                description=row.get("description", ""),
            )
            db.add(park)
            success += 1
        except Exception as e:
            errors.append(f"行 {_}: {str(e)}")

    db.commit()
    return {"success": success, "errors": errors}


@router.post("/import/sites")
async def import_sites(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """从Excel批量导入遗址点"""
    content = await file.read()
    df = pd.read_excel(io.BytesIO(content))

    success = 0
    errors = []

    for _, row in df.iterrows():
        try:
            park = db.query(Park).filter(
                (Park.name == row["park_name"]) | (Park.short_name == row["park_name"])
            ).first()
            if not park:
                errors.append(f"公园不存在: {row['park_name']}")
                continue

            site = Site(
                park_id=park.id,
                site_name=row["site_name"],
                site_type=row.get("site_type", ""),
                period=row.get("period", ""),
                integrity_score=int(row["integrity_score"]) if pd.notna(row.get("integrity_score")) else None,
                safety_score=int(row["safety_score"]) if pd.notna(row.get("safety_score")) else None,
                description=row.get("description", ""),
            )
            db.add(site)
            success += 1
        except Exception as e:
            errors.append(f"行 {_}: {str(e)}")

    db.commit()
    return {"success": success, "errors": errors}


@router.post("/import/surveys")
async def import_surveys(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """从Excel批量导入问卷数据"""
    content = await file.read()
    df = pd.read_excel(io.BytesIO(content))

    success = 0
    errors = []

    for _, row in df.iterrows():
        try:
            park = db.query(Park).filter(
                (Park.name == row["park_name"]) | (Park.short_name == row["park_name"])
            ).first()
            if not park:
                errors.append(f"公园不存在: {row['park_name']}")
                continue

            # 创建或获取问卷
            survey = db.query(Survey).filter(
                Survey.park_id == park.id,
                Survey.survey_date == str(row.get("survey_date", ""))
            ).first()

            if not survey:
                survey = Survey(
                    park_id=park.id,
                    survey_date=str(row.get("survey_date", "")),
                    sampling_method=row.get("sampling_method", ""),
                )
                db.add(survey)
                db.flush()

            # 创建回答
            answer = SurveyAnswer(
                survey_id=survey.id,
                respondent_id=str(row.get("respondent_id", "")),
                question_code=str(row.get("question_code", "")),
                question_text=str(row.get("question_text", "")),
                answer_value=int(row["answer_value"]) if pd.notna(row.get("answer_value")) else None,
                answer_text=str(row.get("answer_text", "")),
                respondent_age=str(row.get("age", "")),
                respondent_gender=str(row.get("gender", "")),
            )
            db.add(answer)
            success += 1
        except Exception as e:
            errors.append(f"行 {_}: {str(e)}")

    db.commit()
    return {"success": success, "errors": errors}


# ==================== 指标管理 ====================

@router.get("/indicators")
async def admin_list_indicators(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """获取所有评估指标列表"""
    indicators = db.query(Indicator).order_by(Indicator.code).all()
    return [
        {
            "id": ind.id,
            "code": ind.code,
            "name": ind.name,
            "dimension": ind.dimension,
            "sub_dimension": ind.sub_dimension,
        }
        for ind in indicators
    ]


# ==================== 用户管理 ====================

@router.get("/users")
async def admin_list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    users = db.query(User).all()
    return [
        {
            "id": u.id, "username": u.username, "email": u.email,
            "full_name": u.full_name, "role": u.role, "is_active": u.is_active,
        }
        for u in users
    ]


@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: int,
    role: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "用户不存在")
    user.role = role
    db.commit()
    return {"message": f"已将 {user.username} 角色更新为 {role}"}


@router.put("/users/{user_id}/status")
async def toggle_user_status(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "用户不存在")
    user.is_active = not user.is_active
    db.commit()
    return {"message": f"用户 {user.username} 已{'启用' if user.is_active else '禁用'}"}


# ==================== 调研报告自动导入 ====================

@router.post("/upload/report")
async def upload_report(
    file: UploadFile = File(...),
    current_user: User = Depends(get_admin_user),
):
    """上传调研报告并返回AI解析预览"""
    import asyncio
    from ..services.doc_parser import extract_text, split_sections, parse_with_llm

    ext = file.filename.lower().rsplit('.', 1)[-1] if '.' in file.filename else ''
    if ext not in ('docx', 'doc', 'txt'):
        raise HTTPException(400, "仅支持 .docx / .doc / .txt 格式")

    content = await file.read()
    if len(content) > 100 * 1024 * 1024:
        raise HTTPException(400, "文件大小不能超过 100MB")

    try:
        text = extract_text(content, file.filename)
        if not text or len(text.strip()) < 50:
            raise HTTPException(400, "文件内容为空或无法识别")

        sections = split_sections(text)

        # LLM 解析（在线程池中执行，避免阻塞事件循环）
        loop = asyncio.get_running_loop()
        parsed = await asyncio.wait_for(
            loop.run_in_executor(None, parse_with_llm, sections),
            timeout=300.0,
        )

        return {
            "file_name": file.filename,
            "text_length": len(text),
            "sections": len(sections),
            "text_preview": text[:500],
            "parsed": parsed,
            "note": (
                "未提取到评分数据，请确认文档包含 D1-D27 指标评分（格式如 'D1遗址本体完整性得分60分'）"
                if not parsed.get("scores") else ""
            ),
        }
    except asyncio.TimeoutError:
        raise HTTPException(500, "AI 解析超时（5分钟），请减小文件或稍后重试")
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        print(f"[Admin] 报告解析失败: {e}")
        raise HTTPException(500, f"解析失败: {str(e)}")


@router.post("/upload/report/confirm")
async def confirm_report_import(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """确认导入解析后的数据"""
    parks_data = data.get("parks", [])
    scores_data = data.get("scores", [])
    surveys_data = data.get("surveys", [])

    grade_map = {100: "好", 80: "较好", 60: "一般", 40: "较差", 20: "差"}
    imported = {"parks": 0, "scores": 0, "surveys": 0}
    errors = []

    # 导入公园
    for p in parks_data:
        try:
            name = p.get("name", "").strip()
            short_name = p.get("short_name", "").strip()
            if not name:
                continue

            existing = db.query(Park).filter(
                (Park.name == name) | (Park.short_name == short_name)
            ).first()
            if existing:
                continue

            park = Park(
                name=name,
                short_name=short_name or None,
                park_type=p.get("park_type", ""),
                province=p.get("province", ""),
                city=p.get("city", ""),
                description=p.get("description", ""),
            )
            db.add(park)
            db.flush()
            imported["parks"] += 1
        except Exception as e:
            errors.append(f"公园导入失败 [{p.get('name')}]: {str(e)}")

    # 导入评分
    for s in scores_data:
        try:
            park_name = s.get("park_name", "").strip()
            indicator_code = s.get("indicator_code", "").strip()
            score_val = int(s.get("score", 0))

            if not park_name or not indicator_code or score_val not in grade_map:
                continue

            park = db.query(Park).filter(
                (Park.name == park_name) | (Park.short_name == park_name)
            ).first()
            if not park:
                continue

            indicator = db.query(Indicator).filter(Indicator.code == indicator_code).first()
            if not indicator:
                continue

            # 检查是否已存在，存在则更新
            existing_score = db.query(Score).filter(
                Score.park_id == park.id,
                Score.indicator_id == indicator.id,
            ).first()

            if existing_score:
                existing_score.normalized_score = score_val
                existing_score.grade = grade_map[score_val]
                existing_score.evidence = s.get("evidence", "")
                existing_score.data_year = s.get("data_year", 2025)
            else:
                score = Score(
                    park_id=park.id,
                    indicator_id=indicator.id,
                    normalized_score=score_val,
                    grade=grade_map[score_val],
                    evidence=s.get("evidence", ""),
                    data_year=s.get("data_year", 2025),
                    evaluator="报告导入",
                )
                db.add(score)
            imported["scores"] += 1
        except Exception as e:
            errors.append(f"评分导入失败 [{s.get('park_name')}/{s.get('indicator_code')}]: {str(e)}")

    # 导入问卷
    for sv in surveys_data:
        try:
            park_name = sv.get("park_name", "").strip()
            if not park_name:
                continue

            park = db.query(Park).filter(
                (Park.name == park_name) | (Park.short_name == park_name)
            ).first()
            if not park:
                continue

            survey = Survey(
                park_id=park.id,
                survey_date=sv.get("survey_date", "2025"),
                total_distributed=sv.get("total_distributed"),
                total_collected=sv.get("total_collected"),
                valid_count=sv.get("valid_count"),
                sampling_method=sv.get("sampling_method", "随机抽样"),
            )
            db.add(survey)
            imported["surveys"] += 1
        except Exception as e:
            errors.append(f"问卷导入失败 [{sv.get('park_name')}]: {str(e)}")

    db.commit()

    return {"imported": imported, "errors": errors}
