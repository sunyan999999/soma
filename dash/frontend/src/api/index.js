const BASE = '/api'

// API Key 存储在 sessionStorage 中，由应用启动时通过 /api/auth/status 检测后提示输入
let API_KEY = sessionStorage.getItem('soma_api_key') || ''

/**
 * 初始化认证：检测是否需要 API Key，如需要则提示用户输入
 * 返回 true 表示已认证或无需认证，false 表示需要认证但用户未提供
 */
export async function initAuth() {
  // localhost 自动放行（服务端跳过认证）
  if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    return true
  }

  try {
    const res = await fetch(BASE + '/auth/status')
    const data = await res.json()
    if (!data.auth_required) return true

    // 已有有效 key，直接返回
    if (API_KEY) return true

    // 弹出输入框
    API_KEY = prompt('此仪表盘已启用 API Key 认证，请输入 Key：\n（请联系管理员获取）') || ''
    if (API_KEY) {
      sessionStorage.setItem('soma_api_key', API_KEY)
      return true
    }
    return false
  } catch {
    return true // 网络错误时放行，由后续请求报错
  }
}

/**
 * 更新 API Key（用户手动设置）
 */
export function setApiKey(key) {
  API_KEY = key
  sessionStorage.setItem('soma_api_key', key)
}

async function request(path, options = {}) {
  const headers = { 'Content-Type': 'application/json' }
  if (API_KEY) headers['X-API-Key'] = API_KEY

  const res = await fetch(BASE + path, {
    headers,
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  health: () => request('/health'),

  community: () => request('/stats/community'),

  competitorStats: () => request('/stats/competitors'),

  chat: (problem) =>
    request('/chat', {
      method: 'POST',
      body: JSON.stringify({ problem }),
    }),

  memoryStats: () => request('/memory/stats'),

  memorySearch: (query, topK = 20) =>
    request('/memory/search', {
      method: 'POST',
      body: JSON.stringify({ query, top_k: topK }),
    }),

  memoryAdd: (content, domain = '通用', type = '笔记', importance = 0.7) =>
    request('/memory/add', {
      method: 'POST',
      body: JSON.stringify({ content, domain, type, importance }),
    }),

  memoryAddSemantic: (subject, predicate, object) =>
    request('/memory/semantic', {
      method: 'POST',
      body: JSON.stringify({ subject, predicate, object }),
    }),

  frameworkWeights: () => request('/framework/weights'),

  frameworkAdjust: (law_id, weight) =>
    request('/framework/adjust-weight', {
      method: 'POST',
      body: JSON.stringify({ law_id, weight }),
    }),

  frameworkEvolve: () =>
    request('/framework/evolve', { method: 'POST' }),

  frameworkStats: () => request('/framework/stats'),

  frameworkLog: () => request('/framework/log'),

  frameworkClearLog: () =>
    request('/framework/log', { method: 'DELETE' }),

  // Config / Provider
  configLLM: () => request('/config/llm'),

  configSwitchProvider: (provider_id) =>
    request('/config/providers/switch', {
      method: 'POST',
      body: JSON.stringify({ provider_id }),
    }),

  configUpdateProvider: (provider_id, api_key, model, base_url) =>
    request('/config/providers/update', {
      method: 'POST',
      body: JSON.stringify({ provider_id, api_key, model, base_url }),
    }),

  // Analytics
  analyticsSummary: () => request('/analytics/summary'),
  analyticsSessions: (limit = 50, offset = 0, provider, mockOnly) => {
    const params = new URLSearchParams({ limit, offset })
    if (provider) params.set('provider', provider)
    if (mockOnly !== undefined) params.set('mock_only', mockOnly)
    return request(`/analytics/sessions?${params}`)
  },
  analyticsSession: (id) => request(`/analytics/session/${id}`),
  analyticsCompare: () => request('/analytics/compare'),
  analyticsClear: (keep) => request(`/analytics/sessions?keep=${keep}`, { method: 'DELETE' }),

  // Benchmarks
  benchmarksLatest: () => request('/benchmarks/latest'),
  benchmarksHistory: (limit = 20) => request(`/benchmarks/history?limit=${limit}`),
  benchmarksRun: () =>
    request('/benchmarks/run', { method: 'POST' }),
  benchmarksCompare: () => request('/benchmarks/compare'),
  // Reports
  reportsList: () => request('/reports'),
  report: (id) => request(`/reports/${id}`),
}
