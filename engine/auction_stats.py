# -*- coding: utf-8 -*-
"""竞价承接·续板率统计引擎 auction_stats

核心问题: 涨停当天(尤其5板以上妖股)，哪些竞价/换手特征 → 次日续板概率更大?
数据: 腾讯日K(不复权) → 每个涨停日特征(连板高度/竞价涨幅/全天换手) + 次日是否续板
输出: content/sectors/auction-stats.md (与网站同位置，渲染成页面)

每日由 daily_scan 自动调用，样本随每日扫描不断累积，续板率越统计越准。
Python 3.7 兼容。
"""
import sys, os, csv, requests
from datetime import date

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
OUT_MD = os.path.join(ROOT, 'content', 'sectors', 'auction-stats.md')
H = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://gu.qq.com/'}

# 历史已知5板以上妖股(初始样本，后续由 watchlist/日志自动发现增量)
KNOWN_YAOGU = {
    'sz002552': '宝鼎科技',  # 7板(08/2026)
    'sh601700': '风范股份',  # 6板(08/2026)
    'sz002792': '通宇通讯',  # 5板(08/2026)
}

def secid_to_tcode(secid):
    """东财secid -> 腾讯code; 已是腾讯code则原样。"""
    if '.' in secid:
        m, num = secid.split('.', 1)
        return ('sh' if m == '1' else 'sz') + num
    return secid

def lim_pct(code):
    """各板块涨停阈值: 20%板(创业板30/科创板68) 30%板(北交) 其余10%。"""
    if code.startswith(('sh68', 'sz30')):
        return 19.5
    if code.startswith(('sh8', 'sz8', 'sz4')):
        return 29.5
    return 9.5

def fetch_daily(code, lmt=130):
    """腾讯日K(不复权)。"""
    url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=%s,day,,,%d,' % (code, lmt)
    try:
        j = requests.get(url, headers=H, timeout=15).json()
        d = (j.get('data') or {}).get(code) or {}
        return d.get('day') or d.get('qfqday') or []
    except Exception:
        return []

def float_hand(code):
    """流通股本(手) via qt.gtimg.cn。"""
    try:
        r = requests.get('https://qt.gtimg.cn/q=%s' % code, headers=H, timeout=10)
        r.encoding = 'gbk'
        parts = r.text.split('~')
        price = float(parts[3])
        fmv_yi = float(parts[44])
        return fmv_yi * 1e8 / price / 100.0 if price else None
    except Exception:
        return None

def discover_pool():
    """自动发现妖股池: 已知历史妖股 + watchlist YAOGU + 日志中曾达5板。"""
    pool = dict(KNOWN_YAOGU)
    # watchlist YAOGU 标签
    import auction_sniffer as AS
    if os.path.exists(AS.WATCH):
        for line in open(AS.WATCH, encoding='utf-8'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 4 and parts[3].startswith('YAOGU'):
                pool.setdefault(secid_to_tcode(parts[0]), parts[1])
    # 三只参考票(永久)
    for code, (name, _s) in AS.DEFAULT_WATCH.items():
        pool.setdefault(code, name)
    # 日志中曾达5板以上的票
    if os.path.exists(AS.LOG):
        for r in csv.reader(open(AS.LOG, encoding='utf-8')):
            try:
                if len(r) > 10 and r[10]:
                    if int(float(r[10])) >= 5:
                        pool.setdefault(r[1], r[2])
            except Exception:
                pass
    return pool

def extract(code, name):
    """提取该股所有涨停日样本: (连板高度/竞价涨幅/全天换手/次日是否续板)。"""
    rows = fetch_daily(code, 130)
    if not rows:
        return []
    fh = float_hand(code)
    lim = lim_pct(code)
    n = len(rows)

    def is_limit(idx):
        """rows[idx] 是否涨停日(idx<0 视为 False)。"""
        if idx < 0 or idx >= n:
            return False
        p = float(rows[idx-1][2]) if idx else float(rows[idx][1])
        return (float(rows[idx][2]) - p) / p * 100 >= lim

    out = []
    run = -1
    for i in range(n):
        op = float(rows[i][1]); cl = float(rows[i][2]); vol = float(rows[i][5])
        prev = float(rows[i-1][2]) if i else op
        pct = (cl - prev) / prev * 100
        gap = (op - prev) / prev * 100
        if pct < lim:
            continue
        # 连续涨停段: 前一交易日也是涨停日则属同一段，否则新起一段
        run = run if is_limit(i - 1) else run + 1
        # 连板高度: 往前数连续涨停(含当日)
        h = 0; k = i
        while k >= 0 and is_limit(k):
            h += 1; k -= 1
        turn = vol / fh * 100 if fh else None
        nxt_lim = nxt_pct = None
        if i + 1 < n:
            nxt_pct = (float(rows[i+1][2]) - cl) / cl * 100
            nxt_lim = nxt_pct >= lim
        out.append({'date': rows[i][0], 'name': name, 'code': code,
                    'height': h, 'gap': gap, 'turn': turn, 'run': run,
                    'pct': pct, 'next_lim': nxt_lim, 'next_pct': nxt_pct})
    return out

# ── 分层 ──
def h_tier(h):
    if h <= 1: return '首板'
    if h <= 3: return '2-3板'
    if h == 4: return '4板'
    return '5板+'

def g_tier(g):
    if g >= 9.5: return '一字(≥9.5%)'
    if g >= 5: return '高开强(+5~9.5%)'
    if g >= 1: return '高开中(+1~5%)'
    return '平/低开(<+1%)'

def t_tier(t):
    if t is None: return '—'
    if t < 5: return '缩量(<5%)'
    if t < 15: return '温和(5~15%)'
    if t < 25: return '换手(15~25%)'
    return '巨量(≥25%)'

def group(recs, tier_fn):
    """按分层统计续板率。返回 [(tier, n, cont, rate)] 按 n 降序。"""
    d = {}
    for r in recs:
        if r['next_lim'] is None:
            continue  # 最后一个交易日无次日结果
        k = tier_fn(r)
        d.setdefault(k, [0, 0])
        d[k][0] += 1
        if r['next_lim']:
            d[k][1] += 1
    rows = []
    for k, (n, c) in d.items():
        rows.append((k, n, c, c * 100.0 / n))
    rows.sort(key=lambda x: -x[1])
    return rows

def render_table(rows):
    lines = ['| 特征 | 样本 | 续板 | 续板率 |', '|------|------|------|--------|']
    for k, n, c, rate in rows:
        lines.append('| %s | %d | %d | **%.0f%%** |' % (k, n, c, rate))
    return '\n'.join(lines)

def main():
    pool = discover_pool()
    recs = []
    stock_lines = []
    for code, name in sorted(pool.items()):
        sub = extract(code, name)
        if not sub:
            print('  (无数据/退市?) %s %s' % (code, name))
            continue
        # 显示该股连板段 (按 run 分组)
        segs = {}
        for r in sub:
            segs.setdefault(r['run'], []).append(r)
        seg_txt = []
        for _k, seg in sorted(segs.items()):
            if len(seg) >= 2:
                seg_txt.append('%d连板(%s~%s)' % (len(seg), seg[0]['date'], seg[-1]['date']))
            else:
                seg_txt.append('%s' % seg[0]['date'])
        stock_lines.append('| %s | %s | %d | %s |' % (
            name, code, len(sub), '、'.join(seg_txt)))
        recs.extend(sub)
        print('%s %s: %d个涨停日样本' % (code, name, len(sub)))

    judged = [r for r in recs if r['next_lim'] is not None]
    n = len(judged)
    cont = sum(1 for r in judged if r['next_lim'])
    total_rate = cont * 100.0 / n if n else 0

    h_rows = group(recs, lambda r: h_tier(r['height']))
    g_rows = group(recs, lambda r: g_tier(r['gap']))
    t_rows = group(recs, lambda r: t_tier(r['turn']))
    # 交叉: 高度×竞价涨幅
    cross_rows = group(recs, lambda r: '%s·%s' % (h_tier(r['height']), g_tier(r['gap'])))

    # 动态结论: 样本数>=3 且 续板率最高/最低 的特征
    def best_worst(rows):
        good = [r for r in rows if r[1] >= 3]
        if not good:
            return None, None
        good.sort(key=lambda x: -x[3])
        return good[0], good[-1]

    b1, w1 = best_worst(h_rows)
    b2, w2 = best_worst(g_rows)
    b3, w3 = best_worst(t_rows)

    sig = []
    sig.append('- **总续板率 %d%%**（%d个涨停日样本，%d次续板）—— 样本每日自动累积，本页自动重算。' % (total_rate, n, cont))
    if b2 and b2[1] >= 3:
        sig.append('- 🟢 续板率最高竞价形态: **%s**（样本%d，续板率%d%%）—— 下次看到同形态，续板概率明显更高。'
                   % (b2[0], b2[1], round(b2[3])))
    if w2 and w2[0] != (b2[0] if b2 else '') and w2[1] >= 3:
        sig.append('- 🔴 续板率最低竞价形态: **%s**（样本%d，续板率%d%%）—— 高位竞价破位放量时警惕断板。'
                   % (w2[0], w2[1], round(w2[3])))
    if b3 and b3[1] >= 3:
        sig.append('- 🟢 续板率最高换手: **%s**（样本%d，续板率%d%%）'
                   % (b3[0], b3[1], round(b3[3])))
    if w3 and w3[0] != (b3[0] if b3 else '') and w3[1] >= 3:
        sig.append('- 🔴 续板率最低换手: **%s**（样本%d，续板率%d%%）'
                   % (w3[0], w3[1], round(w3[3])))
    if b1 and b1[1] >= 3:
        sig.append('- 🟢 连板高度上续板率最高: **%s**（样本%d，续板率%d%%）'
                   % (b1[0], b1[1], round(b1[3])))

    today = date.today().isoformat()
    stocks_csv = ', '.join(repr(p[1]) for p in sorted(pool.items()))
    md = """---
slug: auction-stats
updated: '%(today)s'
tags: ["竞价承接", "续板率", "连板", "统计"]
stocks: [%(stocks_csv)s]
---

## 竞价承接·续板率统计

> 核心问题：**涨停当天（尤其5板以上妖股），哪些竞价/换手特征 → 次日续板概率更大？**
> 数据来自 `auction_stats.py` 每日自动重算，样本随每日扫描持续累积——从明天起，每出现一次竞价快照+次日结果就多一个样本，续板率越统计越准。

### 样本池（自动发现: 历史妖股 + 当日5板+ + 参考票）

| 股票 | 代码 | 涨停日样本 | 连板段 |
|------|------|-----------|--------|
%(stocks)s

### 全样本续板率

%(sig)s

### 按连板高度 → 次日续板率

%(h)s

### 按竞价涨幅(开盘定位) → 次日续板率

%(g)s

### 按全天换手 → 次日续板率

%(t)s

### 交叉: 连板高度 × 竞价涨幅 → 续板率

%(cross)s

### 数据说明
- 涨停判定: 10%%板≥9.5%%，20%%板≥19.5%%，30%%板≥29.5%%（按板块涨停阈值）。
- 竞价涨幅 = 开盘价相对昨收，日K可得；竞价成交量(9:25量)自 9:26 定时任务起实时记录到 `auction_log.csv`，跨天累积后本页会追加"竞价换手率"维度。
- 样本不剔除一字/放量极端值，保持原始分布。
""" % {'today': today, 'stocks_csv': stocks_csv,
       'stocks': '\n'.join(stock_lines) if stock_lines else '（暂无样本）',
       'sig': '\n'.join(sig) if sig else '- 样本不足，等待累积。',
       'h': render_table(h_rows) if h_rows else '- 样本不足',
       'g': render_table(g_rows) if g_rows else '- 样本不足',
       't': render_table(t_rows) if t_rows else '- 样本不足',
       'cross': render_table(cross_rows) if cross_rows else '- 样本不足'}

    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    with open(OUT_MD, 'w', encoding='utf-8') as f:
        f.write(md)
    print('=' * 60)
    print('续板率统计: 总样本%d 续板率%d%%' % (n, total_rate))
    print('写入 %s' % OUT_MD)

if __name__ == '__main__':
    main()
