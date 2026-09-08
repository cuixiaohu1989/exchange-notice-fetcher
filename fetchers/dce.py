"""大商所 (DCE) 爬虫 - Playwright 模式

瑞数 WAF 策略与 CZCE 相同：
- 用 Playwright 真实浏览器（headless=True）
- 不注入 stealth 脚本
- 导航用 wait_until="commit" + wait_for_load_state("networkidle")

DCE 网站已改版，新版通知页面结构：
  div.text-list-wrap > a.ellipsis
    ├─ 文本内容 (标题)
    └─ span.date (日期, 格式 "2026-07-23")
"""
import time
from typing import List

from .base import PlaywrightFetcher, Notice


class DCEFetcher(PlaywrightFetcher):
    """大商所通知爬虫（Playwright + 瑞数 WAF 绕过）"""

    def _navigate(self, page) -> bool:
        """瑞数 WAF 绕过导航（动态等待内容出现，兼容 CI 上 Chromium 较慢的 WAF 首次执行）"""
        try:
            self.logger.info(f"[{self.name}] 导航到 {self.config['url']}")
            page.goto(
                self.config["url"],
                wait_until="commit",
                timeout=30000,
            )

            # 瑞数 WAF 首次执行可能较慢，循环等待列表出现，最多 30 秒
            for i in range(15):
                try:
                    page.wait_for_selector("div.text-list-wrap a.ellipsis", timeout=2000)
                    self.logger.info(f"[{self.name}] 列表已加载（ waited {i * 2}s ）")
                    return True
                except Exception:
                    pass
                time.sleep(2)

            # 兜底：等 networkidle
            try:
                page.wait_for_load_state("networkidle", timeout=30000)
            except Exception:
                self.logger.warning(f"[{self.name}] networkidle 等待超时")

            time.sleep(2)
            return True

        except Exception as e:
            self.logger.error(f"[{self.name}] 导航失败: {e}")
            return False

    def _wait_for_content(self, page):
        """等待通知列表加载"""
        try:
            page.wait_for_selector(
                "div.text-list-wrap a.ellipsis", timeout=10000
            )
        except Exception:
            self.logger.warning(f"[{self.name}] 等待通知列表超时")

    def _parse_items(self, page) -> List[Notice]:
        """解析 DCE 通知列表（新版页面结构）"""
        items = page.query_selector_all("div.text-list-wrap > a.ellipsis")
        self.logger.info(f"[{self.name}] 找到 {len(items)} 个通知链接")

        notices = []
        for item in items:
            try:
                # 链接
                link = item.get_attribute("href") or ""

                # 日期在 span.date 中
                date_el = item.query_selector("span.date")
                date_str = date_el.inner_text().strip() if date_el else ""

                # 标题：获取 a 标签的所有文本，去掉日期部分
                full_text = item.inner_text().strip()
                # 去掉末尾的日期
                title = full_text.replace(date_str, "").strip()
                # 去掉可能的换行和空白
                title = " ".join(title.split())

                if not title or not date_str:
                    continue

                link = self._build_url(link, self.config.get("base_domain", ""))

                try:
                    parsed_date = self._parse_date(date_str)
                    notices.append(Notice(
                        exchange="DCE",
                        exchange_name="大商所",
                        title=title,
                        notice_date=parsed_date.isoformat(),
                        link=link,
                    ))
                except ValueError:
                    continue

            except Exception:
                continue

        self.logger.info(f"[{self.name}] 解析到 {len(notices)} 条通知")
        return notices

    def _parse_page(self, page) -> List[Notice]:
        """解析页面；若未解析到内容，刷新重试一次（应对 CI 上 WAF 首次加载偶发空白）"""
        notices = self._parse_items(page)
        if not notices:
            self.logger.warning(f"[{self.name}] 首次解析为空，尝试刷新重试")
            try:
                page.reload(wait_until="networkidle", timeout=30000)
                time.sleep(3)
                notices = self._parse_items(page)
            except Exception as e:
                self.logger.warning(f"[{self.name}] 刷新重试失败: {e}")
        return notices
