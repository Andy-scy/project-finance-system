"""财务计算引擎（程序实时计算，不落库）。

所有内部运算使用整数「分」，输出统一转换为「元」。
原则：原始录入数据与计算数据分离；计算结果永远由本模块推导。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from ..config import DIRECT_CATEGORIES, INDIRECT_CATEGORIES
from ..models import Contract, CostItem, Invoice, PaymentRecord, PaymentSchedule, Project
from .money import add_months, bp_to_pct, cents_to_yuan, ratio_pct
from .settings_svc import get_settings


def derive_tax(total_cents: int | None, tax_rate_bp: int | None):
    """含税额 + 税率 → (不含税额, 税额)。整数分，四舍五入到分。"""
    if total_cents is None or tax_rate_bp is None:
        return None, None
    excl = int(
        (Decimal(total_cents) * 10000 / Decimal(10000 + tax_rate_bp))
        .quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )
    return excl, total_cents - excl


@dataclass
class ProjectContext:
    project: Project
    contract: Contract | None
    schedules: list[PaymentSchedule] = field(default_factory=list)
    payments: list[PaymentRecord] = field(default_factory=list)
    invoices: list[Invoice] = field(default_factory=list)
    costs: list[CostItem] = field(default_factory=list)


def load_context(db: Session, project: Project) -> ProjectContext:
    return ProjectContext(
        project=project,
        contract=project.contract,
        schedules=sorted(project.schedules, key=lambda s: (s.sort_order, s.id)),
        payments=sorted(project.payments, key=lambda r: (r.payment_date, r.id)),
        invoices=sorted(project.invoices, key=lambda i: (i.issue_date, i.id)),
        costs=sorted(project.costs, key=lambda c: (c.cost_date, c.id)),
    )


def _schedule_rows(ctx: ProjectContext) -> list[dict]:
    rows = []
    for s in ctx.schedules:
        pays = [r for r in ctx.payments if r.schedule_id == s.id]
        received = sum(r.amount_cents for r in pays)
        plan = s.amount_cents
        actual_date = None
        status = "未到账"
        if plan is not None and plan > 0:
            if received >= plan:
                status = "已到账"
                cum = 0
                for r in pays:  # 找到收满那天
                    cum += r.amount_cents
                    if cum >= plan:
                        actual_date = r.payment_date
                        break
            elif received > 0:
                status = "部分到账"
        else:
            if received > 0:
                status = "已到账"
                actual_date = pays[-1].payment_date if pays else None
        rows.append({
            "id": s.id,
            "name": s.name or "未命名节点",
            "ratio_pct": bp_to_pct(s.ratio_bp),
            "amount": cents_to_yuan(plan),
            "expected_date": s.expected_date.isoformat() if s.expected_date else None,
            "is_warranty": bool(s.is_warranty),
            "sort_order": s.sort_order,
            "note": s.note,
            "received": cents_to_yuan(received),
            "pending": cents_to_yuan(max(plan - received, 0)) if plan is not None else None,
            "status": status,
            "actual_date": actual_date.isoformat() if actual_date else None,
            "overdue": bool(
                s.expected_date and status != "已到账" and s.expected_date < date.today()
            ),
        })
    return rows


def _warranty_info(ctx: ProjectContext, contract_headline: int | None, schedules: list[dict]) -> dict:
    c = ctx.contract
    info = {
        "amount": None, "ratio_pct": None, "months": None, "start_date": None,
        "expected_date": None, "actual_date": None, "received": None,
        "status": "日期未知", "days_to_due": None, "reminder_days": None,
    }
    if c is None:
        return info
    w_sched = next((s for s in ctx.schedules if s.is_warranty), None)
    amount = c.warranty_amount_cents
    if amount is None and c.warranty_ratio_bp is not None and contract_headline:
        amount = int((Decimal(contract_headline) * c.warranty_ratio_bp / 10000).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if amount is None and w_sched is not None:
        amount = w_sched.amount_cents
    expected = c.warranty_expected_date
    if expected is None and c.warranty_months:
        start = c.warranty_start_date or ctx.project.end_date or ctx.project.start_date
        if start:
            expected = add_months(start, c.warranty_months)
    received_cents = sum(
        r.amount_cents for r in ctx.payments
        if r.type == "质保金" or (w_sched is not None and r.schedule_id == w_sched.id)
    )
    actual = c.warranty_actual_date
    if actual is None and amount and received_cents >= amount:
        pays = [r for r in ctx.payments if r.type == "质保金" or (w_sched and r.schedule_id == w_sched.id)]
        cum = 0
        for r in pays:
            cum += r.amount_cents
            if cum >= amount:
                actual = r.payment_date
                break
    days_to_due = (expected - date.today()).days if expected else None
    settings_reminder = ctx._settings.get("reminder_days", [30, 7, 0]) if hasattr(ctx, "_settings") else [30, 7, 0]
    window = max(settings_reminder) if settings_reminder else 30
    if actual or (amount is not None and received_cents >= amount and amount and amount > 0):
        status = "已到账"
    elif expected is None:
        status = "日期未知"
    elif days_to_due < 0:
        status = "已到期未到账"
    elif days_to_due <= window:
        status = "即将到账"
    else:
        status = "未到账"
    info.update({
        "amount": cents_to_yuan(amount),
        "ratio_pct": bp_to_pct(c.warranty_ratio_bp),
        "months": c.warranty_months,
        "start_date": c.warranty_start_date.isoformat() if c.warranty_start_date else None,
        "expected_date": expected.isoformat() if expected else None,
        "actual_date": actual.isoformat() if actual else None,
        "received": cents_to_yuan(received_cents),
        "status": status,
        "days_to_due": days_to_due,
        "reminder_days": settings_reminder if hasattr(ctx, "_settings") else [30, 7, 0],
    })
    return info


def _recovery_info(ctx: ProjectContext, total_cost_cents: int | None) -> dict:
    info = {
        "recovered": False, "recovery_date": None, "days": None,
        "first_payment_date": None, "status": "尚未收回成本",
    }
    pays = ctx.payments
    if pays:
        info["first_payment_date"] = pays[0].payment_date.isoformat()
    if not total_cost_cents or total_cost_cents <= 0:
        info["status"] = "无成本数据"
        return info
    cum = 0
    for r in pays:
        cum += r.amount_cents
        if cum >= total_cost_cents:
            info["recovered"] = True
            info["recovery_date"] = r.payment_date.isoformat()
            if ctx.project.start_date:
                info["days"] = (r.payment_date - ctx.project.start_date).days
            info["status"] = f"已于 {r.payment_date.isoformat()} 收回成本"
            return info
    return info


def _consistency_issues(ctx: ProjectContext, vals: dict) -> list[dict]:
    issues: list[dict] = []
    headline = cents_to_yuan(vals["_headline_cents"])          # 元
    schedules = vals["_schedules_yuan"]                         # 元
    received = cents_to_yuan(vals["received_cents"]) or 0.0     # 元
    invoiced = cents_to_yuan(vals["invoiced_cents"]) or 0.0     # 元
    # 1. 付款节点合计 vs 合同金额（容差1分）
    plan_sum = sum(s["amount"] for s in schedules if s["amount"] is not None)
    n_plan = len([s for s in schedules if s["amount"] is not None])
    if headline and n_plan and plan_sum and abs(plan_sum - headline) > 0.01:
        diff = plan_sum - headline
        issues.append({
            "level": "warning", "code": "schedule_mismatch",
            "message": f"付款节点金额合计与合同金额不一致（相差 {diff:,.2f} 元），请检查。",
        })
    # 2. 已到账 > 合同金额
    if headline and received > headline:
        issues.append({
            "level": "danger", "code": "received_over",
            "message": f"累计到账金额已超过合同金额（超出 {received - headline:,.2f} 元）。",
        })
    # 3. 已开票 > 合同金额
    if headline and invoiced > headline:
        issues.append({
            "level": "warning", "code": "invoiced_over",
            "message": "已开票金额超过合同金额，请检查发票记录。",
        })
    # 4. 质保金 > 合同金额
    w = vals["warranty"]
    if headline and w.get("amount") and w["amount"] > headline:
        issues.append({
            "level": "warning", "code": "warranty_over",
            "message": "质保金金额超过合同金额，请检查。",
        })
    # 5. 税额自洽：不含税+税额 与 含税 不一致
    c = ctx.contract
    if c and c.total_amount_cents and c.excl_tax_amount_cents and c.tax_rate_bp is not None:
        d_excl, _ = derive_tax(c.total_amount_cents, c.tax_rate_bp)
        if d_excl is not None and abs(d_excl - c.excl_tax_amount_cents) > 100:  # 容差1元
            issues.append({
                "level": "warning", "code": "tax_inconsistent",
                "message": "不含税金额与（含税金额÷税率）计算结果不一致，请人工确认。",
            })
    # 6. 亏损
    revenue = vals.get("revenue_cents")
    cost = vals.get("total_cost_cents")
    if revenue and cost and cost > revenue:
        issues.append({
            "level": "danger", "code": "loss",
            "message": f"项目成本超过收入（亏损 {cents_to_yuan(cost - revenue):,.2f} 元），利润率为负。",
        })
    return issues


def compute_project(ctx: ProjectContext, settings: dict | None = None) -> dict:
    """计算单个项目的全部财务指标（输出金额单位：元）。"""
    settings = settings or {}
    ctx._settings = settings  # 供 _warranty_info 读取提醒窗口
    p = ctx.project
    c = ctx.contract
    today = date.today()

    total_cents = c.total_amount_cents if c else None
    excl_in = c.excl_tax_amount_cents if c else None
    rate_bp = c.tax_rate_bp if c else None
    d_excl, d_tax = derive_tax(total_cents, rate_bp)
    tax_cents = c.tax_amount_cents if c else None

    eff_excl = excl_in if excl_in is not None else d_excl
    eff_total = total_cents if total_cents is not None else (
        int((Decimal(eff_excl) * (10000 + rate_bp) / 10000).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        if eff_excl is not None and rate_bp is not None else None
    )
    headline = total_cents if total_cents is not None else excl_in  # 展示用"合同金额"

    tax_mode = settings.get("tax_mode", "excl_tax")
    revenue_cents = eff_excl if tax_mode == "excl_tax" else eff_total
    if revenue_cents is None:
        revenue_cents = eff_total if tax_mode == "excl_tax" else eff_excl

    received_cents = sum(r.amount_cents for r in ctx.payments)
    received_ratio = ratio_pct(received_cents, headline) if headline else None
    pending_cents = (headline - received_cents) if headline is not None else None

    invoiced_cents = sum(i.amount_cents for i in ctx.invoices)
    not_invoiced_cents = (headline - invoiced_cents) if headline is not None else None

    direct_cents = sum(x.amount_cents for x in ctx.costs if x.kind == "direct")
    indirect_cents = sum(x.amount_cents for x in ctx.costs if x.kind == "indirect")
    tax_cost_cents = sum(x.amount_cents for x in ctx.costs if x.kind == "tax")
    total_cost_cents = direct_cents + indirect_cents + tax_cost_cents

    profit_cents = (revenue_cents - total_cost_cents) if revenue_cents is not None else None
    margin = ratio_pct(profit_cents, revenue_cents) if profit_cents is not None and revenue_cents else None

    direct_by_cat: dict[str, int] = {}
    indirect_by_cat: dict[str, int] = {}
    tax_by_cat: dict[str, int] = {}
    for x in ctx.costs:
        if x.kind == "direct":
            bucket = direct_by_cat
        elif x.kind == "tax":
            bucket = tax_by_cat
        else:
            bucket = indirect_by_cat
        bucket[x.category or "其他"] = bucket.get(x.category or "其他", 0) + x.amount_cents

    schedules = _schedule_rows(ctx)
    last_pay = ctx.payments[-1].payment_date.isoformat() if ctx.payments else None
    next_expected = next(
        (s["expected_date"] for s in schedules if s["expected_date"] and s["status"] != "已到账"),
        None,
    )

    vals = {
        "_headline_cents": headline,
        "_schedules_yuan": schedules,
        "received_cents": received_cents,
        "invoiced_cents": invoiced_cents,
        "total_cost_cents": total_cost_cents,
        "revenue_cents": revenue_cents,
    }
    warranty = _warranty_info(ctx, headline, schedules)
    vals["warranty"] = warranty
    recovery = _recovery_info(ctx, total_cost_cents)
    issues = _consistency_issues(ctx, vals)

    invoice_status = "未开票"
    if headline and invoiced_cents >= headline:
        invoice_status = "已全额开票"
    elif invoiced_cents > 0:
        invoice_status = "部分开票"

    return {
        "project_id": p.id,
        "contract_amount": cents_to_yuan(headline),
        "total_amount": cents_to_yuan(total_cents),
        "excl_tax_amount": cents_to_yuan(eff_excl),
        "tax_amount": cents_to_yuan(tax_cents if tax_cents is not None else (d_tax if d_tax is not None else None)),
        "tax_rate": bp_to_pct(rate_bp),
        "revenue": cents_to_yuan(revenue_cents),
        "tax_mode": tax_mode,
        "received": cents_to_yuan(received_cents),
        "pending": cents_to_yuan(pending_cents),
        "received_ratio": received_ratio,          # 百分数
        "over_received": bool(pending_cents is not None and pending_cents < 0),
        "invoiced": cents_to_yuan(invoiced_cents),
        "not_invoiced": cents_to_yuan(not_invoiced_cents),
        "invoice_status": invoice_status,
        "last_payment_date": last_pay,
        "next_expected_date": next_expected,
        "direct_cost": cents_to_yuan(direct_cents),
        "indirect_cost": cents_to_yuan(indirect_cents),
        "tax_cost": cents_to_yuan(tax_cost_cents),
        "total_cost": cents_to_yuan(total_cost_cents),
        "direct_by_category": {k: cents_to_yuan(v) for k, v in direct_by_cat.items()},
        "indirect_by_category": {k: cents_to_yuan(v) for k, v in indirect_by_cat.items()},
        "tax_by_category": {k: cents_to_yuan(v) for k, v in tax_by_cat.items()},
        "profit": cents_to_yuan(profit_cents),
        "margin": margin,                           # 百分数，可为负
        "has_cost_data": bool(ctx.costs),
        "recovery": recovery,
        "warranty": warranty,
        "schedules": schedules,
        "schedule_plan_sum": sum(s["amount"] for s in schedules if s["amount"] is not None),
        "issues": issues,
        "_today": today.isoformat(),
    }


def compute_all(db: Session, project_ids: list[int] | None = None) -> dict[int, dict]:
    settings = get_settings(db)
    q = db.query(Project).order_by(Project.id)
    if project_ids is not None:
        q = q.filter(Project.id.in_(project_ids))
    out: dict[int, dict] = {}
    for p in q.all():
        out[p.id] = compute_project(load_context(db, p), settings)
    return out
