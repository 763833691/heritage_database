"""文献综述结构化数据测试：年份缺失时不得因 int/str 排序崩溃。

运行：
    cd backend
    python -m pytest tests/test_kb_review.py -q
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.literature import Literature
from app.services.kb_lint import generate_literature_review


def test_review_handles_missing_year(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'kb.db'}")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()

    session.add_all([
        Literature(title="有年份文献", year=2020, keywords='["遗址"]', authors="[]"),
        Literature(title="无年份文献", year=None, keywords='["保护"]', authors="[]"),
    ])
    session.commit()

    result = generate_literature_review(session, "", 20)

    assert result["total_found"] == 2
    years = [item["year"] for item in result["by_year"]]
    assert 2020 in years and "未知" in years
    assert years[0] == 2020, "数字年份应排在“未知”之前"
    assert result["years_range"] == [2020, 2020]
    session.close()
