#!/usr/bin/env python3
"""
行业雷达 · 每日扫描引擎
用法: python daily_scan.py
有异常 → 弹窗提醒 + 输出报告
无异常 → 静默更新日期
"""

import sys, io, json, time, random, urllib.request, subprocess, os
from datetime import date
from pathlib import Path

if not getattr(sys.stdout, 'encoding', '') or 'utf-8' not in (sys.stdout.encoding or '').lower():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
OUTPUT = Path(__file__).parent / "output"
OUTPUT.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# ── 前瞻事件扫描（导入）──
sys.path.insert(0, str(Path(__file__).parent))
import forward_events

# ── 配置 ──
WATCHLIST = {
    "半导体":       ["688981","002371","603501","688012","688072","002049","300661","688536"],
    "AI芯片":       ["688256","688041","603019","000977","688158","688047","688249"],
    "光通信/CPO":   ["300308","300502","300394","688498","002222","688313","300570"],
    "MLCC":         ["000636","300408","300285","603738","002859"],
    "PCB":          ["002463","002938","600183","603228","300476","002384"],
    "先进封装":     ["600584","002156","300604","688037","688120","688082","002409"],
    "人形机器人":   ["300124","688017","300024","601100","002472","688160","688322"],
    "低空经济":     ["000099","688297","002389","300690","688568","600760"],
    "商业航天":     ["688270","600118","688568","300342","688048","002025"],
    "固态电池":     ["300750","002709","002882","300450","300568","688567","688275"],
    "算电协同":     ["600406","002015","300750","002335","002837","300499","301162"],
    "6G/通信":      ["001270","002281","600498","688387","300308","688100"],
    "AI应用":       ["002230","688111","688787","300033","300624","688018"],
    "市场异动":     ["600519","300308","000636","603986","688256","002475","300476"],
}
ALERT_PCT = 7.0      # 单日涨超7%
ALERT_VOL = 3.0      # 量比>3
ALERT_TURN = 10.0    # 换手>10%

# ── 行情 ──
def tencent_quote(codes):
    prefixed = []
    for c in codes:
        if c.startswith(("6","9")): prefixed.append(f"sh{c}")
        elif c.startswith("8"): prefixed.append(f"bj{c}")
        else: prefixed.append(f"sz{c}")
    url = "https://qt.gtimg.cn/q=" + ",".join(prefixed)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    resp = urllib.request.urlopen(req, timeout=10)
    data = resp.read().decode("gbk")
    result = {}
    for line in data.strip().split(";"):
        if "=" not in line or '"' not in line: continue
        key = line.split("=")[0].split("_")[-1]
        vals = line.split('"')[1].split("~")
        if len(vals) < 53: continue
        code = key[2:]
        result[code] = {
            "name": vals[1], "price": float(vals[3]) if vals[3] else 0,
            "change_pct": float(vals[32]) if vals[32] else 0,
            "vol_ratio": float(vals[49]) if vals[49] else 0,
            "turnover_pct": float(vals[38]) if vals[38] else 0,
        }
    return result

# ── 桌面通知 ──
def toast(title, body):
    ps = f'''
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    $t = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
    $t.GetElementsByTagName("text")[0].AppendChild($t.CreateTextNode("{title}")) | Out-Null
    $t.GetElementsByTagName("text")[1].AppendChild($t.CreateTextNode("{body}")) | Out-Null
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("{title}").Show($t)
    '''
    try:
        subprocess.run(['powershell', '-Command', ps], capture_output=True, timeout=5)
    except:
        pass

# ── 自动触发 Serenity 挖掘 ──
def auto_hunt(alerts):
    """有异动→标记需要深挖的板块"""
    sectors_hit = set()
    for a in alerts:
        for s in a["sectors"]:
            if s != "市场异动":
                sectors_hit.add(s)
    if sectors_hit:
        print(f"  🧠 建议Serenity深挖: {' '.join(sectors_hit)}")
        print(f"     手动运行: python serenity_hunter.py <板块名>")

# ── 前瞻事件检查（日历 + 搜索清单，输出到控制台供 Claude 执行 WebSearch）──
def forward_event_report():
    lines = []
    today = date.today()
    events = forward_events.load_events()
    hits = forward_events.check_calendar(events, today)
    lines.append("## 前瞻事件日历")
    if hits:
        lines.append("")
        lines.extend("> " + h for h in hits)
    else:
        lines.append("- ✅ 未来3天内无已知事件")
    # 搜索清单写入单独文件，供每日扫描的 WebSearch 阶段使用
    search_lines = []
    for cat, queries in forward_events.SEARCH_TEMPLATES.items():
        search_lines.append(f"### {cat}")
        for q in queries:
            q = q.replace("{M}", str(today.month)).replace("{D}", str(today.day))
            search_lines.append(f"- {q}")
    return lines, search_lines

# ── 主流程 ──
def main():
    t0 = time.time()
    all_codes = list(set(sum(WATCHLIST.values(), [])))
    quotes = tencent_quote(all_codes)

    alerts = []
    for code in all_codes:
        q = quotes.get(code)
        if not q or q["price"] == 0: continue
        reasons = []
        if abs(q["change_pct"]) >= ALERT_PCT:
            d = "↑" if q["change_pct"] > 0 else "↓"
            reasons.append(f"单日{d}{abs(q['change_pct']):.1f}%")
        if q["vol_ratio"] >= ALERT_VOL:
            reasons.append(f"量比{q['vol_ratio']:.1f}")
        if q["turnover_pct"] >= ALERT_TURN:
            reasons.append(f"换手{q['turnover_pct']:.1f}%")
        if reasons:
            sectors = [s for s, codes in WATCHLIST.items() if code in codes]
            alerts.append({"code": code, "name": q["name"], "change": q["change_pct"], "reasons": reasons, "sectors": sectors})

    alerts.sort(key=lambda x: abs(x["change"]), reverse=True)

    # 输出
    today = date.today().isoformat()
    lines = [f"# 行业雷达扫描 {today}", "", f"## 异动 ({len(alerts)}个)", ""]
    for a in alerts[:20]:
        lines.append(f"- **{a['code']} {a['name']}**: {a['change']:+.1f}% | {' | '.join(a['reasons'])} | {'、'.join(a['sectors'][:2])}")
    if not alerts:
        lines.append("✅ 无异常信号")

    report = "\n".join(lines)

    # 市场情绪（涨停/炸板/连板/晋级率/赚钱效应/题材热度）
    try:
        import market_sentiment as ms
        _sdate = ms.find_last_trade_date(date.today())
        if _sdate:
            _s = ms.build_stats(_sdate)
            if _s:
                _emo = {'亢奋': '🔥', '活跃': '😄', '中性': '😐',
                        '低迷': '🥶', '冰点': '💀'}.get(_s['level'], '')
                report += f"\n\n## 市场情绪 {_emo} {_s['level']}（情绪分 {_s['score']}）\n"
                report += f"- 涨停 {_s['zt']} | 炸板 {_s['zb']}（炸板率 {_s['zbr']}%）| 跌停 {_s['dt']} | 最高 {_s['maxBoard']}板"
                _lad = ' → '.join(f"{b}板×{n}" for b, n in sorted(_s['ladder'].items()))
                report += f"\n- 连板天梯: {_lad}"
                if _s['ljRate'] is not None:
                    report += f"\n- 晋级率 {_s['ljRate']}% | 赚钱效应(昨日涨停今均) {_s['profit']}%"
                _rs = ' | '.join(f"{r}×{n}" for r, n in _s.get('reasons', [])[:5])
                if _rs:
                    report += f"\n- 题材热度: {_rs}"
    except Exception:
        pass

    # 龙虎榜资金动向（机构净买 / 净买 / 净卖警示）
    try:
        import lhb
        _ltd = lhb.find_last_trade_date(date.today())
        if _ltd:
            _lrows = lhb.get_lhb(_ltd)
            _seen = {}
            for _r in _lrows:
                _c = _r['code']
                if _c not in _seen or abs(_r['instNet']) > abs(_seen[_c]['instNet']):
                    _seen[_c] = _r
            _lrows = list(_seen.values())
            if _lrows:
                report += "\n\n## 龙虎榜资金动向\n"
                for _line in lhb.report_block(_lrows):
                    report += _line + "\n"
    except Exception:
        pass

    # 命中率复盘（龙虎榜alpha / 情绪分前瞻 / 事件待验证）
    try:
        import review
        _rlines = review.run(date.today())
        if _rlines:
            report += "\n".join(_rlines) + "\n"
    except Exception:
        pass

    # 前瞻事件：日历 + 搜索清单，先拼进报告再写盘
    event_lines, search_lines = forward_event_report()
    report += "\n\n" + "\n".join(event_lines) + "\n"
    (OUTPUT / "forward_search_checklist.md").write_text(
        "# 前瞻事件搜索清单\n\n" + "\n".join(search_lines), encoding="utf-8")

    (OUTPUT / "daily_alerts.md").write_text(report, encoding="utf-8")
    (OUTPUT / "scan_summary.json").write_text(json.dumps({"date": today, "alerts": len(alerts), "top": alerts[:10]}, ensure_ascii=False, indent=2), encoding="utf-8")

    # 竞价承接嗅探器: 涨停池(5板妖股+低位涨停)自动纳入次日9:25竞价观察池
    try:
        import auction_sniffer
        auction_sniffer.update_watchlist(today.strftime('%Y%m%d'))
    except Exception as _e:
        print(f"⚠️ auction watchlist 更新失败: {_e}")

    # 竞价承接·续板率统计: 涨停特征→次日续板概率, 样本每日累积写入 content/sectors/auction-stats.md
    try:
        import auction_stats
        auction_stats.main()
        print("📊 续板率统计已更新: content/sectors/auction-stats.md")
    except Exception as _e:
        print(f"⚠️ auction_stats 统计失败: {_e}")

    # 弹窗
    if len(alerts) >= 5:
        toast("行业雷达", f"今日{len(alerts)}个异动信号\n{alerts[0]['name']}({alerts[0]['code']}) {alerts[0]['change']:+.1f}%")

    # 异动→自动Serenity深挖
    if len(alerts) >= 5:
        auto_hunt(alerts)

    if search_lines:
        print(f"🔭 前瞻清单已生成: engine/output/forward_search_checklist.md")

    elapsed = time.time() - t0
    print(f"扫描完成: {len(alerts)}个异动 | {elapsed:.1f}s | {today}")

if __name__ == "__main__":
    main()
