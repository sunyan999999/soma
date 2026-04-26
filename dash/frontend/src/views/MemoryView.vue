<script setup>
import { ref, inject, onMounted } from 'vue'
import { api } from '../api'

const toast = inject('toast')

const stats = ref({ episodic: 0, semantic: 0, skill: 0 })
const searchQuery = ref('')
const searchResults = ref([])
const searching = ref(false)

// Add form
const addContent = ref('')
const addDomain = ref('通用')
const addType = ref('笔记')
const addImportance = ref(0.7)
const adding = ref(false)

// Semantic form
const semSubject = ref('')
const semPredicate = ref('')
const semObject = ref('')
const addingSem = ref(false)

// Tab state
const tab = ref('search') // 'search' | 'add' | 'semantic'

onMounted(async () => {
  try { stats.value = await api.memoryStats() } catch {}
})

async function doSearch() {
  if (!searchQuery.value.trim()) return
  searching.value = true
  try {
    const data = await api.memorySearch(searchQuery.value)
    searchResults.value = data.results
  } catch (e) {
    toast(`搜索失败: ${e.message}`, 'error')
  } finally {
    searching.value = false
  }
}

async function doAddMemory() {
  if (!addContent.value.trim()) return
  adding.value = true
  try {
    await api.memoryAdd(addContent.value, addDomain.value, addType.value, addImportance.value)
    toast('记忆已保存', 'success')
    addContent.value = ''
    stats.value = await api.memoryStats()
  } catch (e) {
    toast(`保存失败: ${e.message}`, 'error')
  } finally {
    adding.value = false
  }
}

async function doAddSemantic() {
  if (!semSubject.value.trim() || !semPredicate.value.trim() || !semObject.value.trim()) return
  addingSem.value = true
  try {
    await api.memoryAddSemantic(semSubject.value, semPredicate.value, semObject.value)
    toast('三元组已保存', 'success')
    semSubject.value = ''
    semPredicate.value = ''
    semObject.value = ''
    stats.value = await api.memoryStats()
  } catch (e) {
    toast(`保存失败: ${e.message}`, 'error')
  } finally {
    addingSem.value = false
  }
}
</script>

<template>
  <div>
    <h1 class="page-title">记忆管理</h1>
    <p class="page-subtitle">浏览、搜索和注入记忆资粮</p>

    <!-- Stats -->
    <div class="grid-3" style="margin-bottom:24px;">
      <div class="card" style="text-align:center;">
        <div style="font-size:2rem;font-weight:700;color:var(--accent);">{{ stats.episodic }}</div>
        <div style="font-size:0.8rem;color:var(--text-muted);">情节记忆</div>
      </div>
      <div class="card" style="text-align:center;">
        <div style="font-size:2rem;font-weight:700;color:var(--cyan);">{{ stats.semantic }}</div>
        <div style="font-size:0.8rem;color:var(--text-muted);">语义三元组</div>
      </div>
      <div class="card" style="text-align:center;">
        <div style="font-size:2rem;font-weight:700;color:var(--amber);">{{ stats.skill }}</div>
        <div style="font-size:0.8rem;color:var(--text-muted);">技能模式</div>
      </div>
    </div>

    <!-- Tab Switcher -->
    <div class="row" style="margin-bottom:20px;">
      <button class="btn" :class="tab === 'search' ? 'btn-primary' : 'btn-secondary'" @click="tab = 'search'">🔍 搜索</button>
      <button class="btn" :class="tab === 'add' ? 'btn-primary' : 'btn-secondary'" @click="tab = 'add'">➕ 情节记忆</button>
      <button class="btn" :class="tab === 'semantic' ? 'btn-primary' : 'btn-secondary'" @click="tab = 'semantic'">🔗 语义三元组</button>
    </div>

    <!-- Search Tab -->
    <div v-if="tab === 'search'">
      <div class="card">
        <div class="row" style="gap:12px;">
          <input
            v-model="searchQuery"
            placeholder="输入关键词搜索记忆..."
            @keydown.enter="doSearch"
            style="flex:1;"
          />
          <button class="btn btn-primary" :disabled="searching" @click="doSearch">
            {{ searching ? '搜索中...' : '搜索' }}
          </button>
        </div>
      </div>

      <div v-if="searchResults.length" class="gap-md mt-lg">
        <p style="font-size:0.85rem;color:var(--text-muted);">
          找到 {{ searchResults.length }} 条结果
        </p>
        <div
          v-for="(r, i) in searchResults"
          :key="r.memory_id || i"
          class="card"
        >
          <div class="row row-between">
            <span class="badge badge-accent">{{ r.source }}</span>
            <div class="row" style="gap:16px;font-size:0.75rem;color:var(--text-muted);">
              <span>分数 {{ (r.activation_score || 0).toFixed(3) }}</span>
              <span>重要度 {{ (r.importance || 0).toFixed(2) }}</span>
            </div>
          </div>
          <p style="font-size:0.88rem;margin-top:12px;color:var(--text-secondary);line-height:1.7;">
            {{ r.content_preview }}
          </p>
        </div>
      </div>

      <div v-if="searchQuery && !searching && !searchResults.length" style="text-align:center;padding:40px;color:var(--text-muted);">
        未找到相关记忆
      </div>
    </div>

    <!-- Add Episodic Tab -->
    <div v-if="tab === 'add'">
      <div class="card">
        <div class="gap-md">
          <textarea
            v-model="addContent"
            placeholder="输入知识片段、案例、理论..."
            style="min-height:120px;"
          />
          <div class="grid-3">
            <div>
              <label style="font-size:0.8rem;color:var(--text-muted);display:block;margin-bottom:4px;">领域</label>
              <input v-model="addDomain" placeholder="哲学/思维/管理..." />
            </div>
            <div>
              <label style="font-size:0.8rem;color:var(--text-muted);display:block;margin-bottom:4px;">类型</label>
              <input v-model="addType" placeholder="理论/方法论/案例..." />
            </div>
            <div>
              <label style="font-size:0.8rem;color:var(--text-muted);display:block;margin-bottom:4px;">
                重要性: {{ addImportance.toFixed(2) }}
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
            {{ adding ? '保存中...' : '保存记忆' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Add Semantic Tab -->
    <div v-if="tab === 'semantic'">
      <div class="card">
        <div class="gap-md">
          <p style="font-size:0.85rem;color:var(--text-secondary);">
            语义三元组: <strong>主语</strong> — 谓词 → <strong>宾语</strong>
          </p>
          <div class="grid-3">
            <input v-model="semSubject" placeholder="主语 (如: 增长)" />
            <input v-model="semPredicate" placeholder="谓词 (如: 依赖)" />
            <input v-model="semObject" placeholder="宾语 (如: 创新)" />
          </div>
          <button
            class="btn btn-primary"
            :disabled="!semSubject.trim() || !semPredicate.trim() || !semObject.trim() || addingSem"
            @click="doAddSemantic"
          >
            {{ addingSem ? '保存中...' : '保存三元组' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
