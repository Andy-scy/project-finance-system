"""ORM 数据模型。

金额一律以整数「分」（BIGINT）存储，避免浮点误差；
对外 API 层统一转换为「元」。日期使用 SQLAlchemy Date（SQLite 中存 ISO 字符串）。
税率以「基点」整数存储：1300 = 13.00%。
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _now():
    return datetime.now()


class Company(Base):
    """公司主体（多公司切换）。"""

    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text)                        # 公司名称
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), index=True)  # 所属公司
    name: Mapped[str] = mapped_column(Text)                       # 项目名称（必填）
    code: Mapped[str | None] = mapped_column(Text)                # 项目编号
    customer_name: Mapped[str | None] = mapped_column(Text)       # 客户名称
    owner: Mapped[str | None] = mapped_column(Text)               # 项目负责人
    project_type: Mapped[str | None] = mapped_column(Text)        # 项目类型
    status: Mapped[str] = mapped_column(Text, default="未开始")    # 项目状态
    start_date: Mapped[date | None] = mapped_column(Date)         # 项目开始日期
    end_date: Mapped[date | None] = mapped_column(Date)           # 项目结束日期
    year: Mapped[int | None] = mapped_column(Integer)             # 归属年度（看板归集用）
    notes: Mapped[str | None] = mapped_column(Text)               # 备注
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    company: Mapped["Company | None"] = relationship()

    contract: Mapped["Contract | None"] = relationship(
        back_populates="project", uselist=False, cascade="all, delete-orphan"
    )
    schedules: Mapped[list["PaymentSchedule"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="PaymentSchedule.sort_order"
    )
    payments: Mapped[list["PaymentRecord"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    invoices: Mapped[list["Invoice"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    costs: Mapped[list["CostItem"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    files: Mapped[list["UploadedFile"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class Contract(Base):
    """合同信息（与项目 1:1）。"""

    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), unique=True)
    contract_no: Mapped[str | None] = mapped_column(Text)              # 合同编号
    total_amount_cents: Mapped[int | None] = mapped_column(BigInteger)  # 含税合同总金额（分）
    tax_rate_bp: Mapped[int | None] = mapped_column(Integer)           # 税率（基点 1300=13%）
    tax_amount_cents: Mapped[int | None] = mapped_column(BigInteger)   # 税额（分）
    excl_tax_amount_cents: Mapped[int | None] = mapped_column(BigInteger)  # 不含税金额（分）
    sign_date: Mapped[date | None] = mapped_column(Date)               # 合同签订日期
    contract_end_date: Mapped[date | None] = mapped_column(Date)       # 合同到期日（续签提醒依据，缺省用项目结束日期）
    payment_terms: Mapped[str | None] = mapped_column(Text)            # 付款条款原文
    warranty_months: Mapped[int | None] = mapped_column(Integer)       # 质保期（月）
    warranty_start_date: Mapped[date | None] = mapped_column(Date)     # 质保期起算日
    warranty_ratio_bp: Mapped[int | None] = mapped_column(Integer)     # 质保金比例（基点）
    warranty_amount_cents: Mapped[int | None] = mapped_column(BigInteger)  # 质保金金额（分）
    warranty_expected_date: Mapped[date | None] = mapped_column(Date)  # 预计质保金到账日期
    warranty_actual_date: Mapped[date | None] = mapped_column(Date)    # 实际质保金到账日期

    project: Mapped[Project] = relationship(back_populates="contract")


class PaymentSchedule(Base):
    """付款节点。计划数据保存于本表，实际到账情况由回款记录实时汇总。"""

    __tablename__ = "payment_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(Text, default="")                 # 节点名称
    ratio_bp: Mapped[int | None] = mapped_column(Integer)               # 比例（基点）
    amount_cents: Mapped[int | None] = mapped_column(BigInteger)        # 计划金额（分）
    expected_date: Mapped[date | None] = mapped_column(Date)            # 预计到账日期
    is_warranty: Mapped[bool] = mapped_column(Boolean, default=False)   # 是否质保金节点
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str | None] = mapped_column(Text)

    project: Mapped[Project] = relationship(back_populates="schedules")


class PaymentRecord(Base):
    """回款记录（一项目多笔到账）。"""

    __tablename__ = "payment_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    schedule_id: Mapped[int | None] = mapped_column(ForeignKey("payment_schedules.id"))
    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id"))
    amount_cents: Mapped[int] = mapped_column(BigInteger)               # 回款金额（分）
    payment_date: Mapped[date] = mapped_column(Date)                    # 回款日期
    type: Mapped[str] = mapped_column(Text, default="合同款")            # 合同款/质保金/其他
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    project: Mapped[Project] = relationship(back_populates="payments")
    schedule: Mapped["PaymentSchedule | None"] = relationship()
    invoice: Mapped["Invoice | None"] = relationship()


class Invoice(Base):
    """发票记录。"""

    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    invoice_no: Mapped[str | None] = mapped_column(Text)                # 发票号码
    amount_cents: Mapped[int] = mapped_column(BigInteger)               # 开票金额（分）
    issue_date: Mapped[date] = mapped_column(Date)                      # 开票日期
    type: Mapped[str] = mapped_column(Text, default="销项发票")
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    project: Mapped[Project] = relationship(back_populates="invoices")


class CostItem(Base):
    """成本明细。kind=direct 直接成本 / indirect 间接成本。"""

    __tablename__ = "cost_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    kind: Mapped[str] = mapped_column(Text)                             # direct / indirect
    category: Mapped[str] = mapped_column(Text, default="其他")          # 分类
    amount_cents: Mapped[int] = mapped_column(BigInteger)               # 金额（分）
    cost_date: Mapped[date] = mapped_column(Date)                       # 发生日期
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    project: Mapped[Project] = relationship(back_populates="costs")


class UploadedFile(Base):
    """上传的合同 / 项目文件（保存在本地 data/uploads）。"""

    __tablename__ = "uploaded_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), index=True)
    orig_name: Mapped[str] = mapped_column(Text)
    stored_name: Mapped[str] = mapped_column(Text)
    mime: Mapped[str | None] = mapped_column(Text)
    size: Mapped[int] = mapped_column(Integer, default=0)
    kind: Mapped[str] = mapped_column(Text, default="other")            # contract / other
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    project: Mapped[Project | None] = relationship(back_populates="files")


class ExtractionRecord(Base):
    """AI 识别记录。识别结果必须经用户确认后才写入项目。"""

    __tablename__ = "extraction_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), index=True)
    file_id: Mapped[int | None] = mapped_column(ForeignKey("uploaded_files.id"))
    status: Mapped[str] = mapped_column(Text, default="pending")        # pending/confirmed/discarded
    engine: Mapped[str] = mapped_column(Text, default="ai")             # ai / manual
    model: Mapped[str | None] = mapped_column(Text)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")       # 结构化识别结果
    raw_digest: Mapped[str | None] = mapped_column(Text)                # 原文摘要
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)


class Setting(Base):
    """系统设置（KV）。"""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str | None] = mapped_column(Text)
