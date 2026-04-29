<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api'

const { t } = useI18n()

const reports = ref([])
const loading = ref(true)
const error = ref('')
const selectedReport = ref(null)
const reportContent = ref('')
const reportMeta = ref(null)
const reportLoading = ref(false)

onMounted(async () => {
  try {
    const data = await api.reportsList()
    reports.value = data.reports || []
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})

async function openReport(report) {
  reportLoading.value = true
  selectedReport.value = report
  reportContent.value = ''
  reportMeta.value = null
  try {
    const data = await api.report(report.id)
    reportContent.value = data.content
    reportMeta.value = data.meta
  } catch (e) {
    reportContent.value = ''
  } finally {
    reportLoading.value = false
  }
}

function backToList() {
  selectedReport.value = null
  reportContent.value = ''
  reportMeta.value = null
}

function renderMarkdown(md) {
  if (!md) return ''
  // Remove YAML frontmatter
  let html = md.replace(/^---[\s\S]*?---\n*/, '')
  // Headers
  html = html.replace(/^#### (.+)$/gm, '<h4>$1</h4>')
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>')
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>')
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>')
  // Bold and italic
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')
  // Code blocks
  html = html.replace(/```[\s\S]*?```/g, (match) => {
    const code = match.replace(/```\w*\n?/, '').replace(/```$/, '')
    return `<pre><code>${escapeHtml(code)}</code></pre>`
  })
  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>')
  // Blockquotes
  html = html.replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
  // Horizontal rules
  html = html.replace(/^---$/gm, '<hr>')
  // Tables — process line-by-line for correct header/data detection
  const lines = html.split('\n')
  const out = []
  let tableRows = []
  function flushTable() {
    if (tableRows.length === 0) return
    let tbl = '<table>'
    for (let i = 0; i < tableRows.length; i++) {
      const cells = tableRows[i].split('|').filter(c => c.trim())
      if (i === 1 && cells.every(c => /^[-:]+$/.test(c.trim()))) continue
      const tag = i === 0 ? 'th' : 'td'
      tbl += '<tr>' + cells.map(c => `<${tag}>${c.trim()}</${tag}>`).join('') + '</tr>'
    }
    tbl += '</table>'
    out.push(tbl)
    tableRows = []
  }
  for (const line of lines) {
    if (/^\|(.+)\|$/.test(line)) {
      tableRows.push(line)
    } else {
      flushTable()
      out.push(line)
    }
  }
  flushTable()
  html = out.join('\n')
  // Lists
  html = html.replace(/^- (.+)$/gm, '<li>$1</li>')
  html = html.replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>')
  // Line breaks
  html = html.replace(/\n\n/g, '<br><br>')
  html = html.replace(/\n/g, '<br>')
  // Clean up: merge consecutive blockquotes
  html = html.replace(/<\/blockquote>\s*<blockquote>/g, '<br>')
  return html
}

function escapeHtml(text) {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}
</script>

<template>
  <div>
    <!-- List View -->
    <template v-if="!selectedReport">
      <h1 class="page-title">{{ t('reports.title') }}</h1>
      <p class="page-subtitle">{{ t('reports.subtitle') }}</p>

      <!-- Loading -->
      <div v-if="loading" class="gap-md">
        <div class="skeleton" style="height:80px;" />
        <div class="skeleton" style="height:80px;" />
      </div>

      <!-- Error -->
      <div v-else-if="error" class="card" style="text-align:center;padding:40px;">
        <p style="color:var(--rose);">{{ error }}</p>
      </div>

      <!-- Empty -->
      <div v-else-if="reports.length === 0" style="text-align:center;padding:80px 20px;color:var(--text-muted);">
        <div style="font-size:3rem;margin-bottom:16px;">📋</div>
        <p style="font-size:1.05rem;">{{ t('reports.noReports') }}</p>
        <p style="font-size:0.8rem;margin-top:4px;">{{ t('reports.noReportsDesc') }}</p>
      </div>

      <!-- Report Cards -->
      <div v-else class="gap-lg">
        <div
          v-for="report in reports"
          :key="report.id"
          class="card"
          style="cursor:pointer;transition:border-color 0.2s;"
          @mouseenter="$event.currentTarget.style.borderColor='var(--accent)'"
          @mouseleave="$event.currentTarget.style.borderColor='var(--border)'"
          @click="openReport(report)"
        >
          <div class="row row-between">
            <div>
              <h3 style="font-size:1.05rem;margin:0;">{{ report.title }}</h3>
              <p v-if="report.title_en" style="font-size:0.8rem;color:var(--text-muted);margin-top:2px;">
                {{ report.title_en }}
              </p>
            </div>
            <div style="text-align:right;">
              <span class="badge badge-accent">{{ report.version }}</span>
            </div>
          </div>

          <p v-if="report.summary" style="font-size:0.85rem;color:var(--text-secondary);margin-top:12px;line-height:1.6;">
            {{ report.summary }}
          </p>

          <div class="row" style="gap:16px;margin-top:12px;font-size:0.75rem;color:var(--text-muted);">
            <span>📅 {{ report.date }}</span>
            <span v-if="report.models">🧠 {{ report.models.length }} {{ t('reports.models') }}</span>
          </div>
        </div>
      </div>
    </template>

    <!-- Report Detail View -->
    <template v-else>
      <button class="btn btn-secondary btn-sm" style="margin-bottom:16px;" @click="backToList">
        ← {{ t('reports.backToList') }}
      </button>

      <div v-if="reportLoading" class="card" style="text-align:center;padding:60px;">
        <p style="color:var(--text-muted);">{{ t('reports.loading') }}</p>
      </div>

      <div v-else-if="!reportContent" class="card" style="text-align:center;padding:40px;">
        <p style="color:var(--rose);">{{ t('reports.loadFailed') }}</p>
      </div>

      <div v-else class="card report-content" v-html="renderMarkdown(reportContent)" />
    </template>
  </div>
</template>

<style scoped>
.report-content :deep(h1) {
  font-size: 1.6rem;
  margin: 0 0 8px 0;
  color: var(--text-primary);
  border-bottom: 1px solid var(--border);
  padding-bottom: 12px;
}
.report-content :deep(h2) {
  font-size: 1.25rem;
  margin: 32px 0 12px 0;
  color: var(--text-primary);
  border-bottom: 1px solid var(--border);
  padding-bottom: 8px;
}
.report-content :deep(h3) {
  font-size: 1.05rem;
  margin: 24px 0 8px 0;
  color: var(--text-secondary);
}
.report-content :deep(h4) {
  font-size: 0.95rem;
  margin: 16px 0 6px 0;
  color: var(--text-secondary);
}
.report-content :deep(p) {
  line-height: 1.85;
  margin: 8px 0;
  color: var(--text-secondary);
}
.report-content :deep(strong) {
  color: var(--text-primary);
}
.report-content :deep(blockquote) {
  border-left: 3px solid var(--accent);
  padding: 8px 16px;
  margin: 12px 0;
  background: rgba(99,102,241,0.06);
  border-radius: 0 6px 6px 0;
  color: var(--text-secondary);
}
.report-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 16px 0;
  font-size: 0.85rem;
}
.report-content :deep(th) {
  background: rgba(99,102,241,0.1);
  padding: 10px 12px;
  text-align: left;
  font-weight: 600;
  color: var(--text-primary);
  border-bottom: 2px solid var(--border);
}
.report-content :deep(td) {
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
  color: var(--text-secondary);
}
.report-content :deep(tr:hover td) {
  background: rgba(255,255,255,0.02);
}
.report-content :deep(hr) {
  border: none;
  border-top: 1px solid var(--border);
  margin: 24px 0;
}
.report-content :deep(code) {
  background: rgba(255,255,255,0.06);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.85em;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
}
.report-content :deep(pre) {
  background: rgba(0,0,0,0.2);
  padding: 16px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 12px 0;
}
.report-content :deep(pre code) {
  background: none;
  padding: 0;
}
.report-content :deep(ul) {
  margin: 8px 0;
  padding-left: 24px;
}
.report-content :deep(li) {
  line-height: 1.8;
  color: var(--text-secondary);
}
</style>
