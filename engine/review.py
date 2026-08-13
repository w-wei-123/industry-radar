#!/usr/bin/env python3
"""
命中率复盘 · 系统自我验证
=========================
让系统用历史数据验证自己的信号是否有效，反向优化。这是唯一能让系统自我进化的机制。

三块复盘：
  1. 龙虎榜 alpha   机构净买 vs 机构净卖 vs 中性的 D1/D5 后验表现
                     → 验证"机构席位"信号是否真的能预测短期走势
  2. 情绪分前瞻     高情绪分(≥70) vs 低情绪分(<40) 的次日涨停家数
                     → 验证"情绪分"能否提前判断次日市场热度
  3. 事件待验证     前瞻事件已到期但 status 仍为 pending
                     → 提醒人工核对实际结果，完成推演闭环

数据源：
  东财龙虎榜（历史日期重查，D1/D5 后验字段上榜 N 日后才填充）
  engine/output/sentiment_history.json（情绪分历史）
  forward_events.json（前瞻事件库）

输出 engine/output/review.md + 报告段。

用法:
  python review.py             # 今日复盘
  python review.py 20260813    # 指定锚点日期
"""
import sys
import io
import json
from datetime import date, timedelta
from pathlib import Path
from statistics import mean

if not getattr(sys.stdout, 'encoding', '') or 'utf-8' not in (sys.stdout.encoding or '').lower():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ENGINE = Path(__file__).parent
OUTPUT = ENGINE / "output"

import lhb
import market_sentiment as ms
import forward_events


def _avg(items, key):
    vals = [x[key] for x in items if x[key] is not None]
    return round(mean(vals), 2) if vals else None


def review_lhb(anchor: date, back_days: int = 12):
    """龙虎榜 alpha：历史上榜股按机构净买分组，对比 D1/D5 后验表现"""
    buckets = {'inst_buy': [], 'inst_sell': [], 'other': []}
    for i in range(1, back_days + 1):
        td = (anchor - timedelta(days=i)).strftime('%Y%m%d')
        rows = lhb.get_lhb(td)          # 历史日期重查，D 字段此时已有值
        for r in rows:
            if r['d1'] is None and r['d5'] is None:
                continue                 # 后验未生成（当天）
            if r['instNet'] > 0.01:
                buckets['inst_buy'].append(r)
            elif r['instNet'] < -0.01:
                buckets['inst_sell'].append(r)
            else:
                buckets['other'].append(r)

    lines = []
    total = sum(len(v) for v in buckets.values())
    if not total:
        return lines
    lines.append("## 🔁 命中率复盘 · 龙虎榜 alpha")
    lines.append(f"（{total} 只有后验样本）")
    for key, label in [('inst_buy', '机构净买'), ('inst_sell', '机构净卖'), ('other', '中性')]:
        b = buckets[key]
        if not b:
            continue
        d1, d5 = _avg(b, 'd1'), _avg(b, 'd5')
        tag = ''
        if key == 'inst_buy' and d1 and d1 < 0:
            tag = ' ⚠️ 信号反向'
        if key == 'inst_sell' and d1 and d1 > 1:
            tag = ' ⚠️ 杀跌错杀'
        lines.append(f"- **{label}**（{len(b)}只）: 后1日均 {d1}% | 后5日均 {d5}%{tag}")
    return lines


def review_sentiment():
    """情绪分前瞻：高情绪分 vs 低情绪分的次日涨停家数"""
    hist = ms.load_history()
    lines = []
    if len(hist) < 4:
        return lines
    high_next, low_next = [], []
    for i in range(len(hist) - 1):
        s0, s1 = hist[i], hist[i + 1]
        if s0.get('score', 50) >= 70:
            high_next.append(s1.get('zt', 0))
        if s0.get('score', 50) < 40:
            low_next.append(s1.get('zt', 0))
    lines.append("## 🔁 命中率复盘 · 情绪分前瞻")
    if high_next:
        lines.append(f"- 情绪分≥70（亢奋）后次日平均涨停 {round(mean(high_next), 1)} 家（{len(high_next)}次）")
    else:
        lines.append("- 尚无情绪分≥70 样本")
    if low_next:
        lines.append(f"- 情绪分<40（低迷）后次日平均涨停 {round(mean(low_next), 1)} 家（{len(low_next)}次）")
    else:
        lines.append("- 尚无情绪分<40 样本")
    return lines


def review_events(anchor: date):
    """事件闭环：已到期但仍 pending 的前瞻事件 → 人工核对实际结果"""
    events = forward_events.load_events()
    pending = []
    for e in events:
        if e.get('status') == 'pending':
            try:
                ed = date.fromisoformat(e['date'])
            except Exception:
                continue
            if ed <= anchor:
                pending.append(e)
    if not pending:
        return []
    lines = ["## ⏳ 命中率复盘 · 事件待验证"]
    for e in pending:
        lines.append(f"- {e['date']} **{e.get('title')}** → 已到期，实际结果？")
    return lines


def run(anchor: date = None):
    anchor = anchor or date.today()
    lines = []
    lines += review_lhb(anchor)
    lines += review_sentiment()
    lines += review_events(anchor)
    if lines:
        lines.insert(0, "")
    return lines


def main():
    anchor = date.today()
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        anchor = date(int(arg[:4]), int(arg[4:6]), int(arg[6:8]))
    lines = run(anchor)
    if not lines:
        print("🔁 复盘：暂无足够样本（龙虎榜后验/情绪历史/到期事件均不足）")
        return
    report = "\n".join(lines).strip()
    print(report)
    (OUTPUT / "review.md").write_text(report + "\n", encoding='utf-8')


if __name__ == '__main__':
    main()
