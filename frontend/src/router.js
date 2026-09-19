import { createRouter, createWebHashHistory } from 'vue-router'
import Dashboard from './views/Dashboard.vue'
import Projects from './views/Projects.vue'
import ProjectForm from './views/ProjectForm.vue'
import ProjectDetail from './views/ProjectDetail.vue'
import ExtractionConfirm from './views/ExtractionConfirm.vue'
import Settings from './views/Settings.vue'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: Dashboard, meta: { title: '经营看板' } },
    { path: '/projects', name: 'projects', component: Projects, meta: { title: '项目管理' } },
    { path: '/projects/new', name: 'project-new', component: ProjectForm, meta: { title: '新建项目' } },
    { path: '/projects/:id', name: 'project-detail', component: ProjectDetail, meta: { title: '项目详情' } },
    { path: '/extract/:id', name: 'extract-confirm', component: ExtractionConfirm, meta: { title: 'AI识别确认' } },
    { path: '/settings', name: 'settings', component: Settings, meta: { title: '系统设置' } },
  ],
})

router.afterEach((to) => {
  document.title = (to.meta.title ? to.meta.title + ' · ' : '') + '项目财务与合同管理分析系统'
})

export default router
