"""广期所 (GFEX) 爬虫 - 使用 requests + BeautifulSoup（服务端渲染页面）

广期所官网 notice/index.shtml 是JS动态渲染的，但存在一个服务端渲染的备用页面：
  /gfex/tzts/list_yw_5.shtml

该页面返回完整的HTML（含通知列表），无需Playwright，用requests直接抓取即可。

HTML结构:
  div.pageList.newsList.news-list-yw > ul > li
    └─ div.clearfix
       ├─ div.item_time > span.dd (日) + span.yyMM (年.月, 如 "2026.04")
       └─ div.item_main > div.item_main_title > a (标题+链接) + p (摘要)
"""
import re
import requests
from bs4 import BeautifulSoup
from .base import BaseFetcher, Notice


class GFEXFetcher(BaseFetcher):
    """广期所通知爬虫（requests方案，无需Playwright）

    使用服务端渲染页面 list_yw_5.shtml，避免JS渲染和WAF问题。
    """

    # 通知列表页URL（服务端渲染）
    LIST_URL = "http://www.gfex.com.cn/gfex/tzts/list_yw_5.shtml"

    # HTTP请求头
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    def fetch(self, start_date, end_date):
        """抓取广期所通知"""
        self.logger.info(f"[{self.name}] 开始抓取 (requests模式)")

        try:
            resp = requests.get(
                self.LIST_URL,
                headers=self.HEADERS,
                timeout=15,
                verify=False,  # GFEX SSL证书有问题
            )
            resp.encoding = "utf-8"

            if resp.status_code != 200:
                self.logger.error(f"[{self.name}] HTTP {resp.status_code}")
                return []

            soup = BeautifulSoup(resp.text, "html.parser")

            # 查找通知项: 链接格式 /gfex/tzts/YYYYMM/<hash>.shtml
            notice_links = soup.find_all(
                "a", href=re.compile(r"/gfex/tzts/\d{6}/[a-f0-9]{32}")
            )

            # 去重（同一通知可能有2个链接：标题链接和图片链接）
            seen_hrefs = set()
            notices = []

            for a_tag in notice_links:
                href = a_tag.get("href", "")
                if href in seen_hrefs:
                    continue
                seen_hrefs.add(href)

                # 找到所在的 li 元素
                li = a_tag
                while li and li.name != "li":
                    li = li.parent
                if not li:
                    continue

                # 提取标题
                title = a_tag.get_text(strip=True)
                if not title:
                    title = a_tag.get("title", "")
                if not title:
                    continue

                # 提取日期: span.dd (日) + span.yyMM (年.月)
                dd_el = li.select_one("span.dd")
                yy_el = li.select_one("span.yyMM")
                if not dd_el or not yy_el:
                    continue

                day_str = dd_el.get_text(strip=True)
                yymm_str = yy_el.get_text(strip=True)  # 格式: "2026.04"

                # 组合成日期: "2026.04" + "01" → "2026-04-01"
                date_str = f"{yymm_str.replace('.', '-')}-{day_str}"

                try:
                    parsed_date = self._parse_date(date_str)
                except ValueError:
                    self.logger.debug(
                        f"[{self.name}] 日期解析失败: {date_str}"
                    )
                    continue

                # 补全链接URL
                link = self._build_url(href, "http://www.gfex.com.cn")

                notices.append(Notice(
                    exchange="GFEX",
                    exchange_name="广期所",
                    title=title,
                    notice_date=parsed_date.isoformat(),
                    link=link,
                ))

            self.logger.info(
                f"[{self.name}] 解析到 {len(notices)} 条通知"
            )
            return self._filter_by_date(notices, start_date, end_date)

        except requests.RequestException as e:
            self.logger.error(f"[{self.name}] 请求失败: {e}")
            return []
        except Exception as e:
            self.logger.error(f"[{self.name}] 解析失败: {e}")
            return []
