"""项目 API：列表 / 详情 / CRUD / 合同 / 付款节点 / 回款 / 发票 / 成本 / 附件。"""
from __future__ import annotations

import time
import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from ..config import (DIRECT_CATEGORIES, INDIRECT_CATEGORIES, PROJECT_STATUSES,
                      PROJECT_TYPES, TAX_CATEGORIES, TAX_RATE_OPTIONS, UPLOAD_DIR)
from ..database import get_db
from ..models import (Contract, CostItem, ExtractionRecord, Invoice, PaymentRecord,
                      PaymentSchedule, Project, UploadedFile)
from ..services.calc import compute_project, load_context
from ..services.money import parse_date_any, pct_to_bp, yuan_to_cents, cents_to_yuan
from ..services.settings_svc import get_settings

router = APIRouter(prefix="/projects", tags=["projects"])

MONEY_KEYS = {"total_amount": "total_amount_cents", "excl_tax_amount": "excl_tax_amount_cents",
              "tax_amount": "tax_amount_cents", "warranty_amount": "warranty_amount_cents"}
RATE_KEYS = {"tax_rate": "tax_rate_bp", "warranty_ratio": "warranty_ratio_bp"}
DATE_KEYS = {"sign_date", "contract_end_date", "warranty_start_date", "warranty_expected_date", "warranty_actual_date"}


# ── 序列化 ───────────────────────────────────────────────────

def ser_contract(c: Contract | None) -> dict | None:
    if c is None:
        return None
    return {
        "id": c.id,
        "contract_no": c.contract_no,
        "total_amount": cents_to_yuan(c.total_amount_cents),
        "tax_rate": None if c.tax_rate_bp is None else c.tax_rate_bp / 100.0,
        "tax_amount": cents_to_yuan(c.tax_amount_cents),
        "excl_tax_amount": cents_to_yuan(c.excl_tax_amount_cents),
        "sign_date": c.sign_date.isoformat() if c.sign_date else None,
        "contract_end_date": c.contract_end_date.isoformat() if c.contract_end_date else None,
        "payment_terms": c.payment_terms,
        "warranty_months": c.warranty_months,
        "warranty_start_date": c.warranty_start_date.isoformat() if c.warranty_start_date else None,
        "warranty_ratio": None if c.warranty_ratio_bp is None else c.warranty_ratio_bp / 100.0,
        "warranty_amount": cents_to_yuan(c.warranty_amount_cents),
        "warranty_expected_date": c.warranty_expected_date.isoformat() if c.warranty_expected_date else None,
        "warranty_actual_date": c.warranty_actual_date.isoformat() if c.warranty_actual_date else None,
    }


def ser_schedule(s: PaymentSchedule) -> dict:
    return {
        "id": s.id, "name": s.name,
        "ratio": None if s.ratio_bp is None else s.ratio_bp / 100.0,
        "amount": cents_to_yuan(s.amount_cents),
        "expected_date": s.expected_date.isoformat() if s.expected_date else None,
        "is_warranty": bool(s.is_warranty),
        "sort_order": s.sort_order, "note": s.note,
    }


def ser_payment(r: PaymentRecord) -> dict:
    return {
        "id": r.id, "amount": cents_to_yuan(r.amount_cents),
        "payment_date": r.payment_date.isoformat(), "type": r.type,
        "schedule_id": r.schedule_id, "invoice_id": r.invoice_id, "note": r.note,
    }


def ser_invoice(i: Invoice) -> dict:
    return {
        "id": i.id, "invoice_no": i.invoice_no, "amount": cents_to_yuan(i.amount_cents),
        "issue_date": i.issue_date.isoformat(), "type": i.type, "note": i.note,
    }


def ser_cost(x: CostItem) -> dict:
    return {
        "id": x.id, "kind": x.kind, "category": x.category,
        "amount": cents_to_yuan(x.amount_cents),
        "cost_date": x.cost_date.isoformat(), "note": x.note,
    }


def ser_file(f: UploadedFile) -> dict:
    return {
        "id": f.id, "orig_name": f.orig_name, "size": f.size, "kind": f.kind,
        "mime": f.mime, "uploaded_at": f.uploaded_at.isoformat() if f.uploaded_at else None,
    }


def get_project_or_404(db: Session, project_id: int) -> Project:
    p = db.get(Project, project_id)
    if p is None:
        raise HTTPException(404, "项目不存在")
    return p


def _apply_contract_data(db: Session, contract: Contract, data: dict):
    for k, attr in MONEY_KEYS.items():
        if k in data:
            setattr(contract, attr, yuan_to_cents(data[k]))
    for k in RATE_KEYS:
        if k in data:
            setattr(contract, {"tax_rate": "tax_rate_bp", "warranty_ratio": "warranty_ratio_bp"}[k],
                    pct_to_bp(data[k]))
    for k in DATE_KEYS:
        if k in data:
            setattr(contract, k, parse_date_any(data[k]))
    for k in ("contract_no", "payment_terms"):
        if k in data:
            v = data[k]
            setattr(contract, k, str(v).strip() if v not in (None, "") else None)
    if "warranty_months" in data:
        try:
            contract.warranty_months = int(data["warranty_months"]) if data["warranty_months"] not in (None, "") else None
        except (TypeError, ValueError):
            contract.warranty_months = None
    db.flush()


def _recompute_tax_fields(contract: Contract):
    """程序负责税额/不含税额/预计质保金到账日补算。"""
    from decimal import Decimal, ROUND_HALF_UP
    if contract.total_amount_cents and contract.tax_rate_bp is not None:
        from ..services.calc import derive_tax
        d_excl, d_tax = derive_tax(contract.total_amount_cents, contract.tax_rate_bp)
        if contract.excl_tax_amount_cents is None:
            contract.excl_tax_amount_cents = d_excl
        if contract.tax_amount_cents is None:
            contract.tax_amount_cents = d_tax
    elif contract.excl_tax_amount_cents and contract.tax_rate_bp is not None and not contract.total_amount_cents:
        contract.total_amount_cents = int(
            (Decimal(contract.excl_tax_amount_cents) * (10000 + contract.tax_rate_bp) / 10000)
            .quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if contract.warranty_months and contract.warranty_expected_date is None:
        from ..services.money import add_months
        p = contract.project
        start = contract.warranty_start_date or p.end_date or p.start_date
        if start:
            contract.warranty_expected_date = add_months(start, contract.warranty_months)


# ── 列表 / 详情 ──────────────────────────────────────────────

SORTERS = {
    "contract_amount": lambda cp: cp.get("contract_amount") or 0,
    "received": lambda cp: cp.get("received") or 0,
    "pending": lambda cp: cp.get("pending") or 0,
    "profit": lambda cp: cp.get("profit") if cp.get("profit") is not None else -1e18,
    "margin": lambda cp: cp.get("margin") if cp.get("margin") is not None else -1e18,
    "received_ratio": lambda cp: cp.get("received_ratio") if cp.get("received_ratio") is not None else -1,
}


@router.get("")
def list_projects(
    year: int | None = None,
    status: str | None = None,
    q: str | None = None,
    sort: str = "contract_amount",
    order: str = "desc",
    warranty_status: str | None = None,
    recovery: str | None = None,
    company_id: int | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Project)
    if company_id:
        query = query.filter(Project.company_id == company_id)
    if year:
        query = query.filter(Project.year == year)
    if status:
        query = query.filter(Project.status == status)
    if q:
        like = f"%{q}%"
        query = query.filter(
            Project.name.like(like) | Project.customer_name.like(like) | Project.code.like(like)
        )
    projects = query.all()
    settings = get_settings(db)
    items = []
    for p in projects:
        cp = compute_project(load_context(db, p), settings)
        if warranty_status and cp["warranty"]["status"] != warranty_status:
            continue
        if recovery == "recovered" and not cp["recovery"]["recovered"]:
            continue
        if recovery == "not_recovered" and cp["recovery"]["recovered"]:
            continue
        items.append({
            "id": p.id, "name": p.name, "code": p.code,
            "company_id": p.company_id,
            "company_name": p.company.name if p.company else None,
            "customer_name": p.customer_name, "owner": p.owner,
            "project_type": p.project_type, "status": p.status,
            "start_date": p.start_date.isoformat() if p.start_date else None,
            "end_date": p.end_date.isoformat() if p.end_date else None,
            "year": p.year,
            "contract": ser_contract(p.contract),
            "computed": cp,
        })
    keyfn = SORTERS.get(sort, SORTERS["contract_amount"])
    items.sort(key=keyfn, reverse=(order != "asc"))
    return {"items": items, "total": len(items)}


@router.get("/meta")
def project_meta():
    return {
        "statuses": PROJECT_STATUSES,
        "project_types": PROJECT_TYPES,
        "direct_categories": DIRECT_CATEGORIES,
        "indirect_categories": INDIRECT_CATEGORIES,
        "tax_categories": TAX_CATEGORIES,
        "tax_rate_options": TAX_RATE_OPTIONS,
        "payment_types": ["合同款", "质保金", "其他"],
        "invoice_types": ["销项发票", "进项发票"],
        "schedule_names": ["首付款", "预付款", "进度款", "中期款", "验收款", "尾款", "质保金"],
    }


@router.get("/{project_id}")
def project_detail(project_id: int, db: Session = Depends(get_db)):
    p = get_project_or_404(db, project_id)
    settings = get_settings(db)
    cp = compute_project(load_context(db, p), settings)
    extractions = db.query(ExtractionRecord).filter(ExtractionRecord.project_id == p.id)\
        .order_by(ExtractionRecord.id.desc()).all()
    return {
        "id": p.id, "name": p.name, "code": p.code,
        "company_id": p.company_id,
        "company_name": p.company.name if p.company else None,
        "customer_name": p.customer_name, "owner": p.owner,
        "project_type": p.project_type, "status": p.status,
        "start_date": p.start_date.isoformat() if p.start_date else None,
        "end_date": p.end_date.isoformat() if p.end_date else None,
        "year": p.year, "notes": p.notes,
        "contract": ser_contract(p.contract),
        "schedules": [ser_schedule(s) for s in p.schedules],
        "payments": [ser_payment(r) for r in sorted(p.payments, key=lambda x: x.payment_date)],
        "invoices": [ser_invoice(i) for i in sorted(p.invoices, key=lambda x: x.issue_date)],
        "costs": [ser_cost(x) for x in sorted(p.costs, key=lambda x: x.cost_date)],
        "files": [ser_file(f) for f in p.files],
        "computed": cp,
        "extractions": [{
            "id": r.id, "status": r.status, "engine": r.engine, "model": r.model,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        } for r in extractions],
    }


# ── 项目 CRUD ────────────────────────────────────────────────

@router.post("")
def create_project(body: dict, db: Session = Depends(get_db)):
    name = str(body.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "项目名称必填。其余字段可以先留空，保存后随时补充。")
    p = Project(name=name[:200])
    if body.get("company_id"):
        try:
            p.company_id = int(body["company_id"])
        except (TypeError, ValueError):
            p.company_id = None
    for k in ("code", "customer_name", "owner", "project_type", "notes"):
        if body.get(k) not in (None, ""):
            setattr(p, k, str(body[k]).strip())
    if body.get("status"):
        p.status = str(body["status"])
    for k in ("start_date", "end_date"):
        p.__setattr__(k, parse_date_any(body.get(k)))
    db.add(p)
    db.flush()

    cdata = body.get("contract") or {}
    if any(v not in (None, "") for v in cdata.values()):
        c = Contract(project_id=p.id)
        _apply_contract_data(db, c, cdata)
        db.add(c)
        db.flush()
        _recompute_tax_fields(c)
    for i, sc in enumerate(body.get("schedules") or []):
        db.add(PaymentSchedule(
            project_id=p.id,
            name=str(sc.get("name") or f"节点{i + 1}").strip()[:40],
            ratio_bp=pct_to_bp(sc.get("ratio")),
            amount_cents=yuan_to_cents(sc.get("amount")),
            expected_date=parse_date_any(sc.get("expected_date")),
            is_warranty=bool(sc.get("is_warranty")),
            sort_order=i,
        ))
    if not p.year:
        p.year = (p.contract.sign_date.year if p.contract and p.contract.sign_date
                  else (p.start_date.year if p.start_date else date.today().year))
    db.commit()
    db.refresh(p)
    return {"id": p.id, "name": p.name}


@router.put("/{project_id}")
def update_project(project_id: int, body: dict, db: Session = Depends(get_db)):
    p = get_project_or_404(db, project_id)
    if "name" in body:
        name = str(body.get("name") or "").strip()
        if not name:
            raise HTTPException(400, "项目名称不能为空。")
        p.name = name[:200]
    for k in ("code", "customer_name", "owner", "project_type", "notes"):
        if k in body:
            setattr(p, k, str(body[k]).strip() if body[k] not in (None, "") else None)
    if "status" in body:
        p.status = str(body["status"]) if body["status"] else "未开始"
    for k in ("start_date", "end_date"):
        if k in body:
            setattr(p, k, parse_date_any(body[k]))
    if "company_id" in body:
        try:
            p.company_id = int(body["company_id"]) if body["company_id"] else None
        except (TypeError, ValueError):
            pass
    if "year" in body:
        try:
            p.year = int(body["year"]) if body["year"] else None
        except (TypeError, ValueError):
            pass
    p.updated_at = datetime.now()
    db.commit()
    return {"ok": True}


@router.delete("/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db)):
    p = get_project_or_404(db, project_id)
    db.delete(p)
    db.commit()
    return {"ok": True}


# ── 合同 ─────────────────────────────────────────────────────

@router.put("/{project_id}/contract")
def update_contract(project_id: int, body: dict, db: Session = Depends(get_db)):
    p = get_project_or_404(db, project_id)
    c = p.contract or Contract(project_id=p.id)
    if c.id is None:
        db.add(c)
    _apply_contract_data(db, c, body)
    _recompute_tax_fields(c)
    if not p.year and c.sign_date:
        p.year = c.sign_date.year
    db.commit()
    return {"ok": True, "contract": ser_contract(c)}


# ── 付款节点 ─────────────────────────────────────────────────

@router.post("/{project_id}/schedules")
def add_schedule(project_id: int, body: dict, db: Session = Depends(get_db)):
    p = get_project_or_404(db, project_id)
    max_order = max((s.sort_order for s in p.schedules), default=-1)
    s = PaymentSchedule(
        project_id=p.id,
        name=str(body.get("name") or "付款节点").strip()[:40],
        ratio_bp=pct_to_bp(body.get("ratio")),
        amount_cents=yuan_to_cents(body.get("amount")),
        expected_date=parse_date_any(body.get("expected_date")),
        is_warranty=bool(body.get("is_warranty")),
        sort_order=body.get("sort_order", max_order + 1),
        note=body.get("note"),
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return ser_schedule(s)


@router.put("/{project_id}/schedules/{schedule_id}")
def update_schedule(project_id: int, schedule_id: int, body: dict, db: Session = Depends(get_db)):
    s = db.get(PaymentSchedule, schedule_id)
    if s is None or s.project_id != project_id:
        raise HTTPException(404, "付款节点不存在")
    if "name" in body:
        s.name = str(body["name"] or "").strip()[:40] or s.name
    if "ratio" in body:
        s.ratio_bp = pct_to_bp(body["ratio"])
    if "amount" in body:
        s.amount_cents = yuan_to_cents(body["amount"])
    if "expected_date" in body:
        s.expected_date = parse_date_any(body["expected_date"])
    if "is_warranty" in body:
        s.is_warranty = bool(body["is_warranty"])
    if "note" in body:
        s.note = body["note"]
    db.commit()
    return ser_schedule(s)


@router.delete("/{project_id}/schedules/{schedule_id}")
def delete_schedule(project_id: int, schedule_id: int, db: Session = Depends(get_db)):
    s = db.get(PaymentSchedule, schedule_id)
    if s is None or s.project_id != project_id:
        raise HTTPException(404, "付款节点不存在")
    db.delete(s)
    db.commit()
    return {"ok": True}


# ── 回款记录 ─────────────────────────────────────────────────

@router.post("/{project_id}/payments")
def add_payment(project_id: int, body: dict, db: Session = Depends(get_db)):
    p = get_project_or_404(db, project_id)
    amount = yuan_to_cents(body.get("amount"))
    if not amount or amount <= 0:
        raise HTTPException(400, "请输入正确的回款金额。")
    r = PaymentRecord(
        project_id=p.id,
        amount_cents=amount,
        payment_date=parse_date_any(body.get("payment_date")) or date.today(),
        type=body.get("type") or "合同款",
        schedule_id=body.get("schedule_id"),
        invoice_id=body.get("invoice_id"),
        note=body.get("note"),
    )
    if r.schedule_id:
        s = db.get(PaymentSchedule, r.schedule_id)
        if s is None or s.project_id != p.id:
            r.schedule_id = None
    if r.invoice_id:
        inv = db.get(Invoice, r.invoice_id)
        if inv is None or inv.project_id != p.id:
            r.invoice_id = None
    db.add(r)
    db.commit()
    db.refresh(r)
    return ser_payment(r)


@router.put("/{project_id}/payments/{payment_id}")
def update_payment(project_id: int, payment_id: int, body: dict, db: Session = Depends(get_db)):
    r = db.get(PaymentRecord, payment_id)
    if r is None or r.project_id != project_id:
        raise HTTPException(404, "回款记录不存在")
    if "amount" in body:
        amount = yuan_to_cents(body["amount"])
        if not amount or amount <= 0:
            raise HTTPException(400, "请输入正确的回款金额。")
        r.amount_cents = amount
    if "payment_date" in body:
        r.payment_date = parse_date_any(body["payment_date"]) or r.payment_date
    if "type" in body:
        r.type = body["type"] or r.type
    if "schedule_id" in body:
        r.schedule_id = body["schedule_id"]
    if "invoice_id" in body:
        r.invoice_id = body["invoice_id"]
    if "note" in body:
        r.note = body["note"]
    db.commit()
    return ser_payment(r)


@router.delete("/{project_id}/payments/{payment_id}")
def delete_payment(project_id: int, payment_id: int, db: Session = Depends(get_db)):
    r = db.get(PaymentRecord, payment_id)
    if r is None or r.project_id != project_id:
        raise HTTPException(404, "回款记录不存在")
    db.delete(r)
    db.commit()
    return {"ok": True}


# ── 发票 ─────────────────────────────────────────────────────

@router.post("/{project_id}/invoices")
def add_invoice(project_id: int, body: dict, db: Session = Depends(get_db)):
    p = get_project_or_404(db, project_id)
    amount = yuan_to_cents(body.get("amount"))
    if not amount or amount <= 0:
        raise HTTPException(400, "请输入正确的开票金额。")
    inv = Invoice(
        project_id=p.id,
        invoice_no=str(body.get("invoice_no") or "").strip() or None,
        amount_cents=amount,
        issue_date=parse_date_any(body.get("issue_date")) or date.today(),
        type=body.get("type") or "销项发票",
        note=body.get("note"),
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return ser_invoice(inv)


@router.put("/{project_id}/invoices/{invoice_id}")
def update_invoice(project_id: int, invoice_id: int, body: dict, db: Session = Depends(get_db)):
    inv = db.get(Invoice, invoice_id)
    if inv is None or inv.project_id != project_id:
        raise HTTPException(404, "发票不存在")
    if "invoice_no" in body:
        inv.invoice_no = str(body["invoice_no"] or "").strip() or None
    if "amount" in body:
        amount = yuan_to_cents(body["amount"])
        if not amount or amount <= 0:
            raise HTTPException(400, "请输入正确的开票金额。")
        inv.amount_cents = amount
    if "issue_date" in body:
        inv.issue_date = parse_date_any(body["issue_date"]) or inv.issue_date
    if "type" in body:
        inv.type = body["type"] or inv.type
    if "note" in body:
        inv.note = body["note"]
    db.commit()
    return ser_invoice(inv)


@router.delete("/{project_id}/invoices/{invoice_id}")
def delete_invoice(project_id: int, invoice_id: int, db: Session = Depends(get_db)):
    inv = db.get(Invoice, invoice_id)
    if inv is None or inv.project_id != project_id:
        raise HTTPException(404, "发票不存在")
    db.delete(inv)
    db.commit()
    return {"ok": True}


# ── 成本 ─────────────────────────────────────────────────────

@router.post("/{project_id}/costs")
def add_cost(project_id: int, body: dict, db: Session = Depends(get_db)):
    p = get_project_or_404(db, project_id)
    kind = body.get("kind")
    if kind not in ("direct", "indirect", "tax"):
        raise HTTPException(400, "成本类别必须为 direct / indirect / tax。")
    amount = yuan_to_cents(body.get("amount"))
    if not amount or amount <= 0:
        raise HTTPException(400, "请输入正确的成本金额。")
    default_cat = {"direct": "其他直接成本", "indirect": "其他间接成本", "tax": "增值税"}[kind]
    x = CostItem(
        project_id=p.id, kind=kind,
        category=str(body.get("category") or default_cat),
        amount_cents=amount,
        cost_date=parse_date_any(body.get("cost_date")) or date.today(),
        note=body.get("note"),
    )
    db.add(x)
    db.commit()
    db.refresh(x)
    return ser_cost(x)


@router.put("/{project_id}/costs/{cost_id}")
def update_cost(project_id: int, cost_id: int, body: dict, db: Session = Depends(get_db)):
    x = db.get(CostItem, cost_id)
    if x is None or x.project_id != project_id:
        raise HTTPException(404, "成本记录不存在")
    if "kind" in body and body["kind"] in ("direct", "indirect", "tax"):
        x.kind = body["kind"]
    if "category" in body:
        x.category = body["category"] or x.category
    if "amount" in body:
        amount = yuan_to_cents(body["amount"])
        if not amount or amount <= 0:
            raise HTTPException(400, "请输入正确的成本金额。")
        x.amount_cents = amount
    if "cost_date" in body:
        x.cost_date = parse_date_any(body["cost_date"]) or x.cost_date
    if "note" in body:
        x.note = body["note"]
    db.commit()
    return ser_cost(x)


@router.delete("/{project_id}/costs/{cost_id}")
def delete_cost(project_id: int, cost_id: int, db: Session = Depends(get_db)):
    x = db.get(CostItem, cost_id)
    if x is None or x.project_id != project_id:
        raise HTTPException(404, "成本记录不存在")
    db.delete(x)
    db.commit()
    return {"ok": True}


# ── 附件 ─────────────────────────────────────────────────────

@router.post("/{project_id}/files")
def upload_file(project_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    p = get_project_or_404(db, project_id)
    data = file.file.read()
    if len(data) > 50 * 1024 * 1024:
        raise HTTPException(400, "文件不能超过 50MB。")
    stored = f"{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}_{file.filename}"
    stored = stored.replace("\\", "_").replace("/", "_")
    path = UPLOAD_DIR / stored
    path.write_bytes(data)
    f = UploadedFile(
        project_id=p.id, orig_name=file.filename, stored_name=stored,
        mime=file.content_type, size=len(data), kind="other",
    )
    db.add(f)
    db.commit()
    db.refresh(f)
    return ser_file(f)


@router.get("/{project_id}/files/{file_id}/download")
def download_file(project_id: int, file_id: int, db: Session = Depends(get_db)):
    from fastapi.responses import FileResponse
    f = db.get(UploadedFile, file_id)
    if f is None or (f.project_id != project_id and project_id != 0):
        raise HTTPException(404, "文件不存在")
    path = UPLOAD_DIR / f.stored_name
    if not path.exists():
        raise HTTPException(404, "文件已丢失（本地存储被删除）")
    return FileResponse(str(path), filename=f.orig_name)


@router.delete("/{project_id}/files/{file_id}")
def delete_file(project_id: int, file_id: int, db: Session = Depends(get_db)):
    f = db.get(UploadedFile, file_id)
    if f is None or (f.project_id != project_id and project_id != 0):
        raise HTTPException(404, "文件不存在")
    path = UPLOAD_DIR / f.stored_name
    if path.exists():
        try:
            path.unlink()
        except OSError:
            pass
    db.delete(f)
    db.commit()
    return {"ok": True}
