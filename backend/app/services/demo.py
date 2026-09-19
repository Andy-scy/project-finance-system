"""示例数据：一键生成一套覆盖常见场景的演示项目（含各类异常，便于验收提醒功能）。"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from ..models import (Contract, CostItem, ExtractionRecord, Invoice, PaymentRecord,
                      PaymentSchedule, Project, Setting, UploadedFile)


def seed_demo(db: Session, force: bool = False) -> dict:
    n = db.query(Project).count()
    if n and not force:
        return {"ok": False, "error": f"数据库中已有 {n} 个项目。如需覆盖请选择「清空数据」后再载入。"}
    if force:
        for table in (ExtractionRecord, UploadedFile, PaymentRecord, PaymentSchedule,
                      Invoice, CostItem, Contract, Project, Setting):
            db.query(table).delete()
        db.commit()
        from .settings_svc import ensure_defaults
        ensure_defaults(db)

    def d(y, m, dd):
        return date(y, m, dd)

    # (name, code, customer, owner, type, status, start, end, year, cno, total, rate, sign,
    #  terms, w_months, w_ratio, w_amount, nodes, payments, invoices, costs)
    P = []

    def add(name, code, customer, owner, ptype, status, start, end, year, cno, total, rate, sign,
            w_months, nodes, payments, invoices, costs, w_start=None):
        P.append(dict(name=name, code=code, customer=customer, owner=owner, ptype=ptype,
                      status=status, start=start, end=end, year=year, cno=cno, total=total,
                      rate=rate, sign=sign, w_months=w_months, nodes=nodes, payments=payments,
                      invoices=invoices, costs=costs, w_start=w_start))

    # 1. 标准项目：100万 / 13% / 30-40-20-10，已收70%
    add("智慧园区综合管理平台", "XM-2026-001", "高新园区开发有限公司", "王建国", "软件开发", "进行中",
        d(2026, 3, 1), d(2026, 12, 31), 2026, "HT-2026-001", 1000000, 13, d(2026, 2, 20), 12,
        [("首付款", 30, 300000, d(2026, 3, 1), False),
         ("中期款", 40, 400000, d(2026, 6, 1), False),
         ("尾款", 20, 200000, d(2026, 9, 1), False),
         ("质保金", 10, 100000, d(2027, 9, 1), True)],
        [(300000, d(2026, 3, 5), "合同款", "首付款"), (400000, d(2026, 6, 10), "合同款", "中期款")],
        [(300000, d(2026, 3, 4), "001"), (400000, d(2026, 6, 9), "002")],
        [("direct", "人工", 210000, d(2026, 3, 15)), ("direct", "外包", 95000, d(2026, 4, 20)),
         ("direct", "设备", 68000, d(2026, 5, 10)), ("indirect", "项目管理费用", 45000, d(2026, 5, 31)),
         ("indirect", "差旅", 18000, d(2026, 6, 20))])

    # 2. 亏损项目：成本超收入
    add("厂房智能化改造二期", "XM-2026-002", "宏远制造集团", "李梅", "系统集成", "进行中",
        d(2026, 1, 10), d(2026, 8, 30), 2026, "HT-2026-002", 600000, 9, d(2026, 1, 5), 12,
        [("首付款", 30, 180000, d(2026, 1, 15), False),
         ("验收款", 50, 300000, d(2026, 9, 1), False),
         ("质保金", 20, 120000, d(2027, 9, 1), True)],
        [(180000, d(2026, 1, 20), "合同款", "首付款")],
        [(180000, d(2026, 1, 19), "011")],
        [("direct", "材料", 380000, d(2026, 2, 1)), ("direct", "人工", 160000, d(2026, 3, 1)),
         ("direct", "运输", 25000, d(2026, 3, 10)), ("indirect", "管理费用", 42000, d(2026, 4, 1))])

    # 3. 2025 已结算项目：全额回款+质保金已收，成本已回收
    add("数据中心机房建设", "XM-2025-001", "云图数据科技", "赵磊", "工程实施", "已结算",
        d(2025, 2, 1), d(2025, 10, 31), 2025, "HT-2025-001", 2360000, 6, d(2025, 1, 15), 12,
        [("首付款", 30, 708000, d(2025, 2, 1), False),
         ("进度款", 40, 944000, d(2025, 6, 1), False),
         ("验收款", 20, 472000, d(2025, 11, 1), False),
         ("质保金", 10, 236000, d(2026, 11, 1), True)],
        [(708000, d(2025, 2, 10), "合同款", "首付款"), (944000, d(2025, 6, 15), "合同款", "进度款"),
         (472000, d(2025, 11, 20), "合同款", "验收款"), (236000, d(2026, 11, 5), "质保金", "质保金")],
        [(708000, d(2025, 2, 8), "101"), (944000, d(2025, 6, 14), "102"),
         (472000, d(2025, 11, 18), "103"), (236000, d(2026, 11, 4), "104")],
        [("direct", "设备", 1200000, d(2025, 3, 1)), ("direct", "人工", 350000, d(2025, 5, 1)),
         ("direct", "外包", 180000, d(2025, 6, 1)), ("indirect", "项目管理费用", 90000, d(2025, 7, 1)),
         ("indirect", "差旅", 45000, d(2025, 8, 1))])

    # 4. 质保金即将到账（2026-09-20 附近）
    add("市政管网监测系统", "XM-2025-002", "市政公用事业管理局", "陈晓", "软件开发", "已完成",
        d(2025, 3, 1), d(2025, 9, 10), 2025, "HT-2025-002", 890000, 6, d(2025, 2, 20), 12,
        [("首付款", 40, 356000, d(2025, 3, 1), False),
         ("验收款", 50, 445000, d(2025, 10, 1), False),
         ("质保金", 10, 89000, d(2026, 9, 20), True)],
        [(356000, d(2025, 3, 10), "合同款", "首付款"), (445000, d(2025, 10, 15), "合同款", "验收款")],
        [(356000, d(2025, 3, 8), "111"), (445000, d(2025, 10, 14), "112")],
        [("direct", "人工", 260000, d(2025, 4, 1)), ("direct", "设备", 210000, d(2025, 5, 1)),
         ("indirect", "办公费用", 30000, d(2025, 6, 1))], w_start=d(2025, 9, 20))

    # 5. 质保金已到期未到账
    add("企业官网及小程序开发", "XM-2026-003", "蓝海贸易有限公司", "孙倩", "软件开发", "已完成",
        d(2025, 6, 1), d(2025, 8, 31), 2025, "HT-2025-003", 180000, 6, d(2025, 5, 20), 12,
        [("首付款", 50, 90000, d(2025, 6, 1), False),
         ("尾款", 40, 72000, d(2025, 9, 1), False),
         ("质保金", 10, 18000, d(2026, 8, 31), True)],
        [(90000, d(2025, 6, 5), "合同款", "首付款"), (72000, d(2025, 9, 10), "合同款", "尾款")],
        [(90000, d(2025, 6, 4), "121"), (72000, d(2025, 9, 9), "122")],
        [("direct", "人工", 70000, d(2025, 7, 1)), ("indirect", "管理费用", 15000, d(2025, 8, 1))],
        w_start=d(2025, 8, 31))

    # 6. 开票长期未回款
    add("生产线视觉检测系统", "XM-2026-004", "精工机械股份公司", "周平", "设备供应", "进行中",
        d(2026, 4, 1), d(2026, 10, 31), 2026, "HT-2026-004", 1580000, 13, d(2026, 3, 15), 12,
        [("预付款", 30, 474000, d(2026, 4, 1), False),
         ("到货款", 40, 632000, d(2026, 7, 1), False),
         ("验收款", 20, 316000, d(2026, 11, 1), False),
         ("质保金", 10, 158000, d(2027, 11, 1), True)],
        [(474000, d(2026, 4, 10), "合同款", "预付款")],
        [(474000, d(2026, 4, 8), "131"), (632000, d(2026, 7, 2), "132")],
        [("direct", "设备", 640000, d(2026, 5, 1)), ("direct", "人工", 210000, d(2026, 6, 1)),
         ("indirect", "差旅", 38000, d(2026, 6, 15))])

    # 7. 未开始：有合同无成本
    add("仓储物流自动化项目", "XM-2026-005", "迅达物流集团", "吴刚", "系统集成", "未开始",
        None, d(2027, 6, 30), 2026, "HT-2026-005", 3200000, 13, d(2026, 8, 1), 24,
        [("预付款", 30, 960000, d(2026, 9, 1), False),
         ("进度款", 40, 1280000, d(2027, 1, 1), False),
         ("验收款", 20, 640000, d(2027, 7, 1), False),
         ("质保金", 10, 320000, d(2028, 7, 1), True)],
        [], [], [])

    # 8. 到账超合同（多收预付款异常）
    add("老旧小区安防升级", "XM-2025-004", "幸福里社区居委会", "郑华", "工程实施", "已关闭",
        d(2025, 5, 1), d(2025, 7, 31), 2025, "HT-2025-004", 420000, 9, d(2025, 4, 20), 12,
        [("首付款", 50, 210000, d(2025, 5, 1), False),
         ("尾款", 50, 210000, d(2025, 8, 1), False)],
        [(210000, d(2025, 5, 10), "合同款", "首付款"), (220000, d(2025, 8, 15), "合同款", "尾款")],
        [(210000, d(2025, 5, 9), "141")],
        [("direct", "设备", 180000, d(2025, 5, 20)), ("direct", "人工", 90000, d(2025, 6, 10)),
         ("indirect", "管理费用", 20000, d(2025, 7, 1))])

    for spec in P:
        p = Project(
            name=spec["name"], code=spec["code"], customer_name=spec["customer"],
            owner=spec["owner"], project_type=spec["ptype"], status=spec["status"],
            start_date=spec["start"], end_date=spec["end"], year=spec["year"],
        )
        db.add(p)
        db.flush()
        from decimal import Decimal, ROUND_HALF_UP
        total_c = int(Decimal(str(spec["total"])) * 100)
        rate_bp = int(spec["rate"] * 100)
        excl = int((Decimal(total_c) * 10000 / (10000 + rate_bp)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        c = Contract(
            project_id=p.id, contract_no=spec["cno"], total_amount_cents=total_c,
            tax_rate_bp=rate_bp, excl_tax_amount_cents=excl, tax_amount_cents=total_c - excl,
            sign_date=spec["sign"], payment_terms="、".join(f"{n[0]}{n[1]}%" for n in spec["nodes"]),
            warranty_months=spec["w_months"],
            warranty_ratio_bp=spec["nodes"][-1][1] * 100 if spec["nodes"][-1][4] else None,
            warranty_amount_cents=next((int(Decimal(str(n[2])) * 100) for n in spec["nodes"] if n[4]), None),
            warranty_expected_date=next((n[3] for n in spec["nodes"] if n[4]), None),
        )
        if spec.get("w_start"):
            c.warranty_start_date = spec["w_start"]
        db.add(c)
        for i, (nm, ratio, amount, expected, is_w) in enumerate(spec["nodes"]):
            db.add(PaymentSchedule(project_id=p.id, name=nm, ratio_bp=int(ratio * 100),
                                   amount_cents=int(Decimal(str(amount)) * 100),
                                   expected_date=expected, is_warranty=is_w, sort_order=i))
        db.flush()  # autoflush=False，需显式 flush 才能查出节点 id
        name2id = {s.name: s.id for s in db.query(PaymentSchedule).filter_by(project_id=p.id).all()}
        for amount, pdate, ptype, node_name in spec["payments"]:
            db.add(PaymentRecord(project_id=p.id, amount_cents=int(Decimal(str(amount)) * 100),
                                 payment_date=pdate, type=ptype, schedule_id=name2id.get(node_name)))
        for amount, idate, no in spec["invoices"]:
            db.add(Invoice(project_id=p.id, amount_cents=int(Decimal(str(amount)) * 100),
                           issue_date=idate, invoice_no=no))
        for kind, cat, amount, cdate in spec["costs"]:
            db.add(CostItem(project_id=p.id, kind=kind, category=cat,
                            amount_cents=int(Decimal(str(amount)) * 100), cost_date=cdate))
    db.commit()
    return {"ok": True, "created": len(P)}
