"""日志配置模块"""
import logging
import sys


def setup_logger(name: str = "fetcher", level: int = logging.INFO) -> logging.Logger:
    """创建并配置日志记录器，输出到控制台"""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 避免重复添加handler
    if logger.handlers:
        return logger

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "[%(asctime)s][%(levelname)s][%(name)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(handler)
    return logger
