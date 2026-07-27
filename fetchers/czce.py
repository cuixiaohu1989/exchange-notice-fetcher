"""郑商所 (CZCE) 爬虫 - Playwright + API 拦截

瑞数 WAF 策略：
- 必须用 Playwright 真实浏览器（headless=True 即可）
- 不能注入 stealth 脚本（瑞数 WAF 检测 navigator 篡改并拦截）
- 导航用 wait_until="commit" + wait_for_load_state("networkidle") 等 WAF JS 自动通过

通知数据获取：
- 页面加载后调用 selectNoticeCN API 返回 JSON
- 拦截 API 响应即可获得结构化通知数据（title, pubtime, pathurl）
- 若 API 拦截失败，降级为解析页面 DOM
"""
import time
from datetime import date, datetime
from typing import List

from .base import PlaywrightFetcher, Notice


class CZCEFetcher(PlaywrightFetcher):
    """郑商所通知爬虫（Playwright + API 拦截 + DOM 降级）"""

    # API 响应拦截结果
    _api_data = None

    def _navigate(self, page) -> bool:
        """瑞数 WAF 绕过导航：commit + networkidle 等待，支持重试"""
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
            # 云环境网络较慢，给予 120 秒超时
            if self._wait_for_api(page, timeout=120):
                return True

            # 首次未拦截到 API，刷新页面再试一次
            self.logger.warning(f"[{self.name}] 首次未拦截到 API，尝试刷新页面")
            self._api_data = None
            page.reload(wait_until="commit", timeout=30000)
            if self._wait_for_api(page, timeout=90):
                return True

            self.logger.warning(f"[{self.name}] 刷新后仍未拦截到 API，将尝试 DOM 解析")
            return True

        except Exception as e:
            self.logger.error(f"[{self.name}] 导航失败: {e}")
            return False

    def _wait_for_api(self, page, timeout: int = 90) -> bool:
        """等待 API 响应到达，超时返回 False"""
        try:
            page.wait_for_load_state("networkidle", timeout=timeout * 1000)
        except Exception:
            self.logger.warning(f"[{self.name}] networkidle 等待超时 ({timeout}s)")

        # networkidle 后仍可能还有 API 在飞，再轮询等待
        for _ in range(timeout // 3):
            if self._api_data:
                return True
            time.sleep(3)
        return False

    def _wait_for_content(self, page):
        """等待内容加载（API 响应已通过拦截获取）"""
        if not self._api_data:
            # 再等一下，可能 API 响应还在路上
            time.sleep(3)

    def _parse_page(self, page) -> List[Notice]:
        """从拦截的 API JSON 数据解析通知；API 失败时降级解析 DOM"""
        # API 响应可能在 _wait_for_api 刚结束时到达，再稍等片刻
        if not self._api_data:
            for _ in range(5):
                if self._api_data:
                    break
                time.sleep(3)

        if self._api_data:
            return self._parse_api_data()

        self.logger.warning(f"[{self.name}] 未拦截到 API 数据，尝试 DOM 解析")
        return self._parse_dom(page)

    def _parse_api_data(self) -> List[Notice]:
        """从 API JSON 解析通知"""
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
                try:
                    parsed_date = date.fromisoformat(pubtime[:10])
                except (ValueError, TypeError):
                    continue

            notices.append(Notice(
                exchange="CZCE",
                exchange_name="郑商所",
                title=title,
                notice_date=parsed_date.isoformat(),
                link=self._build_url(link, "http://www.czce.com.cn"),
            ))

        self.logger.info(f"[{self.name}] API 解析到 {len(notices)} 条通知")
        return notices

    def _parse_dom(self, page) -> List[Notice]:
        """从页面 DOM 解析通知列表（API 失败时的降级方案）"""
        notices = []
        try:
            # 郑商所通知列表常见选择器
            selectors = [
                ".news-list li",
                ".list_main li",
                ".list li",
                ".ggtz-list li",
                ".notice-list li",
                "ul.list li",
                "table tr",
            ]
            items = []
            for selector in selectors:
                items = page.query_selector_all(selector)
                if items:
                    self.logger.info(f"[{self.name}] DOM 选择器命中: {selector} ({len(items)} 项)")
                    break

            for item in items:
                link_el = item.query_selector("a")
                if not link_el:
                    continue
                title = self._safe_text(link_el)
                if not title:
                    continue

                href = self._safe_attr(link_el, "href") or ""
                # 尝试从邻居元素或文本中提取日期
                date_text = ""
                # 常见：span.date / span.time / .date
                for ds in [".date", ".time", ".pubtime", ".rq"]:
                    de = item.query_selector(ds)
                    if de:
                        date_text = self._safe_text(de)
                        break
                if not date_text:
                    # 从 title 或 href 中尝试提取日期
                    date_text = self._extract_date_from_text(title + " " + href)

                if not date_text:
                    continue

                try:
                    parsed_date = self._parse_date(date_text)
                except ValueError:
                    continue

                notices.append(Notice(
                    exchange="CZCE",
                    exchange_name="郑商所",
                    title=title,
                    notice_date=parsed_date.isoformat(),
                    link=self._build_url(href, "http://www.czce.com.cn"),
                ))
        except Exception as e:
            self.logger.error(f"[{self.name}] DOM 解析失败: {e}")

        self.logger.info(f"[{self.name}] DOM 解析到 {len(notices)} 条通知")
        return notices

    def _extract_date_from_text(self, text: str) -> str:
        """从文本中提取日期（如 2026-07-27 或 2026/07/27）"""
        import re
        match = re.search(r"20\d{2}[-/][01]\d[-/][0123]\d", text)
        return match.group(0) if match else ""
