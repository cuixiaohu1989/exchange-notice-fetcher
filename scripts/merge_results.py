"""
Merge daily crawl results into accumulated data for the public webpage.

Reads:
  - results.json (today's crawl output)
  - docs/data.json (accumulated history, if exists)

Writes:
  - docs/data.json (updated with new notices, deduplicated)

Usage:
  python scripts/merge_results.py            # Normal merge
  python scripts/merge_results.py --reset    # Clear data.json and start fresh
"""
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
RESULTS_FILE = os.path.join(PROJECT_ROOT, "results.json")
DATA_FILE = os.path.join(PROJECT_ROOT, "docs", "data.json")

# Beijing timezone
BJT = timezone(timedelta(hours=8))

# 测试页特征：URL 末尾为 /YYYYMMDD.html（无内容ID）。
# 注意：大商所真实内容ID也是8位纯数字（如 /19624363.html），
# 旧正则 /(19|20)\d{6}\.html$ 会把以19/20开头的DCE真实ID误判为测试页而丢弃。
# 改为：仅当这8位数字能解析为合法日期(年2000-2099,月1-12,日1-31)时才视为测试页，
# 这样 DCE 的任意数字ID(19624363 -> "1962-43-63" 非合法日期)不会被误杀。
TEST_URL_PATTERN = re.compile(r"/(\d{8})\.s?html?$")


def _looks_like_valid_date(num8: str) -> bool:
    """8位数字能否解析为合法日期（年2000-2099）"""
    try:
        y, m, d = int(num8[:4]), int(num8[4:6]), int(num8[6:8])
    except ValueError:
        return False
    if not (2000 <= y <= 2099):
        return False
    if not (1 <= m <= 12):
        return False
    if not (1 <= d <= 31):
        return False
    return True


def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def notice_key(n):
    """Dedup key: exchange + notice_date + title"""
    return f"{n.get('exchange', '')}|{n.get('notice_date', '')}|{n.get('title', '')}"


def is_valid_notice(n):
    """Filter out test/fake data. Real exchange URLs contain content IDs.

    测试页 URL 末尾为合法的 /YYYYMMDD.html；大商所真实内容ID(如 /19624363.html)
    虽是8位数字但不构成合法日期，不会被误杀。
    """
    link = n.get("link", "")
    if not link or not link.startswith("http"):
        return False
    m = TEST_URL_PATTERN.search(link)
    if m and _looks_like_valid_date(m.group(1)):
        print(f"  SKIP (test URL pattern): {n.get('title', '')[:40]}")
        return False
    if len(link) < 45:
        print(f"  SKIP (suspiciously short URL): {n.get('title', '')[:40]}")
        return False
    return True


def main():
    # Handle --reset flag
    if "--reset" in sys.argv:
        print("Reset mode: clearing data.json")
        save_json(DATA_FILE, {"notices": [], "last_update": "", "total": 0})
        print("data.json cleared.")
        return

    # Load today's results
    results = load_json(RESULTS_FILE, {})
    if results.get("status") != "success":
        print(f"Crawl status is '{results.get('status')}', skipping merge.")
        existing = load_json(DATA_FILE, {"notices": [], "last_update": "", "total": 0})
        existing["last_update"] = datetime.now(BJT).isoformat()
        save_json(DATA_FILE, existing)
        print(f"Updated last_update time. Total notices unchanged: {existing.get('total', 0)}")
        return

    new_notices = results.get("notices", [])
    crawl_date = results.get("date", "")

    # Date freshness check
    today_bjt = datetime.now(BJT).strftime("%Y-%m-%d")
    if crawl_date and crawl_date != today_bjt:
        crawl_dt = None
        try:
            crawl_dt = datetime.strptime(crawl_date, "%Y-%m-%d")
        except ValueError:
            pass
        if crawl_dt:
            age = (datetime.now(BJT).date() - crawl_dt.date()).days
            if age > 2:
                print(f"WARNING: results.json date is {crawl_date} ({age} days old). "
                      f"Skipping merge to prevent stale data contamination.")
                return
            else:
                print(f"NOTE: results.json date is {crawl_date} ({age} day(s) old). Proceeding.")

    # Filter out test/fake entries
    valid_notices = [n for n in new_notices if is_valid_notice(n)]
    skipped = len(new_notices) - len(valid_notices)
    if skipped > 0:
        print(f"Filtered out {skipped} invalid/test notice(s).")

    # Add crawled_date to each notice
    for n in valid_notices:
        if not n.get("crawled_date"):
            n["crawled_date"] = crawl_date

    # Load existing accumulated data
    existing = load_json(DATA_FILE, {"notices": [], "last_update": "", "total": 0})
    # Also clean any existing test data from data.json
    before = len(existing["notices"])
    existing["notices"] = [n for n in existing["notices"] if is_valid_notice(n)]
    cleaned = before - len(existing["notices"])
    if cleaned > 0:
        print(f"Cleaned {cleaned} invalid/test notice(s) from existing data.json")

    existing_keys = {notice_key(n) for n in existing["notices"]}

    # Merge: add only new notices
    added = 0
    for n in valid_notices:
        key = notice_key(n)
        if key not in existing_keys:
            existing["notices"].append(n)
            existing_keys.add(key)
            added += 1

    # Sort by notice_date descending
    existing["notices"].sort(
        key=lambda n: n.get("notice_date", ""),
        reverse=True
    )

    # Update metadata
    existing["total"] = len(existing["notices"])
    existing["last_update"] = datetime.now(BJT).isoformat()

    save_json(DATA_FILE, existing)
    print(f"Merge complete: +{added} new notices, total={existing['total']}")


if __name__ == "__main__":
    main()
