<script setup>
import { ref, inject, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api'
import DecompositionGraph from '../components/DecompositionGraph.vue'
import ActivationSankey from '../components/ActivationSankey.vue'
import PromptPreview from '../components/PromptPreview.vue'

const { t } = useI18n()
function lawName(id) { return t(`laws.${id}`) || id }
const toast = inject('toast')

const problem = ref('')
const loading = ref(false)
const result = ref(null)
const activeFocusIdx = ref(0)
const showDecompTree = ref(false)
const showActivationFlow = ref(false)

const phaseLabel = ref('')
const phaseMessages = computed(() => [
  t('chat.decomposing'),
  t('chat.activating'),
  t('chat.synthesizing'),
])
let phaseTimer = null

// 规律名映射供图表组件使用
const lawNames = computed(() => ({
  first_principles: t('laws.first_principles'),
  systems_thinking: t('laws.systems_thinking'),
  contradiction_analysis: t('laws.contradiction_analysis'),
  pareto_principle: t('laws.pareto_principle'),
  inversion: t('laws.inversion'),
  analogical_reasoning: t('laws.analogical_reasoning'),
  evolutionary_lens: t('laws.evolutionary_lens'),
}))

async function analyze() {
  if (!problem.value.trim()) return
  loading.value = true
  result.value = null
  showDecompTree.value = false
  showActivationFlow.value = false
  phaseLabel.value = phaseMessages.value[0]
  let idx = 0
  phaseTimer = setInterval(() => {
    idx = (idx + 1) % phaseMessages.value.length
    phaseLabel.value = phaseMessages.value[idx]
  }, 800)

  try {
    const data = await api.chat(problem.value)
    result.value = data
    toast(t('chat.analysisComplete'), 'success')
  } catch (e) {
    toast(`${t('chat.analysisFailed')}: ${e.message}`, 'error')
  } finally {
    clearInterval(phaseTimer)
    loading.value = false
    phaseLabel.value = ''
  }
}

const hasResult = computed(() => result.value !== null)
</script>

<template>
  <div>
    <h1 class="page-title">{{ t('chat.title') }}</h1>
    <p class="page-subtitle">
      {{ t('chat.subtitle') }}
      <span
        v-if="result?.mock_mode"
        style="display:inline-block;margin-left:8px;padding:2px 10px;border-radius:12px;background:rgba(245,158,11,0.15);color:var(--amber);font-size:0.75rem;font-weight:600;"
      >
        {{ t('chat.mockMode') }}
      </span>
    </p>

    <!-- Input Area -->
    <div class="card" style="margin-bottom:24px;">
      <textarea
        v-model="problem"
        :placeholder="t('chat.placeholder')"
        style="min-height:80px;font-size:1rem;"
        @keydown.ctrl.enter="analyze"
      />
      <div class="row row-between" style="margin-top:12px;">
        <span style="font-size:0.75rem;color:var(--text-muted);">
          {{ t('chat.ctrlEnter') }}
        </span>
        <button
          class="btn btn-primary"
          :disabled="!problem.trim() || loading"
          @click="analyze"
        >
          <span v-if="loading" class="pulse">🔍</span>
          <span v-else>🔍</span>
          {{ loading ? phaseLabel : t('chat.analyze') }}
        </button>
      </div>
    </div>

    <!-- Loading Skeleton -->
    <div v-if="loading && !result" class="gap-md">
      <div class="skeleton" style="height:60px;" />
      <div class="skeleton" style="height:100px;" />
      <div class="skeleton" style="height:200px;" />
    </div>

    <!-- Empty State -->
    <div
      v-if="!loading && !result"
      style="text-align:center;padding:80px 20px;color:var(--text-muted);"
    >
      <div style="font-size:3rem;margin-bottom:16px;">🧠</div>
      <p style="font-size:1.05rem;">{{ t('chat.emptyTitle') }}</p>
      <p style="font-size:0.8rem;margin-top:4px;">
        {{ t('chat.emptyDesc') }}
      </p>
    </div>

    <!-- Results -->
    <div v-if="hasResult" class="gap-lg">
      <!-- Foci -->
      <section>
        <div class="row row-between mb-md">
          <h2 style="font-size:1.1rem;">{{ t('chat.decomposition') }}</h2>
          <span style="font-size:0.8rem;color:var(--text-muted);">
            {{ result.foci.length }} {{ t('chat.dimensions') }}
          </span>
        </div>
        <div class="grid-2">
          <div
            v-for="(f, i) in result.foci"
            :key="f.law_id"
            class="card"
            :style="{
              cursor: 'pointer',
              borderColor: activeFocusIdx === i ? 'var(--border-active)' : 'var(--border)',
            }"
            @click="activeFocusIdx = i"
          >
            <div class="row row-between">
              <span class="badge badge-accent">{{ lawName(f.law_id) }}</span>
              <span class="badge badge-cyan">{{ t('chat.weight') }} {{ f.weight.toFixed(2) }}</span>
            </div>
            <p style="font-size:0.85rem;margin-top:12px;color:var(--text-secondary);line-height:1.6;">
              {{ f.dimension.slice(0, 120) }}...
            </p>
            <div style="margin-top:10px;font-size:0.75rem;color:var(--text-muted);">
              {{ f.rationale }}
            </div>
          </div>
        </div>
      </section>

      <!-- 思维拆解树 -->
      <section v-if="result.foci.length">
        <div class="card" style="margin-top:8px;padding:10px 16px;">
          <div style="display:flex;align-items:center;justify-content:space-between;cursor:pointer;user-select:none;" @click="showDecompTree = !showDecompTree">
            <span style="font-size:0.88rem;font-weight:600;color:var(--text-secondary);">{{ showDecompTree ? '▾' : '▸' }} {{ t('chat.decompositionTree') }}</span>
          </div>
          <div v-if="showDecompTree" style="padding:8px 12px 12px;">
            <DecompositionGraph
              :foci="result.foci"
              :problem="result.problem"
              :law-names="lawNames"
            />
          </div>
        </div>
      </section>

      <!-- Activated Memories -->
      <section v-if="result.activated_memories.length">
        <div class="row row-between mb-md">
          <h2 style="font-size:1.1rem;">{{ t('chat.activatedMemories') }}</h2>
          <span style="font-size:0.8rem;color:var(--text-muted);">
            {{ result.activated_memories.length }} {{ t('chat.relatedMemories') }}
          </span>
        </div>
        <div class="grid-2">
          <div
            v-for="am in result.activated_memories"
            :key="am.id"
            class="card"
          >
            <div class="row row-between">
              <span class="badge badge-amber">{{ am.source }}</span>
              <div class="row" style="gap:16px;">
                <span style="font-size:0.75rem;color:var(--text-muted);">
                  {{ t('chat.score') }} {{ am.activation_score.toFixed(3) }}
                </span>
                <span style="font-size:0.75rem;color:var(--text-muted);">
                  {{ t('chat.importance') }} {{ am.importance.toFixed(2) }}
                </span>
              </div>
            </div>
            <p style="font-size:0.85rem;margin-top:12px;color:var(--text-secondary);line-height:1.7;">
              {{ am.content.slice(0, 200) }}{{ am.content.length > 200 ? '...' : '' }}
            </p>
          </div>
        </div>
      </section>

      <!-- 记忆激活流 -->
      <section v-if="result.foci.length && result.activated_memories.length">
        <div class="card" style="margin-top:8px;padding:10px 16px;">
          <div style="display:flex;align-items:center;justify-content:space-between;cursor:pointer;user-select:none;" @click="showActivationFlow = !showActivationFlow">
            <span style="font-size:0.88rem;font-weight:600;color:var(--text-secondary);">{{ showActivationFlow ? '▾' : '▸' }} {{ t('chat.activationFlow') }}</span>
          </div>
          <div v-if="showActivationFlow" style="padding:8px 12px 12px;">
            <ActivationSankey
              :foci="result.foci"
              :activated-memories="result.activated_memories"
            />
          </div>
        </div>
      </section>

      <!-- Prompt 预览 -->
      <section v-if="result.prompt" style="margin-top:8px;">
        <PromptPreview :prompt="result.prompt" />
      </section>

      <!-- Answer -->
      <section>
        <h2 style="font-size:1.1rem;margin-bottom:12px;">{{ t('chat.answer') }}</h2>
        <div class="card answer-content" v-html="result.answer
          .replace(/^## (.+)$/gm, '<h2>$1</h2>')
          .replace(/^### (.+)$/gm, '<h3>$1</h3>')
          .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
          .replace(/^- (.+)$/gm, '<li>$1</li>')
          .replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')
          .replace(/\n/g, '<br>')
        " />
      </section>

      <!-- System Status Sidebar -->
      <div class="grid-3" style="margin-top:32px;">
        <div class="card" style="text-align:center;">
          <div style="font-size:1.8rem;font-weight:700;color:var(--accent);">
            {{ result.memory_stats.episodic }}
          </div>
          <div style="font-size:0.75rem;color:var(--text-muted);">{{ t('chat.episodicMemory') }}</div>
        </div>
        <div class="card" style="text-align:center;">
          <div style="font-size:1.8rem;font-weight:700;color:var(--cyan);">
            {{ result.memory_stats.semantic }}
          </div>
          <div style="font-size:0.75rem;color:var(--text-muted);">{{ t('chat.semanticTriples') }}</div>
        </div>
        <div class="card" style="text-align:center;">
          <div style="font-size:1.8rem;font-weight:700;color:var(--amber);">
            {{ result.memory_stats.skill }}
          </div>
          <div style="font-size:0.75rem;color:var(--text-muted);">{{ t('chat.skillPatterns') }}</div>
        </div>
      </div>
    </div>
  </div>
</template>
