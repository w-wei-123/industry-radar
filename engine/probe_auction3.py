# -*- coding: utf-8 -*-
"""Probe3: 10jqka historical minute / auction"""
import requests
requests.packages.urllib3.disable_warnings()
H = {'User-Agent':'Mozilla/5.0','Referer':'http://stockpage.10jqka.com.cn/001258/'}

def get(url):
    try:
        r = requests.get(url, headers=H, timeout=15, verify=False)
        return r
    except Exception as e:
        return 'ERR:%s' % e

def probe(url, label):
    print('='*70)
    print(label)
    print('URL:', url)
    r = get(url)
    if isinstance(r, str): print('  ERR', r); return
    print('  status', r.status_code, 'len', len(r.text))
    print('  head:', r.text[:300].replace('\n',' | '))

if __name__ == '__main__':
    # 同花顺实时1分钟
    probe('http://d.10jqka.com.cn/v6/line/hs_001258/09/last.js', '10jqka current 1min (hs_001258/09)')
    # 同花顺历史分时 time (by date)
    probe('http://d.10jqka.com.cn/v6/time/hs_001258/2026-08-11.js', '10jqka historical time 2026-08-11')
    # 东财 realtime quote fields
    probe('https://push2.eastmoney.com/api/qt/stock/get?secid=0.001258&fields=f43,f44,f45,f46,f47,f48,f50,f57,f58,f60,f107,f116,f117,f168,f169,f170,f171,f62',
          'EastMoney realtime quote fields')
