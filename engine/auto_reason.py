#!/usr/bin/env python3
"""
行业雷达 · 自动推理引擎
读取每日扫描结果 → 识别异动模式 → 套用模板生成分析 → 更新 market-pulse → 部署

用法: python auto_reason.py [--dry-run] [--no-deploy]
  --dry-run   只输出不写文件
  --no-deploy  不执行 build + deploy

成本: $0（本地推理，不调用 AI）
覆盖: ~80% 常见场景（普跌/轮动/存储/机器人/单板块暴增）
无法识别时 → 标记 NEED_HUMAN，等 Claude 手动分析
"""

import sys, io, json, re, os, subprocess
from datetime import date, datetime, timedelta
from pathlib import Path
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = Path(__file__).parent.parent
OUTPUT = Path(__file__).parent / "output"
CONTENT = ROOT / "content" / "sectors"
MARKET_PULSE = CONTENT / "market-pulse.md"
DRY_RUN = "--dry-run" in sys.argv
NO_DEPLOY = "--no-deploy" in sys.argv

# ── 板块关键词映射 ──
SECTOR_KEYWORDS = {
    "半导体": ["半导体", "设备", "材料", "晶圆", "代工", "EDA"],
    "AI芯片": ["AI芯片", "算力", "GPU", "DCU", "推理"],
    "光通信/CPO": ["光通信", "CPO", "光模块", "光芯片", "光纤"],
    "MLCC": ["MLCC", "被动元件", "电容"],
    "PCB": ["PCB", "覆铜板", "CCL", "载板"],
    "先进封装": ["先进封装", "CoWoS", "封测", "HBM", "Chiplet"],
    "人形机器人": ["机器人", "减速器", "丝杠", "灵巧手"],
    "低空经济": ["低空", "无人机", "eVTOL"],
    "商业航天": ["航天", "卫星", "火箭"],
    "固态电池": ["固态电池", "电解质", "锂电池"],
    "算电协同": ["算电", "液冷", "电力", "储能", "制冷"],
    "6G/通信": ["6G", "通信", "太赫兹", "基站"],
    "AI应用": ["AI应用", "大模型", "软件"],
    "存储芯片": ["存储", "NAND", "DRAM", "HBM", "江波龙", "兆易"],
}


# ── 场景模板库 ──
def template_broad_selloff(alerts, sectors_hit):
    """普跌模板：多板块无差别抛售"""
    top = alerts[:6]
    rows = "\n".join(
        f"| {a['name']}({a['code']}) | **{a['change']:+.1f}%** | {', '.join(a['sectors'][:2])} |"
        for a in top
    )
    return f"""**🔴 {date.today().isoformat()} 自动扫描：{len(alerts)}个异动 · {len(sectors_hit)}个板块普跌**

**定性：{len(sectors_hit)}个板块同时异动 → 大概率是流动性/情绪共振，非基本面逆转。**

| 跌幅最大 | 跌幅 | 板块 |
|------|:--:|------|
{rows}

⚠️ 自动推理（模板匹配）：若北向未连续3日净流出>100亿，此类普跌通常1-2日修复。关注率先反弹的板块 → 可能是下一波主线。
"""


def template_sector_surge(alerts, main_sector, direction):
    """单板块暴增/暴跌模板"""
    top = alerts[:8]
    dir_word = "大涨" if direction == "up" else "暴跌"
    rows = "\n".join(
        f"| {a['name']}({a['code']}) | **{a['change']:+.1f}%** | {' | '.join(a['reasons'])} |"
        for a in top
    )
    return f"""**🔴 {date.today().isoformat()} 自动扫描：{main_sector}{dir_word} · {len(alerts)}个信号**

| 标的 | 涨跌幅 | 触发原因 |
|------|:--:|------|
{rows}

⚠️ 自动推理（模板匹配）：{main_sector}集中异动 → 关注上游瓶颈标的和产业链传导。若为利好驱动 → 先看最上游瓶颈（Serenity得分最高的）；若为利空 → 区分是板块独跌还是全市场共振。
"""


def template_rotation(alerts, up_sectors, down_sectors):
    """板块轮动模板"""
    return f"""**🔴 {date.today().isoformat()} 自动扫描：板块轮动 · {len(alerts)}个信号**

- 上涨板块：{', '.join(up_sectors) if up_sectors else '无'}
- 下跌板块：{', '.join(down_sectors) if down_sectors else '无'}

⚠️ 自动推理（模板匹配）：板块分化 → 资金在迁移。关注上涨板块的上游瓶颈（Serenity高分标的），可能是下一轮主线。
"""


def template_quiet():
    """无异常模板"""
    return f"""**🟢 {date.today().isoformat()} 自动扫描：无异常信号**

全板块监控正常，无触发异动阈值的标的。静默观察。
"""


# ── 模式识别 ──
def detect_pattern(alerts):
    """识别异动模式，返回 (pattern_name, context)"""
    if not alerts:
        return "quiet", {}

    # 统计板块分布
    sector_counts = Counter()
    direction_counts = Counter()
    for a in alerts:
        for s in a["sectors"]:
            if s != "市场异动":
                sector_counts[s] += 1
        direction_counts["up" if a["change"] > 0 else "down"] += 1

    sectors_hit = set(sector_counts.keys())
    up_count = direction_counts.get("up", 0)
    down_count = direction_counts.get("down", 0)

    # 普跌：>60% 下跌，>5 板块
    if len(sectors_hit) >= 5 and down_count > up_count * 3:
        return "broad_selloff", {"sectors_hit": sectors_hit}

    # 单板块集中：某个板块占比 > 50%
    if sector_counts:
        top_sector, top_count = sector_counts.most_common(1)[0]
        if top_count >= len(alerts) * 0.5:
            direction = "up" if up_count > down_count else "down"
            return "sector_surge", {"main_sector": top_sector, "direction": direction}

    # 轮动：有涨有跌
    if up_count > 0 and down_count > 0 and up_count / max(down_count, 1) > 0.3:
        up_sectors = [s for s in sectors_hit if any(
            a["change"] > 0 for a in alerts if s in a["sectors"]
        )]
        down_sectors = [s for s in sectors_hit if any(
            a["change"] < 0 for a in alerts if s in a["sectors"]
        )]
        return "rotation", {"up_sectors": up_sectors, "down_sectors": down_sectors}

    # 分散异动：有信号但不集中
    return "scattered", {"sectors_hit": sectors_hit}


def generate_reasoning(alerts):
    """主推理函数：识别 → 生成"""
    pattern, ctx = detect_pattern(alerts)

    if pattern == "quiet":
        return template_quiet(), "quiet", 0.9
    elif pattern == "broad_selloff":
        return template_broad_selloff(alerts, ctx["sectors_hit"]), "broad_selloff", 0.8
    elif pattern == "sector_surge":
        return template_sector_surge(alerts, ctx["main_sector"], ctx["direction"]), "sector_surge", 0.75
    elif pattern == "rotation":
        return template_rotation(alerts, ctx["up_sectors"], ctx["down_sectors"]), "rotation", 0.7
    else:
        # 分散异动，标记需要人工
        return None, "scattered", 0.0


# ── 更新 market-pulse.md ──
def update_market_pulse(content_block):
    """在 market-pulse.md 的 7/4 更新之前插入新更新"""
    if not MARKET_PULSE.exists():
        print("  ❌ market-pulse.md 不存在")
        return False

    raw = MARKET_PULSE.read_text(encoding="utf-8")
    today_str = date.today().isoformat()

    # 检查今天是否已更新
    if f"**🔴 {today_str}" in raw or f"**🟢 {today_str}" in raw:
        print(f"  ⚠️ 今天({today_str})已更新，跳过")
        return False

    # 更新 frontmatter 日期
    raw = re.sub(r"updated:\s*'[\d-]+'", f"updated: '{today_str}'", raw)

    # 在第一个每日更新块之前插入（找到最近的 "自动扫描" 或 "更新" 标题之前）
    # 策略：在 "## 🧠 Pro 深度推演" 之前插入
    if "## 🧠 Pro 深度推演" in raw:
        insert_pos = raw.index("## 🧠 Pro 深度推演")
    elif "## 前瞻推演" in raw:
        insert_pos = raw.index("## 前瞻推演")
    else:
        # 在最后一个 --- 分隔符之前
        parts = raw.rsplit("---", 2)
        if len(parts) >= 2:
            insert_pos = len(parts[0]) + len(parts[1])
        else:
            insert_pos = len(raw)

    new_section = f"\n---\n\n{content_block}\n"
    new_raw = raw[:insert_pos] + new_section + raw[insert_pos:]

    # 清理超过5天的旧更新
    new_raw = clean_old_updates(new_raw)

    if not DRY_RUN:
        # 备份
        backup = MARKET_PULSE.with_suffix(".md.backup")
        backup.write_text(raw, encoding="utf-8")
        MARKET_PULSE.write_text(new_raw, encoding="utf-8")
        print(f"  ✅ market-pulse.md 已更新（备份: {backup.name}）")
        # 删除备份
        backup.unlink(missing_ok=True)
    else:
        print("  [DRY-RUN] 将写入 market-pulse.md:")
        print(f"  {content_block[:200]}...")

    return True


def clean_old_updates(raw):
    """移除超过5天的自动扫描更新块"""
    cutoff = date.today() - timedelta(days=5)
    cutoff_str = cutoff.isoformat()

    # 匹配以 "**🔴 YYYY-MM-DD 自动扫描" 或 "**🟢 YYYY-MM-DD 自动扫描" 开头的块
    # 也匹配手动写的 "**🔴 X/X 更新" 格式
    lines = raw.split("\n")
    result = []
    skip_until_separator = False
    i = 0

    while i < len(lines):
        line = lines[i]
        # 检测旧的每日更新标题
        is_old_update = False
        for prefix in ["**🔴 ", "**🟢 ", "**🟨 "]:
            if line.strip().startswith(prefix):
                # 尝试提取日期
                date_match = re.search(r'(\d{4}-\d{2}-\d{2})', line)
                if not date_match:
                    date_match = re.search(r'(\d{1,2}/\d{1,2})', line)
                    if date_match:
                        # X/X 格式，补充年份
                        month_day = date_match.group(1)
                        try:
                            m, d = month_day.split("/")
                            extracted_date = f"2026-{int(m):02d}-{int(d):02d}"
                        except:
                            extracted_date = None
                    else:
                        extracted_date = None
                else:
                    extracted_date = date_match.group(1)

                if extracted_date and extracted_date < cutoff_str:
                    is_old_update = True
                    skip_until_separator = True
                break

        if skip_until_separator:
            if line.strip().startswith("---"):
                skip_until_separator = False
                # 跳过这个分隔符
                i += 1
                # 也跳过后面紧跟的空行
                while i < len(lines) and lines[i].strip() == "":
                    i += 1
                continue
            i += 1
            continue

        result.append(line)
        i += 1

    return "\n".join(result)


# ── 主流程 ──
def main():
    print("=" * 50)
    print(f"🧠 自动推理引擎 · {date.today().isoformat()}")
    print("=" * 50)

    # 1. 读取扫描结果
    scan_file = OUTPUT / "scan_summary.json"
    if not scan_file.exists():
        print("  ⚠️ scan_summary.json 不存在，先运行 daily_scan.py")
        return

    scan = json.loads(scan_file.read_text(encoding="utf-8"))
    alerts = scan.get("top", []) or []
    all_alerts_raw = scan.get("alerts_list", []) or alerts

    print(f"  异动信号: {scan.get('alerts', len(alerts))}个")

    if len(alerts) < 3:
        print("  信号不足3个 → 生成静默报告")
        content, pattern, confidence = generate_reasoning([])
    else:
        # 2. 模式识别 + 生成推理
        content, pattern, confidence = generate_reasoning(all_alerts_raw if all_alerts_raw else alerts)
        if content is None:
            print(f"  ⚠️ 无法匹配模板（模式: {pattern}）→ 标记 NEED_HUMAN")
            content = f"""**🟨 {date.today().isoformat()} 自动扫描：{len(alerts)}个信号 · 需要人工分析**

模式识别结果：`{pattern}`（置信度不足，模板无法覆盖）

异动标的：{', '.join(f"{a['name']}({a['code']})" for a in alerts[:8])}

> ⚠️ 此场景超出自动推理范围，请手动运行 `claude` 分析。
"""
            confidence = 0.0

    print(f"  模式: {pattern} | 置信度: {confidence:.0%}")
    print(f"  生成内容: {content[:120]}...")

    # 3. 更新 market-pulse
    updated = update_market_pulse(content)
    if not updated:
        print("  ⏭️ 跳过部署（未更新）")
        return

    # 4. 更新 .last-scan-date
    last_scan = ROOT / ".last-scan-date"
    if not DRY_RUN:
        last_scan.write_text(date.today().isoformat(), encoding="utf-8")

    # 5. Build + Deploy
    if NO_DEPLOY:
        print("  ⏭️ 跳过部署（--no-deploy）")
        return

    if DRY_RUN:
        print("  [DRY-RUN] 完成，未写入任何文件")
        return

    print("\n📦 Build...")
    result = subprocess.run(
        ["npm", "run", "build"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        print(f"  ❌ Build 失败:\n{result.stderr[-500:]}")
        return

    print("  ✅ Build 成功")

    print("🚀 Deploy...")
    deploy_result = subprocess.run(
        ["git", "add", "docs/", "content/"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    subprocess.run(
        ["git", "commit", "-m", f"auto: {date.today().isoformat()} 自动推理更新 [{pattern}]"],
        cwd=str(ROOT),
        capture_output=True,
        timeout=30,
    )
    push_result = subprocess.run(
        ["git", "push"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    if push_result.returncode == 0:
        print("  ✅ 已推送")
    else:
        print(f"  ⚠️ Push 失败（可能需要手动 git push）: {push_result.stderr[-200:]}")

    print(f"\n✅ 自动推理完成 [{pattern}] 置信度 {confidence:.0%}")
    if confidence < 0.6:
        print("⚠️ 置信度偏低，建议人工review")


if __name__ == "__main__":
    main()
