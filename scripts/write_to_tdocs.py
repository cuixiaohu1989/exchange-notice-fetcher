#!/usr/bin/env python3
"""
将 results.json 中的交易所通知写入腾讯文档在线表格。

用法:
    python scripts/write_to_tdocs.py                    # 从 results.json 读取
    python scripts/write_to_tdocs.py --file other.json  # 指定其他JSON文件

流程:
    1. 读取 results.json
    2. 查询腾讯文档表格已有数据（去重 + 定位最后一行）
    3. 批量写入新通知
    4. 为链接列设置超链接
"""
import json
import subprocess
import sys
import os
from pathlib import Path

# ============================================================
# 配置（如需修改表格，更新这两个ID即可）
# ============================================================
FILE_ID = "BOKXxEativjs"
SHEET_ID = "BB08J2"

# tencentdocs.py 脚本路径（WorkBuddy 内置插件）
TDOCS_SCRIPT = os.path.join(
    os.environ.get("LOCALAPPDATA", ""),
    "Programs", "WorkBuddy", "resources", "app.asar.unpacked",
    "resources", "builtin-plugins", "tencent-docs-plugin",
    "skills", "tencent-docs", "tencentdocs.py",
)

# Python 解释器（优先用 venv，回退到系统 Python）
VENV_PYTHON = r"C:\Users\cui\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
if not os.path.exists(VENV_PYTHON):
    VENV_PYTHON = sys.executable  # 回退到当前解释器


def tdoc_call(service: str, tool: str, args: dict) -> dict:
    """调用 tencentdocs.py CLI 执行 MCP 工具"""
    cmd = [
        VENV_PYTHON, TDOCS_SCRIPT,
        "tdoc_call", service, tool,
        json.dumps(args, ensure_ascii=False),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"tdoc_call 失败: {result.stderr}")

    output = json.loads(result.stdout)
    if "result" not in output:
        raise RuntimeError(f"无效响应: {output}")

    # 提取 result.content[0].text 中的 JSON
    content = output["result"].get("content", [])
    if not content:
        return {}

    text = content[0].get("text", "{}")
    # structuredContent 可能直接有数据
    structured = output["result"].get("structuredContent", {})
    if structured and "error" not in structured:
        return structured
    # 否则解析 text
    return json.loads(text)


def read_results(json_path: str) -> list:
    """读取 results.json，返回通知列表"""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    notices = data.get("notices", [])
    fetch_date = data.get("date", "")

    print(f"读取 {json_path}: {len(notices)} 条通知, 采集日期={fetch_date}")

    # 给每条通知添加采集日期
    for n in notices:
        n["fetch_date"] = fetch_date

    return notices


def get_existing_data() -> tuple:
    """
    获取表格已有数据。
    Returns:
        (last_row_index, existing_keys)
        last_row_index: 最后一行有数据的行号 (0-based)，表头算第0行
        existing_keys: 已有通知的 (exchange, notice_date, title) 集合
    """
    # 读取前 500 行（足够覆盖历史数据）
    result = tdoc_call("sheet-mcp", "get_cell_data", {
        "file_id": FILE_ID,
        "sheet_id": SHEET_ID,
        "start_row": 0,
        "end_row": 500,
        "start_col": 0,
        "end_col": 4,
        "return_csv": True,
    })

    csv_data = result.get("csv_data", "")
    if not csv_data.strip():
        return 0, set()

    lines = csv_data.strip().split("\n")
    last_row = 0
    existing_keys = set()

    for i, line in enumerate(lines):
        # CSV 行可能包含逗号在引号内的情况，简单解析
        parts = _parse_csv_line(line)
        if len(parts) >= 4 and parts[0].strip():
            last_row = i
            # exchange=parts[1], notice_date=parts[2], title=parts[3]
            if i > 0:  # 跳过表头
                key = (parts[1].strip(), parts[2].strip(), parts[3].strip())
                existing_keys.add(key)

    return last_row, existing_keys


def _parse_csv_line(line: str) -> list:
    """简单 CSV 行解析（处理引号内的逗号）"""
    parts = []
    current = ""
    in_quotes = False
    for ch in line:
        if ch == '"':
            in_quotes = not in_quotes
        elif ch == "," and not in_quotes:
            parts.append(current)
            current = ""
        else:
            current += ch
    parts.append(current)
    return parts


def write_notices(notices: list, start_row: int, existing_keys: set) -> int:
    """
    批量写入通知到表格。
    Returns: 实际写入的行数
    """
    # 过滤掉已存在的通知
    new_notices = []
    for n in notices:
        key = (n.get("exchange_name", ""), n.get("notice_date", ""), n.get("title", ""))
        if key not in existing_keys:
            new_notices.append(n)

    if not new_notices:
        print("没有新通知需要写入（全部已存在）")
        return 0

    print(f"新增 {len(new_notices)} 条通知，从第 {start_row + 1} 行开始写入")

    # 构建 set_range_value 参数（0-based row/col）
    values = []
    for i, n in enumerate(new_notices):
        row = start_row + i
        values.append({"row": row, "col": 0, "value_type": "STRING", "string_value": n.get("fetch_date", "")})
        values.append({"row": row, "col": 1, "value_type": "STRING", "string_value": n.get("exchange_name", "")})
        values.append({"row": row, "col": 2, "value_type": "STRING", "string_value": n.get("notice_date", "")})
        values.append({"row": row, "col": 3, "value_type": "STRING", "string_value": n.get("title", "")})
        values.append({"row": row, "col": 4, "value_type": "STRING", "string_value": n.get("link", "")})

    # 批量写入
    result = tdoc_call("sheet-mcp", "set_range_value", {
        "file_id": FILE_ID,
        "sheet_id": SHEET_ID,
        "values": values,
    })
    print(f"批量写入完成: {result.get('trace_id', '')}")

    # 为链接列设置超链接
    for i, n in enumerate(new_notices):
        row = start_row + i
        link = n.get("link", "")
        if link:
            tdoc_call("sheet-mcp", "set_link", {
                "file_id": FILE_ID,
                "sheet_id": SHEET_ID,
                "row": row,
                "col": 4,
                "url": link,
                "display_text": "查看详情",
            })

    # 设置数据区域样式：自动换行 + 垂直居中
    end_row = start_row + len(new_notices) - 1
    if end_row >= start_row:
        tdoc_call("sheet-mcp", "set_cell_style", {
            "file_id": FILE_ID,
            "sheet_id": SHEET_ID,
            "start_row": start_row,
            "end_row": end_row,
            "start_col": 0,
            "end_col": 4,
            "wrap_text": True,
            "vertical_align": "center",
            "font_size": 11,
        })

    return len(new_notices)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="将交易所通知写入腾讯文档")
    parser.add_argument("--file", default="results.json", help="JSON文件路径")
    args = parser.parse_args()

    json_path = args.file
    if not os.path.isabs(json_path):
        # 相对于项目根目录
        project_root = Path(__file__).parent.parent
        json_path = str(project_root / json_path)

    if not os.path.exists(json_path):
        print(f"错误: 文件不存在 {json_path}")
        sys.exit(1)

    # 1. 读取通知数据
    notices = read_results(json_path)
    if not notices:
        print("没有通知数据需要写入")
        return

    # 2. 检查 tencentdocs.py 是否存在
    if not os.path.exists(TDOCS_SCRIPT):
        print(f"错误: tencentdocs.py 不存在: {TDOCS_SCRIPT}")
        sys.exit(1)

    # 3. 获取已有数据（去重 + 定位最后一行）
    print("查询表格已有数据...")
    last_row, existing_keys = get_existing_data()
    print(f"表格已有数据到第 {last_row + 1} 行, 已有 {len(existing_keys)} 条通知")

    # 4. 写入新通知
    written = write_notices(notices, last_row + 1, existing_keys)

    print(f"\n完成! 新写入 {written} 条通知")
    print(f"腾讯文档链接: https://docs.qq.com/sheet/DQk9LWHhFYXRpdmpz")


if __name__ == "__main__":
    main()
