# -*- coding: utf-8 -*-
"""Probe5: inspect Tencent today-minute structure for 09:25 auction; get float shares from EM realtime"""
import requests, json, time
requests.packages.urllib3.disable_warnings()

def get(url, ref='https://gu.qq.com/'):
    try:
        r = requests.get(url, headers={'User-Agent':'Mozilla/5.0','Referer':ref}, timeout=12, verify=False)
        return r
    except Exception as e:
        return 'ERR:%s' % e

# 1. Tencent today minute structure
r = get('https://web.ifzq.gtimg.cn/appstock/app/minute/query?code=sh600664')
if not isinstance(r, str):
    try:
        raw = r.json()
        d = raw['data']['sh600664']
        print('keys of sh600664:', list(d.keys()))
        rows = d.get('data')
        if rows:
            print('first5:', rows[:5])
            print('len:', len(rows))
            times = [x[0] for x in rows]
            print('times start:', times[:3], '... end:', times[-1])
    except Exception as e:
        print('minute parse err', e, r.text[:200])

# 2. EastMoney realtime for float shares (f117 float mktcap, f43 price, f168 turnover)
print('='*70)
for secid, label in [('0.001258','立新能源'), ('1.600664','哈药股份'), ('1.600721','百花医药')]:
    url = ('https://push2.eastmoney.com/api/qt/stock/get?secid=%s'
           '&fields=f57,f58,f43,f46,f47,f168,f116,f117' % secid)
    r = get(url, 'https://quote.eastmoney.com/')
    if isinstance(r, str): print(label, 'ERR', r); continue
    try:
        d = r.json()['data']
        price = d.get('f43', 0) / 100.0
        fvol = d.get('f117', 0)  # 流通市值 (元)
        float_shares = fvol / price if price else 0  # 流通股本(股)
        print('%s %s 现价%.2f 流通市值%.1f亿 流通股本约%.2f亿股 换手率%.2f%%' % (
            label, d.get('f58'), price, fvol/1e8, float_shares/1e8, d.get('f168',0)/100.0))
    except Exception as e:
        print(label, 'parse err', e)
    time.sleep(1)

# 3. retry eastmoney push2his once, single request
print('='*70)
print('eastmoney push2his retry (single):')
r = get('https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=1.600664&fields1=f1,f2,f3&fields2=f51,f52,f53&klt=101&fqt=0&lmt=5', 'https://quote.eastmoney.com/')
print('  HTTP', r.status_code if not isinstance(r, str) else r, (len(r.text) if not isinstance(r, str) else ''))
