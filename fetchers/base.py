"""
爬虫适配器基类和数据模型。

设计思路：
- Notice: 统一的通知数据模型，可序列化为JSON
- BaseFetcher: 抽象基类，定义 fetch() 统一接口
- PlaywrightFetcher: 动态页面爬虫基类，封装浏览器交互
- 日期过滤策略：爬取后过滤（各交易所日期格式不统一）
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import date, datetime
from typing import List
import random
import time


@dataclass
class Notice:
    """通知数据模型"""
    exchange: str        # 交易所代码: CZCE/DCE/SHFE/CFFEX/GFEX/INE
    exchange_name: str   # 交易所中文名称
    title: str
    notice_date: str     # ISO格式日期字符串 (如 "2026-07-20")，JSON序列化友好
    link: str

    def to_dict(self) -> dict:
        return asdict(self)


class BaseFetcher(ABC):
    """交易所爬虫适配器基类"""

    def __init__(self, config: dict, logger):
        self.config = config
        self.logger = logger
        self.name = config["code"]

    @abstractmethod
    def fetch(self, start_date: date, end_date: date) -> List[Notice]:
        """
        获取指定日期范围内的通知。

        参数: start_date/end_date 闭区间
        返回: 通知列表（已按日期过滤），失败时返回空列表
        """
        pass

    def _parse_date(self, date_str: str) -> date:
        """统一日期解析，兼容多种格式"""
        date_str = date_str.strip()
        formats = [
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%Y.%m.%d",
            "%Y年%m月%d日",
            "%Y%m%d",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        raise ValueError(f"无法解析日期: {date_str}")

    def _filter_by_date(self, notices: List[Notice], start: date, end: date) -> List[Notice]:
        """按日期范围过滤（爬取后过滤策略）"""
        result = []
        for n in notices:
            try:
                # notice_date 可能是 date 对象或 ISO 字符串
                if isinstance(n.notice_date, date):
                    d = n.notice_date
                else:
                    d = self._parse_date(n.notice_date)
                if start <= d <= end:
                    n.notice_date = d.isoformat()  # 统一转为ISO字符串
                    result.append(n)
            except (ValueError, TypeError):
                continue
        return result

    def _build_url(self, link: str, base_domain: str) -> str:
        """将相对URL补全为绝对URL"""
        if not link:
            return ""
        if link.startswith("http"):
            return link
        if link.startswith("./"):
            return base_domain + link[1:]
        if link.startswith("/"):
            return base_domain + link
        return base_domain + "/" + link


class PlaywrightFetcher(BaseFetcher):
    """基于Playwright的动态页面爬虫基类"""

    def __init__(self, config: dict, logger, browser_manager=None):
        super().__init__(config, logger)
        self.browser_manager = browser_manager
        # 是否使用 stealth 脚本（默认 True）
        # CZCE/DCE 的瑞数 WAF 会检测 stealth 篡改并拦截，需设为 False
        self.use_stealth = config.get("use_stealth", True)

    def set_browser_manager(self, bm):
        """注入BrowserManager实例（由Engine在启动时注入）"""
        self.browser_manager = bm

    def fetch(self, start_date: date, end_date: date) -> List[Notice]:
        """通用Playwright爬取流程"""
        page = None
        try:
            if not self.browser_manager:
                raise RuntimeError("BrowserManager not set")

            page = self.browser_manager.get_page(use_stealth=self.use_stealth)
            self.logger.info(f"[{self.name}] 正在访问 {self.config['url']}")

            # 如果子类定义了 _navigate 方法，使用它（处理WAF等特殊情况）
            # 否则使用默认的 page.goto
            if hasattr(self, "_navigate") and callable(self._navigate):
                success = self._navigate(page)
                if not success:
                    self.logger.error(f"[{self.name}] 导航失败")
                    return []
            else:
                page.goto(
                    self.config["url"],
                    wait_until="networkidle",
                    timeout=60000,
                )

                # 随机延迟（反爬）
                self._random_delay(2, 5)

            # 等待内容加载
            self._wait_for_content(page)

            # 解析页面
            notices = self._parse_page(page)
            self.logger.info(f"[{self.name}] 原始解析到 {len(notices)} 条通知")

            # 按日期过滤
            return self._filter_by_date(notices, start_date, end_date)

        except Exception as e:
            self.logger.error(f"[{self.name}] 爬取失败: {e}", exc_info=True)
            return []
        finally:
            if page:
                try:
                    page.close()
                except Exception:
                    pass

    @abstractmethod
    def _wait_for_content(self, page):
        """等待页面内容加载完成（各交易所不同）"""
        pass

    @abstractmethod
    def _parse_page(self, page) -> List[Notice]:
        """解析页面内容，返回通知列表"""
        pass

    def _random_delay(self, min_s: float = 1.0, max_s: float = 3.0):
        """随机延迟，模拟人类操作"""
        time.sleep(random.uniform(min_s, max_s))

    def _safe_text(self, element) -> str:
        """安全获取元素文本"""
        if element is None:
            return ""
        try:
            return element.inner_text().strip()
        except Exception:
            return ""

    def _safe_attr(self, element, attr: str) -> str:
        """安全获取元素属性"""
        if element is None:
            return ""
        try:
            return element.get_attribute(attr) or ""
        except Exception:
            return ""
