#!/usr/bin/env python3
"""
妖股候选池筛选器 · 7条基因打分
每天自动扫出符合妖股启动前特征的票，标出"故事新/盘小/筹码集中"打分。

7条基因：
  1. 故事新     - 板块/概念是近期新热点（来自涨停池板块分布）
  2. 盘小       - 流通市值 < 40亿 加分多，<60亿 加分少
  3. 股价低     - 启动前股价 < 15元
  4. 首板换手   - 换手 5-15%（不高不低，有资金关注但没充分换手）
  5. 封板坚决   - 开板次数少 + 封单量大 + 封板早
  6. 连板结构   - 1-3板（启动初期），4板以上风险增大
  7. 板块共振   - 同板块多只涨停（题材扩散）

用法:
  python yaogu_hunter.py [日期]             # 正常打分筛选
  python yaogu_hunter.py --mark-risk 002963 "证监会调查+连续亏损"  # 标记雷股
  python yaogu_hunter.py --risk-list        # 查看当前雷股黑名单
日期格式: 20260811，默认今天（取最近交易日）
"""
import sys
import io
import json
import os
import urllib.request
from datetime import date, timedelta
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

UA = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://quote.eastmoney.com/'}

# 雷股黑名单（监管调查/重大亏损/退市风险），经13-Agent验证后人工标记
RISK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'risk_blacklist.json')
RISK_PENALTY = -30   # 被标记雷股的总分惩罚
# 黑名单按代码存（不受名称变更影响），格式: {"code": {"name":..., "reason":..., "date":...}}

def load_blacklist():
    if os.path.exists(RISK_FILE):
        with open(RISK_FILE, encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_blacklist(b):
    with open(RISK_FILE, 'w', encoding='utf-8') as f:
        json.dump(b, f, ensure_ascii=False, indent=2)

def fetch_json(url):
    req = urllib.request.Request(url, headers=UA)
    raw = urllib.request.urlopen(req, timeout=20).read().decode()
    return json.loads(raw)

def get_limit_up_pool(trade_date):
    """获取涨停池（含连板天数/换手/市值/开板/封板时间）"""
    url = (f'https://push2ex.eastmoney.com/getTopicZTPool?ut=7eea3edcaed734bea9cbfc24409ed989'
           f'&dpt=wz.ztzt&Pageindex=0&pagesize=300&sort=fbt%3Aasc&date={trade_date}&_=1')
    d = fetch_json(url)
    if not d.get('data') or not d['data'].get('pool'):
        return []
    return d['data']['pool']

def get_lb_pool(trade_date):
    """获取连板池"""
    url = (f'https://push2ex.eastmoney.com/getTopicLbPool?ut=7eea3edcaed734bea9cbfc24409ed989'
           f'&dpt=wz.ztzt&Pageindex=0&pagesize=300&sort=zbc%3Aasc&date={trade_date}&_=1')
    try:
        d = fetch_json(url)
        if d.get('data') and d['data'].get('pool'):
            return d['data']['pool']
    except Exception:
        pass
    return []

def score_stock(p, sector_hot, blacklist=None):
    """对单只涨停票按7条基因打分"""
    score = 0
    reasons = []
    blacklist = blacklist or {}

    # 基因0: 雷股惩罚（监管调查/重大亏损，经13-Agent验证标记）
    code = p.get('c', '')
    if code in blacklist:
        bl = blacklist[code]
        score += RISK_PENALTY
        reasons.append(f"⚠️雷股-30({bl.get('reason','')})")

    lbc = p.get('lbc', 1)          # 连板天数
    hs = p.get('hs', 0)            # 换手率
    ltsz = p.get('ltsz', 0)        # 流通市值(元)
    zbc = p.get('zbc', 0)          # 开板次数
    fund = p.get('fund', 0)        # 封单金额(元)
    fbt = p.get('fbt', 0)          # 首次封板时间(93000格式)
    hybk = p.get('hybk', '')       # 所属板块
    price = p.get('p', 0) / 1000 if p.get('p', 0) > 100 else p.get('p', 0)  # 价格（分转元）

    # 基因2: 盘小
    ltsz_yi = ltsz / 1e8
    if ltsz_yi < 25:
        score += 25; reasons.append(f"流通{int(ltsz_yi)}亿(极小)")
    elif ltsz_yi < 40:
        score += 20; reasons.append(f"流通{int(ltsz_yi)}亿(小)")
    elif ltsz_yi < 60:
        score += 10; reasons.append(f"流通{int(ltsz_yi)}亿(中小)")
    else:
        reasons.append(f"流通{int(ltsz_yi)}亿(大)")

    # 基因3: 股价低
    if price and price < 10:
        score += 10; reasons.append(f"股价{price:.1f}元(低)")
    elif price and price < 15:
        score += 6; reasons.append(f"股价{price:.1f}元(中低)")
    elif price and price < 25:
        score += 2; reasons.append(f"股价{price:.1f}元(中)")
    else:
        reasons.append(f"股价{price:.1f}元(高)")

    # 基因4: 首板换手适中（5-15%最佳）
    if 5 <= hs <= 15:
        score += 15; reasons.append(f"换手{hs:.1f}%(理想)")
    elif 2 <= hs < 5:
        score += 8; reasons.append(f"换手{hs:.1f}%(偏低锁筹)")
    elif 15 < hs <= 25:
        score += 5; reasons.append(f"换手{hs:.1f}%(偏高)")
    else:
        reasons.append(f"换手{hs:.1f}%(异常)")

    # 基因5: 封板坚决
    if zbc == 0:
        score += 10; reasons.append("开板0次(坚决)")
    elif zbc <= 2:
        score += 6; reasons.append(f"开板{zbc}次(尚可)")
    elif zbc <= 5:
        score += 3; reasons.append(f"开板{zbc}次(松动)")
    else:
        reasons.append(f"开板{zbc}次(炸板)")

    if fund > 0:
        fund_ratio = fund / ltsz * 100 if ltsz else 0
        if fund_ratio > 5:
            score += 8; reasons.append(f"封单占流通{fund_ratio:.1f}%(强)")
        elif fund_ratio > 2:
            score += 5; reasons.append(f"封单占流通{fund_ratio:.1f}%(中)")
        else:
            score += 2; reasons.append(f"封单占流通{fund_ratio:.1f}%(弱)")

    # 基因6: 连板结构（1-3板最优）
    if lbc == 1:
        score += 5; reasons.append("首板")
    elif lbc == 2:
        score += 8; reasons.append("2板(接力)")
    elif lbc == 3:
        score += 5; reasons.append("3板")
    elif lbc >= 4:
        score -= 10; reasons.append(f"{lbc}板(高位!)")

    # 基因1: 故事新 - 板块热度
    hot = sector_hot.get(hybk, 0)
    if hot >= 3:
        score += 12; reasons.append(f"板块[{hybk}]热度{hot}")
    elif hot == 2:
        score += 7; reasons.append(f"板块[{hybk}]热度{hot}")
    elif hot == 1:
        score += 3; reasons.append(f"板块[{hybk}]热度{hot}")
    else:
        reasons.append(f"板块[{hybk}]独苗")

    # 基因7b: 独立催化判断——独苗且高连板 = 独立逻辑龙头（真妖股），
    # 跟风板块普涨 = 弱势（资金搭车，接力确定性差）
    if hot <= 1 and lbc >= 2:
        score += 6; reasons.append("独苗+高连板=独立逻辑龙头")
    elif hot >= 3 and lbc == 1:
        score -= 3; reasons.append("板块普涨首板=跟风(确定性差)")

    return score, reasons

def main():
    blacklist = load_blacklist()

    # ── 命令行模式 ──
    if len(sys.argv) > 1 and sys.argv[1] == '--mark-risk':
        if len(sys.argv) < 3:
            print("用法: python yaogu_hunter.py --mark-risk 002963 \"证监会调查+连续亏损\"")
            return
        code = sys.argv[2]
        reason = sys.argv[3] if len(sys.argv) > 3 else "监管调查/重大风险"
        blacklist[code] = {"reason": reason, "date": date.today().isoformat()}
        save_blacklist(blacklist)
        print(f"✅ 已标记雷股 {code}: {reason}（总分惩罚-30）")
        return

    if len(sys.argv) > 1 and sys.argv[1] == '--risk-list':
        if not blacklist:
            print("📋 雷股黑名单为空——使用 --mark-risk <代码> <原因> 添加")
        else:
            print(f"📋 雷股黑名单（{len(blacklist)}只）：")
            for code, info in blacklist.items():
                print(f"  ⚠️ {code} {info.get('name','')}: {info.get('reason','')} (标记于{info.get('date','')})")
        return

    # ── 正常打分模式 ──
    # 确定目标日期：默认今天，若非交易日往前找（最多7天）
    if len(sys.argv) > 1:
        target = sys.argv[1]
        pool = get_limit_up_pool(target)
    else:
        pool = []
        target = None
        for i in range(0, 8):
            d = date.today() - timedelta(days=i)
            t = d.strftime('%Y%m%d')
            pool = get_limit_up_pool(t)
            if pool:
                target = t
                break
    print(f"📅 目标交易日: {target}\n")

    if not pool:
        print("⚠️ 未获取到涨停池数据（可能非交易日或接口变动）")
        return

    print(f"当日涨停: {len(pool)}只")

    # 板块热度统计
    sector_hot = Counter(p.get('hybk', '') for p in pool)
    print("板块热度TOP10:", ', '.join(f"{k}({v})" for k, v in sector_hot.most_common(10)))

    # 打分排序
    scored = []
    for p in pool:
        s, reasons = score_stock(p, sector_hot, blacklist)
        scored.append((s, p, reasons))
    scored.sort(key=lambda x: -x[0])

    print("\n" + "=" * 70)
    print("🏆 妖股候选池 TOP20（按基因打分）")
    print("=" * 70)
    for i, (s, p, reasons) in enumerate(scored[:20], 1):
        name = p.get('n', '')
        code = p.get('c', '')
        lbc = p.get('lbc', 1)
        hybk = p.get('hybk', '')
        marker = '🔥' if s >= 65 else ('⭐' if s >= 45 else '')
        print(f"\n{i}. {marker} {name}({code}) 总分{s}")
        print(f"   {' | '.join(reasons)}")

    # ── 连板高度榜（3板以上单独列出，不因"高位减分"被埋没）──
    high_boards = sorted([p for p in pool if p.get('lbc', 1) >= 3],
                         key=lambda x: -x.get('lbc', 1))
    if high_boards:
        print("\n" + "=" * 70)
        print("🚀 连板高度榜（3板+，独立显示——高位妖股另一套逻辑）")
        print("=" * 70)
        for p in high_boards:
            name = p.get('n', ''); code = p.get('c', '')
            lbc = p.get('lbc', 1); hybk = p.get('hybk', '')
            bl = " ⚠️雷股" if code in blacklist else ""
            print(f"  {lbc}板 {name}({code}) [{hybk}]{bl}")
        print("  ⚠️ 高度板已从候选池减分，此处仅作行情跟踪——4板+接力风险极高")

    print("\n" + "=" * 70)
    print("📊 解读：总分65+ = 强妖股候选，45-65 = 关注，<45 = 观察")
    print("💡 打分会经过13-Agent流水线二次验证，雷股标记: --mark-risk <代码> <原因>")
    print("⚠️ 本工具仅做概率筛选，不构成投资建议。妖股是幸存者偏差，请理性看待。")

if __name__ == '__main__':
    main()
