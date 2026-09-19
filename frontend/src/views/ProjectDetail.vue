<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, money, todayIso } from '../api'
import { loadCompanies, store } from '../store'

const route = useRoute()
const router = useRouter()
const pid = route.params.id
const loading = ref(false)
const d = ref(null)
const tab = ref('base')
const meta = ref({ statuses: [], direct_categories: [], indirect_categories: [], tax_categories: [], tax_rate_options: [1, 1.5, 3, 5, 6, 9, 13, 20], schedule_names: [], payment_types: [], invoice_types: [], project_types: [] })

async function load() {
  loading.value = true
  try {
    d.value = await api.get(`/projects/${pid}`)
  } catch (e) {
    ElMessage.error(String(e.message || e))
  } finally {
    loading.value = false
  }
}
onMounted(async () => {
  load()
  loadCompanies()
  try { meta.value = await api.get('/projects/meta') } catch { /* ignore */ }
})

const c = computed(() => d.value?.computed || {})
const contract = computed(() => d.value?.contract || {})

// ── 基础信息编辑 ─────────────────────────────────────────────
const editBase = ref(false)
const baseForm = reactive({})
function openEditBase() {
  Object.assign(baseForm, {
    company_id: d.value.company_id, name: d.value.name, code: d.value.code, customer_name: d.value.customer_name,
    owner: d.value.owner, project_type: d.value.project_type, status: d.value.status,
    start_date: d.value.start_date, end_date: d.value.end_date, year: d.value.year, notes: d.value.notes,
  })
  editBase.value = true
}
async function saveBase() {
  try {
    await api.put(`/projects/${pid}`, baseForm)
    editBase.value = false
    ElMessage.success('已保存')
    load()
  } catch (e) { ElMessage.error(String(e.message || e)) }
}

// ── 合同编辑 ────────────────────────────────────────────────
const editContract = ref(false)
const cForm = reactive({})
function openEditContract() {
  Object.assign(cForm, {
    contract_no: contract.value.contract_no, total_amount: contract.value.total_amount,
    tax_rate: contract.value.tax_rate, excl_tax_amount: contract.value.excl_tax_amount,
    tax_amount: contract.value.tax_amount, sign_date: contract.value.sign_date,
    contract_end_date: contract.value.contract_end_date,
    payment_terms: contract.value.payment_terms,
    warranty_months: contract.value.warranty_months, warranty_start_date: contract.value.warranty_start_date,
    warranty_ratio: contract.value.warranty_ratio, warranty_amount: contract.value.warranty_amount,
    warranty_expected_date: contract.value.warranty_expected_date,
    warranty_actual_date: contract.value.warranty_actual_date,
  })
  editContract.value = true
}
async function saveContract() {
  try {
    await api.put(`/projects/${pid}/contract`, cForm)
    editContract.value = false
    ElMessage.success('合同信息已保存')
    load()
  } catch (e) { ElMessage.error(String(e.message || e)) }
}

// ── 付款节点 ────────────────────────────────────────────────
const schedDlg = ref(false)
const schedForm = reactive({ id: null, name: '', ratio: null, amount: null, expected_date: null, is_warranty: false })
function openSched(row) {
  Object.assign(schedForm, row || { id: null, name: '', ratio: null, amount: null, expected_date: null, is_warranty: false })
  schedDlg.value = true
}
function fillSchedAmount() {
  if (schedForm.ratio != null && contract.value.total_amount != null && schedForm.id == null) {
    schedForm.amount = Math.round(contract.value.total_amount * schedForm.ratio) / 100
  }
}
async function saveSched() {
  try {
    if (schedForm.id) await api.put(`/projects/${pid}/schedules/${schedForm.id}`, schedForm)
    else await api.post(`/projects/${pid}/schedules`, schedForm)
    schedDlg.value = false
    ElMessage.success('已保存')
    load()
  } catch (e) { ElMessage.error(String(e.message || e)) }
}
async function delSched(row) {
  await ElMessageBox.confirm(`删除付款节点「${row.name}」？`, '确认', { type: 'warning' })
  await api.del(`/projects/${pid}/schedules/${row.id}`)
  ElMessage.success('已删除'); load()
}

// ── 回款记录 ────────────────────────────────────────────────
const payDlg = ref(false)
const payForm = reactive({ id: null, amount: null, payment_date: todayIso(), type: '合同款', schedule_id: null, invoice_id: null, note: '' })
function openPay(row, presetScheduleId) {
  Object.assign(payForm, {
    id: null, amount: null, payment_date: todayIso(), type: '合同款',
    schedule_id: presetScheduleId ?? null, invoice_id: null, note: '',
  })
  if (row) Object.assign(payForm, {
    id: row.id, amount: row.amount, payment_date: row.payment_date, type: row.type,
    schedule_id: row.schedule_id, invoice_id: row.invoice_id, note: row.note || '',
  })
  payDlg.value = true
}
async function savePay() {
  try {
    if (payForm.id) await api.put(`/projects/${pid}/payments/${payForm.id}`, payForm)
    else await api.post(`/projects/${pid}/payments`, payForm)
    payDlg.value = false
    ElMessage.success('回款已记录，相关指标已自动更新')
    load()
  } catch (e) { ElMessage.error(String(e.message || e)) }
}
async function delPay(row) {
  await ElMessageBox.confirm(`删除这笔 ${money(row.amount)} 元的回款记录？`, '确认', { type: 'warning' })
  await api.del(`/projects/${pid}/payments/${row.id}`)
  ElMessage.success('已删除'); load()
}

// ── 发票 ────────────────────────────────────────────────────
const invDlg = ref(false)
const invForm = reactive({ id: null, invoice_no: '', amount: null, issue_date: todayIso(), type: '销项发票', note: '' })
function openInv(row) {
  Object.assign(invForm, row
    ? { ...row, note: row.note || '' }
    : { id: null, invoice_no: '', amount: null, issue_date: todayIso(), type: '销项发票', note: '' })
  invDlg.value = true
}
async function saveInv() {
  try {
    if (invForm.id) await api.put(`/projects/${pid}/invoices/${invForm.id}`, invForm)
    else await api.post(`/projects/${pid}/invoices`, invForm)
    invDlg.value = false
    ElMessage.success('已保存'); load()
  } catch (e) { ElMessage.error(String(e.message || e)) }
}
async function delInv(row) {
  await ElMessageBox.confirm('删除这条发票记录？', '确认', { type: 'warning' })
  await api.del(`/projects/${pid}/invoices/${row.id}`)
  ElMessage.success('已删除'); load()
}

// ── 成本 ────────────────────────────────────────────────────
const costDlg = ref(false)
const costForm = reactive({ id: null, kind: 'direct', category: '材料', amount: null, cost_date: todayIso(), note: '' })
const taxRatePct = ref(null)
const KIND_NAME = { direct: '直接成本', indirect: '间接成本', tax: '税收成本' }
function openCost(row) {
  Object.assign(costForm, row
    ? { ...row, note: row.note || '' }
    : { id: null, kind: 'direct', category: '材料', amount: null, cost_date: todayIso(), note: '' })
  taxRatePct.value = null
  costDlg.value = true
}
function costCategories() {
  if (costForm.kind === 'tax') return meta.value.tax_categories || []
  return costForm.kind === 'direct' ? meta.value.direct_categories : meta.value.indirect_categories
}
function onKindChange() {
  const cats = costCategories()
  if (!cats.includes(costForm.category)) costForm.category = cats[0]
  taxRatePct.value = null
}
function calcTax() {
  if (costForm.kind !== 'tax' || taxRatePct.value == null) return
  const base = c.value.contract_amount
  if (base == null) {
    ElMessage.warning('请先在「合同」中填写合同金额，再按税率自动计算。')
    return
  }
  costForm.amount = Math.round(base * Number(taxRatePct.value)) / 100
}
const taxCalcHint = computed(() => {
  if (costForm.kind !== 'tax') return ''
  const base = c.value.contract_amount
  if (base == null) return '请先在「合同」中填写合同金额'
  if (taxRatePct.value == null) return `合同金额 ${money(base)} 元 × 税率，选择税率后自动填入`
  return `${money(base)} × ${taxRatePct.value}% = ${money(base * Number(taxRatePct.value) / 100)} 元`
})
async function saveCost() {
  try {
    if (costForm.id) await api.put(`/projects/${pid}/costs/${costForm.id}`, costForm)
    else await api.post(`/projects/${pid}/costs`, costForm)
    costDlg.value = false
    ElMessage.success('已保存'); load()
  } catch (e) { ElMessage.error(String(e.message || e)) }
}
async function delCost(row) {
  await ElMessageBox.confirm('删除这条成本记录？', '确认', { type: 'warning' })
  await api.del(`/projects/${pid}/costs/${row.id}`)
  ElMessage.success('已删除'); load()
}

// ── 附件 ────────────────────────────────────────────────────
const fileInput = ref(null)
async function uploadFile(ev) {
  const file = ev.target.files && ev.target.files[0]
  if (!file) return
  const fd = new FormData()
  fd.append('file', file)
  try {
    await api.upload(`/projects/${pid}/files`, fd)
    ElMessage.success('附件已上传'); load()
  } catch (e) { ElMessage.error(String(e.message || e)) }
  ev.target.value = ''
}
async function delFile(f) {
  await ElMessageBox.confirm(`删除附件「${f.orig_name}」？`, '确认', { type: 'warning' })
  await api.del(`/projects/${pid}/files/${f.id}`)
  load()
}
function downloadFile(f) {
  window.open(`/api/projects/${pid}/files/${f.id}/download`, '_blank')
}

async function delProject() {
  await ElMessageBox.confirm(`确认删除项目「${d.value.name}」？其回款、成本、发票、合同数据将一并删除。`, '危险操作', { type: 'error', confirmButtonText: '删除' })
  await api.del(`/projects/${pid}`)
  ElMessage.success('项目已删除')
  router.push('/projects')
}

const SCHED_STATUS_TAG = { '已到账': 'success', '部分到账': 'warning', '未到账': 'info' }
const WARRANTY_STYLE = {
  '已到账': { color: '#2eab5c', text: '🟢 已到账' },
  '即将到账': { color: '#e6a23c', text: '🟡 即将到账' },
  '已到期未到账': { color: '#e2564a', text: '🔴 已到期未到账' },
  '日期未知': { color: '#b8c2cc', text: '⚪ 日期未知' },
  '未到账': { color: '#4a90d9', text: '未到账' },
}
const STATUS_TAG = { '未开始': 'info', '进行中': 'primary', '已完成': 'success', '已结算': 'warning', '已关闭': 'info' }
const scheduleSumDiff = computed(() => {
  if (c.value.contract_amount == null || c.value.schedule_plan_sum == null) return null
  return Math.round((c.value.schedule_plan_sum - c.value.contract_amount) * 100) / 100
})
function fmtD(iso) { return iso || '待补充' }
</script>

<template>
  <div v-loading="loading">
    <template v-if="d">
      <!-- 头部 -->
      <div class="panel" style="margin-bottom:14px;">
        <div style="display:flex; align-items:flex-start; gap:14px;">
          <div style="flex:1;">
            <div style="display:flex; align-items:center; gap:10px;">
              <h2 style="margin:0; font-size:19px;">{{ d.name }}</h2>
              <el-tag :type="STATUS_TAG[d.status] || 'info'" size="small">{{ d.status }}</el-tag>
              <span class="muted" style="font-size:12.5px;">{{ d.code || '编号待补充' }} · 归属 {{ d.year }} 年</span>
            </div>
            <div class="muted" style="margin-top:5px; font-size:12.5px;">
              客户：{{ d.customer_name || '待补充' }}　负责人：{{ d.owner || '待补充' }}
              　周期：{{ fmtD(d.start_date) }} ~ {{ fmtD(d.end_date) }}
              <template v-if="d.company_name">　公司：{{ d.company_name }}</template>
            </div>          </div>
          <div>
            <el-button size="small" :icon="'Edit'" @click="openEditBase">编辑</el-button>
            <el-button size="small" type="danger" plain :icon="'Delete'" @click="delProject">删除</el-button>
          </div>
        </div>
        <el-divider style="margin:14px 0 10px;" />
        <div style="display:flex; gap:34px; flex-wrap:wrap; font-variant-numeric:tabular-nums;">
          <div><div class="muted" style="font-size:12px;">合同金额</div><b style="font-size:17px;">{{ money(c.contract_amount) }}</b></div>
          <div><div class="muted" style="font-size:12px;">已到账</div><b class="success-text" style="font-size:17px;">{{ money(c.received) }}</b>
            <span v-if="c.received_ratio != null" class="muted" style="font-size:12px;">（{{ c.received_ratio }}%）</span></div>
          <div><div class="muted" style="font-size:12px;">待到账</div>
            <b :class="c.over_received ? 'danger-text' : ''" style="font-size:17px;">{{ c.over_received ? '超收' : money(c.pending) }}</b></div>
          <div><div class="muted" style="font-size:12px;">总成本</div><b style="font-size:17px;">{{ money(c.total_cost) }}</b></div>
          <div><div class="muted" style="font-size:12px;">利润</div>
            <b :class="c.profit == null ? '' : (c.profit < 0 ? 'danger-text' : 'success-text')" style="font-size:17px;">{{ money(c.profit) }}</b></div>
          <div><div class="muted" style="font-size:12px;">利润率</div>
            <b :class="c.margin != null && c.margin < 0 ? 'danger-text' : ''" style="font-size:17px;">{{ c.margin == null ? '—' : c.margin + '%' }}</b></div>
          <div><div class="muted" style="font-size:12px;">成本回收</div><b style="font-size:14px;" :class="c.recovery.recovered ? 'success-text' : 'muted'">{{ c.recovery.status }}</b></div>
          <div v-if="c.warranty.amount != null"><div class="muted" style="font-size:12px;">质保金</div>
            <b style="font-size:14px;">{{ money(c.warranty.amount) }}</b>
            <span class="dot" :style="{ background: WARRANTY_STYLE[c.warranty.status]?.color }" />
            <span style="font-size:12px;">{{ WARRANTY_STYLE[c.warranty.status]?.text }}</span></div>
        </div>
        <el-alert v-for="(iss, i) in c.issues" :key="i" :type="iss.level === 'danger' ? 'error' : 'warning'"
          :title="iss.message" :closable="false" style="margin-top:10px;" />
      </div>

      <el-tabs v-model="tab" type="border-card" style="background:#fff;">
        <!-- 基础信息 -->
        <el-tab-pane label="基础信息" name="base">
          <el-descriptions :column="3" border>
            <el-descriptions-item label="所属公司">{{ d.company_name || '未分配' }}</el-descriptions-item>
            <el-descriptions-item label="项目名称">{{ d.name }}</el-descriptions-item>
            <el-descriptions-item label="项目编号">{{ d.code || '待补充' }}</el-descriptions-item>
            <el-descriptions-item label="客户名称">{{ d.customer_name || '待补充' }}</el-descriptions-item>
            <el-descriptions-item label="项目负责人">{{ d.owner || '待补充' }}</el-descriptions-item>
            <el-descriptions-item label="项目类型">{{ d.project_type || '待补充' }}</el-descriptions-item>
            <el-descriptions-item label="项目状态">{{ d.status }}</el-descriptions-item>
            <el-descriptions-item label="项目开始日期">{{ fmtD(d.start_date) }}</el-descriptions-item>
            <el-descriptions-item label="项目结束日期">{{ fmtD(d.end_date) }}</el-descriptions-item>
            <el-descriptions-item label="归属年度">{{ d.year || '待补充' }}</el-descriptions-item>
            <el-descriptions-item label="备注" :span="3">{{ d.notes || '—' }}</el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>

        <!-- 合同 -->
        <el-tab-pane :label="`合同`" name="contract">
          <div style="display:flex; justify-content:flex-end; margin-bottom:10px;">
            <el-button type="primary" size="small" :icon="'Edit'" @click="openEditContract">
              {{ d.contract ? '编辑合同' : '录入合同信息' }}
            </el-button>
          </div>
          <el-descriptions :column="3" border>
            <el-descriptions-item label="合同编号">{{ contract.contract_no || '待补充' }}</el-descriptions-item>
            <el-descriptions-item label="合同总金额（含税）">{{ money(contract.total_amount) }}</el-descriptions-item>
            <el-descriptions-item label="税率">{{ contract.tax_rate != null ? contract.tax_rate + '%' : '待补充' }}</el-descriptions-item>
            <el-descriptions-item label="不含税金额">
              {{ money(c.excl_tax_amount) }}
              <span v-if="contract.excl_tax_amount == null && contract.total_amount && contract.tax_rate != null" class="muted" style="font-size:11px;">（系统按税率推算）</span>
            </el-descriptions-item>
            <el-descriptions-item label="税额">
              {{ money(c.tax_amount) }}
              <span v-if="contract.tax_amount == null && contract.total_amount && contract.tax_rate != null" class="muted" style="font-size:11px;">（系统按税率推算）</span>
            </el-descriptions-item>
            <el-descriptions-item label="签订日期">{{ fmtD(contract.sign_date) }}</el-descriptions-item>
            <el-descriptions-item label="合同到期日">
              {{ fmtD(contract.contract_end_date || d.end_date) }}
              <span v-if="!contract.contract_end_date && d.end_date" class="muted" style="font-size:11px;">（取项目结束日期）</span>
            </el-descriptions-item>
            <el-descriptions-item label="付款条款" :span="3">{{ contract.payment_terms || '待补充' }}</el-descriptions-item>
            <el-descriptions-item label="质保期">{{ contract.warranty_months != null ? contract.warranty_months + ' 个月' : '待补充' }}</el-descriptions-item>
            <el-descriptions-item label="质保金比例">{{ contract.warranty_ratio != null ? contract.warranty_ratio + '%' : '待补充' }}</el-descriptions-item>
            <el-descriptions-item label="质保金金额">{{ money(c.warranty.amount) }}</el-descriptions-item>
            <el-descriptions-item label="质保期起算">{{ fmtD(contract.warranty_start_date) }}</el-descriptions-item>
            <el-descriptions-item label="预计质保金到账">{{ fmtD(c.warranty.expected_date) }}
              <span v-if="contract.warranty_expected_date == null && c.warranty.expected_date" class="muted" style="font-size:11px;">（系统推算）</span>
            </el-descriptions-item>
            <el-descriptions-item label="实际质保金到账">{{ fmtD(c.warranty.actual_date) }}</el-descriptions-item>
          </el-descriptions>

          <div class="panel-title" style="margin-top:18px;">合同 / 项目文件</div>
          <div style="display:flex; gap:10px; align-items:center; margin-bottom:10px;">
            <el-button size="small" :icon="'Upload'" @click="fileInput.click()">上传文件</el-button>
            <input ref="fileInput" type="file" style="display:none" @change="uploadFile" />
            <span class="muted" style="font-size:12px;">原始合同、扫描件等（本地保存）</span>
          </div>
          <el-table :data="d.files" size="small" empty-text="暂无附件">
            <el-table-column prop="orig_name" label="文件名" min-width="240" />
            <el-table-column label="大小" width="100">
              <template #default="{ row }">{{ (row.size / 1024).toFixed(0) }} KB</template>
            </el-table-column>
            <el-table-column prop="kind" label="类型" width="90">
              <template #default="{ row }">{{ row.kind === 'contract' ? '合同' : '附件' }}</template>
            </el-table-column>
            <el-table-column label="操作" width="140">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="downloadFile(row)">下载</el-button>
                <el-button link type="danger" size="small" @click="delFile(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 付款计划 -->
        <el-tab-pane :label="`付款计划(${d.schedules.length})`" name="schedules">
          <el-alert v-if="scheduleSumDiff != null && Math.abs(scheduleSumDiff) > 0.01" type="warning" :closable="false" style="margin-bottom:10px;"
            :title="`付款节点金额合计与合同金额不一致，相差 ${money(Math.abs(scheduleSumDiff))} 元，请检查。`" />
          <el-alert v-else-if="d.schedules.length && scheduleSumDiff != null" type="success" :closable="false" style="margin-bottom:10px;"
            title="付款节点金额合计与合同金额一致 ✓" />
          <div style="display:flex; justify-content:flex-end; margin-bottom:10px;">
            <el-button type="primary" size="small" :icon="'Plus'" @click="openSched(null)">添加节点</el-button>
          </div>
          <el-table :data="c.schedules" size="small" empty-text="暂无付款节点">
            <el-table-column prop="name" label="节点" width="110" />
            <el-table-column label="比例" width="80" align="right">
              <template #default="{ row }">{{ row.ratio_pct != null ? row.ratio_pct + '%' : '—' }}</template>
            </el-table-column>
            <el-table-column label="计划金额" width="120" align="right">
              <template #default="{ row }"><span class="num">{{ money(row.amount) }}</span></template>
            </el-table-column>
            <el-table-column label="预计到账" width="110">
              <template #default="{ row }"><span :class="row.overdue ? 'danger-text' : ''">{{ fmtD(row.expected_date) }}</span></template>
            </el-table-column>
            <el-table-column label="已到账" width="120" align="right">
              <template #default="{ row }"><span class="num">{{ money(row.received) }}</span></template>
            </el-table-column>
            <el-table-column label="状态" width="90" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="SCHED_STATUS_TAG[row.status]" effect="light">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="实际到账日期" width="120">
              <template #default="{ row }">{{ fmtD(row.actual_date) }}</template>
            </el-table-column>
            <el-table-column label="操作" min-width="150">
              <template #default="{ row }">
                <el-button link type="success" size="small" @click="openPay(null, row.id)">记一笔到账</el-button>
                <el-button link type="primary" size="small" @click="openSched({ id: row.id, name: row.name, ratio: row.ratio_pct, amount: row.amount, expected_date: row.expected_date, is_warranty: row.is_warranty })">编辑</el-button>
                <el-button link type="danger" size="small" @click="delSched(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 回款 -->
        <el-tab-pane :label="`回款(${d.payments.length})`" name="payments">
          <div style="display:flex; gap:16px; margin-bottom:12px; flex-wrap:wrap;">
            <el-tag effect="plain">累计已到账 <b class="success-text">{{ money(c.received) }}</b></el-tag>
            <el-tag effect="plain">尚未到账 <b class="danger-text">{{ money(c.pending) }}</b></el-tag>
            <el-tag effect="plain">回款比例 <b>{{ c.received_ratio == null ? '—' : c.received_ratio + '%' }}</b></el-tag>
            <el-tag effect="plain">最后一笔到账 <b>{{ fmtD(c.last_payment_date) }}</b></el-tag>
            <el-tag effect="plain">下一笔预计到账 <b>{{ fmtD(c.next_expected_date) }}</b></el-tag>
          </div>
          <div style="display:flex; justify-content:flex-end; margin-bottom:10px;">
            <el-button type="primary" size="small" :icon="'Plus'" @click="openPay(null, null)">新增回款</el-button>
          </div>
          <el-table :data="d.payments" size="small" empty-text="暂无回款记录">
            <el-table-column prop="payment_date" label="回款日期" width="110" />
            <el-table-column label="回款金额" width="130" align="right">
              <template #default="{ row }"><span class="num success-text">{{ money(row.amount) }}</span></template>
            </el-table-column>
            <el-table-column prop="type" label="类型" width="90" />
            <el-table-column label="对应付款节点" min-width="120">
              <template #default="{ row }">
                {{ (c.schedules.find(s => s.id === row.schedule_id) || {}).name || '—' }}
              </template>
            </el-table-column>
            <el-table-column label="对应发票" width="120">
              <template #default="{ row }">
                {{ (d.invoices.find(i => i.id === row.invoice_id) || {}).invoice_no || '—' }}
              </template>
            </el-table-column>
            <el-table-column prop="note" label="备注" min-width="140" />
            <el-table-column label="操作" width="120">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="openPay(row)">编辑</el-button>
                <el-button link type="danger" size="small" @click="delPay(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 发票 -->
        <el-tab-pane :label="`发票(${d.invoices.length})`" name="invoices">
          <div style="display:flex; gap:16px; margin-bottom:12px;">
            <el-tag effect="plain">已开票 <b>{{ money(c.invoiced) }}</b></el-tag>
            <el-tag effect="plain">未开票 <b>{{ money(c.not_invoiced) }}</b></el-tag>
            <el-tag effect="plain">{{ c.invoice_status }}</el-tag>
          </div>
          <div style="display:flex; justify-content:flex-end; margin-bottom:10px;">
            <el-button type="primary" size="small" :icon="'Plus'" @click="openInv(null)">登记发票</el-button>
          </div>
          <el-table :data="d.invoices" size="small" empty-text="暂无发票记录">
            <el-table-column prop="issue_date" label="开票日期" width="110" />
            <el-table-column prop="invoice_no" label="发票号码" min-width="150" />
            <el-table-column label="开票金额" width="130" align="right">
              <template #default="{ row }"><span class="num">{{ money(row.amount) }}</span></template>
            </el-table-column>
            <el-table-column prop="type" label="类型" width="100" />
            <el-table-column prop="note" label="备注" min-width="140" />
            <el-table-column label="操作" width="120">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="openInv(row)">编辑</el-button>
                <el-button link type="danger" size="small" @click="delInv(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 成本 -->
        <el-tab-pane :label="`成本(${d.costs.length})`" name="costs">
          <div style="display:flex; gap:16px; margin-bottom:12px; flex-wrap:wrap;">
            <el-tag effect="plain">直接成本 <b>{{ money(c.direct_cost) }}</b></el-tag>
            <el-tag effect="plain">间接成本 <b>{{ money(c.indirect_cost) }}</b></el-tag>
            <el-tag effect="plain" type="danger">税收成本 <b>{{ money(c.tax_cost) }}</b></el-tag>
            <el-tag effect="plain">总成本 <b>{{ money(c.total_cost) }}</b></el-tag>
          </div>
          <div style="display:flex; justify-content:flex-end; margin-bottom:10px;">
            <el-button type="primary" size="small" :icon="'Plus'" @click="openCost(null)">新增成本</el-button>
          </div>
          <el-table :data="d.costs" size="small" empty-text="暂无成本记录">
            <el-table-column prop="cost_date" label="发生日期" width="110" />
            <el-table-column label="类别" width="110">
              <template #default="{ row }">
                <el-tag size="small" :type="row.kind === 'direct' ? 'primary' : (row.kind === 'tax' ? 'danger' : 'warning')" effect="plain">
                  {{ row.kind === 'direct' ? '直接' : (row.kind === 'tax' ? '税金' : '间接') }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="category" label="分类" width="120" />
            <el-table-column label="金额" width="130" align="right">
              <template #default="{ row }"><span class="num">{{ money(row.amount) }}</span></template>
            </el-table-column>
            <el-table-column prop="note" label="备注" min-width="160" />
            <el-table-column label="操作" width="120">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="openCost(row)">编辑</el-button>
                <el-button link type="danger" size="small" @click="delCost(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 利润 -->
        <el-tab-pane label="利润分析" name="profit">
          <el-row :gutter="14">
            <el-col :span="6">
              <div class="kpi-card accent">
                <div class="label">项目收入（{{ c.tax_mode === 'incl_tax' ? '含税口径' : '不含税口径' }}）</div>
                <div class="value num">{{ money(c.revenue) }}</div>
                <div class="extra">可在「系统设置」切换含税/不含税口径</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="kpi-card">
                <div class="label">项目总成本</div>
                <div class="value num">{{ money(c.total_cost) }}</div>
                <div class="extra">直接 {{ money(c.direct_cost) }} + 间接 {{ money(c.indirect_cost) }} + 税金 {{ money(c.tax_cost) }}</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="kpi-card" :class="(c.profit || 0) < 0 ? 'danger' : 'success'">
                <div class="label">项目利润</div>
                <div class="value num">{{ money(c.profit) }}</div>
                <div class="extra">收入 − 总成本</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="kpi-card" :class="(c.margin || 0) < 0 ? 'danger' : 'success'">
                <div class="label">项目利润率</div>
                <div class="value num">{{ c.margin == null ? '—' : c.margin + '%' }}</div>
                <div class="extra">利润 ÷ 收入 × 100%</div>
              </div>
            </el-col>
          </el-row>

          <div style="display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-top:16px;">
            <div>
              <div class="panel-title">成本分类明细</div>
              <el-table :data="[...Object.entries(c.direct_by_category || {}).map(([k, v]) => ({ name: k, v, kind: '直接' })),
                               ...Object.entries(c.indirect_by_category || {}).map(([k, v]) => ({ name: k, v, kind: '间接' })),
                               ...Object.entries(c.tax_by_category || {}).map(([k, v]) => ({ name: k, v, kind: '税金' }))]"
                size="small" empty-text="暂无成本">
                <el-table-column prop="kind" label="类别" width="80" />
                <el-table-column prop="name" label="分类" />
                <el-table-column label="金额" align="right">
                  <template #default="{ row }"><span class="num">{{ money(row.v) }}</span></template>
                </el-table-column>
              </el-table>
            </div>
            <div>
              <div class="panel-title">成本回收分析</div>
              <el-descriptions :column="1" border>
                <el-descriptions-item label="当前状态">
                  <b :class="c.recovery.recovered ? 'success-text' : 'danger-text'">{{ c.recovery.status }}</b>
                </el-descriptions-item>
                <el-descriptions-item label="项目开始日期">{{ fmtD(d.start_date) }}</el-descriptions-item>
                <el-descriptions-item label="第一笔回款日期">{{ fmtD(c.recovery.first_payment_date) }}</el-descriptions-item>
                <el-descriptions-item label="成本回收日期">{{ fmtD(c.recovery.recovery_date) }}</el-descriptions-item>
                <el-descriptions-item label="成本回收周期">
                  {{ c.recovery.days != null ? c.recovery.days + ' 天' : '—' }}
                </el-descriptions-item>
                <el-descriptions-item label="判定规则">累计实际到账 ≥ 累计实际成本 即视为收回</el-descriptions-item>
              </el-descriptions>
            </div>
          </div>
        </el-tab-pane>

        <!-- 质保金 -->
        <el-tab-pane label="质保金" name="warranty">
          <el-row :gutter="14">
            <el-col :span="8">
              <div class="kpi-card" :class="{ danger: c.warranty.status === '已到期未到账', warn: c.warranty.status === '即将到账', success: c.warranty.status === '已到账' }">
                <div class="label">质保金状态</div>
                <div class="value" style="font-size:18px;">{{ WARRANTY_STYLE[c.warranty.status]?.text || '⚪ 日期未知' }}</div>
                <div class="extra">实际到账后自动停止提醒</div>
              </div>
            </el-col>
            <el-col :span="16">
              <el-descriptions :column="3" border>
                <el-descriptions-item label="质保金金额">{{ money(c.warranty.amount) }}</el-descriptions-item>
                <el-descriptions-item label="质保金比例">{{ c.warranty.ratio_pct != null ? c.warranty.ratio_pct + '%' : (contract.warranty_ratio != null ? contract.warranty_ratio + '%' : '待补充') }}</el-descriptions-item>
                <el-descriptions-item label="质保期">{{ contract.warranty_months != null ? contract.warranty_months + ' 个月' : '待补充' }}</el-descriptions-item>
                <el-descriptions-item label="质保期起算日">{{ fmtD(c.warranty.start_date) }}</el-descriptions-item>
                <el-descriptions-item label="预计到账日期">{{ fmtD(c.warranty.expected_date) }}</el-descriptions-item>
                <el-descriptions-item label="实际到账日期">{{ fmtD(c.warranty.actual_date) }}</el-descriptions-item>
                <el-descriptions-item label="质保金已到账">{{ money(c.warranty.received) }}</el-descriptions-item>
                <el-descriptions-item label="距预计到账">
                  {{ c.warranty.days_to_due == null ? '—' : (c.warranty.days_to_due >= 0 ? '还有 ' + c.warranty.days_to_due + ' 天' : '已逾期 ' + (-c.warranty.days_to_due) + ' 天') }}
                </el-descriptions-item>
                <el-descriptions-item label="提醒规则">默认 30 天 / 7 天 / 到期当天</el-descriptions-item>
              </el-descriptions>
            </el-col>
          </el-row>
          <el-alert type="info" :closable="false" style="margin-top:14px;"
            title="如何登记质保金到账？"
            description="在「回款」页新增一笔类型为「质保金」的回款（或关联质保金付款节点），系统会自动把质保金状态更新为已到账。" />
        </el-tab-pane>

        <!-- AI 识别记录 -->
        <el-tab-pane :label="`AI识别(${d.extractions.length})`" name="ai">
          <el-alert type="info" :closable="false" style="margin-bottom:10px;"
            title="这里记录了本项目的 AI 合同识别历史：哪些数据来自 AI、是否已经人工确认。" />
          <div style="margin-bottom:10px;">
            <el-button type="primary" size="small" :icon="'MagicStick'" @click="router.push('/projects/new')">再识别一份新合同</el-button>
          </div>
          <el-table :data="d.extractions" size="small" empty-text="暂无 AI 识别记录">
            <el-table-column prop="id" label="记录ID" width="80" />
            <el-table-column prop="created_at" label="识别时间" width="170" />
            <el-table-column prop="model" label="模型" width="150" />
            <el-table-column prop="engine" label="来源" width="90" />
            <el-table-column label="状态" width="110">
              <template #default="{ row }">
                <el-tag size="small" :type="row.status === 'confirmed' ? 'success' : (row.status === 'pending' ? 'warning' : 'info')">
                  {{ { confirmed: '已确认写入', pending: '待人工确认', discarded: '已放弃' }[row.status] || row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120">
              <template #default="{ row }">
                <el-button v-if="row.status === 'pending'" link type="primary" size="small"
                  @click="router.push('/extract/' + row.id)">去确认</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>

      <!-- 基础信息编辑对话框 -->
      <el-dialog v-model="editBase" title="编辑基础信息" width="640px">
        <el-form label-width="100px">
          <el-form-item label="所属公司">
            <el-select v-model="baseForm.company_id" clearable style="width:100%" placeholder="选择公司">
              <el-option v-for="c in store.companies" :key="c.id" :value="c.id" :label="c.name" />
            </el-select>
          </el-form-item>
          <el-form-item label="项目名称" required><el-input v-model="baseForm.name" /></el-form-item>
          <div style="display:grid; grid-template-columns:1fr 1fr; gap:0 14px;">
            <el-form-item label="项目编号"><el-input v-model="baseForm.code" /></el-form-item>
            <el-form-item label="客户名称"><el-input v-model="baseForm.customer_name" /></el-form-item>
            <el-form-item label="负责人"><el-input v-model="baseForm.owner" /></el-form-item>
            <el-form-item label="项目类型">
              <el-select v-model="baseForm.project_type" filterable allow-create style="width:100%">
                <el-option v-for="t in meta.project_types" :key="t" :label="t" :value="t" />
              </el-select>
            </el-form-item>
            <el-form-item label="状态">
              <el-select v-model="baseForm.status" style="width:100%">
                <el-option v-for="s in meta.statuses" :key="s" :label="s" :value="s" />
              </el-select>
            </el-form-item>
            <el-form-item label="归属年度"><el-input-number v-model="baseForm.year" :controls="false" style="width:100%" /></el-form-item>
            <el-form-item label="开始日期"><el-date-picker v-model="baseForm.start_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item>
            <el-form-item label="结束日期"><el-date-picker v-model="baseForm.end_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item>
          </div>
          <el-form-item label="备注"><el-input v-model="baseForm.notes" type="textarea" :rows="2" /></el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="editBase = false">取消</el-button>
          <el-button type="primary" @click="saveBase">保存</el-button>
        </template>
      </el-dialog>

      <!-- 合同编辑对话框 -->
      <el-dialog v-model="editContract" title="合同信息" width="720px">
        <el-form label-width="120px" size="small">
          <div style="display:grid; grid-template-columns:1fr 1fr; gap:0 14px;">
            <el-form-item label="合同编号"><el-input v-model="cForm.contract_no" /></el-form-item>
            <el-form-item label="签订日期"><el-date-picker v-model="cForm.sign_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item>
            <el-form-item label="合同到期日">
              <el-date-picker v-model="cForm.contract_end_date" type="date" value-format="YYYY-MM-DD" style="width:100%"
                placeholder="留空则用项目结束日期（用于续签提醒）" />
            </el-form-item>
            <el-form-item label="含税总金额(元)"><el-input-number v-model="cForm.total_amount" :controls="false" :precision="2" style="width:100%" /></el-form-item>
            <el-form-item label="税率(%)"><el-input-number v-model="cForm.tax_rate" :controls="false" :precision="2" :min="0" :max="100" style="width:100%" /></el-form-item>
            <el-form-item label="不含税金额(元)">
              <el-input-number v-model="cForm.excl_tax_amount" :controls="false" :precision="2" style="width:100%" placeholder="留空则按含税额与税率自动计算" />
            </el-form-item>
            <el-form-item label="税额(元)">
              <el-input-number v-model="cForm.tax_amount" :controls="false" :precision="2" style="width:100%" placeholder="留空则自动计算" />
            </el-form-item>
            <el-form-item label="质保期(月)"><el-input-number v-model="cForm.warranty_months" :controls="false" style="width:100%" /></el-form-item>
            <el-form-item label="质保期起算日"><el-date-picker v-model="cForm.warranty_start_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item>
            <el-form-item label="质保金比例(%)"><el-input-number v-model="cForm.warranty_ratio" :controls="false" :precision="2" :min="0" :max="100" style="width:100%" /></el-form-item>
            <el-form-item label="质保金金额(元)"><el-input-number v-model="cForm.warranty_amount" :controls="false" :precision="2" style="width:100%" /></el-form-item>
            <el-form-item label="预计质保金到账"><el-date-picker v-model="cForm.warranty_expected_date" type="date" value-format="YYYY-MM-DD" style="width:100%" placeholder="留空则按起算日+质保期推算" /></el-form-item>
            <el-form-item label="实际质保金到账"><el-date-picker v-model="cForm.warranty_actual_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item>
          </div>
          <el-form-item label="付款条款"><el-input v-model="cForm.payment_terms" type="textarea" :rows="3" /></el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="editContract = false">取消</el-button>
          <el-button type="primary" @click="saveContract">保存</el-button>
        </template>
      </el-dialog>

      <!-- 付款节点对话框 -->
      <el-dialog v-model="schedDlg" :title="schedForm.id ? '编辑付款节点' : '添加付款节点'" width="520px">
        <el-form label-width="100px" size="small">
          <el-form-item label="节点名称">
            <el-select v-model="schedForm.name" filterable allow-create style="width:100%">
              <el-option v-for="n in meta.schedule_names" :key="n" :label="n" :value="n" />
            </el-select>
          </el-form-item>
          <el-form-item label="比例(%)"><el-input-number v-model="schedForm.ratio" :controls="false" :precision="2" style="width:100%" @change="fillSchedAmount" /></el-form-item>
          <el-form-item label="计划金额(元)"><el-input-number v-model="schedForm.amount" :controls="false" :precision="2" style="width:100%" /></el-form-item>
          <el-form-item label="预计到账日"><el-date-picker v-model="schedForm.expected_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item>
          <el-form-item label="质保金节点"><el-switch v-model="schedForm.is_warranty" /></el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="schedDlg = false">取消</el-button>
          <el-button type="primary" @click="saveSched">保存</el-button>
        </template>
      </el-dialog>

      <!-- 回款对话框 -->
      <el-dialog v-model="payDlg" :title="payForm.id ? '编辑回款' : '新增回款'" width="520px">
        <el-form label-width="100px" size="small">
          <el-form-item label="回款金额(元)" required><el-input-number v-model="payForm.amount" :controls="false" :precision="2" :min="0" style="width:100%" /></el-form-item>
          <el-form-item label="回款日期" required><el-date-picker v-model="payForm.payment_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item>
          <el-form-item label="回款类型">
            <el-select v-model="payForm.type" style="width:100%">
              <el-option v-for="t in meta.payment_types" :key="t" :label="t" :value="t" />
            </el-select>
          </el-form-item>
          <el-form-item label="对应付款节点">
            <el-select v-model="payForm.schedule_id" clearable style="width:100%" placeholder="（可选）">
              <el-option v-for="s in d.schedules" :key="s.id" :label="`${s.name} ${money(s.amount)}`" :value="s.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="对应发票">
            <el-select v-model="payForm.invoice_id" clearable style="width:100%" placeholder="（可选）">
              <el-option v-for="i in d.invoices" :key="i.id" :label="`${i.invoice_no || '无号'} ${money(i.amount)}`" :value="i.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="备注"><el-input v-model="payForm.note" type="textarea" :rows="2" /></el-form-item>
        </el-form>
        <div class="muted" style="font-size:12px; padding:0 12px 10px;">
          保存后系统自动更新：已到账、待到账、回款率、付款节点状态、成本回收状态。
        </div>
        <template #footer>
          <el-button @click="payDlg = false">取消</el-button>
          <el-button type="primary" @click="savePay">保存</el-button>
        </template>
      </el-dialog>

      <!-- 发票对话框 -->
      <el-dialog v-model="invDlg" :title="invForm.id ? '编辑发票' : '登记发票'" width="520px">
        <el-form label-width="100px" size="small">
          <el-form-item label="发票号码"><el-input v-model="invForm.invoice_no" /></el-form-item>
          <el-form-item label="开票金额(元)" required><el-input-number v-model="invForm.amount" :controls="false" :precision="2" :min="0" style="width:100%" /></el-form-item>
          <el-form-item label="开票日期" required><el-date-picker v-model="invForm.issue_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item>
          <el-form-item label="类型">
            <el-select v-model="invForm.type" style="width:100%">
              <el-option v-for="t in meta.invoice_types" :key="t" :label="t" :value="t" />
            </el-select>
          </el-form-item>
          <el-form-item label="备注"><el-input v-model="invForm.note" type="textarea" :rows="2" /></el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="invDlg = false">取消</el-button>
          <el-button type="primary" @click="saveInv">保存</el-button>
        </template>
      </el-dialog>

      <!-- 成本对话框 -->
      <el-dialog v-model="costDlg" :title="costForm.id ? '编辑成本' : '新增成本'" width="560px">
        <el-form label-width="110px" size="small">
          <el-form-item label="成本类别">
            <el-radio-group v-model="costForm.kind" @change="onKindChange">
              <el-radio-button value="direct">直接成本</el-radio-button>
              <el-radio-button value="indirect">间接成本</el-radio-button>
              <el-radio-button value="tax">税收成本</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="分类">
            <el-select v-model="costForm.category" style="width:100%">
              <el-option v-for="cat in costCategories()" :key="cat" :label="cat" :value="cat" />
            </el-select>
          </el-form-item>
          <el-form-item v-if="costForm.kind === 'tax'" label="按合同额计算">
            <div style="display:flex; align-items:center; gap:10px; width:100%;">
              <el-select v-model="taxRatePct" filterable allow-create default-first-option
                placeholder="选择税率" style="width:120px" @change="calcTax">
                <el-option v-for="r in meta.tax_rate_options" :key="r" :label="r + '%'" :value="r" />
              </el-select>
              <span class="muted" style="font-size:12px;">{{ taxCalcHint }}</span>
            </div>
          </el-form-item>
          <el-form-item label="金额(元)" required><el-input-number v-model="costForm.amount" :controls="false" :precision="2" :min="0" style="width:100%" /></el-form-item>
          <el-form-item label="发生日期" required><el-date-picker v-model="costForm.cost_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item>
          <el-form-item label="备注"><el-input v-model="costForm.note" type="textarea" :rows="2" /></el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="costDlg = false">取消</el-button>
          <el-button type="primary" @click="saveCost">保存</el-button>
        </template>
      </el-dialog>
    </template>
  </div>
</template>
