<script setup>
import { ref, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api/index.js'

const { t } = useI18n()
const loading = ref(true)
const error = ref('')
const items = ref([])
const total = ref(0)
const q = ref('')
const tiers = ref({})
const tab = ref('search')

async function loadTiers() {
  try { tiers.value = await api.memoryTiers() } catch (e) { /* */ }
}
async function doSearch() {
  loading.value = true; error.value = ''
  try {
    const d = await api.memoryList(50, 0, q.value)
    items.value = d.items; total.value = d.total
  } catch (e) { error.value = e.message }
  finally { loading.value = false }
}
async function doDelete(id) {
  if (!confirm('Delete ' + id + '?')) return
  try {
    await api.memoryDelete(id)
    items.value = items.value.filter(m => m.id !== id)
  } catch (e) { error.value = e.message }
}
onMounted(() => { loadTiers(); doSearch() })
const tlist = computed(() => tiers.value?.tiers ? Object.values(tiers.value.tiers) : [])
</script>

<template>
<div class="mv">
  <div class="ph"><h2>Memory / Ji Yi Ku</h2><p class="st">Search, browse, and manage three-tier memory</p></div>
  <div class="tabs">
    <button :class="{a:tab==='search'}" @click="tab='search'">Search</button>
    <button :class="{a:tab==='tiers'}" @click="tab='tiers'">Tiers</button>
  </div>

  <div v-if="tab==='search'">
    <div class="sb">
      <input v-model="q" @keyup.enter="doSearch" placeholder="Search memories..." class="si" />
      <button @click="doSearch" class="btn">Search</button>
      <span class="cb">{{ total }} items</span>
    </div>
    <div v-if="loading" class="sm">Loading...</div>
    <div v-else-if="error" class="sm err">Error: {{ error }}</div>
    <div v-else-if="items.length===0" class="sm">No results</div>
    <div v-else class="ml">
      <div v-for="m in items" :key="m.id" class="mc">
        <div class="ct">{{ m.content }}</div>
        <div class="mm">
          <span>score: {{ m.score.toFixed(3) }}</span>
          <span>{{ m.source }}</span>
          <button @click="doDelete(m.id)" class="bd">X</button>
        </div>
      </div>
    </div>
  </div>

  <div v-if="tab==='tiers'" class="tp">
    <div class="tg">
      <div v-for="t in tlist" :key="t.label" class="tc">
        <div class="tl">{{ t.label }}</div>
        <div class="tn">{{ t.count }}</div>
        <div class="td">{{ t.description }}</div>
      </div>
    </div>
    <div v-if="tiers?.total!==undefined" class="ts">
      <span>Total: {{ tiers.total }}</span>
      <span>Semantic: {{ tiers.semantic }}</span>
      <span>Skill: {{ tiers.skill }}</span>
    </div>
  </div>
</div>
</template>

<style scoped>
.mv{max-width:900px;margin:0 auto}
.ph{margin-bottom:20px}
.ph h2{margin:0}
.st{color:var(--text-muted);font-size:.9rem}
.tabs{display:flex;gap:4px;margin-bottom:16px}
.tabs button{padding:8px 20px;border:1px solid var(--border);border-radius:8px 8px 0 0;background:var(--bg-muted);color:var(--text);cursor:pointer}
.tabs button.a{background:var(--bg-card);border-bottom-color:var(--bg-card);font-weight:600}
.sb{display:flex;gap:8px;margin-bottom:16px;align-items:center}
.si{flex:1;padding:8px 12px;border:1px solid var(--border);border-radius:8px;background:var(--bg-card);color:var(--text)}
.cb{font-size:.85rem;color:var(--text-muted)}
.ml{display:flex;flex-direction:column;gap:10px}
.mc{background:var(--bg-card);border-radius:10px;padding:14px 16px}
.ct{font-size:.9rem;line-height:1.5;margin-bottom:8px}
.mm{display:flex;align-items:center;gap:12px;font-size:.8rem;color:var(--text-muted)}
.bd{padding:2px 8px;border:1px solid #e53935;border-radius:4px;background:none;color:#e53935;cursor:pointer;font-size:.75rem}
.tg{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:16px;margin-bottom:20px}
.tc{background:var(--bg-card);border-radius:12px;padding:20px;text-align:center}
.tl{font-size:.85rem;color:var(--text-muted);margin-bottom:8px}
.tn{font-size:2.5rem;font-weight:700;color:#2196F3}
.td{font-size:.8rem;color:var(--text-muted);margin-top:8px}
.ts{display:flex;gap:16px;font-size:.85rem;color:var(--text-muted);padding:12px;background:var(--bg-muted);border-radius:8px}
.sm{text-align:center;padding:40px;color:var(--text-muted)}
.sm.err{color:#e53935}
.btn{padding:6px 16px;border:1px solid var(--border);border-radius:8px;background:var(--bg-card);color:var(--text);cursor:pointer}
.btn:hover{background:var(--bg-muted)}
</style>
