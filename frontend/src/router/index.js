import { createRouter, createWebHistory } from 'vue-router'
import { AUTH_ENABLED } from '@/config/app'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { guest: true, title: '登录' },
  },
  {
    path: '/',
    component: () => import('@/views/Layout.vue'),
    children: [
      { path: '', name: 'Home', component: () => import('@/views/Dashboard.vue'), meta: { title: '首页' } },
      { path: 'research-data', name: 'ResearchData', component: () => import('@/views/ResearchData.vue'), meta: { title: '研究数据' } },
      { path: 'parks', name: 'Parks', component: () => import('@/views/Parks.vue'), meta: { title: '遗址公园' } },
      { path: 'parks/:id', name: 'ParkDetail', component: () => import('@/views/ParkDetail.vue'), meta: { title: '公园详情' } },
      { path: 'map', name: 'Map', component: () => import('@/views/MapView.vue'), meta: { title: '地图浏览', flush: true, hideFooter: true } },
      { path: 'compare', name: 'Comparison', component: () => import('@/views/Comparison.vue'), meta: { title: '对比分析' } },
      { path: 'comparison', redirect: '/compare' },
      { path: 'knowledge-graph', name: 'KnowledgeGraph', component: () => import('@/views/KnowledgeGraph.vue'), meta: { title: '知识图谱', wide: true } },
      { path: 'assistant', name: 'Assistant', component: () => import('@/views/Chat.vue'), meta: { title: 'AI助手', wide: true, hideFooter: true } },
      { path: 'chat', redirect: '/assistant' },
      { path: 'library', name: 'Library', component: () => import('@/views/KnowledgeBase.vue'), meta: { title: '知识库' } },
      { path: 'knowledge-base', redirect: '/library' },
      { path: 'bibliometrics', name: 'Bibliometrics', component: () => import('@/views/Bibliometrics.vue'), meta: { title: '文献计量' } },
      { path: 'about', name: 'About', component: () => import('@/views/About.vue'), meta: { title: '关于我们' } },
      { path: 'data-management', name: 'DataManagement', component: () => import('@/views/admin/DataManage.vue'), meta: { title: '数据管理', admin: true } },
      { path: 'admin', redirect: '/data-management' },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({ history: createWebHistory(), routes, scrollBehavior: () => ({ top: 0 }) })

router.beforeEach((to) => {
  document.title = `${to.meta.title || '研究平台'} - 遗址公园研究平台`
  if (!AUTH_ENABLED) return true
  if (to.meta.guest) return true
  if (to.meta.admin && !localStorage.getItem('token')) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  return true
})

export default router
