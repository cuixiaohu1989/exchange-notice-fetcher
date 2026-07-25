"""BaseFetcher 日期解析和过滤单元测试"""
import pytest
from datetime import date

from fetchers.base import BaseFetcher, Notice


class TestParseDate:
    """测试日期解析"""

    def setup_method(self):
        """创建一个最小化的BaseFetcher子类用于测试"""
        class TestFetcher(BaseFetcher):
            def fetch(self, start_date, end_date):
                return []
        self.fetcher = TestFetcher({"code": "TEST"}, None)

    def test_parse_yyyy_dash_mm_dash_dd(self):
        assert self.fetcher._parse_date("2026-07-20") == date(2026, 7, 20)

    def test_parse_yyyy_slash_mm_slash_dd(self):
        assert self.fetcher._parse_date("2026/07/20") == date(2026, 7, 20)

    def test_parse_yyyy_dot_mm_dot_dd(self):
        assert self.fetcher._parse_date("2026.07.20") == date(2026, 7, 20)

    def test_parse_chinese_date(self):
        assert self.fetcher._parse_date("2026年07月20日") == date(2026, 7, 20)

    def test_parse_yyyymmdd(self):
        assert self.fetcher._parse_date("20260720") == date(2026, 7, 20)

    def test_parse_with_whitespace(self):
        assert self.fetcher._parse_date("  2026-07-20  ") == date(2026, 7, 20)

    def test_parse_invalid_raises(self):
        with pytest.raises(ValueError):
            self.fetcher._parse_date("invalid date")

    def test_parse_empty_raises(self):
        with pytest.raises(ValueError):
            self.fetcher._parse_date("")


class TestFilterByDate:
    """测试日期过滤"""

    def setup_method(self):
        class TestFetcher(BaseFetcher):
            def fetch(self, start_date, end_date):
                return []
        self.fetcher = TestFetcher({"code": "TEST"}, None)

    def test_filter_in_range(self):
        notices = [
            Notice("TEST", "测试", "标题1", "2026-07-20", "http://example.com/1"),
            Notice("TEST", "测试", "标题2", "2026-07-21", "http://example.com/2"),
            Notice("TEST", "测试", "标题3", "2026-07-22", "http://example.com/3"),
        ]
        result = self.fetcher._filter_by_date(notices, date(2026, 7, 20), date(2026, 7, 21))
        assert len(result) == 2
        assert result[0].title == "标题1"
        assert result[1].title == "标题2"

    def test_filter_single_day(self):
        notices = [
            Notice("TEST", "测试", "标题1", "2026-07-20", "http://example.com/1"),
            Notice("TEST", "测试", "标题2", "2026-07-21", "http://example.com/2"),
        ]
        result = self.fetcher._filter_by_date(notices, date(2026, 7, 20), date(2026, 7, 20))
        assert len(result) == 1
        assert result[0].title == "标题1"

    def test_filter_empty_list(self):
        result = self.fetcher._filter_by_date([], date(2026, 7, 20), date(2026, 7, 21))
        assert len(result) == 0

    def test_filter_no_match(self):
        notices = [
            Notice("TEST", "测试", "标题1", "2026-07-15", "http://example.com/1"),
        ]
        result = self.fetcher._filter_by_date(notices, date(2026, 7, 20), date(2026, 7, 21))
        assert len(result) == 0


class TestNoticeToDict:
    """测试Notice序列化"""

    def test_to_dict(self):
        n = Notice("CFFEX", "中金所", "测试标题", "2026-07-20", "http://example.com")
        d = n.to_dict()
        assert d["exchange"] == "CFFEX"
        assert d["exchange_name"] == "中金所"
        assert d["title"] == "测试标题"
        assert d["notice_date"] == "2026-07-20"
        assert d["link"] == "http://example.com"
