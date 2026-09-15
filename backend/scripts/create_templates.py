"""生成Excel导入模板"""
import pandas as pd
import os

output_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'frontend', 'public', 'templates')
os.makedirs(output_dir, exist_ok=True)

# 遗址公园模板
parks_template = pd.DataFrame({
    'name': ['圆明园国家考古遗址公园'],
    'short_name': ['圆明园'],
    'park_type': ['城市型'],
    'batch': [1],
    'province': ['北京'],
    'city': ['北京'],
    'district': ['海淀区'],
    'longitude': [116.30],
    'latitude': [40.01],
    'total_area': [3.5],
    'world_heritage': [0],
    'aaa_level': ['5A'],
    'open_year': [1988],
    'description': ['清代皇家园林'],
})
parks_template.to_excel(os.path.join(output_dir, 'parks_template.xlsx'), index=False)

# 遗址点模板
sites_template = pd.DataFrame({
    'park_name': ['圆明园'],
    'site_name': ['西洋楼遗址'],
    'site_type': ['建筑基址'],
    'period': ['清代'],
    'integrity_score': [60],
    'safety_score': [60],
    'description': [''],
})
sites_template.to_excel(os.path.join(output_dir, 'sites_template.xlsx'), index=False)

# 评分模板
scores_template = pd.DataFrame({
    'park_name': ['圆明园', '圆明园'],
    'indicator_code': ['D1', 'D2'],
    'score': [60, 60],
    'evidence': ['实地调研', '实地调研'],
    'data_year': [2025, 2025],
})
scores_template.to_excel(os.path.join(output_dir, 'scores_template.xlsx'), index=False)

# 问卷模板
surveys_template = pd.DataFrame({
    'park_name': ['圆明园'],
    'survey_date': ['2025-01-15'],
    'respondent_id': ['P01-001'],
    'question_code': ['Q1'],
    'question_text': ['您对遗址保护的满意度'],
    'answer_value': [4],
    'answer_text': [''],
    'age': ['18-30'],
    'gender': ['男'],
    'sampling_method': ['随机抽样'],
})
surveys_template.to_excel(os.path.join(output_dir, 'surveys_template.xlsx'), index=False)

print("Templates created:")
for f in os.listdir(output_dir):
    print(f"  - {f}")
