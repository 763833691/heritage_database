"""
数据库初始化脚本
- 创建表结构
- 插入初始数据（评估指标、遗址公园基础信息）
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import engine, SessionLocal, Base
from app.models import *
from app.core.auth import get_password_hash


def init_tables():
    """创建所有表"""
    print("[INIT] 创建数据库表...")
    Base.metadata.create_all(bind=engine)
    print("[OK] 数据库表创建完成")


def init_admin_user():
    """创建管理员账户"""
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin",
                email="admin@heritage.com",
                hashed_password=get_password_hash("admin123"),
                full_name="系统管理员",
                role="admin",
                is_active=True,
            )
            db.add(admin)
            db.commit()
            print("[OK] 管理员账户创建完成 (admin / admin123)")
        else:
            print("[INFO]  管理员账户已存在")
    finally:
        db.close()


def init_indicators():
    """插入评估指标数据"""
    db = SessionLocal()
    try:
        existing = db.query(Indicator).count()
        if existing > 0:
            print(f"[INFO]  评估指标已存在 ({existing}条)")
            return

        indicators = [
            # B1 遗址保护效能 - C1 遗址本体保护
            {"code": "D1", "name": "遗址本体完整性", "dimension": "遗址保护效能", "sub_dimension": "遗址本体保护", "weight_urban": 0.15, "weight_suburb": 0.18, "weight_rural": 0.16},
            {"code": "D2", "name": "遗址本体安全性", "dimension": "遗址保护效能", "sub_dimension": "遗址本体保护", "weight_urban": 0.12, "weight_suburb": 0.15, "weight_rural": 0.14},
            # B1 - C2 环境风貌保护
            {"code": "D3", "name": "周边环境协调性", "dimension": "遗址保护效能", "sub_dimension": "环境风貌保护", "weight_urban": 0.08, "weight_suburb": 0.10, "weight_rural": 0.12},
            {"code": "D4", "name": "生态环境保护度", "dimension": "遗址保护效能", "sub_dimension": "环境风貌保护", "weight_urban": 0.06, "weight_suburb": 0.08, "weight_rural": 0.10},
            {"code": "D5", "name": "景观风貌维护度", "dimension": "遗址保护效能", "sub_dimension": "环境风貌保护", "weight_urban": 0.06, "weight_suburb": 0.07, "weight_rural": 0.08},
            # B2 文化传播效能 - C3 文化传播内容
            {"code": "D6", "name": "遗址信息丰富度", "dimension": "文化传播效能", "sub_dimension": "文化传播内容", "weight_urban": 0.06, "weight_suburb": 0.05, "weight_rural": 0.05},
            {"code": "D7", "name": "遗址文化吸引力", "dimension": "文化传播效能", "sub_dimension": "文化传播内容", "weight_urban": 0.05, "weight_suburb": 0.04, "weight_rural": 0.04},
            # B2 - C4 传播渠道与受众
            {"code": "D8", "name": "传播媒介丰富度", "dimension": "文化传播效能", "sub_dimension": "传播渠道与受众", "weight_urban": 0.04, "weight_suburb": 0.03, "weight_rural": 0.03},
            {"code": "D9", "name": "展示设施阐释力", "dimension": "文化传播效能", "sub_dimension": "传播渠道与受众", "weight_urban": 0.04, "weight_suburb": 0.03, "weight_rural": 0.03},
            # B2 - C5 文化传播效果
            {"code": "D10", "name": "受众认知度", "dimension": "文化传播效能", "sub_dimension": "文化传播效果", "weight_urban": 0.04, "weight_suburb": 0.03, "weight_rural": 0.03},
            {"code": "D11", "name": "情感联结度", "dimension": "文化传播效能", "sub_dimension": "文化传播效果", "weight_urban": 0.04, "weight_suburb": 0.03, "weight_rural": 0.03},
            {"code": "D12", "name": "传播影响力", "dimension": "文化传播效能", "sub_dimension": "文化传播效果", "weight_urban": 0.04, "weight_suburb": 0.03, "weight_rural": 0.03},
            # B3 教育传承效能 - C6 教育内容定位
            {"code": "D13", "name": "教育内容科学性", "dimension": "教育传承效能", "sub_dimension": "教育内容定位", "weight_urban": 0.03, "weight_suburb": 0.02, "weight_rural": 0.02},
            {"code": "D14", "name": "教育内容与遗址关联度", "dimension": "教育传承效能", "sub_dimension": "教育内容定位", "weight_urban": 0.03, "weight_suburb": 0.02, "weight_rural": 0.02},
            # B3 - C7 教育活动开展
            {"code": "D15", "name": "教育活动频次", "dimension": "教育传承效能", "sub_dimension": "教育活动开展", "weight_urban": 0.03, "weight_suburb": 0.02, "weight_rural": 0.02},
            {"code": "D16", "name": "教育活动丰富度", "dimension": "教育传承效能", "sub_dimension": "教育活动开展", "weight_urban": 0.03, "weight_suburb": 0.02, "weight_rural": 0.02},
            {"code": "D17", "name": "公众参与度", "dimension": "教育传承效能", "sub_dimension": "教育活动开展", "weight_urban": 0.03, "weight_suburb": 0.02, "weight_rural": 0.02},
            # B3 - C8 文化教育传承效果
            {"code": "D18", "name": "文化信息传达度", "dimension": "教育传承效能", "sub_dimension": "文化教育传承效果", "weight_urban": 0.03, "weight_suburb": 0.02, "weight_rural": 0.02},
            {"code": "D19", "name": "文化认同提升度", "dimension": "教育传承效能", "sub_dimension": "文化教育传承效果", "weight_urban": 0.03, "weight_suburb": 0.02, "weight_rural": 0.02},
            # B4 文化活化效能 - C9 文化转化效果
            {"code": "D20", "name": "文创产品丰富度", "dimension": "文化活化效能", "sub_dimension": "文化转化效果", "weight_urban": 0.02, "weight_suburb": 0.01, "weight_rural": 0.01},
            {"code": "D21", "name": "文创产业融合度", "dimension": "文化活化效能", "sub_dimension": "文化转化效果", "weight_urban": 0.02, "weight_suburb": 0.01, "weight_rural": 0.01},
            {"code": "D22", "name": "文旅融合贡献度", "dimension": "文化活化效能", "sub_dimension": "文化转化效果", "weight_urban": 0.02, "weight_suburb": 0.01, "weight_rural": 0.01},
            # B4 - C10 文化活动与公众互动
            {"code": "D23", "name": "文化活动开展度", "dimension": "文化活化效能", "sub_dimension": "文化活动与公众互动", "weight_urban": 0.02, "weight_suburb": 0.01, "weight_rural": 0.01},
            {"code": "D24", "name": "文化活动丰富度", "dimension": "文化活化效能", "sub_dimension": "文化活动与公众互动", "weight_urban": 0.02, "weight_suburb": 0.01, "weight_rural": 0.01},
            {"code": "D25", "name": "公众互动参与", "dimension": "文化活化效能", "sub_dimension": "文化活动与公众互动", "weight_urban": 0.02, "weight_suburb": 0.01, "weight_rural": 0.01},
            {"code": "D26", "name": "社区共建共管", "dimension": "文化活化效能", "sub_dimension": "文化活动与公众互动", "weight_urban": 0.02, "weight_suburb": 0.01, "weight_rural": 0.01},
            {"code": "D27", "name": "公众参与和共建", "dimension": "文化活化效能", "sub_dimension": "文化活动与公众互动", "weight_urban": 0.02, "weight_suburb": 0.01, "weight_rural": 0.01},
        ]

        for ind_data in indicators:
            indicator = Indicator(**ind_data)
            db.add(indicator)

        db.commit()
        print(f"[OK] 评估指标数据插入完成 ({len(indicators)}条)")
    finally:
        db.close()


def init_parks():
    """插入遗址公园基础数据"""
    db = SessionLocal()
    try:
        existing = db.query(Park).count()
        if existing > 0:
            print(f"[INFO]  遗址公园数据已存在 ({existing}条)")
            return

        parks = [
            # 城市型
            {"name": "圆明园国家考古遗址公园", "short_name": "圆明园", "park_type": "城市型", "batch": 1,
             "province": "北京", "city": "北京", "district": "海淀区", "longitude": 116.30, "latitude": 40.01,
             "total_area": 3.5, "world_heritage": 0, "aaa_level": "5A", "open_year": 1988,
             "description": "清代皇家园林，三山五园文化廊道核心"},
            {"name": "大明宫国家考古遗址公园", "short_name": "大明宫", "park_type": "城市型", "batch": 1,
             "province": "陕西", "city": "西安", "district": "未央区", "longitude": 108.96, "latitude": 34.29,
             "total_area": 3.5, "world_heritage": 1, "aaa_level": "5A", "open_year": 2010,
             "description": "唐代政治中枢，丝绸之路起点城市标志性见证"},
            {"name": "隋唐洛阳城国家考古遗址公园", "short_name": "隋唐洛阳城", "park_type": "城市型", "batch": 1,
             "province": "河南", "city": "洛阳", "district": "西工区", "longitude": 112.45, "latitude": 34.67,
             "total_area": 47.0, "world_heritage": 1, "aaa_level": "4A", "open_year": 2010,
             "description": "隋唐东都宫城核心区，黄河文化带重要节点"},
            # 城郊型
            {"name": "汉长安城未央宫国家考古遗址公园", "short_name": "未央宫", "park_type": "城郊型", "batch": 3,
             "province": "陕西", "city": "西安", "district": "未央区", "longitude": 108.85, "latitude": 34.30,
             "total_area": 4.8, "world_heritage": 1, "aaa_level": None, "open_year": 2021,
             "description": "西汉政治中枢，丝绸之路起点"},
            {"name": "杜陵国家考古遗址公园", "short_name": "杜陵", "park_type": "城郊型", "batch": 3,
             "province": "陕西", "city": "西安", "district": "长安区", "longitude": 108.97, "latitude": 34.15,
             "total_area": 23.0, "world_heritage": 0, "aaa_level": None, "open_year": 2022,
             "description": "西汉中期帝陵，事死如生丧葬礼仪典型代表"},
            {"name": "周口店国家考古遗址公园", "short_name": "周口店", "park_type": "城郊型", "batch": 1,
             "province": "北京", "city": "北京", "district": "房山区", "longitude": 115.95, "latitude": 39.69,
             "total_area": 4.8, "world_heritage": 1, "aaa_level": "4A", "open_year": 2014,
             "description": "古人类遗址，世界文化遗产"},
            # 乡村型
            {"name": "统万城国家考古遗址公园", "short_name": "统万城", "park_type": "乡村型", "batch": 4,
             "province": "陕西", "city": "榆林", "district": "靖边县", "longitude": 108.84, "latitude": 37.99,
             "total_area": 42.6, "world_heritage": 0, "aaa_level": "4A", "open_year": 2023,
             "description": "大夏国都城遗址，民族融合见证"},
            {"name": "屈家岭国家考古遗址公园", "short_name": "屈家岭", "park_type": "乡村型", "batch": 4,
             "province": "湖北", "city": "荆门", "district": "屈家岭管理区", "longitude": 112.85, "latitude": 30.82,
             "total_area": 0.402, "world_heritage": 0, "aaa_level": "4A", "open_year": 2022,
             "description": "屈家岭文化命名地，长江中游早期文明实证"},
            {"name": "殷墟国家考古遗址公园", "short_name": "殷墟", "park_type": "乡村型", "batch": 1,
             "province": "河南", "city": "安阳", "district": "殷都区", "longitude": 114.32, "latitude": 36.13,
             "total_area": 36.0, "world_heritage": 1, "aaa_level": "5A", "open_year": 2010,
             "description": "商代都城遗址，甲骨文发源地"},
        ]

        for park_data in parks:
            park = Park(**park_data)
            db.add(park)

        db.commit()
        print(f"[OK] 遗址公园数据插入完成 ({len(parks)}条)")
    finally:
        db.close()


def init_sample_scores():
    """插入示例评分数据（城市型公园）"""
    db = SessionLocal()
    try:
        existing = db.query(Score).count()
        if existing > 0:
            print(f"[INFO]  评分数据已存在 ({existing}条)")
            return

        # 城市型公园评分（基于第三章文档数据）
        scores_data = {
            "圆明园": {
                "D1": 60, "D2": 60, "D3": 80, "D4": 60, "D5": 80,
                "D6": 80, "D7": 80, "D8": 100, "D9": 40,
                "D10": 80, "D11": 60, "D12": 80,
                "D13": 80, "D14": 80, "D15": 80, "D16": 80, "D17": 60,
                "D18": 80, "D19": 60,
                "D20": 80, "D21": 80, "D22": 60,
                "D23": 80, "D24": 80, "D25": 80, "D26": 60, "D27": 60,
            },
            "大明宫": {
                "D1": 40, "D2": 40, "D3": 60, "D4": 20, "D5": 40,
                "D6": 80, "D7": 20, "D8": 80, "D9": 40,
                "D10": 80, "D11": 60, "D12": 40,
                "D13": 80, "D14": 60, "D15": 60, "D16": 60, "D17": 60,
                "D18": 60, "D19": 60,
                "D20": 60, "D21": 60, "D22": 60,
                "D23": 60, "D24": 60, "D25": 60, "D26": 60, "D27": 60,
            },
            "隋唐洛阳城": {
                "D1": 60, "D2": 60, "D3": 80, "D4": 40, "D5": 80,
                "D6": 80, "D7": 40, "D8": 100, "D9": 60,
                "D10": 80, "D11": 60, "D12": 60,
                "D13": 80, "D14": 80, "D15": 60, "D16": 80, "D17": 60,
                "D18": 60, "D19": 60,
                "D20": 80, "D21": 80, "D22": 80,
                "D23": 80, "D24": 80, "D25": 80, "D26": 60, "D27": 60,
            },
        }

        grade_map = {100: "好", 80: "较好", 60: "一般", 40: "较差", 20: "差"}

        for park_name, scores in scores_data.items():
            park = db.query(Park).filter(Park.short_name == park_name).first()
            if not park:
                continue

            indicators = db.query(Indicator).all()
            ind_map = {ind.code: ind.id for ind in indicators}

            for code, score_val in scores.items():
                score = Score(
                    park_id=park.id,
                    indicator_id=ind_map.get(code),
                    normalized_score=score_val,
                    grade=grade_map.get(score_val, "一般"),
                    data_year=2025,
                    evaluator="调研组",
                )
                db.add(score)

        db.commit()
        print("[OK] 示例评分数据插入完成")
    finally:
        db.close()


def main():
    print("=" * 50)
    print("[DB]  国家考古遗址公园智能研究平台")
    print("    数据库初始化脚本")
    print("=" * 50)
    print()

    init_tables()
    init_admin_user()
    init_indicators()
    init_parks()
    init_sample_scores()

    print()
    print("=" * 50)
    print("[OK] 数据库初始化完成！")
    print("=" * 50)


if __name__ == "__main__":
    main()
