"""金额 / 税率 / 日期换算工具。

金额：数据库存整数「分」，API 层用「元」（float，2位小数）。
税率：数据库存整数「基点」（1300 = 13.00%），API 层用百分数（13.0）。
"""
from __future__ import annotations

import calendar
import re
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")


def yuan_to_cents(v) -> int | None:
    """元（可传 Decimal/str/int/float）→ 分。None / 空串 / 非法 → None。"""
    if v is None or v == "":
        return None
    try:
        d = Decimal(str(v)).quantize(CENT, rounding=ROUND_HALF_UP)
    except Exception:
        return None
    return int((d * 100).to_integral_value(rounding=ROUND_HALF_UP))


def cents_to_yuan(c: int | None) -> float | None:
    if c is None:
        return None
    return float(Decimal(c) / 100)


def pct_to_bp(v) -> int | None:
    """百分数 13.5 → 基点 1350。"""
    if v is None or v == "":
        return None
    try:
        return int((Decimal(str(v)) * 100).to_integral_value(rounding=ROUND_HALF_UP))
    except Exception:
        return None


def bp_to_pct(bp: int | None) -> float | None:
    if bp is None:
        return None
    return float(Decimal(bp) / 100)


def ratio_pct(num: int | None, den: int | None) -> float | None:
    """num/den × 100，保留1位小数。分母无效返回 None。"""
    if den is None or den == 0 or num is None:
        return None
    return float((Decimal(num) * 100 / Decimal(den)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def parse_money_text(v) -> float | None:
    """解析人写的金额文本："1,000,000.50" / "100万" / "￥12,000元" / 12.5 → 元(float)。"""
    if v is None or v == "":
        return None
    if isinstance(v, (int, float, Decimal)):
        return float(v)
    s = str(v).strip().replace(",", "").replace("，", "")
    s = re.sub(r"[￥¥元人民币币]|RMB|CNY", "", s, flags=re.I).strip()
    mult = 1.0
    m = re.search(r"(\d+(?:\.\d+)?)\s*万", s)
    if m:
        mult = 10000.0
        s = re.sub(r"万", "", s)
    elif re.search(r"\d\s*千", s):
        mult = 1000.0
        s = s.replace("千", "")
    s = s.strip()
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group()) * mult
    except Exception:
        return None


def parse_date_any(v) -> date | None:
    """解析常见日期表述 → date。支持 ISO / 2026年3月1日 / 2026/3/1 / 2026.3.1 / datetime / date。"""
    if v is None or v == "":
        return None
    if isinstance(v, date):
        return v
    s = str(v).strip()
    m = re.search(r"(\d{4})[年/\-.](\d{1,2})[月/\-.](\d{1,2})日?", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


def add_months(d: date, months: int) -> date:
    """日期加 N 个月（月末自动截断）。"""
    m0 = d.month - 1 + int(months)
    y = d.year + m0 // 12
    m = m0 % 12 + 1
    day = min(d.day, calendar.monthrange(y, m)[1])
    return date(y, m, day)


def days_between(a: date, b: date) -> int:
    return (b - a).days
