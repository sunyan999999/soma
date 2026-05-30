<script setup>
import { ref, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api/index.js'

const { t } = useI18n()
const loading = ref(true)
const error = ref('')
const status = ref(null)

async function loadStatus() {
  loading.value = true
  error.value = ''
  try {
    status.value = await api.zhongdaoStatus()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function resetSession() {
  try {
    await api.zhongdaoReset()
    status.value.session_usage = {}
    status.value.total_samples = 0
    status.value.last_corrections = []
  } catch (e) {
    error.value = e.message
  }
}

const usageBars = computed(() => {
  if (!status.value?.session_usage) return []
  const usage = status.value.session_usage
  const total = status.value.total_samples || 1
  return Object.entries(usage)
    .map(([id, count]) => ({
      id,
      name: t(`laws.${id}`) || id,
      count,
      ratio: count / total,
    }))
    .sort((a, b) => b.count - a.count)
})

const correctionTypes = computed(() => ({
  overuse_penalty: t('zhongdao.overusePenalty'),
  neglect_boost: t('zhongdao.neglectBoost'),
}))

onMounted(loadStatus)
</script>

<template>
  <div class="zhongdao-view">
    <div class="page-header">
      <h2>{{ t('zhongdao.title') }}</h2>
      <p class="subtitle">{{ t('zhongdao.subtitle') }}</p>
      <div class="header-actions">
        <button class="btn btn-sm" @click="loadStatus">{{ t('common.refresh') }}</button>
        <button class="btn btn-sm btn-warn" @click="resetSession">{{ t('zhongdao.resetSession') }}</button>
      </div>
    </div>

    <div v-if="loading" class="state-msg">⏳ {{ t('common.loading') }}</div>
    <div v-else-if="error" class="state-msg error">❌ {{ error }}</div>
    <div v-else-if="!status?.enabled" class="state-msg">
      <p>⚙️ {{ t('zhongdao.notEnabled') }}</p>
      <p class="hint">{{ t('zhongdao.notEnabledHint') }}</p>
    </div>

    <template v-else>
      <!-- 配置参数 -->
      <section class="card">
        <h3>{{ t('zhongdao.configTitle') }}</h3>
        <div class="config-grid">
          <div class="config-item">
            <span class="config-label">{{ t('zhongdao.thresholdRatio') }}</span>
            <span class="config-value">{{ (status.config.threshold_ratio * 100).toFixed(0) }}%</span>
          </div>
          <div class="config-item">
            <span class="config-label">{{ t('zhongdao.penaltyFactor') }}</span>
            <span class="config-value">{{ (status.config.penalty_factor * 100).toFixed(0) }}%</span>
          </div>
          <div class="config-item">
            <span class="config-label">{{ t('zhongdao.boostFactor') }}</span>
            <span class="config-value">{{ (status.config.boost_factor * 100).toFixed(0) }}%</span>
          </div>
          <div class="config-item">
            <span class="config-label">{{ t('zhongdao.minSamples') }}</span>
            <span class="config-value">{{ status.config.min_samples }}</span>
          </div>
        </div>
      </section>

      <!-- 规律使用分布 -->
      <section class="card">
        <h3>{{ t('zhongdao.usageTitle') }}
          <span class="badge">{{ status.total_samples }} {{ t('common.timesUnit') }}</span>
        </h3>
        <div v-if="usageBars.length === 0" class="state-msg">
          {{ t('zhongdao.noUsageYet') }}
        </div>
        <div v-else class="usage-chart">
          <div v-for="bar in usageBars" :key="bar.id" class="usage-bar-row">
            <span class="bar-name">{{ bar.name }}</span>
            <div class="bar-track">
              <div
                class="bar-fill"
                :class="{ overused: bar.ratio > status.config.threshold_ratio }"
                :style="{ width: (bar.ratio * 100) + '%' }"
              ></div>
            </div>
            <span class="bar-value">
              {{ bar.count }}/{{ status.total_samples }}
              ({{ (bar.ratio * 100).toFixed(0) }}%)
            </span>
            <span v-if="bar.ratio > status.config.threshold_ratio" class="overuse-tag">
              ⚠️ {{ t('zhongdao.overused') }}
            </span>
          </div>
        </div>
      </section>

      <!-- 最近校正记录 -->
      <section class="card">
        <h3>{{ t('zhongdao.correctionsTitle') }}
          <span class="badge">{{ status.last_corrections.length }} {{ t('common.itemsUnit') }}</span>
        </h3>
        <div v-if="status.last_corrections.length === 0" class="state-msg">
          {{ t('zhongdao.noCorrectionsYet') }}
        </div>
        <div v-else class="corrections-list">
          <div
            v-for="(c, i) in status.last_corrections"
            :key="i"
            class="correction-item"
            :class="c.type"
          >
            <span class="corr-type">{{ correctionTypes[c.type] || c.type }}</span>
            <span class="corr-law">{{ t(`laws.${c.law_id}`) || c.law_name }}</span>
            <span v-if="c.type === 'overuse_penalty'" class="corr-detail">
              {{ (c.usage_ratio * 100).toFixed(1) }}%
              {{ c.old_weight }} → {{ c.new_weight }}
            </span>
            <span v-else class="corr-detail">
              {{ t('zhongdao.weight') }}: {{ c.weight }}
            </span>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.zhongdao-view { max-width: 900px; margin: 0 auto; }
.page-header { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; margin-bottom: 24px; }
.page-header h2 { margin: 0; }
.subtitle { color: var(--text-muted); margin: 0; flex: 1; }

.card { background: var(--bg-card); border-radius: 12px; padding: 20px; margin-bottom: 20px; }
.card h3 { margin: 0 0 16px 0; font-size: 1.1rem; }
.badge { font-size: 0.8rem; color: var(--text-muted); font-weight: normal; margin-left: 8px; }

.config-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; }
.config-item { display: flex; flex-direction: column; gap: 4px; }
.config-label { font-size: 0.85rem; color: var(--text-muted); }
.config-value { font-size: 1.3rem; font-weight: 600; }

.usage-chart { display: flex; flex-direction: column; gap: 10px; }
.usage-bar-row { display: flex; align-items: center; gap: 10px; }
.bar-name { width: 100px; font-size: 0.9rem; text-align: right; flex-shrink: 0; }
.bar-track { flex: 1; height: 24px; background: var(--bg-muted); border-radius: 12px; overflow: hidden; }
.bar-fill { height: 100%; background: #4caf50; border-radius: 12px; transition: width 0.5s; min-width: 4px; }
.bar-fill.overused { background: #ff9800; }
.bar-value { font-size: 0.85rem; color: var(--text-muted); min-width: 100px; }
.overuse-tag { font-size: 0.8rem; color: #ff9800; font-weight: 600; white-space: nowrap; }

.corrections-list { display: flex; flex-direction: column; gap: 8px; }
.correction-item { display: flex; align-items: center; gap: 12px; padding: 10px 14px; border-radius: 8px; font-size: 0.9rem; }
.correction-item.overuse_penalty { background: #fff3e0; border-left: 3px solid #ff9800; }
.correction-item.neglect_boost { background: #e8f5e9; border-left: 3px solid #4caf50; }
.corr-type { font-weight: 600; min-width: 80px; }
.corr-law { font-weight: 500; }
.corr-detail { color: var(--text-muted); }

.state-msg { text-align: center; padding: 40px 20px; color: var(--text-muted); }
.state-msg.error { color: #e53935; }
.hint { font-size: 0.85rem; margin-top: 8px; }

.header-actions { display: flex; gap: 8px; }
.btn { padding: 6px 16px; border: 1px solid var(--border); border-radius: 8px; background: var(--bg-card); color: var(--text); cursor: pointer; font-size: 0.85rem; }
.btn:hover { background: var(--bg-muted); }
.btn-warn { border-color: #ff9800; color: #ff9800; }
.btn-warn:hover { background: #fff3e0; }
</style>
