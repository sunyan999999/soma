<script setup>
import { useI18n } from 'vue-i18n'

const { locale } = useI18n()

function toggle() {
  locale.value = locale.value === 'zh' ? 'en' : 'zh'
}
</script>

<template>
  <button
    class="lang-switcher"
    :title="locale === 'zh' ? 'Switch to English' : '切换到中文'"
    @click="toggle"
  >
    <span class="lang-icon">{{ locale === 'zh' ? '🌐' : '🌏' }}</span>
    <span class="lang-label">{{ locale === 'zh' ? '中' : 'EN' }}</span>
  </button>
</template>

<style scoped>
.lang-switcher {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 5px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg-card);
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 0.75rem;
  font-weight: 600;
  transition: all var(--transition);
  margin: 0 12px 8px;
}
.lang-switcher:hover {
  border-color: var(--accent);
  color: var(--text-primary);
  background: var(--bg-card-hover);
}
.lang-icon {
  font-size: 0.85rem;
}
.lang-label {
  min-width: 18px;
  text-align: center;
}
</style>
