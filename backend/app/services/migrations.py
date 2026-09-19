"""轻量数据库迁移（幂等，可重复执行）。

v1.1 新增：companies 表、projects.company_id 列、contracts.contract_end_date 列。
服务每次启动时自动执行（init_db 调用）；独立迁移脚本 scripts/migrate_v1_1.py 也调用本模块。
"""
from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def run_all(engine: Engine) -> dict:
    """补列 / 建表 / 默认公司 / 项目归属，返回执行摘要。重复执行为无害空操作。"""
    result = {"added_columns": [], "created_company": None, "assigned_projects": 0}
    insp = inspect(engine)
    with engine.begin() as conn:
        if insp.has_table("projects"):
            pcols = {c["name"] for c in insp.get_columns("projects")}
            if "company_id" not in pcols:
                conn.execute(text("ALTER TABLE projects ADD COLUMN company_id INTEGER"))
                result["added_columns"].append("projects.company_id")
        if insp.has_table("contracts"):
            ccols = {c["name"] for c in insp.get_columns("contracts")}
            if "contract_end_date" not in ccols:
                conn.execute(text("ALTER TABLE contracts ADD COLUMN contract_end_date DATE"))
                result["added_columns"].append("contracts.contract_end_date")

    from ..models import Company, Project
    from ..database import SessionLocal
    db = SessionLocal()
    try:
        if db.query(Company).count() == 0:
            comp = Company(name="默认公司", sort_order=0)
            db.add(comp)
            db.commit()
            db.refresh(comp)
            result["created_company"] = comp.name
        comp = db.query(Company).order_by(Company.id).first()
        if comp is not None:
            n = (
                db.query(Project)
                .filter(Project.company_id.is_(None))
                .update({Project.company_id: comp.id})
            )
            db.commit()
            result["assigned_projects"] = n
    finally:
        db.close()
    return result
