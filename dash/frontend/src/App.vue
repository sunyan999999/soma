<script setup>
import { ref, provide, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import LanguageSwitcher from './components/LanguageSwitcher.vue'
import { api, initAuth } from './api/index.js'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()

const somaVersion = ref('...')
const communityStats = ref(null)

onMounted(async () => {
  // 先初始化认证：检查是否需要 API Key 并提示用户输入
  await initAuth()
  try {
    const h = await api.health()
    somaVersion.value = h.version || 'unknown'
  } catch {
    somaVersion.value = 'unknown'
  }
  try {
    communityStats.value = await api.community()
  } catch {
    communityStats.value = null
  }
})

const toasts = ref([])
let toastId = 0

function addToast(message, type = 'info') {
  const id = ++toastId
  toasts.value.push({ id, message, type })
  setTimeout(() => {
    toasts.value = toasts.value.filter(t => t.id !== id)
  }, 3500)
}

provide('toast', addToast)

function formatDownloads(n) {
  if (!n && n !== 0) return '...'
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return n.toLocaleString()
}

const navItems = computed(() => [
  { path: '/', icon: '💬', label: t('nav.chat') },
  { path: '/reports', icon: '📋', label: t('nav.reports') },
  { path: '/benchmarks', icon: '📐', label: t('nav.benchmarks') },
  { path: '/analytics', icon: '📊', label: t('nav.analytics') },
  { path: '/memory', icon: '📚', label: t('nav.memory') },
  { path: '/framework', icon: '⚖️', label: t('nav.framework') },
  { path: '/settings', icon: '⚙️', label: t('nav.settings') },
])
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="sidebar-logo">SOMA</div>
      <LanguageSwitcher />
      <nav style="display:flex;flex-direction:column;gap:4px;">
        <button
          v-for="item in navItems"
          :key="item.path"
          class="nav-link"
          :class="{ active: route.path === item.path }"
          @click="router.push(item.path)"
        >
          <span class="nav-icon">{{ item.icon }}</span>
          {{ item.label }}
        </button>
      </nav>
      <!-- 社区统计 -->
      <div v-if="communityStats?.github || communityStats?.pypi" class="sidebar-stats">
        <div class="stats-title">📡 Community</div>
        <!-- GitHub 基础数据 -->
        <template v-if="communityStats?.github">
          <div class="stat-row">
            <span class="stat-icon">⭐</span>
            <span class="stat-val">{{ communityStats.github.stars?.toLocaleString() || '...' }}</span>
            <span class="stat-label">Stars</span>
          </div>
          <div class="stat-row">
            <span class="stat-icon">🔀</span>
            <span class="stat-val">{{ communityStats.github.forks?.toLocaleString() || '...' }}</span>
            <span class="stat-label">Forks</span>
          </div>
          <div class="stat-row">
            <span class="stat-icon">👁️</span>
            <span class="stat-val">{{ communityStats.github.watchers?.toLocaleString() || '...' }}</span>
            <span class="stat-label">Watchers</span>
          </div>
          <!-- Traffic 需要 SOMA_GITHUB_TOKEN，无 Token 时不显示 -->
          <template v-if="communityStats.github.clones_count !== undefined">
            <div class="stats-title" style="margin-top:12px;">📈 Traffic (14d)</div>
            <div class="stat-row">
              <span class="stat-icon">📥</span>
              <span class="stat-val">{{ formatDownloads(communityStats.github.clones_count) }}</span>
              <span class="stat-label">Clones</span>
            </div>
            <div class="stat-row">
              <span class="stat-icon">🔄</span>
              <span class="stat-val">{{ formatDownloads(communityStats.github.clones_uniques) }}</span>
              <span class="stat-label">Unique cloners</span>
            </div>
            <div class="stat-row">
              <span class="stat-icon">👀</span>
              <span class="stat-val">{{ formatDownloads(communityStats.github.views_count) }}</span>
              <span class="stat-label">Visitors</span>
            </div>
            <div class="stat-row">
              <span class="stat-icon">🆕</span>
              <span class="stat-val">{{ formatDownloads(communityStats.github.views_uniques) }}</span>
              <span class="stat-label">Unique visitors</span>
            </div>
          </template>
        </template>
        <!-- PyPI -->
        <template v-if="communityStats?.pypi">
          <div class="stat-row">
            <span class="stat-icon">📦</span>
            <span class="stat-val">{{ formatDownloads(communityStats.pypi.total_downloads) }}</span>
            <span class="stat-label">PyPI Downloads</span>
          </div>
        </template>
      </div>
      <div style="margin-top:auto;padding:16px;color:var(--text-muted);font-size:0.75rem;">
        v{{ somaVersion }}
      </div>
    </aside>

    <main class="main-content">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>

    <div class="toast-container">
      <div
        v-for="t in toasts"
        :key="t.id"
        class="toast"
        :class="`toast-${t.type}`"
      >
        {{ t.message }}
      </div>
    </div>
  </div>
</template>
