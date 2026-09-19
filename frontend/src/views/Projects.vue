<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api, money, pct } from '../api'
import { loadCompanies, store } from '../store'

const router = useRouter()
const loading = ref(false)
const items = ref([])
const years = ref([])
const meta = ref({ statuses: [], project_types: [] })

const filters = reactive({ q: '', year: null, status: null, warranty_status: null, recovery: null })
const sortState = reactive({ sort: 'contract_amount', order: 'desc' })

const warrantyOptions = [
  { value: '已到账', label: '🟢 已到账' },
  { value: '即将到账', label: '🟡 即将到账' },
  { value: '已到期未到账', label: '🔴 已到期未到账' },
  { value: '日期未知', label: '⚪ 日期未知' },
  { value: '未到账', label: '未到账（未临期）' },
]

async function load() {
  loading.value = true
  try {
    const params = new URLSearchParams()
    params.set('company_id', store.companyId || '')
    if (filters.q) params.set('q', filters.q)
    if (filters.year) params.set('year', filters.year)
    if (filters.status) params.set('status', filters.status)
    if (filters.warranty_status) params.set('warranty_status', filters.warranty_status)
    if (filters.recovery) params.set('recovery', filters.recovery)
    params.set('sort', sortState.sort)
    params.set('order', sortState.order)
    const res = await api.get('/projects?' + params.toString())
    items.value = res.items
  } catch (e) {
    ElMessage.error(String(e.message || e))
  } finally {
    loading.value = false
  }
}
watch(() => store.companyId, load)

async function loadMeta() {
  try {
    meta.value = await api.get('/projects/meta')
    const dash = await api.get('/dashboard')
    years.value = dash.years || []
  } catch { /* ignore */ }
}

onMounted(() => { load(); loadMeta() })

function onSortChange({ prop, order }) {
  if (!order) { sortState.sort = 'contract_amount'; sortState.order = 'desc' }
  else {
    sortState.sort = prop
    sortState.order = order === 'ascending' ? 'asc' : 'desc'
  }
  load()
}

function open(p) { router.push('/projects/' + p.id) }

function resetFilters() {
  filters.q = ''; filters.year = null; filters.status = null
  filters.warranty_status = null; filters.recovery = null
  load()
}

const WARRANTY_STYLE = {
  '已到账': { color: '#2eab5c', text: '已到账' },
  '即将到账': { color: '#e6a23c', text: '即将到账' },
  '已到期未到账': { color: '#e2564a', text: '已到期未到账' },
  '日期未知': { color: '#b8c2cc', text: '日期未知' },
  '未到账': { color: '#b8c2cc', text: '未到账' },
}
const STATUS_TAG = {
  '未开始': 'info', '进行中': 'primary', '已完成': 'success', '已结算': 'warning', '已关闭': 'info',
}
</script>

<template>
  <div v-loading="loading">
    <div class="panel" style="margin-bottom:14px;">
      <div style="display:flex; flex-wrap:wrap; gap:10px; align-items:center;">
        <el-input v-model="filters.q" placeholder="搜索项目 / 客户 / 项目编号" clearable style="width:240px"
          :prefix-icon="'Search'" @keyup.enter="load" @clear="load" />
        <span class="muted" style="font-size:12.5px;">按上方「公司」筛选范围查看</span>
        <el-select v-model="filters.year" placeholder="年度" clearable style="width:110px" @change="load">
          <el-option v-for="y in years" :key="y" :label="y + '年'" :value="y" />
        </el-select>
        <el-select v-model="filters.status" placeholder="项目状态" clearable style="width:120px" @change="load">
          <el-option v-for="s in meta.statuses" :key="s" :label="s" :value="s" />
        </el-select>
        <el-select v-model="filters.warranty_status" placeholder="质保金状态" clearable style="width:150px" @change="load">
          <el-option v-for="o in warrantyOptions" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
        <el-select v-model="filters.recovery" placeholder="成本回收" clearable style="width:130px" @change="load">
          <el-option label="已收回成本" value="recovered" />
          <el-option label="尚未收回" value="not_recovered" />
        </el-select>
        <el-button :icon="'Search'" type="primary" plain @click="load">查询</el-button>
        <el-button :icon="'RefreshLeft'" text @click="resetFilters">重置</el-button>
        <div style="flex:1" />
        <span class="muted" style="font-size:12.5px">共 {{ items.length }} 个项目</span>
      </div>
    </div>

    <div class="panel" style="padding:0;">
      <el-table :data="items" style="width:100%" @sort-change="onSortChange" @row-click="open"
        :header-cell-style="{ background: '#f5f8fb' }" row-class-name="row-click" height="calc(100vh - 250px)">
        <el-table-column label="项目" min-width="200" fixed>
          <template #default="{ row }">
            <div style="font-weight:600; cursor:pointer;">{{ row.name }}</div>
            <div class="muted" style="font-size:11.5px;">
              {{ row.code || '编号待补充' }} · {{ row.customer_name || '客户待补充' }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="合同金额" width="110" sortable="custom" prop="contract_amount" align="right">
          <template #default="{ row }">
            <span class="num">{{ money(row.computed.contract_amount) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="已到账" width="105" sortable="custom" prop="received" align="right">
          <template #default="{ row }">
            <span class="num success-text">{{ money(row.computed.received) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="待到账" width="105" sortable="custom" prop="pending" align="right">
          <template #default="{ row }">
            <span class="num" :class="row.computed.over_received ? 'danger-text' : ''">
              {{ row.computed.over_received ? '超收 ' + money(-row.computed.pending) : money(row.computed.pending) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="总成本" width="105" align="right">
          <template #default="{ row }">
            <span class="num">{{ money(row.computed.total_cost) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="利润" width="105" sortable="custom" prop="profit" align="right">
          <template #default="{ row }">
            <span class="num" :class="row.computed.profit == null ? 'muted' : (row.computed.profit < 0 ? 'danger-text' : '')">
              {{ money(row.computed.profit) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="利润率" width="90" sortable="custom" prop="margin" align="right">
          <template #default="{ row }">
            <span :class="row.computed.margin == null ? 'muted' : (row.computed.margin < 0 ? 'danger-text' : '')">
              {{ row.computed.margin == null ? '—' : row.computed.margin + '%' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="发票状态" width="95" align="center">
          <template #default="{ row }">
            <span style="font-size:12px">{{ row.computed.invoice_status }}</span>
          </template>
        </el-table-column>
        <el-table-column label="成本回收" width="95" align="center">
          <template #default="{ row }">
            <span style="font-size:12px" :class="row.computed.recovery.recovered ? 'success-text' : 'muted'">
              {{ row.computed.recovery.recovered ? '已收回' : (row.computed.recovery.status === '无成本数据' ? '无成本' : '未收回') }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="质保金" width="130">
          <template #default="{ row }">
            <template v-if="row.computed.warranty.amount != null">
              <span class="dot" :style="{ background: WARRANTY_STYLE[row.computed.warranty.status]?.color }" />
              <span style="font-size:12px">{{ money(row.computed.warranty.amount) }}</span>
              <div class="muted" style="font-size:11px; padding-left:13px;">
                {{ WARRANTY_STYLE[row.computed.warranty.status]?.text }}
                <template v-if="row.computed.warranty.status === '即将到账'">({{ row.computed.warranty.days_to_due }}天)</template>
              </div>
            </template>
            <span v-else class="muted" style="font-size:12px">待补充</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="86" align="center" fixed="right">
          <template #default="{ row }">
            <el-tag :type="STATUS_TAG[row.status] || 'info'" size="small" effect="light">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="" width="60" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click.stop="open(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<style>
.row-click { cursor: pointer; }
</style>
