<script setup>
import { ref, inject, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import * as echarts from 'echarts/core'
import { LineChart, BarChart, RadarChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent, GridComponent, RadarComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { api } from '../api'

echarts.use([LineChart, BarChart, RadarChart, TooltipComponent, LegendComponent, GridComponent, RadarComponent, CanvasRenderer])

const { t, locale } = useI18n()
const dateLocale = () => locale.value === 'zh' ? 'zh-CN' : 'en-US'
const toast = inject('toast')
const loading = ref(true)
const running = ref(false)
const error = ref(null)
const latest = ref(null)
const history = ref([])
const compareData = ref(null)
const trendChartRef = ref(null)
const radarChartRef = ref(null)
const compareChartRef = ref(null)
let trendChart = null
let radarChart = null
let compareChart = null

async function loadData() {
  loading.value = true
  error.value = null
  try {
    const [l, h, c] = await Promise.all([
      api.benchmarksLatest().catch(() => null),
      api.benchmarksHistory(),
      api.benchmarksCompare().catch(() => null),
    ])
    latest.value = l
    history.value = h || []
    compareData.value = c
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function runBenchmark() {
  running.value = true
  try {
    await api.benchmarksRun()
    toast(t('benchmarks.runComplete'), 'success')
    await loadData()
  } catch (e) {
    toast(`${t('benchmarks.runFailed')}: ${e.message}`, 'error')
  } finally {
    running.value = false
  }
}

const scoreCards = computed(() => {
  if (!latest.value?.scores) return []
  const s = latest.value.scores
  return [
    { label: t('benchmarks.overallScore'), value: s.overall, color: 'var(--accent)', icon: '🎯' },
    { label: t('benchmarks.memoryAbility'), value: s.memory, color: 'var(--cyan)', icon: '🧠' },
    { label: t('benchmarks.wisdomReasoning'), value: s.wisdom, color: 'var(--emerald)', icon: '💡' },
    { label: t('benchmarks.evolutionLoop'), value: s.evolution, color: 'var(--amber)', icon: '🧬' },
    { label: t('benchmarks.scalability'), value: s.scalability, color: 'var(--rose)', icon: '📐' },
  ]
})

const memoryMetrics = computed(() => {
  if (!latest.value?.memory) return []
  const m = latest.value.memory
  return [
    { label: t('benchmarks.semanticRecall'), value: (m.semantic_recall_rate * 100).toFixed(0) + '%', target: '>90%' },
    { label: t('benchmarks.insertLatency'), value: m.avg_insert_latency_ms + 'ms', target: '<5ms' },
    { label: t('benchmarks.queryLatency'), value: m.avg_query_latency_ms + 'ms', target: '<20ms' },
    { label: t('benchmarks.crossSession'), value: m.cross_session_persistence ? '✅' : '❌', target: '✅' },
    { label: t('benchmarks.dedupRate'), value: (m.dedup_ratio * 100).toFixed(0) + '%', target: '>80%' },
    { label: t('benchmarks.totalMemories'), value: '' + m.total_memories + t('common.itemsUnit'), target: '-' },
  ]
})

const wisdomMetrics = computed(() => {
  if (!latest.value?.wisdom) return []
  const w = latest.value.wisdom
  return [
    { label: t('benchmarks.decompositionCoverage'), value: (w.decomposition_coverage * 100).toFixed(0) + '%', target: '100%' },
    { label: t('benchmarks.thinkingDiversity'), value: w.thinking_diversity_entropy?.toFixed(2) || '0', target: '>0.8' },
    { label: t('benchmarks.giniCoefficient'), value: w.thinking_diversity_gini?.toFixed(2) || '0', target: '<0.3' },
    { label: t('benchmarks.synthesisDepthGain'), value: '+' + w.synthesis_gain_depth_pct + '%', target: '>10%' },
    { label: t('benchmarks.synthesisStructureGain'), value: '+' + w.synthesis_gain_structure_pct + '%', target: '>50%' },
    { label: t('benchmarks.memoryRelevance'), value: w.memory_relevance_score?.toFixed(3) || '0', target: '>0.8' },
  ]
})

const evolutionMetrics = computed(() => {
  if (!latest.value?.evolution) return []
  const e = latest.value.evolution
  return [
    { label: t('benchmarks.totalReflections'), value: '' + e.total_reflections + t('common.timesUnit'), target: '>30' },
    { label: t('benchmarks.matureLaws'), value: e.laws_with_enough_samples + '/7', target: '7/7' },
    { label: t('benchmarks.avgSuccessRate'), value: (e.avg_success_rate * 100).toFixed(0) + '%', target: '>70%' },
    { label: t('benchmarks.solidifiedSkills'), value: '' + e.skills_solidified + t('common.countUnit'), target: '>5' },
  ]
})

const historyScores = computed(() => {
  return history.value.map(h => ({
    id: h.id,
    time: new Date(h.timestamp * 1000).toLocaleDateString(dateLocale()),
    memory: h.scores.memory,
    wisdom: h.scores.wisdom,
    evolution: h.scores.evolution,
    scalability: h.scores.scalability || 0,
    overall: h.scores.overall,
  })).reverse()
})

const scalabilityMetrics = computed(() => {
  if (!latest.value?.scalability) return []
  const s = latest.value.scalability
  return [
    { label: t('benchmarks.fts5Speedup'), value: s.fts5_speedup_vs_like ? '×' + s.fts5_speedup_vs_like.toFixed(1) : '-', target: '>5×' },
    { label: t('benchmarks.query1k'), value: s.query_1k_ms ? s.query_1k_ms + 'ms' : '-', target: '<30ms' },
    { label: t('benchmarks.query10k'), value: s.query_10k_ms ? s.query_10k_ms + 'ms' : '-', target: '<150ms' },
    { label: t('benchmarks.query100k'), value: s.query_100k_ms ? s.query_100k_ms + 'ms' : '-', target: '<300ms' },
    { label: t('benchmarks.insertThroughput'), value: s.insert_throughput_per_s ? s.insert_throughput_per_s.toFixed(0) + '/s' : '-', target: '>10/s' },
    { label: t('benchmarks.searchThroughput'), value: s.search_throughput_per_s ? s.search_throughput_per_s.toFixed(0) + '/s' : '-', target: '>50/s' },
  ]
})

function renderTrendChart() {
  if (!trendChartRef.value || historyScores.value.length < 2) return
  if (!trendChart) {
    trendChart = echarts.init(trendChartRef.value)
  }
  const labels = historyScores.value.map(h => h.time)
  const fmt = (v) => v != null ? Number(v).toFixed(1) : '0'
  trendChart.setOption({
    tooltip: {
      trigger: 'axis',
      valueFormatter: (v) => v != null ? Number(v).toFixed(1) : '-',
    },
    legend: {
      bottom: 0,
      textStyle: { color: '#94a3b8', fontSize: 11 },
      data: [
        t('benchmarks.overallScore'),
        t('benchmarks.memoryAbility'),
        t('benchmarks.wisdomReasoning'),
        t('benchmarks.evolutionLoop'),
        t('benchmarks.scalability'),
      ],
    },
    grid: { left: 40, right: 20, top: 16, bottom: 40 },
    xAxis: {
      type: 'category',
      data: labels,
      axisLine: { lineStyle: { color: '#334155' } },
      axisLabel: { color: '#94a3b8', fontSize: 10 },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      splitLine: { lineStyle: { color: '#1e293b' } },
      axisLabel: { color: '#94a3b8', fontSize: 10 },
    },
    series: [
      {
        name: t('benchmarks.overallScore'),
        type: 'line',
        data: historyScores.value.map(h => h.overall),
        lineStyle: { color: '#818cf8', width: 2.5 },
        itemStyle: { color: '#818cf8' },
        symbol: 'circle',
        symbolSize: 6,
      },
      {
        name: t('benchmarks.memoryAbility'),
        type: 'line',
        data: historyScores.value.map(h => h.memory),
        lineStyle: { color: '#06b6d4', width: 1.5, type: 'dashed' },
        itemStyle: { color: '#06b6d4' },
        symbol: 'diamond',
        symbolSize: 5,
      },
      {
        name: t('benchmarks.wisdomReasoning'),
        type: 'line',
        data: historyScores.value.map(h => h.wisdom),
        lineStyle: { color: '#10b981', width: 1.5, type: 'dashed' },
        itemStyle: { color: '#10b981' },
        symbol: 'triangle',
        symbolSize: 5,
      },
      {
        name: t('benchmarks.evolutionLoop'),
        type: 'line',
        data: historyScores.value.map(h => h.evolution),
        lineStyle: { color: '#f59e0b', width: 1.5, type: 'dashed' },
        itemStyle: { color: '#f59e0b' },
        symbol: 'rect',
        symbolSize: 5,
      },
      {
        name: t('benchmarks.scalability'),
        type: 'line',
        data: historyScores.value.map(h => h.scalability),
        lineStyle: { color: '#f43f5e', width: 1.5, type: 'dotted' },
        itemStyle: { color: '#f43f5e' },
        symbol: 'arrow',
        symbolSize: 5,
      },
    ],
  }, true)
}

const competitors = computed(() => {
  if (!compareData.value?.competitors) return []
  return Object.entries(compareData.value.competitors).map(([name, data]) => ({
    name,
    stars: data.stars,
    recall: data.semantic_recall,
    recallPct: Math.round(data.semantic_recall * 100),
    queryMs: data.query_latency_ms,
    dedupPct: Math.round(data.dedup * 100),
    strength: data.strength,
    weakness: data.weakness,
    somaAdvantage: data.soma_advantage,
  })).sort((a, b) => b.stars - a.stars)
})

const radarData = computed(() => {
  if (!latest.value?.scores) return null
  const s = latest.value.scores
  return [
    { name: t('benchmarks.overallScore'), max: 100, value: s.overall },
    { name: t('benchmarks.memoryAbility'), max: 100, value: s.memory },
    { name: t('benchmarks.wisdomReasoning'), max: 100, value: s.wisdom },
    { name: t('benchmarks.evolutionLoop'), max: 100, value: s.evolution },
    { name: t('benchmarks.scalability'), max: 100, value: s.scalability },
  ]
})

const versionCompareData = computed(() => {
  if (history.value.length < 2) return null
  const sorted = [...history.value].sort((a, b) => b.timestamp - a.timestamp)
  const cur = sorted[0]
  const prev = sorted[1]
  const dims = ['overall', 'memory', 'wisdom', 'evolution', 'scalability']
  const dimLabels = [
    t('benchmarks.overallScore'),
    t('benchmarks.memoryAbility'),
    t('benchmarks.wisdomReasoning'),
    t('benchmarks.evolutionLoop'),
    t('benchmarks.scalability'),
  ]
  return {
    curVersion: cur.version || t('benchmarks.currentVersion'),
    prevVersion: prev.version || t('benchmarks.previousVersion'),
    dims,
    dimLabels,
    curValues: dims.map(d => cur.scores[d] || 0),
    prevValues: dims.map(d => prev.scores[d] || 0),
    diffs: dims.map(d => ((cur.scores[d] || 0) - (prev.scores[d] || 0)).toFixed(1)),
  }
})

function renderRadarChart() {
  if (!radarChartRef.value || !radarData.value) return
  if (!radarChart) radarChart = echarts.init(radarChartRef.value)
  radarChart.setOption({
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, textStyle: { color: '#94a3b8', fontSize: 11 } },
    radar: {
      center: ['50%', '45%'],
      radius: '65%',
      axisName: { color: '#94a3b8', fontSize: 10 },
      indicator: radarData.value.map(d => ({ name: d.name, max: d.max })),
      axisLine: { lineStyle: { color: '#334155' } },
      splitLine: { lineStyle: { color: '#1e293b' } },
      splitArea: { areaStyle: { color: ['rgba(99,102,241,0.02)', 'rgba(99,102,241,0.04)'] } },
    },
    series: [{
      type: 'radar',
      symbol: 'circle',
      symbolSize: 4,
      lineStyle: { color: '#818cf8', width: 2 },
      areaStyle: { color: 'rgba(129,140,248,0.15)' },
      itemStyle: { color: '#818cf8' },
      data: [{ value: radarData.value.map(d => d.value), name: t('benchmarks.currentVersion') }],
    }],
  }, true)
}

function renderCompareChart() {
  if (!compareChartRef.value || !versionCompareData.value) return
  if (!compareChart) compareChart = echarts.init(compareChartRef.value)
  const d = versionCompareData.value
  compareChart.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params) => {
        const dimIdx = params[0]?.dataIndex
        const diff = d.diffs[dimIdx]
        const diffStr = diff >= 0 ? '+' + diff : diff
        return `${d.dimLabels[dimIdx]}<br/>
          ${params[0]?.marker} ${params[0]?.seriesName}: ${params[0]?.value.toFixed(1)}<br/>
          ${params[1]?.marker} ${params[1]?.seriesName}: ${params[1]?.value.toFixed(1)}<br/>
          <b>${diffStr}</b>`
      },
    },
    legend: {
      bottom: 0,
      textStyle: { color: '#94a3b8', fontSize: 11 },
    },
    grid: { left: 40, right: 20, top: 16, bottom: 44 },
    xAxis: {
      type: 'category',
      data: d.dimLabels,
      axisLine: { lineStyle: { color: '#334155' } },
      axisLabel: { color: '#94a3b8', fontSize: 10, interval: 0 },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      splitLine: { lineStyle: { color: '#1e293b' } },
      axisLabel: { color: '#94a3b8', fontSize: 10 },
    },
    series: [
      {
        name: d.curVersion,
        type: 'bar',
        data: d.curValues,
        itemStyle: { color: '#818cf8', borderRadius: [4, 4, 0, 0] },
        barMaxWidth: 32,
        label: { show: true, position: 'top', color: '#818cf8', fontSize: 10, formatter: (v) => v.value.toFixed(0) },
      },
      {
        name: d.prevVersion,
        type: 'bar',
        data: d.prevValues,
        itemStyle: { color: 'rgba(148,163,184,0.35)', borderRadius: [4, 4, 0, 0] },
        barMaxWidth: 32,
        label: { show: true, position: 'top', color: '#94a3b8', fontSize: 10, formatter: (v) => v.value.toFixed(0) },
      },
    ],
  }, true)
}

watch([historyScores, radarData, versionCompareData, locale], () => {
  nextTick(() => {
    renderTrendChart()
    renderRadarChart()
    renderCompareChart()
  })
}, { deep: true })

function resizeCharts() {
  trendChart?.resize()
  radarChart?.resize()
  compareChart?.resize()
}

onMounted(() => {
  loadData()
  window.addEventListener('resize', resizeCharts)
})

onUnmounted(() => {
  trendChart?.dispose()
  radarChart?.dispose()
  compareChart?.dispose()
  window.removeEventListener('resize', resizeCharts)
})

function formatTime(ts) {
  if (!ts) return '-'
  return new Date(ts * 1000).toLocaleString(dateLocale())
}

</script>

<template>
  <div>
    <div class="row row-between" style="margin-bottom:8px;">
      <div>
        <h1 class="page-title">{{ t('benchmarks.title') }}</h1>
        <p class="page-subtitle">{{ t('benchmarks.subtitle') }}</p>
      </div>
      <div class="row" style="gap:8px;">
        <button class="btn btn-secondary btn-sm" @click="loadData">{{ t('benchmarks.refresh') }}</button>
        <button class="btn btn-primary btn-sm" @click="runBenchmark" :disabled="running">
          {{ running ? t('benchmarks.running') : t('benchmarks.runBenchmark') }}
        </button>
      </div>
    </div>

    <div v-if="loading" class="gap-md">
      <div class="skeleton" style="height:80px;" />
      <div class="skeleton" style="height:200px;" />
    </div>

    <div v-if="error" style="text-align:center;padding:60px;color:var(--text-muted);">
      <div style="font-size:3rem;margin-bottom:16px;">⚠️</div>
      <div>{{ error }}</div>
      <button class="btn btn-primary" @click="loadData" style="margin-top:16px;">{{ t('analytics.retry') }}</button>
    </div>

    <div v-if="!loading && !error && !latest" style="text-align:center;padding:60px;color:var(--text-muted);">
      <div style="font-size:3rem;margin-bottom:16px;">📐</div>
      <div style="font-size:1.1rem;margin-bottom:8px;">{{ t('benchmarks.noData') }}</div>
      <div style="font-size:0.85rem;margin-bottom:20px;">{{ t('benchmarks.noDataDesc') }}</div>
      <button class="btn btn-primary" @click="runBenchmark" :disabled="running">
        {{ running ? t('benchmarks.running') : t('benchmarks.runBenchmark') }}
      </button>
    </div>

    <div v-if="latest" class="gap-lg">
      <!-- Score Overview -->
      <div class="grid-5">
        <div v-for="card in scoreCards" :key="card.label" class="card" style="text-align:center;">
          <div style="font-size:1.2rem;margin-bottom:4px;">{{ card.icon }}</div>
          <div :style="{ fontSize: '1.8rem', fontWeight: 700, color: card.color }">
            {{ card.value }}
          </div>
          <div style="font-size:0.75rem;color:var(--text-muted);margin-top:4px;">{{ card.label }}</div>
        </div>
      </div>

      <!-- Score Trend Chart -->
      <section class="card" v-if="historyScores.length > 1">
        <h2 style="font-size:1rem;margin-bottom:16px;">{{ t('benchmarks.scoreTrend') }}</h2>
        <div ref="trendChartRef" class="trend-chart" />
      </section>

      <!-- Radar + Version Compare -->
      <div class="grid-chart-duo" v-if="latest">
        <!-- Radar Chart -->
        <section class="card" v-if="radarData">
          <h2 style="font-size:1rem;margin-bottom:12px;">{{ t('benchmarks.radarChart') }}</h2>
          <div ref="radarChartRef" class="radar-chart" />
        </section>

        <!-- Version Comparison -->
        <section class="card" v-if="versionCompareData">
          <h2 style="font-size:1rem;margin-bottom:12px;">{{ t('benchmarks.versionCompare') }}</h2>
          <div ref="compareChartRef" class="compare-chart" />
        </section>
      </div>

      <!-- Four Dimensions -->
      <div class="grid-4-dim">
        <!-- Memory -->
        <section class="card">
          <h2 style="font-size:1rem;margin-bottom:12px;">{{ t('benchmarks.memoryCap') }}</h2>
          <div class="metric-list">
            <div v-for="m in memoryMetrics" :key="m.label" class="metric-row">
              <span class="metric-label">{{ m.label }}</span>
              <span class="metric-value">{{ m.value }}</span>
              <span class="metric-target">{{ m.target }}</span>
            </div>
          </div>
        </section>

        <!-- Wisdom -->
        <section class="card">
          <h2 style="font-size:1rem;margin-bottom:12px;">{{ t('benchmarks.wisdomCap') }}</h2>
          <div class="metric-list">
            <div v-for="m in wisdomMetrics" :key="m.label" class="metric-row">
              <span class="metric-label">{{ m.label }}</span>
              <span class="metric-value">{{ m.value }}</span>
              <span class="metric-target">{{ m.target }}</span>
            </div>
          </div>
        </section>

        <!-- Evolution -->
        <section class="card">
          <h2 style="font-size:1rem;margin-bottom:12px;">{{ t('benchmarks.evolutionCap') }}</h2>
          <div class="metric-list">
            <div v-for="m in evolutionMetrics" :key="m.label" class="metric-row">
              <span class="metric-label">{{ m.label }}</span>
              <span class="metric-value">{{ m.value }}</span>
              <span class="metric-target">{{ m.target }}</span>
            </div>
          </div>
        </section>

        <!-- Scalability -->
        <section class="card">
          <h2 style="font-size:1rem;margin-bottom:12px;">{{ t('benchmarks.scalabilityCap') }}</h2>
          <div class="metric-list">
            <div v-for="m in scalabilityMetrics" :key="m.label" class="metric-row">
              <span class="metric-label">{{ m.label }}</span>
              <span class="metric-value">{{ m.value }}</span>
              <span class="metric-target">{{ m.target }}</span>
            </div>
          </div>
        </section>
      </div>

      <!-- Competitive Comparison -->
      <section class="card" v-if="competitors.length">
        <h2 style="font-size:1rem;margin-bottom:16px;">{{ t('benchmarks.competitorCompare') }}</h2>
        <div style="overflow-x:auto;">
          <table class="compare-table">
            <thead>
              <tr>
                <th>{{ t('benchmarks.project') }}</th>
                <th>{{ t('benchmarks.stars') }}</th>
                <th>{{ t('benchmarks.semanticRecall') }}</th>
                <th>{{ t('benchmarks.queryLatency') }}</th>
                <th>{{ t('benchmarks.dedupRate') }}</th>
                <th>{{ t('benchmarks.advantage') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr class="soma-row">
                <td><strong>SOMA</strong></td>
                <td>-</td>
                <td>{{ latest.memory ? (latest.memory.semantic_recall_rate * 100).toFixed(0) + '%' : '-' }}</td>
                <td>{{ latest.memory ? latest.memory.avg_query_latency_ms + 'ms' : '-' }}</td>
                <td>{{ latest.memory ? (latest.memory.dedup_ratio * 100).toFixed(0) + '%' : '-' }}</td>
                <td style="color:var(--accent);font-weight:600;">{{ t('benchmarks.frameworkEvo') }}</td>
              </tr>
              <tr v-for="c in competitors" :key="c.name">
                <td><strong>{{ c.name }}</strong></td>
                <td>{{ c.stars >= 1000 ? (c.stars / 1000).toFixed(1) + 'K' : c.stars }}</td>
                <td>{{ c.recallPct }}%</td>
                <td>{{ c.queryMs }}ms</td>
                <td>{{ c.dedupPct }}%</td>
                <td style="font-size:0.75rem;color:var(--text-secondary);">{{ c.somaAdvantage }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- Last Updated -->
      <div style="text-align:center;font-size:0.75rem;color:var(--text-muted);">
        {{ t('benchmarks.lastTest') }}: {{ formatTime(latest.timestamp) }} | {{ t('benchmarks.historyCount') }}: {{ history.length }} {{ t('analytics.times') }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.grid-5 {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
}
.grid-4-dim {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
@media (max-width: 1200px) {
  .grid-5 { grid-template-columns: repeat(3, 1fr); }
}
@media (max-width: 1024px) {
  .grid-5 { grid-template-columns: repeat(2, 1fr); }
  .grid-4-dim { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 640px) {
  .grid-5 { grid-template-columns: 1fr; }
  .grid-4-dim { grid-template-columns: 1fr; }
}

.metric-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.metric-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: rgba(255,255,255,0.02);
  border-radius: 8px;
}

.metric-label {
  font-size: 0.78rem;
  color: var(--text-secondary);
  min-width: 80px;
}

.metric-value {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-primary);
}

.metric-target {
  font-size: 0.65rem;
  color: var(--text-muted);
  min-width: 44px;
  text-align: right;
}

.trend-chart {
  width: 100%;
  height: 300px;
}

.radar-chart {
  width: 100%;
  height: 320px;
}

.compare-chart {
  width: 100%;
  height: 300px;
}

.grid-chart-duo {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

@media (max-width: 768px) {
  .grid-chart-duo { grid-template-columns: 1fr; }
}

/* Compare Table */
.compare-table {
  width: 100%;
  font-size: 0.8rem;
  border-collapse: collapse;
}

.compare-table th {
  text-align: left;
  padding: 8px 12px;
  color: var(--text-muted);
  font-weight: 500;
  border-bottom: 1px solid var(--border);
}

.compare-table td {
  padding: 10px 12px;
  border-bottom: 1px solid rgba(255,255,255,0.03);
}

.soma-row {
  background: rgba(99, 102, 241, 0.08);
}
</style>
