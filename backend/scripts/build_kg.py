"""
知识图谱构建脚本
从PostgreSQL数据库读取数据，构建Neo4j知识图谱
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal, neo4j_driver
from app.models.park import Park
from app.models.site import Site
from app.models.indicator import Indicator
from app.models.score import Score
from app.models.exhibition import Exhibition


def clear_graph():
    """清空Neo4j数据库"""
    print("🗑️  清空Neo4j数据库...")
    with neo4j_driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
    print("✅ 清空完成")


def create_constraints():
    """创建唯一性约束"""
    print("🔒 创建约束...")
    constraints = [
        "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Park) REQUIRE p.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Site) REQUIRE s.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (i:Indicator) REQUIRE i.code IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (t:ParkType) REQUIRE t.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (pr:Province) REQUIRE pr.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (h:HistoricalPeriod) REQUIRE h.name IS UNIQUE",
    ]
    with neo4j_driver.session() as session:
        for constraint in constraints:
            try:
                session.run(constraint)
            except Exception:
                pass  # 约束可能已存在
    print("✅ 约束创建完成")


def build_park_nodes():
    """创建遗址公园节点"""
    print("🏛️  创建遗址公园节点...")
    db = SessionLocal()
    try:
        parks = db.query(Park).all()
        with neo4j_driver.session() as session:
            for park in parks:
                query = """
                MERGE (p:Park {name: $name})
                SET p.short_name = $short_name,
                    p.type = $park_type,
                    p.batch = $batch,
                    p.city = $city,
                    p.province = $province,
                    p.area = $area,
                    p.world_heritage = $world_heritage,
                    p.aaa_level = $aaa_level,
                    p.open_year = $open_year,
                    p.description = $description
                """
                session.run(query,
                    name=park.name,
                    short_name=park.short_name,
                    park_type=park.park_type,
                    batch=park.batch,
                    city=park.city,
                    province=park.province,
                    area=park.total_area,
                    world_heritage=park.world_heritage,
                    aaa_level=park.aaa_level,
                    open_year=park.open_year,
                    description=park.description,
                )

                # 创建类型节点和关系
                session.run("""
                    MERGE (t:ParkType {name: $type})
                    WITH t
                    MATCH (p:Park {name: $name})
                    MERGE (p)-[:HAS_TYPE]->(t)
                """, type=park.park_type, name=park.name)

                # 创建省份节点和关系
                session.run("""
                    MERGE (pr:Province {name: $province})
                    WITH pr
                    MATCH (p:Park {name: $name})
                    MERGE (p)-[:LOCATED_IN]->(pr)
                """, province=park.province, name=park.name)

                # 创建城市节点和关系
                session.run("""
                    MERGE (c:City {name: $city, province: $province})
                    WITH c
                    MATCH (p:Park {name: $name})
                    MERGE (p)-[:LOCATED_IN]->(c)
                """, city=park.city, province=park.province, name=park.name)

                # 创建批次关系
                if park.batch:
                    session.run("""
                        MERGE (b:Batch {number: $batch})
                        WITH b
                        MATCH (p:Park {name: $name})
                        MERGE (p)-[:BELONGS_TO_BATCH]->(b)
                    """, batch=park.batch, name=park.name)

        print(f"✅ 创建了 {len(parks)} 个遗址公园节点")
    finally:
        db.close()


def build_site_nodes():
    """创建遗址点节点"""
    print("🏺 创建遗址点节点...")
    db = SessionLocal()
    try:
        sites = db.query(Site).all()
        if not sites:
            print("ℹ️  暂无遗址点数据")
            return

        with neo4j_driver.session() as session:
            for site in sites:
                park = db.query(Park).filter(Park.id == site.park_id).first()
                if not park:
                    continue

                query = """
                MATCH (p:Park {name: $park_name})
                MERGE (s:Site {name: $site_name})
                SET s.type = $site_type,
                    s.period = $period,
                    s.integrity_score = $integrity_score,
                    s.safety_score = $safety_score
                MERGE (p)-[:CONTAINS]->(s)
                """
                session.run(query,
                    park_name=park.name,
                    site_name=site.site_name,
                    site_type=site.site_type,
                    period=site.period,
                    integrity_score=site.integrity_score,
                    safety_score=site.safety_score,
                )

                # 创建时期节点
                if site.period:
                    session.run("""
                        MERGE (h:HistoricalPeriod {name: $period})
                        WITH h
                        MATCH (s:Site {name: $site_name})
                        MERGE (s)-[:BELONGS_TO]->(h)
                    """, period=site.period, site_name=site.site_name)

        print(f"✅ 创建了 {len(sites)} 个遗址点节点")
    finally:
        db.close()


def build_indicator_and_scores():
    """创建评估指标和评分关系"""
    print("📊 创建评估指标和评分...")
    db = SessionLocal()
    try:
        indicators = db.query(Indicator).all()
        scores = db.query(Score).all()

        grade_map = {100: "好", 80: "较好", 60: "一般", 40: "较差", 20: "差"}

        with neo4j_driver.session() as session:
            # 创建指标节点
            for ind in indicators:
                query = """
                MERGE (i:Indicator {code: $code})
                SET i.name = $name,
                    i.dimension = $dimension,
                    i.sub_dimension = $sub_dimension
                """
                session.run(query,
                    code=ind.code,
                    name=ind.name,
                    dimension=ind.dimension,
                    sub_dimension=ind.sub_dimension,
                )

                # 创建维度节点
                session.run("""
                    MERGE (d:Dimension {name: $dimension})
                    WITH d
                    MATCH (i:Indicator {code: $code})
                    MERGE (i)-[:BELONGS_TO]->(d)
                """, dimension=ind.dimension, code=ind.code)

            # 创建评分关系
            for score in scores:
                park = db.query(Park).filter(Park.id == score.park_id).first()
                indicator = db.query(Indicator).filter(Indicator.id == score.indicator_id).first()
                if not park or not indicator:
                    continue

                query = """
                MATCH (p:Park {name: $park_name})
                MATCH (i:Indicator {code: $indicator_code})
                MERGE (p)-[r:HAS_SCORE]->(i)
                SET r.value = $value,
                    r.grade = $grade,
                    r.year = $year
                """
                session.run(query,
                    park_name=park.name,
                    indicator_code=indicator.code,
                    value=score.normalized_score,
                    grade=score.normalized_score and grade_map.get(score.normalized_score, "一般"),
                    year=score.data_year,
                )

        print(f"✅ 创建了 {len(indicators)} 个指标节点，{len(scores)} 条评分关系")
    finally:
        db.close()


def build_exhibition_data():
    """创建展示利用相关节点"""
    print("🎪 创建展示利用数据...")
    db = SessionLocal()
    try:
        exhibitions = db.query(Exhibition).all()
        if not exhibitions:
            print("ℹ️  暂无展示利用数据")
            return

        with neo4j_driver.session() as session:
            for exh in exhibitions:
                park = db.query(Park).filter(Park.id == exh.park_id).first()
                if not park:
                    continue

                # 创建博物馆节点
                if exh.museum_count and exh.museum_count > 0:
                    session.run("""
                        MATCH (p:Park {name: $park_name})
                        MERGE (m:Museum {name: $park_name + '博物馆'})
                        SET m.area = $area
                        MERGE (p)-[:HAS_MUSEUM]->(m)
                    """, park_name=park.name, area=exh.museum_area)

                # 创建传播媒介关系
                if exh.media_count:
                    session.run("""
                        MATCH (p:Park {name: $park_name})
                        MERGE (md:MediaSystem {park: $park_name})
                        SET md.count = $count
                        MERGE (p)-[:HAS_MEDIA]->(md)
                    """, park_name=park.name, count=exh.media_count)

        print("✅ 展示利用数据创建完成")
    finally:
        db.close()


def build_similarity_relations():
    """构建遗址公园之间的相似性关系"""
    print("🔗 构建相似性关系...")
    db = SessionLocal()
    try:
        parks = db.query(Park).all()

        with neo4j_driver.session() as session:
            # 同类型公园之间建立相似关系
            type_groups = {}
            for park in parks:
                if park.park_type not in type_groups:
                    type_groups[park.park_type] = []
                type_groups[park.park_type].append(park.name)

            for park_type, park_names in type_groups.items():
                for i in range(len(park_names)):
                    for j in range(i + 1, len(park_names)):
                        session.run("""
                            MATCH (a:Park {name: $name1})
                            MATCH (b:Park {name: $name2})
                            MERGE (a)-[:SIMILAR_TYPE]->(b)
                            MERGE (b)-[:SIMILAR_TYPE]->(a)
                        """, name1=park_names[i], name2=park_names[j])

            # 同省份公园之间建立同城关系
            province_groups = {}
            for park in parks:
                if park.province not in province_groups:
                    province_groups[park.province] = []
                province_groups[park.province].append(park.name)

            for province, park_names in province_groups.items():
                if len(park_names) > 1:
                    for i in range(len(park_names)):
                        for j in range(i + 1, len(park_names)):
                            session.run("""
                                MATCH (a:Park {name: $name1})
                                MATCH (b:Park {name: $name2})
                                MERGE (a)-[:SAME_REGION]->(b)
                                MERGE (b)-[:SAME_REGION]->(a)
                            """, name1=park_names[i], name2=park_names[j])

        print("✅ 相似性关系构建完成")
    finally:
        db.close()


def print_stats():
    """打印图谱统计"""
    print("\n📊 知识图谱统计：")
    with neo4j_driver.session() as session:
        # 节点统计
        result = session.run("""
            MATCH (n)
            RETURN labels(n) as labels, count(n) as count
            ORDER BY count DESC
        """)
        print("\n  节点类型：")
        for record in result:
            labels = record["labels"]
            count = record["count"]
            print(f"    {', '.join(labels)}: {count}")

        # 关系统计
        result = session.run("""
            MATCH ()-[r]->()
            RETURN type(r) as type, count(r) as count
            ORDER BY count DESC
        """)
        print("\n  关系类型：")
        for record in result:
            print(f"    {record['type']}: {record['count']}")

        # 总计
        node_count = session.run("MATCH (n) RETURN count(n) as c").single()["c"]
        rel_count = session.run("MATCH ()-[r]->() RETURN count(r) as c").single()["c"]
        print(f"\n  总计: {node_count} 个节点, {rel_count} 条关系")


def main():
    print("=" * 50)
    print("🕸️  知识图谱构建脚本")
    print("=" * 50)
    print()

    if not neo4j_driver:
        print("[ERROR] Neo4j 未连接，请先设置 NEO4J_ENABLED=true 并确保 Neo4j 服务已启动")
        print("   在 backend/.env 中设置:")
        print("     NEO4J_ENABLED=true")
        print("     NEO4J_URI=bolt://localhost:7687")
        print("     NEO4J_USER=neo4j")
        print("     NEO4J_PASSWORD=heritage123")
        return

    clear_graph()
    create_constraints()
    build_park_nodes()
    build_site_nodes()
    build_indicator_and_scores()
    build_exhibition_data()
    build_similarity_relations()
    print_stats()

    print()
    print("=" * 50)
    print("✅ 知识图谱构建完成！")
    print("   可通过 http://localhost:7474 查看")
    print("=" * 50)


if __name__ == "__main__":
    main()
