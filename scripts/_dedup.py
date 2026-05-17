"""
BOSS直聘职位去重脚本 - 已见 ID 记录本

功能：
1. 从爬虫 CSV 中读取所有职位
2. 从 seen_jobs.txt 读取已处理的 Job ID
3. 过滤掉已处理的旧职位，只保留新职位
4. 输出 jobs_data.json（仅新职位）
5. 返回新职位数量（供后续流程判断）

用途：多次触发技能时，AI 每次只分析"新鲜批次"

ID 来源：从 _detail_url 中提取 encryptId
  URL 格式: https://www.zhipin.com/job_detail/{encryptId}.html
"""
import csv
import json
import os
import re
import sys
from pathlib import Path


SEEN_FILE = "seen_jobs.txt"
OUTPUT_JSON = "jobs_data.json"


def _extract_job_id(url: str) -> str:
    """从 BOSS 直聘详情 URL 中提取唯一 Job ID"""
    m = re.search(r'/job_detail/([a-zA-Z0-9_\-]+)\.html', url or '')
    if m:
        return m.group(1)
    return url


def load_seen(seen_path: str) -> set[str]:
    """读取已见 ID 记录"""
    path = Path(seen_path)
    if not path.exists():
        return set()
    with open(path, "r", encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def save_seen(seen_path: str, ids: set[str]):
    """追加写入新 ID 到已见记录"""
    with open(seen_path, "a", encoding="utf-8") as f:
        for jid in ids:
            f.write(jid + "\n")


def dedup_from_csv(csv_path: str, cwd: str = ".") -> list[dict]:
    """
    主逻辑：读 CSV → 去重 → 写 jobs_data.json

    返回：新职位列表（每个职位 dict 包含 encryptJobId）
    """
    os.chdir(cwd)
    seen = load_seen(SEEN_FILE)

    csv_fields = ["职位名称", "公司", "薪资", "城市", "经验", "学历",
                   "融资阶段", "公司规模", "行业", "职位描述", "详情链接"]

    all_jobs = []
    seen_count = 0
    new_count = 0
    new_jobs = []
    total = 0

    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row_idx, row in enumerate(reader, 1):
            total += 1
            url = row.get("详情链接", "")
            jid = _extract_job_id(url)

            job = {
                "idx": row_idx,
                "encryptJobId": jid,
                "name": row.get("职位名称", ""),
                "company": row.get("公司", ""),
                "salary": row.get("薪资", ""),
                "city": row.get("城市", ""),
                "exp": row.get("经验", ""),
                "edu": row.get("学历", ""),
                "stage": row.get("融资阶段", ""),
                "scale": row.get("公司规模", ""),
                "industry": row.get("行业", ""),
                "description": row.get("职位描述", ""),
                "url": url,
            }

            all_jobs.append(job)

            if jid in seen:
                seen_count += 1
            else:
                new_count += 1
                seen.add(jid)
                new_jobs.append(job)

    # 写 jobs_data.json（仅新职位）
    if new_jobs:
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(new_jobs, f, ensure_ascii=False, indent=2)

    # 更新 seen_jobs.txt（追加本次新出现的 ID）
    new_ids = {j["encryptJobId"] for j in new_jobs}
    save_seen(SEEN_FILE, new_ids)

    print(f"📊 去重结果:", file=sys.stderr)
    print(f"   共扫描 {total} 个职位", file=sys.stderr)
    print(f"   已见(跳过): {seen_count} 个", file=sys.stderr)
    print(f"   新职位:  {new_count} 个", file=sys.stderr)
    print(f"   已见 ID 记录总计: {len(load_seen(SEEN_FILE))} 个", file=sys.stderr)
    print(f"   jobs_data.json: {'✓ 已写入' if new_jobs else '✗ 无新职位，跳过'}", file=sys.stderr)

    return new_jobs


def entry(csv_path: str, cwd: str = ".") -> bool:
    """
    供 SKILL.md 调用的入口函数
    
    返回 True = 有新职位待分析
    返回 False = 全部已见，无需分析
    """
    new_jobs = dedup_from_csv(csv_path, cwd)
    if new_jobs:
        print(f"✓ {len(new_jobs)} 个新职位等待 AI 分析", file=sys.stderr)
        return True
    else:
        print("⏹ 没有新职位，无需分析", file=sys.stderr)
        return False


if __name__ == "__main__":
    # CLI 用法：python scripts/_dedup.py <csv_path>
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "jobs_杭州_用户研究实习生_详情.csv"
    entry(csv_path)
