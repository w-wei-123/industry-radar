# -*- coding: utf-8 -*-
"""Fetch real daily klines (Tencent, unadjusted) for 3 reference stocks; find limit-up streaks."""
import requests, time
requests.packages.urllib3.disable_warnings()
H = {'User-Agent':'Mozilla/5.0','Referer':'https://gu.qq.com/'}

def fetch_daily(code, label, lmt=90):
    url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=%s,day,,,%d,' % (code, lmt)
    r = requests.get(url, headers=H, timeout=15, verify=False)
    j = r.json()
    d = (j.get('data') or {}).get(code) or {}
    rows = d.get('day') or d.get('qfqday') or []
    out = []
    for p in rows:
        # [date, open, close, high, low, volume(手)]
        out.append({'date': p[0], 'open': float(p[1]), 'close': float(p[2]),
                    'high': float(p[3]), 'low': float(p[4]), 'vol': float(p[5])})
    return label, out

def tencent_float_shares(code):
    """流通股本(手) from qt.gtimg.cn realtime quote."""
    try:
        r = requests.get('https://qt.gtimg.cn/q=%s' % code, headers=H, timeout=10)
        r.encoding = 'gbk'
        parts = r.text.split('~')
        price = float(parts[3]) if len(parts) > 3 else 0
        # field with 流通市值 (亿元) - locate by trying known indexes
        for idx in range(len(parts)):
            try:
                v = float(parts[idx])
            except:
                continue
        # common: idx 38=总市值, idx 37=流通市值 (亿)
        if len(parts) > 38:
            fmv = float(parts[37])  # 流通市值 亿
            shares_hand = fmv * 1e8 / price / 100.0  # 手
            return shares_hand
    except Exception as e:
        print('   float_shares err:', e)
    return None

def analyze(code, label, recent_days=45):
    name, rows = fetch_daily(code, label, recent_days + 5)
    rows = rows[-recent_days:]
    print('='*80)
    print('%s 最近%d个交易日（不复权）' % (label, len(rows)))
    # detect limit-up runs (>=9.9%)
    n = len(rows)
    i = 0
    while i < n:
        if rows[i]['pct'] if 'pct' in rows[i] else False:
            i += 1
            continue
        # compute pct on the fly
        i += 1
    # recompute with pct
    for idx in range(len(rows)):
        prev = rows[idx-1]['close'] if idx > 0 else rows[idx]['open']
        rows[idx]['pct'] = (rows[idx]['close'] - prev) / prev * 100
        rows[idx]['gap'] = (rows[idx]['open'] - prev) / prev * 100  # 竞价涨幅
    # streaks
    i = 0
    while i < n:
        if rows[i]['pct'] >= 9.9:
            j = i
            while j+1 < n and rows[j+1]['pct'] >= 9.9:
                j += 1
            dur = j - i + 1
            print('  -- %d连板  %s ~ %s --' % (dur, rows[i]['date'], rows[j]['date']))
            for k in range(i, j+1):
                r = rows[k]
                nxt = rows[k+1] if k+1 < n else None
                nxt_txt = ('次日%s %+.2f%%(开%+.2f%%)' % (nxt['date'], nxt['pct'], nxt['gap'])) if nxt else '(未完)'
                # classify 涨停形态 by open gap
                if r['gap'] >= 9.5:
                    form = '一字板'
                elif r['gap'] >= 5:
                    form = '高开秒板'
                elif r['gap'] >= 1:
                    form = '高开换手'
                else:
                    form = '平开/低开换手'
                print('    %s 竞价%+.2f%%(开%.2f) 收%+.2f%% 量%.0f万手 %s | %s' % (
                    r['date'], r['gap'], r['open'], r['pct'], r['vol']/1e4, form, nxt_txt))
            i = j + 1
        else:
            i += 1

if __name__ == '__main__':
    analyze('sz001258', '立新能源(001258)', 45)
    time.sleep(1)
    analyze('sh600721', '百花医药(600721)', 45)
    time.sleep(1)
    analyze('sh600664', '哈药股份(600664)', 45)
