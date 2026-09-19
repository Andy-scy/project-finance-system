"""异常检测与年度 Dashboard 聚合。全部指标实时计算。"""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from ..models import Project
from .calc import compute_project, load_context
from .money import add_months
from .settings_svc import get_settings


def project_alerts(computed: dict, project: Project, settings: dict, today: date | None = None) -> list[dict]:
    """根据单个项目的计算结果生成异常/提醒列表。"""
    today = today or date.today()
    alerts: list[dict] = []
    pid, pname = project.id, project.name
    w = computed.get("warranty") or {}
    rec = computed.get("recovery") or {}

    def add(level: str, code: str, title: str, detail: str, sort_date=None):
        alerts.append({
            "level": level, "code": code, "project_id": pid, "project_name": pname,
            "title": title, "detail": detail,
            "sort_date": sort_date.isoformat() if isinstance(sort_date, date) else sort_date,
        })

    # ── 质保金提醒 ─────────────────────────────────────────────
    if w.get("amount"):
        if w.get("status") == "已到期未到账":
            add("danger", "warranty_overdue", "质保金已到期但未到账",
                f"质保金 {w['amount']:,.2f} 元，预计到账日 {w.get('expected_date','—')}，"
                f"已逾期 {-w['days_to_due']} 天。", w.get("expected_date"))
        elif w.get("status") == "即将到账":
            add("warning", "warranty_upcoming", "质保金即将到账",
                f"质保金 {w['amount']:,.2f} 元，预计 {w.get('expected_date','—')} 到账"
                f"（还有 {w['days_to_due']} 天）。", w.get("expected_date"))

    # ── 付款节点逾期 ──────────────────────────────────────────
    for s in computed.get("schedules", []):
        if s.get("overdue"):
            add("warning", "schedule_overdue", "付款节点已过预计日期未收全",
                f"节点「{s['name']}」预计 {s['expected_date']} 到账 "
                f"{(s['amount'] or 0):,.2f} 元，目前仅到账 {(s['received'] or 0):,.2f} 元。",
                s.get("expected_date"))

    # ── 合同结束仍大额未到账 ──────────────────────────────────
    if (project.end_date and project.end_date < today and computed.get("pending")
            and computed.get("contract_amount")
            and computed["pending"] > computed["contract_amount"] * 0.05):
        add("warning", "pending_after_end", "合同已结束但仍有款项未到账",
            f"项目于 {project.end_date.isoformat()} 结束，尚有 {computed['pending']:,.2f} 元未到账。",
            project.end_date)

    # ── 已开票长期未回款 ──────────────────────────────────────
    overdue_days = int(settings.get("invoice_overdue_days", 30) or 30)
    if (computed.get("invoiced") and computed.get("received") is not None
            and computed["invoiced"] > computed["received"] and project.invoices):
        first_unpaid = min(i.issue_date for i in project.invoices)
        if first_unpaid and (today - first_unpaid).days >= overdue_days:
            add("warning", "invoice_overdue", "已开票但长时间未足额回款",
                f"已开票 {computed['invoiced']:,.2f} 元，最早开票 {first_unpaid.isoformat()}"
                f"（{(today - first_unpaid).days} 天前），累计到账 {computed['received']:,.2f} 元。",
                first_unpaid)

    # ── 项目已开始但成本为空 ──────────────────────────────────
    if (project.start_date and project.start_date < today
            and project.status in ("进行中", "已完成", "已结算")
            and not computed.get("has_cost_data")):
        add("info", "no_cost", "项目已开始但未录入任何成本",
            f"项目于 {project.start_date.isoformat()} 开始，成本数据为空，无法计算利润与成本回收。")

    # ── 亏损 / 成本超收入 ────────────────────────────────────
    if computed.get("profit") is not None and computed.get("revenue") and computed["profit"] < 0:
        add("danger", "loss", "项目亏损",
            f"收入 {computed['revenue']:,.2f} 元，成本 {computed['total_cost']:,.2f} 元，"
            f"利润率 {computed['margin']}%。")

    # ── 利润率异常（低于设置阈值） ────────────────────────────
    threshold = settings.get("margin_alert_ratio", 0)
    if (threshold and computed.get("margin") is not None and computed["profit"] is not None
            and computed["profit"] > 0 and computed["margin"] < threshold):
        add("warning", "low_margin", "项目利润率偏低",
            f"当前利润率 {computed['margin']}%，低于预警阈值 {threshold}%。")

    # ── 到账超合同 ────────────────────────────────────────────
    if computed.get("over_received") and computed.get("contract_amount"):
        add("danger", "received_over", "到账金额超过合同金额",
            f"累计到账 {computed['received']:,.2f} 元，已超过合同金额 "
            f"{computed['contract_amount']:,.2f} 元，请核对回款记录。")

    # ── 数据一致性 ───────────────────────────────────────────
    for iss in computed.get("issues", []):
        if iss["code"] in ("received_over", "loss"):
            continue  # 已在上面以更友好的文案生成
        add(iss["level"], iss["code"], "数据一致性提示", iss["message"])

    return alerts


LEVEL_ORDER = {"danger": 0, "warning": 1, "info": 2}


def dashboard_data(db: Session, year: int | None = None, company_id: int | None = None) -> dict:
    settings = get_settings(db)
    today = date.today()
    year = year or today.year

    query = db.query(Project).filter(Project.year == year).order_by(Project.id)
    if company_id:
        query = query.filter(Project.company_id == company_id)
    projects = query.all()
    computed_map = {p.id: compute_project(load_context(db, p), settings) for p in projects}

    # ── KPI ──────────────────────────────────────────────────
    def s(field, default=None):
        vals = [computed_map[p.id].get(field) for p in projects]
        vals = [v for v in vals if v is not None]
        return sum(vals) if vals else default

    kpis = {
        "year": year,
        "project_count": len(projects),
        "contract_amount": s("contract_amount", 0.0),
        "revenue": s("revenue", 0.0),
        "received": s("received", 0.0),
        "pending": s("pending", 0.0),
        "total_cost": s("total_cost", 0.0),
        "direct_cost": s("direct_cost", 0.0),
        "indirect_cost": s("indirect_cost", 0.0),
        "tax_cost": s("tax_cost", 0.0),
        "profit": s("profit", 0.0),
        "invoiced": s("invoiced", 0.0),
        "not_invoiced": s("not_invoiced", 0.0),
        "warranty_pending": 0.0,
        "recovered_count": 0,
        "not_recovered_count": 0,
        "status_counts": {},
        "avg_margin": None,
    }
    profit_sum, revenue_sum = 0.0, 0.0
    status_counts: dict[str, int] = {}
    for p in projects:
        cp = computed_map[p.id]
        status_counts[p.status] = status_counts.get(p.status, 0) + 1
        if cp["warranty"]["amount"] and cp["warranty"]["status"] != "已到账":
            kpis["warranty_pending"] += cp["warranty"]["amount"]
        if cp["recovery"]["recovered"]:
            kpis["recovered_count"] += 1
        elif cp.get("has_cost_data"):
            kpis["not_recovered_count"] += 1
        if cp.get("revenue") and cp.get("profit") is not None:
            profit_sum += cp["profit"]
            revenue_sum += cp["revenue"]
    kpis["status_counts"] = status_counts
    kpis["avg_margin"] = round(profit_sum / revenue_sum * 100, 1) if revenue_sum else None

    # ── 图表数据 ─────────────────────────────────────────────
    months = [f"{m}月" for m in range(1, 13)]
    sign_by_month = [0.0] * 12
    pay_by_month = [0.0] * 12
    cost_by_month = [0.0] * 12
    for p in projects:
        c = p.contract
        if c and c.sign_date and c.sign_date.year == year:
            sign_by_month[c.sign_date.month - 1] += (c.total_amount_cents or 0) / 100.0
        for r in p.payments:
            if r.payment_date.year == year:
                pay_by_month[r.payment_date.month - 1] += r.amount_cents / 100.0
        for x in p.costs:
            if x.cost_date.year == year:
                cost_by_month[x.cost_date.month - 1] += x.amount_cents / 100.0

    ranked = sorted(projects, key=lambda p: (computed_map[p.id].get("contract_amount") or 0), reverse=True)
    amount_rank = [
        {"name": p.name, "value": computed_map[p.id].get("contract_amount") or 0}
        for p in ranked[:8] if computed_map[p.id].get("contract_amount")
    ]
    profit_rank = sorted(
        [{"name": p.name, "value": computed_map[p.id].get("profit") or 0} for p in projects
         if computed_map[p.id].get("profit") is not None],
        key=lambda x: x["value"], reverse=True)[:8]
    margin_list = [
        {"name": p.name, "value": computed_map[p.id].get("margin")}
        for p in projects if computed_map[p.id].get("margin") is not None
    ]
    margin_top = sorted([m for m in margin_list], key=lambda x: x["value"], reverse=True)[:5]
    margin_bottom = sorted([m for m in margin_list], key=lambda x: x["value"])[:5]

    charts = {
        "monthly": {"months": months, "sign": sign_by_month, "payment": pay_by_month, "cost": cost_by_month},
        "amount_rank": amount_rank,
        "profit_rank": profit_rank,
        "margin_top": margin_top,
        "margin_bottom": margin_bottom,
        "cost_structure": {
            "direct": kpis["direct_cost"], "indirect": kpis["indirect_cost"],
            "tax": kpis["tax_cost"],
            "direct_by_category": {}, "indirect_by_category": {}, "tax_by_category": {},
        },
        "payment_status": {
            "received": kpis["received"], "pending": max(kpis["pending"], 0),
            "warranty": kpis["warranty_pending"],
        },
        "status_counts": status_counts,
    }
    for p in projects:
        cp = computed_map[p.id]
        for cat, v in (cp.get("direct_by_category") or {}).items():
            charts["cost_structure"]["direct_by_category"][cat] = \
                charts["cost_structure"]["direct_by_category"].get(cat, 0) + v
        for cat, v in (cp.get("indirect_by_category") or {}).items():
            charts["cost_structure"]["indirect_by_category"][cat] = \
                charts["cost_structure"]["indirect_by_category"].get(cat, 0) + v
        for cat, v in (cp.get("tax_by_category") or {}).items():
            charts["cost_structure"]["tax_by_category"][cat] = \
                charts["cost_structure"]["tax_by_category"].get(cat, 0) + v

    # ── 待处理事项 ───────────────────────────────────────────
    alerts: list[dict] = []
    for p in projects:
        alerts.extend(project_alerts(computed_map[p.id], p, settings, today))
    alerts.sort(key=lambda a: (LEVEL_ORDER.get(a["level"], 9), a.get("sort_date") or "9999"))

    years = sorted({r[0] for r in db.query(Project.year).all() if r[0]} | {today.year})

    return {
        "kpis": kpis,
        "charts": charts,
        "alerts": alerts,
        "years": years,
        "projects": [{"id": p.id, "name": p.name, "status": p.status,
                      "computed": computed_map[p.id]} for p in projects],
    }
