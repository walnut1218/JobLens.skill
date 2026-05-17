"""
每日新岗位推送脚本 - 供 cron / 用户主动触发 调用

流程：
1. 爬取最新职位（支持 headless 模式）
2. 去重过滤（比对 seen_jobs.txt）
3. 输出结果

用法：
  uv run python scripts/push_daily.py --city 杭州 --keyword 用户研究 --pages 3

环境要求：
- token.json 需存在于 skill 根目录
- 已安装 Chrome 浏览器（通过 channel=chrome 调用）
"""
import argparse
import json
import os
import re
import sys
import time
import random
import csv
from pathlib import Path

from patchright.sync_api import sync_playwright

from _token_utils import validate_token

# ---- 常量 ----
BASE_URL = "https://www.zhipin.com"
SEARCH_URL = f"{BASE_URL}/wapi/zpgeek/search/joblist.json"

# ---- 依赖现有的 dedup 函数 ----
def _extract_job_id(url: str) -> str:
    m = re.search(r'/job_detail/([a-zA-Z0-9_\-]+)\.html', url or '')
    return m.group(1) if m else url


def load_seen(seen_path: str) -> set[str]:
    path = Path(seen_path)
    if not path.exists():
        return set()
    with open(path, "r", encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def save_seen(seen_path: str, ids: set[str]):
    with open(seen_path, "a", encoding="utf-8") as f:
        for jid in ids:
            f.write(jid + "\n")


# ---- 编码映射 ----
CITY_CODES: dict[str, str] = {
    "北京": "101010100", "上海": "101020100", "广州": "101280100",
    "深圳": "101280600", "杭州": "101210100", "成都": "101270100",
    "南京": "101190100", "武汉": "101200100", "西安": "101110100",
    "苏州": "101190400", "长沙": "101250100", "郑州": "101180100",
    "重庆": "101040100", "天津": "101030100", "合肥": "101220100",
    "厦门": "101230200", "济南": "101120100", "青岛": "101120200",
    "大连": "101070200", "宁波": "101210400", "福州": "101230100",
    "东莞": "101281600", "珠海": "101280700", "佛山": "101280800",
    "昆明": "101290100", "贵阳": "101260100", "太原": "101100100",
    "南昌": "101240100", "南宁": "101300100", "石家庄": "101090100",
    "哈尔滨": "101050100", "长春": "101060100", "沈阳": "101070100",
    "海口": "101310100", "兰州": "101160100", "乌鲁木齐": "101130100",
    "无锡": "101190200", "常州": "101191100", "温州": "101210700",
    "惠州": "101280300",
}

SALARY_CODES: dict[str, str] = {
    "3K以下": "401", "3-5K": "402", "5-10K": "403",
    "10-15K": "404", "10-20K": "405", "20-50K": "406", "50K以上": "407",
}

EXPERIENCE_CODES: dict[str, str] = {
    "应届": "108", "1年以内": "101", "1-3年": "103",
    "3-5年": "104", "5-10年": "105", "10年以上": "106",
}

EDUCATION_CODES: dict[str, str] = {
    "大专": "202", "本科": "203", "硕士": "204", "博士": "205",
}

SCALE_CODES: dict[str, str] = {
    "0-20人": "301", "20-99人": "302", "100-499人": "303",
    "500-999人": "304", "1000-9999人": "305", "10000人以上": "306",
}

INDUSTRY_CODES: dict[str, str] = {
    "互联网": "100020", "电子商务": "100021", "游戏": "100024",
    "软件/信息服务": "100032", "人工智能": "100901", "大数据": "100902",
    "云计算": "100903", "区块链": "100904", "物联网": "100905",
    "金融": "100101", "银行": "100102", "保险": "100103",
    "证券/基金": "100104", "教育培训": "100200", "医疗健康": "100300",
    "房地产": "100400", "汽车": "100500", "物流/运输": "100600",
    "广告/传媒": "100700", "消费品": "100800", "制造业": "101000",
    "能源/环保": "101100", "政府/非营利": "101200", "农业": "101300",
}

STAGE_CODES: dict[str, str] = {
    "未融资": "801", "天使轮": "802", "A轮": "803",
    "B轮": "804", "C轮": "805", "D轮及以上": "806",
    "已上市": "807", "不需要融资": "808",
}

JOB_TYPE_CODES: dict[str, str] = {}


# ---- 搜索 + 详情采集（headless 版本，带自动降级） ----
def _save_token(token_path: str, cookies: dict, ua: str, stoken: str):
    """更新 token.json 中的 cookie 值（登录后 cookie 可能变更）"""
    data = {"cookies": cookies, "user_agent": ua, "stoken": stoken}
    with open(token_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _do_search_collect(
    keyword: str, city: str, pages: int,
    token_path: str, seen_path: str, output_dir: str,
    headless: bool,
    salary: str | None = None,
    experience: str | None = None,
    education: str | None = None,
    scale: str | None = None,
    industry: str | None = None,
    stage: str | None = None,
) -> tuple[list[dict], int]:
    """
    执行一轮搜索+详情采集。
    返回：(all_raw_jobs, worst_code)
    其中 worst_code 是搜索过程中遇到的最差 code（0=正常, 37=风控, -1=异常）
    """
    with open(token_path, "r", encoding="utf-8") as f:
        token = json.load(f)
    cookies = token.get("cookies", {})
    ua = token.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
    stoken = str(token.get("stoken", "") or cookies.get("__zp_stoken__", ""))
    city_code = CITY_CODES.get(city, "101210100")

    all_jobs: list[dict] = []
    worst_code = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            channel="chrome",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-gpu",
                "--window-size=1280,800",
            ]
        )
        context = browser.new_context(
            user_agent=ua, locale="zh-CN",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()

        try:
            page.goto(BASE_URL, wait_until="domcontentloaded", timeout=15000)
        except Exception:
            pass

        pw_cookies = [
            {"name": n, "value": v, "domain": ".zhipin.com", "path": "/"}
            for n, v in cookies.items()
        ]
        if pw_cookies:
            context.add_cookies(pw_cookies)

        # Search pages
        for pn in range(1, pages + 1):
            time.sleep(random.uniform(2.0, 4.0))
            params = {"query": keyword, "page": pn, "city": city_code, "__zp_stoken__": stoken}
            if salary and (sc := SALARY_CODES.get(salary)):
                params["salary"] = sc
            if experience and (ec := EXPERIENCE_CODES.get(experience)):
                params["experience"] = ec
            if education and (edc := EDUCATION_CODES.get(education)):
                params["degree"] = edc
            if scale and (slc := SCALE_CODES.get(scale)):
                params["scale"] = slc
            if industry and (ic := INDUSTRY_CODES.get(industry)):
                params["industry"] = ic
            if stage and (stc := STAGE_CODES.get(stage)):
                params["stage"] = stc

            result = page.evaluate("""
                async (params) => {
                    try {
                        const sp = new URLSearchParams();
                        for (const [k, v] of Object.entries(params)) {
                            if (v != null) sp.append(k, String(v));
                        }
                        const resp = await fetch('""" + SEARCH_URL + """?' + sp.toString(), {
                            method: 'GET', credentials: 'include',
                            headers: {
                                'Accept': 'application/json, text/plain, */*',
                                'Referer': 'https://www.zhipin.com/web/geek/job',
                                'X-Requested-With': 'XMLHttpRequest'
                            }
                        });
                        return await resp.json();
                    } catch(e) {
                        return {code: -1, message: e.message, zpData: {}};
                    }
                }
            """, params)

            jobs = result.get("zpData", {}).get("jobList", [])
            code = result.get("code", -1)
            print(f"  第{pn}页: code={code}, jobs={len(jobs)}", file=sys.stderr, flush=True)

            for j in jobs:
                j["_job_description"] = ""
                j["_detail_url"] = ""
                all_jobs.append(j)

            if abs(code) > abs(worst_code):
                worst_code = code

            if code not in (1, 0):
                print(f"  搜索异常(code={code})，停止翻页", file=sys.stderr, flush=True)
                break

        # Only collect details if search succeeded
        if not all_jobs:
            browser.close()
            return all_jobs, worst_code

        print(f"共 {len(all_jobs)} 个职位，开始采集详情...", file=sys.stderr, flush=True)
        for idx, job in enumerate(all_jobs):
            jid = job.get("encryptJobId", "")
            if not jid:
                continue
            time.sleep(random.uniform(1.5, 3.0))
            detail_url = f"{BASE_URL}/job_detail/{jid}.html"
            job["_detail_url"] = detail_url
            try:
                page.goto(detail_url, wait_until="domcontentloaded", timeout=20000)
                desc = page.evaluate("""
                    () => {
                        const sel = document.querySelector('.job-sec-text');
                        if (sel && sel.innerText.trim()) return sel.innerText;
                        const sec = document.querySelectorAll('.job-section, .job-detail__content, .text');
                        for (const s of sec) {
                            if (s.innerText.length > 50) return s.innerText;
                        }
                        return '';
                    }
                """)
                job["_job_description"] = desc if desc else ""
                desc_len = len(job["_job_description"])
                print(f"  [{idx+1}/{len(all_jobs)}] {job.get('jobName','')[:20]}... desc={desc_len}字", file=sys.stderr, flush=True)
            except Exception as e:
                print(f"  [{idx+1}/{len(all_jobs)}] FAILED: {jid} - {e}", file=sys.stderr, flush=True)

        # Save updated cookies (token may have changed during session)
        try:
            new_cookies_raw = context.cookies()
            new_cookies = {c["name"]: c["value"] for c in new_cookies_raw}
            new_stoken = str(new_cookies.get("__zp_stoken__", stoken))
            if new_cookies:
                _save_token(token_path, new_cookies, ua, new_stoken)
        except Exception:
            pass

        browser.close()

    return all_jobs, worst_code


def _dedup_and_output(all_jobs: list[dict], seen_path: str, output_dir: str) -> list[dict]:
    """去重过滤 + 写 jobs_data.json + 返回新职位列表"""
    seen = load_seen(seen_path)
    new_jobs = []
    seen_count = 0
    detail_count = 0

    for job in all_jobs:
        url = job.get("_detail_url", "")
        jid = job.get("encryptJobId", "") or _extract_job_id(url)

        if jid in seen:
            seen_count += 1
            continue
        seen.add(jid)

        formatted = {
            "encryptJobId": jid,
            "name": job.get("jobName", ""),
            "company": job.get("brandName", ""),
            "salary": job.get("salaryDesc", ""),
            "city": job.get("cityName", ""),
            "exp": job.get("jobExperience", ""),
            "edu": job.get("jobDegree", ""),
            "stage": job.get("brandStageName", ""),
            "scale": job.get("brandScaleName", ""),
            "industry": job.get("brandIndustry", ""),
            "description": job.get("_job_description", ""),
            "url": url,
        }
        if formatted["description"]:
            detail_count += 1
        new_jobs.append(formatted)

    new_ids = {j["encryptJobId"] for j in new_jobs}
    save_seen(seen_path, new_ids)

    if new_jobs:
        jobs_data_path = os.path.join(output_dir, "jobs_data.json")
        with open(jobs_data_path, "w", encoding="utf-8") as f:
            json.dump(new_jobs, f, ensure_ascii=False, indent=2)
        print(f"  jobs_data.json 已写入: {len(new_jobs)} 个新职位", file=sys.stderr, flush=True)

    print(file=sys.stderr, flush=True)
    print(f"📊 每日检查结果:", file=sys.stderr, flush=True)
    print(f"   共扫描: {len(all_jobs)} 个职位", file=sys.stderr, flush=True)
    print(f"   已见跳过: {seen_count} 个", file=sys.stderr, flush=True)
    print(f"   新职位: {len(new_jobs)} 个（含详情: {detail_count} 个）", file=sys.stderr, flush=True)
    print(file=sys.stderr, flush=True)

    return new_jobs


def search_and_detail_headless(
    keyword: str, city: str, pages: int,
    token_path: str, seen_path: str, output_dir: str,
    salary: str | None = None,
    experience: str | None = None,
    education: str | None = None,
    scale: str | None = None,
    industry: str | None = None,
    stage: str | None = None,
) -> list[dict]:
    """
    爬取职位 -> 去重 -> 返回新职位列表。

    headless 模式遇到 code=37/36 时自动降级：
    1. 弹出可见 Chrome 浏览器
    2. 重新导航至 BOSS 直聘
    3. 等待页面加载后重新尝试搜索
    """
    if not os.path.exists(token_path):
        print("❌ token.json 不存在，请先登录", file=sys.stderr)
        return []

    # token 预校验（仅给一次警告）
    if not validate_token(token_path, silent=False):
        print("⚠️  token 已失效，请重新登录后再试。运行 run.ps1 前先手动扫码登录。", file=sys.stderr)
        print("   跳过本次每日检查。", file=sys.stderr)
        return []

    print(f"🔍 搜索: {keyword} @ {city}（headless 模式）", file=sys.stderr, flush=True)
    all_jobs, worst_code = _do_search_collect(
        keyword, city, pages, token_path, seen_path, output_dir,
        headless=True,
        salary=salary, experience=experience,
        education=education, scale=scale,
        industry=industry, stage=stage,
    )

    # 如果 headless 模式被风控，自动降级到可见浏览器
    if worst_code in (37, 36):
        print(f"⚠️  headless 模式被风控(code={worst_code})，自动降级到可见浏览器...", file=sys.stderr, flush=True)
        print(f"   正在弹出 Chrome 窗口，无需手动操作", file=sys.stderr, flush=True)
        all_jobs, _ = _do_search_collect(
            keyword, city, pages, token_path, seen_path, output_dir,
            headless=False,
            salary=salary, experience=experience,
            education=education, scale=scale,
            industry=industry, stage=stage,
        )

    if not all_jobs:
        print(f"❌ 搜索失败，无有效职位数据", file=sys.stderr, flush=True)
        return []

    return _dedup_and_output(all_jobs, seen_path, output_dir)


def main():
    parser = argparse.ArgumentParser(description="每日新岗位推送")
    parser.add_argument("--city", default="杭州")
    parser.add_argument("--keyword", default="用户研究")
    parser.add_argument("--pages", type=int, default=3)
    parser.add_argument("--salary", default="", help="薪资范围：3K以下/3-5K/5-10K/10-15K/10-20K/20-50K/50K以上")
    parser.add_argument("--experience", default="", help="经验要求：应届/1年以内/1-3年/3-5年/5-10年/10年以上")
    parser.add_argument("--education", default="", help="学历要求：大专/本科/硕士/博士")
    parser.add_argument("--scale", default="", help="公司规模：0-20人/20-99人/100-499人/500-999人/1000-9999人/10000人以上")
    parser.add_argument("--industry", default="", help="行业：互联网/游戏/人工智能/金融/教育培训/医疗健康/汽车 等")
    parser.add_argument("--stage", default="", help="融资阶段：未融资/天使轮/A轮/B轮/C轮/D轮及以上/已上市/不需要融资")
    args = parser.parse_args()

    # 路径定位：脚本在 scripts/ 子目录，skill 根目录是 parent
    script_dir = Path(__file__).resolve().parent
    root_dir = script_dir.parent

    token_path = root_dir / "token.json"
    seen_path = root_dir / "seen_jobs.txt"
    output_dir = root_dir

    if not token_path.exists():
        print("❌ token.json 不存在，无法爬取")
        print("RESULT:NO_TOKEN")
        return

    print(f"🔍 开始每日检查: {args.city} · {args.keyword} · {args.pages}页", file=sys.stderr, flush=True)

    new_jobs = search_and_detail_headless(
        args.keyword, args.city, args.pages,
        str(token_path), str(seen_path), str(output_dir),
        salary=args.salary or None,
        experience=args.experience or None,
        education=args.education or None,
        scale=args.scale or None,
        industry=args.industry or None,
        stage=args.stage or None,
    )

    # ---- Stdout 输出（供 cron agent 读取） ----
    if not new_jobs:
        print("RESULT:NO_NEW_JOBS")
        # 中文摘要输出到 stderr 已包含

    # 按公司分组展示新职位
    companies = {}
    for j in new_jobs:
        c = j["company"]
        if c not in companies:
            companies[c] = []
        companies[c].append(j)

    print(f"RESULT:NEW_JOBS|{len(new_jobs)}")
    print(f"{'='*40}")
    has_desc = sum(1 for j in new_jobs if j.get("description"))
    print(f"【每日新岗位 · {args.city} · {args.keyword}】")
    print(f"发现 {len(new_jobs)} 个新职位，{has_desc} 个详情已采集")
    print()
    for c, jobs in sorted(companies.items()):
        print(f"🏢 {c}")
        for j in jobs:
            desc_flag = "📄" if j.get("description") else "❌"
            print(f"  {desc_flag} {j['name']} | {j['salary']} | {j.get('edu','')}")
        print()
    print(f"{'='*40}")
    if new_jobs:
        print("💡 提示：已生成 jobs_data.json，运行报告脚本即可出 Word 报告")


if __name__ == "__main__":
    main()
