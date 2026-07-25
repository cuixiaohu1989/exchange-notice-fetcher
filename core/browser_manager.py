"""
Playwright浏览器生命周期管理。

使用上下文管理器模式（__enter__/__exit__），
确保每次任务只创建一个浏览器实例，任务结束后强制销毁，
防止内存泄漏。

反爬策略：
- 随机化viewport和User-Agent
- 隐藏webdriver自动化标记
- 注入stealth脚本伪造chrome对象和plugins
"""
import random
from playwright.sync_api import sync_playwright


class BrowserManager:
    """Playwright浏览器生命周期管理器"""

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    ]

    # 注入页面的反检测JS脚本
    STEALTH_SCRIPT = """
        // 隐藏webdriver标记
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        // 伪造chrome对象
        window.chrome = {runtime: {}};
        // 伪造plugins
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });
        // 伪造languages
        Object.defineProperty(navigator, 'languages', {
            get: () => ['zh-CN', 'zh', 'en']
        });
        // 伪造permissions
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) =>
            parameters.name === 'notifications'
                ? Promise.resolve({state: Notification.permission})
                : originalQuery(parameters);
    """

    def __init__(self, logger, headless: bool = True):
        self.logger = logger
        self.headless = headless
        self._playwright = None
        self._browser = None
        self._context = None           # 带 stealth 的 context（SHFE/INE 用）
        self._context_no_stealth = None  # 不带 stealth 的 context（CZCE/DCE 用）

    def _create_context(self, use_stealth: bool):
        """创建浏览器上下文

        use_stealth=True: 注入反检测脚本（用于普通 WAF）
        use_stealth=False: 不注入任何脚本（瑞数 WAF 会检测 stealth 篡改并拦截）
        """
        viewport = {
            "width": random.randint(1280, 1920),
            "height": random.randint(720, 1080),
        }
        ctx = self._browser.new_context(
            viewport=viewport,
            user_agent=random.choice(self.USER_AGENTS),
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            extra_http_headers={
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
        )
        if use_stealth:
            ctx.add_init_script(self.STEALTH_SCRIPT)
        return ctx

    def __enter__(self):
        """创建浏览器实例"""
        self._playwright = sync_playwright().start()

        launch_kwargs = {
            "headless": self.headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-gpu",
            ],
        }
        try:
            self._browser = self._playwright.chromium.launch(
                channel="chrome", **launch_kwargs
            )
            self.logger.info("使用系统Chrome浏览器")
        except Exception:
            self._browser = self._playwright.chromium.launch(**launch_kwargs)
            self.logger.info("使用Playwright自带Chromium浏览器")

        # 默认创建带 stealth 的 context
        self._context = self._create_context(use_stealth=True)

        self.logger.info(
            f"浏览器已创建 (headless={self.headless})"
        )
        return self

    def __exit__(self, *args):
        """销毁浏览器实例，防止内存泄漏"""
        try:
            if self._context:
                self._context.close()
            if self._context_no_stealth:
                self._context_no_stealth.close()
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception as e:
            self.logger.error(f"关闭浏览器时出错: {e}")
        self.logger.info("浏览器实例已销毁")

    def get_page(self, use_stealth: bool = True):
        """创建新页面（上下文隔离，避免cookie/状态污染）

        use_stealth=True:  使用带 stealth 脚本的 context（SHFE/INE）
        use_stealth=False: 使用无 stealth 的 context（CZCE/DCE 瑞数 WAF）
        """
        if use_stealth:
            return self._context.new_page()
        else:
            if not self._context_no_stealth:
                self._context_no_stealth = self._create_context(use_stealth=False)
            return self._context_no_stealth.new_page()
