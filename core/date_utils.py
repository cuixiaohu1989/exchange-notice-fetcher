"""日期计算工具模块"""
from datetime import date, timedelta


class SkipFetchException(Exception):
    """周末跳过任务异常"""
    pass


def get_fetch_date_range() -> tuple[date, date]:
    """
    根据今天星期几，返回需要获取的日期范围（闭区间）。

    - 周一: 上周五 ~ 上周日（3天）
    - 周二~周五: 昨天 ~ 昨天（1天）
    - 周六/周日: 抛出 SkipFetchException

    Returns:
        (start_date, end_date) 闭区间
    """
    today = date.today()
    weekday = today.weekday()  # 0=周一, 6=周日

    if weekday in (5, 6):  # 周六或周日
        raise SkipFetchException("Today is weekend, skip fetching")

    if weekday == 0:  # 周一
        start = today - timedelta(days=3)  # 上周五
        end = today - timedelta(days=1)    # 上周日
    else:  # 周二到周五
        start = today - timedelta(days=1)
        end = today - timedelta(days=1)

    return start, end
