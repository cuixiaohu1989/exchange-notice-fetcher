"""日期计算工具单元测试"""
import pytest
from datetime import date
from unittest.mock import patch

from core.date_utils import get_fetch_date_range, SkipFetchException


class TestGetFetchDateRange:

    @patch("core.date_utils.date")
    def test_monday_returns_friday_to_sunday(self, mock_date):
        """周一应返回上周五到上周日"""
        mock_date.today.return_value = date(2026, 7, 20)  # 周一
        mock_date.side_effect = lambda *args, **kw: date(*args, **kw)

        start, end = get_fetch_date_range()
        assert start == date(2026, 7, 17)  # 上周五
        assert end == date(2026, 7, 19)    # 上周日

    @patch("core.date_utils.date")
    def test_tuesday_returns_yesterday(self, mock_date):
        """周二应返回昨天"""
        mock_date.today.return_value = date(2026, 7, 21)  # 周二
        mock_date.side_effect = lambda *args, **kw: date(*args, **kw)

        start, end = get_fetch_date_range()
        assert start == date(2026, 7, 20)  # 昨天
        assert end == date(2026, 7, 20)

    @patch("core.date_utils.date")
    def test_wednesday_returns_yesterday(self, mock_date):
        """周三应返回昨天"""
        mock_date.today.return_value = date(2026, 7, 22)  # 周三
        mock_date.side_effect = lambda *args, **kw: date(*args, **kw)

        start, end = get_fetch_date_range()
        assert start == date(2026, 7, 21)
        assert end == date(2026, 7, 21)

    @patch("core.date_utils.date")
    def test_thursday_returns_yesterday(self, mock_date):
        """周四应返回昨天"""
        mock_date.today.return_value = date(2026, 7, 23)  # 周四
        mock_date.side_effect = lambda *args, **kw: date(*args, **kw)

        start, end = get_fetch_date_range()
        assert start == date(2026, 7, 22)
        assert end == date(2026, 7, 22)

    @patch("core.date_utils.date")
    def test_friday_returns_yesterday(self, mock_date):
        """周五应返回昨天"""
        mock_date.today.return_value = date(2026, 7, 24)  # 周五
        mock_date.side_effect = lambda *args, **kw: date(*args, **kw)

        start, end = get_fetch_date_range()
        assert start == date(2026, 7, 23)
        assert end == date(2026, 7, 23)

    @patch("core.date_utils.date")
    def test_saturday_raises_skip(self, mock_date):
        """周六应抛出SkipFetchException"""
        mock_date.today.return_value = date(2026, 7, 25)  # 周六
        mock_date.side_effect = lambda *args, **kw: date(*args, **kw)

        with pytest.raises(SkipFetchException):
            get_fetch_date_range()

    @patch("core.date_utils.date")
    def test_sunday_raises_skip(self, mock_date):
        """周日应抛出SkipFetchException"""
        mock_date.today.return_value = date(2026, 7, 26)  # 周日
        mock_date.side_effect = lambda *args, **kw: date(*args, **kw)

        with pytest.raises(SkipFetchException):
            get_fetch_date_range()

    @patch("core.date_utils.date")
    def test_monday_edge_case(self, mock_date):
        """周一跨月情况：7月1日是周二，6月29日是周一"""
        mock_date.today.return_value = date(2026, 6, 29)  # 周一
        mock_date.side_effect = lambda *args, **kw: date(*args, **kw)

        start, end = get_fetch_date_range()
        assert start == date(2026, 6, 26)  # 上周五
        assert end == date(2026, 6, 28)    # 上周日
