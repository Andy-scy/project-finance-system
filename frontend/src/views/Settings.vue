<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api'
import { loadCompanies, store } from '../store'

const ai = reactive({ ai_base_url: '', ai_api_key: '', ai_model: '', ai_vision_model: '' })
const aiHint = ref('')
const calc = reactive({
  tax_mode: 'excl_tax', reminder_days: '30,7,0', invoice_overdue_days: 30, margin_alert_ratio: 0,
  renewal_remind_days: 30, settlement_remind_days: 7,
})
const years = ref([])
const reportYear = ref(new Date().getFullYear())
const testing = ref(false)
const importInput = ref(null)
const importing = ref(false)
const newCompanyName = ref('')

onMounted(async () => {
  try {
    const s = await api.get('/settings')
    Object.assign(ai, { ai_base_url: s.ai_base_url, ai_api_key: s.ai_api_key, ai_model: s.ai_model, ai_vision_model: s.ai_vision_model })
    aiHint.value = s.ai_api_key_hint || ''
    Object.assign(calc, {
      tax_mode: s.tax_mode, reminder_days: s.reminder_days,
      invoice_overdue_days: s.invoice_overdue_days, margin_alert_ratio: s.margin_alert_ratio,
      renewal_remind_days: s.renewal_remind_days, settlement_remind_days: s.settlement_remind_days,
    })
    const dash = await api.get('/dashboard')
    years.value = dash.years || []
    loadCompanies(true)
  } catch (e) { ElMessage.error(String(e.message || e)) }
})

async function addCompany() {
  const name = newCompanyName.value.trim()
  if (!name) { ElMessage.warning('请输入公司名称'); return }
  try {
    await api.post('/companies', { name })
    newCompanyName.value = ''
    ElMessage.success('公司已添加')
    loadCompanies(true)
  } catch (e) { ElMessage.error(String(e.message || e)) }
}
async function renameCompany(c) {
  const { value } = await ElMessageBox.prompt('修改公司名称', '重命名', { inputValue: c.name, inputPattern: /\S+/, inputErrorMessage: '名称不能为空' })
  await api.put('/companies/' + c.id, { name: value.trim() })
  ElMessage.success('已修改')
  loadCompanies(true)
}
async function removeCompany(c) {
  await ElMessageBox.confirm(`删除公司「${c.name}」？（仅能删除没有项目的公司）`, '确认', { type: 'warning' })
  await api.del('/companies/' + c.id)
  ElMessage.success('已删除')
  loadCompanies(true)
}

async function saveSettings() {
  try {
    await api.put('/settings', { ...ai, ...calc })
    ElMessage.success('设置已保存')
    const s = await api.get('/settings')
    ai.ai_api_key = s.ai_api_key
    aiHint.value = s.ai_api_key_hint || ''
  } catch (e) { ElMessage.error(String(e.message || e)) }
}

async function testAi() {
  testing.value = true
  try {
    await api.put('/settings', { ...ai, ...calc })
    const res = await api.post('/settings/test-ai')
    if (res.ok) ElMessage.success(`连接成功（${res.model}）：${res.reply}`)
    else ElMessage.error(res.error || '连接失败')
  } catch (e) { ElMessage.error(String(e.message || e)) }
  finally { testing.value = false }
}

function exportXlsx() { window.open(`/api/export/projects.xlsx?year=${reportYear.value || ''}`, '_blank') }
function exportCsv() { window.open(`/api/export/projects.csv?year=${reportYear.value || ''}`, '_blank') }
function exportDetail() { window.open(`/api/export/payments.xlsx?year=${reportYear.value || ''}`, '_blank') }
function downloadTemplate() { window.open('/api/export/template.xlsx', '_blank') }
function openReport() { window.open(`/api/report/annual?year=${reportYear.value}`, '_blank') }

async function doImport(ev) {
  const file = ev.target.files && ev.target.files[0]
  if (!file) return
  importing.value = true
  try {
    const fd = new FormData()
    fd.append('file', file)
    const res = await api.upload('/import/projects', fd)
    ElMessage.success(`导入成功：新建 ${res.created} 个项目${res.errors?.length ? '，' + res.errors.length + ' 行有问题' : ''}`)
    if (res.errors?.length) ElMessageBox.alert(res.errors.join('<br/>'), '导入提示', { dangerouslyUseHTMLString: true })
  } catch (e) { ElMessage.error(String(e.message || e)) }
  finally { importing.value = false; ev.target.value = '' }
}

async function loadDemo() {
  await ElMessageBox.confirm('载入 8 个示例项目（覆盖 2025/2026 两个年度，包含各类异常场景）？', '示例数据', { type: 'info' })
  try {
    let res = await api.post('/system/demo-data', {})
    if (!res.ok && String(res.error).includes('已有')) {
      await ElMessageBox.confirm('数据库中已有项目。要清空后重新载入示例数据吗？（现有数据将全部删除）', '确认覆盖', { type: 'error', confirmButtonText: '清空并载入' })
      res = await api.post('/system/demo-data', { force: true })
    }
    if (res.ok) ElMessage.success(`已载入 ${res.created} 个示例项目，请刷新看板查看`)
    else ElMessage.error(res.error || '载入失败')
  } catch (e) { /* 取消 */ }
}

async function resetAll() {
  await ElMessageBox.confirm('将删除全部项目及回款、成本、发票、附件记录（系统设置保留）。此操作不可恢复！', '危险操作', { type: 'error', confirmButtonText: '确认清空' })
  await api.post('/system/reset')
  ElMessage.success('数据已清空')
}
</script>

<template>
  <div style="max-width: 980px;">
    <!-- 公司管理 -->
    <div class="panel">
      <div class="panel-title">公司管理
        <span class="right">顶部切换器按公司筛选全部数据；删掉的公司无法恢复</span>
      </div>
      <div style="display:flex; gap:10px; margin-bottom:12px;">
        <el-input v-model="newCompanyName" placeholder="输入新公司名称" style="width:280px" @keyup.enter="addCompany" />
        <el-button type="primary" :icon="'Plus'" @click="addCompany">添加公司</el-button>
      </div>
      <el-table :data="store.companies" size="small" empty-text="暂无公司（后端会自动创建默认公司）">
        <el-table-column prop="name" label="公司名称" min-width="200" />
        <el-table-column label="项目数" width="90" align="center">
          <template #default="{ row }">{{ row.project_count }}</template>
        </el-table-column>
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="renameCompany(row)">重命名</el-button>
            <el-button link type="danger" size="small" @click="removeCompany(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- AI 配置 -->
    <div class="panel">
      <div class="panel-title">AI 识别配置 <span class="right">API Key 仅保存在本机后端数据库，不会下发到浏览器</span></div>
      <el-form label-width="150px" size="small">
        <el-form-item label="接口地址 Base URL">
          <el-input v-model="ai.ai_base_url" placeholder="https://open.bigmodel.cn/api/paas/v4" />
          <div class="muted" style="font-size:12px;">支持 OpenAI 兼容接口：智谱 GLM、DeepSeek、OpenAI、通义等。智谱示例：https://open.bigmodel.cn/api/paas/v4</div>
        </el-form-item>
        <el-form-item label="API Key">
          <el-input v-model="ai.ai_api_key" type="password" show-password
            :placeholder="aiHint ? `已配置（${aiHint}），输入新值可修改` : 'sk-…'" />
        </el-form-item>
        <el-form-item label="文本模型（合同识别）">
          <el-input v-model="ai.ai_model" placeholder="glm-4.6 / deepseek-chat / gpt-4o-mini 等" />
        </el-form-item>
        <el-form-item label="视觉模型（图片OCR）">
          <el-input v-model="ai.ai_vision_model" placeholder="glm-4.5v / gpt-4o 等（扫描件、图片用）" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="saveSettings" :icon="'Check'">保存设置</el-button>
          <el-button @click="testAi" :loading="testing" :icon="'Connection'">测试 AI 连接</el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 计算口径 -->
    <div class="panel">
      <div class="panel-title">财务计算口径</div>
      <el-form label-width="150px" size="small">
        <el-form-item label="利润收入口径">
          <el-radio-group v-model="calc.tax_mode">
            <el-radio value="excl_tax">按不含税金额计算（推荐）</el-radio>
            <el-radio value="incl_tax">按含税金额计算</el-radio>
          </el-radio-group>
          <div class="muted" style="font-size:12px;">修改后所有项目的利润、利润率立即按新口径重新计算。</div>
        </el-form-item>
        <el-form-item label="质保金提前提醒">
          <el-input v-model="calc.reminder_days" style="width:220px" placeholder="30,7,0" />
          <span class="muted" style="font-size:12px; margin-left:8px;">逗号分隔的提前天数（30,7,0 = 提前30天、7天、到期当天各提醒一次）</span>
        </el-form-item>
        <el-form-item label="续签提醒(天)">
          <el-input-number v-model="calc.renewal_remind_days" :min="1" :max="365" :controls="false" style="width:120px" />
          <span class="muted" style="font-size:12px; margin-left:8px;">合同到期前N天弹窗提醒续签（默认30天）</span>
        </el-form-item>
        <el-form-item label="结算提醒(天)">
          <el-input-number v-model="calc.settlement_remind_days" :min="1" :max="365" :controls="false" style="width:120px" />
          <span class="muted" style="font-size:12px; margin-left:8px;">付款节点预计结算日前N天弹窗提醒（默认7天），逾期始终提醒</span>
        </el-form-item>
        <el-form-item label="开票未回款预警(天)">
          <el-input-number v-model="calc.invoice_overdue_days" :min="1" :controls="false" style="width:120px" />
          <span class="muted" style="font-size:12px; margin-left:8px;">已开票超过该天数仍未足额回款时预警</span>
        </el-form-item>
        <el-form-item label="利润率预警阈值(%)">
          <el-input-number v-model="calc.margin_alert_ratio" :min="0" :max="100" :controls="false" style="width:120px" />
          <span class="muted" style="font-size:12px; margin-left:8px;">0 = 仅在亏损时预警；如设 10，则利润率低于10%预警</span>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="saveSettings" :icon="'Check'">保存设置</el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 数据管理 -->
    <div class="panel">
      <div class="panel-title">数据导入导出 <span class="right">全部数据保存在本机 backend/data 目录</span></div>
      <el-form label-width="150px" size="small">
        <el-form-item label="数据年度">
          <el-select v-model="reportYear" style="width:130px" clearable placeholder="全部年度">
            <el-option v-for="y in years" :key="y" :label="y + '年'" :value="y" />
          </el-select>
        </el-form-item>
        <el-form-item label="导出">
          <el-button :icon="'Download'" @click="exportXlsx">项目总览 Excel</el-button>
          <el-button :icon="'Download'" @click="exportDetail">完整明细 Excel</el-button>
          <el-button :icon="'Download'" @click="exportCsv">CSV</el-button>
        </el-form-item>
        <el-form-item label="年度报告">
          <el-button type="primary" plain :icon="'Document'" @click="openReport">生成年度经营分析报告 (PDF)</el-button>
        </el-form-item>
        <el-form-item label="Excel 导入">
          <el-button :icon="'Upload'" @click="downloadTemplate">下载导入模板</el-button>
          <el-button type="primary" plain :icon="'Upload'" :loading="importing" @click="importInput.click()">导入项目</el-button>
          <input ref="importInput" type="file" accept=".xlsx,.xlsm" style="display:none" @change="doImport" />
        </el-form-item>
      </el-form>
      <el-divider />
      <el-form label-width="150px" size="small">
        <el-form-item label="示例 / 清空">
          <el-button :icon="'MagicStick'" @click="loadDemo">载入示例数据</el-button>
          <el-button type="danger" plain :icon="'Delete'" @click="resetAll">清空全部数据</el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 使用说明 -->
    <div class="panel">
      <div class="panel-title">推荐使用流程</div>
      <el-steps :active="9" align-center style="margin-top:6px;">
        <el-step title="新建项目" description="手动填写或拖入合同" />
        <el-step title="AI 识别" description="自动提取关键信息" />
        <el-step title="人工确认" description="逐项核对后写入" />
        <el-step title="记回款" description="每笔到账 30 秒录完" />
        <el-step title="自动分析" description="利润/回收/质保金提醒" />
        <el-step title="年度报告" description="一键生成 PDF" />
      </el-steps>
    </div>
  </div>
</template>
