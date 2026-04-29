<script setup>
import { ref, inject, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api'
import ActivationSankey from '../components/ActivationSankey.vue'

const { t } = useI18n()
const toast = inject('toast')

const stats = ref({ episodic: 0, semantic: 0, skill: 0 })
const searchQuery = ref('')
const searchResults = ref([])
const searching = ref(false)

// Add form
const addContent = ref('')
const addDomain = ref(t('memory.defaultDomain'))
const addType = ref(t('memory.defaultType'))
const addImportance = ref(0.7)
const adding = ref(false)

// Semantic form
const semSubject = ref('')
const semPredicate = ref('')
const semObject = ref('')
const addingSem = ref(false)

// Tab state
const tab = ref('search')

// 激活流数据（从最新 analytics session 加载）
const flowFoci = ref([])
const flowMemories = ref([])
const flowLoading = ref(false)

onMounted(async () => {
  try { stats.value = await api.memoryStats() } catch {}
})

async function loadActivationFlow() {
  if (flowFoci.value.length) return
  flowLoading.value = true
  try {
    const sessions = await api.analyticsSessions(1, 0, '', false)
    if (sessions.length) {
      const detail = await api.analyticsSession(sessions[0].id)
      flowFoci.value = detail.foci || []
      flowMemories.value = (detail.activated_memories || []).map(am => ({
        source: am.source,
        content: am.content || '',
        activation_score: am.activation_score || 0,
      }))
    }
  } catch {}
  flowLoading.value = false
}

async function doSearch() {
  if (!searchQuery.value.trim()) return
  searching.value = true
  try {
    const data = await api.memorySearch(searchQuery.value)
    searchResults.value = data.results
  } catch (e) {
    toast(`${t('memory.searchFailed')}: ${e.message}`, 'error')
  } finally {
    searching.value = false
  }
}

async function doAddMemory() {
  if (!addContent.value.trim()) return
  adding.value = true
  try {
    await api.memoryAdd(addContent.value, addDomain.value, addType.value, addImportance.value)
    toast(t('memory.saved'), 'success')
    addContent.value = ''
    stats.value = await api.memoryStats()
  } catch (e) {
    toast(`${t('memory.saveFailed')}: ${e.message}`, 'error')
  } finally {
    adding.value = false
  }
}

async function doAddSemantic() {
  if (!semSubject.value.trim() || !semPredicate.value.trim() || !semObject.value.trim()) return
  addingSem.value = true
  try {
    await api.memoryAddSemantic(semSubject.value, semPredicate.value, semObject.value)
    toast(t('memory.tripleSaved'), 'success')
    semSubject.value = ''
    semPredicate.value = ''
    semObject.value = ''
    stats.value = await api.memoryStats()
  } catch (e) {
    toast(`${t('memory.saveFailed')}: ${e.message}`, 'error')
  } finally {
    addingSem.value = false
  }
}
</script>

<template>
  <div>
    <h1 class="page-title">{{ t('memory.title') }}</h1>
    <p class="page-subtitle">{{ t('memory.subtitle') }}</p>

    <!-- Stats -->
    <div class="grid-3" style="margin-bottom:24px;">
      <div class="card" style="text-align:center;">
        <div style="font-size:2rem;font-weight:700;color:var(--accent);">{{ stats.episodic }}</div>
        <div style="font-size:0.8rem;color:var(--text-muted);">{{ t('memory.episodicMemory') }}</div>
      </div>
      <div class="card" style="text-align:center;">
        <div style="font-size:2rem;font-weight:700;color:var(--cyan);">{{ stats.semantic }}</div>
        <div style="font-size:0.8rem;color:var(--text-muted);">{{ t('memory.semanticTriples') }}</div>
      </div>
      <div class="card" style="text-align:center;">
        <div style="font-size:2rem;font-weight:700;color:var(--amber);">{{ stats.skill }}</div>
        <div style="font-size:0.8rem;color:var(--text-muted);">{{ t('memory.skillPatterns') }}</div>
      </div>
    </div>

    <!-- Tab Switcher -->
    <div class="row" style="margin-bottom:20px;">
      <button class="btn" :class="tab === 'search' ? 'btn-primary' : 'btn-secondary'" @click="tab = 'search'">{{ t('memory.searchTab') }}</button>
      <button class="btn" :class="tab === 'add' ? 'btn-primary' : 'btn-secondary'" @click="tab = 'add'">{{ t('memory.episodicTab') }}</button>
      <button class="btn" :class="tab === 'semantic' ? 'btn-primary' : 'btn-secondary'" @click="tab = 'semantic'">{{ t('memory.semanticTab') }}</button>
      <button class="btn" :class="tab === 'flow' ? 'btn-primary' : 'btn-secondary'" @click="tab = 'flow'; loadActivationFlow()">{{ t('memory.activationFlowTab') }}</button>
    </div>

    <!-- Search Tab -->
    <div v-if="tab === 'search'">
      <div class="card">
        <div class="row" style="gap:12px;">
          <input
            v-model="searchQuery"
            :placeholder="t('memory.searchPlaceholder')"
            @keydown.enter="doSearch"
            style="flex:1;"
          />
          <button class="btn btn-primary" :disabled="searching" @click="doSearch">
            {{ searching ? t('memory.searching') : t('memory.search') }}
          </button>
        </div>
      </div>

      <div v-if="searchResults.length" class="gap-md mt-lg">
        <p style="font-size:0.85rem;color:var(--text-muted);">
          {{ t('memory.found') }} {{ searchResults.length }} {{ t('memory.resultsFound') }}
        </p>
        <div
          v-for="(r, i) in searchResults"
          :key="r.memory_id || i"
          class="card"
        >
          <div class="row row-between">
            <span class="badge badge-accent">{{ r.source }}</span>
            <div class="row" style="gap:16px;font-size:0.75rem;color:var(--text-muted);">
              <span>{{ t('memory.score') }} {{ (r.activation_score || 0).toFixed(3) }}</span>
              <span>{{ t('memory.importance') }} {{ (r.importance || 0).toFixed(2) }}</span>
            </div>
          </div>
          <p style="font-size:0.88rem;margin-top:12px;color:var(--text-secondary);line-height:1.7;">
            {{ r.content_preview }}
          </p>
        </div>
      </div>

      <div v-if="searchQuery && !searching && !searchResults.length" style="text-align:center;padding:40px;color:var(--text-muted);">
        {{ t('memory.noResults') }}
      </div>
    </div>

    <!-- Add Episodic Tab -->
    <div v-if="tab === 'add'">
      <div class="card">
        <div class="gap-md">
          <textarea
            v-model="addContent"
            :placeholder="t('memory.contentPlaceholder')"
            style="min-height:120px;"
          />
          <div class="grid-3">
            <div>
              <label style="font-size:0.8rem;color:var(--text-muted);display:block;margin-bottom:4px;">{{ t('memory.domain') }}</label>
              <input v-model="addDomain" :placeholder="t('memory.domainPlaceholder')" />
            </div>
            <div>
              <label style="font-size:0.8rem;color:var(--text-muted);display:block;margin-bottom:4px;">{{ t('memory.type') }}</label>
              <input v-model="addType" :placeholder="t('memory.typePlaceholder')" />
            </div>
            <div>
              <label style="font-size:0.8rem;color:var(--text-muted);display:block;margin-bottom:4px;">
                {{ t('memory.importanceLabel') }}: {{ addImportance.toFixed(2) }}
              </label>
              <input
                type="range" min="0" max="1" step="0.05"
                v-model.number="addImportance"
                style="width:100%;accent-color:var(--accent);"
              />
            </div>
          </div>
          <button
            class="btn btn-primary"
            :disabled="!addContent.trim() || adding"
            @click="doAddMemory"
          >
            {{ adding ? t('memory.saving') : t('memory.save') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Add Semantic Tab -->
    <div v-if="tab === 'semantic'">
      <div class="card">
        <div class="gap-md">
          <p style="font-size:0.85rem;color:var(--text-secondary);">
            {{ t('memory.tripleDesc') }}
          </p>
          <div class="grid-3">
            <input v-model="semSubject" :placeholder="t('memory.subjectPlaceholder')" />
            <input v-model="semPredicate" :placeholder="t('memory.predicatePlaceholder')" />
            <input v-model="semObject" :placeholder="t('memory.objectPlaceholder')" />
          </div>
          <button
            class="btn btn-primary"
            :disabled="!semSubject.trim() || !semPredicate.trim() || !semObject.trim() || addingSem"
            @click="doAddSemantic"
          >
            {{ addingSem ? t('memory.saving') : t('memory.saveTriple') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Activation Flow Tab -->
    <div v-if="tab === 'flow'">
      <div class="card">
        <h3 class="card-title">{{ t('memory.activationFlowTab') }}</h3>
        <div v-if="flowLoading" style="text-align:center;padding:40px;">
          <span class="pulse">⏳</span>
        </div>
        <div v-else-if="flowFoci.length && flowMemories.length" style="margin-top:12px;">
          <ActivationSankey
            :foci="flowFoci"
            :activated-memories="flowMemories"
          />
        </div>
        <div v-else style="text-align:center;padding:40px;color:var(--text-muted);font-size:0.85rem;">
          {{ t('framework.noDecompositionData') }}
        </div>
      </div>
    </div>
  </div>
</template>
