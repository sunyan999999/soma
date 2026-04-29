<script setup>
import { ref, inject, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api'
import DecompositionGraph from '../components/DecompositionGraph.vue'

const { t } = useI18n()
function lawName(id) { return t(`laws.${id}`) || id }
const toast = inject('toast')

const weights = ref({})
const lawStats = ref({})
const evolveChanges = ref(null)
const evolving = ref(false)

// Log
const logData = ref({ entries: [], total: 0 })
const clearingLog = ref(false)

// 最新拆解数据
const latestFoci = ref([])
const latestProblem = ref('')

const lawNames = computed(() => ({
  first_principles: t('laws.first_principles'),
  systems_thinking: t('laws.systems_thinking'),
  contradiction_analysis: t('laws.contradiction_analysis'),
  pareto_principle: t('laws.pareto_principle'),
  inversion: t('laws.inversion'),
  analogical_reasoning: t('laws.analogical_reasoning'),
  evolutionary_lens: t('laws.evolutionary_lens'),
}))

onMounted(async () => {
  try {
    const [w, s, l] = await Promise.all([
      api.frameworkWeights(),
      api.frameworkStats(),
      api.frameworkLog(),
    ])
    weights.value = w
    lawStats.value = s
    logData.value = l
  } catch {}

  // 加载最新一次会话的拆解数据
  try {
    const sessions = await api.analyticsSessions(1, 0, '', false)
    if (sessions.length && sessions[0].foci) {
      latestFoci.value = sessions[0].foci
      latestProblem.value = sessions[0].problem_preview || ''
    }
  } catch {}
})

async function adjustWeight(lawId, newWeight) {
  try {
    await api.frameworkAdjust(lawId, newWeight)
    weights.value = { ...weights.value, [lawId]: newWeight }
    toast(`${t('framework.weightUpdated')}: ${lawName(lawId)} → ${newWeight.toFixed(2)}`, 'success')
  } catch (e) {
    toast(`${t('framework.adjustFailed')}: ${e.message}`, 'error')
  }
}

async function doEvolve() {
  evolving.value = true
  evolveChanges.value = null
  try {
    const data = await api.frameworkEvolve()
    weights.value = data.weights
    evolveChanges.value = data.changes
    if (data.changes.length) {
      toast(`${t('framework.applied')} ${data.changes.length} ${t('framework.changesApplied')}`, 'success')
    } else {
      toast(t('framework.noData'), 'info')
    }
  } catch (e) {
    toast(`${t('framework.evolveFailed')}: ${e.message}`, 'error')
  } finally {
    evolving.value = false
  }
}

async function clearLog() {
  clearingLog.value = true
  try {
    await api.frameworkClearLog()
    logData.value = { entries: [], total: 0 }
    toast(t('framework.logCleared'), 'info')
  } catch (e) {
    toast(`${t('framework.clearFailed')}: ${e.message}`, 'error')
  } finally {
    clearingLog.value = false
  }
}
</script>

<template>
  <div>
    <h1 class="page-title">{{ t('framework.title') }}</h1>
    <p class="page-subtitle">{{ t('framework.subtitle') }}</p>

    <div class="grid-2" style="margin-bottom:24px;">
      <!-- Weights -->
      <div class="card">
        <h3 class="card-title">{{ t('framework.lawWeights') }}</h3>
        <div class="gap-sm" style="margin-top:16px;">
          <div v-for="(w, lawId) in weights" :key="lawId">
            <div class="row row-between" style="margin-bottom:4px;">
              <span style="font-size:0.85rem;font-weight:500;">{{ lawName(lawId) }}</span>
              <span style="font-size:0.8rem;color:var(--text-muted);">{{ w.toFixed(3) }}</span>
            </div>
            <div style="position:relative;height:6px;background:rgba(255,255,255,0.05);border-radius:3px;overflow:hidden;">
              <div
                :style="{
                  width: (w * 100) + '%',
                  height: '100%',
                  borderRadius: '3px',
                  background: `linear-gradient(90deg, var(--accent), var(--cyan))`,
                  transition: 'width 0.5s ease',
                }"
              />
            </div>
          </div>
        </div>
      </div>

      <!-- Adjust -->
      <div class="card">
        <h3 class="card-title">{{ t('framework.manualAdjust') }}</h3>
        <div class="gap-sm" style="margin-top:16px;">
          <div v-for="(w, lawId) in weights" :key="'adj_'+lawId" class="row" style="gap:12px;">
            <span style="width:120px;font-size:0.8rem;">{{ lawName(lawId) }}</span>
            <input
              type="range" min="0" max="1" step="0.01"
              :value="w"
              style="flex:1;accent-color:var(--accent);"
              @change="adjustWeight(lawId, parseFloat($event.target.value))"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- Latest Decomposition Tree -->
    <div class="card" style="margin-bottom:24px;">
      <h3 class="card-title">{{ t('framework.latestDecomposition') }}</h3>
      <div v-if="latestFoci.length" style="margin-top:12px;">
        <DecompositionGraph
          :foci="latestFoci"
          :problem="latestProblem"
          :law-names="lawNames"
        />
      </div>
      <div v-else style="text-align:center;padding:40px;color:var(--text-muted);font-size:0.85rem;">
        {{ t('framework.noDecompositionData') }}
      </div>
    </div>

    <!-- Success Rate Stats -->
    <div v-if="Object.keys(lawStats).length" class="card" style="margin-bottom:24px;">
      <h3 class="card-title">{{ t('framework.successRate') }}</h3>
      <div class="grid-3" style="margin-top:16px;">
        <div v-for="(s, lawId) in lawStats" :key="lawId" style="text-align:center;">
          <div
            :style="{
              fontSize: '1.6rem',
              fontWeight: '700',
              color: s.success_rate >= 0.7 ? 'var(--emerald)' : s.success_rate >= 0.4 ? 'var(--amber)' : 'var(--rose)',
            }"
          >
            {{ (s.success_rate * 100).toFixed(0) }}%
          </div>
          <div style="font-size:0.85rem;font-weight:600;margin-top:2px;">{{ lawName(lawId) }}</div>
          <div style="font-size:0.75rem;color:var(--text-muted);">
            {{ s.successes }}/{{ s.total }} {{ t('common.success') }}
          </div>
        </div>
      </div>
    </div>

    <!-- Evolve -->
    <div class="card" style="margin-bottom:24px;">
      <div class="row row-between">
        <div>
          <h3 class="card-title">{{ t('framework.autoEvolve') }}</h3>
          <p style="font-size:0.8rem;color:var(--text-muted);margin-top:4px;">
            {{ t('framework.evolveRule') }}
          </p>
        </div>
        <button class="btn btn-primary" :disabled="evolving" @click="doEvolve">
          {{ evolving ? t('framework.evolving') : t('framework.doEvolve') }}
        </button>
      </div>

      <div v-if="evolveChanges" class="mt-md">
        <div v-if="evolveChanges.length === 0" style="color:var(--text-muted);font-size:0.85rem;">
          {{ t('framework.noChange') }}
        </div>
        <div v-for="c in evolveChanges" :key="c.law_id || c.skill_name" class="card" style="margin-top:12px;background:rgba(99,102,241,0.05);">
          <template v-if="c.type === 'skill_solidified'">
            {{ t('framework.skillSolidified') }}: {{ c.skill_name }}
            <span style="font-size:0.8rem;color:var(--text-muted);"> ({{ c.occurrences }} {{ t('framework.successCount') }})</span>
          </template>
          <template v-else>
            <strong>{{ lawName(c.law_id) }}</strong>:
            {{ c.old_weight }} → <strong>{{ c.new_weight }}</strong>
            <span style="font-size:0.8rem;color:var(--text-muted);">
              ({{ t('framework.successRateLabel') }} {{ (c.success_rate * 100).toFixed(0) }}%, n={{ c.total_samples }})
            </span>
          </template>
        </div>
      </div>
    </div>

    <!-- Reflection Log -->
    <div class="card">
      <div class="row row-between">
        <h3 class="card-title">{{ t('framework.reflectionLog') }} ({{ logData.total }})</h3>
        <button class="btn btn-secondary btn-sm" :disabled="clearingLog || logData.total === 0" @click="clearLog">
          {{ t('framework.clear') }}
        </button>
      </div>
      <div v-if="logData.entries.length === 0" style="text-align:center;padding:24px;color:var(--text-muted);font-size:0.85rem;">
        {{ t('framework.noLog') }}
      </div>
      <div v-else class="gap-sm" style="margin-top:16px;max-height:400px;overflow-y:auto;">
        <div
          v-for="entry in logData.entries"
          :key="entry.task_id + entry.timestamp"
          style="padding:8px 0;border-bottom:1px solid var(--border);font-size:0.85rem;"
        >
          <span :style="{color: entry.outcome === 'success' ? 'var(--emerald)' : 'var(--rose)'}">
            [{{ entry.outcome === 'success' ? t('common.success') : t('common.failure') }}]
          </span>
          <span style="color:var(--text-muted);margin-left:8px;">{{ entry.task_id }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
