"""AI 合同信息抽取：严格防猜 —— 识别不到的字段一律 null，绝不编造。

流程：解析文件 → LLM 结构化抽取 → 校验归一化 → 生成「待确认」识别记录
     → 前端确认页人工核对 → confirm 后才写入项目。
每个字段携带：value（归一化值）、confidence（置信度）、source（页码+原文摘录）、needs_review。
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.orm import Session

from ..config import UPLOAD_DIR
from ..models import Contract, ExtractionRecord, PaymentSchedule, Project, UploadedFile
from .ai_client import AIError, chat, extract_json
from .fileparse import build_llm_text, parse_file
from .money import parse_date_any, parse_money_text, pct_to_bp, yuan_to_cents

# 字段定义：key → (中文名, 类型)
FIELD_SPECS: dict[str, tuple[str, str]] = {
    "project_name": ("项目名称", "text"),
    "customer_name": ("客户名称（甲方/发包方）", "text"),
    "contract_no": ("合同编号", "text"),
    "total_amount": ("含税合同总金额（元）", "money"),
    "excl_tax_amount": ("不含税金额（元）", "money"),
    "tax_rate": ("税率（%，填数字如13）", "rate"),
    "tax_amount": ("税额（元）", "money"),
    "sign_date": ("合同签订日期", "date"),
    "start_date": ("项目开始日期", "date"),
    "end_date": ("项目结束/交付日期", "date"),
    "payment_terms": ("付款方式条款（原文）", "text"),
    "warranty_months": ("质保期（月）", "int"),
    "warranty_start_date": ("质保期起算日期", "date"),
    "warranty_ratio": ("质保金比例（%）", "rate"),
    "warranty_amount": ("质保金金额（元）", "money"),
    "warranty_expected_date": ("预计质保金到账日期", "date"),
    "invoice_requirements": ("发票要求", "text"),
    "notes": ("其他重要合同条款", "text"),
}

LOW_CONFIDENCE = 0.6  # 低于该置信度 → 标记「需要人工确认」

SYSTEM_PROMPT = """你是资深合同信息抽取引擎。任务：从合同原文中抽取结构化字段，输出 JSON。

铁律（必须遵守）：
1. 只抽取原文中【明确写出】的信息。原文没有、模糊、需要推断的一律填 null，严禁猜测、严禁编造、严禁用常识补全。
2. 每个字段必须给出 confidence（0~1 小数，表示你对该值来自原文的确信程度）和 source：{"page": 页码或null, "quote": 原文摘录（不超过60字，逐字复制）}。
3. 金额一律换算为纯数字（单位：元），如 "壹佰万元整(¥1,000,000)" → 1000000；"100万" → 1000000。
4. 税率填数字（不含%），如 "13%" → 13，"6%" → 6。
5. 日期用 YYYY-MM-DD。相对表述如"验收合格后30日内付款"无法确定具体日期 → 日期字段填 null。
6. payment_schedules：把付款条款拆成数组。每项含 name（如 首付款/进度款/中期款/尾款/验收款/质保金）、ratio（%数字或null）、amount（元数字或null）、expected_date（原文明确的日期或null）、is_warranty（质保金节点为 true）。条款没写具体金额/日期就填 null。
7. 大小写金额不一致时取大写金额并降低 confidence。
8. 只输出一个 JSON 对象，不要输出任何其他文字。

输出 JSON 结构：
{
  "fields": {
    "project_name": {"value": ...或null, "confidence": 0.0, "source": {"page": 1, "quote": "..."}},
    ... 全部18个字段都要出现 ...
  },
  "payment_schedules": [
    {"name": "首付款", "ratio": 30, "amount": 300000, "expected_date": null, "is_warranty": false,
     "confidence": 0.9, "source": {"page": 3, "quote": "..."}}
  ],
  "summary": "用一段话概括该合同（50字内）"
}

字段 key 列表：project_name, customer_name, contract_no, total_amount, excl_tax_amount, tax_rate,
tax_amount, sign_date, start_date, end_date, payment_terms, warranty_months, warranty_start_date,
warranty_ratio, warranty_amount, warranty_expected_date, invoice_requirements, notes"""


def _norm_field(kind: str, raw) -> dict:
    """归一化单个字段值。返回 {value, display}；无法解析 → value=None。"""
    if raw is None:
        return {"value": None, "display": None}
    if kind == "money":
        yuan = parse_money_text(raw)
        return {"value": yuan, "display": f"{yuan:,.2f}" if yuan is not None else None}
    if kind == "rate":
        try:
            v = float(str(raw).replace("%", "").strip())
            if 0 < v <= 1:  # 0.13 → 13%
                v = v * 100
            return {"value": v, "display": f"{v:g}%"}
        except Exception:
            return {"value": None, "display": None}
    if kind == "int":
        try:
            v = int(float(str(raw).strip().replace("个月", "").replace("月", "")))
            return {"value": v, "display": f"{v}个月"}
        except Exception:
            return {"value": None, "display": None}
    if kind == "date":
        d = parse_date_any(raw)
        return {"value": d.isoformat() if d else None, "display": d.isoformat() if d else None}
    # text
    s = str(raw).strip()
    return {"value": s or None, "display": s or None}


def _norm_source(src) -> dict:
    if not isinstance(src, dict):
        return {"page": None, "quote": None}
    page = src.get("page")
    try:
        page = int(page)
    except (TypeError, ValueError):
        page = None
    quote = str(src.get("quote") or "").strip()[:120] or None
    return {"page": page, "quote": quote}


def run_extraction(db: Session, *, file_row: UploadedFile | None = None,
                   text: str | None = None, filename: str = "粘贴文本.txt") -> ExtractionRecord:
    """执行一次 AI 识别，生成 pending 状态的 ExtractionRecord。"""
    from .settings_svc import get_settings
    s = get_settings(db)

    if file_row is not None:
        path = UPLOAD_DIR / file_row.stored_name
        parsed = parse_file(path, file_row.orig_name, file_row.mime)
        if parsed["error"]:
            raise AIError(parsed["error"])
        model = s.get("ai_model")
        content = build_llm_text(parsed)
        images = parsed.get("images", [])
    else:
        content = (text or "").strip()
        images = []
        model = s.get("ai_model")

    if not content and not images:
        raise AIError("没有可识别的文本内容（文件可能是纯扫描件且未配置视觉模型）。")

    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    if content:
        messages.append({"role": "user",
                         "content": f"请从以下合同原文中抽取信息：\n\n{content}"})
    else:
        blocks = [{"type": "text",
                   "text": "以下是合同扫描页图片，请先 OCR 再按规则抽取字段。"}]
        for im in images[:8]:
            blocks.append({"type": "image_url",
                           "image_url": {"url": f"data:image/png;base64,{im['b64']}"}})
        messages.append({"role": "user", "content": blocks})
        # 图片 OCR 用视觉模型
        model = s.get("ai_vision_model") or model

    raw_out = chat(db, messages, model=model, temperature=0.1, max_tokens=4096)
    data = extract_json(raw_out)

    # ── 归一化 ────────────────────────────────────────────────
    payload_fields: dict[str, dict] = {}
    raw_fields = data.get("fields") or {}
    for key, (label, kind) in FIELD_SPECS.items():
        rf = raw_fields.get(key)
        if not isinstance(rf, dict):
            rf = {"value": rf if raw_fields.get(key) is not None else None,
                  "confidence": None, "source": None}
        norm = _norm_field(kind, rf.get("value"))
        conf = rf.get("confidence")
        try:
            conf = round(float(conf), 2)
        except (TypeError, ValueError):
            conf = None
        value = norm["value"]
        needs_review = (
            value is None or conf is None or conf < LOW_CONFIDENCE
        )
        payload_fields[key] = {
            "label": label, "kind": kind,
            "value": value, "display": norm["display"] or (str(rf.get("value")) if value is None and rf.get("value") is not None else norm["display"]),
            "raw": rf.get("value"),
            "confidence": conf,
            "source": _norm_source(rf.get("source")),
            "needs_review": needs_review,
            "missing": value is None,
        }

    schedules_out: list[dict] = []
    for sch in (data.get("payment_schedules") or [])[:12]:
        if not isinstance(sch, dict):
            continue
        amount_yuan = parse_money_text(sch.get("amount")) if sch.get("amount") is not None else None
        ratio = None
        if sch.get("ratio") is not None:
            try:
                ratio = float(str(sch.get("ratio")).replace("%", ""))
                if 0 < ratio <= 1:
                    ratio *= 100
            except Exception:
                ratio = None
        d = parse_date_any(sch.get("expected_date"))
        conf = sch.get("confidence")
        try:
            conf = round(float(conf), 2)
        except (TypeError, ValueError):
            conf = None
        schedules_out.append({
            "name": str(sch.get("name") or "付款节点").strip()[:40],
            "ratio": ratio,
            "amount": amount_yuan,
            "expected_date": d.isoformat() if d else None,
            "is_warranty": bool(sch.get("is_warranty")) or ("质保" in str(sch.get("name") or "")),
            "confidence": conf,
            "source": _norm_source(sch.get("source")),
            "needs_review": conf is None or conf < LOW_CONFIDENCE,
        })

    digest = (content[:500] + ("…" if len(content) > 500 else "")) if content else "（图片扫描件）"
    record = ExtractionRecord(
        file_id=file_row.id if file_row else None,
        status="pending",
        engine="ai",
        model=model,
        payload_json=json.dumps({
            "fields": payload_fields,
            "payment_schedules": schedules_out,
            "summary": str(data.get("summary") or "")[:200],
            "truncated": bool(parsed["truncated"]) if file_row is not None else False,
            "page_count": len(parsed.get("pages", [])) if file_row is not None else 0,
            "image_pages": [im["page"] for im in images] if file_row is not None else [],
        }, ensure_ascii=False),
        raw_digest=digest,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def record_payload(record: ExtractionRecord) -> dict:
    return json.loads(record.payload_json or "{}")


# ── 确认写入 ──────────────────────────────────────────────────

def _clean_str(v, limit=200):
    if v is None:
        return None
    s = str(v).strip()
    return s[:limit] if s else None


def apply_to_project(db: Session, record: ExtractionRecord, body: dict) -> Project:
    """把用户确认后的数据写入项目（新建或并入）。只写用户提交的字段。"""
    mode = body.get("mode", "new")
    pdata = body.get("project") or {}
    cdata = body.get("contract") or {}
    sdata = body.get("schedules") or []
    replace_schedules = bool(body.get("replace_schedules"))

    if mode == "existing":
        pid = body.get("project_id")
        project = db.get(Project, pid) if pid else None
        if project is None:
            raise AIError("未找到要并入的项目。")
    else:
        name = _clean_str(pdata.get("name")) or "未命名项目"
        project = Project(
            name=name,
            status=_clean_str(pdata.get("status")) or "进行中",
        )
        db.add(project)
        db.flush()

    # 项目基础字段（提供才写）
    field_map = {
        "name": "name", "code": "code", "customer_name": "customer_name",
        "owner": "owner", "project_type": "project_type", "status": "status",
        "notes": "notes",
    }
    for k, attr in field_map.items():
        if k in pdata and pdata[k] is not None:
            setattr(project, attr, _clean_str(pdata[k], 500))
    for k in ("start_date", "end_date"):
        if k in pdata:
            d = parse_date_any(pdata[k])
            setattr(project, k, d)
    if "year" in pdata and pdata["year"]:
        try:
            project.year = int(pdata["year"])
        except (TypeError, ValueError):
            pass
    if not project.year:
        c0 = project.contract
        if c0 and c0.sign_date:
            project.year = c0.sign_date.year
        elif project.start_date:
            project.year = project.start_date.year
        else:
            project.year = datetime.now().year
    db.flush()

    # 合同字段
    contract = project.contract or Contract(project_id=project.id)
    if contract.id is None:
        db.add(contract)
    money_map = {
        "total_amount": "total_amount_cents",
        "tax_amount": "tax_amount_cents",
        "excl_tax_amount": "excl_tax_amount_cents",
        "warranty_amount": "warranty_amount_cents",
    }
    rate_map = {"tax_rate": "tax_rate_bp", "warranty_ratio": "warranty_ratio_bp"}
    date_map = {
        "sign_date": "sign_date", "warranty_start_date": "warranty_start_date",
        "warranty_expected_date": "warranty_expected_date",
        "warranty_actual_date": "warranty_actual_date",
    }
    for k, attr in money_map.items():
        if k in cdata:
            setattr(contract, attr, yuan_to_cents(cdata[k]))
    for k, attr in rate_map.items():
        if k in cdata:
            setattr(contract, attr, pct_to_bp(cdata[k]))
    for k, attr in date_map.items():
        if k in cdata:
            setattr(contract, attr, parse_date_any(cdata[k]))
    if "contract_no" in cdata:
        contract.contract_no = _clean_str(cdata["contract_no"])
    if "payment_terms" in cdata:
        contract.payment_terms = _clean_str(cdata["payment_terms"], 4000)
    if "warranty_months" in cdata:
        try:
            contract.warranty_months = int(cdata["warranty_months"]) if cdata["warranty_months"] not in (None, "") else None
        except (TypeError, ValueError):
            contract.warranty_months = None
    db.flush()

    # 程序补算：不含税金额 / 税额（仅当用户提供含税+税率且未同时给出时）
    if contract.total_amount_cents and contract.tax_rate_bp is not None:
        from .calc import derive_tax
        d_excl, d_tax = derive_tax(contract.total_amount_cents, contract.tax_rate_bp)
        if contract.excl_tax_amount_cents is None and d_excl is not None:
            contract.excl_tax_amount_cents = d_excl
        if contract.tax_amount_cents is None and d_tax is not None:
            contract.tax_amount_cents = d_tax
    elif contract.excl_tax_amount_cents and contract.tax_rate_bp is not None and contract.total_amount_cents is None:
        contract.total_amount_cents = int(
            __import__("decimal").Decimal(contract.excl_tax_amount_cents)
            * (10000 + contract.tax_rate_bp) / 10000
        )
    # 预计质保金到账日 = 质保期起算日 + 质保期月数（未明确给出时程序推算）
    if contract.warranty_months and contract.warranty_expected_date is None:
        from .money import add_months
        start = contract.warranty_start_date or project.end_date or project.start_date
        if start:
            contract.warranty_expected_date = add_months(start, contract.warranty_months)
    db.flush()

    # 付款节点
    if replace_schedules or mode == "new":
        if replace_schedules:
            for s in list(project.schedules):
                db.delete(s)
            db.flush()
        for i, sc in enumerate(sdata):
            db.add(PaymentSchedule(
                project_id=project.id,
                name=_clean_str(sc.get("name")) or f"节点{i + 1}",
                ratio_bp=pct_to_bp(sc.get("ratio")),
                amount_cents=yuan_to_cents(sc.get("amount")),
                expected_date=parse_date_any(sc.get("expected_date")),
                is_warranty=bool(sc.get("is_warranty")),
                sort_order=i,
            ))
    db.flush()

    # 关联附件 / 记录
    if record.file_id:
        f = db.get(UploadedFile, record.file_id)
        if f is not None:
            f.project_id = project.id
            f.kind = "contract"
    record.project_id = project.id
    record.status = "confirmed"
    record.confirmed_at = datetime.now()
    db.commit()
    db.refresh(project)
    return project
