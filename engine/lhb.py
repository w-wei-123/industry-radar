#!/usr/bin/env python3
"""
龙虎榜 · 资金动向雷达
======================
东财数据中心龙虎榜每日明细：
  上榜个股净买额 / 上榜原因 / 机构净买 / 涨跌幅 / 后验表现(D1-D30，供命中率复盘)

功能：
  1. 龙虎榜净买 Top（谁在被资金抢筹）
  2. 机构净买 Top（机构专用席位动向）
  3. 净卖 Top（出货警示）
  4. 上榜原因聚合（涨停原因/偏离值/换手率等）

输出 engine/output/lhb.json + 报告段落。
数据源: datacenter-web.eastmoney.com RPT_DAILYBILLBOARD_DETAILSNEW

用法:
  python lhb.py            # 自动定位最近交易日
  python lhb.py 20260813   # 指定日期
"""
import sys
import io
import json
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from typing import List, Dict, Optional

if not getattr(sys.stdout, 'encoding', '') or 'utf-8' not in (sys.stdout.encoding or '').lower():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ENGINE = Path(__file__).parent
OUTPUT = ENGINE / "output"
OUTPUT.mkdir(parents=True, exist_ok=True)
UA = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://data.eastmoney.com/'}
REPORT = 'RPT_DAILYBILLBOARD_DETAILSNEW'


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=UA)
    return json.loads(urllib.request.urlopen(req, timeout=12).read().decode('utf-8', errors='replace'))


def get_lhb(trade_date: str) -> List[Dict]:
    """东财龙虎榜每日明细（date 格式 YYYYMMDD → 接口 YYYY-MM-DD）"""
    d = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]}"
    url = ('https://datacenter-web.eastmoney.com/api/data/v1/get'
           f'?sortColumns=BILLBOARD_NET_AMT&sortTypes=-1&pageSize=300&pageNumber=1'
           f'&reportName={REPORT}&columns=ALL&filter=(TRADE_DATE%3D%27{d}%27)')
    try:
        j = fetch_json(url)
        rows = ((j.get('result') or {}).get('data')) or []
    except Exception:
        return []
    out = []
    for r in rows:
        code = str(r.get('SECURITY_CODE', ''))
        if code[:2] not in ('60', '68', '00', '30'):
            continue  # 过滤转债/基金/其他非股票
        out.append({
            'code': r.get('SECURITY_CODE', ''),
            'name': r.get('SECURITY_NAME_ABBR', ''),
            'explain': r.get('EXPLAIN', '') or r.get('EXPLANATION', ''),
            'netAmt': (r.get('BILLBOARD_NET_AMT') or 0) / 1e8,      # 亿元
            'buyAmt': (r.get('BILLBOARD_BUY_AMT') or 0) / 1e8,
            'sellAmt': (r.get('BILLBOARD_SELL_AMT') or 0) / 1e8,
            'instNet': (r.get('NET_BS_AMT') or 0) / 1e8,            # 机构净买 亿元
            'chg': r.get('CHANGE_RATE'),
            'turn': r.get('TURNOVERRATE'),
            'd1': r.get('D1_CLOSE_ADJCHRATE'),                      # 后验表现(当日为None)
            'd5': r.get('D5_CLOSE_ADJCHRATE'),
        })
    return out


def find_last_trade_date(anchor: date, back_days: int = 8) -> Optional[str]:
    for i in range(back_days):
        d = anchor - timedelta(days=i)
        s = d.strftime('%Y%m%d')
        if get_lhb(s):
            return s
    return None


def report_block(rows: List[Dict]) -> List[str]:
    """生成报告段落"""
    lines = []
    if not rows:
        lines.append("- 今日无龙虎榜数据")
        return lines
    inst = [r for r in rows if r['instNet'] > 0.01]
    inst.sort(key=lambda r: -r['instNet'])
    buy = sorted(rows, key=lambda r: -r['netAmt'])[:8]
    sell = sorted(rows, key=lambda r: r['netAmt'])[:5]

    if inst:
        lines.append("- **机构净买 Top**: " + ' | '.join(
            f"{r['name']}({r['instNet']:.2f}亿)" for r in inst[:5]))
    lines.append("- **龙虎榜净买**: " + ' | '.join(
        f"{r['name']}({r['netAmt']:+.2f}亿)" for r in buy))
    lines.append("- **净卖警示**: " + ' | '.join(
        f"{r['name']}({r['netAmt']:+.2f}亿)" for r in sell))
    return lines


def main():
    anchor = date.today()
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        anchor = date(int(arg[:4]), int(arg[4:6]), int(arg[6:8]))
    td = find_last_trade_date(anchor)
    if not td:
        print("❌ 最近8日无龙虎榜数据")
        return
    rows = get_lhb(td)
    # 按股票去重（同日多次上榜，保留机构净买最大的一条）
    seen = {}
    for r in rows:
        c = r['code']
        if c not in seen or abs(r['instNet']) > abs(seen[c]['instNet']):
            seen[c] = r
    rows = list(seen.values())
    print(f"🐉 龙虎榜（{td}）：{len(rows)} 只上榜")
    for line in report_block(rows):
        print("  " + line)
    (OUTPUT / "lhb.json").write_text(json.dumps({
        'date': td, 'count': len(rows), 'rows': rows,
    }, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
