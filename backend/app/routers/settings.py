"""系统设置 / 系统操作 API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database import SessionLocal, get_db
from ..models import Setting
from ..services.ai_client import AIError, test_ai
from ..services.demo import seed_demo
from ..services.settings_svc import DEFAULTS, get_settings, masked, save_settings

router = APIRouter(tags=["settings"])


@router.get("/settings")
def read_settings(db: Session = Depends(get_db)):
    return masked(get_settings(db))


@router.put("/settings")
def write_settings(body: dict, db: Session = Depends(get_db)):
    save_settings(db, body)
    return {"ok": True, "settings": masked(get_settings(db))}


@router.post("/settings/test-ai")
def test_ai_connection(db: Session = Depends(get_db)):
    try:
        result = test_ai(db)
        return {"ok": True, **result}
    except AIError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"测试失败：{e}"}


@router.post("/system/demo-data")
def load_demo_data(body: dict | None = None, db: Session = Depends(get_db)):
    force = bool((body or {}).get("force"))
    return seed_demo(db, force=force)


@router.post("/system/reset")
def reset_data(db: Session = Depends(get_db)):
    """清空全部业务数据（保留系统设置）。"""
    from ..models import (Contract, CostItem, ExtractionRecord, Invoice,
                          PaymentRecord, PaymentSchedule, Project, UploadedFile)
    for t in (ExtractionRecord, UploadedFile, PaymentRecord, PaymentSchedule,
              Invoice, CostItem, Contract, Project):
        db.query(t).delete()
    db.commit()
    return {"ok": True}
