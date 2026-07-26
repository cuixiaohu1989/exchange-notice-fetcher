"""
Merge daily crawl results into accumulated data for the public webpage.

Reads:
  - results.json (today's crawl output)
  - docs/data.json (accumulated history, if exists)

Writes:
  - docs/data.json (updated with new notices, deduplicated)
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
RESULTS_FILE = os.path.join(PROJECT_ROOT, "results.json")
DATA_FILE = os.path.join(PROJECT_ROOT, "docs", "data.json")

# Beijing timezone
BJT = timezone(timedelta(hours=8))


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


def main():
    # Load today's results
    results = load_json(RESULTS_FILE, {})
    if results.get("status") != "success":
        print(f"Crawl status is '{results.get('status')}', skipping merge.")
        # Still update last_update time so the page shows it tried
        existing = load_json(DATA_FILE, {"notices": [], "last_update": "", "total": 0})
        existing["last_update"] = datetime.now(BJT).isoformat()
        save_json(DATA_FILE, existing)
        print(f"Updated last_update time. Total notices unchanged: {existing.get('total', 0)}")
        return

    new_notices = results.get("notices", [])
    crawl_date = results.get("date", "")

    # Add crawled_date to each notice
    for n in new_notices:
        if not n.get("crawled_date"):
            n["crawled_date"] = crawl_date

    # Load existing accumulated data
    existing = load_json(DATA_FILE, {"notices": [], "last_update": "", "total": 0})
    existing_keys = {notice_key(n) for n in existing["notices"]}

    # Merge: add only new notices
    added = 0
    for n in new_notices:
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
