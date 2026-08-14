# -*- coding: utf-8 -*-
"""Probe4: Tencent mkline m1 (auction bar?) + re-test eastmoney hosts"""
import requests, time
requests.packages.urllib3.disable_warnings()

def get(url, ref='https://gu.qq.com/'):
    try:
        r = requests.get(url, headers={'User-Agent':'Mozilla/5.0','Referer':ref}, timeout=12, verify=False)
        return r
    except Exception as e:
        return 'ERR:%s' % e

def show(label, r, keys):
    print('='*70)
    print(label)
    if isinstance(r, str): print('  ERR', r); return
    print('  HTTP', r.status_code, 'len', len(r.text))
    try:
        j = r.json()
    except Exception as e:
        print('  not json:', r.text[:150]); return
    print('  keys:', list(j.keys()) if isinstance(j, dict) else type(j))

if __name__ == '__main__':
    # Tencent 1-min mkline
    url = 'https://web.ifzq.gtimg.cn/appstock/app/kline/mkline?param=sh600664,m1,,,480'
    r = get(url)
    show('Tencent mkline m1 sh600664 (480 bars)', r, None)
    if not isinstance(r, str):
        try:
            d = r.json().get('data', {}).get('sh600664', {})
            for key in ('m1','qfqm1'):
                rows = d.get(key)
                if rows:
                    print('  key=%s %d rows' % (key, len(rows)))
                    print('  first3:', rows[:3])
                    print('  last3:', rows[-3:])
                    times = [x[0] for x in rows]
                    print('  times range:', times[0], '~', times[-1])
                    print('  dates:', sorted(set(t[:10] for t in times)))
                    auct = [x for x in rows if x[0][11:] in ('09:25','09:30','09:15')]
                    print('  auction-ish bars:', auct[:5])
        except Exception as e:
            print('  parse err', e)

    # Tencent today minute/query (first point?)
    url2 = 'https://web.ifzq.gtimg.cn/appstock/app/minute/query?code=sh600664'
    r2 = get(url2)
    show('Tencent minute/query sh600664 (today)', r2, None)
    if not isinstance(r2, str):
        try:
            d = r2.json().get('data', {}).get('sh600664', {})
            data = d.get('data', d.get('qfqmin', []))
            if data:
                print('  first:', data[0])
                print('  len:', len(data))
                # find 09:2x
                for x in data[:10]: print('   ', x)
        except Exception as e:
            print('  parse err', e)

    # eastmoney http variant + numbered host
    for u in ['http://push2his.eastmoney.com/api/qt/stock/kline/get?secid=1.600664&fields1=f1,f2,f3&fields2=f51,f52,f53&klt=101&fqt=0&lmt=5',
              'https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=1.600664&fields1=f1,f2,f3&fields2=f51,f52,f53&klt=101&fqt=0&lmt=5&cb=x']:
        r3 = get(u, 'https://quote.eastmoney.com/')
        show('eastmoney push2his retry: %s' % u.split('/api')[0], r3, None)
        time.sleep(1)
