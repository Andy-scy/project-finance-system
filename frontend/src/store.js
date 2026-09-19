// 全局公司切换状态（多公司支持）
import { reactive } from 'vue'
import { api } from './api'

function readId() {
  const v = parseInt(localStorage.getItem('pfs_company_id') || '0', 10)
  return isNaN(v) ? 0 : v
}

export const store = reactive({
  companyId: readId(),   // 0 = 全部公司
  companies: [],         // [{id, name, project_count}]
  companiesLoaded: false,
  reminderTotal: 0,      // 提醒中心待办总数（铃铛角标）
})

export function setCompanyId(id) {
  store.companyId = Number(id) || 0
  localStorage.setItem('pfs_company_id', String(store.companyId))
}

export async function loadCompanies(force = false) {
  if (store.companiesLoaded && !force) return store.companies
  try {
    const res = await api.get('/companies')
    store.companies = res.items || []
    store.companiesLoaded = true
    // 当前选中的公司若已被删除，回退到「全部公司」
    if (store.companyId && !store.companies.some((c) => c.id === store.companyId)) {
      setCompanyId(0)
    }
  } catch { /* 后端未升级等场景静默降级 */ }
  return store.companies
}

export function companyName(id = store.companyId) {
  if (!id) return '全部公司'
  const c = store.companies.find((x) => x.id === id)
  return c ? c.name : '全部公司'
}

export async function refreshReminderTotal() {
  try {
    const res = await api.get('/reminders?company_id=' + store.companyId)
    store.reminderTotal = res.total || 0
    return res
  } catch {
    store.reminderTotal = 0
    return null
  }
}
