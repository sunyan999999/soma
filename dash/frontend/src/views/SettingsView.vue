<script setup>
import { ref, inject, computed, onMounted } from 'vue'
import { api } from '../api'

const toast = inject('toast')

const loading = ref(true)
const saving = ref(false)
const llmConfig = ref(null)
const selectedProviderId = ref('')
const showKey = ref(false)

// Edit form state
const editKey = ref('')
const editModel = ref('')
const editBaseUrl = ref('')

const providerList = computed(() => {
  if (!llmConfig.value) return []
  return Object.entries(llmConfig.value.providers).map(([id, p]) => ({
    id,
    ...p,
  }))
})

const currentProvider = computed(() => {
  return providerList.value.find(p => p.id === llmConfig.value?.current_provider)
})

const selectedProvider = computed(() => {
  return providerList.value.find(p => p.id === selectedProviderId.value)
})

const isCurrentSelected = computed(() => {
  return selectedProviderId.value === llmConfig.value?.current_provider
})

function selectProvider(id) {
  selectedProviderId.value = id
  const p = providerList.value.find(x => x.id === id)
  if (p) {
    editKey.value = p.has_key ? '' : ''
    editModel.value = p.model || ''
    editBaseUrl.value = p.base_url || ''
  }
  showKey.value = false
}

async function loadConfig() {
  loading.value = true
  try {
    llmConfig.value = await api.configLLM()
    selectedProviderId.value = llmConfig.value.current_provider
    const p = providerList.value.find(x => x.id === selectedProviderId.value)
    if (p) {
      editModel.value = p.model || ''
      editBaseUrl.value = p.base_url || ''
    }
  } catch (e) {
    toast(`加载配置失败: ${e.message}`, 'error')
  } finally {
    loading.value = false
  }
}

async function saveProvider() {
  saving.value = true
  try {
    const result = await api.configUpdateProvider(
      selectedProviderId.value,
      editKey.value || null,
      editModel.value || null,
      editBaseUrl.value || null
    )
    if (result.provider) {
      llmConfig.value = {
        ...llmConfig.value,
        current_provider: result.current_provider,
        providers: {
          ...llmConfig.value.providers,
          [result.provider_id]: {
            ...llmConfig.value.providers[result.provider_id],
            ...result.provider,
            has_key: !!result.provider.api_key,
          },
        },
      }
    }
    editKey.value = ''
    toast('配置已保存', 'success')
  } catch (e) {
    toast(`保存失败: ${e.message}`, 'error')
  } finally {
    saving.value = false
  }
}

async function switchProvider() {
  if (isCurrentSelected.value) return
  try {
    const result = await api.configSwitchProvider(selectedProviderId.value)
    llmConfig.value = {
      ...llmConfig.value,
      current_provider: result.current_provider,
    }
    toast(`已切换至 ${result.provider.name}`, 'success')
  } catch (e) {
    toast(`切换失败: ${e.message}`, 'error')
  }
}

function maskKey(key) {
  if (!key) return ''
  if (key === '****') return '****'
  if (key.length > 8) return key.slice(0, 6) + '****' + key.slice(-4)
  return '****'
}

onMounted(loadConfig)
</script>

<template>
  <div>
    <h1 class="page-title">⚙️ 设置</h1>
    <p class="page-subtitle">
      配置大模型提供商，切换后 Chat 页面将自动使用所选模型
    </p>

    <!-- Status Banner -->
    <div
      v-if="llmConfig?.mock_mode"
      style="margin-bottom:24px;padding:14px 20px;border-radius:12px;background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.2);display:flex;align-items:center;gap:12px;"
    >
      <span style="font-size:1.3rem;">⚡</span>
      <div>
        <div style="font-weight:600;color:var(--amber);font-size:0.9rem;">
          Mock 模式 — 未检测到可用的 API Key
        </div>
        <div style="font-size:0.8rem;color:var(--text-muted);margin-top:2px;">
          选择一个提供商并填写 API Key 后，将自动切换至真实模型。
        </div>
      </div>
    </div>
    <div
      v-else-if="llmConfig && !llmConfig.mock_mode"
      style="margin-bottom:24px;padding:14px 20px;border-radius:12px;background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.2);display:flex;align-items:center;gap:12px;"
    >
      <span style="font-size:1.3rem;">🧠</span>
      <div>
        <div style="font-weight:600;color:var(--emerald);font-size:0.9rem;">
          真实模型模式 — {{ currentProvider?.name }}
        </div>
        <div style="font-size:0.8rem;color:var(--text-muted);margin-top:2px;">
          Chat 页面将调用真实 LLM 进行分析。
        </div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="gap-md">
      <div class="skeleton" style="height:48px;" />
      <div class="skeleton" style="height:200px;" />
    </div>

    <div v-if="!loading && llmConfig" class="gap-lg">
      <!-- Current Status Card -->
      <div class="card">
        <div class="card-header">
          <span class="card-title">📡 当前状态</span>
          <span
            class="badge"
            :class="currentProvider?.has_key ? 'badge-emerald' : 'badge-amber'"
          >
            {{ currentProvider?.has_key ? 'Key 已配置' : '未配置 Key' }}
          </span>
        </div>
        <div class="row" style="gap:24px;flex-wrap:wrap;">
          <div>
            <div style="font-size:0.75rem;color:var(--text-muted);margin-bottom:4px;">当前模型</div>
            <div style="font-weight:600;">{{ currentProvider?.name || '-' }}</div>
          </div>
          <div>
            <div style="font-size:0.75rem;color:var(--text-muted);margin-bottom:4px;">Model ID</div>
            <div style="font-weight:600;font-family:monospace;font-size:0.85rem;">
              {{ currentProvider?.model || '未设置' }}
            </div>
          </div>
          <div v-if="currentProvider?.base_url">
            <div style="font-size:0.75rem;color:var(--text-muted);margin-bottom:4px;">Base URL</div>
            <div style="font-weight:600;font-family:monospace;font-size:0.8rem;">
              {{ currentProvider.base_url }}
            </div>
          </div>
        </div>
      </div>

      <!-- Provider Grid -->
      <section>
        <h2 style="font-size:1.1rem;margin-bottom:16px;">🔌 选择提供商</h2>
        <div class="provider-grid">
          <button
            v-for="p in providerList"
            :key="p.id"
            class="provider-card"
            :class="{
              'provider-selected': selectedProviderId === p.id,
              'provider-active': llmConfig.current_provider === p.id,
            }"
            @click="selectProvider(p.id)"
          >
            <div class="row row-between" style="margin-bottom:8px;">
              <span style="font-weight:600;font-size:0.9rem;">{{ p.name }}</span>
              <span
                v-if="p.has_key"
                style="font-size:0.65rem;padding:2px 8px;border-radius:10px;background:rgba(16,185,129,0.12);color:var(--emerald);"
              >
                Key
              </span>
            </div>
            <div style="font-size:0.7rem;color:var(--text-muted);line-height:1.4;">
              {{ p.description }}
            </div>
            <div style="margin-top:8px;font-size:0.7rem;font-family:monospace;color:var(--text-secondary);opacity:0.7;">
              {{ p.model }}
            </div>
            <div
              v-if="llmConfig.current_provider === p.id"
              style="margin-top:8px;font-size:0.7rem;color:var(--accent);font-weight:600;"
            >
              ✓ 当前使用
            </div>
          </button>
        </div>
      </section>

      <!-- Config Form -->
      <section v-if="selectedProvider" class="card">
        <div class="card-header">
          <span class="card-title">
            {{ selectedProvider.name }} 配置
          </span>
          <div class="row" style="gap:8px;">
            <button
              v-if="!isCurrentSelected"
              class="btn btn-primary btn-sm"
              @click="switchProvider"
            >
              切换至此模型
            </button>
            <span
              v-else
              class="badge badge-accent"
              style="padding:6px 14px;"
            >
              当前使用中
            </span>
          </div>
        </div>

        <div class="gap-md">
          <!-- API Key -->
          <div>
            <label style="font-size:0.8rem;font-weight:500;color:var(--text-secondary);display:block;margin-bottom:6px;">
              API Key
              <span style="color:var(--text-muted);font-weight:400;">
                — {{ selectedProvider.has_key ? '已保存' : '输入新 Key' }}
              </span>
            </label>
            <div class="row" style="gap:8px;">
              <div style="position:relative;flex:1;">
                <input
                  v-model="editKey"
                  :type="showKey ? 'text' : 'password'"
                  :placeholder="selectedProvider.has_key ? 'Key 已保存，留空不修改' : '输入 API Key...'"
                  style="padding-right:44px;"
                />
              </div>
              <button
                class="btn btn-secondary btn-sm"
                @click="showKey = !showKey"
                style="min-width:44px;justify-content:center;"
              >
                {{ showKey ? '🙈' : '👁' }}
              </button>
            </div>
          </div>

          <!-- Model -->
          <div>
            <label style="font-size:0.8rem;font-weight:500;color:var(--text-secondary);display:block;margin-bottom:6px;">
              Model ID
            </label>
            <input
              v-model="editModel"
              :placeholder="selectedProvider.model || '输入模型 ID...'"
            />
          </div>

          <!-- Base URL -->
          <div>
            <label style="font-size:0.8rem;font-weight:500;color:var(--text-secondary);display:block;margin-bottom:6px;">
              Base URL
              <span style="color:var(--text-muted);font-weight:400;">
                — 留空使用默认
              </span>
            </label>
            <input
              v-model="editBaseUrl"
              :placeholder="selectedProvider.base_url || 'https://api.openai.com/v1'"
            />
          </div>

          <div class="row row-between" style="margin-top:4px;">
            <span style="font-size:0.75rem;color:var(--text-muted);">
              API Key 将安全存储至本地配置文件
            </span>
            <button
              class="btn btn-primary"
              :disabled="saving"
              @click="saveProvider"
            >
              {{ saving ? '保存中...' : '💾 保存配置' }}
            </button>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.provider-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

@media (max-width: 900px) {
  .provider-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 600px) {
  .provider-grid {
    grid-template-columns: 1fr;
  }
}

.provider-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px;
  text-align: left;
  cursor: pointer;
  transition: all var(--transition);
  color: var(--text-primary);
  font-family: var(--font);
  font-size: 0.85rem;
}

.provider-card:hover {
  background: var(--bg-card-hover);
  border-color: rgba(255, 255, 255, 0.15);
  transform: translateY(-1px);
}

.provider-selected {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 2px var(--accent-glow);
}

.provider-active {
  background: rgba(99, 102, 241, 0.06);
}
</style>
