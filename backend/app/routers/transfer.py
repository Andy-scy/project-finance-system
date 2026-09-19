"""导入导出 / 年度报告 / 下载模板。"""
from __future__ import annotations

import urllib.parse

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.excelio import (export_projects_csv, export_projects_xlsx,
                                export_template_xlsx, import_projects_xlsx)
from ..services.report import generate_annual_report

router = APIRouter(tags=["transfer"])


def _xlsx_response(data: bytes, filename: str) -> Response:
    quoted = urllib.parse.quote(filename)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quoted}"},
    )


@router.get("/export/projects.xlsx")
def export_xlsx(year: int | None = None, db: Session = Depends(get_db)):
    return _xlsx_response(export_projects_xlsx(db, year), f"项目财务数据_{year or '全部'}.xlsx")


@router.get("/export/projects.csv")
def export_csv(year: int | None = None, db: Session = Depends(get_db)):
    csv_text = export_projects_csv(db, year)
    quoted = urllib.parse.quote(f"项目财务数据_{year or '全部'}.csv")
    return Response(
        content=b"\xef\xbb\xbf" + csv_text.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quoted}"},
    )


@router.get("/export/payments.xlsx")
def export_payments(year: int | None = None, db: Session = Depends(get_db)):
    # 复用完整工作簿（含付款计划/回款/成本/发票明细页）
    return _xlsx_response(export_projects_xlsx(db, year), f"项目财务明细_{year or '全部'}.xlsx")


@router.get("/export/template.xlsx")
def template():
    return _xlsx_response(export_template_xlsx(), "项目导入模板.xlsx")


@router.post("/import/projects")
async def import_projects(file: UploadFile, db: Session = Depends(get_db)):
    name = (file.filename or "").lower()
    if not name.endswith((".xlsx", ".xlsm")):
        raise HTTPException(400, "请上传 .xlsx 格式的 Excel 文件。")
    data = await file.read()
    result = import_projects_xlsx(db, data)
    if not result.get("ok"):
        raise HTTPException(400, result.get("error", "导入失败"))
    return result


@router.get("/report/annual")
def annual_report(year: int, db: Session = Depends(get_db)):
    try:
        pdf = generate_annual_report(db, year)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"报告生成失败：{e}")
    quoted = urllib.parse.quote(f"{year}年度项目经营分析报告.pdf")
    return Response(
        content=pdf, media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{quoted}"},
    )
