# -*- coding: utf-8 -*-
"""Probe2: Tencent m1 / Sina 1min for auction bar"""
import requests, json
requests.packages.urllib3.disable_warnings()
H = {'User-Agent':'Mozilla/5.0','Referer':'https://gu.qq.com/'}

def get(url):
    try:
        r = requests.get(url, headers=H, timeout=15, verify=False)
        return r
    except Exception as e:
        return 'ERR:%s' % e

def probe_tencent_m1(code, label):
    print('='*70)
    print('TENCENT m1 %s' % label)
    url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=%s,m1,,,640,qfq' % code
    r = get(url)
    if isinstance(r, str): print('  ERR', r); return
    try:
        j = r.json()
        d = (j.get('data') or {}).get(code) or {}
        # m1 data key could be 'm1' or 'qfqm1'
        for key in ('m1','qfqm1'):
            rows = d.get(key) or []
            if rows:
                print('  key=%s %d bars' % (key, len(rows)))
                # each row: [time, open, close, high, low, vol, ...]
                times = [row[0] for row in rows]
                print('  first3:', rows[:3])
                print('  last3:', rows[-3:])
                # find 09:25 bars
                auct = [row for row in rows if row[0][11:] in ('09:25','09:15','09:30')]
                for a in auct[:6]: print('   A:', a)
                # unique dates
                dates = sorted(set(t[:10] for t in times))
                print('  dates:', dates[-8:])
                return
        print('  no m1 rows; keys=', list(d.keys())[:10])
    except Exception as e:
        print('  parse err', e, str(j)[:200] if 'j' in dir() else r.text[:200])

def probe_sina_1min(symbol, label):
    print('='*70)
    print('SINA 1min %s' % label)
    url = ('https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData'
           '?symbol=%s&scale=1&ma=no&datalen=400') % symbol
    r = get(url)
    if isinstance(r, str): print('  ERR', r); return
    try:
        j = r.json()
        print('  %d bars' % len(j))
        print('  first:', j[0] if j else '-')
        print('  last:', j[-1] if j else '-')
        times = [x['day'] for x in j]
        auct = [x for x in j if '09:2' in x['day'] or '09:3' in x['day']][:6]
        for a in auct[:6]: print('   A:', a)
        dates = sorted(set(t[:10] for t in times))
        print('  dates:', dates[-6:])
    except Exception as e:
        print('  parse err', e, r.text[:200])

if __name__ == '__main__':
    probe_tencent_m1('sz001258', '立新能源 001258')
    probe_sina_1min('sz001258', '立新能源 001258')
