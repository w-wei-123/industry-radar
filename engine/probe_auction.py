# -*- coding: utf-8 -*-
"""Probe: can we get historical 9:25 auction volume from EastMoney?"""
import requests, json, sys
requests.packages.urllib3.disable_warnings()

def get(url, **kw):
    try:
        r = requests.get(url, headers={'User-Agent':'Mozilla/5.0','Referer':'https://quote.eastmoney.com/'}, timeout=15, verify=False, **kw)
        return r
    except Exception as e:
        return 'ERR:%s' % e

def probe_trends(secid, label):
    print('='*70)
    print('TRENDS2 %s' % label)
    for ndays in (1, 6):
        url = ('https://push2his.eastmoney.com/api/qt/stock/trends2/get?'
               'secid=%s&fields1=f1,f2,f3,f7,f8&fields2=f51,f52,f53,f54,f55,f56,f57,f58'
               '&ndays=%d&iscr=0&iscca=0' % (secid, ndays))
        r = get(url)
        if isinstance(r, str): print('  ERR', r); continue
        try:
            j = r.json()
            if not j or not j.get('data'):
                print('  ndays=%d -> no data' % ndays); continue
            d = j['data']
            trends = d.get('trends') or []
            print('  ndays=%d -> %d minute points, first=%s last=%s' % (ndays, len(trends), trends[0] if trends else '-', trends[-1] if trends else '-'))
            # check for auction times
            for t in trends[:8]:
                print('    ', t)
        except Exception as e:
            print('  parse err', e, r.text[:200])

def probe_daily(secid, label):
    print('='*70)
    print('DAILY KLINE %s' % label)
    # daily kline f51 date, f52 open f53 close f56 vol f58 turnover? fields: f5 vol, f6 amount, f8 turnover, f10 volratio
    url = ('https://push2his.eastmoney.com/api/qt/stock/kline/get?'
           'secid=%s&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&'
           'klt=101&fqt=0&end=20500101&lmt=40' % secid)
    r = get(url)
    if isinstance(r, str): print('  ERR', r); return
    try:
        j = r.json()
        kl = (j.get('data') or {}).get('klines') or []
        print('  %d days (date open close high low vol amt ...)' % len(kl))
        for line in kl[-15:]:
            print('   ', line)
    except Exception as e:
        print('  parse err', e)

if __name__ == '__main__':
    # 立新能源 001258 -> secid 0.001258
    probe_trends('0.001258', '立新能源 001258')
    probe_daily('0.001258', '立新能源 001258')
