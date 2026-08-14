# -*- coding: utf-8 -*-
"""Full reference table: 竞价涨幅 + 全天换手率 (Tencent float shares) for 3 妖股."""
import requests, time
requests.packages.urllib3.disable_warnings()
H = {'User-Agent':'Mozilla/5.0','Referer':'https://gu.qq.com/'}

def fetch_daily(code, lmt=90):
    url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=%s,day,,,%d,' % (code, lmt)
    j = requests.get(url, headers=H, timeout=15).json()
    d = (j.get('data') or {}).get(code) or {}
    rows = d.get('day') or d.get('qfqday') or []
    out = []
    for p in rows:
        out.append({'date': p[0], 'open': float(p[1]), 'close': float(p[2]),
                    'high': float(p[3]), 'low': float(p[4]), 'vol': float(p[5])})
    return out

def float_hand(code):
    """流通股本(手) via Tencent qt.gtimg.cn."""
    try:
        r = requests.get('https://qt.gtimg.cn/q=%s' % code, headers=H, timeout=10)
        r.encoding = 'gbk'
        parts = r.text.split('~')
        price = float(parts[3])
        fmv_yi = float(parts[44])   # 流通市值 亿元 (Tencent qt 0-based idx 44)
        return fmv_yi * 1e8 / price / 100.0  # 手
    except Exception as e:
        print('   float err', e)
        return None

def report(code, label, days=45):
    rows = fetch_daily(code, days + 5)[-days:]
    fh = float_hand(code)
    n = len(rows)
    for i in range(n):
        prev = rows[i-1]['close'] if i else rows[i]['open']
        rows[i]['pct'] = (rows[i]['close'] - prev) / prev * 100
        rows[i]['gap'] = (rows[i]['open'] - prev) / prev * 100
        rows[i]['turn'] = rows[i]['vol'] / fh * 100 if fh else 0
    print('='*88)
    print('%s (流通股本约%.2f亿股)' % (label, fh/1e6 if fh else 0))
    i = 0
    while i < n:
        if rows[i]['pct'] >= 9.9:
            j = i
            while j+1 < n and rows[j+1]['pct'] >= 9.9: j += 1
            print('  ── %d连板 %s~%s ──' % (j-i+1, rows[i]['date'], rows[j]['date']))
            for k in range(i, j+1):
                r = rows[k]
                nxt = rows[k+1] if k+1 < n else None
                nxt_txt = ('次日%s %+.2f%% 开%+.2f%%' % (nxt['date'], nxt['pct'], nxt['gap'])) if nxt else '(未完)'
                form = '一字' if r['gap']>=9.5 else ('高开秒' if r['gap']>=5 else ('高开换手' if r['gap']>=1 else '平/低开换手'))
                print('    %s | 竞价%+.2f%% | 收%+.2f%% | 全天换手%.1f%% | %s | %s' % (
                    r['date'], r['gap'], r['pct'], r['turn'], form, nxt_txt))
            i = j + 1
        else:
            i += 1
    # tail for 哈药 (non-limit last days)
    if code == 'sh600664':
        print('  尾段明细:')
        for r in rows[-6:]:
            print('    %s 开%.2f 收%.2f %+.2f%% 换手%.1f%%' % (r['date'], r['open'], r['close'], r['pct'], r['turn']))

if __name__ == '__main__':
    report('sz001258', '立新能源(001258)')
    time.sleep(1)
    report('sh600721', '百花医药(600721)')
    time.sleep(1)
    report('sh600664', '哈药股份(600664)')
