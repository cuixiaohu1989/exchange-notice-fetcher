"""
6家期货交易所爬虫配置与工厂函数。

每家交易所的配置包含：
- code: 交易所代码
- name: 中文名称
- url: 通知页面URL
- engine: 爬取引擎 ("requests" 或 "playwright")
- selectors: CSS选择器配置
- use_stealth: 是否使用stealth反检测
"""

EXCHANGE_CONFIGS = [
    {
        "code": "CFFEX",
        "name": "中金所",
        "engine": "requests",
        "url": "http://www.cffex.com.cn/jystz/",
        "base_domain": "http://www.cffex.com.cn",
        "selectors": {
            "list": "ul.clearFloat li",
            "title": "a.list_a_text",
            "date": "a.time.comparetime",
        },
    },
    {
        "code": "CZCE",
        "name": "郑商所",
        "engine": "playwright",
        "use_stealth": False,  # 瑞数 WAF 检测 stealth 篡改并拦截
        "url": "http://www.czce.com.cn/cn/gyjys/jysdt/ggytz/H077001003001index_1.htm",
        "base_domain": "http://www.czce.com.cn",
        "selectors": {
            "list": "tr",
            "title": "td.xxgktit a",
            "date": "td.xxgktd1",
        },
    },
    {
        "code": "DCE",
        "name": "大商所",
        "engine": "playwright",
        "use_stealth": False,  # 瑞数 WAF 检测 stealth 篡改并拦截
        "url": "http://www.dce.com.cn/dce/channel/list/239.html",
        "base_domain": "http://www.dce.com.cn",
        "selectors": {
            "list": "div.text-list-wrap > a.ellipsis",
            "title": "a",
            "date": "span.date",
        },
    },
    {
        "code": "SHFE",
        "name": "上期所",
        "engine": "playwright",
        "use_stealth": True,
        "url": "https://www.shfe.com.cn/publicnotice/notice/",
        "base_domain": "https://www.shfe.com.cn/publicnotice/notice",
        "selectors": {
            "list": "div.table_item_info",
            "title": ".info_item_title a",
            "date": ".info_item_date",
        },
    },
    {
        "code": "GFEX",
        "name": "广期所",
        "engine": "requests",  # 改为requests：list_yw_5.shtml 是服务端渲染
        "url": "http://www.gfex.com.cn/gfex/tzts/list_yw_5.shtml",
        "base_domain": "http://www.gfex.com.cn",
        "selectors": {
            "list": "div.pageList.newsList li",
            "title": "div.item_main_title a",
            "date_dd": "span.dd",
            "date_yy": "span.yyMM",
        },
    },
    {
        "code": "INE",
        "name": "上期能源",
        "engine": "playwright",
        "use_stealth": True,
        "url": "https://www.ine.cn/notice/",
        "base_domain": "https://www.ine.cn",
        "selectors": {
            "list": "ul.home_news_contant_listUl > li",
            "title": "a",
            "date": "i",
        },
    },
]


def create_all_fetchers(logger, browser_manager=None):
    """工厂函数：创建所有交易所爬虫实例"""
    from .cffex import CFFEXFetcher
    from .czce import CZCEFetcher
    from .dce import DCEFetcher
    from .shfe import SHFEFetcher
    from .gfex import GFEXFetcher
    from .ine import INEFetcher

    fetcher_map = {
        "CFFEX": CFFEXFetcher,
        "CZCE": CZCEFetcher,
        "DCE": DCEFetcher,
        "SHFE": SHFEFetcher,
        "GFEX": GFEXFetcher,
        "INE": INEFetcher,
    }

    fetchers = []
    for cfg in EXCHANGE_CONFIGS:
        cls = fetcher_map.get(cfg["code"])
        if cls is None:
            continue
        if cfg["engine"] == "playwright":
            fetchers.append(cls(cfg, logger, browser_manager))
        else:
            fetchers.append(cls(cfg, logger))
    return fetchers
