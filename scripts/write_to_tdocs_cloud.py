#!/usr/bin/env python3
"""
云端版: 将 results.json 中的交易所通知写入腾讯文档在线表格。
使用腾讯文档 Open API (sheetbook endpoint) + OAuth access_token。
设计用于 GitHub Actions 云端执行。

关键发现:
  - sheetbook 写入端点需要内部 fileID (300000000$BOKXxEativjs)
  - PUT /openapi/sheetbook/v2/{内部fileID}/values/{sheet_id}!{range}
  - body: {"values": [[row1...], [row2...], ...]}
  - 认证头: Access-Token / Client-Id / Open-Id

环境变量 (GitHub Secrets):
    TDOC_ACCESS_TOKEN  - OAuth access token (30天有效期)
    TDOC_CLIENT_ID     - 应用 Client ID
    TDOC_OPEN_ID       - 用户 Open ID

用法:
    python scripts/write_to_tdocs_cloud.py                    # 从 results.json 读取
    python scripts/write_to_tdocs_cloud.py --file other.json  # 指定其他JSON

去重策略:
  使用 state/notices_state.json 文件记录已写入的通知和最后一行行号。
  每次运行时加载状态 → 过滤新通知 → 写入 → 更新状态。
  GitHub Actions 需要将更新后的状态文件 commit 回仓库。
"""
import json
import os
import sys
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

# ============================================================
# 配置
# ============================================================
# 内部 fileID (通过 fileID 转换器获取: GET /openapi/drive/v2/util/converter?type=2&value=DQk9LWHhFYXRpdmpz)
INTERNAL_FILE_ID = "300000000$BOKXxEativjs"
SHEET_ID = "BB08J2"
SPREADSHEET_URL = "https://docs.qq.com/sheet/DQk9LWHhFYXRpdmpz"
NUM_COLS = 5  # A-E: 采集日期, 交易所, 通知日期, 通知标题, 链接

# API 端点
SHEETBOOK_WRITE_URL = "https://docs.qq.com/openapi/sheetbook/v2/{file_id}/values/{range}"
CONVERTER_URL = "https://docs.qq.com/openapi/drive/v2/util/converter"

# 状态文件路径 (相对于项目根目录)
STATE_FILE = "state/notices_state.json"


def get_headers():
    """获取 Open API 认证头"""
    token = os.environ.get("TDOC_ACCESS_TOKEN", "")
    client_id = os.environ.get("TDOC_CLIENT_ID", "")
    open_id = os.environ.get("TDOC_OPEN_ID", "")

    if not all([token, client_id, open_id]):
        print("警告: 未设置 TDOC 环境变量，跳过腾讯文档写入（不影响网页发布）")
        return None

    return {
        "Access-Token": token,
        "Client-Id": client_id,
        "Open-Id": open_id,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def convert_file_id(encoded_id, headers):
    """通过 fileID 转换器获取内部 fileID"""
    url = f"{CONVERTER_URL}?type=2&value={encoded_id}"
    req = urllib.request.Request(url, method="GET")
    for k, v in headers.items():
        req.add_header(k, v)

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("ret") == 0:
            return data["data"]["fileID"]
        print(f"警告: fileID 转换失败: {data}")
    except Exception as e:
        print(f"警告: fileID 转换请求失败: {e}")

    return None


def load_state():
    """加载去重状态文件"""
    project_root = Path(__file__).parent.parent
    state_path = project_root / STATE_FILE

    if state_path.exists():
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"警告: 状态文件读取失败 ({e})，将从头开始")

    # 初始状态: 表头在第1行，数据从第2行开始
    return {"last_row": 1, "written_keys": []}


def save_state(state):
    """保存去重状态文件"""
    project_root = Path(__file__).parent.parent
    state_path = project_root / STATE_FILE
    state_path.parent.mkdir(exist_ok=True)

    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    print(f"状态文件已更新: {state_path}")


def write_sheet_data(headers, internal_file_id, start_row, rows):
    """
    通过 sheetbook API 写入数据到表格
    start_row: 起始行号 (1-based, A1=第1行)
    rows: 二维数组，每个元素是一行的值列表
    """
    if not rows:
        return True

    encoded_id = urllib.parse.quote(internal_file_id, safe="")
    end_row = start_row + len(rows) - 1
    range_str = f"{SHEET_ID}!A{start_row}:E{end_row}"

    url = SHEETBOOK_WRITE_URL.format(file_id=encoded_id, range=range_str)

    # 构造请求体
    values = []
    for row_data in rows:
        padded = list(row_data) + [""] * (NUM_COLS - len(row_data))
        values.append(padded[:NUM_COLS])

    body = json.dumps({"values": values}).encode("utf-8")

    req = urllib.request.Request(url, data=body, method="PUT")
    for k, v in headers.items():
        req.add_header(k, v)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("ret") == 0:
            return True
        else:
            print(f"写入失败: {json.dumps(data, ensure_ascii=False)}")
            return False
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace") if e.fp else ""
        print(f"写入失败: HTTP {e.code} {detail[:300]}")
        return False
    except Exception as e:
        print(f"写入失败: {e}")
        return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="将交易所通知写入腾讯文档 (云端版)")
    parser.add_argument("--file", default="results.json", help="JSON文件路径")
    args = parser.parse_args()

    json_path = args.file
    if not os.path.isabs(json_path):
        json_path = str(Path(__file__).parent.parent / json_path)

    if not os.path.exists(json_path):
        print(f"错误: 文件不存在 {json_path}")
        sys.exit(1)

    # 1. 读取通知数据
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    notices = data.get("notices", [])
    fetch_date = data.get("date", "")

    print(f"读取 {json_path}: {len(notices)} 条通知, 采集日期={fetch_date}")

    if not notices:
        print("没有通知数据需要写入")
        return

    # 2. 获取认证头
    headers = get_headers()
    if headers is None:
        print("跳过腾讯文档写入（缺少凭证）")
        return

    # 3. 获取内部 fileID (优先使用配置的，备选通过转换器获取)
    internal_file_id = INTERNAL_FILE_ID
    if "$" not in internal_file_id:
        converted = convert_file_id(internal_file_id, headers)
        if converted:
            internal_file_id = converted

    print(f"内部 fileID: {internal_file_id}")

    # 4. 加载去重状态
    state = load_state()
    written_keys = set(tuple(k) for k in state.get("written_keys", []))
    last_row = state.get("last_row", 1)

    print(f"去重状态: 已写入 {len(written_keys)} 条, 最后一行 = {last_row}")

    # 5. 过滤新通知
    new_notices = []
    for n in notices:
        key = (
            n.get("exchange_name", ""),
            n.get("notice_date", ""),
            n.get("title", ""),
        )
        if key not in written_keys:
            new_notices.append(n)
            written_keys.add(key)

    if not new_notices:
        print("没有新通知需要写入（全部已存在）")
        print(f"\n腾讯文档链接: {SPREADSHEET_URL}")
        return

    print(f"新增 {len(new_notices)} 条通知，从第 {last_row + 1} 行开始写入")

    # 6. 构造写入数据
    write_rows = []
    for n in new_notices:
        write_rows.append([
            fetch_date,
            n.get("exchange_name", ""),
            n.get("notice_date", ""),
            n.get("title", ""),
            n.get("link", ""),
        ])

    # 7. 写入
    start_row = last_row + 1
    success = write_sheet_data(headers, internal_file_id, start_row, write_rows)

    if success:
        print(f"写入成功! 新增 {len(new_notices)} 条通知 (行 {start_row}-{start_row + len(write_rows) - 1})")

        # 8. 更新状态
        state["last_row"] = start_row + len(write_rows) - 1
        state["written_keys"] = [list(k) for k in written_keys]
        save_state(state)
        print(f"状态已更新: last_row={state['last_row']}, 总计 {len(written_keys)} 条")
    else:
        print("写入失败，跳过腾讯文档写入（不影响网页发布）")
        return

    print(f"\n腾讯文档链接: {SPREADSHEET_URL}")


if __name__ == "__main__":
    main()
