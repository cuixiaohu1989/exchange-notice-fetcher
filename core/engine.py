"""
核心引擎：编排所有交易所爬虫，顺序执行，输出JSON结果。

关键设计：
- 顺序爬取（非并发）：每个交易所间隔3-6秒随机延迟，降低WAF检测风险
- 单点失败隔离：每个爬虫独立try-catch，失败返回None不影响其他
- 重试机制：最多3次，间隔递增（5s/10s/15s）
- 输出JSON：结构化结果，供WorkBuddy自动化读取
"""
import time
import random
from .date_utils import get_fetch_date_range, SkipFetchException, beijing_today
from fetchers.base import PlaywrightFetcher


class FetchEngine:
    """核心引擎：编排爬虫 + 输出结果"""

    def __init__(self, fetchers, logger, headless=True, max_retries=3):
        self.fetchers = fetchers
        self.logger = logger
        self.headless = headless
        self.max_retries = max_retries

    def run(self) -> dict:
        """
        主流程入口。

        Returns:
            JSON可序列化的结果字典:
            {
                "status": "success" | "skipped" | "partial",
                "date": "2026-07-24",
                "date_range": {"start": "2026-07-23", "end": "2026-07-23"},
                "total": 15,
                "failed_exchanges": [],
                "notices": [...]
            }
        """
        self.logger.info("=" * 60)
        self.logger.info("交易所通知获取任务开始")

        # 1. 日期判断
        try:
            start_date, end_date = get_fetch_date_range()
            self.logger.info(f"获取日期范围: {start_date} ~ {end_date}")
        except SkipFetchException:
            self.logger.info("今天是周末，跳过任务")
            return {
                "status": "skipped",
                "reason": "weekend",
                "date": beijing_today().isoformat(),
                "date_range": None,
                "total": 0,
                "failed_exchanges": [],
                "notices": [],
            }

        # 2. 检查是否需要Playwright（有动态爬虫时才需要）
        has_playwright_fetchers = any(
            isinstance(f, PlaywrightFetcher) for f in self.fetchers
        )

        if has_playwright_fetchers:
            from .browser_manager import BrowserManager
            browser_ctx = BrowserManager(self.logger, headless=self.headless)
        else:
            browser_ctx = None  # 无需浏览器（如仅爬取CFFEX）

        with (browser_ctx if browser_ctx else _DummyCtx()) as browser_mgr:
            # 将BrowserManager注入到所有Playwright爬虫
            for fetcher in self.fetchers:
                if isinstance(fetcher, PlaywrightFetcher):
                    fetcher.set_browser_manager(browser_mgr)

            # 3. 顺序爬取（每个交易所之间随机延迟）
            all_notices = []
            failed_exchanges = []

            for i, fetcher in enumerate(self.fetchers):
                notices = self._safe_fetch(fetcher, start_date, end_date)

                if notices is not None:
                    all_notices.extend(notices)
                    self.logger.info(
                        f"[{fetcher.name}] 完成: 获取 {len(notices)} 条通知"
                    )
                else:
                    failed_exchanges.append(fetcher.name)

                # 交易所之间随机延迟（最后一个不用延迟）
                if i < len(self.fetchers) - 1:
                    delay = random.uniform(3, 6)
                    self.logger.info(f"等待 {delay:.1f}s 后爬取下一个交易所...")
                    time.sleep(delay)

        # 4. 排序：按交易所名称 + 日期倒序
        all_notices.sort(
            key=lambda n: (n.exchange_name, n.notice_date),
            reverse=True,
        )

        # 5. 构造结果
        result = {
            "status": "success" if not failed_exchanges else "partial",
            "date": beijing_today().isoformat(),
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "total": len(all_notices),
            "failed_exchanges": failed_exchanges,
            "notices": [n.to_dict() for n in all_notices],
        }

        self.logger.info("=" * 60)
        self.logger.info(
            f"任务完成: 共获取 {len(all_notices)} 条通知"
            + (f"，失败交易所: {', '.join(failed_exchanges)}" if failed_exchanges else "")
        )
        self.logger.info("=" * 60)

        return result

    def _safe_fetch(self, fetcher, start_date, end_date):
        """
        带重试的安全爬取。

        Returns:
            List[Notice] 成功时返回通知列表
            None 彻底失败时返回None
        """
        for attempt in range(self.max_retries):
            try:
                return fetcher.fetch(start_date, end_date)
            except Exception as e:
                self.logger.warning(
                    f"[{fetcher.name}] 第 {attempt + 1}/{self.max_retries} 次尝试失败: {e}"
                )
                if attempt < self.max_retries - 1:
                    delay = 5 * (attempt + 1)
                    self.logger.info(f"等待 {delay}s 后重试...")
                    time.sleep(delay)

        self.logger.error(f"[{fetcher.name}] 全部 {self.max_retries} 次重试失败")
        return None


class _DummyCtx:
    """空上下文管理器（无需Playwright时使用）"""
    def __enter__(self):
        return None
    def __exit__(self, *args):
        pass
