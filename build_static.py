#!/usr/bin/env python3
"""
行业雷达 · 纯静态网站生成器
把 content/sectors/*.md 渲染成零 JS 的纯静态 HTML，输出到 docs/
替代 Next.js，解决 GitHub Pages 加载卡顿问题。

用法: python build_static.py
输出: docs/ (index.html + sector/<slug>.html)
"""
import io
import os
import re
import sys
import yaml
from datetime import date, datetime
from pathlib import Path
from typing import Tuple, Optional, List, Dict, Any, Union

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = Path(__file__).parent
CONTENT_DIR = ROOT / "content" / "sectors"
OUT_DIR = ROOT / "docs"

# ── 板块展示名称映射 ──
SECTOR_LABELS = {
    "semiconductor": "半导体",
    "ai-chips": "AI芯片/算力",
    "optical-cpo": "光通信/CPO",
    "storage-chips": "存储芯片",
    "advanced-packaging": "先进封装",
    "pcb": "PCB",
    "ai-applications": "AI应用",
    "humanoid-robot": "人形机器人",
    "low-altitude-economy": "低空经济",
    "commercial-aerospace": "商业航天",
    "solid-state-battery": "固态电池",
    "compute-power-grid": "算电协同",
    "6g-communications": "6G/通信技术",
    "ai-supply-chain": "AI产业链全景图",
    "market-pulse": "市场异动&前瞻推演",
}

# ── 板块 slug 顺序（market-pulse 置顶）──
SECTOR_ORDER = [
    "market-pulse",
    "ai-chips", "semiconductor", "optical-cpo", "storage-chips",
    "advanced-packaging", "pcb", "ai-applications", "humanoid-robot",
    "low-altitude-economy", "commercial-aerospace", "solid-state-battery",
    "compute-power-grid", "6g-communications", "ai-supply-chain",
]


def parse_frontmatter(text: str) -> Tuple[Dict, str]:
    """解析 --- 之间的 YAML frontmatter，返回 (meta, content)"""
    if text.startswith('---'):
        parts = text.split('---', 2)
        if len(parts) >= 3:
            try:
                meta = yaml.safe_load(parts[1]) or {}
            except Exception:
                meta = {}
            return meta, parts[2]
    return {}, text


def md_escape(text: str) -> str:
    """转义 HTML 特殊字符"""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def inline_markdown(line: str) -> str:
    """处理行内格式：粗体、斜体、行内代码"""
    line = md_escape(line)
    # 行内代码 `code`
    line = re.sub(r'`([^`]+)`', r'<code>\1</code>', line)
    # 粗体 **text**
    line = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', line)
    # 斜体 *text*
    line = re.sub(r'(?<!\*)\*([^*\n]+)\*(?!\*)', r'<em>\1</em>', line)
    return line


def render_table(table_lines: List[str]) -> str:
    """渲染 markdown 表格行 → HTML 表格"""
    rows = []
    for line in table_lines:
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        rows.append(cells)
    if not rows:
        return ''
    # 去掉分隔行 |---|:--:|
    rows = [r for r in rows if not all(re.match(r'^[-:]+$', c) for c in r)]
    if not rows:
        return ''
    header = rows[0]
    body = rows[1:]
    html = ['<div class="table-wrap"><table>', '<thead><tr>']
    for h in header:
        html.append(f'<th>{inline_markdown(h)}</th>')
    html.append('</tr></thead><tbody>')
    for row in body:
        html.append('<tr>')
        for i, cell in enumerate(row):
            # 第一列加粗加左对齐
            if i == 0:
                html.append(f'<td class="td-first">{inline_markdown(cell)}</td>')
            else:
                html.append(f'<td>{inline_markdown(cell)}</td>')
        html.append('</tr>')
    html.append('</tbody></table></div>')
    return '\n'.join(html)


def render_markdown(content: str) -> str:
    """完整 markdown → HTML 渲染（标题/表格/列表/引用/代码块/hr）"""
    lines = content.split('\n')
    html = []
    i = 0
    in_code = False
    code_buf = []
    in_list = False
    in_blockquote = False

    def close_list():
        nonlocal in_list
        if in_list:
            html.append('</ul>')
            in_list = False

    def close_quote():
        nonlocal in_blockquote
        if in_blockquote:
            html.append('</blockquote>')
            in_blockquote = False

    while i < len(lines):
        line = lines[i]

        # 代码块
        if line.strip().startswith('```'):
            if in_code:
                html.append('<pre><code>' + md_escape('\n'.join(code_buf)) + '</code></pre>')
                code_buf = []
                in_code = False
            else:
                close_list(); close_quote()
                in_code = True
            i += 1
            continue
        if in_code:
            code_buf.append(line)
            i += 1
            continue

        stripped = line.strip()

        # 空行
        if not stripped:
            close_list(); close_quote()
            i += 1
            continue

        # 标题
        m = re.match(r'^(#{1,4})\s+(.*)', line)
        if m:
            close_list(); close_quote()
            level = len(m.group(1))
            html.append(f'<h{level}>{inline_markdown(m.group(2))}</h{level}>')
            i += 1
            continue

        # 分隔线
        if re.match(r'^---+\s*$', line):
            close_list(); close_quote()
            html.append('<hr>')
            i += 1
            continue

        # 引用
        if stripped.startswith('>'):
            if not in_blockquote:
                close_list()
                html.append('<blockquote>')
                in_blockquote = True
            html.append(f'<p>{inline_markdown(stripped[1:].strip())}</p>')
            i += 1
            continue

        # 表格（连续 | 行）
        if stripped.startswith('|') and stripped.endswith('|'):
            close_list(); close_quote()
            table = []
            while i < len(lines) and lines[i].strip().startswith('|') and lines[i].strip().endswith('|'):
                table.append(lines[i].strip())
                i += 1
            html.append(render_table(table))
            continue

        # 列表
        m = re.match(r'^[-*]\s+(.*)', line)
        if m:
            if not in_list:
                close_quote()
                html.append('<ul>')
                in_list = True
            html.append(f'<li>{inline_markdown(m.group(1))}</li>')
            i += 1
            continue

        # 有序列表
        m = re.match(r'^\d+\.\s+(.*)', line)
        if m:
            if not in_list:
                close_quote()
                html.append('<ol>')
                in_list = True
            html.append(f'<li>{inline_markdown(m.group(1))}</li>')
            i += 1
            continue

        # 普通段落
        close_list(); close_quote()
        html.append(f'<p>{inline_markdown(stripped)}</p>')
        i += 1

    close_list(); close_quote()
    if in_code:
        html.append('<pre><code>' + md_escape('\n'.join(code_buf)) + '</code></pre>')
    return '\n'.join(html)


def render_supply_chain(sc_md: str) -> str:
    """渲染供应链导图：按标题层级输出缩进式列表（每行一条，层级用边框缩进表达）"""
    items = []
    for line in sc_md.split('\n'):
        line = line.rstrip()
        if not line.strip():
            continue
        m = re.match(r'^(#{1,4})\s+(.*)', line)
        if m:
            items.append((len(m.group(1)), inline_markdown(m.group(2))))
        else:
            # 非标题行（细节行）→ 最小层级
            items.append((4, inline_markdown(line.strip())))

    if not items:
        return ''

    # 层级 → 类名
    def lv_cls(level):
        return {1: 'lv1', 2: 'lv2', 3: 'lv3', 4: 'lv4'}.get(level, 'lv4')

    rows = []
    for level, label in items:
        rows.append(f'<div class="sc-item {lv_cls(level)}">{label}</div>')
    return f'<div class="sc-root">{"".join(rows)}</div>'


def render_materials_table(materials: list) -> str:
    """渲染关键材料表格"""
    if not materials:
        return ''
    html = ['<div class="table-wrap"><table><thead><tr>',
            '<th>材料</th><th>缺口程度</th><th>国产化</th><th>供应商</th></tr></thead><tbody>']
    for m in materials:
        gap = str(m.get('gapLevel', ''))
        gap_class = 'gap-high' if ('严重' in gap or '极' in gap) else ('gap-mid' if '中' in gap else '')
        html.append(f'<tr><td class="td-first">{md_escape(str(m.get("material", "")))}</td>'
                    f'<td><span class="gap-tag {gap_class}">{md_escape(gap)}</span></td>'
                    f'<td>{md_escape(str(m.get("localization", "")))}</td>'
                    f'<td>{md_escape(str(m.get("suppliers", "")))}</td></tr>')
    html.append('</tbody></table></div>')
    return '\n'.join(html)


def render_market_chart(md: dict) -> str:
    """渲染市场规模预测：简单 SVG 柱状图"""
    if not md:
        return ''
    years = md.get('years', [])
    values = md.get('values', [])
    unit = md.get('unit', '')
    label = md.get('label', '')
    if not years or not values:
        return ''
    max_v = max(values)
    w = len(values) * 64 + 40
    h = 220
    bars = []
    for i, (y, v) in enumerate(zip(years, values)):
        bh = int(v / max_v * (h - 60))
        x = 20 + i * 64
        y_top = h - 30 - bh
        bars.append(f'<rect x="{x}" y="{y_top}" width="36" height="{bh}" rx="3" fill="#2563eb" opacity="0.85">'
                    f'<title>{y}: {v/1e8:.0f}亿{unit}</title></rect>')
        bars.append(f'<text x="{x+18}" y="{y_top-6}" text-anchor="middle" font-size="22" fill="#64748b">{v/1e8:.0f}</text>')
        bars.append(f'<text x="{x+18}" y="{h-12}" text-anchor="middle" font-size="24" fill="#94a3b8">{y}</text>')
    return (f'<div class="chart-box"><p class="chart-label">{md_escape(label)}</p>'
            f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}" role="img" aria-label="{md_escape(label)}">'
            f'<line x1="16" y1="{h-30}" x2="{w-8}" y2="{h-30}" stroke="#e2e8f0"/>'
            f'<line x1="16" y1="{h-30}" x2="16" y2="12" stroke="#e2e8f0"/>{chr(10).join(bars)}'
            f'</svg><p class="chart-unit">单位：{md_escape(unit)}</p></div>')


def parse_companies(content: str) -> List[Dict]:
    """从正文解析 头部企业 表格"""
    m = re.search(r'## 头部企业\s*\n(.*?)(?=\n## |\Z)', content, re.S)
    if not m:
        return []
    table_lines = [l.strip() for l in m.group(1).split('\n') if l.strip().startswith('|')]
    if len(table_lines) < 2:
        return []
    rows = [l for l in table_lines if not all(re.match(r'^[-:]+$', c) for c in l.strip().strip('|').split('|'))]
    if not rows:
        return []
    data = []
    for row in rows[1:]:
        cells = [c.strip() for c in row.strip().strip('|').split('|')]
        if len(cells) >= 5:
            data.append({
                'name': cells[1], 'business': cells[2],
                'region': cells[3], 'advantage': cells[4]
            })
    return data


def strip_tables(content: str) -> str:
    """移除 头部企业/关键材料 表格段（已单独渲染）"""
    content = re.sub(r'## 头部企业[\s\S]*?(?=\n## |\Z)', '\n', content)
    content = re.sub(r'## 关键材料[\s\S]*?(?=\n## |\Z)', '\n', content)
    return content


def days_since(date_str: str) -> int:
    try:
        d = datetime.strptime(date_str, '%Y-%m-%d').date()
        return (date.today() - d).days
    except Exception:
        return 999


def load_sectors() -> List[Dict]:
    """加载所有板块数据"""
    sectors = []
    for f in sorted(CONTENT_DIR.glob('*.md')):
        text = f.read_text(encoding='utf-8')
        meta, content = parse_frontmatter(text)
        slug = meta.get('slug', f.stem)
        sectors.append({
            'slug': slug,
            'file': f,
            'meta': meta,
            'content': content,
            'alerts': meta.get('alerts', []) or [],
            'materials': meta.get('materials', []) or [],
            'marketData': meta.get('marketData'),
            'supplyChain': meta.get('supplyChain'),
            'companies': parse_companies(content),
        })
    # 按 SECTOR_ORDER 排序，未知的放后面
    order = {s: i for i, s in enumerate(SECTOR_ORDER)}
    sectors.sort(key=lambda s: order.get(s['slug'], 99))
    return sectors


# ── CSS ──
CSS = """
:root { --blue:#2563eb; --blue-d:#1d4ed8; --gray:#f8fafc; --border:#e2e8f0;
        --ink:#0f172a; --body:#334155; --muted:#94a3b8; --radius:12px;
        --shadow-sm:0 1px 2px rgba(15,23,42,.05);
        --shadow-md:0 8px 24px rgba(15,23,42,.08); }
* { box-sizing:border-box; margin:0; padding:0; }
body { font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;
       background:var(--gray); color:var(--body); line-height:1.7; font-size:16px; }
a { color:var(--blue); text-decoration:none; }
a:hover { text-decoration:underline; }
.nav { background:var(--ink); color:#fff; position:sticky; top:0; z-index:50;
       box-shadow:0 1px 3px rgba(0,0,0,.15); }
.nav-inner { max-width:1120px; margin:0 auto; padding:0 20px; display:flex; align-items:center;
             gap:16px; height:56px; }
.nav-logo { font-weight:800; font-size:20px; color:#fff; white-space:nowrap; letter-spacing:.3px; }
.nav-logo:hover { text-decoration:none; }
.nav-links { display:flex; gap:6px; overflow-x:auto; padding-bottom:4px; flex:1;
             scrollbar-width:none; }
.nav-links::-webkit-scrollbar { display:none; }
.nav-link { color:#cbd5e1; font-size:16px; padding:4px 10px; border-radius:6px; white-space:nowrap; }
.nav-link:hover { color:#fff; background:rgba(255,255,255,.12); text-decoration:none; }
.nav-link.active { color:#fff; background:var(--blue); font-weight:600; }
.container { max-width:1120px; margin:0 auto; padding:28px 20px 72px; }
.hero { text-align:center; padding:40px 0 32px; }
.hero h1 { font-size:34px; font-weight:800; color:var(--ink); letter-spacing:.5px; }
.hero p { color:#64748b; margin-top:10px; font-size:17px; }
.hero .updated { color:var(--blue); font-weight:600; margin-top:8px; font-size:16px; }
.grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(290px,1fr)); gap:18px; }
.card { position:relative; background:#fff; border:1px solid var(--border); border-radius:var(--radius);
        padding:20px; box-shadow:var(--shadow-sm); transition:box-shadow .18s, border-color .18s, transform .18s;
        display:block; }
.card:hover { box-shadow:var(--shadow-md); border-color:#94a3b8; transform:translateY(-2px);
              text-decoration:none; }
.card h2 { font-size:20px; font-weight:700; color:var(--ink); }
.card:hover h2 { color:var(--blue); }
.card .tags { color:var(--muted); font-size:14px; margin-top:8px; line-height:1.5; }
.card .meta { display:flex; justify-content:space-between; margin-top:14px; color:var(--muted);
              font-size:13px; border-top:1px dashed var(--border); padding-top:12px; }
.card.new { border-color:var(--blue); background:#eff6ff; }
.card.recent { border-color:#cbd5e1; }
.badge { position:absolute; top:-10px; right:-10px; min-width:26px; height:26px; padding:0 8px;
         display:flex; align-items:center; justify-content:center; background:#ef4444; color:#fff;
         font-size:14px; font-weight:700; border-radius:999px; box-shadow:0 2px 6px rgba(0,0,0,.2); }
.badge.blue { background:var(--blue); }
.badge.gray { background:#94a3b8; }
.back { display:inline-block; font-size:16px; margin-bottom:24px; color:var(--muted); }
.back:hover { color:var(--blue); }
.sector-header { margin-bottom:24px; padding-bottom:20px; border-bottom:1px solid var(--border); }
.sector-header h1 { font-size:28px; font-weight:800; color:var(--ink); letter-spacing:.3px; }
.tag-row { display:flex; flex-wrap:wrap; gap:6px; margin:12px 0; }
.tag { background:#eff6ff; color:var(--blue-d); border:1px solid #bfdbfe; font-size:14px;
       padding:3px 10px; border-radius:999px; }
.sector-meta { color:var(--muted); font-size:16px; }
.alert-section { margin:20px 0 32px; }
.alert-section h2 { font-size:20px; color:#dc2626; margin-bottom:12px; }
.alert { display:flex; gap:12px; background:#fef2f2; border:1px solid #fecaca; border-radius:10px;
         padding:14px 16px; margin-bottom:10px; }
.alert .num { flex-shrink:0; width:22px; height:22px; border-radius:50%; background:#ef4444;
              color:#fff; font-size:13px; font-weight:700; display:flex; align-items:center;
              justify-content:center; }
.alert p { font-size:16px; color:#991b1b; line-height:1.6; }
.alert .date { font-size:13px; color:#f87171; margin-top:4px; }
.article { background:#fff; border:1px solid var(--border); border-radius:var(--radius);
           padding:32px 36px; margin-bottom:32px; box-shadow:var(--shadow-sm); }
.article h2 { font-size:22px; font-weight:700; color:var(--ink); margin:32px 0 14px; padding-bottom:10px;
              border-bottom:1px solid #e2e8f0; }
.article h2:first-child { margin-top:0; }
.article h3 { font-size:19px; font-weight:600; color:#1e293b; margin:24px 0 10px; }
.article h4 { font-size:17px; font-weight:600; color:#334155; margin:18px 0 8px; }
.article p { font-size:16px; line-height:1.85; color:var(--body); margin-bottom:14px; }
.article ul,.article ol { margin:0 0 14px 22px; }
.article li { font-size:16px; line-height:1.75; color:var(--body); margin-bottom:6px; }
.article strong { color:var(--ink); }
.article blockquote { border-left:3px solid var(--blue); padding:12px 16px; margin:14px 0;
                      background:#eff6ff; border-radius:0 8px 8px 0; font-size:15px; color:var(--body); }
.article blockquote p { margin-bottom:0; }
.article hr { border:none; border-top:1px solid #e2e8f0; margin:28px 0; }
.article code { background:#f1f5f9; padding:2px 6px; border-radius:4px; font-size:15px; color:#4b5563;
                font-family:'Cascadia Code','Fira Code',monospace; }
.article pre { background:var(--ink); color:#e2e8f0; padding:18px 20px; border-radius:10px; overflow-x:auto;
               margin:14px 0; font-size:14px; line-height:1.65; }
.article pre code { background:none; color:inherit; padding:0; }
.table-wrap { overflow-x:auto; margin:16px 0; }
table { width:100%; border-collapse:collapse; font-size:15px; }
th { background:#f1f5f9; text-align:left; padding:10px 14px; font-weight:600; color:var(--ink);
     border-bottom:1px solid #d1d5db; white-space:nowrap; }
td { padding:10px 14px; border-bottom:1px solid #eef2f7; color:var(--body); vertical-align:top; }
td.td-first { font-weight:600; color:var(--ink); white-space:nowrap; }
tr:hover td { background:#f8fafc; }
.section-block { margin-bottom:32px; }
.section-title { font-size:21px; font-weight:700; color:var(--ink); margin-bottom:14px;
                 padding-left:12px; border-left:4px solid var(--blue); line-height:1.4; }
.section-title span { font-size:15px; color:var(--muted); font-weight:400; margin-left:8px; }
.gap-tag { display:inline-block; padding:1px 8px; border-radius:999px; font-size:13px; }
.gap-high { background:#fef2f2; color:#dc2626; border:1px solid #fecaca; }
.gap-mid { background:#fffbeb; color:#b45309; border:1px solid #fde68a; }
.chart-box { background:#fff; border:1px solid var(--border); border-radius:12px; padding:16px; }
.chart-label { font-size:17px; font-weight:600; color:#0f172a; margin-bottom:8px; }
.chart-unit { font-size:13px; color:#94a3b8; margin-top:4px; text-align:right; }
.sc-root { display:flex; flex-direction:column; }
.sc-item { font-size:16px; color:#334155; padding:5px 10px; border-left:3px solid var(--border);
           margin:2px 0; border-radius:0 6px 6px 0; }
.sc-item strong { color:#0f172a; }
.sc-item.lv1 { background:#eff6ff; border-left-color:var(--blue); font-weight:600; color:#1e40af;
               font-size:17px; }
.sc-item.lv2 { margin-left:16px; background:#f8fafc; border-left-color:#93c5fd; }
.sc-item.lv3 { margin-left:32px; border-left-color:#c7d2fe; }
.sc-item.lv4 { margin-left:48px; border-left-color:#e2e8f0; color:#64748b; font-size:15px; }
.footer { text-align:center; color:#94a3b8; font-size:14px; padding:24px 0 40px; border-top:1px solid var(--border); }
.footer p { margin:4px 0; }
.details summary { cursor:pointer; color:#94a3b8; font-size:16px; margin:8px 0; }
.details summary:hover { color:var(--blue); }
.related { display:flex; flex-wrap:wrap; gap:8px; margin-top:10px; }
.related a { background:#f1f5f9; border:1px solid var(--border); padding:4px 12px; border-radius:8px;
             font-size:16px; color:#334155; }
.related a:hover { background:#e2e8f0; text-decoration:none; }
.sentiment { display:flex; flex-wrap:wrap; gap:12px; margin-bottom:12px; }
.s-item { background:#fff; border:1px solid var(--border); border-radius:10px;
          padding:10px 18px; min-width:96px; text-align:center; box-shadow:var(--shadow-sm); }
.s-label { font-size:13px; color:var(--muted); margin-bottom:4px; }
.s-val { font-size:28px; font-weight:700; color:var(--ink); line-height:1.2; }
.s-val small { font-size:13px; color:var(--muted); font-weight:400; }
.s-ladder { font-size:16px; color:var(--body); margin:12px 0 4px; line-height:1.7; }
.s-ladder b { color:var(--ink); }
.s-reasons { margin-top:10px; display:flex; flex-wrap:wrap; gap:6px; }
.s-reasons .tag { font-size:13px; }
@media (max-width:640px) {
  .hero h1 { font-size:31px; }
  .grid { grid-template-columns:1fr; }
  .article { padding:18px; }
}
"""


def render_nav(active_slug: Optional[str], sectors: list) -> str:
    items = []
    for s in sectors:
        slug = s['slug']
        label = SECTOR_LABELS.get(slug, s['meta'].get('sector', slug))
        cls = ' active' if slug == active_slug else ''
        items.append(f'<a class="nav-link{cls}" href="sector/{slug}.html">{label}</a>')
    return f'''<nav class="nav"><div class="nav-inner">
<a class="nav-logo" href="index.html">📡 行业雷达</a>
<div class="nav-links">{"".join(items)}</div>
</div></nav>'''


def render_alert(alert: dict, i: int) -> str:
    companies = alert.get('companies', [])
    comp_str = f' · 涉及：{"、".join(companies)}' if companies else ''
    date_str = str(alert.get('date', ''))
    return (f'<div class="alert"><span class="num">{i + 1}</span><div>'
            f'<p>{md_escape(str(alert.get("text", "")))}</p>'
            f'<p class="date">{date_str}{comp_str}</p></div></div>')


def load_calendar_events() -> List[Dict]:
    """读事件日历（forward_events.json，已被 auto_prune 清理过期）"""
    p = ROOT / 'engine' / 'forward_events.json'
    if not p.exists():
        return []
    try:
        import json as _json
        events = _json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return []
    return sorted(events, key=lambda e: str(e.get('date', '9999-99-99')))


def render_calendar(events: List[Dict]) -> str:
    """渲染事件日历表格（动态，跟随 auto_prune 自动清理）"""
    if not events:
        return ''
    rows = []
    for e in events:
        d = str(e.get('date', ''))
        title = md_escape(str(e.get('title', '')))
        cat = md_escape(str(e.get('cat', '')))
        sector = md_escape(str(e.get('sector', '')))
        note = md_escape(str(e.get('note', '')))
        rows.append(f'<tr><td class="td-first">{d}</td><td>{title}</td>'
                    f'<td>{cat}</td><td>{sector}</td><td>{note}</td></tr>')
    return (f'<section class="section-block"><h2 class="section-title">📅 事件日历'
            f'<span>自动清理：已发生超3天 / 推演超7天剔除</span></h2>'
            f'<div class="table-wrap"><table><thead><tr><th>日期</th><th>事件</th>'
            f'<th>分类</th><th>影响板块</th><th>看点</th></tr></thead><tbody>'
            f'{"".join(rows)}</tbody></table></div></section>')


def load_sentiment() -> Optional[Dict]:
    """读市场情绪（market_sentiment.json，每日扫描生成）"""
    p = ROOT / 'engine' / 'output' / 'market_sentiment.json'
    if not p.exists():
        return None
    try:
        import json as _json
        return _json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return None


def render_sentiment(s: Optional[Dict]) -> str:
    """渲染市场情绪卡片（涨停/炸板/连板天梯/晋级率/题材热度）"""
    if not s:
        return ''
    emoji = {'亢奋': '🔥', '活跃': '😄', '中性': '😐',
             '低迷': '🥶', '冰点': '💀'}.get(str(s.get('level', '')), '')
    score = s.get('score', '?')
    zt, zb, dt = s.get('zt', 0), s.get('zb', 0), s.get('dt', 0)
    zbr = s.get('zbr', 0)
    maxb = s.get('maxBoard', 0)
    ladder = ' → '.join(f'{b}板×{n}' for b, n in sorted((s.get('ladder') or {}).items()))
    lj = s.get('ljRate')
    profit = s.get('profit')
    reasons = ' '.join(f'<span class="tag">{md_escape(r)}×{n}</span>'
                       for r, n in (s.get('reasons') or [])[:6])
    items = [f'<div class="s-item"><div class="s-label">涨停</div><div class="s-val">{zt}</div></div>',
             f'<div class="s-item"><div class="s-label">炸板率</div><div class="s-val">{zbr}%<small>(炸{zb})</small></div></div>',
             f'<div class="s-item"><div class="s-label">跌停</div><div class="s-val">{dt}</div></div>',
             f'<div class="s-item"><div class="s-label">最高板</div><div class="s-val">{maxb}</div></div>']
    if lj is not None:
        items.append(f'<div class="s-item"><div class="s-label">晋级率</div><div class="s-val">{lj}%</div></div>')
        items.append(f'<div class="s-item"><div class="s-label">赚钱效应</div><div class="s-val">{profit}%</div></div>')
    return (f'<section class="section-block"><h2 class="section-title">📊 市场情绪 {emoji} {md_escape(str(s.get("level","")))}'
            f'<span>情绪分 {score}</span></h2>'
            f'<div class="sentiment">{"".join(items)}</div>'
            f'<p class="s-ladder">连板天梯: {md_escape(ladder)}</p>'
            f'<div class="s-reasons">{reasons}</div></section>')


def load_lhb() -> Optional[Dict]:
    """读龙虎榜资金动向（lhb.json，每日扫描生成）"""
    p = ROOT / 'engine' / 'output' / 'lhb.json'
    if not p.exists():
        return None
    try:
        import json as _json
        return _json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return None


def render_lhb(s: Optional[Dict]) -> str:
    """渲染龙虎榜资金动向（机构净买/净买/净卖警示）"""
    if not s:
        return ''
    rows = s.get('rows') or []
    if not rows:
        return ''
    inst = [r for r in rows if (r.get('instNet') or 0) > 0.01]
    inst.sort(key=lambda r: -r['instNet'])
    buy = sorted(rows, key=lambda r: -r['netAmt'])[:6]
    sell = sorted(rows, key=lambda r: r['netAmt'])[:3]
    item = lambda r: f'{md_escape(str(r["name"]))} {r["netAmt"]:+.2f}亿'
    parts = []
    if inst:
        parts.append(f'<p class="s-ladder"><b>机构净买</b>: '
                     + ' | '.join(f'{md_escape(str(r["name"]))}({r["instNet"]:.2f}亿)' for r in inst[:4]) + '</p>')
    parts.append(f'<p class="s-ladder"><b>净买</b>: ' + ' | '.join(item(r) for r in buy) + '</p>')
    parts.append(f'<p class="s-ladder" style="color:#dc2626"><b>净卖警示</b>: ' + ' | '.join(item(r) for r in sell) + '</p>')
    return (f'<section class="section-block"><h2 class="section-title">🐉 龙虎榜资金动向'
            f'<span>{s.get("date", "")} 上榜 {len(rows)}只</span></h2>'
            + ''.join(parts) + '</section>')


def load_review() -> Optional[str]:
    """读命中率复盘（review.md，每日扫描生成）"""
    p = ROOT / 'engine' / 'output' / 'review.md'
    if not p.exists():
        return None
    try:
        return p.read_text(encoding='utf-8').strip()
    except Exception:
        return None


def render_review(content: Optional[str]) -> str:
    """渲染命中率复盘（系统自我验证：龙虎榜alpha/情绪分前瞻/事件待验证）"""
    if not content:
        return ''
    body = render_markdown(content)
    return (f'<section class="section-block"><h2 class="section-title">🔁 命中率复盘'
            f'<span>系统自我验证 · 反向优化</span></h2>{body}</section>')


def render_home(sectors: list, build_time: str) -> str:
    latest = max((s['meta'].get('updated', '') for s in sectors), default='')
    today = date.today().isoformat()
    cards = []
    for s in sectors:
        slug = s['slug']
        meta = s['meta']
        label = SECTOR_LABELS.get(slug, meta.get('sector', slug))
        updated = str(meta.get('updated', ''))
        ds = days_since(updated)
        alert_count = 0
        for a in s['alerts']:
            if -7 <= days_since(str(a.get('date', ''))) <= 3:
                alert_count += 1
        tags = meta.get('tags', [])[:3]
        stock_count = len(meta.get('stocks', []))

        card_cls = 'card'
        badge = ''
        if alert_count > 0:
            card_cls += ' new'
            badge = f'<span class="badge">{alert_count}</span>'
        elif ds <= 1:
            card_cls += ' new'
            badge = '<span class="badge blue">今日</span>'
        elif ds <= 3:
            card_cls += ' recent'
            badge = '<span class="badge gray">最近</span>'

        tag_str = ' · '.join(str(t) for t in tags) if tags else ''
        updated_disp = '今天' if ds <= 1 else updated
        updated_cls = 'color:var(--blue);font-weight:600;' if ds <= 1 else ''
        cards.append(f'''<a class="{card_cls}" href="sector/{slug}.html">
{badge}
<h2>{md_escape(label)}</h2>
<p class="tags">{md_escape(tag_str)}</p>
<div class="meta"><span>{stock_count} 只标的</span><span style="{updated_cls}">🕐 {md_escape(updated_disp)}</span></div>
</a>''')

    return f'''<!DOCTYPE html>
<html lang="zh-CN"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="build-time" content="{build_time}">
<title>行业雷达 — A股前沿行业全景分析</title>
<style>{CSS}</style></head>
<body>
{render_nav(None, sectors)}
<div class="container">
  <div class="hero">
    <h1>行业雷达</h1>
    <p>聚焦 A 股前沿行业 · 头部企业 · 产业链全景 · 材料缺口 · 市场前景</p>
    <p class="updated">🕐 最后更新 {latest}（{today} 扫描）</p>
  </div>
  <div class="grid">{"".join(cards)}</div>
</div>
<div class="footer"><p>数据来源：公开研报、政府协会、行业榜单 · 仅供参考，不构成投资建议</p></div>
</body></html>'''


def render_sector_page(s: dict, sectors: list, build_time: str) -> str:
    slug = s['slug']
    meta = s['meta']
    label = SECTOR_LABELS.get(slug, meta.get('sector', slug))
    tags = meta.get('tags', [])
    stocks = meta.get('stocks', [])
    updated = str(meta.get('updated', ''))
    content = s['content']
    alerts = s['alerts']
    companies = s['companies']
    materials = s['materials']
    market_data = s['marketData']
    supply_chain = s['supplyChain']
    related = meta.get('relatedSectors', [])

    # 活跃提醒窗口：已发生3天内 或 未来7天内（过期推演每天扫描会补新，直接剔除）
    active = [a for a in alerts if -7 <= days_since(str(a.get('date', ''))) <= 3]
    history = []

    # 内容块
    body_html = render_markdown(strip_tables(content))
    # market-pulse 页动态插入 情绪区 + 龙虎榜 + 事件日历（跟随每日扫描自动更新）
    if slug == 'market-pulse':
        dyn = (render_sentiment(load_sentiment()) + render_lhb(load_lhb())
               + render_review(load_review()) + render_calendar(load_calendar_events()))
        body_html = dyn + body_html

    # 供应链
    sc_html = ''
    if supply_chain:
        sc_html = f'<section class="section-block"><h2 class="section-title">🔗 产业链导图</h2>{render_supply_chain(str(supply_chain))}</section>'

    # 头部企业
    comp_html = ''
    if companies:
        rows = []
        active_names = {c for a in active for c in a.get('companies', [])}
        for i, c in enumerate(companies):
            name = c['name']
            alert_mark = ' 🔔' if name in active_names else ''
            rows.append(f'<tr><td class="td-first">{i + 1}</td><td class="td-first">{md_escape(name)}{alert_mark}</td>'
                        f'<td>{md_escape(c["business"])}</td><td>{md_escape(c["region"])}</td>'
                        f'<td>{md_escape(c["advantage"])}</td></tr>')
        comp_html = f'''<section class="section-block"><h2 class="section-title">🏢 头部企业<span>（{len(companies)}家）</span></h2>
<div class="table-wrap"><table><thead><tr><th>#</th><th>企业</th><th>业务</th><th>地区</th><th>核心优势</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table></div></section>'''

    # 关键材料
    mat_html = ''
    if materials:
        mat_html = f'<section class="section-block"><h2 class="section-title">🧩 关键材料 & 缺口</h2>{render_materials_table(materials)}</section>'

    # 市场规模
    chart_html = ''
    if market_data:
        chart_html = f'<section class="section-block"><h2 class="section-title">📈 市场规模预测</h2>{render_market_chart(market_data)}</section>'

    # 相关板块
    rel_html = ''
    if related:
        rel_links = []
        for rslug in related:
            rs = next((x for x in sectors if x['slug'] == rslug), None)
            if rs:
                rlabel = SECTOR_LABELS.get(rslug, rs['meta'].get('sector', rslug))
                rel_links.append(f'<a href="{rslug}.html">{md_escape(rlabel)}</a>')
        if rel_links:
            rel_html = f'<section class="section-block"><h2 class="section-title">🔗 相关板块</h2><div class="related">{"".join(rel_links)}</div></section>'

    # 提醒区
    alerts_html = ''
    if active:
        alert_items = ''.join(render_alert(a, i) for i, a in enumerate(active))
        alerts_html = f'<div class="alert-section"><h2>🔔 近期提醒（{len(active)}条，过去3天~未来7天）</h2>{alert_items}</div>'

    tag_row = ''.join(f'<span class="tag">{md_escape(str(t))}</span>' for t in tags)

    return f'''<!DOCTYPE html>
<html lang="zh-CN"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="build-time" content="{build_time}">
<title>{md_escape(label)} — 行业雷达</title>
<style>{CSS}</style></head>
<body>
{render_nav(slug, sectors)}
<div class="container">
  <a class="back" href="index.html">← 返回首页</a>
  <div class="sector-header">
    <h1>{md_escape(label)}</h1>
    <div class="tag-row">{tag_row}</div>
    <p class="sector-meta">{len(stocks)} 只成分股 · 更新于 {updated}</p>
  </div>
  {alerts_html}
  <div class="article">{body_html}</div>
  {sc_html}
  {comp_html}
  {mat_html}
  {chart_html}
  {rel_html}
  <div style="margin-top:32px;padding-top:20px;border-top:1px solid var(--border)">
    <a class="back" href="index.html">← 返回首页查看其他板块</a>
  </div>
</div>
<div class="footer"><p>数据来源：公开研报、政府协会、行业榜单 · 仅供参考，不构成投资建议</p></div>
</body></html>'''


def main():
    build_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    sectors = load_sectors()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / 'sector').mkdir(exist_ok=True)

    # 生成首页
    (OUT_DIR / 'index.html').write_text(render_home(sectors, build_time), encoding='utf-8')

    # 生成每个板块页
    for s in sectors:
        html = render_sector_page(s, sectors, build_time)
        (OUT_DIR / 'sector' / f"{s['slug']}.html").write_text(html, encoding='utf-8')

    # 彻底清理旧 Next.js 产物（_next、.txt、.js、.json、404、_not-found 及 sector 子目录残留）
    import shutil
    rm_files = ['404.html', '_not-found.html', '_not-found']
    for f in rm_files:
        p = OUT_DIR / f
        if p.exists():
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            else:
                try:
                    p.unlink()
                except Exception:
                    pass
    for p in OUT_DIR.glob('*'):
        if p.name in ('_next',) or p.suffix in ('.txt', '.js', '.json') or p.name.startswith('_'):
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            else:
                try:
                    p.unlink()
                except Exception:
                    pass
    # sector/ 目录：删除非 .html 的残留（旧 RSC .txt 与嵌套子目录）
    sector_dir = OUT_DIR / 'sector'
    if sector_dir.exists():
        for p in sector_dir.iterdir():
            if p.suffix != '.html' or p.is_dir():
                if p.is_dir():
                    shutil.rmtree(p, ignore_errors=True)
                else:
                    try:
                        p.unlink()
                    except Exception:
                        pass

    # 写入 .nojekyll（保证 GitHub Pages 不忽略下划线文件）
    (OUT_DIR / '.nojekyll').write_text('', encoding='utf-8')

    print(f"✅ 纯静态网站生成完成: {len(sectors)} 个板块")
    print(f"   输出: {OUT_DIR}")
    print(f"   构建时间: {build_time}")
    sizes = [(p.name, p.stat().st_size) for p in OUT_DIR.glob('*.html')] + \
            [(f"sector/{p.name}", p.stat().st_size) for p in (OUT_DIR / 'sector').glob('*.html')]
    sizes.sort(key=lambda x: -x[1])
    print(f"   首页: {sizes[0][1] // 1024}KB | 最大板块页: {sizes[0][0]} ({sizes[0][1] // 1024}KB)")


if __name__ == '__main__':
    main()
