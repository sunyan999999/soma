const BASE = '/api'

// 服务器通过 HTML 注入的 API Key
const API_KEY = window.__SOMA_API_KEY__ || ''

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
