"""中金所 (CFFEX) 爬虫 - 使用 requests + BeautifulSoup（静态HTML，无WAF）"""
import requests
from bs4 import BeautifulSoup
from .base import BaseFetcher, Notice


class CFFEXFetcher(BaseFetcher):
    """中金所通知爬虫

    中金所是6家交易所中唯一使用静态HTML页面的，
    无WAF反爬机制，可直接用requests获取。
    """

    def fetch(self, start_date, end_date):
        self.logger.info(f"[{self.name}] 开始爬取（requests+BS4）")
        try:
            resp = requests.get(
                self.config["url"],
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/125.0.0.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                },
                timeout=30,
            )
            resp.encoding = resp.apparent_encoding

            soup = BeautifulSoup(resp.text, "html.parser")

            notices = []
            list_selector = self.config["selectors"]["list"]
            title_selector = self.config["selectors"]["title"]
            date_selector = self.config["selectors"]["date"]

            for item in soup.select(list_selector):
                title_el = item.select_one(title_selector)
                date_el = item.select_one(date_selector)

                if title_el and date_el:
                    title = title_el.get_text(strip=True)
                    date_str = date_el.get_text(strip=True)

                    if not title or not date_str:
                        continue

                    link = title_el.get("href", "")
                    link = self._build_url(link, self.config["base_domain"])

                    try:
                        parsed_date = self._parse_date(date_str)
                        notices.append(Notice(
                            exchange="CFFEX",
                            exchange_name="中金所",
                            title=title,
                            notice_date=parsed_date.isoformat(),
                            link=link,
                        ))
                    except ValueError:
                        continue

            self.logger.info(f"[{self.name}] 解析到 {len(notices)} 条通知")
            return self._filter_by_date(notices, start_date, end_date)

        except Exception as e:
            self.logger.error(f"[{self.name}] 爬取失败: {e}", exc_info=True)
            return []
