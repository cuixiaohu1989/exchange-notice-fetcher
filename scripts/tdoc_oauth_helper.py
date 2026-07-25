#!/usr/bin/env python3
"""
腾讯文档 OAuth 2.0 授权辅助脚本（一次性运行）

流程:
    1. 构造授权 URL，用户在浏览器中打开并扫码授权
    2. 授权后浏览器重定向到回调地址，URL 中包含 code 参数
    3. 用户复制 code，粘贴到本脚本
    4. 脚本用 code 换取 access_token / refresh_token / open_id
    5. 打印结果，用户将其配置为 GitHub Secrets

用法:
    python scripts/tdoc_oauth_helper.py

前置条件:
    - 已在 https://docs.qq.com/open/developers/ 注册开发者并创建应用
    - 已获取 Client ID 和 Client Secret
    - 已在应用设置中配置回调地址（redirect_uri）

注意:
    redirect_uri 必须是 HTTPS 且已在开发者平台白名单中。
    如果没有自己的域名，可以用 https://docs.qq.com 作为回调地址——
    授权后浏览器会跳转到 docs.qq.com?code=XXXX&state=XXXX，
    从地址栏复制 code 即可。
"""
import argparse
import json
import urllib.parse
import urllib.request


# ── 腾讯文档 OAuth 端点 ──────────────────────────────────────────
AUTHORIZE_URL = "https://docs.qq.com/oauth/v2/authorize"
TOKEN_URL = "https://docs.qq.com/oauth/v2/token"


def build_authorize_url(client_id: str, redirect_uri: str, state: str = "xyz") -> str:
    """构造授权 URL"""
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "new_login": "1",
        "response_type": "code",
        "scope": "all",
        "state": state,
    }
    return f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


def exchange_token(client_id: str, client_secret: str, redirect_uri: str, code: str) -> dict:
    """用授权码换取 access_token + refresh_token"""
    params = {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
        "code": code,
    }
    url = f"{TOKEN_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    parser = argparse.ArgumentParser(description="腾讯文档 OAuth 授权辅助")
    parser.add_argument("--client-id", required=True, help="第三方应用 Client ID")
    parser.add_argument("--client-secret", required=True, help="第三方应用 Client Secret")
    parser.add_argument(
        "--redirect-uri",
        default="https://docs.qq.com",
        help="回调地址（需与开发者平台配置一致，默认 https://docs.qq.com）",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  腾讯文档 OAuth 2.0 授权辅助")
    print("=" * 60)

    # Step 1: 构造授权 URL
    state = "tdoc_auth_2026"
    auth_url = build_authorize_url(args.client_id, args.redirect_uri, state)

    print("\n[Step 1] 请在浏览器中打开以下链接，扫码授权:\n")
    print(auth_url)
    print()

    print("授权后，浏览器会重定向到回调地址。")
    print("请从浏览器地址栏中复制 'code' 参数的值。")
    print(f"URL 类似: {args.redirect_uri}?code=XXXXXX&state={state}")
    print()

    # Step 2: 获取用户输入的 code
    code = input("[Step 2] 请粘贴 code 值: ").strip()
    if not code:
        print("错误: code 不能为空")
        return

    # Step 3: 换取 token
    print("\n[Step 3] 正在换取 Token...")
    try:
        result = exchange_token(
            args.client_id, args.client_secret, args.redirect_uri, code
        )
    except Exception as e:
        print(f"错误: {e}")
        return

    access_token = result.get("access_token", "")
    refresh_token = result.get("refresh_token", "")
    open_id = result.get("user_id", "")
    expires_in = result.get("expires_in", 0)

    if not access_token:
        print(f"错误: 未获取到 access_token，响应: {json.dumps(result, ensure_ascii=False)}")
        return

    print("\n" + "=" * 60)
    print("  授权成功!")
    print("=" * 60)
    print()
    print("请将以下值配置为 GitHub Secrets:")
    print()
    print(f"  TDOC_CLIENT_ID     = {args.client_id}")
    print(f"  TDOC_CLIENT_SECRET = {args.client_secret}")
    print(f"  TDOC_REFRESH_TOKEN = {refresh_token}")
    print(f"  TDOC_OPEN_ID       = {open_id}")
    print()
    print(f"(Access Token 有效期: {expires_in // 86400} 天)")
    print(f"(Refresh Token 有效期: 1 年)")
    print()
    print("GitHub 仓库 → Settings → Secrets and variables → Actions")
    print("→ New repository secret → 逐个添加以上 4 个 Secret")
    print()
    print("注意: Refresh Token 有效期 1 年，到期后需重新运行本脚本获取。")


if __name__ == "__main__":
    main()
