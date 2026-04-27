<script setup>
import { ref, inject, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api'

const { t, locale } = useI18n()
function lawName(id) { return t(`laws.${id}`) || id }
const dateLocale = () => locale.value === 'zh' ? 'zh-CN' : 'en-US'
const toast = inject('toast')
const loading = ref(true)
const error = ref(null)
const summary = ref(null)
const compareData = ref(null)
const sessions = ref([])
const detailSession = ref(null)
const filterProvider = ref('')
const filterMock = ref(undefined)

// Evolution monitoring
const evoStats = ref({})
const evoLog = ref({ entries: [], total: 0 })
const evoLoading = ref(false)
const lastEvo = ref(null)

const hasEvolutionData = computed(() => {
  return Object.keys(evoStats.value).length > 0
})

const lawStatCards = computed(() => {
  return Object.entries(evoStats.value).map(([id, s]) => ({
    id,
    label: lawName(id),
    successes: s.successes,
    failures: s.failures,
    total: s.total,
    rate: s.success_rate,
    ratePct: Math.round(s.success_rate * 100),
  })).sort((a, b) => b.total - a.total)
})

const weightTimeline = computed(() => {
  if (!compareData.value?.weight_timeline) return []
  return compareData.value.weight_timeline
    .filter(t => Object.keys(t.weights).length > 0)
    .slice(-30)
})

const timelineProviders = computed(() => {
  const set = new Set()
  weightTimeline.value.forEach(t => set.add(t.provider))
  return [...set]
})

const statCards = computed(() => {
  if (!summary.value) return []
  return [
    { label: t('analytics.totalSessions'), value: summary.value.total_sessions, color: 'var(--accent)' },
    { label: t('analytics.realModel'), value: summary.value.mock_vs_real?.real || 0, color: 'var(--emerald)' },
    { label: t('analytics.mockMode'), value: summary.value.mock_vs_real?.mock || 0, color: 'var(--amber)' },
    { label: t('analytics.avgResponse'), value: summary.value.avg_response_time_ms, color: 'var(--cyan)' },
    { label: t('analytics.avgDimensions'), value: summary.value.avg_foci_count, color: 'var(--accent)' },
    { label: t('analytics.avgActivated'), value: summary.value.avg_activated_count, color: 'var(--emerald)' },
    { label: t('analytics.avgAnswerLen'), value: Math.round(summary.value.avg_answer_length) + ' ' + t('analytics.characters'), color: 'var(--cyan)' },
  ]
})

const providerBars = computed(() => {
  if (!compareData.value?.provider_stats) return []
  const maxCount = Math.max(...Object.values(compareData.value.provider_stats).map(s => s.count), 1)
  return Object.entries(compareData.value.provider_stats).map(([name, stats]) => ({
    name,
    count: stats.count,
    avgFoci: stats.avg_foci,
    avgActivated: stats.avg_activated,
    avgLen: stats.avg_answer_length,
    avgTime: stats.avg_response_time_ms,
    pct: Math.round((stats.count / maxCount) * 100),
  }))
})

const weightBars = computed(() => {
  if (!summary.value?.current_weights) return []
  const entries = Object.entries(summary.value.current_weights)
    .filter(([, w]) => typeof w === 'number' && !isNaN(w))
  if (!entries.length) return []
  return entries.sort((a, b) => b[1] - a[1]).map(([id, w]) => ({
    id,
    label: lawName(id),
    weight: w,
    pct: Math.round(w * 100),
  }))
})

async function loadData() {
  loading.value = true
  error.value = null
  try {
    const [s, c, sess] = await Promise.all([
      api.analyticsSummary(),
      api.analyticsCompare(),
      api.analyticsSessions(50),
    ])
    summary.value = s
    compareData.value = c
    sessions.value = sess
  } catch (e) {
    error.value = e.message
    toast(`${t('analytics.loadFailed')}: ${e.message}`, 'error')
  } finally {
    loading.value = false
  }
  loadEvolution()
}

async function loadEvolution() {
  evoLoading.value = true
  try {
    const [stats, log] = await Promise.all([
      api.frameworkStats(),
      api.frameworkLog(),
    ])
    evoStats.value = stats || {}
    evoLog.value = log || { entries: [], total: 0 }
    if (evoLog.value.entries?.length) {
      lastEvo.value = evoLog.value.entries[0]
    }
  } catch {
    // evolution data load failure does not affect main panel
  } finally {
    evoLoading.value = false
  }
}

async function showDetail(id) {
  try {
    detailSession.value = await api.analyticsSession(id)
  } catch (e) {
    toast(`${t('analytics.loadDetailFailed')}: ${e.message}`, 'error')
  }
}

function closeDetail() {
  detailSession.value = null
}

function formatTime(ts) {
  return new Date(ts * 1000).toLocaleString(dateLocale())
}

function formatDate(ts) {
  return new Date(ts * 1000).toLocaleDateString(dateLocale())
}

async function clearOld() {
  try {
    const res = await api.analyticsClear(200)
    toast(t('analytics.cleaned', { count: res.removed }), 'success')
    loadData()
  } catch (e) {
    toast(`${t('analytics.cleanFailed')}: ${e.message}`, 'error')
  }
}

onMounted(loadData)
</script>

<template>
  <div>
    <div class="row row-between" style="margin-bottom:8px;">
      <div>
        <h1 class="page-title">{{ t('analytics.title') }}</h1>
        <p class="page-subtitle">{{ t('analytics.subtitle') }}</p>
      </div>
      <button class="btn btn-secondary btn-sm" @click="loadData">{{ t('analytics.refresh') }}</button>
    </div>

    <div v-if="loading" class="gap-md">
      <div class="skeleton" style="height:80px;" />
      <div class="skeleton" style="height:200px;" />
    </div>

    <div v-if="!loading && error" style="text-align:center;padding:60px 20px;color:var(--text-muted);">
      <div style="font-size:3rem;margin-bottom:16px;">⚠️</div>
      <div style="font-size:1rem;margin-bottom:8px;">{{ t('analytics.loadFailed') }}</div>
      <div style="font-size:0.8rem;color:var(--text-muted);margin-bottom:20px;">{{ error }}</div>
      <button class="btn btn-primary" @click="loadData">{{ t('analytics.retry') }}</button>
    </div>

    <div v-if="!loading && summary" class="gap-lg">
      <!-- Stat Cards -->
      <div class="grid-3">
        <div v-for="card in statCards" :key="card.label" class="card" style="text-align:center;">
          <div :style="{ fontSize: '1.6rem', fontWeight: 700, color: card.color }">
            {{ card.value }}
          </div>
          <div style="font-size:0.75rem;color:var(--text-muted);margin-top:4px;">{{ card.label }}</div>
        </div>
      </div>

      <!-- Provider Comparison -->
      <section class="card" v-if="providerBars.length">
        <h2 style="font-size:1rem;margin-bottom:16px;">{{ t('analytics.providerCompare') }}</h2>
        <div class="bar-chart">
          <div v-for="bar in providerBars" :key="bar.name" class="bar-row">
            <div class="bar-label">{{ bar.name }}</div>
            <div class="bar-track">
              <div
                class="bar-fill"
                :style="{ width: bar.pct + '%', background: bar.name === 'mock' ? 'var(--amber)' : 'var(--accent)' }"
              />
              <span class="bar-val">{{ bar.count }} {{ t('analytics.times') }}</span>
            </div>
            <div class="bar-meta">
              <span :title="t('analytics.avgDimensions')">{{ bar.avgFoci }} {{ t('analytics.dimensions') }}</span>
              <span :title="t('analytics.avgActivated')">{{ bar.avgActivated }} {{ t('analytics.memories') }}</span>
              <span :title="t('analytics.avgResponse')">{{ bar.avgTime }}ms</span>
            </div>
          </div>
        </div>
      </section>

      <!-- Weights + Mock vs Real side by side -->
      <div class="grid-2">
        <!-- Weight Distribution -->
        <section class="card">
          <h2 style="font-size:1rem;margin-bottom:16px;">{{ t('analytics.weightDistribution') }}</h2>
          <div v-if="weightBars.length" class="bar-chart">
            <div v-for="bar in weightBars" :key="bar.id" class="bar-row">
              <div class="bar-label" style="font-size:0.75rem;">{{ bar.label }}</div>
              <div class="bar-track">
                <div
                  class="bar-fill"
                  :style="{
                    width: bar.pct + '%',
                    background: `hsl(${240 + bar.pct * 1.4}, 70%, ${50 + bar.pct * 0.2}%)`,
                  }"
                />
                <span class="bar-val">{{ bar.weight.toFixed(2) }}</span>
              </div>
            </div>
          </div>
        </section>

        <!-- Mock vs Real -->
        <section class="card" v-if="compareData?.mode_stats">
          <h2 style="font-size:1rem;margin-bottom:16px;">{{ t('analytics.mockVsReal') }}</h2>
          <div class="bar-chart" style="margin-top:12px;">
            <div class="bar-row" v-if="compareData.mode_stats.real?.count">
              <div class="bar-label">{{ t('analytics.realModelLabel') }}</div>
              <div class="bar-track">
                <div
                  class="bar-fill"
                  :style="{ width: Math.min(100, (compareData.mode_stats.real.count / Math.max(summary.total_sessions,1) * 100)) + '%', background: 'var(--emerald)' }"
                />
                <span class="bar-val">{{ compareData.mode_stats.real.count }} {{ t('analytics.times') }}</span>
              </div>
            </div>
            <div class="bar-row" v-if="compareData.mode_stats.mock?.count">
              <div class="bar-label">{{ t('analytics.mockLabel') }}</div>
              <div class="bar-track">
                <div
                  class="bar-fill"
                  :style="{ width: Math.min(100, (compareData.mode_stats.mock.count / Math.max(summary.total_sessions,1) * 100)) + '%', background: 'var(--amber)' }"
                />
                <span class="bar-val">{{ compareData.mode_stats.mock.count }} {{ t('analytics.times') }}</span>
              </div>
            </div>
          </div>

          <div v-if="compareData.mode_stats.real && compareData.mode_stats.mock" style="margin-top:16px;font-size:0.8rem;color:var(--text-muted);line-height:1.6;">
            <div>{{ t('analytics.realModelStats', { dims: compareData.mode_stats.real.avg_foci, mems: compareData.mode_stats.real.avg_activated, len: compareData.mode_stats.real.avg_answer_length }) }}</div>
            <div>{{ t('analytics.mockStats', { dims: compareData.mode_stats.mock.avg_foci, mems: compareData.mode_stats.mock.avg_activated, len: compareData.mode_stats.mock.avg_answer_length }) }}</div>
          </div>
        </section>
      </div>

      <!-- Evolution Monitoring -->
      <section class="card">
        <div class="row row-between" style="margin-bottom:16px;">
          <h2 style="font-size:1rem;">{{ t('analytics.evolution') }}</h2>
          <div class="row" style="gap:8px;">
            <span v-if="lastEvo" style="font-size:0.7rem;color:var(--text-muted);">
              {{ t('analytics.lastReflect') }}: {{ lastEvo.task_id }} — {{ lastEvo.outcome === 'success' ? t('common.success') : t('common.failure') }}
            </span>
            <button class="btn btn-secondary btn-sm" @click="loadEvolution" :disabled="evoLoading" style="font-size:0.7rem;">
              {{ evoLoading ? t('analytics.loadEvolution') : '🔄' }}
            </button>
          </div>
        </div>

        <div v-if="!hasEvolutionData && !evoLoading" style="text-align:center;padding:24px;color:var(--text-muted);font-size:0.85rem;">
          {{ t('analytics.noEvolution') }}
        </div>

        <div v-else class="gap-md">
          <!-- Law Stats Table -->
          <div v-if="lawStatCards.length">
            <div style="font-size:0.8rem;font-weight:600;margin-bottom:8px;">{{ t('analytics.lawSuccessTracking') }}</div>
            <div style="overflow-x:auto;">
              <table style="width:100%;font-size:0.78rem;border-collapse:collapse;">
                <thead>
                  <tr style="color:var(--text-muted);text-align:left;">
                    <th style="padding:6px 10px;">{{ t('analytics.law') }}</th>
                    <th style="padding:6px 10px;">{{ t('analytics.success') }}</th>
                    <th style="padding:6px 10px;">{{ t('analytics.failure') }}</th>
                    <th style="padding:6px 10px;">{{ t('analytics.total') }}</th>
                    <th style="padding:6px 10px;">{{ t('framework.successRateLabel') }}</th>
                    <th style="padding:6px 10px;">{{ t('analytics.trend') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="card in lawStatCards" :key="card.id" style="border-top:1px solid var(--border);">
                    <td style="padding:8px 10px;font-weight:600;text-transform:capitalize;">{{ card.label }}</td>
                    <td style="padding:8px 10px;color:var(--emerald);">{{ card.successes }}</td>
                    <td style="padding:8px 10px;color:var(--rose);">{{ card.failures }}</td>
                    <td style="padding:8px 10px;">{{ card.total }}</td>
                    <td style="padding:8px 10px;">
                      <span :style="{ color: card.rate >= 0.7 ? 'var(--emerald)' : card.rate >= 0.3 ? 'var(--amber)' : 'var(--rose)' }">
                        {{ card.ratePct }}%
                      </span>
                    </td>
                    <td style="padding:8px 10px;">
                      <div style="width:60px;height:6px;background:rgba(255,255,255,0.06);border-radius:3px;overflow:hidden;">
                        <div :style="{ width: card.ratePct + '%', height:'100%',
                          background: card.rate >= 0.7 ? 'var(--emerald)' : card.rate >= 0.3 ? 'var(--amber)' : 'var(--rose)',
                          borderRadius:'3px' }" />
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div style="font-size:0.65rem;color:var(--text-muted);margin-top:6px;">
              {{ t('analytics.evoTip') }}
            </div>
          </div>

          <!-- Weight Timeline -->
          <div v-if="weightTimeline.length > 1">
            <div style="font-size:0.8rem;font-weight:600;margin-bottom:8px;">{{ t('analytics.weightTimeline') }}</div>
            <div style="font-size:0.7rem;color:var(--text-muted);margin-bottom:10px;">
              <span v-for="pv in timelineProviders" :key="pv" class="badge" style="margin-right:6px;"
                :class="pv === 'mock' ? 'badge-amber' : 'badge-accent'">{{ pv }}</span>
            </div>
            <div class="timeline-mini">
              <div v-for="(wt, i) in weightTimeline" :key="i" class="timeline-dot-row">
                <div class="timeline-dot-label">{{ Object.keys(wt.weights).length }} {{ t('analytics.items') }}</div>
                <div class="timeline-dots">
                  <span v-for="(w, id) in wt.weights" :key="id"
                    class="timeline-dot-single"
                    :style="{ background: `hsl(${240 + w * 140}, 70%, ${40 + w * 25}%)`,
                      width: Math.max(4, w * 20) + 'px' }"
                    :title="id + ': ' + w.toFixed(2)" />
                </div>
                <div class="timeline-dot-provider">{{ wt.provider }}</div>
              </div>
            </div>
          </div>

          <!-- Reflect Log -->
          <div v-if="evoLog.entries?.length">
            <div style="font-size:0.8rem;font-weight:600;margin-bottom:8px;">{{ t('analytics.reflectLog') }}</div>
            <div class="gap-sm">
              <div v-for="(entry, i) in evoLog.entries.slice(0, 10)" :key="i"
                class="row" style="justify-content:space-between;padding:6px 10px;font-size:0.75rem;
                  background:rgba(255,255,255,0.02);border-radius:6px;">
                <span>{{ entry.task_id }}</span>
                <span :style="{ color: entry.outcome === 'success' ? 'var(--emerald)' : 'var(--rose)' }">
                  {{ entry.outcome === 'success' ? t('common.success') : t('common.failure') }}
                </span>
                <span style="color:var(--text-muted);">{{ formatTime(entry.timestamp) }}</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Sessions List -->
      <section>
        <div class="row row-between mb-md">
          <h2 style="font-size:1rem;">{{ t('analytics.sessionHistory') }}</h2>
          <div class="row" style="gap:8px;">
            <select v-model="filterProvider" style="width:auto;font-size:0.8rem;padding:6px 10px;">
              <option value="">{{ t('analytics.allProviders') }}</option>
              <option v-for="bar in providerBars" :key="bar.name" :value="bar.name">{{ bar.name }}</option>
            </select>
            <select v-model="filterMock" style="width:auto;font-size:0.8rem;padding:6px 10px;">
              <option :value="undefined">{{ t('analytics.allModes') }}</option>
              <option :value="true">Mock</option>
              <option :value="false">{{ t('analytics.realModelLabel') }}</option>
            </select>
            <button class="btn btn-secondary btn-sm" @click="clearOld()" style="font-size:0.75rem;">
              {{ t('analytics.cleanOld') }}
            </button>
          </div>
        </div>

        <div v-if="sessions.length === 0" style="text-align:center;padding:40px;color:var(--text-muted);">
          {{ t('analytics.noSessions') }}
        </div>

        <div v-else class="session-list">
          <div
            v-for="s in sessions"
            :key="s.id"
            class="session-row card"
            style="padding:14px 18px;cursor:pointer;"
            @click="showDetail(s.id)"
          >
            <div class="row row-between">
              <div style="flex:1;min-width:0;">
                <div class="row" style="gap:8px;margin-bottom:4px;">
                  <span class="badge" :class="s.mock_mode ? 'badge-amber' : 'badge-emerald'">
                    {{ s.mock_mode ? 'Mock' : s.provider }}
                  </span>
                  <span style="font-size:0.8rem;color:var(--text-secondary);" class="text-ellipsis">
                    {{ s.problem_preview }}
                  </span>
                </div>
                <div class="row" style="gap:16px;font-size:0.7rem;color:var(--text-muted);">
                  <span>{{ s.foci_count }} {{ t('analytics.dimensions') }}</span>
                  <span>{{ s.activated_count }} {{ t('analytics.memories') }}</span>
                  <span>{{ s.answer_length }} {{ t('analytics.characters') }}</span>
                  <span>{{ s.response_time_ms }}ms</span>
                </div>
              </div>
              <span style="font-size:0.75rem;color:var(--text-muted);white-space:nowrap;margin-left:12px;">
                {{ formatDate(s.created_at) }}
              </span>
            </div>
          </div>
        </div>
      </section>
    </div>

    <!-- Detail Modal -->
    <div v-if="detailSession" class="modal-overlay" @click.self="closeDetail">
      <div class="modal-card">
        <div class="row row-between mb-md">
          <h3 style="font-size:1.05rem;">{{ t('analytics.sessionDetail') }}</h3>
          <button class="btn btn-secondary btn-sm" @click="closeDetail">✕</button>
        </div>

        <div class="gap-md" style="max-height:70vh;overflow-y:auto;">
          <div>
            <div style="font-size:0.75rem;color:var(--text-muted);margin-bottom:4px;">{{ t('analytics.problem') }}</div>
            <div style="font-size:0.9rem;line-height:1.6;">{{ detailSession.problem }}</div>
          </div>

          <div class="row" style="gap:16px;flex-wrap:wrap;">
            <span class="badge" :class="detailSession.mock_mode ? 'badge-amber' : 'badge-emerald'">
              {{ detailSession.mock_mode ? 'Mock' : detailSession.provider_used }}
            </span>
            <span style="font-size:0.8rem;color:var(--text-muted);">
              {{ detailSession.foci?.length || 0 }} {{ t('analytics.dimensions') }}
            </span>
            <span style="font-size:0.8rem;color:var(--text-muted);">
              {{ detailSession.activated_memories?.length || 0 }} {{ t('analytics.memories') }}
            </span>
          </div>

          <div v-if="detailSession.foci?.length">
            <div style="font-size:0.8rem;font-weight:600;margin-bottom:8px;">{{ t('analytics.decomposeDimensions') }}</div>
            <div v-for="f in detailSession.foci" :key="f.law_id" class="card" style="padding:10px 14px;margin-bottom:6px;">
              <span class="badge badge-accent">{{ lawName(f.law_id) }}</span>
              <span style="margin-left:8px;font-size:0.8rem;color:var(--text-muted);">{{ t('chat.weight') }} {{ f.weight.toFixed(2) }}</span>
              <div style="font-size:0.8rem;color:var(--text-secondary);margin-top:4px;">{{ f.dimension?.slice(0, 200) }}</div>
            </div>
          </div>

          <div v-if="detailSession.activated_memories?.length">
            <div style="font-size:0.8rem;font-weight:600;margin-bottom:8px;">{{ t('analytics.activatedMemories') }}</div>
            <div v-for="am in detailSession.activated_memories.slice(0, 10)" :key="am.id"
              class="card" style="padding:10px 14px;margin-bottom:6px;"
            >
              <div class="row row-between">
                <span class="badge badge-amber">{{ am.source }}</span>
                <span style="font-size:0.7rem;color:var(--text-muted);">{{ t('chat.score') }} {{ am.activation_score.toFixed(4) }}</span>
              </div>
              <div style="font-size:0.8rem;color:var(--text-secondary);margin-top:4px;">{{ am.content?.slice(0, 150) }}</div>
            </div>
          </div>

          <div>
            <div style="font-size:0.8rem;font-weight:600;margin-bottom:8px;">{{ t('analytics.answer') }} ({{ detailSession.answer?.length || 0 }} {{ t('analytics.characters') }})</div>
            <div class="card answer-content" style="max-height:300px;overflow-y:auto;" v-html="(detailSession.answer || '')
              .replace(/^## (.+)$/gm, '<h2>$1</h2>')
              .replace(/^### (.+)$/gm, '<h3>$1</h3>')
              .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
              .replace(/^- (.+)$/gm, '<li>$1</li>')
              .replace(/\n/g, '<br>')
            " />
          </div>

          <div v-if="detailSession.weights">
            <div style="font-size:0.8rem;font-weight:600;margin-bottom:4px;">{{ t('analytics.weightSnapshot') }}</div>
            <div style="font-size:0.75rem;color:var(--text-muted);">
              <span v-for="(w, id) in detailSession.weights" :key="id" style="margin-right:12px;">
                {{ id }}: {{ w.toFixed(2) }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.bar-chart {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.bar-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.bar-label {
  width: 90px;
  min-width: 90px;
  font-size: 0.8rem;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-transform: capitalize;
}

.bar-track {
  flex: 1;
  height: 22px;
  background: rgba(255,255,255,0.04);
  border-radius: 6px;
  position: relative;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: 6px;
  transition: width 0.5s ease;
  min-width: 4px;
}

.bar-val {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 0.7rem;
  color: var(--text-primary);
  font-weight: 600;
}

.bar-meta {
  display: flex;
  gap: 8px;
  font-size: 0.65rem;
  color: var(--text-muted);
  min-width: 160px;
  justify-content: flex-end;
}

.text-ellipsis {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-row {
  margin-bottom: 6px;
  transition: all var(--transition);
}
.session-row:hover {
  border-color: var(--accent);
  background: rgba(99,102,241,0.06);
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  backdrop-filter: blur(4px);
}

.modal-card {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 24px;
  width: 90%;
  max-width: 800px;
  max-height: 85vh;
  overflow-y: auto;
}

/* ── Evolution Timeline ─────────────────────────────────── */
.timeline-mini {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.timeline-dot-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.timeline-dot-label {
  width: 36px;
  min-width: 36px;
  font-size: 0.6rem;
  color: var(--text-muted);
  text-align: right;
}

.timeline-dots {
  display: flex;
  gap: 3px;
  flex-wrap: wrap;
  flex: 1;
}

.timeline-dot-single {
  height: 6px;
  border-radius: 3px;
  display: inline-block;
}

.timeline-dot-provider {
  width: 64px;
  min-width: 64px;
  font-size: 0.6rem;
  color: var(--text-muted);
  text-transform: capitalize;
}
</style>
