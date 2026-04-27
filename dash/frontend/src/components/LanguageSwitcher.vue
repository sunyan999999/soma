<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { locale, t } = useI18n()

const tooltip = computed(() => locale.value === 'zh' ? t('lang.switchToEn') : t('lang.switchToZh'))
const label = computed(() => locale.value === 'zh' ? t('lang.zh') : t('lang.en'))

function toggle() {
  locale.value = locale.value === 'zh' ? 'en' : 'zh'
}
</script>

<template>
  <button
    class="lang-switcher"
    :title="tooltip"
    @click="toggle"
  >
    <span class="lang-icon">{{ locale === 'zh' ? '🌐' : '🌏' }}</span>
    <span class="lang-label">{{ label }}</span>
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
