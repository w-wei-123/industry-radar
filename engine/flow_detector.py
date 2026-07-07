#!/usr/bin/env python3
"""
资金真实性检测引擎
不依赖平台的大小单分类（可以被拆单骗），而是用无法造假的指标判断进出货：
- 换手率vs价格背离度
- 高开低走/低开高走
- 量价背离
- 连涨/连跌后的换手异常

用法: python flow_detector.py <股票代码> [--days 5]
输出: 资金真实性评分 0-100 + 判断结论
"""

import sys, io, json, urllib.request, re
from datetime import date, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# ── 数据获取 ──
def get_kline(code, days=30):
    """从腾讯获取日K线（免费，稳定）"""
    if code.startswith(("6", "9")):
        prefixed = f"sh{code}"
    else:
        prefixed = f"sz{code}"
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={prefixed},day,,,{days+5},qfq"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://gu.qq.com/"})
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode("utf-8"))
        klines_raw = data["data"][prefixed].get("qfqday", data["data"][prefixed].get("day", []))
        if not klines_raw:
            return []
        result = []
        for k in klines_raw[-days:]:
            result.append({
                "date": k[0],
                "open": float(k[1]),
                "close": float(k[2]),
                "high": float(k[3]),
                "low": float(k[4]),
                "volume": int(float(k[5])),
                "amount": 0,
                "turnover": 0,
                "pre_close": float(k[2]) if len(result) == 0 else result[-1]["close"],
            })
        return result
    except Exception as e:
        print(f"  ⚠️ 获取K线失败: {e}")
        return []


def get_realtime(code):
    """腾讯实时行情"""
    if code.startswith(("6", "9")):
        prefixed = f"sh{code}"
    else:
        prefixed = f"sz{code}"
    url = f"https://qt.gtimg.cn/q={prefixed}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        data = resp.read().decode("gbk")
        if "=" not in data:
            return None
        vals = data.split('"')[1].split("~")
        if len(vals) < 53:
            return None
        return {
            "name": vals[1],
            "price": float(vals[3]) if vals[3] else 0,
            "change_pct": float(vals[32]) if vals[32] else 0,
            "high": float(vals[33]) if vals[33] else 0,
            "low": float(vals[34]) if vals[34] else 0,
            "open": float(vals[5]) if vals[5] else 0,
            "pre_close": float(vals[4]) if vals[4] else 0,
            "vol_ratio": float(vals[49]) if vals[49] else 0,
            "turnover_pct": float(vals[38]) if vals[38] else 0,
            "amount": float(vals[37]) if vals[37] else 0,
        }
    except:
        return None


# ── 检测函数 ──
def detect_gap_trap(code, realtime):
    """检测高开诱多：高开>3% 但当前价<开盘价且跌超2%"""
    if not realtime or realtime["pre_close"] == 0:
        return 0, ""
    gap = (realtime["open"] - realtime["pre_close"]) / realtime["pre_close"] * 100
    fade = (realtime["price"] - realtime["open"]) / realtime["open"] * 100
    if gap > 3 and fade < -2:
        score = min(30, abs(fade) * 6)
        return score, f"高开+{gap:.1f}%后回落{fade:.1f}% → 大概率诱多出货"
    elif gap > 3 and fade < 0:
        return 10, f"高开+{gap:.1f}%小幅回落{fade:.1f}% → 有出货嫌疑但不强"
    elif gap < -2 and realtime["change_pct"] > 2:
        return 10, f"低开{gap:.1f}%后拉升+{realtime['change_pct']:.1f}% → 可能洗盘吸筹"
    return 0, ""


def detect_turnover_diverge(klines, realtime=None):
    """量vs价格背离：量暴增+价格横盘/微跌 = 出货。优先用实时换手，fallback到K线量"""
    if len(klines) < 5:
        return 0, ""

    today = klines[-1]
    prev5 = klines[-6:-1] if len(klines) >= 6 else klines[:-1]
    price_change_5d = (today["close"] - klines[-6]["close"]) / klines[-6]["close"] * 100 if len(klines) >= 6 else 0

    # 用实时换手做检测
    if realtime and realtime.get("turnover_pct", 0) > 0:
        today_turnover = realtime["turnover_pct"]
    else:
        today_turnover = today.get("turnover", 0)

    if today_turnover == 0:
        # fallback: 用成交量比值
        avg_vol_prev = sum(k["volume"] for k in prev5) / len(prev5) if prev5 else today["volume"]
        if avg_vol_prev == 0:
            return 0, ""
        vol_ratio = today["volume"] / avg_vol_prev
        if vol_ratio > 3 and abs(price_change_5d) < 2:
            return 20, f"成交量{vol_ratio:.1f}x暴增但价格仅变{price_change_5d:+.1f}% → 对倒出货特征明显"
        elif vol_ratio > 2 and abs(price_change_5d) < 3:
            return 12, f"量{vol_ratio:.1f}x放大+价格微动 → 有对倒嫌疑"
        return 0, ""

    # 换手暴增但价格不涨
    if today_turnover > 20 and abs(price_change_5d) < 2:
        return 25, f"换手{today_turnover:.1f}%暴增但价格仅变{price_change_5d:+.1f}% → 对倒出货特征明显"
    elif today_turnover > 12 and abs(price_change_5d) < 3:
        return 15, f"换手{today_turnover:.1f}%偏高+价格微动 → 有对倒嫌疑"
    elif today_turnover > 10 and price_change_5d < -3:
        return 10, f"换手{today_turnover:.1f}%+价格下跌{price_change_5d:.1f}% → 放量下跌需警惕"
    return 0, ""


def detect_volume_price(klines):
    """量价背离：量在放大但价格不创新高"""
    if len(klines) < 10:
        return 0, ""
    recent5 = klines[-5:]
    prev5 = klines[-10:-5]
    avg_vol_recent = sum(k["volume"] for k in recent5) / 5
    avg_vol_prev = sum(k["volume"] for k in prev5) / 5
    max_price_recent = max(k["high"] for k in recent5)
    max_price_prev = max(k["high"] for k in prev5)

    if avg_vol_prev == 0:
        return 0, ""

    vol_ratio = avg_vol_recent / avg_vol_prev

    if vol_ratio > 1.5 and max_price_recent < max_price_prev * 1.01:
        return 15, f"近5日均量{vol_ratio:.1f}x但价格未创新高 → 放量滞涨=出货"
    elif vol_ratio > 2.0 and max_price_recent <= max_price_prev:
        return 20, f"量能翻倍但高点下移 → 主力边拉边撤"
    return 0, ""


def detect_limit_up_quality(code, realtime, klines):
    """涨停板质量：封板时间/封单量/开板次数"""
    if not realtime or not klines:
        return 0, ""
    today = klines[-1] if klines else None
    if not today:
        return 0, ""

    change = realtime["change_pct"]
    turnover = realtime["turnover_pct"]

    if change > 9.5 and turnover > 15:
        return 20, f"涨停但换手{turnover:.1f}% → 涨停板出货嫌疑（烂板）"
    elif change > 9.5 and turnover > 8:
        return 10, f"涨停换手{turnover:.1f}%偏高 → 关注次日是否高开低走"

    if today["high"] >= today["close"] * 1.08 and change < 2:
        return 25, f"盘中触及涨停后回落至仅{change:+.1f}% → 经典涨停板出货"

    return 0, ""


# ══════════════════════════════════════════════════════════
# 高级检测：量价背离 · OBV · MFI · Wyckoff · 尾盘砸盘
# 这些抓"聪明出货"——涨不停的票里悄悄撤退
# ══════════════════════════════════════════════════════════

def calc_obv(klines):
    """计算 OBV (On-Balance Volume) 序列"""
    obv = [0]
    for i in range(1, len(klines)):
        if klines[i]["close"] > klines[i-1]["close"]:
            obv.append(obv[-1] + klines[i]["volume"])
        elif klines[i]["close"] < klines[i-1]["close"]:
            obv.append(obv[-1] - klines[i]["volume"])
        else:
            obv.append(obv[-1])
    return obv


def calc_mfi(klines, period=14):
    """计算 MFI (Money Flow Index)"""
    if len(klines) < period + 1:
        return []
    mfi = []
    for i in range(period, len(klines)):
        pos_flow = 0
        neg_flow = 0
        for j in range(i - period + 1, i + 1):
            tp = (klines[j]["high"] + klines[j]["low"] + klines[j]["close"]) / 3
            if tp > 0:
                mf = tp * (klines[j]["volume"] if klines[j]["volume"] > 0 else 0)
            else:
                mf = 0
            prev_tp = (klines[j-1]["high"] + klines[j-1]["low"] + klines[j-1]["close"]) / 3
            if tp > prev_tp:
                pos_flow += mf
            elif tp < prev_tp:
                neg_flow += mf
        if neg_flow == 0:
            mfi.append(100)
        else:
            mr = pos_flow / neg_flow
            mfi.append(100 - (100 / (1 + mr)))
    return mfi


def detect_obv_divergence(klines):
    """OBV 背离检测 —— 抓"涨不停的票里聪明钱在撤"

    看跌背离: 价格创新高，但 OBV 不创新高 → 量能衰竭 = 出货
    看涨背离: 价格创新低，但 OBV 不创新低 → 量能积聚 = 吸筹
    """
    if len(klines) < 20:
        return 0, ""

    obv = calc_obv(klines)

    # 找近期价格高点（近20日）
    recent_prices = [k["close"] for k in klines[-20:]]
    recent_obv = obv[-20:]

    max_price_idx = recent_prices.index(max(recent_prices))
    max_obv_idx = recent_obv.index(max(recent_obv))

    # 价格高点在过去5天内(最近)，OBV高点在更早
    if max_price_idx >= len(recent_prices) - 6 and max_obv_idx < max_price_idx - 2:
        price_rise = (recent_prices[-1] - recent_prices[0]) / recent_prices[0] * 100
        if price_rise > 5:
            return 30, f"价格{price_rise:+.1f}%但OBV未确认新高 → 量价顶背离，聪明钱在涨势中撤退"

    # 也检查10日短周期
    if len(klines) >= 10:
        recent10_p = [k["close"] for k in klines[-10:]]
        recent10_obv = obv[-10:]
        if recent10_p[-1] >= max(recent10_p[:-3]) and recent10_obv[-1] < max(recent10_obv[:-3]) * 0.95:
            return 20, f"短线价格高位但OBV回落 → 短期动能衰竭"

    # 看涨背离(吸筹) —— 不是出货，但值得标记
    min_price_idx = recent_prices.index(min(recent_prices))
    min_obv_idx = recent_obv.index(min(recent_obv))
    if min_price_idx >= len(recent_prices) - 6 and min_obv_idx < min_price_idx - 2:
        price_drop = (recent_prices[-1] - recent_prices[0]) / recent_prices[0] * 100
        if price_drop < -5:
            return -15, f"价格下跌但OBV未确认新低 → 可能洗盘吸筹（非出货）"

    return 0, ""


def detect_mfi_divergence(klines):
    """MFI 背离检测 —— 价格涨但资金在流出"""
    mfi = calc_mfi(klines)
    if len(mfi) < 10:
        return 0, ""

    recent_prices = [k["close"] for k in klines[-10:]]
    recent_mfi = mfi[-10:]

    # 价格走高但MFI走低 → 资金在流出的上涨
    price_trend = (recent_prices[-1] - recent_prices[0]) / recent_prices[0] * 100
    mfi_change = recent_mfi[-1] - recent_mfi[0]

    if price_trend > 3 and mfi_change < -5:
        return 25, f"价格+{price_trend:.1f}%但MFI{mfi_change:+.0f} → 资金背离，上涨缺乏真实买盘"

    # MFI极度超买(>80)后回落
    if max(recent_mfi) > 80 and recent_mfi[-1] < 60:
        return 15, f"MFI从{max(recent_mfi):.0f}跌至{recent_mfi[-1]:.0f} → 资金从超买区撤离"

    # MFI低于20 → 可能超卖
    if recent_mfi[-1] < 20 and price_trend < -5:
        return -10, f"MFI极度超卖({recent_mfi[-1]:.0f}) → 恐慌盘出尽，可能反弹"

    return 0, ""


def detect_wyckoff_distribution(klines, realtime):
    """Wyckoff 分布日检测 + 尾盘砸盘

    分布日特征:
    1. 收盘价在全天最低1/3区域 → 拉高后尾盘被砸
    2. 成交量放大但收盘弱势 → 有人在尾盘出货
    3. 连续出现分布日 → 主力在系统性减持
    """
    if len(klines) < 5:
        return 0, ""

    # 今天的收盘位置
    today = klines[-1]
    day_range = today["high"] - today["low"]
    if day_range == 0:
        return 0, ""

    close_position = (today["close"] - today["low"]) / day_range  # 0=收最低, 1=收最高

    # 检查近N天有多少"分布日"
    dist_days = 0
    for k in klines[-10:]:
        r = k["high"] - k["low"]
        if r == 0:
            continue
        cp = (k["close"] - k["low"]) / r
        # 收在最低1/3 = 尾盘被砸
        if cp < 0.33:
            dist_days += 1

    today_dist = close_position < 0.33

    if today_dist and realtime and realtime.get("vol_ratio", 1) > 1.5:
        return 20, f"放量+收在低位({close_position:.0%}) → 尾盘砸盘出货"

    if dist_days >= 4:
        return 30, f"近10日{dist_days}个分布日(收低位) → 系统性减持信号"

    if dist_days >= 3 and today_dist:
        return 20, f"近10日{dist_days}天尾盘弱势 → 主力在持续出货"

    # 上影线检测：冲高回落
    upper_shadow = (today["high"] - max(today["open"], today["close"])) / day_range
    if upper_shadow > 0.5 and realtime and realtime.get("vol_ratio", 1) > 1.3:
        return 15, f"长上影线{upper_shadow:.0%}+放量 → 拉高诱多后砸回"

    return 0, ""


def detect_volume_climax(klines):
    """成交量顶点检测 —— 天量之后缩量 = 动能耗尽

    一波上涨的最后阶段往往出现天量（散户蜂拥而入），
    随后成交量快速萎缩（没有新钱进来），价格开始横盘或下跌。
    """
    if len(klines) < 15:
        return 0, ""

    volumes = [k["volume"] for k in klines]
    max_vol_20d = max(volumes[-20:]) if len(volumes) >= 20 else max(volumes)
    today_vol = volumes[-1]
    avg_vol_5d = sum(volumes[-6:-1]) / 5 if len(volumes) >= 6 else today_vol

    if max_vol_20d == 0:
        return 0, ""

    # 天量出现在过去3-10天内，最近几天量在萎缩
    max_vol_idx = volumes[-20:].index(max_vol_20d) if len(volumes) >= 20 else 0
    max_vol_pos = len(volumes) - 20 + max_vol_idx if len(volumes) >= 20 else max_vol_idx

    days_since_climax = len(volumes) - 1 - max_vol_pos

    if 2 <= days_since_climax <= 8 and today_vol < max_vol_20d * 0.5:
        # 天量后缩量过半
        price_at_climax = klines[max_vol_pos]["close"]
        price_now = klines[-1]["close"]
        price_change = (price_now - price_at_climax) / price_at_climax * 100

        if price_change < -2:
            return 20, f"天量后{days_since_climax}日缩量过半+价格{price_change:+.1f}% → 量能枯竭，顶部确认"
        elif price_change < 2:
            return 12, f"天量后{days_since_climax}日缩量+价格横盘 → 动能衰竭中"

    # 今天是否是天量本身（散户冲进去）
    if today_vol >= max_vol_20d * 0.95 and today_vol > avg_vol_5d * 2.5:
        today_change = (klines[-1]["close"] - klines[-2]["close"]) / klines[-2]["close"] * 100 if len(klines) >= 2 else 0
        if today_change < 1:
            return 15, f"天量但价格仅变{today_change:+.1f}% → 巨量滞涨=有人在倒货"

    return 0, ""


def detect_completed_distribution(klines):
    """检测已经完成的出货——回头看40-60天内的"顶部分布"模式

    经典出货模式:
    1. 一段大幅上涨 (涨幅>30%)
    2. 顶部出现天量（散户涌入）
    3. 随后缩量下跌（没人接盘了）
    4. 当前价格已从高点回落 >15%

    这不是"现在在出货"，而是"已经出完了，目前在下跌段"
    """
    if len(klines) < 40:
        return 0, ""

    prices = [k["close"] for k in klines]
    volumes = [k["volume"] for k in klines]

    # 找过去60天内的最高点
    lookback = min(60, len(klines))
    peak_price = max(k["high"] for k in klines[-lookback:])
    peak_idx = next(i for i in range(len(klines)-lookback, len(klines)) if klines[i]["high"] == peak_price)
    days_since_peak = len(klines) - 1 - peak_idx

    # 从高点回撤
    current_price = prices[-1]
    drawdown = (current_price - peak_price) / peak_price * 100

    # 高点之前要有明显涨幅
    if peak_idx >= 20:
        pre_peak = klines[peak_idx - 20]["close"]
        rally = (peak_price - pre_peak) / pre_peak * 100
    else:
        rally = 0

    # 找到天量日（高点附近的成交量顶峰）
    vol_near_peak = volumes[max(0, peak_idx-5):min(len(volumes), peak_idx+6)]
    if not vol_near_peak:
        return 0, ""
    climax_vol = max(vol_near_peak)
    avg_vol_after = sum(volumes[peak_idx:]) / max(1, len(volumes[peak_idx:]))
    avg_vol_before = sum(volumes[max(0,peak_idx-20):peak_idx]) / max(1, 20)

    # 典型出货模式: 大涨 + 天量 + 缩量下跌
    if rally > 20 and drawdown < -15:
        vol_collapse = avg_vol_before > 0 and (avg_vol_after / avg_vol_before) < 0.7
        if vol_collapse:
            return 40, f"已完成出货: +{rally:.0f}%拉升→天量顶→缩量跌{drawdown:.0f}%（已过{days_since_peak}天）→ 主力高位已出，当前为下跌段"

    if rally > 30 and drawdown < -10 and avg_vol_after < avg_vol_before * 0.8:
        return 30, f"大概率已出货: +{rally:.0f}%涨后回撤{drawdown:.0f}%+缩量 → 当前是出货后的阴跌段"

    # 跌幅巨大但无前期大涨 → 可能是长期弱势，不算"出货"
    if drawdown < -25 and rally > 15:
        return 20, f"深度回撤{drawdown:.0f}%（高点{days_since_peak}天前）→ 主力大概率已离场"

    return 0, ""


def detect_continuous_abnormal(klines):
    """连续异动后换手异常：连续涨/跌停后换手率突然放大3x"""
    if len(klines) < 8:
        return 0, ""

    today = klines[-1]
    recent = klines[-6:-1]

    # 检测前期是否连续大涨
    up_streak = 0
    for k in reversed(recent):
        if k["close"] > k["open"] * 1.02:
            up_streak += 1
        else:
            break

    avg_prev_turnover = sum(k["turnover"] for k in klines[-8:-3]) / 5 if len(klines) >= 8 else today["turnover"]

    if up_streak >= 3 and today["turnover"] > avg_prev_turnover * 2.5:
        return 20, f"连涨{up_streak}日后换手{today['turnover']:.1f}%暴增 → 高位换手=出货窗口"

    # 连续涨停后的异常
    limit_up_count = sum(1 for k in recent if k["close"] >= k["pre_close"] * 1.095 if "pre_close" in k)
    if limit_up_count >= 2 and today["turnover"] > avg_prev_turnover * 2:
        return 25, f"连续{limit_up_count}个涨停后换手暴增 → 游资撤退信号强烈"

    return 0, ""


# ── 综合评估 ──
def analyze(code, days=30):
    """主分析函数"""
    realtime = get_realtime(code)
    klines = get_kline(code, max(days, 90))  # 至少90天，覆盖完成出货检测

    if not realtime or realtime["price"] == 0:
        return {"error": f"无法获取 {code} 实时行情", "score": -1}

    name = realtime["name"]
    findings = []
    total_score = 0

    # 1. 高开诱多检测
    score, msg = detect_gap_trap(code, realtime)
    if score > 0:
        findings.append(("高开诱多", score, msg))
        total_score += score

    # 2. 换手率背离
    if klines:
        score, msg = detect_turnover_diverge(klines, realtime)
        if score > 0:
            findings.append(("换手背离", score, msg))
            total_score += score

    # 3. 量价背离
    if klines:
        score, msg = detect_volume_price(klines)
        if score > 0:
            findings.append(("量价背离", score, msg))
            total_score += score

    # 4. 涨停板质量
    score, msg = detect_limit_up_quality(code, realtime, klines)
    if score > 0:
        findings.append(("涨停质量", score, msg))
        total_score += score

    # 5. 连续异动
    if klines:
        score, msg = detect_continuous_abnormal(klines)
        if score > 0:
            findings.append(("连续异动", score, msg))
            total_score += score

    # 6. OBV背离（高级）
    if klines:
        score, msg = detect_obv_divergence(klines)
        if score > 0:
            findings.append(("OBV背离", score, msg))
            total_score += score
        elif score < 0:
            findings.append(("OBV吸筹", -score, msg))

    # 7. MFI背离（高级）
    if klines:
        score, msg = detect_mfi_divergence(klines)
        if score > 0:
            findings.append(("MFI背离", score, msg))
            total_score += score
        elif score < 0:
            findings.append(("MFI超卖", -score, msg))

    # 8. Wyckoff分布日/尾盘砸盘（高级）
    if klines:
        score, msg = detect_wyckoff_distribution(klines, realtime)
        if score > 0:
            findings.append(("Wyckoff", score, msg))
            total_score += score

    # 9. 成交量顶点（高级）
    if klines:
        score, msg = detect_volume_climax(klines)
        if score > 0:
            findings.append(("量能顶点", score, msg))
            total_score += score

    # 10. 历史出货检测（高级）—— 看过去40-60天的顶部出货
    if klines:
        score, msg = detect_completed_distribution(klines)
        if score > 0:
            findings.append(("历史出货", score, msg))
            total_score += score

    # 综合判断
    if total_score >= 40:
        verdict = "🔴 高度疑似出货"
    elif total_score >= 20:
        verdict = "🟡 有出货嫌疑"
    elif total_score >= 8:
        verdict = "🟢 轻微异常"
    else:
        verdict = "✅ 未检测到出货信号"

    total_score = min(100, total_score)

    return {
        "code": code,
        "name": name,
        "price": realtime["price"],
        "change_pct": realtime["change_pct"],
        "turnover": realtime["turnover_pct"],
        "vol_ratio": realtime["vol_ratio"],
        "score": total_score,
        "verdict": verdict,
        "findings": sorted(findings, key=lambda x: x[1], reverse=True),
        "note": "注意: 本检测基于无法造假的技术指标（换手率背离/高开低走/量价异常），不依赖平台主力净流入数据。但无法100%识别拆单出货和L2级别操纵。"
    }


# ── 输出 ──
def main():
    if len(sys.argv) < 2:
        print("用法: python flow_detector.py <股票代码> [股票代码2 ...]")
        print("示例: python flow_detector.py 002520 002137")
        return

    codes = sys.argv[1:]
    for code in codes:
        code = code.strip().replace(".SZ", "").replace(".SH", "").replace("sz", "").replace("sh", "")
        result = analyze(code)
        print()
        print("=" * 55)
        print(f"  {result.get('name', code)}({code})  现价: {result.get('price', '-')}  涨跌: {result.get('change_pct', 0):+.1f}%")
        print(f"  换手: {result.get('turnover', 0):.1f}%  量比: {result.get('vol_ratio', 0):.2f}")
        print(f"  出货风险评分: {result['score']}/100  →  {result['verdict']}")
        if result.get("findings"):
            print("  检测信号:")
            for cat, s, msg in result["findings"]:
                print(f"    [{cat}] +{s}分: {msg}")
        print(f"  {result.get('note', '')}")


if __name__ == "__main__":
    main()
