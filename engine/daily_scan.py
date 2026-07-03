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

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
OUTPUT = Path(__file__).parent / "output"
OUTPUT.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

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
    (OUTPUT / "daily_alerts.md").write_text(report, encoding="utf-8")
    (OUTPUT / "scan_summary.json").write_text(json.dumps({"date": today, "alerts": len(alerts), "top": alerts[:10]}, ensure_ascii=False, indent=2), encoding="utf-8")

    # 弹窗
    if len(alerts) >= 5:
        toast("行业雷达", f"今日{len(alerts)}个异动信号\n{alerts[0]['name']}({alerts[0]['code']}) {alerts[0]['change']:+.1f}%")

    # 异动→自动Serenity深挖
    if len(alerts) >= 5:
        auto_hunt(alerts)

    elapsed = time.time() - t0
    print(f"扫描完成: {len(alerts)}个异动 | {elapsed:.1f}s | {today}")

if __name__ == "__main__":
    main()
