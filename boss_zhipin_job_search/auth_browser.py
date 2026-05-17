"""CDP / patchright 登录与 stoken 提取（与 boss-agent-cli.auth.browser 中 zhipin 分支对齐）。"""

from __future__ import annotations

import sys
import time
from typing import Any, cast

LOGIN_PAGE_URL = "https://www.zhipin.com/web/user/"
HOME_URL = "https://www.zhipin.com/"
_DEFAULT_CDP_URL = "http://localhost:9222"

_CDP_PROBE_TIMEOUT = 3
_NAV_TIMEOUT_MS = 15000
_NETWORKIDLE_GRACE_MS = 3000
_POST_LOGIN_WAIT = 3
_STOKEN_GENERATION_WAIT = 2


def _warm_home_for_runtime(page: Any, home_url: str, *, stage: str) -> None:
	try:
		page.goto(home_url, wait_until="domcontentloaded", timeout=_NAV_TIMEOUT_MS)
	except Exception as e:
		print(f"[zhipin-search] {stage}：首页导航未在预期时间完成（{e}），继续尝试提取凭证", file=sys.stderr)
	try:
		page.wait_for_load_state("networkidle", timeout=_NETWORKIDLE_GRACE_MS)
	except Exception as e:
		print(f"[zhipin-search] {stage}：首页未进入 networkidle（{e}），继续提取凭证", file=sys.stderr)


def probe_cdp(cdp_url: str | None = None) -> str | None:
	import httpx

	base = cdp_url or _DEFAULT_CDP_URL
	try:
		resp = httpx.get(f"{base}/json/version", timeout=_CDP_PROBE_TIMEOUT)
		return cast("str | None", resp.json().get("webSocketDebuggerUrl"))
	except (httpx.HTTPError, ValueError, KeyError):
		return None


def login_via_cdp(*, cdp_url: str | None = None, timeout: int = 120) -> dict[str, Any]:
	from patchright.sync_api import sync_playwright

	ws_url = probe_cdp(cdp_url)
	if not ws_url:
		raise ConnectionError("CDP 不可用，请用带 --remote-debugging-port=9222 的 Chrome 启动后重试")

	print("[zhipin-search] 正在连接 CDP Chrome 并打开登录页…", file=sys.stderr)
	pw = sync_playwright().start()
	browser = pw.chromium.connect_over_cdp(ws_url)
	ctx = browser.contexts[0] if browser.contexts else browser.new_context()
	page = ctx.new_page()

	try:
		try:
			page.goto(LOGIN_PAGE_URL, wait_until="commit", timeout=_NAV_TIMEOUT_MS)
		except Exception:
			pass

		print(f"[zhipin-search] 请在 Chrome 中完成登录，等待中…（超时 {timeout}s）", file=sys.stderr)
		for i in range(timeout):
			time.sleep(1)
			cookies = ctx.cookies()
			success = [c for c in cookies if c["name"] == "wt2" and "zhipin" in c.get("domain", "")]
			if success:
				print("[zhipin-search] 检测到登录成功", file=sys.stderr)
				break
			if i > 0 and i % 15 == 0:
				print(f"[zhipin-search] 等待中… {i}s", file=sys.stderr)
		else:
			raise TimeoutError(f"CDP 登录超时（{timeout}s）")

		try:
			page.goto(HOME_URL, wait_until="domcontentloaded", timeout=_NAV_TIMEOUT_MS)
		except Exception:
			pass
		all_cookies = {c["name"]: c["value"] for c in ctx.cookies() if "zhipin" in c.get("domain", "")}
		ua = page.evaluate("navigator.userAgent")
		stoken = str(all_cookies.get("__zp_stoken__", "") or _extract_stoken(page))
		return {"cookies": all_cookies, "stoken": stoken, "user_agent": ua}
	finally:
		try:
			page.close()
		finally:
			pw.stop()


def login_via_browser(*, timeout: int = 120) -> dict[str, Any]:
	from patchright.sync_api import sync_playwright

	with sync_playwright() as p:
		browser = p.chromium.launch(headless=False)
		context = browser.new_context(
			viewport={"width": 1280, "height": 800},
			locale="zh-CN",
			timezone_id="Asia/Shanghai",
		)
		page = context.new_page()
		page.goto(LOGIN_PAGE_URL, wait_until="domcontentloaded")
		print("[zhipin-search] 已打开 BOSS 直聘登录页。", file=sys.stderr)
		print(f"[zhipin-search] 请扫码或手机号登录（超时 {timeout} 秒）…", file=sys.stderr)

		login_detected = False

		def _on_response(response: Any) -> None:
			nonlocal login_detected
			url = response.url
			if (
				url.startswith("https://www.zhipin.com/wapi/zppassport/qrcode/loginConfirm")
				or url.startswith("https://www.zhipin.com/wapi/zppassport/qrcode/dispatcher")
				or url.startswith("https://www.zhipin.com/wapi/zppassport/login/phoneV2")
			):
				login_detected = True

		page.on("response", _on_response)
		deadline = time.time() + timeout
		while time.time() < deadline and not login_detected:
			try:
				cookies_list = context.cookies()
				if any(c["name"] == "wt2" and "zhipin" in c.get("domain", "") for c in cookies_list):
					login_detected = True
					break
			except Exception:
				pass
			time.sleep(1)

		if not login_detected:
			browser.close()
			raise TimeoutError(f"登录超时（{timeout} 秒）")

		print("[zhipin-search] 检测到登录成功，正在提取凭证…", file=sys.stderr)
		time.sleep(_POST_LOGIN_WAIT)
		_warm_home_for_runtime(page, HOME_URL, stage="登录后回到首页")

		cookies_list = context.cookies()
		cookies = {c["name"]: c["value"] for c in cookies_list if "zhipin" in c.get("domain", "")}
		user_agent = page.evaluate("navigator.userAgent")
		stoken = _extract_stoken(page)
		browser.close()

	return {"cookies": cookies, "stoken": stoken, "user_agent": user_agent}


def _extract_stoken(page: Any) -> str:
	try:
		stoken = page.evaluate("""
			() => {
				const match = document.cookie.match(/__zp_stoken__=([^;]+)/);
				return match ? match[1] : '';
			}
		""")
		if not stoken:
			stoken = page.evaluate("() => window.__zp_stoken__ || ''")
		return cast("str", stoken)
	except Exception:
		return ""
