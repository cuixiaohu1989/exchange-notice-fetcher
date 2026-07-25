"""上期所 (SHFE) 爬虫 - 使用 Playwright + stealth（JS渲染 + WAF人机识别）"""
from .base import PlaywrightFetcher, Notice


class SHFEFetcher(PlaywrightFetcher):
    """上期所通知爬虫

    上期所官网有WAF人机识别检测，需要stealth绕过。
    通知列表结构: div.table_item_info > .info_item_title a(标题+链接) + .info_item_date(日期)
    """

    def _wait_for_content(self, page):
        """等待通知列表加载完成（WAF验证后）"""
        # 等待通知列表容器出现
        page.wait_for_selector("div.table_item_info", timeout=30000)

    def _parse_page(self, page) -> list:
        notices = []
        base_domain = self.config["base_domain"]

        items = page.query_selector_all("div.table_item_info")
        for item in items:
            title_el = item.query_selector(".info_item_title a")
            date_el = item.query_selector(".info_item_date")

            if title_el and date_el:
                title = self._safe_text(title_el)
                date_str = self._safe_text(date_el)
                link = self._safe_attr(title_el, "href")

                if not title or not date_str:
                    continue

                link = self._build_url(link, base_domain)

                try:
                    parsed_date = self._parse_date(date_str)
                    notices.append(Notice(
                        exchange="SHFE",
                        exchange_name="上期所",
                        title=title,
                        notice_date=parsed_date.isoformat(),
                        link=link,
                    ))
                except ValueError:
                    continue

        return notices
