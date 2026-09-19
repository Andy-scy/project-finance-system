<script setup>
// 全屏提醒中心：合同续签 / 工程款结算 / 质保金到期
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { store, refreshReminderTotal } from '../store'

const router = useRouter()
const visible = defineModel({ type: Boolean, default: false })
const data = ref(null)
const loading = ref(false)

async function open() {
  visible.value = true
  loading.value = true
  data.value = await refreshReminderTotal()
  loading.value = false
}
defineExpose({ open })

function goProject(item) {
  visible.value = false
  router.push('/projects/' + item.project_id)
}

const SECTIONS = [
  { key: 'renewals', icon: '📄', color: '#c0392b', title: '合同续签提醒', desc: '到期未续签 / 即将到期' },
  { key: 'settlements', icon: '💰', color: '#b9770e', title: '工程款结算提醒', desc: '逾期未收 / 即将到结算日' },
  { key: 'warranties', icon: '🛡️', color: '#1e8449', title: '质保金到期提醒', desc: '已到期未到账 / 即将到账' },
]
</script>

<template>
  <el-dialog v-model="visible" width="720px" top="6vh" class="reminder-dialog"
    :show-close="false" align-center>
    <template #header>
      <div style="display:flex; align-items:center; gap:10px;">
        <el-icon :size="24" color="#c0392b"><Bell /></el-icon>
        <div>
          <div style="font-size:18px; font-weight:700;">待办提醒中心</div>
          <div class="muted" style="font-size:12px;">
            共 <b class="danger-text">{{ data?.total ?? 0 }}</b> 项需要关注 · 每次打开系统自动检查
          </div>
        </div>
      </div>
    </template>

    <div v-loading="loading" style="min-height:120px; max-height:62vh; overflow-y:auto;">
      <template v-if="data">
        <div v-for="sec in SECTIONS" :key="sec.key">
          <template v-if="(data[sec.key] || []).length">
            <div class="reminder-sec-title" :style="{ borderColor: sec.color }">
              <span style="font-size:16px;">{{ sec.icon }}</span>
              <b>{{ sec.title }}</b>
              <el-tag size="small" :type="sec.key === 'renewals' ? 'danger' : 'warning'" effect="dark" round>
                {{ data[sec.key].length }}
              </el-tag>
              <span class="muted" style="font-size:11.5px; margin-left:4px;">{{ sec.desc }}</span>
            </div>
            <div v-for="(item, i) in data[sec.key]" :key="sec.key + i" class="reminder-item"
              :class="'lv-' + item.level" @click="goProject(item)">
              <div style="display:flex; align-items:center; gap:8px;">
                <el-tag size="small" :type="item.level === 'danger' ? 'danger' : 'warning'" effect="dark">
                  {{ item.level === 'danger' ? '紧急' : '预警' }}
                </el-tag>
                <b style="font-size:13.5px;">{{ item.project_name }}</b>
                <span style="font-size:13px;">— {{ item.title }}</span>
              </div>
              <div class="muted" style="font-size:12.5px; margin-top:4px;">{{ item.detail }}</div>
            </div>
          </template>
        </div>
        <el-empty v-if="data.total === 0" description="当前没有待办提醒，一切正常 ✓" :image-size="80" />
      </template>
    </div>

    <template #footer>
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <span class="muted" style="font-size:12px;">点击任意条目可直接进入项目处理</span>
        <el-button type="primary" size="large" @click="visible = false">我知道了</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<style>
.reminder-dialog .el-dialog__header { border-bottom: 2px solid #1f4e79; margin-right: 0; padding-bottom: 12px; }
.reminder-sec-title {
  display: flex; align-items: center; gap: 8px;
  border-left: 4px solid; padding: 6px 10px; margin: 14px 0 8px;
  background: #f5f8fb; border-radius: 4px; font-size: 14px;
}
.reminder-item {
  border: 1px solid #e8ecf2; border-radius: 6px;
  padding: 10px 12px; margin-bottom: 8px; cursor: pointer;
  transition: all .15s;
}
.reminder-item:hover { border-color: #1f4e79; background: #f7fafd; transform: translateX(2px); }
.reminder-item.lv-danger { border-left: 4px solid #e2564a; }
.reminder-item.lv-warning { border-left: 4px solid #e6a23c; }
</style>
