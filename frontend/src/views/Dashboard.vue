<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { api, money, moneyWan, pct } from '../api'
import { companyName, loadCompanies, refreshReminderTotal, store } from '../store'
import KpiCard from '../components/KpiCard.vue'
import EChart from '../components/EChart.vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const year = ref(new Date().getFullYear())
const data = ref(null)
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    data.value = await api.get(`/dashboard?year=${year.value}&company_id=${store.companyId}`)
  } catch (e) {
    ElMessage.error(String(e.message || e))
  } finally {
    loading.value = false
  }
}
onMounted(load)
onMounted(loadCompanies)
watch(() => store.companyId, load)
function changeYear(y) { if (y) load() }

const k = computed(() => data.value?.kpis || {})
const charts = computed(() => data.value?.charts || {})
const years = computed(() => {
  const ys = data.value?.years || [new Date().getFullYear()]
  return ys
})

const levelName = { danger: '紧急', warning: '预警', info: '提示' }
const alertType = { danger: 'error', warning: 'warning', info: 'info' }

const monthlyOption = computed(() => ({
  tooltip: { trigger: 'axis', valueFormatter: (v) => money(v) + ' 元' },
  legend: { data: ['签约合同额', '实际回款', '成本发生'], textStyle: { fontSize: 12 } },
  grid: { left: 60, right: 20, top: 34, bottom: 26 },
  xAxis: { type: 'category', data: charts.value.monthly?.months || [] },
  yAxis: { type: 'value', axisLabel: { formatter: (v) => (v / 10000) + '万' } },
  series: [
    { name: '签约合同额', type: 'bar', data: charts.value.monthly?.sign || [], itemStyle: { color: '#8fb4d9' }, barGap: 0 },
    { name: '实际回款', type: 'bar', data: charts.value.monthly?.payment || [], itemStyle: { color: '#1f4e79' } },
    { name: '成本发生', type: 'line', data: charts.value.monthly?.cost || [], itemStyle: { color: '#c0392b' }, smooth: true, symbolSize: 5 },
  ],
}))

function rankOption(rows, color) {
  const sorted = [...(rows || [])].reverse()
  return {
    tooltip: { valueFormatter: (v) => money(v) + ' 元' },
    grid: { left: 110, right: 40, top: 8, bottom: 24 },
    xAxis: { type: 'value', axisLabel: { formatter: (v) => (v / 10000) + '万' } },
    yAxis: { type: 'category', data: sorted.map((r) => r.name.length > 9 ? r.name.slice(0, 9) + '…' : r.name), axisLabel: { fontSize: 11 } },
    series: [{ type: 'bar', data: sorted.map((r) => r.value), itemStyle: { color }, barMaxWidth: 16, label: { show: true, position: 'right', fontSize: 10, formatter: (p) => moneyWan(p.value) + '万' } }],
  }
}
const amountRankOption = computed(() => rankOption(charts.value.amount_rank, '#4a7aa5'))
const profitRankOption = computed(() => rankOption(charts.value.profit_rank, '#1e8449'))

const marginOption = computed(() => {
  const top = charts.value.margin_top || []
  const bottom = charts.value.margin_bottom || []
  return {
    tooltip: { valueFormatter: (v) => v + '%' },
    grid: { left: 110, right: 46, top: 8, bottom: 24 },
    xAxis: { type: 'value', axisLabel: { formatter: '{value}%' } },
    yAxis: { type: 'category', data: [...bottom, ...top].map((r) => r.name.length > 9 ? r.name.slice(0, 9) + '…' : r.name), axisLabel: { fontSize: 11 } },
    series: [{
      type: 'bar',
      data: [...bottom, ...top].map((r) => ({
        value: r.value,
        itemStyle: { color: r.value < 0 ? '#c0392b' : '#2e7d32' },
      })),
      barMaxWidth: 16,
      label: { show: true, position: 'right', fontSize: 10, formatter: (p) => p.value + '%' },
    }],
  }
})

const costOption = computed(() => {
  const cs = charts.value.cost_structure || {}
  const segs = [
    { name: '直接成本', value: cs.direct || 0, color: '#1f4e79' },
    { name: '间接成本', value: cs.indirect || 0, color: '#8fb4d9' },
    { name: '税金成本', value: cs.tax || 0, color: '#e67e22' },
  ].filter(s => s.value > 0)
  return {
    tooltip: { valueFormatter: (v) => money(v) + ' 元' },
    legend: { bottom: 0, textStyle: { fontSize: 11 } },
    series: [{
      type: 'pie', radius: ['38%', '62%'], center: ['50%', '44%'],
      data: segs.length ? segs.map(s => ({ name: s.name, value: s.value, itemStyle: { color: s.color } }))
                        : [{ name: '暂无成本数据', value: 1, itemStyle: { color: '#e8ecf2' } }],
      label: { formatter: '{b}\n{d}%', fontSize: 11 },
    }],
  }
})

const costCatOption = computed(() => {
  const cs = charts.value.cost_structure || {}
  const entries = Object.entries(cs.direct_by_category || {})
  return {
    tooltip: { valueFormatter: (v) => money(v) + ' 元' },
    series: [{
      type: 'pie', radius: ['30%', '58%'], center: ['50%', '50%'],
      data: entries.map(([name, value], i) => ({
        name, value,
        itemStyle: { color: ['#1f4e79', '#4a7aa5', '#7a9cbf', '#a9c2d8', '#c4d5e5', '#e3ecf4'][i % 6] },
      })),
      label: { fontSize: 10, formatter: '{b} {d}%' },
    }],
  }
})

const payStatusOption = computed(() => {
  const ps = charts.value.payment_status || {}
  return {
    tooltip: { valueFormatter: (v) => money(v) + ' 元' },
    legend: { bottom: 0, textStyle: { fontSize: 11 } },
    series: [{
      type: 'pie', radius: ['38%', '62%'], center: ['50%', '44%'],
      data: [
        { name: '已到账', value: ps.received || 0, itemStyle: { color: '#1e8449' } },
        { name: '待到账', value: ps.pending || 0, itemStyle: { color: '#c0392b' } },
        { name: '待收质保金', value: ps.warranty || 0, itemStyle: { color: '#e67e22' } },
      ],
      label: { formatter: '{b}\n{d}%', fontSize: 11 },
    }],
  }
})

const statusOption = computed(() => {
  const sc = charts.value.status_counts || {}
  const colors = { '未开始': '#b8c2cc', '进行中': '#4a90d9', '已完成': '#2eab5c', '已结算': '#1f4e79', '已关闭': '#7a8694' }
  return {
    tooltip: {},
    legend: { bottom: 0, textStyle: { fontSize: 11 } },
    series: [{
      type: 'pie', radius: ['38%', '62%'], center: ['50%', '44%'],
      data: Object.entries(sc).map(([name, value]) => ({ name, value, itemStyle: { color: colors[name] || '#999' } })),
      label: { formatter: '{b} {c}个', fontSize: 11 },
    }],
  }
})

function goProject(a) {
  if (a.project_id) router.push('/projects/' + a.project_id)
}
function openReport() {
  window.open(`/api/report/annual?year=${year.value}`, '_blank')
}
function receivedRatio() {
  const total = k.value.contract_amount
  if (!total) return null
  return pct(k.value.received / total * 100)
}
</script>

<template>
  <div v-loading="loading">
    <div class="panel" style="margin-bottom:16px; display:flex; align-items:center; gap:14px; padding:12px 18px;">
      <span style="font-weight:600">年度经营看板</span>
      <el-tag effect="dark" size="small" style="background:#2e6da4; border-color:#2e6da4;">
        <el-icon style="vertical-align:-2px"><OfficeBuilding /></el-icon>
        {{ companyName() }}
      </el-tag>
      <el-select v-model="year" style="width:110px" @change="changeYear">
        <el-option v-for="y in years" :key="y" :label="y + '年'" :value="y" />
      </el-select>
      <div style="flex:1" />
      <el-button :icon="'Refresh'" size="small" @click="load">刷新</el-button>
      <el-button type="primary" size="small" :icon="'Download'" @click="openReport">生成年度报告(PDF)</el-button>    </div>

    <!-- 首页七问 -->
    <div class="kpi-grid" style="grid-template-columns: repeat(4, 1fr); margin-bottom:12px;">
      <KpiCard accent :label="`${year}年签了多少钱的项目？`" :value="moneyWan(k.contract_amount)" extra="合同总额（含税）" />
      <KpiCard :label="'赚了多少钱？（收入−成本）'" :value="moneyWan(k.profit)"
        :tone="(k.profit || 0) < 0 ? 'danger' : 'success'"
        :extra="`利润率 ${pct(k.avg_margin)} · 收入口径${'不含税'}`" />
      <KpiCard :label="'已经收到多少钱？'" :value="moneyWan(k.received)" tone="success" :extra="`回款比例 ${receivedRatio() ?? '—'}`" />
      <KpiCard :label="'还有多少钱没收到？'" :value="moneyWan(k.pending)" tone="warn" extra="待到账金额" />
      <KpiCard :label="'有多少质保金待收？'" :value="moneyWan(k.warranty_pending)" tone="warn" extra="含即将到期与已逾期" />
      <KpiCard :label="'有没有逾期 / 异常款项？'"
        :value="String((data?.alerts || []).filter(a => a.level === 'danger').length)" unit="项紧急"
        :tone="(data?.alerts || []).some(a => a.level === 'danger') ? 'danger' : ''"
        :extra="`全部待处理 ${(data?.alerts || []).length} 项`" />
      <KpiCard :label="'成本收回情况'"
        :value="`${k.recovered_count ?? 0}/${(k.recovered_count ?? 0) + (k.not_recovered_count ?? 0)}`" unit="个项目已回收"
        :extra="`尚未收回成本 ${k.not_recovered_count ?? 0} 个`" />
      <KpiCard :label="'开票情况'" :value="moneyWan(k.invoiced)" :extra="`未开票 ${moneyWan(k.not_invoiced)}`" />
    </div>

    <!-- 第二行指标 -->
    <div class="kpi-grid" style="grid-template-columns: repeat(6, 1fr); margin-bottom:16px;">
      <KpiCard :label="'项目总数'" :value="String(k.project_count ?? 0)" unit="个" />
      <KpiCard :label="'不含税收入'" :value="moneyWan(k.revenue)" />
      <KpiCard :label="'总成本'" :value="moneyWan(k.total_cost)" :extra="`直接 ${moneyWan(k.direct_cost)} + 间接 ${moneyWan(k.indirect_cost)} + 税金 ${moneyWan(k.tax_cost)}`" />
      <KpiCard :label="'已开票'" :value="moneyWan(k.invoiced)" />
      <KpiCard :label="'未开票'" :value="moneyWan(k.not_invoiced)" />
      <KpiCard :label="'待收质保金'" :value="moneyWan(k.warranty_pending)" />
    </div>

    <!-- 图表 -->
    <div class="panel">
      <div class="panel-title">年度收入与回款趋势
        <span class="right">按月统计：签约合同额 / 实际回款 / 成本发生（单位：元）</span>
      </div>
      <EChart :option="monthlyOption" height="300px" />
    </div>

    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:16px; margin-top:16px;">
      <div class="panel">
        <div class="panel-title">项目合同金额排名 <span class="right">TOP 8</span></div>
        <EChart :option="amountRankOption" height="260px" />
      </div>
      <div class="panel">
        <div class="panel-title">项目利润排名 <span class="right">TOP 8</span></div>
        <EChart :option="profitRankOption" height="260px" />
      </div>
      <div class="panel">
        <div class="panel-title">利润率排名 <span class="right">最高 5 个 / 最低 5 个（红色为亏损）</span></div>
        <EChart :option="marginOption" height="260px" />
      </div>
      <div class="panel">
        <div class="panel-title">回款情况 <span class="right">已到账 / 待到账 / 待收质保金</span></div>
        <EChart :option="payStatusOption" height="260px" />
      </div>
      <div class="panel">
        <div class="panel-title">成本构成 <span class="right">直接 / 间接</span></div>
        <EChart :option="costOption" height="260px" />
      </div>
      <div class="panel">
        <div class="panel-title">项目状态分布</div>
        <EChart :option="statusOption" height="260px" />
      </div>
    </div>

    <div class="panel" v-if="(charts.cost_structure?.direct_by_category || {})" >
      <div class="panel-title">直接成本分类构成</div>
      <EChart v-if="Object.keys(charts.cost_structure?.direct_by_category || {}).length" :option="costCatOption" height="240px" />
      <el-empty v-else description="本年度暂无成本数据" :image-size="60" />
    </div>

    <!-- 待处理事项 -->
    <div class="panel">
      <div class="panel-title">待处理事项
        <span class="right">系统自动检测 · 点击可进入项目处理</span>
      </div>
      <template v-if="(data?.alerts || []).length">
        <el-alert v-for="(a, i) in data.alerts" :key="i" :type="alertType[a.level]" :closable="false"
          style="margin-bottom:8px; cursor:pointer;" @click="goProject(a)">
          <template #title>
            <b>[{{ levelName[a.level] }}] {{ a.project_name }}</b> — {{ a.title }}
          </template>
          {{ a.detail }}
        </el-alert>
      </template>
      <el-empty v-else description="未发现异常事项，一切正常 ✓" :image-size="70" />
    </div>
  </div>
</template>
