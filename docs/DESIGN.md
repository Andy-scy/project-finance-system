# 项目财务与合同管理分析系统 — 设计文档

> 版本：v1.0（MVP）· 日期：2026-09-12

## 1. 系统定位

面向中小公司的**本地 Web 应用**：按年度管理所有项目，自动计算财务指标、追踪回款、
管理质保金提醒，并生成年度可视化经营分析报告。

- 后端：Python 3.12 + FastAPI + SQLAlchemy + SQLite（零配置，数据全部本地）
- 前端：Vue 3 + Element Plus + ECharts（构建后由后端静态托管）
- AI：OpenAI 兼容接口（智谱 GLM / OpenAI / DeepSeek 等均可），Key 仅保存在后端

**核心原则**
1. AI 只负责"理解和提取"，程序负责"计算和校验"，用户负责"最终确认"。
2. AI 不允许猜测：识别不到的字段一律返回「未识别 / 需要人工确认」，绝不编造。
3. 原始录入数据与系统计算数据分离：计算值全部实时由程序推导，不落库。
4. 金额一律以**整数"分"**存储（BIGINT），避免浮点误差；对外展示为"元"。
5. 日期统一存 `YYYY-MM-DD` 标准格式。

---

## 2. 数据模型（SQLite）

```
Project          项目（1）─┬─（1）Contract          合同
                          ├─（N）PaymentSchedule   付款节点
                          ├─（N）PaymentRecord     回款记录
                          ├─（N）Invoice           发票
                          ├─（N）CostItem          成本明细（kind=direct/indirect）
                          ├─（N）UploadedFile      附件（合同/其他）
                          └─（N）ExtractionRecord  AI识别记录
Setting          系统设置（KV：AI配置、计算口径、提醒规则）
```

### 2.1 Project 项目
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | |
| name | TEXT | 项目名称（必填） |
| code | TEXT? | 项目编号 |
| customer_name | TEXT? | 客户名称 |
| owner | TEXT? | 项目负责人 |
| project_type | TEXT? | 项目类型 |
| status | TEXT | 未开始/进行中/已完成/已结算/已关闭 |
| start_date / end_date | DATE? | 项目开始/结束日期 |
| year | INTEGER | 归属年度（默认=合同签订年，用于年度看板归集） |
| notes | TEXT? | 备注 |

> 保存不要求字段齐全，缺省显示「待补充」。

### 2.2 Contract 合同（与项目 1:1）
| 字段 | 类型 | 说明 |
|---|---|---|
| contract_no | TEXT? | 合同编号 |
| total_amount_cents | BIGINT? | 含税合同总金额（分） |
| tax_rate_bp | INTEGER? | 税率（基点：1300 = 13.00%） |
| tax_amount_cents | BIGINT? | 税额（可由程序按含税额+税率倒算） |
| excl_tax_amount_cents | BIGINT? | 不含税金额（可由程序计算） |
| sign_date | DATE? | 合同签订日期 |
| payment_terms | TEXT? | 付款条款原文 |
| warranty_months | INTEGER? | 质保期（月） |
| warranty_start_date | DATE? | 质保期起算日 |
| warranty_ratio_bp | INTEGER? | 质保金比例（基点） |
| warranty_amount_cents | BIGINT? | 质保金金额 |
| warranty_expected_date | DATE? | 预计质保金到账日（程序可按起算日+月数推算） |
| warranty_actual_date | DATE? | 实际质保金到账日期 |

### 2.3 PaymentSchedule 付款节点
`name`（首付款/中期款/尾款/质保金/自定义）、`ratio_bp`（比例，可空）、
`amount_cents`（计划金额，可空）、`expected_date`（预计到账）、`actual_date`（实际到账，可手工填）、
`is_warranty`（是否质保金节点）、`sort_order`。
- 节点的"已收金额/状态（未到账·部分到账·已到账）"由关联回款记录实时汇总，不落库。

### 2.4 PaymentRecord 回款记录
`amount_cents`、`payment_date`、`type`（合同款/质保金/其他）、`schedule_id?`（对应付款节点）、
`invoice_id?`（对应发票）、`note`。

### 2.5 Invoice 发票
`invoice_no?`、`amount_cents`（开票金额）、`issue_date`（开票日期）、`type`（销项/进项，默认销项）、`note`。

### 2.6 CostItem 成本明细（直接+间接共用一张表，kind 区分）
| 字段 | 说明 |
|---|---|
| kind | `direct`（材料/人工/外包/设备/运输/其他直接）· `indirect`（管理费用/差旅/办公/项目管理/其他间接） |
| category | 上述分类之一 |
| amount_cents | 金额 |
| cost_date | 发生日期 |
| note | 备注 |

> 说明：直接成本与间接成本结构完全一致，故合并为一张表用 `kind` 区分，避免双表冗余、便于统一汇总（等价于设计要求中的 DirectCost / IndirectCost 两个实体）。

### 2.7 WarrantyPayment（质保金）
质保金 = Contract 的质保金字段组 + 标记 `is_warranty=true` 的付款节点 + 类型为「质保金」的回款记录，
三处数据由程序对账，不单独建表重复存储（避免数据不一致）。提醒状态由程序实时计算。

### 2.8 ExtractionRecord AI识别记录
| 字段 | 说明 |
|---|---|
| file_id? | 来源附件 |
| project_id? | 确认后归属的项目 |
| status | `pending` 待确认 / `confirmed` 已确认 / `discarded` 已放弃 |
| engine / model | `ai` 或 `manual`；模型名 |
| payload_json | 结构化识别结果：每个字段 `{value, confidence, source:{page, quote}, needs_review}` |
| raw_text_digest | 原文摘要（前500字，便于人工核对） |

### 2.9 Setting
KV 表：`ai_base_url`、`ai_api_key`、`ai_model`、`ai_vision_model`、`tax_mode`（excl_tax 默认 / incl_tax）、
`reminder_days`（默认 "30,7,0"）、`invoice_overdue_days`（默认 30）、`margin_alert_ratio`（默认 0）。

---

## 3. 财务计算（程序实时计算，全部整数分运算）

### 3.1 税额推导（tax_mode 决定收入口径）
- 已知含税额 + 税率：`不含税 = 含税 ÷ (1 + 税率)`，`税额 = 含税 - 不含税`（银行家外四舍五入到分）。
- 合同同时给出不含税与含税且互相矛盾 → 一致性告警。
- 项目收入 = 按 `tax_mode` 取不含税金额（默认）或含税金额。

### 3.2 项目级指标
```
直接成本合计 = Σ 直接成本明细
间接成本合计 = Σ 间接成本明细
项目总成本   = 直接 + 间接
项目利润     = 项目收入 - 项目总成本
项目利润率   = 项目利润 ÷ 项目收入（收入为0/空 → 不计算，显示「—」）
累计已到账   = Σ 回款记录
尚未到账     = 合同金额 - 累计已到账
回款比例     = 累计已到账 ÷ 合同金额
已开票金额   = Σ 发票金额；未开票 = 合同金额 - 已开票
最后一笔到账日期 = max(回款日期)
下一笔预计到账   = min(未收满节点的 expected_date)
```

### 3.3 成本回收
- 回收日期 = 最早的一天 D：`Σ(回款日期 ≤ D 的回款) ≥ 项目总成本（全部已录入成本）`。
- 回收周期 = 回收日期 − 项目开始日期（天）。
- 未达到 → 「尚未收回成本」；成本为 0/空 → 「无成本数据」。

### 3.4 质保金状态
| 状态 | 条件 |
|---|---|
| 🟢 已到账 | 已填实际到账日，或质保金相关回款 ≥ 质保金金额 |
| 🟡 即将到账 | 未到账且 预计到账日 − 今天 ≤ max(提醒天数)（默认30天） |
| 🔴 已到期未到账 | 今天 > 预计到账日 且未到账 |
| ⚪ 日期未知 | 无预计到账日 |
| （未到账） | 其余，正常展示 |
- 实际到账后自动停止一切提醒。

### 3.5 一致性检查（实时）
1. 付款节点计划金额之和 ≠ 合同金额（容差1分）→ 「付款节点金额与合同金额不一致，请检查」
2. 已到账 > 合同金额
3. 已开票 > 合同金额
4. 质保金金额 > 合同金额
5. 项目总成本 > 收入（亏损/超收预警）
6. 利润率为负

### 3.6 异常检测（Dashboard 待处理事项）
- 合同已结束仍大额未到账
- 已开票超过 N 天未回款
- 付款节点已过预计日期未收满
- 质保金已到期未到账 / 即将到账提醒（30/7/0天）
- 项目已开始但成本数据为空
- 成本超过合同收入 / 利润率异常

---

## 4. AI 合同识别流程

```
上传文件(PDF/Word/图片/扫描件/文本) 或 粘贴文本
   → 后端解析（PyMuPDF 按页抽文本 / python-docx / 视觉模型OCR）
   → LLM 结构化抽取（严格 Prompt：识别不到 → null，禁止编造；逐字段给置信度+原文位置+原文摘录）
   → Pydantic 校验、归一化（金额→分、日期→ISO、税率→基点），异常值丢弃并标 needs_review
   → 生成 ExtractionRecord(status=pending) → 前端「AI识别结果确认页」
   → 用户逐字段核对/修改/勾选（低置信度默认不勾选，标注「需要人工确认」）
   → 确认写入：创建新项目 或 应用到已有项目（程序计算税额/不含税额，拆分付款节点）
```

抽取字段：项目名称、客户、合同编号、含税/不含税金额、税率、签订日期、开始/结束日期、
付款方式、付款节点（名称/比例/金额/预计日期/是否质保金）、质保期、质保金比例与金额、
发票要求、其他重要条款。

**防猜机制**：Prompt 硬约束 + confidence < 0.6 自动标「需要人工确认」+ 日期无法从相对表述
确定时返回 null + 确认页必须由用户点击「确认写入」才落库。

AI 未配置时：手动录入完全可用；识别入口提示先到「设置」配置 API（可一键测试连通性）。

---

## 5. 页面结构

```
┌ 侧边栏 ─────────────────────────────┐
│ 📊 经营看板   /           │ 年度KPI + 图表 + 待处理事项
│ 📁 项目管理   /projects   │ 列表(搜索/筛选/排序) + 新建
│ 📄 项目详情   /projects/:id │ 基础信息|合同|回款|发票|成本|利润|付款计划|质保金|AI识别|附件
│ 🤖 识别确认   /extract/:id  │ 合同原文识别结果 → 系统字段 映射表 + 确认写入
│ ⚙ 系统设置   /settings    │ AI配置|计算口径|提醒规则|数据导入导出|示例数据
└────────────────────────────────────┘
```

**Dashboard**（默认当年）：项目总数、合同总额、不含税收入、已到账、待到账、总成本、
直接/间接成本、总利润、平均利润率、已开票/未开票、已回收成本项目数、待收质保金；
图表：月度签约与回款趋势、项目金额/利润/利润率排名、成本构成、回款构成、项目状态分布；
下方「待处理事项」列表。

**项目列表列**：项目 | 客户 | 合同金额 | 已到账 | 待到账 | 总成本 | 利润 | 利润率 |
发票状态 | 成本回收 | 质保金 | 状态；支持按 金额/利润/利润率/回款率 排序，按
关键词/年度/状态/质保金状态筛选。

**新建项目**：两种方式并排 —— ① 手动填写（可只填名称就保存，缺项显示待补充）；
② 拖入合同文件 → 自动进入 AI 识别。

---

## 6. API 设计（/api 前缀，JSON）

```
GET/POST        /api/projects                 列表(筛选排序) / 新建
GET/PUT/DELETE  /api/projects/{id}            详情(含全部计算结果) / 修改 / 删除
PUT             /api/projects/{id}/contract   更新合同
POST/PUT/DELETE /api/projects/{id}/schedules[/{sid}]   付款节点
POST/PUT/DELETE /api/projects/{id}/payments[/{pid}]    回款记录
POST/PUT/DELETE /api/projects/{id}/invoices[/{iid}]    发票
POST/PUT/DELETE /api/projects/{id}/costs[/{cid}]       成本(kind=direct|indirect)
POST/GET        /api/projects/{id}/files      上传附件 / 列表；GET .../files/{fid}/download；DELETE
GET             /api/projects/{id}/extractions 项目的AI识别记录

POST            /api/extractions/upload       上传文件→解析→AI识别→生成待确认记录
POST            /api/extractions/text         粘贴文本→同上
GET             /api/extractions?status=      待确认列表
GET             /api/extractions/{id}         识别详情
POST            /api/extractions/{id}/confirm 确认写入(新建项目或并入已有项目)
POST            /api/extractions/{id}/discard 放弃

GET             /api/dashboard?year=2026      KPI+图表数据+待处理事项+可用年份
GET/PUT         /api/settings                 读取(脱敏)/保存
POST            /api/settings/test-ai         AI连通性测试
POST            /api/system/demo-data         载入示例数据   POST /api/system/reset 清空
GET             /api/export/projects.xlsx|.csv /api/export/payments.xlsx  导出
POST            /api/import/projects          Excel导入(可下载模板 GET /api/export/template.xlsx)
GET             /api/report/annual?year=2026  年度经营分析报告 PDF
GET             /api/health                   健康检查
```

金额入参/出参统一为「元」（2位小数），入库/计算时转为整数分。

---

## 7. 目录结构

```
project-finance-system/
├── backend/
│   ├── app/
│   │   ├── main.py            FastAPI 入口 + 静态托管前端
│   │   ├── database.py        SQLite 引擎/会话
│   │   ├── models.py          ORM 模型
│   │   ├── schemas.py         Pydantic 出入参
│   │   ├── routers/           projects / extractions / dashboard / settings / transfer(导入导出)
│   │   └── services/          calc(财务计算) / alerts(异常) / ai_client / extraction /
│   │                          fileparse / excelio / report / demo
│   ├── data/                  app.db + uploads/（全部本地）
│   └── requirements.txt
├── frontend/                  Vue3 + Vite 源码（构建产物 dist/ 由后端托管）
├── scripts/                   smoke_test.py 冒烟测试
├── docs/DESIGN.md             本文档
├── start.bat                  一键启动（自动建环境→起服务→开浏览器）
└── README.md
```
