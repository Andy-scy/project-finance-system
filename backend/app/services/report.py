"""年度经营分析报告（PDF）生成：reportlab 排版 + matplotlib 图表。

正式报告结构：年度项目总览 / 合同金额 / 收入 / 成本 / 利润与利润率 /
回款情况 / 发票情况 / 质保金情况 / 重点项目分析 / 异常项目 / 年度趋势图表。
"""
from __future__ import annotations

import io
import os
from datetime import date, datetime

import matplotlib
matplotlib.use("Agg")

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

from sqlalchemy.orm import Session

from .alerts import dashboard_data
from .settings_svc import get_settings

# ── 中文字体注册 ──────────────────────────────────────────────
FONT = "Helvetica"
FONT_BOLD = "Helvetica-Bold"


def _register_fonts():
    global FONT, FONT_BOLD
    import reportlab.pdfbase.pdfmetrics as pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    candidates = [
        ("msyh", r"C:\Windows\Fonts\msyh.ttc", 0),
        ("simhei", r"C:\Windows\Fonts\simhei.ttf", None),
        ("simsun", r"C:\Windows\Fonts\simsun.ttc", 0),
        ("deng", r"C:\Windows\Fonts\Deng.ttf", None),
    ]
    for name, path, idx in candidates:
        if not os.path.exists(path):
            continue
        try:
            if idx is None:
                pdfmetrics.registerFont(TTFont(name, path))
            else:
                pdfmetrics.registerFont(TTFont(name, path, subfontIndex=idx))
            FONT = name
            FONT_BOLD = name
            return path
        except Exception:
            continue
    return None


def _setup_matplotlib(font_path: str | None):
    from matplotlib import font_manager, rcParams
    if font_path:
        try:
            font_manager.fontManager.addfont(font_path)
            fam = font_manager.FontProperties(fname=font_path).get_name()
            rcParams["font.family"] = fam
        except Exception:
            pass
    else:
        rcParams["font.family"] = ["Microsoft YaHei", "SimHei", "sans-serif"]
    rcParams["axes.unicode_minus"] = False


PRIMARY = colors.HexColor("#1F4E79")
LIGHT = colors.HexColor("#EAF1F8")
DANGER = colors.HexColor("#C0392B")
GREEN = colors.HexColor("#1E8449")
GREY = colors.HexColor("#666666")


def _styles():
    h1 = ParagraphStyle("h1", fontName=FONT, fontSize=20, leading=28,
                        alignment=1, textColor=PRIMARY, spaceAfter=6)
    sub = ParagraphStyle("sub", fontName=FONT, fontSize=10, leading=14,
                         alignment=1, textColor=GREY, spaceAfter=14)
    h2 = ParagraphStyle("h2", fontName=FONT, fontSize=13, leading=18,
                        textColor=PRIMARY, spaceBefore=14, spaceAfter=6)
    body = ParagraphStyle("body", fontName=FONT, fontSize=9.5, leading=15)
    small = ParagraphStyle("small", fontName=FONT, fontSize=8, leading=11, textColor=GREY)
    return h1, sub, h2, body, small


def _kv_table(rows, col_widths=None):
    data = [[Paragraph(f"<b>{k}</b>", ParagraphStyle("k", fontName=FONT, fontSize=9)),
             Paragraph(f"<b>{v}</b>", ParagraphStyle("v", fontName=FONT, fontSize=9))]
            for k, v in rows]
    t = Table(data, colWidths=col_widths or [45 * mm, 110 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), LIGHT),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B9CCE0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def _data_table(headers, rows, money_cols=(), danger_rows=(), col_widths=None):
    cell = ParagraphStyle("c", fontName=FONT, fontSize=8.5, leading=11)
    cell_r = ParagraphStyle("cr", fontName=FONT, fontSize=8.5, leading=11, alignment=2)
    head = ParagraphStyle("h", fontName=FONT, fontSize=8.5, leading=11,
                          textColor=colors.white, alignment=1)
    data = [[Paragraph(str(h), head) for h in headers]]
    for i, row in enumerate(rows):
        line = []
        for j, v in enumerate(row):
            st = cell_r if j in money_cols else cell
            if i in danger_rows:
                st = ParagraphStyle(f"d{i}{j}", parent=st, textColor=DANGER)
            line.append(Paragraph("—" if v is None or v == "" else str(v), st))
        data.append(line)
    t = Table(data, colWidths=col_widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B9CCE0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F8FC")]),
    ]
    t.setStyle(TableStyle(style))
    return t


def _fmt_money(v, dash="—"):
    if v is None:
        return dash
    return f"{v:,.2f}"


def _chart_monthly(charts) -> bytes:
    import matplotlib.pyplot as plt
    m = charts["monthly"]
    fig, ax = plt.subplots(figsize=(7.2, 2.9), dpi=150)
    x = range(12)
    ax.bar([i - 0.2 for i in x], m["sign"], width=0.4, label="签约合同额", color="#8FB4D9")
    ax.bar([i + 0.2 for i in x], m["payment"], width=0.4, label="实际回款", color="#1F4E79")
    ax.plot(x, m["cost"], marker="o", markersize=3, linewidth=1.4, label="成本发生", color="#C0392B")
    ax.set_xticks(list(x))
    ax.set_xticklabels(m["months"], fontsize=8)
    ax.legend(fontsize=8, frameon=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(labelsize=8)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v/10000:g}万")
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()


def _chart_cost(charts) -> bytes:
    import matplotlib.pyplot as plt
    cs = charts["cost_structure"]
    fig, ax = plt.subplots(figsize=(3.4, 2.6), dpi=150)
    segs = [("直接成本", cs["direct"], "#1F4E79"),
            ("间接成本", cs["indirect"], "#8FB4D9"),
            ("税金成本", cs.get("tax", 0), "#E67E22")]
    segs = [(n, v, c) for n, v, c in segs if v and v > 0]
    if not segs:
        ax.text(0.5, 0.5, "本年度无成本数据", ha="center", va="center", fontsize=9)
        ax.axis("off")
    else:
        ax.pie([v for _, v, _ in segs], labels=[n for n, _, _ in segs],
               autopct="%1.1f%%", colors=[c for _, _, c in segs],
               textprops={"fontsize": 8}, startangle=90)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()


def _chart_payment(charts) -> bytes:
    import matplotlib.pyplot as plt
    ps = charts["payment_status"]
    fig, ax = plt.subplots(figsize=(3.4, 2.6), dpi=150)
    vals = [ps["received"], ps["pending"], ps["warranty"]]
    labels = ["已到账", "待到账", "待收质保金"]
    colors_ = ["#1E8449", "#C0392B", "#E67E22"]
    if sum(vals) <= 0:
        ax.text(0.5, 0.5, "本年度无回款数据", ha="center", va="center", fontsize=9)
        ax.axis("off")
    else:
        ax.pie(vals, labels=labels, autopct="%1.1f%%", colors=colors_,
               textprops={"fontsize": 8}, startangle=90)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()


def generate_annual_report(db: Session, year: int) -> bytes:
    settings = get_settings(db)
    font_path = _register_fonts()
    _setup_matplotlib(font_path)
    data = dashboard_data(db, year)
    kpis, charts, alerts, projects = data["kpis"], data["charts"], data["alerts"], data["projects"]
    h1, sub, h2, body, small = _styles()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, topMargin=18 * mm, bottomMargin=16 * mm,
        leftMargin=18 * mm, rightMargin=18 * mm,
        title=f"{year}年度项目经营分析报告",
    )

    def footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont(FONT, 8)
        canvas.setFillColor(GREY)
        canvas.drawString(18 * mm, 10 * mm, f"{year}年度项目经营分析报告")
        canvas.drawRightString(192 * mm, 10 * mm, f"第 {canvas.getPageNumber()} 页")
        canvas.restoreState()

    story = []
    mode_txt = "不含税收入" if settings.get("tax_mode") == "excl_tax" else "含税收入"
    story.append(Paragraph(f"{year} 年度项目经营分析报告", h1))
    story.append(Paragraph(
        f"报告生成日期：{date.today().isoformat()}　|　利润计算口径：{mode_txt}　|　项目总数：{kpis['project_count']} 个",
        sub))

    # 1. 年度总览
    story.append(Paragraph("一、年度项目总览", h2))
    overview_rows = [
        ("项目总数", f"{kpis['project_count']} 个"),
        ("项目合同总额（含税）", f"¥ {_fmt_money(kpis['contract_amount'])}"),
        ("年度收入（{0}）".format(mode_txt), f"¥ {_fmt_money(kpis['revenue'])}"),
        ("总成本（直接 {0} + 间接 {1} + 税金 {2}）".format(
            _fmt_money(kpis['direct_cost']), _fmt_money(kpis['indirect_cost']), _fmt_money(kpis['tax_cost'])),
         f"¥ {_fmt_money(kpis['total_cost'])}"),
        ("总利润", f"¥ {_fmt_money(kpis['profit'])}"),
        ("加权平均利润率", f"{kpis['avg_margin']}%" if kpis["avg_margin"] is not None else "—"),
        ("已到账 / 待到账", f"¥ {_fmt_money(kpis['received'])} / ¥ {_fmt_money(kpis['pending'])}"),
        ("已开票 / 未开票", f"¥ {_fmt_money(kpis['invoiced'])} / ¥ {_fmt_money(kpis['not_invoiced'])}"),
        ("已收回成本项目 / 尚未收回", f"{kpis['recovered_count']} 个 / {kpis['not_recovered_count']} 个"),
        ("待收质保金", f"¥ {_fmt_money(kpis['warranty_pending'])}"),
        ("待处理事项", f"{len(alerts)} 项（其中紧急 {sum(1 for a in alerts if a['level']=='danger')} 项）"),
    ]
    story.append(_kv_table(overview_rows))

    # 2. 项目明细
    story.append(Paragraph("二、项目明细", h2))
    rows, danger_rows = [], []
    for i, pj in enumerate(projects):
        cp = pj["computed"]
        if cp["profit"] is not None and cp["profit"] < 0:
            danger_rows.append(i + 1)
        rows.append([
            pj["name"][:16], pj["status"],
            _fmt_money(cp["contract_amount"]), _fmt_money(cp["received"]),
            _fmt_money(cp["pending"]), _fmt_money(cp["total_cost"]),
            _fmt_money(cp["profit"]),
            f"{cp['margin']}%" if cp["margin"] is not None else "—",
            "已回收" if cp["recovery"]["recovered"] else ("无成本" if not cp["has_cost_data"] else "未回收"),
        ])
    if rows:
        story.append(_data_table(
            ["项目", "状态", "合同金额", "已到账", "待到账", "总成本", "利润", "利润率", "成本回收"],
            rows, money_cols={2, 3, 4, 5, 6},
            col_widths=[36 * mm, 14 * mm, 22 * mm, 22 * mm, 22 * mm, 22 * mm, 22 * mm, 14 * mm, 16 * mm]))
    else:
        story.append(Paragraph(f"{year} 年度暂无项目数据。", body))

    story.append(PageBreak())

    # 3. 趋势图表
    story.append(Paragraph("三、年度趋势：签约 / 回款 / 成本", h2))
    story.append(Image(io.BytesIO(_chart_monthly(charts)), width=170 * mm, height=68 * mm))

    # 4. 成本与回款结构
    story.append(Paragraph("四、成本构成与回款情况", h2))
    img_t = Table([[Image(io.BytesIO(_chart_cost(charts)), width=80 * mm, height=61 * mm),
                    Image(io.BytesIO(_chart_payment(charts)), width=80 * mm, height=61 * mm)]],
                  colWidths=[85 * mm, 85 * mm])
    img_t.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    story.append(img_t)

    # 5. 重点项目分析
    story.append(Paragraph("五、重点项目分析（按利润排序）", h2))
    top = sorted([p for p in projects if p["computed"].get("profit") is not None],
                 key=lambda p: p["computed"]["profit"], reverse=True)[:5]
    if top:
        rows = [[p["name"][:20], _fmt_money(p["computed"]["contract_amount"]),
                 _fmt_money(p["computed"]["revenue"]), _fmt_money(p["computed"]["total_cost"]),
                 _fmt_money(p["computed"]["profit"]),
                 f"{p['computed']['margin']}%" if p["computed"]["margin"] is not None else "—"]
                for p in top]
        story.append(_data_table(["项目", "合同金额", "收入", "总成本", "利润", "利润率"],
                                 rows, money_cols={1, 2, 3, 4},
                                 col_widths=[52 * mm, 25 * mm, 25 * mm, 25 * mm, 25 * mm, 20 * mm]))
    else:
        story.append(Paragraph("暂无可参与排名的项目（缺少收入或成本数据）。", body))

    # 6. 质保金情况
    story.append(Paragraph("六、质保金情况", h2))
    wrows = []
    for pj in projects:
        w = pj["computed"]["warranty"]
        if not w.get("amount"):
            continue
        wrows.append([pj["name"][:18], _fmt_money(w["amount"]),
                      w.get("expected_date") or "—", w.get("actual_date") or "—",
                      w["status"]])
    if wrows:
        status_style = {r: DANGER for r, row in enumerate(wrows, start=1) if row[4] == "已到期未到账"}
        t = _data_table(["项目", "质保金金额", "预计到账日", "实际到账日", "状态"],
                        wrows, money_cols={1},
                        col_widths=[52 * mm, 28 * mm, 30 * mm, 30 * mm, 26 * mm])
        story.append(t)
        story.append(Spacer(1, 4))
        story.append(Paragraph("状态说明：已到账 / 即将到账 / 已到期未到账 / 日期未知。", small))
    else:
        story.append(Paragraph("本年度项目暂无质保金数据。", body))

    # 7. 异常项目与待处理事项
    story.append(Paragraph("七、异常项目与待处理事项", h2))
    if alerts:
        rows = [[
            {"danger": "紧急", "warning": "预警", "info": "提示"}.get(a["level"], a["level"]),
            a["project_name"][:14], a["title"], a["detail"][:60],
        ] for a in alerts]
        story.append(_data_table(["级别", "项目", "事项", "说明"], rows,
                                 col_widths=[14 * mm, 34 * mm, 42 * mm, 80 * mm]))
    else:
        story.append(Paragraph("未发现异常事项。", body))

    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "报告说明：本报告由项目财务与合同管理系统根据项目档案自动生成，"
        "利润与利润率等指标为系统实时计算结果，数据以项目档案录入为准。", small))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
