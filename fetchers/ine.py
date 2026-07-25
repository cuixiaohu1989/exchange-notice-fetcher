"""上期能源 (INE) 爬虫 - 使用 Playwright + stealth（WAF人机识别）

INE与SHFE（上期所）同属上海期货交易所体系，但页面结构不同。
INE官网WAF会先显示"WEB 应用防火墙"页面，约15秒后自动通过，显示真实内容。

HTML结构（WAF通过后）:
  ul.home_news_contant_listUl > li
    ├─ a (标题+链接, href="/publicnotice/notice/YYYYMM/tYYYYMMDD_XXXXXX.html")
    └─ i (日期, 格式 "2026-07-24")
"""
from .base import PlaywrightFetcher, Notice


class INEFetcher(PlaywrightFetcher):
    """上期能源通知爬虫

    INE官网WAF需要约15秒通过JS人机验证。
    WAF通过后，通知列表在首页底部以 ul.home_news_contant_listUl 呈现。
    """

    def _wait_for_content(self, page):
        """等待WAF验证通过 + 通知列表加载

        INE的WAF会在页面加载后显示"WEB 应用防火墙"页面，
        然后约10-15秒后自动重定向到真实内容。
        """
        self.logger.info(f"[{self.name}] 等待WAF验证通过...")

        # 分段等待，每5秒检查一次是否WAF已通过
        for i in range(4):  # 最多等20秒
            page.wait_for_timeout(5000)
            title = page.title()
            # WAF通过后，title不再是"WEB 应用防火墙"或"404"
            if "WEB 应用防火墙" not in title and "404" not in title:
                self.logger.info(
                    f"[{self.name}] WAF已通过 (等待{(i + 1) * 5}s)"
                )
                break
        else:
            self.logger.warning(
                f"[{self.name}] WAF未在20秒内通过，尝试继续解析"
            )

        # 等待通知列表元素出现
        try:
            page.wait_for_selector(
                "ul.home_news_contant_listUl li", timeout=10000
            )
        except Exception:
            self.logger.warning(
                f"[{self.name}] 通知列表未出现，尝试继续解析"
            )

    def _parse_page(self, page) -> list:
        """解析INE通知列表"""
        notices = []
        base_domain = self.config["base_domain"]

        # INE首页底部的通知列表
        items = page.query_selector_all(
            "ul.home_news_contant_listUl > li"
        )

        if not items:
            self.logger.warning(
                f"[{self.name}] 未找到通知列表元素"
            )
            return notices

        for item in items:
            # 标题和链接: <a href="/publicnotice/notice/...">标题</a>
            title_el = item.query_selector("a")
            if not title_el:
                continue

            title = self._safe_text(title_el)
            link = self._safe_attr(title_el, "href")

            if not title or not link:
                continue

            # 过滤导航链接（非通知项）
            if "/publicnotice/notice/" not in link:
                continue

            link = self._build_url(link, base_domain)

            # 日期: <i>2026-07-24</i>
            date_el = item.query_selector("i")
            if not date_el:
                continue

            date_str = self._safe_text(date_el)
            if not date_str:
                continue

            try:
                parsed_date = self._parse_date(date_str)
                notices.append(Notice(
                    exchange="INE",
                    exchange_name="上期能源",
                    title=title,
                    notice_date=parsed_date.isoformat(),
                    link=link,
                ))
            except ValueError:
                self.logger.debug(
                    f"[{self.name}] 日期解析失败: {date_str}"
                )
                continue

        self.logger.info(f"[{self.name}] 解析到 {len(notices)} 条通知")
        return notices
