# -*- coding: utf-8 -*-
"""竞价承接嗅探器 auction_sniffer

9:25-9:29 集合竞价定盘瞬间抓取 竞价量/竞价额/竞价涨幅/竞价换手率，
判断资金承接意愿 -> 预判连板延续性。数据落 engine/output/auction_log.csv。

用法:
  python auction_sniffer.py            # 实时抓取(9:15-9:30窗口内调用，其他时段为演示)
  python auction_sniffer.py --backfill # 回填自选股近N天日线(竞价涨幅+全天换手率，竞价量None)

配合 daily_scan/yaogu_hunter: 5板以上妖股 + 低位涨停自动纳入 watchlist。
Python 3.7 兼容。
"""
import sys, csv, os, time, datetime, json
from datetime import date
import requests
requests.packages.urllib3.disable_warnings()

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, 'output')
WATCH = os.path.join(OUT, 'auction_watch.txt')
LOG = os.path.join(OUT, 'auction_log.csv')

H_Q = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://gu.qq.com/'}
H_E = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://quote.eastmoney.com/'}

# 关注池: code -> (名称, 东财secid, 腾讯前缀)
DEFAULT_WATCH = {
    'sz001258': ('立新能源', '0.001258'),
    'sh600721': ('百花医药', '1.600721'),
    'sh600664': ('哈药股份', '1.600664'),
}

def ensure_out():
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    if not os.path.exists(LOG):
        with open(LOG, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['date', 'code', 'name', 'auction_price', 'auction_gap_pct',
                        'auction_vol_hand', 'auction_amt', 'auction_turnover_pct',
                        'prev_close', 'day_turnover_pct', 'boards', 'note'])

def load_watch():
    """读取自选池: 每行 `sz001258,立新能源,0.001258` 或仅 code。"""
    d = dict(DEFAULT_WATCH)
    if os.path.exists(WATCH):
        for line in open(WATCH, encoding='utf-8'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = [p.strip() for p in line.split(',')]
            code = parts[0]
            name = parts[1] if len(parts) > 1 else code
            secid = parts[2] if len(parts) > 2 else code
            d[code] = (name, secid)
    return d

def tencent_qt(code):
    """腾讯实时行情 -> dict; 9:15-9:30 时 开/量=竞价结果。"""
    try:
        r = requests.get('https://qt.gtimg.cn/q=%s' % code, headers=H_Q, timeout=10)
        r.encoding = 'gbk'
        parts = r.text.split('~')
        if len(parts) < 45:
            return None
        price = float(parts[3]); prev = float(parts[4]); openp = float(parts[5])
        vol = float(parts[6])  # 手 (竞价时=竞价量)
        turn = float(parts[38]) if parts[38] else 0.0
        fmv = float(parts[44]) if parts[44] else 0.0  # 流通市值亿
        float_hand = fmv * 1e8 / price / 100.0 if price else 0.0
        gap = (openp - prev) / prev * 100 if prev else 0.0
        return {'price': price, 'prev': prev, 'open': openp, 'vol': vol,
                'turn': turn, 'fmv': fmv, 'float_hand': float_hand, 'gap': gap}
    except Exception:
        return None

def em_qt(secid):
    """东财实时 -> dict; 9:15-9:30 时 f46开/f47量=竞价。"""
    try:
        url = ('https://push2.eastmoney.com/api/qt/stock/get?secid=%s'
               '&fields=f43,f44,f45,f46,f47,f48,f57,f58,f60,f62,f168,f170' % secid)
        j = requests.get(url, headers=H_E, timeout=10, verify=False).json()
        d = j.get('data') or {}
        return {'price': (d.get('f43') or 0) / 100.0,
                'prev': (d.get('f60') or 0) / 100.0,
                'open': (d.get('f46') or 0) / 100.0,
                'vol': (d.get('f47') or 0),           # 手
                'amt': (d.get('f48') or 0),           # 元
                'turn': (d.get('f168') or 0) / 100.0, # 全天换手率%
                'pct': (d.get('f170') or 0) / 100.0}
    except Exception:
        return None

def backfill_daily(code, name, secid, days=20):
    """回填: 从腾讯日K(不复权)算 竞价涨幅/全天换手率/涨停数/次日。竞价量无法获得=None。"""
    url = ('https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=%s,day,,,%d,'
           % (code, days + 5))
    try:
        j = requests.get(url, headers=H_Q, timeout=15).json()
        rows = ((j.get('data') or {}).get(code) or {}).get('day') or []
    except Exception:
        return []
    if not rows:
        return []
    qt = tencent_qt(code)
    fh = qt['float_hand'] if qt else None
    out = []
    n = len(rows)
    for i in range(n):
        p = rows[i]
        date = p[0]; op = float(p[1]); cl = float(p[2])
        prev = float(rows[i-1][2]) if i else op
        vol = float(p[5])
        gap = (op - prev) / prev * 100
        pct = (cl - prev) / prev * 100
        turn = vol / fh * 100 if fh else None
        # 涨停统计(当前连板高度): 往前数连续涨停
        boards = 0
        k = i
        while k >= 0:
            pk = float(rows[k-1][2]) if k else float(rows[k][1])
            if (float(rows[k][2]) - pk) / pk * 100 >= 9.9:
                boards += 1
                k -= 1
            else:
                break
        nxt = rows[i+1] if i + 1 < n else None
        note = ''
        if pct >= 9.9:
            note = '涨停'
        if nxt:
            nxt_prev = cl
            nxt_pct = (float(nxt[2]) - nxt_prev) / nxt_prev * 100
            note += '|次日%.1f%%' % nxt_pct
        out.append([date, code, name, op, round(gap, 2), None, None, None,
                    round(prev, 2), round(turn, 2) if turn else None, boards, note])
    return out

def live_snapshot(watch, retries=2):
    """实时抓竞价快照。返回要写入的行列表。瞬时失败自动重试。"""
    now = datetime.datetime.now()
    rows = []
    for code, (name, secid) in watch.items():
        tq = None
        for _a in range(retries + 1):
            tq = tencent_qt(code)
            if tq:
                break
            time.sleep(0.5)
        eq = em_qt(secid)
        qt = tq or {}
        gap = qt.get('gap')
        vol = qt.get('vol')
        prev = qt.get('prev')
        openp = qt.get('open')
        turn = qt.get('turn')
        amt = None
        fh = qt.get('float_hand')
        auc_turn = vol / fh * 100 if (vol and fh) else None
        if eq:
            if gap is None:
                gap = (eq['open'] - eq['prev']) / eq['prev'] * 100 if eq['prev'] else None
            if eq.get('amt'):
                amt = eq['amt']
            if eq.get('open') and not openp:
                openp = eq['open']
        note = 'LIVE9:25' if now.hour == 9 and now.minute < 30 else 'DEMO'
        rows.append([now.strftime('%Y-%m-%d'), code, name,
                     openp if openp else '', round(gap, 2) if gap is not None else '',
                     round(vol, 0) if vol else '', amt if amt else '',
                     round(auc_turn, 2) if auc_turn is not None else '',
                     round(prev, 2) if prev else '', turn if turn else '',
                     '', note])
    return rows

def main():
    ensure_out()
    mode = 'backfill' if '--backfill' in sys.argv else 'live'
    watch = load_watch()
    rows = []
    if mode == 'backfill':
        for code, (name, secid) in watch.items():
            rows.extend(backfill_daily(code, name, secid))
            time.sleep(1)
    else:
        rows = live_snapshot(watch)
    if not rows:
        print('no rows (watch empty or fetch fail)')
        return
    new = False
    existing = set()
    if os.path.exists(LOG):
        for r in csv.reader(open(LOG, encoding='utf-8')):
            if len(r) > 1:
                existing.add((r[0], r[1], r[4]))
    with open(LOG, 'a', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        for row in rows:
            key = (row[0], row[1], str(row[4]))
            if key in existing:
                continue
            w.writerow(row)
            existing.add(key)
            new = True
            print(','.join(str(x) for x in row))
    print('auction_sniffer[%s] done. rows written=%d  total in log=%d'
          % (mode, sum(1 for _ in rows), len(existing)))
    if mode == 'live':
        print('提示: 实时竞价需在交易日 9:15-9:30 调用; 其他时段为演示快照。')

def to_secid(code):
    """A股 code -> 东财 secid (SH 6/68->1., 其余->0.) 及腾讯前缀。"""
    if code.startswith(('6', '9')):
        return '1.' + code, 'sh' + code
    return '0.' + code, 'sz' + code

def update_watchlist(trade_date=None, keep_days=1):
    """从同花顺涨停池更新关注池: 5板以上妖股 + 低位(<=2板)涨停。
    trade_date: 'YYYYMMDD'。每日20:00由 daily_scan 调用，次日9:25捕捉竞价。
    返回写入文件的数量。"""
    sys.path.insert(0, BASE)
    try:
        import market_sentiment as ms
        if trade_date is None:
            trade_date = ms.find_last_trade_date(date.today())
        rows = ms.get_limit_up(trade_date)
    except Exception as e:
        print('update_watchlist err:', e)
        return 0
    if not rows:
        print('update_watchlist: %s 涨停池空(可能未收盘/未索引)' % trade_date)
        return 0
    yaogu = [r for r in rows if r.get('days', 0) >= 5]   # 5板以上妖股
    low = [r for r in rows if r.get('days', 0) <= 2]      # 低位首板/2板
    pool = yaogu + low[:50]                                # 低位封顶50只
    lines = ['# auto watchlist generated %s (auction_sniffer)' % trade_date]
    for r in pool:
        code = str(r.get('code', ''))
        if not code:
            continue
        name = r.get('name', code)
        secid, tcode = to_secid(code)
        tag = 'YAOGU%d' % r.get('days', 0) if r.get('days', 0) >= 5 else 'LOW'
        lines.append('%s,%s,%s,%s' % (tcode, name, secid, tag))
    # 始终保留三只参考票
    for code, (name, secid) in DEFAULT_WATCH.items():
        lines.append('%s,%s,%s,REF' % (code, name, secid))
    ensure_out()
    with open(WATCH, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    print('update_watchlist %s: 妖股%d 低位%d -> 写入 %s' % (trade_date, len(yaogu), len(low), WATCH))
    return len(lines)

if __name__ == '__main__':
    if '--update' in sys.argv:
        update_watchlist()
    else:
        main()
