#!/usr/bin/env python3
"""analyze_report.py"""
import json
from collections import Counter

data = json.load(open('jobs_data.json', 'r', encoding='utf-8'))
print(f'共 {len(data)} 个职位\n')

# 职位名称高频词
words = Counter()
name_list = [j.get('name','') for j in data]
for n in name_list:
    for w in ['用户研究','用户运营','产品经理','数据分析','AI','游戏','实习','专员','总监','市场','用户增长','UI']:
        if w in n:
            words[w] += 1
print('=== 职位名称高频标签 ===')
for w, cnt in words.most_common():
    print(f'  {w}: {cnt}个')

print()
# 学历和经验分布
edu_dist = Counter()
exp_dist = Counter()
for j in data:
    edu_dist[j.get('edu','不限')] += 1
    exp_dist[j.get('exp','不限')] += 1
print('=== 学历要求 ===')
for k,v in edu_dist.most_common():
    print(f'  {k}: {v}个')
print('=== 经验要求 ===')
for k,v in exp_dist.most_common():
    print(f'  {k}: {v}个')

print()
# 行业分布
ind_dist = Counter()
for j in data:
    ind_dist[j.get('industry','未知')] += 1
print('=== 行业分布 TOP15 ===')
for ind, cnt in ind_dist.most_common(15):
    print(f'  {ind}: {cnt}个')

print()
# 技能关键词
skill_kw = ['SPSS','Python','SQL','R语言','Tableau','Excel','问卷','访谈','可用性测试','统计分析','定性','定量','用户画像','A/B测试','焦点小组','数据分析']
skill_cnt = {}
for kw in skill_kw:
    cnt = 0
    for j in data:
        if kw in j.get('description',''):
            cnt += 1
    skill_cnt[kw] = cnt
print('=== 职位描述中提及的技能关键词 ===')
for kw, cnt in sorted(skill_cnt.items(), key=lambda x:-x[1]):
    print(f'  {kw}: {cnt}/75个岗位提及')

print()
# 薪资取样
print('=== 薪资样本（前15个） ===')
for j in data[:15]:
    print(f'  {j["salary"]:25s} | {j["name"][:20]:20s} | {j["company"][:12]}')
