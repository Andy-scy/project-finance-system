"""提醒中心数据源：合同续签 / 工程款结算 / 质保金到期。

供前端全屏提醒弹窗与顶部铃铛使用，按公司过滤，全部实时计算。
"""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from ..models import Project
from .calc import compute_project, load_context
from .settings_svc import get_settings

MAX_PER_LIST = 50  # 每类最多返回条数，超出只计数


def _item(p: Project, level: str, title: str, detail: str, date_str: str | None = None) -> dict:
    return {
        "project_id": p.id,
        "project_name": p.name,
        "level": level,          # danger / warning
        "title": title,
        "detail": detail,
        "date": date_str,
    }


def build_reminders(db: Session, company_id: int | None = None, today: date | None = None) -> dict:
    settings = get_settings(db)
    today = today or date.today()
    renewal_days = int(settings.get("renewal_remind_days", 30) or 30)
    settlement_days = int(settings.get("settlement_remind_days", 7) or 7)

    q = db.query(Project)
    if company_id:
        q = q.filter(Project.company_id == company_id)

    renewals: list[dict] = []
    settlements: list[dict] = []
    warranties: list[dict] = []

    for p in q.all():
        cp = compute_project(load_context(db, p), settings)

        # ── 1. 合同续签（仅未开始/进行中的有效合同）──────────────
        c = p.contract
        end = (c.contract_end_date if c else None) or p.end_date
        if end and p.status in ("未开始", "进行中"):
            days = (end - today).days
            if days < 0:
                renewals.append(_item(
                    p, "danger", "合同已到期未续签",
                    f"合同已于 {end.isoformat()} 到期 {-days} 天，请尽快办理续签，"
                    f"或把项目状态调整为已完成/已结算/已关闭。", end.isoformat()))
            elif days <= renewal_days:
                renewals.append(_item(
                    p, "danger" if days <= 7 else "warning", "合同即将到期，请安排续签",
                    f"合同将于 {end.isoformat()} 到期（还有 {days} 天），请提前与客户确认续签意向。",
                    end.isoformat()))

        # ── 2. 工程款结算（付款节点：临期 + 逾期未收全）──────────
        for s in cp.get("schedules", []):
            if not s.get("expected_date") or s.get("status") == "已到账":
                continue
            exp = date.fromisoformat(s["expected_date"])
            days = (exp - today).days
            amount = s.get("amount") or 0
            if days < 0:
                settlements.append(_item(
                    p, "danger", "工程款结算已逾期",
                    f"节点「{s['name']}」原定 {s['expected_date']} 结算 {amount:,.2f} 元，"
                    f"已逾期 {-days} 天未收全，请尽快催收。", s["expected_date"]))
            elif days <= settlement_days:
                settlements.append(_item(
                    p, "warning", "工程款即将到结算日",
                    f"节点「{s['name']}」预计 {s['expected_date']} 结算 {amount:,.2f} 元"
                    f"（还有 {days} 天），请提前确认结算条件。", s["expected_date"]))

        # ── 3. 质保金到期 ────────────────────────────────────────
        w = cp.get("warranty") or {}
        if w.get("amount"):
            if w.get("status") == "已到期未到账":
                warranties.append(_item(
                    p, "danger", "质保金已到期未到账",
                    f"质保金 {w['amount']:,.2f} 元，预计到账日 {w.get('expected_date') or '—'}，"
                    f"已逾期 {-(w.get('days_to_due') or 0)} 天。", w.get("expected_date")))
            elif w.get("status") == "即将到账":
                warranties.append(_item(
                    p, "warning", "质保金即将到账",
                    f"质保金 {w['amount']:,.2f} 元，预计 {w.get('expected_date') or '—'} 到账"
                    f"（还有 {w.get('days_to_due')} 天）。", w.get("expected_date")))

    def _sort(lst):
        lst.sort(key=lambda x: (0 if x["level"] == "danger" else 1, x.get("date") or "9999"))
        return lst

    _sort(renewals)
    _sort(settlements)
    _sort(warranties)
    counts = {
        "renewals": len(renewals),
        "settlements": len(settlements),
        "warranties": len(warranties),
    }
    return {
        "renewals": renewals[:MAX_PER_LIST],
        "settlements": settlements[:MAX_PER_LIST],
        "warranties": warranties[:MAX_PER_LIST],
        "counts": counts,
        "total": counts["renewals"] + counts["settlements"] + counts["warranties"],
    }
