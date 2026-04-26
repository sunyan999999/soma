<script setup>
import { ref, inject, computed, onMounted } from 'vue'
import { api } from '../api'

const toast = inject('toast')
const loading = ref(true)
const running = ref(false)
const error = ref(null)
const latest = ref(null)
const history = ref([])
const compareData = ref(null)

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
    toast('基准测试完成', 'success')
    await loadData()
  } catch (e) {
    toast(`测试失败: ${e.message}`, 'error')
  } finally {
    running.value = false
  }
}

const scoreCards = computed(() => {
  if (!latest.value?.scores) return []
  const s = latest.value.scores
  const items = [
    { label: '综合评分', value: s.overall, color: 'var(--accent)', icon: '🎯' },
    { label: '记忆能力', value: s.memory, color: 'var(--cyan)', icon: '🧠' },
    { label: '智慧推理', value: s.wisdom, color: 'var(--emerald)', icon: '💡' },
    { label: '进化闭环', value: s.evolution, color: 'var(--amber)', icon: '🧬' },
  ]
  return items
})

const memoryMetrics = computed(() => {
  if (!latest.value?.memory) return []
  const m = latest.value.memory
  return [
    { label: '语义召回率', value: (m.semantic_recall_rate * 100).toFixed(0) + '%', target: '>90%' },
    { label: '写入延迟', value: m.avg_insert_latency_ms + 'ms', target: '<5ms' },
    { label: '查询延迟', value: m.avg_query_latency_ms + 'ms', target: '<20ms' },
    { label: '跨会话持久', value: m.cross_session_persistence ? '✅' : '❌', target: '✅' },
    { label: '去重率', value: (m.dedup_ratio * 100).toFixed(0) + '%', target: '>80%' },
    { label: '记忆总量', value: m.total_memories + '条', target: '-' },
  ]
})

const wisdomMetrics = computed(() => {
  if (!latest.value?.wisdom) return []
  const w = latest.value.wisdom
  return [
    { label: '拆解覆盖率', value: (w.decomposition_coverage * 100).toFixed(0) + '%', target: '100%' },
    { label: '思维多样性熵', value: w.thinking_diversity_entropy?.toFixed(2) || '0', target: '>0.8' },
    { label: '基尼系数', value: w.thinking_diversity_gini?.toFixed(2) || '0', target: '<0.3' },
    { label: '合成深度增益', value: '+' + w.synthesis_gain_depth_pct + '%', target: '>10%' },
    { label: '合成结构增益', value: '+' + w.synthesis_gain_structure_pct + '%', target: '>50%' },
    { label: '记忆关联度', value: w.memory_relevance_score?.toFixed(3) || '0', target: '>0.8' },
  ]
})

const evolutionMetrics = computed(() => {
  if (!latest.value?.evolution) return []
  const e = latest.value.evolution
  return [
    { label: '反思总数', value: e.total_reflections + '次', target: '>30' },
    { label: '成熟规律数', value: e.laws_with_enough_samples + '/7', target: '7/7' },
    { label: '平均成功率', value: (e.avg_success_rate * 100).toFixed(0) + '%', target: '>70%' },
    { label: '已固化技能', value: e.skills_solidified + '个', target: '>5' },
  ]
})

const historyScores = computed(() => {
  return history.value.map(h => ({
    id: h.id,
    time: new Date(h.timestamp * 1000).toLocaleDateString('zh-CN'),
    memory: h.scores.memory,
    wisdom: h.scores.wisdom,
    evolution: h.scores.evolution,
    overall: h.scores.overall,
  })).reverse()
})

const maxHistoryScore = computed(() => {
  return Math.max(100, ...historyScores.value.map(h => h.overall))
})

const competitors = computed(() => {
  if (!compareData.value?.competitors) return []
  const soma = compareData.value.soma || {}
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

function formatTime(ts) {
  if (!ts) return '-'
  return new Date(ts * 1000).toLocaleString('zh-CN')
}

onMounted(loadData)
</script>

<template>
  <div>
    <div class="row row-between" style="margin-bottom:8px;">
      <div>
        <h1 class="page-title">📐 基准测试</h1>
        <p class="page-subtitle">
          三维基准测试 — 记忆 · 智慧 · 进化 — 追踪 SOMA 能力演进
        </p>
      </div>
      <div class="row" style="gap:8px;">
        <button class="btn btn-secondary btn-sm" @click="loadData">🔄 刷新</button>
        <button class="btn btn-primary btn-sm" @click="runBenchmark" :disabled="running">
          {{ running ? '⏳ 测试中...' : '▶ 运行基准测试' }}
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
      <button class="btn btn-primary" @click="loadData" style="margin-top:16px;">🔄 重试</button>
    </div>

    <div v-if="!loading && !error && !latest" style="text-align:center;padding:60px;color:var(--text-muted);">
      <div style="font-size:3rem;margin-bottom:16px;">📐</div>
      <div style="font-size:1.1rem;margin-bottom:8px;">暂无基准测试数据</div>
      <div style="font-size:0.85rem;margin-bottom:20px;">点击"运行基准测试"按钮开始首次评测</div>
      <button class="btn btn-primary" @click="runBenchmark" :disabled="running">
        {{ running ? '⏳ 测试中...' : '▶ 运行基准测试' }}
      </button>
    </div>

    <div v-if="latest" class="gap-lg">
      <!-- Score Overview -->
      <div class="grid-4">
        <div v-for="card in scoreCards" :key="card.label" class="card" style="text-align:center;">
          <div style="font-size:1.2rem;margin-bottom:4px;">{{ card.icon }}</div>
          <div :style="{ fontSize: '1.8rem', fontWeight: 700, color: card.color }">
            {{ card.value }}
          </div>
          <div style="font-size:0.75rem;color:var(--text-muted);margin-top:4px;">{{ card.label }}</div>
        </div>
      </div>

      <!-- Score History Mini Chart -->
      <section class="card" v-if="historyScores.length > 1">
        <h2 style="font-size:1rem;margin-bottom:16px;">📈 评分趋势</h2>
        <div class="history-chart">
          <div class="history-bar-row" v-for="h in historyScores" :key="h.id">
            <div class="history-bar-label">{{ h.time }}</div>
            <div class="history-bar-track">
              <div class="history-bar-seg" :style="{
                width: (h.memory / maxHistoryScore * 100) + '%',
                background: 'var(--cyan)',
              }" :title="'记忆: ' + h.memory" />
              <div class="history-bar-seg" :style="{
                width: (h.wisdom / maxHistoryScore * 100) + '%',
                background: 'var(--emerald)',
                marginLeft: '2px',
              }" :title="'智慧: ' + h.wisdom" />
              <div class="history-bar-seg" :style="{
                width: (h.evolution / maxHistoryScore * 100) + '%',
                background: 'var(--amber)',
                marginLeft: '2px',
              }" :title="'进化: ' + h.evolution" />
              <span class="history-bar-overall">{{ h.overall }}</span>
            </div>
          </div>
        </div>
        <div class="row" style="gap:16px;margin-top:8px;font-size:0.7rem;color:var(--text-muted);">
          <span>▪ 记忆</span><span>▪ 智慧</span><span>▪ 进化</span>
        </div>
      </section>

      <!-- Three Dimensions -->
      <div class="grid-3-dim">
        <!-- Memory -->
        <section class="card">
          <h2 style="font-size:1rem;margin-bottom:12px;">🧠 记忆能力</h2>
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
          <h2 style="font-size:1rem;margin-bottom:12px;">💡 智慧推理</h2>
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
          <h2 style="font-size:1rem;margin-bottom:12px;">🧬 进化闭环</h2>
          <div class="metric-list">
            <div v-for="m in evolutionMetrics" :key="m.label" class="metric-row">
              <span class="metric-label">{{ m.label }}</span>
              <span class="metric-value">{{ m.value }}</span>
              <span class="metric-target">{{ m.target }}</span>
            </div>
          </div>
        </section>
      </div>

      <!-- Competitive Comparison -->
      <section class="card" v-if="competitors.length">
        <h2 style="font-size:1rem;margin-bottom:16px;">🏆 竞品对比</h2>
        <div style="overflow-x:auto;">
          <table class="compare-table">
            <thead>
              <tr>
                <th>项目</th>
                <th>⭐ Stars</th>
                <th>语义召回</th>
                <th>查询延迟</th>
                <th>去重</th>
                <th>SOMA 优势</th>
              </tr>
            </thead>
            <tbody>
              <tr class="soma-row">
                <td><strong>SOMA</strong></td>
                <td>-</td>
                <td>{{ latest.memory ? (latest.memory.semantic_recall_rate * 100).toFixed(0) + '%' : '-' }}</td>
                <td>{{ latest.memory ? latest.memory.avg_query_latency_ms + 'ms' : '-' }}</td>
                <td>{{ latest.memory ? (latest.memory.dedup_ratio * 100).toFixed(0) + '%' : '-' }}</td>
                <td style="color:var(--accent);font-weight:600;">思维框架+进化闭环</td>
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
        最近测试: {{ formatTime(latest.timestamp) }} | 历史记录: {{ history.length }} 次
      </div>
    </div>
  </div>
</template>

<style scoped>
.grid-4 {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.grid-3-dim {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}
@media (max-width: 1024px) {
  .grid-4 { grid-template-columns: repeat(2, 1fr); }
  .grid-3-dim { grid-template-columns: 1fr; }
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

/* History Chart */
.history-chart {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.history-bar-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.history-bar-label {
  width: 60px;
  min-width: 60px;
  font-size: 0.65rem;
  color: var(--text-muted);
  text-align: right;
}

.history-bar-track {
  flex: 1;
  height: 18px;
  background: rgba(255,255,255,0.04);
  border-radius: 6px;
  display: flex;
  align-items: center;
  padding: 0 4px;
  position: relative;
}

.history-bar-seg {
  height: 10px;
  border-radius: 3px;
}

.history-bar-overall {
  position: absolute;
  right: 10px;
  font-size: 0.65rem;
  font-weight: 700;
  color: var(--text-primary);
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
