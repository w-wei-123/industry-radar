#!/usr/bin/env python3
"""
市场情绪量化 · 打板情绪温度计
================================
每日收盘后计算短线情绪指标，判断市场热度周期（决定该进攻还是防守）：

  ◆ 温度指标    涨停家数 / 炸板数 / 炸板率 / 跌停数 / 最高连板
  ◆ 结构指标    连板天梯（2板/3板/4板…）/ 梯队断层 / 涨停题材归因 Top
  ◆ 赚钱效应    晋级率（昨日涨停今日再涨停）/ 昨日涨停今日平均涨幅
  ◆ 情绪分      （0-100 加权合成）→ 情绪周期分级
                 ≥70 亢奋 · 55-70 活跃 · 40-55 中性 · 25-40 低迷 · <25 冰点

数据源：
  涨停池    → 同花顺 limit_up_pool（支持历史日期，含连板数/涨停题材）
  炸板/跌停 → 东财 getTopicZBPool / getTopicDTPool

历史写入 engine/output/sentiment_history.json（保留近20日）。

用法:
  python market_sentiment.py            # 自动定位最近交易日
  python market_sentiment.py 20260813   # 指定日期
"""
import sys
import io
import json
import time
import urllib.request
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import List, Dict, Optional

if not getattr(sys.stdout, 'encoding', '') or 'utf-8' not in (sys.stdout.encoding or '').lower():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ENGINE = Path(__file__).parent
OUTPUT = ENGINE / "output"
OUTPUT.mkdir(parents=True, exist_ok=True)
HISTORY_FILE = OUTPUT / "sentiment_history.json"

THS_UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
          'Referer': 'http://data.10jqka.com.cn/'}
EM_UA = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://quote.eastmoney.com/'}
UT = '7eea3edcaed734bea9cbfc24409ed989'
THS_URL = ('http://data.10jqka.com.cn/dataapi/limit_up/limit_up_pool?page=1&limit=200'
           '&field=199112,10,9001,330323,330324,330325,9002,330329,133971,133970,1968584'
           '&filter=HS,GEM2STAR&order_field=330324&order_type=0&date=')


def fetch_json(url: str, ua: dict) -> dict:
    req = urllib.request.Request(url, headers=ua)
    return json.loads(urllib.request.urlopen(req, timeout=12).read().decode('utf-8', errors='replace'))


def get_limit_up(trade_date: str) -> List[dict]:
    """同花顺涨停池（支持历史日期）→ [{code,name,days,again,reason,turn,openNum}]"""
    try:
        j = fetch_json(THS_URL + trade_date, THS_UA)
        info = ((j.get('data') or {}).get('info')) or []
    except Exception:
        return []
    out = []
    for it in info:
        days = None
        # 优先解析 "2天2板" 文本
        m = re.match(r'(\d+)天(\d+)板', str(it.get('high_days', '')))
        if m:
            days = int(m.group(2))
        # 兜底：high_days_value 是位编码（低16位=连板数）
        if days is None:
            hv = it.get('high_days_value')
            if isinstance(hv, int) and hv > 0:
                days = hv & 0xffff
        if days is None:
            days = 1 if not it.get('is_again_limit') else 2
        out.append({
            'code': str(it.get('code', '')),
            'name': str(it.get('name', '')),
            'days': int(days or 1),
            'again': int(it.get('is_again_limit', 0) or 0),
            'reason': str(it.get('reason_type', '')),
            'turn': float(it.get('turnover_rate', 0) or 0),
            'openNum': int(it.get('open_num', 0) or 0),
        })
    return out


def get_pool(trade_date: str, kind: str) -> List[dict]:
    """拉取池子。kind: ZTPool=同花顺涨停 | ZBPool/DTPool=东财炸板/跌停"""
    if kind == 'ZTPool':
        return get_limit_up(trade_date)
    sort = 'fund%3Aasc' if kind == 'DTPool' else 'fbt%3Aasc'
    url = (f'https://push2ex.eastmoney.com/getTopic{kind}?ut={UT}&dpt=wz.ztzt'
           f'&Pageindex=0&pagesize=400&sort={sort}&date={trade_date}')
    try:
        j = fetch_json(url, EM_UA)
        data = j.get('data') or {}
        qdate = str(data.get('qdate', ''))
        pool = data.get('pool') or []
        if qdate and qdate != trade_date:
            return []  # 东财返回了其他日期数据（请求日期未开盘/非交易日）
        return pool
    except Exception:
        return []


def find_last_trade_date(anchor: date, back_days: int = 8) -> Optional[str]:
    """从 anchor 往回找最近有涨停数据的交易日（同花顺 date 参数真实有效）"""
    for i in range(back_days):
        d = anchor - timedelta(days=i)
        if get_limit_up(d.strftime('%Y%m%d')):
            return d.strftime('%Y%m%d')
    return None


def tencent_pct(codes: List[str]) -> Dict[str, float]:
    """腾讯行情批量查昨日涨停股今日涨跌幅（GBK）"""
    if not codes:
        return {}
    result = {}
    for i in range(0, len(codes), 50):
        batch = codes[i:i + 50]
        pref = [(('sh' if c[0] in '6' else 'sz') + c) for c in batch]
        url = 'http://qt.gtimg.cn/q=' + ','.join(pref)
        try:
            req = urllib.request.Request(url)
            raw = urllib.request.urlopen(req, timeout=10).read().decode('gbk', errors='replace')
            for line in raw.split(';'):
                m = re.search(r'^v_(\w+)="([^"]*)"', line.strip())
                if m:
                    code = m.group(1)[2:]
                    f = m.group(2).split('~')
                    if len(f) > 32 and f[32]:
                        result[code] = float(f[32])
        except Exception:
            continue
    return result


def top_reasons(stocks: List[dict], topn: int = 6) -> List[tuple]:
    """涨停题材归因 Top（reason_type 按 '+' 拆分聚合）"""
    c = Counter()
    for s in stocks:
        for r in s['reason'].replace('+', ' ').split():
            r = r.strip()
            if r and r != '涨停':
                c[r] += 1
    return c.most_common(topn)


def build_stats(trade_date: str) -> Optional[Dict]:
    today_zt = get_limit_up(trade_date)
    if not today_zt:
        return None
    today_zb = get_pool(trade_date, 'ZBPool')
    today_dt = get_pool(trade_date, 'DTPool')

    zt_n = len(today_zt)
    zb_n = len(today_zb)
    dt_n = len(today_dt)
    zbr = round(zb_n / (zt_n + zb_n) * 100, 1) if (zt_n + zb_n) else 0

    # 连板天梯
    ladder = {}
    for p in today_zt:
        ladder[p['days']] = ladder.get(p['days'], 0) + 1
    max_board = max(ladder.keys()) if ladder else 0
    gap = None
    for b in range(2, max_board):
        if ladder.get(b, 0) == 0:
            gap = b
            break

    # 晋级率 / 赚钱效应（昨日涨停池）
    d = date(int(trade_date[:4]), int(trade_date[4:6]), int(trade_date[6:8]))
    prev_date = find_last_trade_date(d - timedelta(days=1))
    lj_rate = None
    profit = None
    if prev_date:
        prev_zt = get_limit_up(prev_date)
        if prev_zt:
            prev_codes = [p['code'] for p in prev_zt]
            today_codes = {p['code'] for p in today_zt}
            promos = [c for c in prev_codes if c in today_codes]
            lj_rate = round(len(promos) / len(prev_codes) * 100, 1)
            pct_map = tencent_pct(prev_codes)
            if pct_map:
                profit = round(sum(pct_map.values()) / len(pct_map), 2)

    score = sentiment_score(zt_n, zbr, lj_rate, profit, max_board)
    return {
        'date': trade_date, 'zt': zt_n, 'zb': zb_n, 'dt': dt_n, 'zbr': zbr,
        'ladder': ladder, 'maxBoard': max_board, 'gap': gap,
        'ljRate': lj_rate, 'profit': profit, 'score': score,
        'level': level_of(score), 'reasons': top_reasons(today_zt),
    }


def sentiment_score(zt: int, zbr: float, lj_rate: Optional[float],
                    profit: Optional[float], max_board: int) -> int:
    score = 20  # 基分
    score += min(30, zt * 0.5)                      # 涨停家数（60家封顶30分）
    if zbr < 15:
        score += 25
    elif zbr < 25:
        score += 20
    elif zbr < 40:
        score += 12
    elif zbr < 55:
        score += 5
    elif zbr < 70:
        score -= 5
    else:
        score -= 15
    if lj_rate is not None:
        if lj_rate >= 45:
            score += 20
        elif lj_rate >= 30:
            score += 15
        elif lj_rate >= 20:
            score += 8
        elif lj_rate >= 10:
            score += 0
        else:
            score -= 8
    if profit is not None:
        if profit >= 6:
            score += 20
        elif profit >= 3:
            score += 15
        elif profit >= 1:
            score += 8
        elif profit >= 0:
            score += 0
        else:
            score -= 10
    if max_board >= 7:
        score += 12
    elif max_board >= 5:
        score += 10
    elif max_board == 4:
        score += 7
    elif max_board == 3:
        score += 4
    elif max_board == 2:
        score += 2
    return max(0, min(100, int(round(score))))


def level_of(score: int) -> str:
    if score >= 70:
        return '亢奋'
    if score >= 55:
        return '活跃'
    if score >= 40:
        return '中性'
    if score >= 25:
        return '低迷'
    return '冰点'


def load_history() -> List[Dict]:
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding='utf-8'))
        except Exception:
            return []
    return []


def save_history(stats: Dict):
    hist = load_history()
    hist = [h for h in hist if h.get('date') != stats['date']]
    hist.append({'date': stats['date'], 'score': stats['score'],
                 'level': stats['level'], 'zt': stats['zt'],
                 'zbr': stats['zbr'], 'ljRate': stats['ljRate'],
                 'maxBoard': stats['maxBoard']})
    hist = hist[-20:]
    HISTORY_FILE.write_text(json.dumps(hist, ensure_ascii=False, indent=2), encoding='utf-8')


def print_report(stats: Dict):
    s = stats
    emoji = {'亢奋': '🔥', '活跃': '😄', '中性': '😐', '低迷': '🥶', '冰点': '💀'}[s['level']]
    print(f"📊 市场情绪（{s['date']}）情绪分 {s['score']} {emoji}【{s['level']}】")
    print(f"   涨停 {s['zt']} | 炸板 {s['zb']} (炸板率 {s['zbr']}%) | 跌停 {s['dt']}")
    ladder = ' → '.join(f'{b}板×{n}' for b, n in sorted(s['ladder'].items())) or '无连板'
    print(f"   连板天梯: {ladder} | 最高 {s['maxBoard']} 板"
          + (f" | ⚠️ {s['gap']}板断层" if s['gap'] else ""))
    if s['ljRate'] is not None:
        print(f"   晋级率 {s['ljRate']}% | 赚钱效应(昨日涨停今均) {s['profit']}%")
    else:
        print("   昨日涨停数据缺失，晋级率/赚钱效应 N/A")
    reasons = ' | '.join(f'{r}×{n}' for r, n in s['reasons']) or '无'
    print(f"   题材热度: {reasons}")
    hist = load_history()
    if len(hist) >= 2:
        trend = ' '.join(f"{h['date'][4:6]}/{h['date'][6:]}:{h['score']}" for h in hist[-10:])
        print(f"   近{len(hist)}日情绪分: {trend}")


def main():
    anchor = date.today()
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        anchor = date(int(arg[:4]), int(arg[4:6]), int(arg[6:8]))
    td = find_last_trade_date(anchor)
    if not td:
        print("❌ 最近8日无涨停数据（可能接口异常或长期休市）")
        return
    stats = build_stats(td)
    if not stats:
        print(f"❌ {td} 无涨停数据")
        return
    (OUTPUT / "market_sentiment.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding='utf-8')
    save_history(stats)
    print_report(stats)


if __name__ == '__main__':
    main()
