#!/usr/bin/env python3
"""
催化剂前置信号检测
从 market-pulse.md 解析事件日历，对比今天日期，输出未来3天内的催化剂

用法: python catalyst_check.py
输出: 即将到来的事件列表（stdout）
"""

import sys, io, re
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKET_PULSE = ROOT / "content" / "sectors" / "market-pulse.md"

def parse_calendar():
    """从 market-pulse.md 解析催化剂日历表格"""
    if not MARKET_PULSE.exists():
        return []

    raw = MARKET_PULSE.read_text(encoding="utf-8")
    lines = raw.split("\n")

    # 找到日历表格区域（## 📅 开头的section）
    in_section = False
    events = []

    for line in lines:
        if "产业催化剂日历" in line:
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if not in_section:
            continue

        line = line.strip()
        if not line.startswith("|") or "---" in line or "日期" in line:
            continue

        parts = [p.strip() for p in line.split("|") if p.strip()]
        if len(parts) < 2:
            continue

        date_str = parts[0].replace("**", "").replace("🔥", "").strip()
        event = parts[1].replace("**", "").strip()
        direction = parts[2].strip() if len(parts) > 2 else ""
        intensity = parts[3].strip() if len(parts) > 3 else ""

        events.append({
            "date_raw": date_str,
            "event": event,
            "direction": direction,
            "intensity": intensity
        })

    return events


def parse_date_range(date_str):
    """解析日期字符串，返回 (start_date, end_date)"""
    today = date.today()
    year = today.year

    # 格式: "7/10-13", "7/7", "7月中", "8/19-23", "10月"
    date_str = date_str.strip()

    # 单日: "7/7"
    match = re.match(r"(\d{1,2})/(\d{1,2})$", date_str)
    if match:
        m, d = int(match.group(1)), int(match.group(2))
        return date(year, m, d), date(year, m, d)

    # 范围: "7/10-13"
    match = re.match(r"(\d{1,2})/(\d{1,2})-(\d{1,2})$", date_str)
    if match:
        m, d1, d2 = int(match.group(1)), int(match.group(2)), int(match.group(3))
        return date(year, m, d1), date(year, m, d2)

    # 月范围: "7月中", "7月下旬", "8月内"
    month_match = re.match(r"(\d{1,2})月", date_str)
    if month_match:
        m = int(month_match.group(1))
        if "下旬" in date_str:
            return date(year, m, 21), date(year, m, 31)
        elif "中" in date_str:
            return date(year, m, 10), date(year, m, 20)
        elif "上旬" in date_str:
            return date(year, m, 1), date(year, m, 10)
        else:
            return date(year, m, 1), date(year, m, 28)

    return None, None


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    today = date.today()
    events = parse_calendar()

    if not events:
        print("⚠️ 无法解析催化剂日历")
        return

    imminent = []
    upcoming = []
    ongoing = []

    for ev in events:
        start, end = parse_date_range(ev["date_raw"])
        if start is None:
            continue

        # 今天正在进行中
        if start <= today <= end:
            ongoing.append(ev)
        # 未来1-3天开始
        elif 1 <= (start - today).days <= 3:
            imminent.append(ev)
        # 未来4-7天
        elif 4 <= (start - today).days <= 7:
            upcoming.append(ev)

    print("=" * 50)
    print(f"📅 催化剂前置信号检测 · {today.isoformat()}")
    print("=" * 50)

    if ongoing:
        print(f"\n🔴 正在进行中 ({len(ongoing)}个):")
        for ev in sorted(ongoing, key=lambda x: parse_date_range(x["date_raw"])[0]):
            print(f"  {ev['intensity']} | {ev['date_raw']} | {ev['event']} [{ev['direction']}]")

    if imminent:
        print(f"\n🟡 即将到来 1-3天内 ({len(imminent)}个):")
        for ev in sorted(imminent, key=lambda x: parse_date_range(x["date_raw"])[0]):
            print(f"  {ev['intensity']} | {ev['date_raw']} | {ev['event']} [{ev['direction']}]")
            # 前置信号提示
            if "发射" in ev["event"] or "首飞" in ev["event"]:
                print(f"    ⚠️ 前置信号: 关注航行预警/发射窗口公告（通常提前2-3天）")

    if upcoming:
        print(f"\n🟢 7天内 ({len(upcoming)}个):")
        for ev in sorted(upcoming, key=lambda x: parse_date_range(x["date_raw"])[0]):
            print(f"  {ev['intensity']} | {ev['date_raw']} | {ev['event']} [{ev['direction']}]")

    if not ongoing and not imminent and not upcoming:
        print("\n✅ 未来7天无重大催化剂")

    print(f"\n💡 规则: 发射类事件提前2-3天关注航行预警 | 展会类提前1-2周关注预告")


if __name__ == "__main__":
    main()
