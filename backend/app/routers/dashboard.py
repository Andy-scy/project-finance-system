"""Dashboard / 年度看板 / 提醒中心 API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.alerts import dashboard_data
from ..services.reminders import build_reminders

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def dashboard(year: int | None = None, company_id: int | None = None, db: Session = Depends(get_db)):
    return dashboard_data(db, year, company_id=company_id)


@router.get("/reminders")
def reminders(company_id: int | None = None, db: Session = Depends(get_db)):
    """提醒中心：合同续签 / 工程款结算 / 质保金到期（弹窗与铃铛数据源）。"""
    return build_reminders(db, company_id=company_id)
