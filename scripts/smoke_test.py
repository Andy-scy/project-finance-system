"""端到端冒烟测试：直接调用后端服务层（不依赖网络/AI），验证核心财务计算正确性。

运行：python scripts/smoke_test.py
"""
import io
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

# 使用独立测试数据库
tmpdir = tempfile.mkdtemp(prefix="pfs_test_")
os.environ["PFS_DATA_DIR"] = tmpdir

from app.database import SessionLocal, init_db  # noqa: E402
from app.models import (Contract, CostItem, Invoice, PaymentRecord,  # noqa: E402
                        PaymentSchedule, Project)
from app.services.calc import compute_project, derive_tax, load_context  # noqa: E402
from app.services.excelio import (export_projects_xlsx, export_template_xlsx,  # noqa: E402
                                  import_projects_xlsx)
from app.services.alerts import dashboard_data  # noqa: E402
from app.services.money import add_months, parse_money_text, parse_date_any, yuan_to_cents  # noqa: E402

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  {detail}")


init_db()
db = SessionLocal()

print("== 1. 金额与日期工具 ==")
check("yuan_to_cents(1000000) == 100000000", yuan_to_cents(1000000) == 100000000)
check("yuan_to_cents(1000000.5) 精确到分", yuan_to_cents(1000000.5) == 100000050)
check("parse_money_text('100万') == 1000000", parse_money_text("100万") == 1000000)
check("parse_money_text('￥1,000,000元') == 1000000", parse_money_text("￥1,000,000元") == 1000000)
check("parse_date_any('2026年3月1日')", parse_date_any("2026年3月1日") == date(2026, 3, 1))
check("add_months(2026-01-31, 1) == 2026-02-28", add_months(date(2026, 1, 31), 1) == date(2026, 2, 28))

print("== 2. 税额推导 ==")
excl, tax = derive_tax(100000000, 1300)  # 100万含税 13%
check("100万含税13% → 不含税 884,955.75", excl == 88495575, f"got {excl}")
check("税额 = 含税 - 不含税 = 115,044.25", tax == 11504425, f"got {tax}")
excl2, _ = derive_tax(100000000, 600)
check("100万含税6% → 不含税 943,396.23", excl2 == 94339623, f"got {excl2}")

print("== 3. 项目财务计算（100万合同/13%/30-40-20-10）==")
p = Project(name="测试项目", code="T-001", status="进行中", start_date=date(2026, 3, 1),
            end_date=date(2026, 12, 31), year=2026)
db.add(p)
db.flush()
c = Contract(project_id=p.id, contract_no="HT-001", total_amount_cents=100000000,
             tax_rate_bp=1300, excl_tax_amount_cents=88495575, tax_amount_cents=11504425,
             sign_date=date(2026, 2, 20), warranty_months=12,
             warranty_start_date=date(2026, 9, 1), warranty_ratio_bp=1000)
db.add(c)
nodes = [("首付款", 3000, 30000000, date(2026, 3, 1), False),
         ("中期款", 4000, 40000000, date(2026, 6, 1), False),
         ("尾款", 2000, 20000000, date(2026, 9, 1), False),
         ("质保金", 1000, 10000000, date(2027, 9, 1), True)]
node_ids = []
for i, (nm, ratio, amt, exp, w) in enumerate(nodes):
    s = PaymentSchedule(project_id=p.id, name=nm, ratio_bp=ratio, amount_cents=amt,
                        expected_date=exp, is_warranty=w, sort_order=i)
    db.add(s)
    db.flush()
    node_ids.append(s.id)
db.add(PaymentRecord(project_id=p.id, schedule_id=node_ids[0], amount_cents=30000000,
                     payment_date=date(2026, 3, 5), type="合同款"))
db.add(PaymentRecord(project_id=p.id, schedule_id=node_ids[1], amount_cents=40000000,
                     payment_date=date(2026, 6, 10), type="合同款"))
db.add(Invoice(project_id=p.id, amount_cents=70000000, issue_date=date(2026, 3, 4), invoice_no="001"))
db.add(CostItem(project_id=p.id, kind="direct", category="人工", amount_cents=25000000,
                cost_date=date(2026, 3, 15)))
db.add(CostItem(project_id=p.id, kind="direct", category="材料", amount_cents=15000000,
                cost_date=date(2026, 4, 1)))
db.add(CostItem(project_id=p.id, kind="indirect", category="管理费用", amount_cents=10000000,
                cost_date=date(2026, 5, 1)))
db.commit()

ctx = load_context(db, p)
cp = compute_project(ctx, {"tax_mode": "excl_tax", "reminder_days": [30, 7, 0]})
check("合同金额 = 1,000,000", cp["contract_amount"] == 1000000.0, cp["contract_amount"])
check("收入(不含税口径) = 884,955.75", abs(cp["revenue"] - 884955.75) < 0.01, cp["revenue"])
check("已到账 = 700,000", cp["received"] == 700000.0)
check("待到账 = 300,000", cp["pending"] == 300000.0)
check("回款比例 = 70%", cp["received_ratio"] == 70.0, cp["received_ratio"])
check("直接成本 = 400,000", cp["direct_cost"] == 400000.0)
check("间接成本 = 100,000", cp["indirect_cost"] == 100000.0)
check("总成本 = 500,000", cp["total_cost"] == 500000.0)
check("利润 = 收入-成本", abs(cp["profit"] - (884955.75 - 500000)) < 0.01, cp["profit"])
check("利润率 ≈ 43.5%", abs(cp["margin"] - 43.5) < 0.15, cp["margin"])
check("已开票 = 700,000", cp["invoiced"] == 700000.0)
check("未开票 = 300,000", cp["not_invoiced"] == 300000.0)
check("首付款节点已到账", cp["schedules"][0]["status"] == "已到账")
check("首付款节点实际到账 2026-03-05", cp["schedules"][0]["actual_date"] == "2026-03-05")
check("尾款节点未到账", cp["schedules"][2]["status"] == "未到账")
check("节点合计 = 合同金额", abs(cp["schedule_plan_sum"] - 1000000) < 0.01)
check("无一致性问题", len(cp["issues"]) == 0, cp["issues"])

print("== 4. 成本回收 ==")
# 成本发生至 2026-05-01 合计 30万；回款累计 2026-06-10 达 70万 → 回收日 2026-06-10
check("已收回成本", cp["recovery"]["recovered"] is True)
check("回收日期 = 2026-06-10", cp["recovery"]["recovery_date"] == "2026-06-10", cp["recovery"])
check("回收周期 = 101 天", cp["recovery"]["days"] == 101, cp["recovery"]["days"])

print("== 5. 质保金 ==")
w = cp["warranty"]
check("质保金金额 = 100,000（按比例10%推算）", w["amount"] == 100000.0, w["amount"])
check("预计到账 = 2027-09-01（起算+12月）", w["expected_date"] == "2027-09-01", w["expected_date"])
check("质保金状态为未到账", w["status"] in ("未到账",))

print("== 6. 含税口径 ==")
cp2 = compute_project(ctx, {"tax_mode": "incl_tax", "reminder_days": [30, 7, 0]})
check("收入(含税口径) = 1,000,000", cp2["revenue"] == 1000000.0)

print("== 7. 异常检测 ==")
dash = dashboard_data(db, 2026)
check("KPI 项目数 = 1", dash["kpis"]["project_count"] == 1)
check("KPI 合同总额 = 100万", dash["kpis"]["contract_amount"] == 1000000.0)

# 构造异常：到账超过合同
db.add(PaymentRecord(project_id=p.id, amount_cents=40000000, payment_date=date(2026, 8, 1), type="其他"))
db.commit()
db.expire_all()  # 让关系缓存失效，重新加载
cp3 = compute_project(load_context(db, p), {"tax_mode": "excl_tax"})
check("检测到「到账超合同」", any(i["code"] == "received_over" for i in cp3["issues"]), cp3["issues"])
codes = {i["code"] for i in cp3["issues"]}
dash = dashboard_data(db, 2026)
check("Dashboard 待处理事项包含超收预警",
      any(a["code"] == "received_over" for a in dash["alerts"]), [a["code"] for a in dash["alerts"]])

print("== 8. Excel 导出/导入 ==")
xlsx = export_projects_xlsx(db, 2026)
check("导出 Excel 非空", len(xlsx) > 4000)
template = export_template_xlsx()
result = import_projects_xlsx(db, template)
check("导入模板（示例行不写入）", result["ok"] and result["created"] == 0, result)

print("== 9. 数据一致性检查（节点不匹配）==")
db.add(PaymentSchedule(project_id=p.id, name="多余节点", amount_cents=1234500, sort_order=9))
db.commit()
db.expire_all()
cp4 = compute_project(load_context(db, p), {"tax_mode": "excl_tax"})
check("检测到「节点金额与合同不一致」", any(i["code"] == "schedule_mismatch" for i in cp4["issues"]))

print()
print(f"结果：{PASS} 通过，{FAIL} 失败")
sys.exit(1 if FAIL else 0)
