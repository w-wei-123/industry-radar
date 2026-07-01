#!/usr/bin/env python3
"""
Serenity 供应链逆向挖掘引擎
核心理念："不买GPU，买GPU离不开的东西"
输入: 板块名 → 输出: 被市场忽视的瓶颈标的 + 证据链
用法: python serenity_hunter.py [sector] [--all]
"""

import sys, io, json, time, random, urllib.request
from datetime import date, datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
OUTPUT = Path(__file__).parent / "output"
OUTPUT.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# ═══════════════════════════════════════════════════════════
# 供应链深度拆解知识库（Serenity核心资产）
# 每个板块: 组件→子材料→瓶颈→上市公司(含冷门小票)
# ═══════════════════════════════════════════════════════════

DEEP_CHAIN = {
"人形机器人": {
  "components": [
    {"name":"行星滚柱丝杠","cost_pct":"25%","materials":[
      {"material":"特种轴承钢(GCr15/SAE52100)","suppliers":["中信特钢(000708)","抚顺特钢(600399)"],"foreign":"日本大同/瑞典OVAKO垄断高端","gap":"严重","domestic_pct":"15%","hidden_gem":"翔楼新材(688289)——精密冷轧轴承钢带,隐形冠军","hidden_reason":"市场只知道恒立液压,不知道它上游钢材只有翔楼能做"},
      {"material":"精密磨床(螺纹磨)","suppliers":["秦川机床(000837)","日发精机(002520)"],"foreign":"瑞士REISHAUER/德国KAPP垄断","gap":"致命","domestic_pct":"<5%","hidden_gem":"华辰装备(300809)——全自动精密磨床,轧辊磨床国内第一","hidden_reason":"市场炒丝杠从没想过丝杠是磨床磨出来的"},
      {"material":"润滑涂层(MoS2/DLC)","suppliers":["昊华科技(600378)","新宙邦(300037)"],"foreign":"日本DAIDO/德国Fuchs","gap":"较大","domestic_pct":"25%"}
    ]},
    {"name":"谐波减速器","cost_pct":"18%","materials":[
      {"material":"柔轮材料(特殊球墨铸铁)","suppliers":["恒工精密(301261)"],"foreign":"日本Hitachi Metals垄断","gap":"严重","domestic_pct":"<10%","hidden_gem":"恒工精密(301261)——连续球墨铸铁棒,日本以外唯一能量产的,绿的谐波就是用它","hidden_reason":"新上市不到半年,基本没人cover"},
      {"material":"交叉滚子轴承","suppliers":["新强联(300850)","长盛轴承(300718)"],"foreign":"日本THK/IKO垄断","gap":"较大","domestic_pct":"20%","hidden_gem":"苏轴股份(430090)——微型滚针轴承,关节核心"}
    ]},
    {"name":"六维力/扭矩传感器","cost_pct":"12%","materials":[
      {"material":"应变片(金属箔式)","suppliers":["中航电测(300114)","东华测试(300354)"],"foreign":"美国Vishay/日本共和","gap":"较大","domestic_pct":"30%","hidden_gem":"康斯特(300445)——高精度压力传感器,从工业校准跨界机器人触觉"},
      {"material":"弹性体(7075航空铝)","suppliers":["南山铝业(600219)","亚太科技(002540)"],"foreign":"美国Alcoa","gap":"中等","domestic_pct":"50%","hidden_gem":"银邦股份(300337)——铝合金层压板,特斯拉供应商"}
    ]},
    {"name":"电子皮肤(触觉阵列)","cost_pct":"8%","materials":[
      {"material":"PVDF压电薄膜","suppliers":["碧水源(300070)","巨化股份(600160)"],"foreign":"日本吴羽化学/法国Arkema垄断","gap":"致命","domestic_pct":"<5%","hidden_gem":"碧水源(300070)——PVDF膜全球前五,从水处理跨界,市值仅200亿","hidden_reason":"没人意识到水处理膜和电子皮肤是同一种材料"},
      {"material":"柔性电极(纳米银线)","suppliers":["苏大维格(300331)","天材创新(688503)"],"foreign":"Cambrios/C3Nano","gap":"较大","domestic_pct":"20%","hidden_gem":"苏大维格(300331)——微纳结构加工,纳米压印光刻,市值仅80亿"},
      {"material":"微结构加工(微针阵列)","suppliers":["赛微电子(300456)","敏芯股份(688286)"],"foreign":"德国Bosch/美国MEMS","gap":"较大","domestic_pct":"15%","hidden_gem":"敏芯股份(688286)——MEMS微传感器,从耳机麦克风跨界,市值仅40亿"}
    ]},
    {"name":"灵巧手微型电机","cost_pct":"10%","materials":[
      {"material":"空心杯电机绕组","suppliers":["鸣志电器(603728)","江苏雷利(300660)","鼎智科技(873593)"],"foreign":"瑞士Maxon/Faulhaber垄断","gap":"严重","domestic_pct":"10%","hidden_gem":"鼎智科技(873593)——微型线性执行器(丝杆步进电机),对标Maxon"},
      {"material":"钕铁硼永磁(N52+)","suppliers":["中科三环(000970)","金力永磁(300748)","大地熊(688077)"],"foreign":"日本日立金属专利壁垒","gap":"中等","domestic_pct":"40%","hidden_gem":"大地熊(688077)——烧结钕铁硼,汽车/机器人双赛道,市值仅60亿"}
    ]},
    {"name":"无框力矩电机","cost_pct":"10%","materials":[
      {"material":"高性能硅钢片(0.1mm)","suppliers":["首钢股份(000959)","望变电气(688336)"],"foreign":"日本JFE/新日铁","gap":"较大","domestic_pct":"20%","hidden_gem":"望变电气(688336)——取向硅钢,从变压器跨界电机,市值仅70亿"},
      {"material":"耐高温绝缘材料","suppliers":["东材科技(601208)","巨化股份(600160)"],"foreign":"杜邦Nomex","gap":"中等","domestic_pct":"35%"}
    ]},
    {"name":"固态电池(灵巧手供电)","cost_pct":"7%","materials":[
      {"material":"LLZO固态电解质粉","suppliers":["上海洗霸(603200)","金龙羽(002882)"],"foreign":"日本出光兴产/丰田","gap":"严重","domestic_pct":"10%","hidden_gem":"上海洗霸(603200)——从工业水处理跨界固态电解质,中试线已投产"},
      {"material":"锂金属负极(超薄)","suppliers":["天赐材料(002709)","赣锋锂业(002460)"],"foreign":"美国SES/LG","gap":"较大","domestic_pct":"20%"}
    ]},
  ]
},

"AI芯片/算力": {
  "components": [
    {"name":"HBM高带宽显存","cost_pct":"35%","materials":[
      {"material":"TSV硅通孔铜填充液","suppliers":["上海新阳(300236)","安集科技(688019)"],"foreign":"美国Entegris/日本ADEKA","gap":"致命","domestic_pct":"<5%","hidden_gem":"上海新阳(300236)——电镀液国产第一,从传统封装跨界先进封装TSV"},
      {"material":"微凸块(bump)电镀锡银","suppliers":["晶方科技(603005)","兴森科技(002436)"],"foreign":"日本住友/美国MacDermid","gap":"严重","domestic_pct":"10%"},
      {"material":"底部填充胶(Underfill)","suppliers":["德邦科技(688035)","回天新材(300041)"],"foreign":"日本Namics/Henkel","gap":"较大","domestic_pct":"15%","hidden_gem":"德邦科技(688035)——电子封装胶,CoWoS必需材料,市值仅50亿"}
    ]},
    {"name":"CoWoS中介层(硅转接板)","cost_pct":"20%","materials":[
      {"material":"高阻硅片(>3000Ωcm)","suppliers":["沪硅产业(688126)","立昂微(605358)"],"foreign":"日本信越/SUMCO","gap":"严重","domestic_pct":"10%"},
      {"material":"临时键合胶/解键合","suppliers":["上海新阳(300236)","飞凯材料(300398)"],"foreign":"3M/Brewer Science","gap":"较大","domestic_pct":"10%","hidden_gem":"飞凯材料(300398)——紫外固化材料,从光通信跨界先进封装"}
    ]},
    {"name":"液冷散热(氟化液)","cost_pct":"8%","materials":[
      {"material":"全氟聚醚(PFPE)冷却液","suppliers":["东阳光(600673)","巨化股份(600160)","新宙邦(300037)"],"foreign":"3M Novec退出后缺口","gap":"致命","domestic_pct":"15%","hidden_gem":"新宙邦(300037)——氟化液+电子级氢氟酸双赛道,从电池电解液跨界,市值300亿"},
      {"material":"微通道冷板(铜钎焊)","suppliers":["科华数据(002335)","高澜股份(300499)"],"foreign":"德国Wieland","gap":"中等","domestic_pct":"40%"}
    ]},
  ]
},

"光通信/CPO": {
  "components": [
    {"name":"DSP电芯片(7nm)","cost_pct":"30%","materials":[
      {"material":"SerDes IP核","suppliers":[],"foreign":"Broadcom/Marvell/Cadence垄断","gap":"致命","domestic_pct":"<5%","hidden_gem":"芯原股份(688521)——全球第七大IP厂商,SerDes IP有储备","hidden_reason":"市场炒光模块从不提DSP,更不提IP"},
      {"material":"先进封装基板(FCBGA)","suppliers":["深南电路(002916)","兴森科技(002436)"],"foreign":"日本IBIDEN/Shinko","gap":"严重","domestic_pct":"10%"}
    ]},
    {"name":"EML激光器(200Gbps)","cost_pct":"20%","materials":[
      {"material":"InP衬底(6寸)","suppliers":["云南锗业(002428)","云南临沧鑫圆(未上市)"],"foreign":"日本住友电工/美国AXT","gap":"致命","domestic_pct":"<5%","hidden_gem":"云南锗业(002428)——锗+InP衬底双稀缺资源,从矿到芯片打通"},
      {"material":"DBR光栅(纳米压印)","suppliers":["苏大维格(300331)"],"foreign":"美国Nanonex/德国SUSS","gap":"较大","domestic_pct":"10%"}
    ]},
    {"name":"硅光集成(PIC)","cost_pct":"15%","materials":[
      {"material":"SOI硅光晶圆","suppliers":["上海新阳(300236)","中芯国际(688981)"],"foreign":"法国Soitec/比利时IMEC","gap":"严重","domestic_pct":"5%"},
      {"material":"锗硅光电探测器","suppliers":["云南锗业(002428)","光迅科技(002281)"],"foreign":"美国Luxtera/Cisco","gap":"较大","domestic_pct":"15%"}
    ]},
  ]
},

"MLCC": {
  "components": [
    {"name":"陶瓷粉料(≤150nm钛酸钡)","cost_pct":"40%","materials":[
      {"material":"纳米钛酸钡粉","suppliers":["国瓷材料(300285)","山东国瓷(未上市)"],"foreign":"日本村田/堺化学","gap":"严重","domestic_pct":"15%","hidden_gem":"国瓷材料(300285)已cover,但上游——"},
      {"material":"高纯四氯化钛(原料)","suppliers":["龙佰集团(002601)","中核钛白(002145)"],"foreign":"日本东邦钛/美国科斯特","gap":"中等","domestic_pct":"50%","hidden_gem":"龙佰集团(002601)——全球钛白粉龙头,从涂料跨界MLCC粉体原料,市值600亿"},
      {"material":"水热反应釜(设备)","suppliers":["海源复材(603058)"],"foreign":"日本Mitsubishi Materials","gap":"较大","domestic_pct":"20%","hidden_gem":"海源复材(603058)——复合材料压机,可做钛酸钡水热釜,市值仅40亿"}
    ]},
    {"name":"MLCC流延机","cost_pct":"25%","materials":[
      {"material":"流延机PET膜(0.5μm平整度)","suppliers":["东材科技(601208)","双星新材(002585)"],"foreign":"日本东丽/帝人","gap":"致命","domestic_pct":"<5%","hidden_gem":"东材科技(601208)——从绝缘膜跨界MLCC离型膜,下游已通过风华验证"},
      {"material":"高精度涂布头(狭缝式)","suppliers":[],"foreign":"日本平野/松下","gap":"致命","domestic_pct":"0%","hidden_gem":"无上市标的——但平野的涂布头用的是日本特殊不锈钢,中国没有替代"}
    ]},
    {"name":"稀土掺杂物(氧化镝/钇)","cost_pct":"5%","materials":[
      {"material":"氧化镝(99.99%)","suppliers":["北方稀土(600111)","盛和资源(600392)","广晟有色(600259)"],"foreign":"中国垄断,出口管制","gap":"独特地位","domestic_pct":"95%","hidden_gem":"盛和资源(600392)——全球稀土资源布局最广,格陵兰+美国+越南矿权"},
      {"material":"氧化钇(5N高纯)","suppliers":["北方稀土(600111)","五矿稀土(000831)"],"foreign":"中国垄断","gap":"独特地位","domestic_pct":"90%"}
    ]},
  ]
},

"固态电池": {
  "components": [
    {"name":"硫化物固态电解质","cost_pct":"35%","materials":[
      {"material":"硫化锂(Li2S,4N+)","suppliers":["天赐材料(002709)","赣锋锂业(002460)","上海洗霸(603200)"],"foreign":"日本出光兴产/三井金属","gap":"致命","domestic_pct":"<5%","hidden_gem":"上海洗霸(603200)——从工业水处理跨界,硫化锂中试线投产,市值仅50亿"},
      {"material":"五硫化二磷(P2S5,4N+)","suppliers":["兴发集团(600141)","云天化(600096)"],"foreign":"日本化学/美国Sigma","gap":"较大","domestic_pct":"10%","hidden_gem":"兴发集团(600141)——磷化工龙头跨界高纯磷化物,市值仅200亿"},
      {"material":"手套箱(水<0.1ppm)","suppliers":["米开罗那(未上市)"],"foreign":"德国MBraun","gap":"较大","domestic_pct":"5%","hidden_gem":"先导智能(300450)——锂电设备龙头,配合固态客户开发干燥房"}
    ]},
    {"name":"氧化物固态电解质(LLZO/LLTO)","cost_pct":"20%","materials":[
      {"material":"氧化镧(5N高纯)","suppliers":["北方稀土(600111)","盛和资源(600392)"],"foreign":"中国主导","gap":"中等","domestic_pct":"60%"},
      {"material":"氧化锆(纳米稳定ZrO2)","suppliers":["国瓷材料(300285)","凯盛科技(600552)"],"foreign":"日本东曹/第一稀元素","gap":"较大","domestic_pct":"30%","hidden_gem":"凯盛科技(600552)——电熔氧化锆龙头,从玻璃跨界固态电解质"}
    ]},
    {"name":"锂金属负极(超薄<20μm)","cost_pct":"15%","materials":[
      {"material":"超薄锂箔(挤压/蒸镀)","suppliers":["天赐材料(002709)","中国锂业(未上市)"],"foreign":"美国Livent/Albemarle","gap":"严重","domestic_pct":"5%","hidden_gem":"恩捷股份(002812)——锂电隔膜龙头,布局锂金属负极涂覆,市值300亿"}
    ]},
  ]
},

"低空经济": {
  "components": [
    {"name":"eVTOL电机(高功率密度)","cost_pct":"20%","materials":[
      {"material":"钐钴永磁(Sm2Co17,耐高温)","suppliers":["中科三环(000970)","金力永磁(300748)"],"foreign":"日本TDK/日立金属","gap":"较大","domestic_pct":"25%","hidden_gem":"正海磁材(300224)——钐钴永磁量产,电动航空核心材料"},
      {"material":"碳纤维复合材料(T800+)","suppliers":["中复神鹰(688295)","光威复材(300699)"],"foreign":"日本东丽/美国Hexcel","gap":"严重","domestic_pct":"15%","hidden_gem":"中复神鹰(688295)——干喷湿纺碳纤维,国内唯一千吨级T1000产线"}
    ]},
    {"name":"适航认证TC(时间垄断)","cost_pct":"N/A","materials":[
      {"material":"飞控系统(冗余设计)","suppliers":["中航智(未上市)","纵横股份(688070)"],"foreign":"Honeywell/Collins","gap":"严重","domestic_pct":"10%","hidden_gem":"纵横股份(688070)——工业无人机飞控,从测绘到eVTOL"},
      {"material":"空域管理系统(UOM/UTM)","suppliers":["莱斯信息(688631)","川大智胜(002253)"],"foreign":"美国AirMap/瑞士Skyguide","gap":"较大","domestic_pct":"20%","hidden_gem":"莱斯信息(688631)——民航二所孵化,低空空管系统国家唯一供应商"}
    ]},
  ]
},
}

# ═══════════════════════════════════════════════════════════
# 数据验证层 (a-stock-data)
# ═══════════════════════════════════════════════════════════

def tencent_batch(codes):
    """批量行情"""
    prefixed = []
    for c in codes:
        if c.startswith(("6","9")): prefixed.append(f"sh{c}")
        elif c.startswith("8"): prefixed.append(f"bj{c}")
        else: prefixed.append(f"sz{c}")
    url = "https://qt.gtimg.cn/q=" + ",".join(prefixed)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        data = resp.read().decode("gbk")
    except:
        return {}
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
            "pe_ttm": float(vals[39]) if vals[39] else 0,
            "mcap_yi": float(vals[44]) if vals[44] else 0,
        }
    return result

# ═══════════════════════════════════════════════════════════
# 挖掘引擎
# ═══════════════════════════════════════════════════════════

def score_hidden_gem(material_info):
    """评分：越冷门越高分"""
    score = 0
    gap = material_info.get("gap","")
    if gap == "致命": score += 30
    elif gap == "严重": score += 22
    elif gap == "较大": score += 14
    elif gap == "中等": score += 7

    pct = int(str(material_info.get("domestic_pct","50")).replace("%","").replace("<","").replace(">",""))
    if pct <= 5: score += 25
    elif pct <= 15: score += 18
    elif pct <= 30: score += 10

    if material_info.get("hidden_gem"): score += 20  # 有隐藏标的加分
    if material_info.get("hidden_reason"): score += 10  # 有反直觉逻辑再加分

    return min(score, 100)

def hunt_sector(sector_name):
    """对单板块执行Serenity深度挖掘"""
    if sector_name not in DEEP_CHAIN:
        print(f"  ⚠️  「{sector_name}」暂无深度拆解数据")
        return []

    chain = DEEP_CHAIN[sector_name]
    findings = []

    # 收集所有标的代码
    all_codes = set()
    for comp in chain["components"]:
        for mat in comp["materials"]:
            for s in mat.get("suppliers",[]):
                code = s.split("(")[-1].rstrip(")") if "(" in s else ""
                if code.isdigit() and len(code)==6: all_codes.add(code)

    # 拉取行情
    quotes = tencent_batch(list(all_codes))

    # 逐组件分析
    for comp in chain["components"]:
        for mat in comp["materials"]:
            gem = mat.get("hidden_gem","")
            reason = mat.get("hidden_reason","")
            gap = mat.get("gap","")

            stocks_data = []
            for s in mat.get("suppliers",[]):
                code = s.split("(")[-1].rstrip(")") if "(" in s else ""
                name = s.split("(")[0] if "(" in s else s
                q = quotes.get(code, {})
                stocks_data.append({
                    "name": name, "code": code,
                    "price": q.get("price",0), "pe": q.get("pe_ttm",0),
                    "mcap_yi": q.get("mcap_yi",0), "change": q.get("change_pct",0),
                })

            score = score_hidden_gem(mat)
            # 有隐藏标的才是"发现级"
            is_discovery = bool(gem and gap in ("致命","严重"))

            findings.append({
                "component": comp["name"], "material": mat["material"],
                "cost_pct": comp.get("cost_pct",""),
                "gap": gap, "domestic_pct": mat.get("domestic_pct",""),
                "foreign": mat.get("foreign",""),
                "serenity_score": score,
                "is_discovery": is_discovery,
                "hidden_gem": gem, "hidden_reason": reason,
                "stocks": stocks_data,
            })

    findings.sort(key=lambda x: x["serenity_score"], reverse=True)
    return findings

def generate_report(sector, findings):
    """生成Markdown报告"""
    discoveries = [f for f in findings if f["is_discovery"]]
    all_findings = findings

    lines = [
        f"# Serenity 深度挖掘：{sector}",
        f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "> 核心理念：不买机器人整机，买机器人离不开的东西。",
        "> 从下游需求 → 逆向拆解每个组件 → 找供应弹性最低的瓶颈 → 映射被忽视的上市公司。",
        "",
        f"## 🎯 发现级标的（{len(discoveries)}个被市场忽视的瓶颈）",
        "",
    ]

    if discoveries:
        for i, d in enumerate(discoveries):
            stocks_str = "、".join([f"{s['name']}({s['code']})" for s in d["stocks"] if s["code"]])
            lines.append(f"### {i+1}. {d['material']}  [{d['serenity_score']}分 · {d['gap']}]")
            lines.append(f"**组件**: {d['component']}（成本占比{d.get('cost_pct','?')}）")
            lines.append(f"**海外垄断**: {d['foreign']}")
            lines.append(f"**国产化率**: {d['domestic_pct']}")
            lines.append(f"**🔍 隐藏标的**: {d['hidden_gem']}")
            lines.append(f"**💡 为什么被忽视**: {d['hidden_reason']}")
            lines.append(f"**相关公司**: {stocks_str}")
            lines.append("")
    else:
        lines.append("⚠️ 暂无发现级标的（已覆盖的瓶颈标的均已较知名）")
        lines.append("")

    lines.append("---")
    lines.append(f"## 📋 完整瓶颈清单（{len(all_findings)}项）")
    lines.append("")
    lines.append("| 得分 | 组件 | 瓶颈材料 | 严重度 | 国产化 | 隐藏标的 |")
    lines.append("|:----:|------|------|:----:|:----:|------|")
    for f in all_findings:
        gem_brief = f["hidden_gem"].split("——")[0] if f["hidden_gem"] else "-"
        lines.append(f"| {f['serenity_score']} | {f['component']} | {f['material']} | {f['gap']} | {f['domestic_pct']} | {gem_brief} |")

    lines.append("")
    lines.append("---")
    lines.append("⚠️ 非投资建议 | 仅供产业链研究参考 | Serenity方法论实践")

    return "\n".join(lines)

# ═══════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════

def main():
    if len(sys.argv) > 1 and sys.argv[1] != "--all":
        sectors = [sys.argv[1]]
    else:
        sectors = list(DEEP_CHAIN.keys())

    print(f"🔍 Serenity 供应链逆向挖掘")
    print(f"━" * 50)

    for sector in sectors:
        t0 = time.time()
        print(f"  ⛏️  拆解: {sector}...")
        findings = hunt_sector(sector)
        if not findings:
            continue

        report = generate_report(sector, findings)
        safe_name = sector.replace("/","-").replace("\\","-").replace(":","-")
        path = OUTPUT / f"serenity_{safe_name}.md"
        path.write_text(report, encoding="utf-8")

        discoveries = [f for f in findings if f["is_discovery"]]
        print(f"     ✅ {len(findings)}个瓶颈 | {len(discoveries)}个隐藏标的 | {time.time()-t0:.1f}s → {path.name}")

        # 打印TOP隐藏发现
        for d in discoveries[:3]:
            gem_name = d["hidden_gem"].split("——")[0] if d["hidden_gem"] else ""
            print(f"        💎 [{d['serenity_score']}分] {d['material']}: {gem_name}")

    print(f"━" * 50)
    print(f"📂 报告目录: {OUTPUT}")

if __name__ == "__main__":
    main()
