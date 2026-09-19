<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { loadCompanies, refreshReminderTotal, setCompanyId, store } from './store'
import ReminderOverlay from './components/ReminderOverlay.vue'

const route = useRoute()
const router = useRouter()
const active = computed(() => route.path)
const overlay = ref(null)

const viewKey = computed(() => route.fullPath + '#' + store.companyId)

onMounted(async () => {
  await loadCompanies()
  // 每次打开 Web 界面自动检查待办：有提醒则弹出全屏提醒中心
  const res = await refreshReminderTotal()
  if (res && res.total > 0) overlay.value?.open()
})

async function onCompanyChange(id) {
  setCompanyId(id)
  await refreshReminderTotal()
}
function openReminders() {
  overlay.value?.open()
}
</script>

<template>
  <el-container class="layout">
    <el-aside width="208px">
      <div class="logo">
        <el-icon :size="22"><Coin /></el-icon>
        <div>
          项目财务与合同管理系统
          <span class="sub">本地版 · 数据保存在本机</span>
        </div>
      </div>
      <el-menu class="side-menu" :default-active="active" router>
        <el-menu-item index="/">
          <el-icon><DataBoard /></el-icon><span>经营看板</span>
        </el-menu-item>
        <el-menu-item index="/projects">
          <el-icon><Folder /></el-icon><span>项目管理</span>
        </el-menu-item>
        <el-menu-item index="/projects/new">
          <el-icon><CirclePlus /></el-icon><span>新建项目</span>
        </el-menu-item>
        <el-menu-item index="/settings">
          <el-icon><Setting /></el-icon><span>系统设置</span>
        </el-menu-item>
      </el-menu>
      <div class="side-foot">v1.1<br />AI 负责识别 · 程序负责计算<br />用户负责确认</div>
    </el-aside>
    <el-container>
      <el-header class="page-header" height="56px">
        <h2>{{ route.meta.title || '' }}</h2>
        <div class="header-right">
          <!-- 公司切换（手动，醒目） -->
          <el-select v-model="store.companyId" class="company-switch" @change="onCompanyChange"
            placeholder="选择公司">
            <template #prefix>
              <el-icon color="#1f4e79"><OfficeBuilding /></el-icon>
            </template>
            <el-option :value="0" label="全部公司" />
            <el-option v-for="c in store.companies" :key="c.id" :value="c.id"
              :label="`${c.name}（${c.project_count}）`" />
          </el-select>
          <!-- 提醒铃铛 -->
          <el-badge :value="store.reminderTotal" :hidden="!store.reminderTotal" :max="99">
            <el-button circle :icon="'Bell'" @click="openReminders" title="待办提醒中心" />
          </el-badge>
          <div class="muted" style="font-size: 12.5px;">
            <el-icon style="vertical-align:-3px"><Lock /></el-icon>
            本地运行 · 127.0.0.1
          </div>
        </div>
      </el-header>
      <el-main class="main-content">
        <router-view :key="viewKey" />
      </el-main>
    </el-container>

    <ReminderOverlay ref="overlay" />
  </el-container>
</template>
