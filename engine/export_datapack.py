#!/usr/bin/env python3
"""
豆包数据包导出器 · 每日生成可复制给豆包AI独立分析的数据包
用法: python export_datapack.py [YYYYMMDD]
输出: engine/data/doubao_datapack_{date}.md
"""
import sys, io, json, os, urllib.request
from datetime import date, timedelta
from collections import Counter
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
UA = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://quote.eastmoney.com/'}
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 大盘指数代码
INDEXES = {
    "sh000001": "沪指", "sz399001": "深成指", "sz399006": "创业板指",
    "sh000688": "科创50", "sz399852": "中证1000", "sh000300": "沪深300",
}

def fetch_json(url):
    req = urllib.request.Request(url, headers=UA)
    raw = urllib.request.urlopen(req, timeout=20).read().decode()
    return json.loads(raw)

def get_limit_up_pool(trade_date):
    url = (f'https://push2ex.eastmoney.com/getTopicZTPool?ut=7eea3edcaed734bea9cbfc24409ed989'
           f'&dpt=wz.ztzt&Pageindex=0&pagesize=300&sort=fbt%3Aasc&date={trade_date}&_=1')
    d = fetch_json(url)
    if not d.get('data') or not d['data'].get('pool'):
        return []
    return d['data']['pool']

def tencent_quote(codes):
    url = "https://qt.gtimg.cn/q=" + ",".join(codes)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=10)
    data = resp.read().decode("gbk")
    result = {}
    for line in data.strip().split(";"):
        if "=" not in line or '"' not in line: continue
        key = line.split("=")[0].split("_")[-1]
        vals = line.split('"')[1].split("~")
        if len(vals) < 53: continue
        result[key] = {"name": vals[1], "price": vals[3], "change_pct": vals[32],
                       "volume": vals[6], "turnover": vals[37], "amount": vals[37]}
    return result

def market_overview():
    """大盘概况"""
    q = tencent_quote(list(INDEXES.keys()))
    lines = []
    for code, name in INDEXES.items():
        v = q.get(code)
        if v and v["price"]:
            lines.append(f"- {name} {v['price']}（{v['change_pct']}%）")
    return lines

def main():
    # 确定目标日期
    if len(sys.argv) > 1:
        target = sys.argv[1]
    else:
        target = None
        for i in range(0, 8):
            d = date.today() - timedelta(days=i)
            t = d.strftime('%Y%m%d')
            pool = get_limit_up_pool(t)
            if pool:
                target = t
                break
    if not target:
        print("⚠️ 未获取到数据")
        return

    pool = get_limit_up_pool(target)
    if not pool:
        print("⚠️ 涨停池为空（非交易日？）")
        return

    # 格式化日期
    d = date.fromisoformat(f"{target[:4]}-{target[4:6]}-{target[6:]}")
    fmt = f"{d.year}-{d.month}-{d.day}"

    lines = [f"【A股盘面数据包 · {fmt}】",
             "供你独立完成'盘面扫描→主线推演→妖股筛选→风险判断'全流程，不依赖我预设结论。",
             "", "━━━━━━━━━━━━━━━━━━━", "一、大盘概况", "━━━━━━━━━━━━━━━━━━━"]

    # 指数
    idx = tencent_quote(list(INDEXES.keys()))
    for code, name in INDEXES.items():
        v = idx.get(code)
        if v and v["price"]:
            lines.append(f"- {name} {v['price']}（{v['change_pct']}%）")
    lines.append("")

    # 涨停统计
    sector_hot = Counter(p.get('hybk', '') for p in pool)
    lines.append(f"- 涨停总数：{len(pool)}只")
    lines.append(f"- 板块热度TOP：{', '.join(f'{k}({v})' for k, v in sector_hot.most_common(8))}")
    lines.append("")

    # 连板梯队
    lb_pool = sorted([p for p in pool if p.get('lbc', 1) >= 3], key=lambda x: -x.get('lbc', 1))
    if lb_pool:
        lines.append("二、连板梯队（高位股，警惕）")
        for p in lb_pool:
            lbc = p.get('lbc', 1)
            lines.append(f"{lbc}板: {p.get('n','')}({p.get('hybk','')})")
        lines.append("")

    # 涨停池完整数据
    lines.append("三、涨停池完整数据")
    lines.append("代码|名称|连板|现价|换手%|流通亿|封单万|开板次|板块")
    for p in pool:
        price = p.get('p', 0) / 1000 if p.get('p', 0) > 100 else p.get('p', 0)
        ltsz = p.get('ltsz', 0) / 1e8
        fund = p.get('fund', 0) / 1e4
        lines.append(f"{p.get('c','')}|{p.get('n','')}|{p.get('lbc',1)}板|{price:.2f}|{p.get('hs',0):.1f}|{ltsz:.0f}|{fund:.0f}|{p.get('zbc',0)}|{p.get('hybk','')}")

    out = DATA_DIR / f"doubao_datapack_{target}.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"✅ 数据包已生成: {out}")
    print(f"涨停{len(pool)}只 | 板块TOP: {', '.join(f'{k}({v})' for k,v in sector_hot.most_common(5))}")

if __name__ == '__main__':
    main()
