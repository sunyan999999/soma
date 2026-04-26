import { createRouter, createWebHistory } from 'vue-router'
import ChatView from '../views/ChatView.vue'
import MemoryView from '../views/MemoryView.vue'
import FrameworkView from '../views/FrameworkView.vue'
import SettingsView from '../views/SettingsView.vue'
import AnalyticsView from '../views/AnalyticsView.vue'
import BenchmarkView from '../views/BenchmarkView.vue'

const routes = [
  { path: '/', name: 'Chat', component: ChatView },
  { path: '/memory', name: 'Memory', component: MemoryView },
  { path: '/framework', name: 'Framework', component: FrameworkView },
  { path: '/settings', name: 'Settings', component: SettingsView },
  { path: '/analytics', name: 'Analytics', component: AnalyticsView },
  { path: '/benchmarks', name: 'Benchmarks', component: BenchmarkView },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
