<script setup>
import { ref, inject, computed } from 'vue'
import { api } from '../api'

const toast = inject('toast')

const problem = ref('')
const loading = ref(false)
const result = ref(null)
const activeFocusIdx = ref(0)

const phaseLabel = ref('')
const phaseMessages = ['拆解问题维度...', '激活记忆资粮...', '综合生成答案...']
let phaseTimer = null

async function analyze() {
  if (!problem.value.trim()) return
  loading.value = true
  result.value = null
  phaseLabel.value = phaseMessages[0]
  let idx = 0
  phaseTimer = setInterval(() => {
    idx = (idx + 1) % phaseMessages.length
    phaseLabel.value = phaseMessages[idx]
  }, 800)

  try {
    const data = await api.chat(problem.value)
    result.value = data
    toast('分析完成', 'success')
  } catch (e) {
    toast(`分析失败: ${e.message}`, 'error')
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
    <h1 class="page-title">智者对话</h1>
    <p class="page-subtitle">
      输入问题，SOMA 将运用思维框架拆解并深度分析
      <span
        v-if="result?.mock_mode"
        style="display:inline-block;margin-left:8px;padding:2px 10px;border-radius:12px;background:rgba(245,158,11,0.15);color:var(--amber);font-size:0.75rem;font-weight:600;"
      >
        ⚡ MOCK 模式
      </span>
    </p>

    <!-- Input Area -->
    <div class="card" style="margin-bottom:24px;">
      <textarea
        v-model="problem"
        placeholder="例如：为什么新产品增长停滞？用户为何流失？如何打破组织惯性？"
        style="min-height:80px;font-size:1rem;"
        @keydown.ctrl.enter="analyze"
      />
      <div class="row row-between" style="margin-top:12px;">
        <span style="font-size:0.75rem;color:var(--text-muted);">
          Ctrl + Enter 快速发送
        </span>
        <button
          class="btn btn-primary"
          :disabled="!problem.trim() || loading"
          @click="analyze"
        >
          <span v-if="loading" class="pulse">🔍</span>
          <span v-else>🔍</span>
          {{ loading ? phaseLabel : '深度分析' }}
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
      <p style="font-size:1.05rem;">输入一个问题，开启深度思考</p>
      <p style="font-size:0.8rem;margin-top:4px;">
        SOMA 将自动拆解问题、激活相关记忆、综合生成回答
      </p>
    </div>

    <!-- Results -->
    <div v-if="hasResult" class="gap-lg">
      <!-- Foci -->
      <section>
        <div class="row row-between mb-md">
          <h2 style="font-size:1.1rem;">🔬 问题拆解</h2>
          <span style="font-size:0.8rem;color:var(--text-muted);">
            {{ result.foci.length }} 个分析维度
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
              <span class="badge badge-accent">{{ f.law_id }}</span>
              <span class="badge badge-cyan">权重 {{ f.weight.toFixed(2) }}</span>
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

      <!-- Activated Memories -->
      <section v-if="result.activated_memories.length">
        <div class="row row-between mb-md">
          <h2 style="font-size:1.1rem;">🧩 激活的记忆资粮</h2>
          <span style="font-size:0.8rem;color:var(--text-muted);">
            {{ result.activated_memories.length }} 条相关记忆
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
                  分数 {{ am.activation_score.toFixed(3) }}
                </span>
                <span style="font-size:0.75rem;color:var(--text-muted);">
                  重要度 {{ am.importance.toFixed(2) }}
                </span>
              </div>
            </div>
            <p style="font-size:0.85rem;margin-top:12px;color:var(--text-secondary);line-height:1.7;">
              {{ am.content.slice(0, 200) }}{{ am.content.length > 200 ? '...' : '' }}
            </p>
          </div>
        </div>
      </section>

      <!-- Answer -->
      <section>
        <h2 style="font-size:1.1rem;margin-bottom:12px;">📝 智者回答</h2>
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
          <div style="font-size:0.75rem;color:var(--text-muted);">情节记忆</div>
        </div>
        <div class="card" style="text-align:center;">
          <div style="font-size:1.8rem;font-weight:700;color:var(--cyan);">
            {{ result.memory_stats.semantic }}
          </div>
          <div style="font-size:0.75rem;color:var(--text-muted);">语义三元组</div>
        </div>
        <div class="card" style="text-align:center;">
          <div style="font-size:1.8rem;font-weight:700;color:var(--amber);">
            {{ result.memory_stats.skill }}
          </div>
          <div style="font-size:0.75rem;color:var(--text-muted);">技能模式</div>
        </div>
      </div>
    </div>
  </div>
</template>
