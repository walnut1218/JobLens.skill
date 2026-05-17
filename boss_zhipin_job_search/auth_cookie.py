"""从本机浏览器 Cookie 库读取 BOSS 直聘登录态（与 boss-agent-cli.auth.cookie_extract 对齐）。"""

from __future__ import annotations

import sys
from typing import Any, Callable

_ZHIPIN_DOMAIN = ".zhipin.com"
_REQUIRED = "wt2"
_STOKEN_COOKIE = "__zp_stoken__"


def extract_cookies(source: str | None = None) -> dict[str, Any] | None:
	"""
	从本地浏览器提取 zhipin.com 域下 Cookie。
	source: 指定浏览器名（如 chrome），None 则按 chrome→firefox→… 依次尝试。
	返回 {"cookies": {...}, "user_agent": "", "stoken": ""} 或 None。
	"""
	try:
		import browser_cookie3
	except ImportError:
		print("未安装 browser-cookie3，请执行: pip install browser-cookie3", file=sys.stderr)
		return None

	loaders: dict[str, Callable[..., Any]] = {
		"chrome": browser_cookie3.chrome,
		"firefox": browser_cookie3.firefox,
		"edge": browser_cookie3.edge,
		"brave": browser_cookie3.brave,
		"opera": browser_cookie3.opera,
		"chromium": browser_cookie3.chromium,
	}

	if source:
		loader = loaders.get(source.lower())
		if loader is None:
			print(f"不支持的浏览器: {source}，支持: {', '.join(loaders.keys())}", file=sys.stderr)
			return None
		return _try_extract(loader)

	for name, loader in loaders.items():
		result = _try_extract(loader)
		if result:
			print(f"[zhipin-search] 从 {name} 提取到 BOSS Cookie", file=sys.stderr)
			return result

	return None


def _try_extract(loader: Callable[..., Any]) -> dict[str, Any] | None:
	try:
		cj = loader(domain_name=_ZHIPIN_DOMAIN)
		fragment = _ZHIPIN_DOMAIN.lstrip(".")
		cookies = {c.name: c.value for c in cj if fragment in (c.domain or "")}
		if not cookies or _REQUIRED not in cookies:
			return None
		stoken = cookies.get(_STOKEN_COOKIE, "")
		return {
			"cookies": cookies,
			"user_agent": "",
			"stoken": stoken,
		}
	except Exception:
		return None
