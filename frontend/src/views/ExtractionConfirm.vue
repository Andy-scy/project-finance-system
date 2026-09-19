<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, money } from '../api'
import { loadCompanies, store } from '../store'

const route = useRoute()
const router = useRouter()
const rid = route.params.id
const rec = ref(null)
const loading = ref(false)
const projects = ref([])
const meta = ref({ statuses: [], project_types: [], schedule_names: [] })

// 可编辑副本：fields[key] = { value, include }；schedules 行同样
const fields = ref({})
const scheds = ref([])

async function load() {
  loading.value = true
  try {
    rec.value = await api.get(`/extractions/${rid}`)
    const payload = rec.value.payload || {}
    const f = {}
    for (const [key, item] of Object.entries(payload.fields || {})) {
      f[key] = { ...item, include: !!(item.value != null && item.display != null && !item.needs_review) }
      // 有值但需要确认的默认勾选为 false；用户可自行勾选
    }
    fields.value = f
    scheds.value = (payload.payment_schedules || []).map((s, i) => ({ ...s, _i: i, include: true }))
  } catch (e) {
    ElMessage.error(String(e.message || e))
  } finally {
    loading.value = false
  }
}
onMounted(load)

async function loadProjects() {
  try {
    const res = await api.get('/projects?sort=contract_amount&order=desc')
    projects.value = res.items
  } catch { /* ignore */ }
}
onMounted(loadProjects)
onMounted(loadCompanies)
onMounted(async () => { try { meta.value = await api.get('/projects/meta') } catch { /* ignore */ } })

const mode = ref('new')
const targetProjectId = ref(null)
const newProj = reactive({
  company_id: store.companyId || null,
  name: '', code: '', customer_name: '', owner: '', project_type: '软件开发', status: '进行中',
  start_date: null, end_date: null,
})

// 新建项目默认名称来自 AI
import { watch } from 'vue'
watch(rec, (r) => {
  if (r && mode.value === 'new') {
    newProj.name = fields.value.project_name?.value || ''
    newProj.customer_name = fields.value.customer_name?.value || ''
    newProj.start_date = fields.value.start_date?.value || null
    newProj.end_date = fields.value.end_date?.value || null
  }
})

// 合同字段对象（confirm 提交用）
function buildContract() {
  const c = {}
  const get = (k) => fields.value[k]?.include ? fields.value[k].value : undefined
  const no = get('contract_no'); if (no != null) c.contract_no = no
  const ta = get('total_amount'); if (ta != null) c.total_amount = ta
  const tr = get('tax_rate'); if (tr != null) c.tax_rate = tr
  const ex = get('excl_tax_amount'); if (ex != null) c.excl_tax_amount = ex
  const tx = get('tax_amount'); if (tx != null) c.tax_amount = tx
  const sd = get('sign_date'); if (sd != null) c.sign_date = sd
  const pt = get('payment_terms'); if (pt != null) c.payment_terms = pt
  const wm = get('warranty_months'); if (wm != null) c.warranty_months = wm
  const ws = get('warranty_start_date'); if (ws != null) c.warranty_start_date = ws
  const wr = get('warranty_ratio'); if (wr != null) c.warranty_ratio = wr
  const wa = get('warranty_amount'); if (wa != null) c.warranty_amount = wa
  const we = get('warranty_expected_date'); if (we != null) c.warranty_expected_date = we
  return c
}

const contractFields = ['contract_no', 'total_amount', 'tax_rate', 'excl_tax_amount', 'tax_amount',
  'sign_date', 'payment_terms', 'warranty_months', 'warranty_start_date', 'warranty_ratio',
  'warranty_amount', 'warranty_expected_date']
const projectTextFields = ['project_name', 'customer_name', 'start_date', 'end_date']

const derivedTaxPreview = computed(() => {
  const ta = fields.value.total_amount, tr = fields.value.tax_rate
  if (ta?.value && tr?.value) {
    const excl = ta.value / (1 + tr.value / 100)
    return { excl, tax: ta.value - excl }
  }
  return null
})

function fieldStatus(f) {
  if (f.value == null) return { text: '未识别', type: 'info' }
  if (f.needs_review) return { text: '需要人工确认', type: 'warning' }
  return { text: 'AI识别', type: 'success' }
}
function confTag(c) {
  if (c == null) return 'info'
  if (c >= 0.8) return 'success'
  if (c >= 0.6) return 'warning'
  return 'danger'
}

function addSchedule() {
  scheds.value.push({
    name: '', ratio: null, amount: null, expected_date: null, is_warranty: false,
    confidence: null, source: { page: null, quote: null }, needs_review: false, _i: -1, include: true,
  })
}
function removeSchedule(i) { scheds.value.splice(i, 1) }
function fillAmount(row) {
  const ta = fields.value.total_amount?.value
  if (row.ratio != null && ta) row.amount = Math.round(ta * row.ratio) / 100
}

const saving = ref(false)
async function confirmWrite() {
  const anySched = scheds.value.some((s) => s.include && (s.name || s.amount))
  if (mode.value === 'new' && !newProj.name.trim()) {
    ElMessage.warning('请填写项目名称（可用 AI 识别结果）。')
    return
  }
  if (mode.value === 'existing' && !targetProjectId.value) {
    ElMessage.warning('请选择要并入的已有项目。')
    return
  }
  saving.value = true
  try {
    const body = {
      mode: mode.value,
      project_id: mode.value === 'existing' ? targetProjectId.value : undefined,
      replace_schedules: mode.value === 'existing' ? anySched : true,
      project: mode.value === 'new' ? {
        company_id: newProj.company_id,
        name: newProj.name, code: newProj.code, customer_name: newProj.customer_name,
        owner: newProj.owner, project_type: newProj.project_type, status: newProj.status,
        start_date: newProj.start_date, end_date: newProj.end_date,
      } : {},
      contract: buildContract(),
      schedules: scheds.value.filter((s) => s.include).map((s) => ({
        name: s.name, ratio: s.ratio, amount: s.amount,
        expected_date: s.expected_date, is_warranty: s.is_warranty,
      })),
    }
    const res = await api.post(`/extractions/${rid}/confirm`, body)
    ElMessage.success(`已写入项目「${res.project_name}」`)
    router.push('/projects/' + res.project_id)
  } catch (e) {
    ElMessage.error(String(e.message || e))
  } finally {
    saving.value = false
  }
}

async function discard() {
  await ElMessageBox.confirm('放弃这份识别结果？（不会写入任何数据）', '确认', { type: 'warning' })
  await api.post(`/extractions/${rid}/discard`)
  ElMessage.info('已放弃')
  router.push('/projects/new')
}

const F_LABEL = {
  project_name: '项目名称', customer_name: '客户名称', contract_no: '合同编号',
  total_amount: '合同总金额（含税）', excl_tax_amount: '不含税金额', tax_rate: '税率',
  tax_amount: '税额', sign_date: '合同签订日期', start_date: '项目开始日期',
  end_date: '项目结束日期', payment_terms: '付款条款', warranty_months: '质保期',
  warranty_start_date: '质保期起算日', warranty_ratio: '质保金比例', warranty_amount: '质保金金额',
  warranty_expected_date: '预计质保金到账日', invoice_requirements: '发票要求', notes: '其他重要条款',
}
</script>

<template>
  <div v-loading="loading">
    <template v-if="rec">
      <div class="panel" style="margin-bottom:14px;">
        <div style="display:flex; align-items:center; gap:12px; flex-wrap:wrap;">
          <el-icon :size="26" color="#1f4e79"><MagicStick /></el-icon>
          <div style="flex:1;">
            <h2 style="margin:0; font-size:17px;">AI 识别结果确认</h2>
            <div class="muted" style="font-size:12.5px;">
              来源文件：{{ rec.file_name }}　模型：{{ rec.model || '—' }}　时间：{{ rec.created_at }}
            </div>
          </div>
          <div v-if="rec.payload?.summary" style="max-width:420px;">
            <el-alert type="info" :closable="false"><template #title>{{ rec.payload.summary }}</template></el-alert>
          </div>
        </div>
        <el-alert type="warning" :closable="false" style="margin-top:12px;">
          <template #title>请逐项核对后再确认写入。AI 只提取合同中明确写出的信息，识别不到的显示「未识别」，不会编造数据；未勾选「采用」的字段不会写入系统。</template>
        </el-alert>
      </div>

      <div style="display:grid; grid-template-columns: 1.7fr 1fr; gap:14px; align-items:start;">
        <div class="panel">
          <div class="panel-title">字段映射：合同原文识别结果 → 系统字段</div>
          <el-table :data="Object.entries(fields)" size="small" class="field-map" row-key="0">
            <el-table-column label="系统字段" width="130">
              <template #default="{ row }"><b style="font-size:12.5px">{{ F_LABEL[row[0]] || row[0] }}</b></template>
            </el-table-column>
            <el-table-column label="识别值（可修改）" min-width="180">
              <template #default="{ row }">
                <template v-if="row[1].kind === 'money'">
                  <el-input-number v-model="row[1].value" :controls="false" :precision="2" size="small" style="width:100%" placeholder="未识别" />
                </template>
                <template v-else-if="row[1].kind === 'rate'">
                  <el-input-number v-model="row[1].value" :controls="false" :precision="2" size="small" style="width:100%" placeholder="未识别" />
                </template>
                <template v-else-if="row[1].kind === 'int'">
                  <el-input-number v-model="row[1].value" :controls="false" size="small" style="width:100%" placeholder="未识别" />
                </template>
                <template v-else-if="row[1].kind === 'date'">
                  <el-date-picker v-model="row[1].value" type="date" value-format="YYYY-MM-DD" size="small" style="width:100%" placeholder="未识别" />
                </template>
                <template v-else>
                  <el-input v-model="row[1].value" size="small" type="textarea" :rows="1" autosize placeholder="未识别" />
                </template>
              </template>
            </el-table-column>
            <el-table-column label="来源（页码/原文）" min-width="170">
              <template #default="{ row }">
                <div style="font-size:11.5px; color:#8a97a5;">
                  <template v-if="row[1].source?.page">第 {{ row[1].source.page }} 页</template>
                  <div v-if="row[1].source?.quote" style="font-style:italic; margin-top:2px;">“{{ row[1].source.quote }}”</div>
                  <span v-if="!row[1].source?.page && !row[1].source?.quote">—</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="置信度" width="86" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="confTag(row[1].confidence)" effect="plain" class="tag-pill">
                  {{ row[1].confidence != null ? (row[1].confidence * 100).toFixed(0) + '%' : '—' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="110" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="fieldStatus(row[1]).type" class="tag-pill">{{ fieldStatus(row[1]).text }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="采用" width="60" align="center">
              <template #default="{ row }">
                <el-checkbox v-model="row[1].include" :disabled="row[1].value == null" />
              </template>
            </el-table-column>
          </el-table>

          <div v-if="derivedTaxPreview" class="muted" style="font-size:12px; margin-top:8px;">
            系统将自动换算：不含税金额 ≈ <b>{{ money(derivedTaxPreview.excl) }}</b> 元，
            税额 ≈ <b>{{ money(derivedTaxPreview.tax) }}</b> 元（含税额 ÷ (1 + 税率)）。若合同已写明不含税金额，请以识别值勾选为准。
          </div>

          <div class="panel-title" style="margin-top:18px;">付款节点（可修改 / 可增删）</div>
          <el-table :data="scheds" size="small" class="field-map">
            <el-table-column label="采用" width="56" align="center">
              <template #default="{ row }"><el-checkbox v-model="row.include" /></template>
            </el-table-column>
            <el-table-column label="节点名称" width="120">
              <template #default="{ row }">
                <el-select v-model="row.name" filterable allow-create size="small" style="width:100%">
                  <el-option v-for="n in meta.schedule_names" :key="n" :label="n" :value="n" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="比例(%)" width="100">
              <template #default="{ row }">
                <el-input-number v-model="row.ratio" :controls="false" :precision="2" size="small" style="width:100%" @change="fillAmount(row)" />
              </template>
            </el-table-column>
            <el-table-column label="金额(元)" width="140">
              <template #default="{ row }">
                <el-input-number v-model="row.amount" :controls="false" :precision="2" size="small" style="width:100%" />
              </template>
            </el-table-column>
            <el-table-column label="预计到账" width="140">
              <template #default="{ row }">
                <el-date-picker v-model="row.expected_date" type="date" value-format="YYYY-MM-DD" size="small" style="width:100%" placeholder="未识别" />
              </template>
            </el-table-column>
            <el-table-column label="质保金" width="64" align="center">
              <template #default="{ row }"><el-checkbox v-model="row.is_warranty" /></template>
            </el-table-column>
            <el-table-column label="来源/置信度" min-width="150">
              <template #default="{ row }">
                <div style="font-size:11.5px; color:#8a97a5;">
                  <template v-if="row.source?.page">第 {{ row.source.page }} 页</template>
                  <span v-if="row.confidence != null" :style="{ color: row.confidence < 0.6 ? '#c0392b' : '#8a97a5' }">
                    　{{ (row.confidence * 100).toFixed(0) }}%
                  </span>
                  <div v-if="row.source?.quote" style="font-style:italic;">“{{ row.source.quote }}”</div>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="" width="56" align="center">
              <template #default="{ $index }">
                <el-button link type="danger" size="small" @click="removeSchedule($index)">删</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-button size="small" :icon="'Plus'" style="margin-top:8px" @click="addSchedule">添加节点</el-button>
        </div>

        <!-- 右侧：写入目标 -->
        <div class="panel">
          <div class="panel-title">确认写入</div>
          <el-radio-group v-model="mode" style="margin-bottom:14px;">
            <el-radio-button value="new">创建新项目</el-radio-button>
            <el-radio-button value="existing">并入已有项目</el-radio-button>
          </el-radio-group>

          <template v-if="mode === 'new'">
            <el-form label-width="90px" size="small">
              <el-form-item label="所属公司">
                <el-select v-model="newProj.company_id" style="width:100%" placeholder="选择公司">
                  <el-option v-for="c in store.companies" :key="c.id" :value="c.id" :label="c.name" />
                </el-select>
              </el-form-item>
              <el-form-item label="项目名称" required><el-input v-model="newProj.name" /></el-form-item>
              <div style="display:grid; grid-template-columns:1fr 1fr; gap:0 10px;">
                <el-form-item label="项目编号"><el-input v-model="newProj.code" /></el-form-item>
                <el-form-item label="客户名称"><el-input v-model="newProj.customer_name" /></el-form-item>
                <el-form-item label="负责人"><el-input v-model="newProj.owner" /></el-form-item>
                <el-form-item label="项目类型">
                  <el-select v-model="newProj.project_type" filterable allow-create style="width:100%">
                    <el-option v-for="t in meta.project_types" :key="t" :label="t" :value="t" />
                  </el-select>
                </el-form-item>
                <el-form-item label="状态">
                  <el-select v-model="newProj.status" style="width:100%">
                    <el-option v-for="s in meta.statuses" :key="s" :label="s" :value="s" />
                  </el-select>
                </el-form-item>
                <el-form-item label="开始日期"><el-date-picker v-model="newProj.start_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item>
                <el-form-item label="结束日期"><el-date-picker v-model="newProj.end_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item>
              </div>
            </el-form>
          </template>
          <template v-else>
            <el-select v-model="targetProjectId" filterable placeholder="选择已有项目" style="width:100%">
              <el-option v-for="p in projects" :key="p.id" :label="`${p.name}（${p.customer_name || '客户待补充'}）`" :value="p.id" />
            </el-select>
            <el-alert type="info" :closable="false" style="margin-top:10px;">
              <template #title>只更新上面勾选「采用」的字段；付款节点按勾选结果合并。</template>
            </el-alert>
          </template>

          <el-divider />
          <div style="display:flex; gap:10px;">
            <el-button type="primary" :loading="saving" :icon="'Check'" @click="confirmWrite" style="flex:1;">
              确认写入项目
            </el-button>
            <el-button :icon="'Close'" @click="discard">放弃</el-button>
          </div>

          <el-divider />
          <div class="panel-title" style="margin:0 0 8px;">合同原文摘录</div>
          <div style="font-size:12px; color:#5c6b7a; line-height:1.8; max-height:260px; overflow-y:auto;
                      background:#f7fafc; border:1px solid #e8ecf2; border-radius:6px; padding:10px; white-space:pre-wrap;">{{ rec.raw_digest || '—' }}…</div>
        </div>
      </div>
    </template>
  </div>
</template>
