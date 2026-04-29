import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'Chat', component: () => import('../views/ChatView.vue') },
  { path: '/memory', name: 'Memory', component: () => import('../views/MemoryView.vue') },
  { path: '/framework', name: 'Framework', component: () => import('../views/FrameworkView.vue') },
  { path: '/settings', name: 'Settings', component: () => import('../views/SettingsView.vue') },
  { path: '/analytics', name: 'Analytics', component: () => import('../views/AnalyticsView.vue') },
  { path: '/benchmarks', name: 'Benchmarks', component: () => import('../views/BenchmarkView.vue') },
  { path: '/reports', name: 'TestReports', component: () => import('../views/TestReportsView.vue') },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
