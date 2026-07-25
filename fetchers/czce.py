"""郑商所 (CZCE) 爬虫 - Playwright + API 拦截

瑞数 WAF 策略：
- 必须用 Playwright 真实浏览器（headless=True 即可）
- 不能注入 stealth 脚本（瑞数 WAF 检测 navigator 篡改并拦截）
- 导航用 wait_until="commit" + wait_for_load_state("networkidle") 等 WAF JS 自动通过

通知数据获取：
- 页面通过 iframe 加载 app.czce.com.cn/cmsapp/notice
- iframe 内部调用 selectNoticeCN API 返回 JSON
- 拦截 API 响应即可获得结构化通知数据（title, pubtime, pathurl）
"""
import time
from datetime import date, datetime
from typing import List

from .base import PlaywrightFetcher, Notice


class CZCEFetcher(PlaywrightFetcher):
    """郑商所通知爬虫（Playwright + API 拦截）"""

    # API 响应拦截结果
    _api_data = None

    def _navigate(self, page) -> bool:
        """瑞数 WAF 绕过导航：commit + networkidle 等待"""
        try:
            self._api_data = None

            # 设置 API 响应拦截
            def on_response(response):
                if "selectNoticeCN" in response.url:
                    try:
                        self._api_data = response.json()
                        self.logger.info(
                            f"[{self.name}] 拦截到 selectNoticeCN API 响应"
                        )
                    except Exception:
                        pass

            page.on("response", on_response)

            # 导航：wait_until="commit" 只等初始响应头
            # 瑞数 WAF 会返回 412 + JS 挑战，浏览器执行 JS 后自动重载
            self.logger.info(f"[{self.name}] 导航到 {self.config['url']}")
            page.goto(
                self.config["url"],
                wait_until="commit",
                timeout=30000,
            )

            # 等待 WAF JS 执行 + 页面重载 + 内容加载完成
            # CZCE 页面较重（含 iframe + API 调用），需要 45 秒
            try:
                page.wait_for_load_state("networkidle", timeout=45000)
            except Exception:
                self.logger.warning(f"[{self.name}] networkidle 等待超时")

            # 额外等待确保 API 响应到达
            time.sleep(3)

            return True

        except Exception as e:
            self.logger.error(f"[{self.name}] 导航失败: {e}")
            return False

    def _wait_for_content(self, page):
        """等待内容加载（API 响应已通过拦截获取）"""
        if not self._api_data:
            # 再等一下，可能 API 响应还在路上
            time.sleep(3)

    def _parse_page(self, page) -> List[Notice]:
        """从拦截的 API JSON 数据解析通知"""
        if not self._api_data:
            self.logger.warning(f"[{self.name}] 未拦截到 API 数据")
            return []

        try:
            records = (
                self._api_data.get("result", {}).get("records", [])
            )
        except (AttributeError, TypeError):
            self.logger.error(f"[{self.name}] API 数据格式异常")
            return []

        notices = []
        for record in records:
            title = record.get("topic", "").strip()
            pubtime = record.get("pubtime", "")
            link = record.get("pathurl", "")

            if not title or not pubtime:
                continue

            # 解析日期 (格式: "2026-07-24T06:48:07.000+00:00")
            try:
                parsed_date = datetime.fromisoformat(pubtime).date()
            except (ValueError, TypeError):
                # 尝试截取日期部分
                try:
                    parsed_date = date.fromisoformat(pubtime[:10])
                except (ValueError, TypeError):
                    continue

            notices.append(Notice(
                exchange="CZCE",
                exchange_name="郑商所",
                title=title,
                notice_date=parsed_date.isoformat(),
                link=link,
            ))

        self.logger.info(f"[{self.name}] 解析到 {len(notices)} 条通知")
        return notices
