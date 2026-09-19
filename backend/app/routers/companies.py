"""公司主体管理 API（多公司切换）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Company, Project

router = APIRouter(prefix="/companies", tags=["companies"])


def ser_company(c: Company, count: int | None = None) -> dict:
    return {
        "id": c.id, "name": c.name, "sort_order": c.sort_order,
        "project_count": count,
    }


@router.get("")
def list_companies(db: Session = Depends(get_db)):
    rows = db.query(Company).order_by(Company.sort_order, Company.id).all()
    counts = dict(db.query(Project.company_id, func.count(Project.id)).group_by(Project.company_id).all())
    return {"items": [ser_company(c, counts.get(c.id, 0)) for c in rows]}


@router.post("")
def create_company(body: dict, db: Session = Depends(get_db)):
    name = str(body.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "公司名称不能为空。")
    max_order = max((c.sort_order for c in db.query(Company).all()), default=0)
    c = Company(name=name[:100], sort_order=max_order + 1)
    db.add(c)
    db.commit()
    db.refresh(c)
    return ser_company(c, 0)


@router.put("/{company_id}")
def update_company(company_id: int, body: dict, db: Session = Depends(get_db)):
    c = db.get(Company, company_id)
    if c is None:
        raise HTTPException(404, "公司不存在")
    if "name" in body:
        name = str(body["name"] or "").strip()
        if not name:
            raise HTTPException(400, "公司名称不能为空。")
        c.name = name[:100]
    if "sort_order" in body:
        try:
            c.sort_order = int(body["sort_order"])
        except (TypeError, ValueError):
            pass
    db.commit()
    return ser_company(c)


@router.delete("/{company_id}")
def delete_company(company_id: int, db: Session = Depends(get_db)):
    c = db.get(Company, company_id)
    if c is None:
        raise HTTPException(404, "公司不存在")
    n = db.query(Project).filter(Project.company_id == company_id).count()
    if n:
        raise HTTPException(400, f"该公司下还有 {n} 个项目，请先转移或删除项目后再删除公司。")
    db.delete(c)
    db.commit()
    return {"ok": True}
