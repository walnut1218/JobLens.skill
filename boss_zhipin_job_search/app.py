#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BOSS 直聘「职位搜索」最小 CLI：调用站内 JSON API（非 HTML 爬虫）。

- 依赖：httpx（默认）；``--playwright`` 时需安装 ``boss-zhipin-job-search[playwright]``。
- 凭证：JSON 内含 ``cookies``、``stoken``、``user_agent``（可与 boss-agent-cli 登录导出格式一致）。

搜索::

	uv run zhipin-search --token path/to/token.json --query Python --city 北京

获取 token（从本机浏览器读 Cookie / CDP / 自动打开窗口登录）::

	uv run zhipin-search login -o path/to/token.json
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path
from typing import Any

import httpx

BASE_URL = "https://www.zhipin.com"
SEARCH_PATH = "/wapi/zpgeek/search/joblist.json"
SEARCH_REFERER = f"{BASE_URL}/web/geek/job"

DEFAULT_HEADERS: dict[str, str] = {
	"User-Agent": (
		"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
		"(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
	),
	"sec-ch-ua": '"Chromium";v="145", "Not(A:Brand";v="99", "Google Chrome";v="145"',
	"sec-ch-ua-mobile": "?0",
	"sec-ch-ua-platform": '"macOS"',
	"Sec-Fetch-Dest": "empty",
	"Sec-Fetch-Mode": "cors",
	"Sec-Fetch-Site": "same-origin",
	"Accept": "application/json, text/plain, */*",
	"Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
	"DNT": "1",
}

CITY_CODES: dict[str, str] = {
	"北京": "101010100",
	"上海": "101020100",
	"广州": "101280100",
	"深圳": "101280600",
	"杭州": "101210100",
	"成都": "101270100",
	"南京": "101190100",
	"武汉": "101200100",
	"西安": "101110100",
	"苏州": "101190400",
	"长沙": "101250100",
	"郑州": "101180100",
	"重庆": "101040100",
	"天津": "101030100",
	"合肥": "101220100",
	"厦门": "101230200",
	"济南": "101120100",
	"青岛": "101120200",
	"大连": "101070200",
	"宁波": "101210400",
	"福州": "101230100",
	"东莞": "101281600",
	"珠海": "101280700",
	"佛山": "101280800",
	"昆明": "101290100",
	"贵阳": "101260100",
	"太原": "101100100",
	"南昌": "101240100",
	"南宁": "101300100",
	"石家庄": "101090100",
	"哈尔滨": "101050100",
	"长春": "101060100",
	"沈阳": "101070100",
	"海口": "101310100",
	"兰州": "101160100",
	"乌鲁木齐": "101130100",
	"无锡": "101190200",
	"常州": "101191100",
	"温州": "101210700",
	"惠州": "101280300",
}

SALARY_CODES: dict[str, str] = {
	"3K以下": "401",
	"3-5K": "402",
	"5-10K": "403",
	"10-15K": "404",
	"10-20K": "405",
	"20-50K": "406",
	"50K以上": "407",
}

EXPERIENCE_CODES: dict[str, str] = {
	"应届": "108",
	"1年以内": "101",
	"1-3年": "103",
	"3-5年": "104",
	"5-10年": "105",
	"10年以上": "106",
}

EDUCATION_CODES: dict[str, str] = {
	"大专": "202",
	"本科": "203",
	"硕士": "204",
	"博士": "205",
}

SCALE_CODES: dict[str, str] = {
	"0-20人": "301",
	"20-99人": "302",
	"100-499人": "303",
	"500-999人": "304",
	"1000-9999人": "305",
	"10000人以上": "306",
}

INDUSTRY_CODES: dict[str, str] = {
	"不限": "0",
	"互联网": "100020",
	"电子商务": "100021",
	"游戏": "100024",
	"软件/信息服务": "100032",
	"人工智能": "100901",
	"大数据": "100902",
	"云计算": "100903",
	"区块链": "100904",
	"物联网": "100905",
	"金融": "100101",
	"银行": "100102",
	"保险": "100103",
	"证券/基金": "100104",
	"教育培训": "100200",
	"医疗健康": "100300",
	"房地产": "100400",
	"汽车": "100500",
	"物流/运输": "100600",
	"广告/传媒": "100700",
	"消费品": "100800",
	"制造业": "101000",
	"能源/环保": "101100",
	"政府/非营利": "101200",
	"农业": "101300",
}

STAGE_CODES: dict[str, str] = {
	"不限": "0",
	"未融资": "801",
	"天使轮": "802",
	"A轮": "803",
	"B轮": "804",
	"C轮": "805",
	"D轮及以上": "806",
	"已上市": "807",
	"不需要融资": "808",
}

JOB_TYPE_CODES: dict[str, str] = {
	"全职": "1901",
	"兼职": "1903",
	"实习": "1903",
}


def _platform_sec_ch_ua() -> str:
	import sys

	if sys.platform == "win32":
		return '"Windows"'
	if sys.platform == "linux":
		return '"Linux"'
	return DEFAULT_HEADERS.get("sec-ch-ua-platform", '"macOS"')


def load_token(path: Path) -> dict[str, Any]:
	data = json.loads(path.read_text(encoding="utf-8"))
	if "cookies" not in data:
		raise SystemExit('token 文件需包含 "cookies" 字段（name -> value 映射）')
	return data


def build_params(
	query: str,
	page: int,
	*,
	city: str | None,
	salary: str | None,
	experience: str | None,
	education: str | None,
	scale: str | None,
	industry: str | None,
	stage: str | None,
	job_type: str | None,
	stoken: str,
) -> dict[str, Any]:
	params: dict[str, Any] = {"query": query, "page": page, "__zp_stoken__": stoken}
	if city:
		code = CITY_CODES.get(city)
		if code is None:
			raise SystemExit(f"未知城市: {city}")
		params["city"] = code
	if salary:
		if c := SALARY_CODES.get(salary):
			params["salary"] = c
	if experience:
		if c := EXPERIENCE_CODES.get(experience):
			params["experience"] = c
	if education:
		if c := EDUCATION_CODES.get(education):
			params["degree"] = c
	if scale:
		if c := SCALE_CODES.get(scale):
			params["scale"] = c
	if industry:
		if c := INDUSTRY_CODES.get(industry):
			params["industry"] = c
	if stage:
		if c := STAGE_CODES.get(stage):
			params["stage"] = c
	if job_type:
		if c := JOB_TYPE_CODES.get(job_type):
			params["jobType"] = c
	return params


def throttle(delay: tuple[float, float]) -> None:
	time.sleep(random.uniform(delay[0], delay[1]))


def search_via_httpx(token: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
	headers = dict(DEFAULT_HEADERS)
	headers["Referer"] = SEARCH_REFERER
	headers["sec-ch-ua-platform"] = _platform_sec_ch_ua()
	if ua := token.get("user_agent"):
		headers["User-Agent"] = str(ua)
	cookies = token.get("cookies") or {}
	with httpx.Client(
		base_url=BASE_URL,
		cookies=cookies,
		headers=headers,
		follow_redirects=True,
		timeout=30,
	) as client:
		resp = client.get(SEARCH_PATH, params=params)
		resp.raise_for_status()
		return resp.json()


def search_via_playwright(token: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
	try:
		from patchright.sync_api import sync_playwright
	except ImportError as e:
		raise SystemExit(
			"未安装 patchright，请执行: pip install 'boss-zhipin-job-search[playwright]' "
			"然后: patchright install chromium",
		) from e

	cookies = token.get("cookies") or {}
	user_agent = str(token.get("user_agent") or DEFAULT_HEADERS["User-Agent"])
	referer = SEARCH_REFERER
	url = BASE_URL + SEARCH_PATH

	with sync_playwright() as p:
		channel = None
		if sys.platform == "win32":
			# 尝试用系统 Chrome（真实浏览器指纹）
			channel = "chrome"
		browser = p.chromium.launch(
			headless=False,
			channel=channel,
			args=["--disable-blink-features=AutomationControlled"],
		)
		try:
			context = browser.new_context(
				user_agent=user_agent,
				viewport={"width": 1280, "height": 800},
				locale="zh-CN",
				timezone_id="Asia/Shanghai",
			)
			page = context.new_page()
			# 先导航到 zhipin.com，确保 Cookie 域匹配
			try:
				page.goto(BASE_URL, wait_until="domcontentloaded", timeout=15000)
			except Exception:
				pass
			pw_cookies: list[dict[str, Any]] = []
			for name, value in cookies.items():
				pw_cookies.append(
					{"name": str(name), "value": str(value), "domain": ".zhipin.com", "path": "/"},
				)
			if pw_cookies:
				context.add_cookies(pw_cookies)
			result = page.evaluate(
				"""
				async ({method, url, params, referer}) => {
					try {
						let fetchUrl = url;
						if (params && Object.keys(params).length > 0) {
							const sp = new URLSearchParams();
							for (const [k, v] of Object.entries(params)) {
								if (v !== null && v !== undefined) sp.append(k, String(v));
							}
							fetchUrl = url + '?' + sp.toString();
						}
						const options = {
							method: method,
							credentials: 'include',
							headers: {
								'Accept': 'application/json, text/plain, */*',
								'Referer': referer,
								'X-Requested-With': 'XMLHttpRequest',
							},
						};
						const resp = await fetch(fetchUrl, options);
						return await resp.json();
					} catch (e) {
						return {code: -1, message: e.message, zpData: {}};
					}
				}
				""",
				{"method": "GET", "url": url, "params": params, "referer": referer},
			)
		finally:
			browser.close()

	return result  # type: ignore[no-any-return]


def _print_job_titles(data: dict[str, Any]) -> None:
	zp = data.get("zpData") or {}
	jobs = zp.get("jobList") or []
	code = data.get("code")
	print(f"code={code} jobs={len(jobs)}", file=sys.stderr)
	for j in jobs:
		name = j.get("jobName", "")
		brand = j.get("brandName", "")
		print(f"- {name} @ {brand}")


def search_main(argv: list[str] | None = None) -> None:
	ap = argparse.ArgumentParser(
		description="BOSS 直聘职位搜索（独立小项目）",
		epilog="获取凭证: zhipin-search login -o token.json",
		formatter_class=argparse.RawDescriptionHelpFormatter,
	)
	ap.add_argument("--token", type=Path, required=True, help="token JSON：cookies + stoken + user_agent")
	ap.add_argument("--query", required=True, help="搜索关键词")
	ap.add_argument("--city", default="", help="城市中文名，如 北京")
	ap.add_argument("--salary", default="", help="薪资档，如 20-50K")
	ap.add_argument("--experience", default="", help="经验，如 3-5年")
	ap.add_argument("--education", default="", help="学历，如 本科")
	ap.add_argument("--scale", default="", help="公司规模")
	ap.add_argument("--industry", default="", help="行业")
	ap.add_argument("--stage", default="", help="融资阶段")
	ap.add_argument("--job-type", default="", dest="job_type", help="职位类型：全职/兼职/实习")
	ap.add_argument("--pages", type=int, default=1, help="从第 1 页起连续抓取页数")
	ap.add_argument("--delay-min", type=float, default=1.5, help="页间延迟下限（秒）")
	ap.add_argument("--delay-max", type=float, default=3.0, help="页间延迟上限（秒）")
	ap.add_argument("--playwright", action="store_true", help="用 patchright 在页面内 fetch")
	ap.add_argument("--json", action="store_true", help="每页完整 JSON 输出到 stdout（JSON Lines）")
	args = ap.parse_args(argv)

	token = load_token(args.token)
	stoken = str(token.get("stoken", "") or "")
	if not stoken:
		stoken = str((token.get("cookies") or {}).get("__zp_stoken__", "") or "")
	if not stoken:
		print("警告: 未找到 stoken，请求可能失败；请使用完整登录导出文件。", file=sys.stderr)

	delay = (args.delay_min, args.delay_max)
	if args.delay_min > args.delay_max:
		raise SystemExit("delay-min 不能大于 delay-max")

	filters = {
		"city": args.city or None,
		"salary": args.salary or None,
		"experience": args.experience or None,
		"education": args.education or None,
		"scale": args.scale or None,
		"industry": args.industry or None,
		"stage": args.stage or None,
		"job_type": args.job_type or None,
	}

	for page in range(1, args.pages + 1):
		throttle(delay)
		params = build_params(args.query, page, stoken=stoken, **filters)
		if args.playwright:
			data = search_via_playwright(token, params)
		else:
			data = search_via_httpx(token, params)

		if args.json:
			print(json.dumps(data, ensure_ascii=False))
		else:
			_print_job_titles(data)


def main() -> None:
	rest = sys.argv[1:]
	if rest and rest[0] == "login":
		from boss_zhipin_job_search.login_cmd import login_main

		login_main(rest[1:])
		return
	search_main()
