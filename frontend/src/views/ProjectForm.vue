<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api, todayIso } from '../api'
import { loadCompanies, store } from '../store'

const router = useRouter()
const meta = ref({ statuses: [], project_types: [], schedule_names: [] })

const form = reactive({
  company_id: store.companyId || null,
  name: '', code: '', customer_name: '', owner: '', project_type: '', status: '进行中',
  start_date: null, end_date: null,
  contract_no: '', total_amount: null, tax_rate: null, sign_date: null, contract_end_date: null, payment_terms: '',
  warranty_months: null, warranty_ratio: null, warranty_amount: null,
})
const schedules = ref([])

function addSchedule() {
  schedules.value.push({ name: '', ratio: null, amount: null, expected_date: null, is_warranty: false })
}
function removeSchedule(i) { schedules.value.splice(i, 1) }
function fillFromRatio(row) {
  if (row.ratio != null && form.total_amount != null) {
    row.amount = Math.round(form.total_amount * row.ratio) / 100
  }
}

const saving = ref(false)
async function save() {
  if (!form.name.trim()) { ElMessage.warning('项目名称必填，其他字段可以先留空。'); return }
  saving.value = true
  try {
    const body = {
      company_id: form.company_id || null,
      name: form.name, code: form.code || null, customer_name: form.customer_name || null,
      owner: form.owner || null, project_type: form.project_type || null, status: form.status,
      start_date: form.start_date, end_date: form.end_date,
      contract: {},
      schedules: schedules.value
        .filter((s) => s.name || s.amount || s.ratio)
        .map((s) => ({ name: s.name || '付款节点', ratio: s.ratio, amount: s.amount, expected_date: s.expected_date, is_warranty: s.is_warranty })),
    }
    if (form.contract_no) body.contract.contract_no = form.contract_no
    if (form.total_amount != null) body.contract.total_amount = form.total_amount
    if (form.tax_rate != null) body.contract.tax_rate = form.tax_rate
    if (form.sign_date) body.contract.sign_date = form.sign_date
    if (form.contract_end_date) body.contract.contract_end_date = form.contract_end_date
    if (form.payment_terms) body.contract.payment_terms = form.payment_terms
    if (form.warranty_months != null) body.contract.warranty_months = form.warranty_months
    if (form.warranty_ratio != null) body.contract.warranty_ratio = form.warranty_ratio
    if (form.warranty_amount != null) body.contract.warranty_amount = form.warranty_amount
    if (Object.keys(body.contract).length === 0) delete body.contract
    const res = await api.post('/projects', body)
    ElMessage.success('项目已创建')
    router.push('/projects/' + res.id)
  } catch (e) {
    ElMessage.error(String(e.message || e))
  } finally {
    saving.value = false
  }
}

// ── 拖入合同 → AI 识别 ────────────────────────────────────────
const dragOver = ref(false)
const uploading = ref(false)
const fileInput = ref(null)

async function handleFiles(fileList) {
  const file = fileList && fileList[0]
  if (!file) return
  uploading.value = true
  ElMessage.info('正在上传并调用 AI 识别，请稍候…')
  try {
    const fd = new FormData()
    fd.append('file', file)
    const res = await api.upload('/extractions/upload', fd)
    if (res.ok) {
      ElMessage.success('识别完成，请核对结果')
      router.push('/extract/' + res.record_id)
    } else {
      ElMessage.error(res.error || '识别失败')
    }
  } catch (e) {
    ElMessage.error(String(e.message || e))
  } finally {
    uploading.value = false
  }
}
function onDrop(e) {
  dragOver.value = false
  handleFiles(e.dataTransfer?.files)
}
function onPick() { fileInput.value?.click() }

import { onMounted } from 'vue'
onMounted(async () => {
  try { meta.value = await api.get('/projects/meta') } catch { /* ignore */ }
})
</script>

<template>
  <div style="display:grid; grid-template-columns: 1.5fr 1fr; gap:16px; align-items:start;">
    <!-- 手动录入 -->
    <div class="panel">
      <div class="panel-title">手动录入项目 <span class="right">只填项目名称即可保存，其余字段随时补充</span></div>
      <el-form label-width="110px" label-position="right">
        <el-divider content-position="left">基础信息</el-divider>
        <el-form-item label="所属公司">
          <el-select v-model="form.company_id" style="width:100%" placeholder="选择公司">
            <el-option v-for="c in store.companies" :key="c.id" :value="c.id"
              :label="`${c.name}（${c.project_count}个项目）`" />
          </el-select>
        </el-form-item>
        <el-form-item label="项目名称" required>
          <el-input v-model="form.name" placeholder="必填" />
        </el-form-item>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:0 16px;">
          <el-form-item label="项目编号"><el-input v-model="form.code" /></el-form-item>
          <el-form-item label="客户名称"><el-input v-model="form.customer_name" /></el-form-item>
          <el-form-item label="项目负责人"><el-input v-model="form.owner" /></el-form-item>
          <el-form-item label="项目类型">
            <el-select v-model="form.project_type" filterable allow-create placeholder="选择或输入" style="width:100%">
              <el-option v-for="t in meta.project_types" :key="t" :label="t" :value="t" />
            </el-select>
          </el-form-item>
          <el-form-item label="项目状态">
            <el-select v-model="form.status" style="width:100%">
              <el-option v-for="s in meta.statuses" :key="s" :label="s" :value="s" />
            </el-select>
          </el-form-item>
          <el-form-item label="开始日期"><el-date-picker v-model="form.start_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item>
          <el-form-item label="结束日期"><el-date-picker v-model="form.end_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item>
        </div>

        <el-divider content-position="left">合同信息（可选）</el-divider>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:0 16px;">
          <el-form-item label="合同编号"><el-input v-model="form.contract_no" /></el-form-item>
          <el-form-item label="合同签订日期"><el-date-picker v-model="form.sign_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item>
          <el-form-item label="合同到期日">
            <el-date-picker v-model="form.contract_end_date" type="date" value-format="YYYY-MM-DD" style="width:100%" placeholder="用于续签提醒" />
          </el-form-item>
          <el-form-item label="合同总金额">
            <el-input-number v-model="form.total_amount" :min="0" :precision="2" :controls="false" style="width:100%" placeholder="元" />
          </el-form-item>
          <el-form-item label="税率(%)">
            <el-input-number v-model="form.tax_rate" :min="0" :max="100" :precision="2" :controls="false" style="width:100%" placeholder="如 13" />
          </el-form-item>
          <el-form-item label="质保期(月)"><el-input-number v-model="form.warranty_months" :min="0" :controls="false" style="width:100%" /></el-form-item>
          <el-form-item label="质保金比例(%)"><el-input-number v-model="form.warranty_ratio" :min="0" :max="100" :precision="2" :controls="false" style="width:100%" /></el-form-item>
        </div>
        <el-form-item label="付款条款">
          <el-input v-model="form.payment_terms" type="textarea" :rows="2" placeholder="例如：合同签订后付30%，中期付40%，验收后付20%，质保金10%一年后支付" />
        </el-form-item>

        <el-divider content-position="left">付款节点（可选，可稍后在项目详情中维护）</el-divider>
        <el-table :data="schedules" size="small" style="margin-bottom:8px;">
          <el-table-column label="节点名称" width="130">
            <template #default="{ row }">
              <el-select v-model="row.name" filterable allow-create placeholder="选择/输入">
                <el-option v-for="n in meta.schedule_names" :key="n" :label="n" :value="n" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="比例(%)" width="110">
            <template #default="{ row }"><el-input-number v-model="row.ratio" :controls="false" :precision="2" style="width:100%" @change="fillFromRatio(row)" /></template>
          </el-table-column>
          <el-table-column label="金额(元)" width="140">
            <template #default="{ row }"><el-input-number v-model="row.amount" :controls="false" :precision="2" style="width:100%" /></template>
          </el-table-column>
          <el-table-column label="预计到账" width="150">
            <template #default="{ row }"><el-date-picker v-model="row.expected_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></template>
          </el-table-column>
          <el-table-column label="质保金" width="70" align="center">
            <template #default="{ row }"><el-checkbox v-model="row.is_warranty" /></template>
          </el-table-column>
          <el-table-column label="" width="60" align="center">
            <template #default="{ $index }"><el-button link type="danger" @click="removeSchedule($index)">删除</el-button></template>
          </el-table-column>
        </el-table>
        <el-button size="small" :icon="'Plus'" @click="addSchedule">添加付款节点</el-button>

        <div style="margin-top:18px; display:flex; gap:10px;">
          <el-button type="primary" :loading="saving" @click="save" :icon="'Check'">保存项目</el-button>
          <el-button @click="router.back()">取消</el-button>
        </div>
      </el-form>
    </div>

    <!-- AI 识别 -->
    <div class="panel">
      <div class="panel-title">拖入合同，AI 自动识别 <span class="right">推荐</span></div>
      <div class="dropzone" :class="{ dragover: dragOver }" @dragover.prevent="dragOver = true"
        @dragleave="dragOver = false" @drop.prevent="onDrop" @click="onPick" v-loading="uploading"
        element-loading-text="AI 识别中，约需 10~60 秒…">
        <el-icon :size="42" style="color:#7a9cbf"><UploadFilled /></el-icon>
        <div style="margin-top:10px; font-weight:600;">把合同文件拖到这里</div>
        <div style="margin-top:6px; font-size:12px;">或点击选择文件（PDF / Word / 图片 / 扫描件 / 文本，≤50MB）</div>
        <input ref="fileInput" type="file" accept=".pdf,.docx,.doc,.png,.jpg,.jpeg,.bmp,.webp,.txt,.md,.csv"
          style="display:none" @change="handleFiles($event.target.files)" />
      </div>
      <el-alert type="info" :closable="false" style="margin-top:14px;">
        <template #title>识别流程</template>
        <div style="font-size:12px; line-height:1.9;">
          ① 上传合同 → ② AI 提取金额、税率、付款节点、质保金等 →
          ③ 进入<b>「识别结果确认页」</b>逐项核对（AI 不会编造：识别不到的会标「未识别 / 需人工确认」）→
          ④ 确认后自动建立项目档案。
        </div>
      </el-alert>
      <el-alert type="warning" :closable="false" style="margin-top:10px;">
        <template #title>首次使用请先配置 AI</template>
        <div style="font-size:12px;">
          到「系统设置」填写 AI API（支持智谱 GLM / OpenAI / DeepSeek 等 OpenAI 兼容接口），可一键测试连通性。
          未配置时仍可手动录入全部数据。
        </div>
      </el-alert>
    </div>
  </div>
</template>
