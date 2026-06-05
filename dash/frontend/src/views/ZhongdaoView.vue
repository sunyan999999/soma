<script setup>
import { ref, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api/index.js'

const { t } = useI18n()
const loading = ref(true)
const error = ref('')
const status = ref(null)
const effectiveness = ref(null)
const suggestion = ref(null)
const activeDays = ref(30)

async function loadStatus() {
  loading.value = true
  error.value = ''
  try {
    const [s, e, sg] = await Promise.all([
      api.zhongdaoStatus(),
      api.zhongdaoEffectiveness(activeDays.value),
      api.zhongdaoSuggest(activeDays.value),
    ])
    status.value = s
    effectiveness.value = e
    suggestion.value = sg
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

async function doArchive() {
  if (!confirm(t('zhongdao.archiveConfirm', { days: 90 }))) return
  try {
    const res = await api.zhongdaoArchive(90)
    alert(t('zhongdao.archivedCount', { count: res.archived_count }))
    loadStatus()
  } catch (e) {
    error.value = e.message
  }
}

async function changeDays(days) {
  activeDays.value = days
  const [e, sg] = await Promise.all([
    api.zhongdaoEffectiveness(days),
    api.zhongdaoSuggest(days),
  ])
  effectiveness.value = e
  suggestion.value = sg
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

const trendBars = computed(() => {
  if (!effectiveness.value?.daily_trend) return []
  return effectiveness.value.daily_trend.slice(-14)
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
        <select v-model.number="activeDays" @change="changeDays(activeDays)" class="days-select">
          <option :value="7">7 {{ t('common.days') }}</option>
          <option :value="14">14 {{ t('common.days') }}</option>
          <option :value="30">30 {{ t('common.days') }}</option>
          <option :value="90">90 {{ t('common.days') }}</option>
        </select>
        <button class="btn btn-sm" @click="loadStatus">{{ t('common.refresh') }}</button>
        <button class="btn btn-sm btn-warn" @click="resetSession">{{ t('zhongdao.resetSession') }}</button>
        <button class="btn btn-sm btn-archive" @click="doArchive">{{ t('zhongdao.archiveOld') }}</button>
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

      <!-- v1.1.4: 自动调参建议 -->
      <section v-if="suggestion" class="card suggestion-card">
        <h3>{{ t('zhongdao.suggestTitle') }}
          <span class="badge">{{ activeDays }}{{ t('common.days') }}</span>
        </h3>
        <div class="suggest-grid">
          <div class="suggest-item">
            <span class="suggest-label">{{ t('zhongdao.current') }}</span>
            <span class="suggest-value">
              R{{ suggestion.current_params.threshold_ratio }} / P{{ suggestion.current_params.penalty_factor }} / B{{ suggestion.current_params.boost_factor }} / S{{ suggestion.current_params.min_samples }}
            </span>
          </div>
          <div class="suggest-item">
            <span class="suggest-label">{{ t('zhongdao.recommended') }}</span>
            <span class="suggest-value rec">
              R{{ suggestion.recommended_params.threshold_ratio }} / P{{ suggestion.recommended_params.penalty_factor }} / B{{ suggestion.recommended_params.boost_factor }} / S{{ suggestion.recommended_params.min_samples }}
            </span>
          </div>
        </div>
        <ul v-if="suggestion.suggestions.length" class="suggest-list">
          <li v-for="(s, i) in suggestion.suggestions" :key="i">{{ s }}</li>
        </ul>
        <p v-else class="state-msg" style="padding:10px">{{ t('zhongdao.paramsOptimal') }}</p>
      </section>

      <!-- v1.1.4: 校正趋势图 -->
      <section class="card">
        <h3>{{ t('zhongdao.trendTitle') }}
          <span class="badge">{{ effectiveness?.total_corrections || 0 }} {{ t('common.timesUnit') }}</span>
        </h3>
        <div v-if="trendBars.length === 0" class="state-msg">
          {{ t('zhongdao.noCorrectionsYet') }}
        </div>
        <div v-else class="trend-chart">
          <div v-for="d in trendBars" :key="d.day" class="trend-bar-col">
            <div class="trend-bar" :style="{ height: Math.max(4, d.count * 16) + 'px' }"
              :title="d.day + ': ' + d.count"></div>
            <span class="trend-label">{{ d.day.slice(5) }}</span>
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

      <!-- v1.1.4: 各规律校正频率 -->
      <section v-if="effectiveness?.law_stats" class="card">
        <h3>{{ t('zhongdao.lawFreqTitle') }}</h3>
        <div class="law-freq-grid">
          <div v-for="(stats, lawId) in effectiveness.law_stats" :key="lawId" class="law-freq-item">
            <span class="law-freq-name">{{ stats.law_name }}</span>
            <span class="law-freq-counts">
              <span class="penalty-tag">{{ t('zhongdao.overusePenalty') }}: {{ stats.overuse_penalty }}</span>
              <span class="boost-tag">{{ t('zhongdao.neglectBoost') }}: {{ stats.neglect_boost }}</span>
            </span>
            <span class="law-freq-delta">Δ{{ stats.avg_weight_delta }}</span>
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

.suggestion-card { border-left: 3px solid #2196F3; }
.suggest-grid { display: flex; gap: 24px; margin-bottom: 12px; }
.suggest-item { display: flex; flex-direction: column; gap: 4px; }
.suggest-label { font-size: 0.8rem; color: var(--text-muted); text-transform: uppercase; }
.suggest-value { font-family: monospace; font-size: 1rem; }
.suggest-value.rec { color: #2196F3; font-weight: 600; }
.suggest-list { margin: 0; padding-left: 20px; font-size: 0.9rem; color: var(--text-muted); }
.suggest-list li { margin-bottom: 4px; }

.trend-chart { display: flex; align-items: flex-end; gap: 4px; height: 120px; padding: 8px 0; }
.trend-bar-col { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 4px; }
.trend-bar { width: 70%; background: #2196F3; border-radius: 3px 3px 0 0; min-height: 4px; transition: height 0.3s; }
.trend-label { font-size: 0.65rem; color: var(--text-muted); transform: rotate(-45deg); transform-origin: center; white-space: nowrap; }

.law-freq-grid { display: flex; flex-direction: column; gap: 8px; }
.law-freq-item { display: flex; align-items: center; gap: 12px; padding: 8px 12px; border-radius: 6px; background: var(--bg-muted); }
.law-freq-name { font-weight: 500; min-width: 120px; }
.law-freq-counts { flex: 1; font-size: 0.85rem; }
.penalty-tag { color: #ff9800; margin-right: 12px; }
.boost-tag { color: #4caf50; }
.law-freq-delta { font-family: monospace; font-size: 0.85rem; color: var(--text-muted); }

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

.header-actions { display: flex; gap: 8px; align-items: center; }
.days-select { padding: 4px 8px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg-card); color: var(--text); font-size: 0.85rem; }
.btn { padding: 6px 16px; border: 1px solid var(--border); border-radius: 8px; background: var(--bg-card); color: var(--text); cursor: pointer; font-size: 0.85rem; }
.btn:hover { background: var(--bg-muted); }
.btn-warn { border-color: #ff9800; color: #ff9800; }
.btn-warn:hover { background: #fff3e0; }
.btn-archive { border-color: #9e9e9e; color: #9e9e9e; }
.btn-archive:hover { background: #f5f5f5; }
</style>
