<script setup>
import { ref, inject, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api'

const { t } = useI18n()
const toast = inject('toast')

const loading = ref(true)
const registering = ref(false)
const experts = ref([])
const orchStatus = ref(null)

// Register form
const newAgentId = ref('')
const newExpertise = ref([])
const newExpertiseInput = ref('')
const newDescription = ref('')

function addExpertise() {
  const v = newExpertiseInput.value.trim()
  if (v && !newExpertise.value.includes(v)) {
    newExpertise.value.push(v)
  }
  newExpertiseInput.value = ''
}

function removeExpertise(item) {
  newExpertise.value = newExpertise.value.filter(e => e !== item)
}

function handleExpertiseKey(e) {
  if (e.key === 'Enter') {
    e.preventDefault()
    addExpertise()
  }
}

async function loadData() {
  loading.value = true
  try {
    const expResult = await api.expertsList()
    experts.value = expResult.experts || []
    orchStatus.value = await api.orchestrationStatus()
  } catch (e) {
    toast(`${e.message}`, 'error')
  } finally {
    loading.value = false
  }
}

async function register() {
  if (!newAgentId.value.trim() || newExpertise.value.length === 0) return
  registering.value = true
  try {
    await api.expertRegister(
      newAgentId.value.trim(),
      [...newExpertise.value],
      newDescription.value.trim(),
    )
    toast(t('experts.registered'), 'success')
    newAgentId.value = ''
    newExpertise.value = []
    newDescription.value = ''
    await loadData()
  } catch (e) {
    toast(`${t('experts.registerFailed')}: ${e.message}`, 'error')
  } finally {
    registering.value = false
  }
}

async function remove(agentId) {
  if (!confirm(t('experts.removeConfirm'))) return
  try {
    await api.expertRemove(agentId)
    toast(t('experts.removed'), 'success')
    await loadData()
  } catch (e) {
    toast(`${t('experts.removeFailed')}: ${e.message}`, 'error')
  }
}

function formatPercent(v) {
  if (v === undefined || v === null) return '...'
  return (v * 100).toFixed(0) + '%'
}

onMounted(loadData)
</script>

<template>
  <div>
    <h1 class="page-title">{{ t('experts.title') }}</h1>
    <p class="page-subtitle">{{ t('experts.subtitle') }}</p>

    <!-- Orchestration Status -->
    <div v-if="orchStatus" class="card" style="margin-bottom:24px;">
      <h2 style="font-size:1rem;margin-bottom:12px;">{{ t('experts.orchestrationStatus') }}</h2>
      <div class="grid-3">
        <div style="text-align:center;">
          <div style="font-size:1.6rem;font-weight:700;color:var(--accent);">
            {{ orchStatus.agent_count }}
          </div>
          <div style="font-size:0.75rem;color:var(--text-muted);">{{ t('experts.currentExperts') }}</div>
        </div>
        <div style="text-align:center;">
          <div style="font-size:1.6rem;font-weight:700;color:var(--cyan);">
            {{ orchStatus.router_stats?.route_count || 0 }}
          </div>
          <div style="font-size:0.75rem;color:var(--text-muted);">{{ t('experts.routeCount') }}</div>
        </div>
        <div style="text-align:center;">
          <div style="font-size:1.6rem;font-weight:700;color:var(--amber);">
            {{ orchStatus.consensus_sessions || 0 }}
          </div>
          <div style="font-size:0.75rem;color:var(--text-muted);">{{ t('experts.consensusSessions') }}</div>
        </div>
      </div>
      <!-- Router stats detail -->
      <div v-if="orchStatus.router_stats" style="margin-top:16px;display:flex;gap:24px;font-size:0.78rem;color:var(--text-muted);">
        <span>{{ t('experts.l1HitRate') }}: {{ formatPercent(orchStatus.router_stats.l1_hit_rate) }}</span>
        <span>{{ t('experts.l2HitRate') }}: {{ formatPercent(orchStatus.router_stats.l2_hit_rate) }}</span>
        <span>{{ t('experts.fallbackRate') }}: {{ formatPercent(orchStatus.router_stats.fallback_rate) }}</span>
      </div>
    </div>

    <!-- Register Form -->
    <div class="card" style="margin-bottom:24px;">
      <h2 style="font-size:1rem;margin-bottom:16px;">{{ t('experts.registerTitle') }}</h2>
      <div style="display:flex;flex-direction:column;gap:12px;">
        <div>
          <label style="font-size:0.8rem;color:var(--text-muted);display:block;margin-bottom:4px;">{{ t('experts.agentId') }}</label>
          <input
            v-model="newAgentId"
            :placeholder="t('experts.agentIdPlaceholder')"
            style="width:100%;"
          />
        </div>
        <div>
          <label style="font-size:0.8rem;color:var(--text-muted);display:block;margin-bottom:4px;">{{ t('experts.expertise') }}</label>
          <div style="display:flex;gap:8px;">
            <input
              v-model="newExpertiseInput"
              :placeholder="t('experts.expertisePlaceholder')"
              style="flex:1;"
              @keydown="handleExpertiseKey"
            />
            <button class="btn btn-secondary" @click="addExpertise">{{ t('experts.addExpertise') }}</button>
          </div>
          <div v-if="newExpertise.length" style="display:flex;flex-wrap:wrap;gap:6px;margin-top:8px;">
            <span
              v-for="e in newExpertise"
              :key="e"
              class="badge badge-accent"
              style="cursor:pointer;"
              @click="removeExpertise(e)"
            >
              {{ e }} ✕
            </span>
          </div>
        </div>
        <div>
          <label style="font-size:0.8rem;color:var(--text-muted);display:block;margin-bottom:4px;">{{ t('experts.description') }}</label>
          <input
            v-model="newDescription"
            :placeholder="t('experts.descriptionPlaceholder')"
            style="width:100%;"
          />
        </div>
        <button
          class="btn btn-primary"
          :disabled="!newAgentId.trim() || newExpertise.length === 0 || registering"
          @click="register"
        >
          {{ registering ? t('experts.registering') : t('experts.register') }}
        </button>
      </div>
    </div>

    <!-- Expert List -->
    <div class="card">
      <h2 style="font-size:1rem;margin-bottom:16px;">{{ t('experts.currentExperts') }}</h2>

      <div v-if="loading" class="skeleton" style="height:120px;" />

      <div v-else-if="experts.length === 0" style="text-align:center;padding:40px 20px;color:var(--text-muted);">
        <div style="font-size:2rem;margin-bottom:8px;">🧠</div>
        <p>{{ t('experts.noExperts') }}</p>
        <p style="font-size:0.8rem;margin-top:4px;">{{ t('experts.noExpertsDesc') }}</p>
      </div>

      <div v-else style="display:flex;flex-direction:column;gap:12px;">
        <div
          v-for="expert in experts"
          :key="expert.agent_id"
          class="card"
          style="display:flex;align-items:center;justify-content:space-between;padding:12px 16px;"
        >
          <div style="flex:1;">
            <div style="display:flex;align-items:center;gap:8px;">
              <span style="font-weight:600;font-size:0.95rem;">{{ expert.agent_id }}</span>
              <span
                v-if="expert.is_default"
                class="badge badge-amber"
                style="font-size:0.7rem;"
              >
                {{ t('experts.defaultAgent') }}
              </span>
            </div>
            <div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:6px;">
              <span
                v-for="e in expert.expertise"
                :key="e"
                class="badge badge-accent"
                style="font-size:0.7rem;"
              >
                {{ e }}
              </span>
            </div>
            <div style="font-size:0.75rem;color:var(--text-muted);margin-top:4px;">
              {{ t('experts.sessionCount') }}: {{ expert.session_count }}
              &nbsp;|&nbsp;
              {{ t('experts.successRate') }}: {{ formatPercent(expert.success_rate) }}
            </div>
          </div>
          <button
            class="btn btn-secondary"
            style="padding:4px 12px;font-size:0.75rem;color:var(--danger);border-color:var(--danger);"
            @click="remove(expert.agent_id)"
          >
            {{ t('experts.remove') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
