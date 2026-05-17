"""Token 校验工具 - 检查 BOSS 直聘登录凭证是否有效"""
import json
import os
import sys
from pathlib import Path

from patchright.sync_api import sync_playwright


BASE_URL = "https://www.zhipin.com"
SEARCH_URL = f"{BASE_URL}/wapi/zpgeek/search/joblist.json"


def validate_token(token_path: str | os.PathLike, silent: bool = False) -> bool:
    """
    校验 token.json 是否仍然有效。

    返回 True = 有效，False = 已过期/需重新登录。

    验证方式：
    1. 打开 Chrome（可见模式，因为 headless 易被风控）
    2. 注入 token 中的 cookies
    3. 发送一条搜索 API 请求
    4. 检查返回 code
       - code=0 → 有效
       - code=37/36 → 失效（风控/登录过期）
       - 其他 → 失效
    """
    token_path = Path(token_path)
    if not token_path.exists():
        if not silent:
            print("❌ token.json 不存在，请先登录", file=sys.stderr)
        return False

    with open(token_path, "r", encoding="utf-8") as f:
        token = json.load(f)

    cookies = token.get("cookies", {})
    ua = token.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
    stoken = str(token.get("stoken", "") or cookies.get("__zp_stoken__", ""))

    if not cookies:
        if not silent:
            print("❌ token.json 中缺少 cookies，请重新登录", file=sys.stderr)
        return False

    if not silent:
        print("🔍 校验登录凭证...", file=sys.stderr, end=" ", flush=True)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                channel="chrome",
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            )
            context = browser.new_context(
                user_agent=ua, locale="zh-CN",
                viewport={"width": 1280, "height": 800}
            )
            page = context.new_page()

            # 先访问首页建立 session
            try:
                page.goto(BASE_URL, wait_until="domcontentloaded", timeout=15000)
            except Exception:
                pass

            # 注入 cookies
            pw_cookies = [
                {"name": n, "value": v, "domain": ".zhipin.com", "path": "/"}
                for n, v in cookies.items()
            ]
            if pw_cookies:
                context.add_cookies(pw_cookies)

            # 发送测试请求
            params = {"query": "用户研究", "page": 1, "city": "101210100", "__zp_stoken__": stoken}
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

            code = result.get("code", -1)
            browser.close()

            if code == 0:
                if not silent:
                    print("✅ 有效（code=0）", file=sys.stderr)
                return True
            elif code in (37, 36):
                if not silent:
                    print(f"❌ 已过期（code={code}，需要重新登录）", file=sys.stderr)
                return False
            else:
                if not silent:
                    print(f"⚠️  异常（code={code}）", file=sys.stderr)
                return False

    except Exception as e:
        if not silent:
            print(f"❌ 校验失败: {e}", file=sys.stderr)
        return False
