"""
简历匹配度评分模块

读取 user_resume.txt（或 user_resume.docx），对每个职位计算 0~100 匹配度。
输出排序后列表，匹配度高的靠前。

user_resume.txt 格式（示例）：
  学历：本科
  专业：语言学
  学校：华中科技大学
  技能：Python, NLP, 爬虫, 数据分析, HLM, SPSS
  研究方向：社交媒体分析, 用户行为, 情绪分析
  经验：0-1年
  目标岗位：用户研究

如没有简历文件，评分模块静默跳过，不影响正常生成报告。
"""
import json
import os
import re
from pathlib import Path


# 用户研究的核心技能/关键词清单
UR_SKILLS = [
    # 研究方法
    "用户研究", "用户调研", "用户访谈", "可用性测试", "焦点小组",
    "问卷", "问卷调查", "深度访谈", "田野调查", "人种志",
    "UCD", "用户中心设计", "用户旅程图", "用户体验地图",
    # 数据分析
    "数据分析", "统计分析", "Python", "SQL", "SPSS", "R语言",
    "HLM", "多层线性模型", "回归分析", "聚类分析", "因子分析",
    "文本分析", "情感分析", "NLP", "自然语言处理",
    # 数据采集
    "爬虫", "数据采集", "数据挖掘", "网络爬虫",
    # 产品相关
    "产品需求", "需求分析", "竞品分析", "AB测试", "A/B测试",
    "用户增长", "用户运营", "增长策略", "用户留存",
    # 行业背景
    "社交媒体", "社交平台", "微博", "社区运营", "内容生态",
    # 工具
    "Excel", "Tableau", "PowerBI", "Axure", "Figma", "Xmind",
    "Jupyter", "机器学习", "深度学习",
]

# 反相关关键词（出现则降分）
UR_ANTI_SKILLS = [
    "后端开发", "前端开发", "全栈", "Java开发", ".NET", "C++",
    "硬件", "嵌入式", "算法工程", "运维", "测试开发",
    "会计核算", "出纳", "法务", "HR", "人力资源",
    "销售", "门店", "客服", "物流", "仓管",
]

# 用户研究相关岗位名称关键词（按匹配度权重）
UR_JOB_TITLE_KEYWORDS = {
    "high": ["用户研究", "用户研究员", "ux研究员", "用户体验研究员"],
    "medium": ["用户增长", "用户运营", "用户产品", "用户洞察",
               "用研", "用户体验", "UX", "UED", "交互设计",
               "产品经理", "数据分析师", "消费者研究", "市场研究"],
    "low": ["产品运营", "策略产品", "内容运营", "社群运营", "数据运营"],
}


def load_resume(resume_path: str = "user_resume.txt") -> dict | None:
    """
    读取简历文本文件，返回结构化的用户画像字典。
    如果文件不存在，返回 None。
    """
    path = Path(resume_path)
    if not path.exists():
        # 尝试 .docx 版本
        docx_path = path.with_suffix(".docx")
        if docx_path.exists():
            try:
                import docx
                doc = docx.Document(str(docx_path))
                text = "\n".join(p.text for p in doc.paragraphs)
                return _parse_resume_text(text)
            except ImportError:
                pass
            except Exception:
                pass
        return None

    try:
        text = path.read_text("utf-8")
        return _parse_resume_text(text)
    except Exception:
        return None


def _parse_resume_text(text: str) -> dict:
    """解析简历文本为结构化数据"""
    resume = {
        "edu_level": "",       # 学历
        "major": "",           # 专业
        "school": "",          # 学校
        "skills": [],          # 技能列表
        "research_areas": [],  # 研究方向
        "experience_years": "", # 经验年限
        "target_roles": [],    # 目标岗位
        "raw_text": text,      # 原始文本（用于全文匹配）
    }

    lines = text.strip().split("\n")
    for line in lines:
        line = line.strip()
        if not line or "：" not in line:
            continue

        key, _, val = line.partition("：")
        key = key.strip()
        val = val.strip()

        if "学历" in key:
            resume["edu_level"] = val
        elif "专业" in key:
            resume["major"] = val
        elif "学校" in key:
            resume["school"] = val
        elif "技能" in key:
            resume["skills"] = [s.strip() for s in val.split(",") if s.strip()]
        elif "研究方向" in key or "研究领域" in key:
            resume["research_areas"] = [s.strip() for s in val.split(",") if s.strip()]
        elif "经验" in key:
            resume["experience_years"] = val
        elif "目标" in key or "意向" in key:
            resume["target_roles"] = [s.strip() for s in val.split(",") if s.strip()]

    return resume


def score_job(job: dict, resume: dict) -> int:
    """
    计算单个职位与用户画像的匹配度（0~100）。
    分数越高越匹配。

    评分维度：
    - 岗位名称匹配  (20分)
    - 学历匹配      (10分)
    - 经验匹配      (10分)
    - 技能匹配      (25分)
    - 研究领域匹配  (15分)
    - 行业领域匹配  (10分)
    - 反相关降分    (最高 -10分)
    """
    name = job.get("name", "")
    description = job.get("description", "")
    city = job.get("city", "")
    edu = job.get("edu", "")
    exp = job.get("exp", "")
    industry = job.get("industry", "")
    salary = job.get("salary", "")

    name_lower = name.lower()
    desc_lower = description.lower()

    score = 0

    # --- 1. 岗位名称匹配 (20分) ---
    title_score = 0
    for kw in UR_JOB_TITLE_KEYWORDS["high"]:
        if kw.lower() in name_lower:
            title_score = 20
            break
    if title_score == 0:
        for kw in UR_JOB_TITLE_KEYWORDS["medium"]:
            if kw.lower() in name_lower:
                title_score = 12
                break
    if title_score == 0:
        for kw in UR_JOB_TITLE_KEYWORDS["low"]:
            if kw.lower() in name_lower:
                title_score = 6
                break
    score += title_score

    # --- 2. 学历匹配 (10分) ---
    edu_level = resume.get("edu_level", "")
    if edu_level == "硕士":
        if "硕士" in edu:
            score += 10
        elif "博士" in edu:
            score += 8
        elif "本科" in edu:
            score += 6
        elif not edu or edu.lower() in ("学历不限", "不限"):
            score += 4
    elif edu_level == "博士":
        if "博士" in edu:
            score += 10
        elif "硕士" in edu:
            score += 6
        elif not edu:
            score += 3
    elif edu_level == "本科":
        if "本科" in edu or "硕士" in edu or "博士" in edu:
            score += 8
        elif not edu:
            score += 4

    # --- 3. 经验匹配 (10分) ---
    exp_years = resume.get("experience_years", "")
    is_intern = "实习" in name or "intern" in name_lower
    if "0" in exp_years or "应届" in exp_years or is_intern:
        if "应届" in exp or "1年以内" in exp:
            score += 10
        elif "1-3年" in exp:
            score += 7
        elif not exp or "经验不限" in exp:
            score += 6
        elif "3-5年" in exp:
            score += 3
        else:
            score += 1
    elif "1" in exp_years:
        if "1年以内" in exp or "1-3年" in exp:
            score += 9
        elif "3-5年" in exp:
            score += 5
        elif not exp:
            score += 4
        else:
            score += 2

    # --- 4. 技能匹配 (25分) ---
    skill_score = 0
    matched_skills = []
    resume_skills = set(s.lower() for s in resume.get("skills", []))
    resume_raw = resume.get("raw_text", "").lower()

    for sk in UR_SKILLS:
        if sk.lower() in desc_lower:
            matched_skills.append(sk)
            # JD 中提到的技能
            skill_score += 1
            # 如果简历中也明确提到，加权重
            if sk.lower() in resume_raw or any(rs in sk.lower() for rs in resume_skills):
                skill_score += 2

    score += min(skill_score, 25)

    # --- 5. 研究领域匹配 (15分) ---
    research_score = 0
    research_areas = [a.lower() for a in resume.get("research_areas", [])]
    for area in research_areas:
        if area in desc_lower:
            research_score += 5
    # 全文匹配
    if resume.get("research_areas"):
        # 检查研究领域关键词是否出现在 JD 中
        all_research_text = " ".join(research_areas)
        for word in all_research_text.split():
            if len(word) > 1 and word in desc_lower:
                research_score += 2
    score += min(research_score, 15)

    # --- 6. 行业领域匹配 (10分) ---
    industry_score = 0
    target_industries = ["互联网", "游戏", "社交", "内容", "科技",
                         "人工智能", "大数据", "软件", "消费",
                         "传媒", "教育", "医疗", "金融"]
    for ind in target_industries:
        if ind in industry:
            industry_score += 3
            break
    # JD 中提到的行业关键词
    for ind in target_industries:
        if ind in desc_lower:
            industry_score += 1
    score += min(industry_score, 10)

    # --- 7. 反相关降分 (最高 -10分) ---
    penalty = 0
    for anti in UR_ANTI_SKILLS:
        if anti.lower() in name_lower or anti.lower() in desc_lower:
            penalty -= 3
    score = max(score + penalty, 0)

    return score


def score_and_sort(jobs: list[dict], resume_path: str = "user_resume.txt") -> list[dict]:
    """
    主入口：加载简历 → 为每个职位打分 → 按分数降序排序 → 返回打过分的新列表。

    每个职位 dict 会新增字段：
      - _match_score: int   匹配度 0~100
      - _is_top: bool       True 表示高分（>= 60）
    """
    resume = load_resume(resume_path)
    if not resume:
        # 无简历，直接原序返回，每个职位标记 -1
        for j in jobs:
            j["_match_score"] = -1
            j["_is_top"] = False
        return jobs

    for j in jobs:
        j["_match_score"] = score_job(j, resume)
        j["_is_top"] = j["_match_score"] >= 60

    # 按分数降序，同分按原始顺序
    # 先存原始索引
    for idx, j in enumerate(jobs):
        j["_orig_idx"] = idx
    jobs.sort(key=lambda j: (-j["_match_score"], j["_orig_idx"]))
    for j in jobs:
        del j["_orig_idx"]

    return jobs


if __name__ == "__main__":
    # 测试模式
    import sys
    resume_path = sys.argv[1] if len(sys.argv) > 1 else "user_resume.txt"
    resume = load_resume(resume_path)
    if resume:
        print("✅ 简历加载成功:")
        print(f"   学历: {resume['edu_level']}")
        print(f"   专业: {resume['major']}")
        print(f"   技能: {resume['skills']}")
        print(f"   研究方向: {resume['research_areas']}")
    else:
        print(f"⚠️  未找到简历文件: {resume_path}")

    # 如果传了 jobs_data.json，跑评分
    json_path = sys.argv[2] if len(sys.argv) > 2 else "jobs_data.json"
    if os.path.exists(json_path) and resume:
        with open(json_path, "r", encoding="utf-8") as f:
            jobs = json.load(f)
        scored = score_and_sort(jobs, resume_path)
        print(f"\n📊 评分结果（共 {len(scored)} 个职位）:")
        print(f"{'排名':<4} {'分数':<4} {'职位名称':<24} {'公司':<20}")
        print("-" * 60)
        for i, j in enumerate(scored[:10], 1):
            star = "★" if j["_is_top"] else " "
            print(f"{star}{i:<3} {j['_match_score']:<4} {j['name'][:22]:<24} {j['company'][:18]:<20}")
        if len(scored) > 10:
            print(f"   ... 共 {len(scored)} 个")
