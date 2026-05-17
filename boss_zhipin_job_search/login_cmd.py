"""登录子命令：Cookie 提取 → CDP → patchright 打开浏览器（与 boss-agent-cli 降级顺序一致，不含 QR httpx）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import httpx

from boss_zhipin_job_search.auth_browser import login_via_browser, login_via_cdp, probe_cdp
from boss_zhipin_job_search.auth_cookie import extract_cookies

USER_INFO_URL = "https://www.zhipin.com/wapi/zpuser/wap/getUserInfo.json"


def verify_zhipin_token(token: dict[str, Any]) -> bool:
	"""用 getUserInfo 校验 Cookie 是否仍有效。"""
	try:
		resp = httpx.get(
			USER_INFO_URL,
			cookies=token.get("cookies", {}),
			headers={
				"User-Agent": token.get("user_agent")
				or "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
				"Referer": "https://www.zhipin.com/",
			},
			timeout=10,
		)
		data = resp.json()
		return bool(data.get("code") == 0)
	except (httpx.HTTPError, ValueError, KeyError):
		return False


def _ensure_patchright() -> None:
	try:
		from patchright.sync_api import sync_playwright  # noqa: F401
	except ImportError:
		raise SystemExit(
			"本步骤需要 patchright。请执行: pip install 'boss-zhipin-job-search[playwright]' "
			"然后: patchright install chromium",
		) from None


def acquire_token(
	*,
	cookie_browser: str | None,
	timeout: int,
	force_cdp: bool,
	cdp_url: str | None,
	patchright_only: bool,
	cookie_only: bool,
) -> tuple[dict[str, Any], str]:
	"""返回 (token, method_name)。"""
	if patchright_only:
		_ensure_patchright()
		return login_via_browser(timeout=timeout), "patchright 浏览器"

	if force_cdp:
		_ensure_patchright()
		return login_via_cdp(cdp_url=cdp_url, timeout=timeout), "CDP"

	print("[zhipin-search] 尝试从本机浏览器提取 Cookie…", file=sys.stderr)
	token = extract_cookies(cookie_browser)
	if token and token.get("cookies", {}).get("wt2"):
		if verify_zhipin_token(token):
			return token, "Cookie 提取"
		print("[zhipin-search] 提取的 Cookie 已失效，尝试其他方式…", file=sys.stderr)
	else:
		print("[zhipin-search] 未能从浏览器提取到有效 Cookie", file=sys.stderr)

	if cookie_only:
		raise SystemExit("Cookie 提取失败或未通过校验；请确认已在 Chrome/Edge 等中登录 zhipin.com")

	if probe_cdp(cdp_url):
		print("[zhipin-search] 检测到 CDP，尝试连接已打开的 Chrome…", file=sys.stderr)
		_ensure_patchright()
		try:
			return login_via_cdp(cdp_url=cdp_url, timeout=timeout), "CDP"
		except Exception as e:
			print(f"[zhipin-search] CDP 登录失败（{e}），将打开内置浏览器窗口…", file=sys.stderr)

	_ensure_patchright()
	return login_via_browser(timeout=timeout), "patchright 浏览器"


def login_main(argv: list[str] | None = None) -> None:
	import argparse

	p = argparse.ArgumentParser(description="获取 BOSS 直聘 token（Cookie / CDP / 打开浏览器登录）")
	p.add_argument("-o", "--output", type=Path, required=True, help="写入 token JSON 路径")
	p.add_argument("--timeout", type=int, default=120, help="等待登录超时（秒）")
	p.add_argument(
		"--browser",
		default="",
		help="仅 Cookie 模式时指定浏览器：chrome / edge / firefox / brave / opera / chromium",
	)
	p.add_argument("--cookie-only", action="store_true", help="只从本机读 Cookie，失败则退出")
	p.add_argument("--patchright-only", action="store_true", help="直接打开 patchright 窗口登录")
	p.add_argument("--force-cdp", action="store_true", help="跳过 Cookie，仅用 CDP（需调试端口 Chrome）")
	p.add_argument("--cdp-url", default="", help="CDP HTTP 根地址，默认 http://localhost:9222")
	args = p.parse_args(argv)

	cdp_url = args.cdp_url or None
	cookie_browser = args.browser or None

	token, method = acquire_token(
		cookie_browser=cookie_browser,
		timeout=args.timeout,
		force_cdp=args.force_cdp,
		cdp_url=cdp_url,
		patchright_only=args.patchright_only,
		cookie_only=args.cookie_only,
	)

	# 若 stoken 仍空，尝试从 cookie 字典补全
	if not token.get("stoken"):
		st = (token.get("cookies") or {}).get("__zp_stoken__", "")
		if st:
			token = {**token, "stoken": str(st)}

	out = {k: v for k, v in token.items() if not k.startswith("_")}
	args.output.parent.mkdir(parents=True, exist_ok=True)
	args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
	print(f"[zhipin-search] 已保存 token（{method}）→ {args.output}", file=sys.stderr)
