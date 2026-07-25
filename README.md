# 交易所通知自动获取系统

每天早上7点（工作日）自动爬取6家期货交易所官网通知，输出JSON结果，通过WorkBuddy写入腾讯文档在线表格。

## 支持的交易所

| 交易所 | 代码 | 爬取方式 | WAF |
|--------|------|----------|-----|
| 中金所 | CFFEX | requests+BS4 | 无 |
| 郑商所 | CZCE | Playwright+stealth | 是 |
| 大商所 | DCE | Playwright | 可能有 |
| 上期所 | SHFE | Playwright+stealth | 是(人机识别) |
| 广期所 | GFEX | Playwright+stealth | 是 |
| 上期能源 | INE | Playwright+stealth | 是(人机识别) |

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt
playwright install chromium

# 测试单个交易所（调试模式）
python main.py --debug --exchange CFFEX

# 正式运行（全交易所）
python main.py

# 有头模式调试（可看到浏览器）
python main.py --exchange GFEX --no-headless
```

## 诊断选择器

GFEX和INE的CSS选择器需要通过诊断脚本确认：

```bash
python scripts/diagnose_selector.py --exchange GFEX
python scripts/diagnose_selector.py --exchange INE
```

## 运行测试

```bash
pytest tests/ -v
```

## 架构

```
GitHub Actions (07:00) → 爬虫 → results.json → 提交到仓库
WorkBuddy自动化 (07:30) → 读取results.json → 写入腾讯文档
```

## 日期逻辑

- 周一：获取上周五~周日的通知
- 周二~周五：获取前一天的通知
- 周末：不运行
