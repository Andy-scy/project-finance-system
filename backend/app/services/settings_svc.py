"""系统设置读写。AI Key 只保存在后端（数据库或环境变量），绝不发给前端明文。"""
from __future__ import annotations

import os

from sqlalchemy.orm import Session

from ..models import Setting

DEFAULTS: dict[str, str] = {
    "ai_base_url": "https://open.bigmodel.cn/api/paas/v4",
    "ai_api_key": "",
    "ai_model": "glm-4.6",
    "ai_vision_model": "glm-4.5v",
    "tax_mode": "excl_tax",          # excl_tax 默认按不含税收入计算利润 / incl_tax 按含税
    "reminder_days": "30,7,0",       # 质保金提前提醒天数
    "invoice_overdue_days": "30",    # 开票后视为"长期未回款"的天数
    "margin_alert_ratio": "0",       # 利润率低于该百分比时预警（0=仅亏损预警）
    "renewal_remind_days": "30",     # 合同到期前N天提醒续签
    "settlement_remind_days": "7",   # 付款节点预计结算前N天提醒
}

_INT_KEYS = {"invoice_overdue_days", "margin_alert_ratio", "renewal_remind_days", "settlement_remind_days"}


def ensure_defaults(db: Session):
    for k, v in DEFAULTS.items():
        if db.get(Setting, k) is None:
            db.add(Setting(key=k, value=v))
    db.commit()


def get_settings(db: Session) -> dict:
    """合并默认值与数据库值。AI Key 若数据库为空则回退环境变量 AI_API_KEY。"""
    rows = {r.key: r.value for r in db.query(Setting).all()}
    out = dict(DEFAULTS)
    out.update({k: v for k, v in rows.items() if v is not None})
    if not out.get("ai_api_key"):
        out["ai_api_key"] = os.environ.get("AI_API_KEY", "")
    for k in _INT_KEYS:
        try:
            out[k] = int(out.get(k) or 0)
        except Exception:
            out[k] = int(DEFAULTS.get(k, "0"))
    out["reminder_days"] = _parse_reminder_days(out.get("reminder_days"))
    return out


def _parse_reminder_days(v) -> list[int]:
    if isinstance(v, list):
        return v
    try:
        days = sorted({int(x) for x in str(v).replace("，", ",").split(",") if str(x).strip()}, reverse=True)
        return days or [30, 7, 0]
    except Exception:
        return [30, 7, 0]


def save_settings(db: Session, data: dict):
    """保存设置。ai_api_key 传 None 或 '********' 表示不修改。"""
    for k, v in data.items():
        if k not in DEFAULTS:
            continue
        if k == "ai_api_key" and (v is None or v == "********"):
            continue
        row = db.get(Setting, k)
        value = str(v) if v is not None else ""
        if row is None:
            db.add(Setting(key=k, value=value))
        else:
            row.value = value
    db.commit()


def masked(settings: dict) -> dict:
    """输出给前端的脱敏视图。"""
    out = dict(settings)
    key = out.get("ai_api_key") or ""
    out["ai_api_key"] = ("********" if key else "")
    out["ai_api_key_hint"] = (key[:4] + "****" + key[-4:]) if len(key) > 8 else ("已配置" if key else "")
    out["reminder_days"] = ",".join(str(x) for x in out.get("reminder_days", []))
    return out
