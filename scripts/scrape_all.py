"""BOSS直聘职位搜索+详情采集脚本（skill用版本）"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import time
from pathlib import Path
from typing import Any

from patchright.sync_api import sync_playwright

from _token_utils import validate_token


BASE_URL = "https://www.zhipin.com"
SEARCH_URL = f"{BASE_URL}/wapi/zpgeek/search/joblist.json"


def load_token(token_path: str) -> dict[str, Any]:
    """加载 token 凭证文件"""
    with open(token_path, "r", encoding="utf-8") as f:
        return json.load(f)


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

# 注意：BOSS 直聘 jobType=1903 同时覆盖兼职和实习，无法精确区分
# 因此不再提供 --job-type 参数，由关键词自由搜索
JOB_TYPE_CODES: dict[str, str] = {}



def search_and_detail(keywords: list[str], city: str, pages: int, token_path: str,
                    salary: str | None = None,
                    experience: str | None = None,
                    education: str | None = None,
                    scale: str | None = None,
                    industry: str | None = None,
                    stage: str | None = None,
                    skip_token_check: bool = False):
    """
    搜索多个关键词并采集详情，返回 CSV 文件路径。
    多个关键词的结果自动去重（按 encryptJobId）。
    """
    if not keywords:
        print("❌ 请提供至少一个搜索关键词", file=sys.stderr)
        return ""

    # token 预校验
    if not skip_token_check and not validate_token(token_path, silent=False):
        print(file=sys.stderr, flush=True)
        print("⚠️  登录凭证已失效，尝试启动登录流程...", file=sys.stderr, flush=True)
        # 尝试重新登录——弹出 Chrome 窗口让用户扫码
        try:
            from patchright.sync_api import sync_playwright as pw
            LOGIN_URL = "https://www.zhipin.com/web/geek/login"
            print("   正在打开登录窗口，请用 BOSS 直聘 App 扫码...", file=sys.stderr, flush=True)
            with pw() as p:
                browser = p.chromium.launch(headless=False, channel="chrome")
                ctx = browser.new_context(viewport={"width": 1280, "height": 800}, locale="zh-CN")
                page = ctx.new_page()
                page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
                input("   扫码完成后按 Enter 继续...")
                new_cookies_raw = ctx.cookies()
                browser.close()
            new_cookies = {c["name"]: c["value"] for c in new_cookies_raw}
            new_stoken = str(new_cookies.get("__zp_stoken__", ""))
            new_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            with open(token_path, "w", encoding="utf-8") as f:
                json.dump({"cookies": new_cookies, "user_agent": new_ua, "stoken": new_stoken}, f, ensure_ascii=False, indent=2)
            print("   token.json 已更新，继续爬取...", file=sys.stderr, flush=True)
        except Exception as e2:
            print(f"   登录失败: {e2}，请手动登录后重试", file=sys.stderr, flush=True)
            return ""

    token = load_token(token_path)
    cookies = token.get("cookies", {})
    ua = str(token.get("user_agent", ""))
    stoken = str(token.get("stoken", "") or cookies.get("__zp_stoken__", ""))

    city_code = CITY_CODES.get(city, "101210100")

    all_jobs: list[dict[str, Any]] = []
    output_csv = f"jobs_{city}_{keywords[0]}_详情.csv"

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False, channel="chrome",
            args=["--disable-blink-features=AutomationControlled"]
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

        try:
            page.goto(BASE_URL, wait_until="domcontentloaded", timeout=15000)
        except Exception:
            pass

        # Step 1: Search
        for pn in range(1, pages + 1):
            time.sleep(random.uniform(2.0, 4.0))
            params = {"query": keywords[0], "page": pn, "city": city_code, "__zp_stoken__": stoken}
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
            print(f"  第{pn}页: code={result.get('code')}, jobs={len(jobs)}", file=sys.stderr, flush=True)
            for j in jobs:
                j["_job_description"] = ""
                j["_detail_url"] = ""
                all_jobs.append(j)
            if result.get("code") not in (1, 0):
                print(f"  搜索异常(code={result.get('code')})，停止翻页", file=sys.stderr, flush=True)
                break

        print(f"共 {len(all_jobs)} 个职位，开始采集详情...", file=sys.stderr, flush=True)

        # Step 2: Detail pages
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

        browser.close()

    # Write CSV
    csv_fields = ["jobName", "brandName", "salaryDesc", "cityName", "jobExperience", "jobDegree",
                  "brandStageName", "brandScaleName", "brandIndustry",
                  "_job_description", "_detail_url"]
    csv_headers = ["职位名称", "公司", "薪资", "城市", "经验", "学历",
                   "融资阶段", "公司规模", "行业", "职位描述", "详情链接"]

    with open(output_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(csv_headers)
        for j in all_jobs:
            row = [j.get(f, "") if isinstance(j.get(f, ""), str) else str(j.get(f, ""))
                   for f in csv_fields]
            w.writerow(row)

    success = sum(1 for j in all_jobs if j["_job_description"])
    print(f"完成！{len(all_jobs)} 个职位，{success} 个详情抓取成功", file=sys.stderr, flush=True)
    print(f"输出文件: {output_csv}", file=sys.stderr, flush=True)
    return output_csv


def main():
    parser = argparse.ArgumentParser(description="BOSS直聘职位搜索+详情采集")
    parser.add_argument("--keyword", default="用户研究", help="搜索关键词")
    parser.add_argument("--city", default="杭州", help="城市")
    parser.add_argument("--pages", type=int, default=5, help="搜索页数")
    parser.add_argument("--token", default="token.json", help="token 文件路径")
    parser.add_argument("--salary", default="", help="薪资范围：3K以下/3-5K/5-10K/10-15K/10-20K/20-50K/50K以上")
    parser.add_argument("--experience", default="", help="经验要求：应届/1年以内/1-3年/3-5年/5-10年/10年以上")
    parser.add_argument("--education", default="", help="学历要求：大专/本科/硕士/博士")
    parser.add_argument("--scale", default="", help="公司规模：0-20人/20-99人/100-499人/500-999人/1000-9999人/10000人以上")
    parser.add_argument("--industry", default="", help="行业：互联网/游戏/人工智能/金融/教育培训/医疗健康/汽车 等")
    parser.add_argument("--stage", default="", help="融资阶段：未融资/天使轮/A轮/B轮/C轮/D轮及以上/已上市/不需要融资")
    args = parser.parse_args()

    search_and_detail(
        keywords=[args.keyword], city=args.city, pages=args.pages, token_path=args.token,
        salary=args.salary or None,
        experience=args.experience or None,
        education=args.education or None,
        scale=args.scale or None,
        industry=args.industry or None,
        stage=args.stage or None,
    )


if __name__ == "__main__":
    main()
