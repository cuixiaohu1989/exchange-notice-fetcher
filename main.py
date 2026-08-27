#!/usr/bin/env python3
"""
交易所通知获取 - 主入口

用法:
    python main.py                          # 正式运行（无头模式，全交易所）
    python main.py --debug                  # 调试模式（不写入，仅打印结果）
    python main.py --exchange CFFEX         # 仅爬取指定交易所
    python main.py --exchange CFFEX --no-headless  # 有头模式（调试用）

输出:
    results.json - 爬取结果，供WorkBuddy自动化读取
"""
import json
import sys
import argparse
from pathlib import Path

from utils.logger import setup_logger
from core.engine import FetchEngine
from fetchers import create_all_fetchers, EXCHANGE_CONFIGS


def main():
    parser = argparse.ArgumentParser(description="期货交易所通知自动获取")
    parser.add_argument(
        "--debug", action="store_true",
        help="调试模式：仅打印结果，不写入文件"
    )
    parser.add_argument(
        "--exchange", type=str,
        help="仅爬取指定交易所 (CFFEX/CZCE/DCE/SHFE/GFEX/INE)"
    )
    parser.add_argument(
        "--no-headless", action="store_true",
        help="使用有头浏览器模式（调试用）"
    )
    parser.add_argument(
        "--headless", action="store_true",
        help="明确使用无头模式（默认即无头，此参数仅为兼容性）"
    )
    args = parser.parse_args()

    # 初始化
    logger = setup_logger()
    logger.info("程序启动")
    logger.info(f"参数: debug={args.debug}, exchange={args.exchange}, "
                f"headless={not args.no_headless}")

    # 创建爬虫
    fetchers = create_all_fetchers(logger)

    # 过滤交易所（如果指定了 --exchange）
    if args.exchange:
        exchange_code = args.exchange.upper()
        fetchers = [f for f in fetchers if f.name == exchange_code]
        if not fetchers:
            logger.error(f"未找到交易所: {args.exchange}")
            logger.info(f"可用交易所: {[c['code'] for c in EXCHANGE_CONFIGS]}")
            sys.exit(1)

    # 运行引擎
    engine = FetchEngine(
        fetchers,
        logger,
        headless=not args.no_headless,
    )
    result = engine.run()

    # 输出JSON
    output_json = json.dumps(result, ensure_ascii=False, indent=2)
    print(output_json)

    if not args.debug:
        output_path = Path("results.json")
        output_path.write_text(output_json, encoding="utf-8")
        logger.info(f"结果已写入 {output_path}")
    else:
        logger.info("调试模式：未写入文件")

    # 退出策略：
    # - 单家交易所偶发失败（WAF 挑战/网络抖动）在 CI 上很常见，
    #   不应让整个 workflow 失败而跳过 merge/deploy，否则已采到的数据也无法发布。
    # - 因此无论是否有失败交易所，main 始终 exit 0，把"是否完整"记录在结果里供日志查看。
    # - 真正的致命错误（如 import 失败、语法错误）会让 Python 以非 0 退出，那才是 workflow 该失败的。
    if result.get("failed_exchanges"):
        logger.warning(
            f"以下交易所本次采集失败（已隔离，不影响其他家）: "
            f"{', '.join(result['failed_exchanges'])}"
        )


if __name__ == "__main__":
    main()
