<script setup>
import { ref, provide } from 'vue'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()

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

const navItems = [
  { path: '/', icon: '💬', label: 'Chat' },
  { path: '/benchmarks', icon: '📐', label: 'Benchmarks' },
  { path: '/analytics', icon: '📊', label: 'Analytics' },
  { path: '/memory', icon: '📚', label: 'Memory' },
  { path: '/framework', icon: '⚖️', label: 'Framework' },
  { path: '/settings', icon: '⚙️', label: 'Settings' },
]
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="sidebar-logo">SOMA</div>
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
      <div style="margin-top:auto;padding:16px;color:var(--text-muted);font-size:0.75rem;">
        v0.2.0-alpha
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
