#!/usr/bin/env python3
"""
前瞻事件扫描器 · 把"即将发生"变成"提前埋伏"
核心原则：**任何能影响板块的重大消息都算前瞻事件**，不限类别。

8 类覆盖框架（骨架，可随时加）：
  1. 发射类     - 火箭/卫星/飞船发射窗口（朱雀三号 → 商业航天）
  2. 政策/会议   - 国务院/部委文件、政治局/国常会、重要行业会议（消费/房地产/机器人/低空）
  3. IPO/融资   - 新股上市/申购、大额定增/减持 → 资金抽血或共振
  4. 期货异动   - 外围消息（美联储/OPEC/地缘/供应）→ 大宗涨停跌停 → 传导A股
  5. 数据窗口   - CPI/PPI/PMI/社融/MLF/LPR、非农、财报季、中报年报窗口
  6. 巨头发布   - 苹果/华为/特斯拉/英伟达/OpenAI 发布会、新车型/新芯片/新品
  7. 技术里程碑 - 适航证/临床三期/量产突破/国家认证（验收/拿证/下线）
  8. 并购重组   - 重大资产重组、行业整合、百亿级订单

判断标准（触发前瞻关注的底线）：
  - 消息足以带动一个板块级别（≥5只票）的资金转向
  - 或对单只龙头有决定性影响（认证/禁令/中标/财报）
  - 日常研报、无板块影响的小事 → 不算

用法:
  python forward_events.py               # 输出今日前瞻清单 + 日历触发检查
  python forward_events.py --check        # 仅检查事件日历触发
  python forward_events.py --search       # 仅输出4类必搜关键词清单
  python forward_events.py --add "日期|分类|事件|影响板块|备注"
                                        # 手动添加事件到日历

事件日历默认内置于 KNOWN_EVENTS，可另存 forward_events.json 覆盖。
"""
import sys
import io
import json
import os
from datetime import date, timedelta

if not getattr(sys.stdout, 'encoding', '') or 'utf-8' not in (sys.stdout.encoding or '').lower():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'forward_events.json')

# ── 事件日历（date 格式 YYYY-MM-DD；status: pending=未发生 done=已发生 cancel=取消）──
KNOWN_EVENTS = [
    # 发射类
    {"date": "2026-08-31", "cat": "发射", "title": "朱雀三号遥二火箭发射(顺延)",
     "sector": "商业航天", "status": "pending",
     "note": "原8/11推迟，行业预估新窗口约8/31；看点=一级回收能否成功"},
    # 政策类
    # IPO类
    {"date": "2026-08-20", "cat": "IPO", "title": "宇树科技挂牌上市(8/12缴款)",
     "sector": "机器人", "status": "pending",
     "note": "A股'人形机器人第一股'，发行PE 219倍/市值约610亿；8/10申购、8/12缴款、8月下旬挂牌"},
    # 期货异动类
    {"date": "2026-08-10", "cat": "期货异动", "title": "原油暴涨5%+铜库存告急",
     "sector": "石油/有色", "status": "done",
     "note": "霍尔木兹协议未达成→WTI涨5.05%至82.13；SPR库存1983年以来最低；LME铜库存单日减4675吨"},
]

# ── 必搜关键词（每日扫描时替换日期执行，覆盖所有能影响板块的重大消息）──
SEARCH_TEMPLATES = {
    "发射": [
        "{M}月{D}日 火箭 发射 窗口 最新",
        "{M}月{D}日 商业航天 发射计划",
        "朱雀三号 星舰 长征 发射时间表 2026",
    ],
    "政策/会议": [
        "国务院 {M}月{D}日 政策 文件 发布",
        "发改委 工信部 新政策 {M}月{D}日 板块",
        "政治局会议 国常会 {M}月 会议 产业",
        "消费 提振 房地产 新政 2026年8月",
        "{M}月 行业大会 论坛 召开 政策",
    ],
    "IPO/融资": [
        "{M}月{D}日 新股 上市 申购 一览",
        "IPO 上市 板块影响 下周",
        "大额定增 减持 计划 本周 龙头",
    ],
    "期货异动": [
        "期货 涨停 跌停 {M}月{D}日",
        "美联储 OPEC 大宗商品 异动 {M}月{D}日",
        "原油 铜 黄金 碳酸锂 夜盘 大涨大跌",
    ],
    "数据窗口": [
        "CPI PPI PMI 社融 发布 {M}月{D}日",
        "MLF LPR 降息 降准 预期 本周",
        "非农 美国 CPI 议息 {M}月 最新",
        "{M}月 中报 财报 预告 业绩 窗口",
    ],
    "巨头发布": [
        "苹果 华为 特斯拉 英伟达 {M}月 发布会 新品",
        "OpenAI 小米 新车型 新芯片 {M}月{D}日 发布",
        "机器人 新款 量产 发布 {M}月 时间",
    ],
    "技术里程碑": [
        "适航证 临床三期 获批 验收 {M}月{D}日",
        "量产 突破 认证 下线 {M}月 里程碑",
        "国产替代 突破 招标 落地 {M}月",
    ],
    "并购重组": [
        "重大资产重组 复牌 停牌 公告 {M}月{D}日",
        "百亿 收购 并购 行业整合 本周",
        "重大合同 中标 订单 公告 {M}月",
    ],
}

# 影响板块映射（搜索命中后归档到哪个板块页；None=按事件实际板块定）
CATEGORY_SECTOR = {
    "发射": "商业航天",
    "政策/会议": None, "IPO/融资": None, "期货异动": None,
    "数据窗口": None, "巨头发布": None, "技术里程碑": None, "并购重组": None,
}

def load_events():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, encoding='utf-8') as f:
            try:
                events = json.load(f)
            except Exception:
                events = KNOWN_EVENTS
    else:
        events = KNOWN_EVENTS
    return auto_prune(events, date.today())

def auto_prune(events, today):
    """自动清理规则：已发生过(日期+3天 < 今天)的事件消除，未发生的不动"""
    kept = []
    removed = 0
    for e in events:
        try:
            e_date = date.fromisoformat(e['date'])
        except Exception:
            kept.append(e)
            continue
        # 已发生超过3天 → 自动消除；未发生/3天内 → 保留
        if e_date + timedelta(days=3) < today:
            removed += 1
            continue
        kept.append(e)
    if removed and os.path.exists(DATA_FILE):
        save_events(kept)
    return kept

def save_events(events):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(events, f, ensure_ascii=False, indent=2)

def check_calendar(events, today):
    """检查事件日历：今天到期/临近/已过，输出触发结论"""
    lines = []
    for e in events:
        if e.get('status') == 'done':
            continue
        try:
            e_date = date.fromisoformat(e['date'])
        except Exception:
            continue
        delta = (e_date - today).days
        cat = e.get('cat', '')
        title = e.get('title', '')
        sector = e.get('sector', '')
        status = e.get('status', 'pending')

        if status == 'cancel':
            lines.append(f"❌ 已取消: [{cat}] {title}（原{e['date']}，板块:{sector}）")
        elif delta == 0:
            lines.append(f"🚀 就是今天: [{cat}] {title}（板块:{sector}）→ 验证落地结果!")
        elif 0 < delta <= 3:
            lines.append(f"⏳ 即将发生({delta}天后): [{cat}] {title}（板块:{sector}）→ 提前埋伏观察")
        elif -3 <= delta < 0:
            lines.append(f"📌 刚过去({-delta}天前): [{cat}] {title}（板块:{sector}）→ 检查实际影响")
        elif delta > 3:
            continue  # 太远，不进清单
    return lines

def print_search_list(today):
    """输出4类必搜关键词清单（供每日扫描执行 WebSearch）"""
    md = f"{today.month}月{today.day}日"
    print("=" * 66)
    print(f"🔭 今日前瞻必搜清单 ({md})")
    print("=" * 66)
    for cat, queries in SEARCH_TEMPLATES.items():
        print(f"\n【{cat}】")
        for q in queries:
            q = q.replace("{M}", str(today.month)).replace("{D}", str(today.day))
            print(f"  · {q}")

def main():
    today = date.today()

    if len(sys.argv) > 1 and sys.argv[1] == '--check':
        events = load_events()
        hits = check_calendar(events, today)
        print(f"📅 事件日历触发检查（{today.isoformat()}）")
        if hits:
            print("\n".join(hits))
        else:
            print("✅ 未来3天内无已知事件，正常执行4类前瞻搜索")
        return

    if len(sys.argv) > 1 and sys.argv[1] == '--search':
        print_search_list(today)
        return

    if len(sys.argv) > 1 and sys.argv[1] == '--add':
        # 格式: --add "2026-08-15|政策|消费新政|消费|待确认"
        try:
            d, cat, title, sector, note = sys.argv[2].split('|')
            events = load_events()
            events.append({"date": d, "cat": cat, "title": title,
                           "sector": sector, "status": "pending", "note": note})
            save_events(events)
            print(f"✅ 已添加事件: {title} ({d})")
        except Exception as e:
            print(f"❌ 格式错误: {e}\n用法: --add \"日期|分类|事件|影响板块|备注\"")
        return

    # 默认：日历检查 + 搜索清单
    events = load_events()
    hits = check_calendar(events, today)
    if hits:
        print(f"📅 事件日历触发检查（{today.isoformat()}）")
        print("\n".join(hits))
        print()
    print_search_list(today)

if __name__ == '__main__':
    main()
