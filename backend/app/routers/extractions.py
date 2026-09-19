"""AI 识别 API：上传/粘贴 → 识别 → 待确认记录 → 确认写入。"""
from __future__ import annotations

import json
import time
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from ..config import UPLOAD_DIR
from ..database import get_db
from ..models import ExtractionRecord, Project, UploadedFile
from ..services.ai_client import AIError
from ..services.extraction import apply_to_project, record_payload, run_extraction
from ..services.fileparse import sniff_kind

router = APIRouter(prefix="/extractions", tags=["extractions"])

ALLOWED_EXT = {".pdf", ".docx", ".doc", ".png", ".jpg", ".jpeg", ".bmp", ".webp", ".txt", ".md", ".csv"}


def _save_upload(file: UploadFile) -> UploadedFile:
    from pathlib import Path
    orig = Path(file.filename or "未命名").name
    ext = Path(orig).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"暂不支持 {ext or '该'} 类型文件。请上传 PDF / Word(.docx) / 图片 / 文本文件。")
    data = file.file.read()
    if len(data) > 50 * 1024 * 1024:
        raise HTTPException(400, "文件不能超过 50MB。")
    stored = f"{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}_{orig}"
    stored = stored.replace("\\", "_").replace("/", "_")
    (UPLOAD_DIR / stored).write_bytes(data)
    f = UploadedFile(orig_name=orig, stored_name=stored, mime=file.content_type,
                     size=len(data), kind="contract")
    db_obj = f
    return db_obj


@router.post("/upload")
async def upload_and_extract(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """上传合同文件 → 解析 → AI 识别 → 生成待确认记录。"""
    try:
        f = _save_upload(file)
    except HTTPException:
        raise
    db.add(f)
    db.commit()
    db.refresh(f)
    try:
        record = run_extraction(db, file_row=f)
    except AIError as e:
        # 保留文件，标记识别失败信息返回
        return {"ok": False, "error": str(e), "file_id": f.id}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"AI 识别失败：{e}", "file_id": f.id}
    return {"ok": True, "record_id": record.id, "file_id": f.id}


@router.post("/text")
def extract_from_text(body: dict, db: Session = Depends(get_db)):
    """粘贴合同文本进行识别（无需上传文件）。"""
    text = str(body.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "请粘贴合同文本内容。")
    try:
        record = run_extraction(db, text=text, filename=body.get("filename") or "粘贴文本")
    except AIError as e:
        raise HTTPException(400, str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"AI 识别失败：{e}")
    return {"ok": True, "record_id": record.id}


@router.get("")
def list_extractions(status: str | None = Query(None), db: Session = Depends(get_db)):
    q = db.query(ExtractionRecord).order_by(ExtractionRecord.id.desc())
    if status:
        q = q.filter(ExtractionRecord.status == status)
    out = []
    for r in q.limit(100).all():
        payload = record_payload(r)
        out.append({
            "id": r.id, "status": r.status, "engine": r.engine, "model": r.model,
            "file_id": r.file_id, "project_id": r.project_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "summary": payload.get("summary"),
        })
    return {"items": out}


@router.get("/{record_id}")
def get_extraction(record_id: int, db: Session = Depends(get_db)):
    r = db.get(ExtractionRecord, record_id)
    if r is None:
        raise HTTPException(404, "识别记录不存在")
    f = db.get(UploadedFile, r.file_id) if r.file_id else None
    return {
        "id": r.id, "status": r.status, "engine": r.engine, "model": r.model,
        "file_id": r.file_id, "project_id": r.project_id,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "raw_digest": r.raw_digest,
        "file_name": f.orig_name if f else "粘贴文本",
        "payload": record_payload(r),
    }


@router.post("/{record_id}/confirm")
def confirm_extraction(record_id: int, body: dict, db: Session = Depends(get_db)):
    """用户确认后写入。body: {mode, project_id?, project, contract, schedules, replace_schedules}"""
    r = db.get(ExtractionRecord, record_id)
    if r is None:
        raise HTTPException(404, "识别记录不存在")
    if r.status == "discarded":
        raise HTTPException(400, "该识别记录已放弃，无法确认。")
    try:
        project = apply_to_project(db, r, body)
    except AIError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "project_id": project.id, "project_name": project.name}


@router.post("/{record_id}/discard")
def discard_extraction(record_id: int, db: Session = Depends(get_db)):
    r = db.get(ExtractionRecord, record_id)
    if r is None:
        raise HTTPException(404, "识别记录不存在")
    r.status = "discarded"
    db.commit()
    return {"ok": True}
