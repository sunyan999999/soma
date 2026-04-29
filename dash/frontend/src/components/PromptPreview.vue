<script setup>
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps({
  prompt: { type: String, default: '' },
})

const open = ref(false)
const copied = ref(false)

const sections = computed(() => {
  if (!props.prompt) return []
  const result = []
  const lines = props.prompt.split('\n')
  let currentSection = null
  let currentLines = []

  for (const line of lines) {
    if (line.startsWith('## 思考角度') || line.startsWith('## Thinking Angles')) {
      if (currentSection) {
        result.push({ ...currentSection, text: currentLines.join('\n') })
      }
      currentSection = { type: 'framework', title: line }
      currentLines = []
    } else if (line.startsWith('## 相关记忆与经验') || line.startsWith('## Related Memories')) {
      if (currentSection) {
        result.push({ ...currentSection, text: currentLines.join('\n') })
      }
      currentSection = { type: 'memory', title: line }
      currentLines = []
    } else if (line.startsWith('## 当前问题') || line.startsWith('## Current Problem')) {
      if (currentSection) {
        result.push({ ...currentSection, text: currentLines.join('\n') })
      }
      currentSection = { type: 'problem', title: line }
      currentLines = []
    } else {
      currentLines.push(line)
    }
  }
  if (currentSection) {
    result.push({ ...currentSection, text: currentLines.join('\n') })
  }
  return result
})

const sectionColors = {
  framework: 'rgba(99,102,241,0.12)',
  memory: 'rgba(245,158,11,0.12)',
  problem: 'rgba(16,185,129,0.06)',
}

const sectionBorders = {
  framework: 'rgba(99,102,241,0.35)',
  memory: 'rgba(245,158,11,0.35)',
  problem: 'rgba(16,185,129,0.2)',
}

const sectionLabels = {
  framework: t('chat.frameworkSection'),
  memory: t('chat.memorySection'),
  problem: t('chat.problemSection'),
}

async function copyPrompt() {
  try {
    await navigator.clipboard.writeText(props.prompt)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  } catch {
    // fallback
    const ta = document.createElement('textarea')
    ta.value = props.prompt
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  }
}
</script>

<template>
  <div v-if="prompt" class="prompt-preview">
    <div class="prompt-header" @click="open = !open">
      <span class="prompt-toggle">{{ open ? '▾' : '▸' }} {{ t('chat.promptPreview') }}</span>
      <button v-if="open" class="btn btn-sm btn-secondary copy-btn" @click.stop="copyPrompt">
        {{ copied ? t('chat.copied') : t('chat.copyPrompt') }}
      </button>
    </div>
    <div v-if="open" class="prompt-body">
      <div
        v-for="(sec, i) in sections"
        :key="i"
        class="prompt-section"
        :style="{
          background: sectionColors[sec.type] || 'transparent',
          borderLeft: `3px solid ${sectionBorders[sec.type] || 'transparent'}`,
        }"
      >
        <div class="section-label">{{ sectionLabels[sec.type] || sec.type }}</div>
        <pre class="section-text">{{ sec.text }}</pre>
      </div>
    </div>
  </div>
</template>

<style scoped>
.prompt-preview {
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}

.prompt-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  cursor: pointer;
  user-select: none;
  transition: background 0.15s;
}
.prompt-header:hover {
  background: rgba(255,255,255,0.03);
}

.prompt-toggle {
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--text-secondary);
}

.copy-btn {
  padding: 4px 12px;
  font-size: 0.78rem;
}

.prompt-body {
  padding: 0 12px 12px;
}

.prompt-section {
  margin-bottom: 8px;
  padding: 8px 12px;
  border-radius: 4px;
}

.section-label {
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-muted);
  margin-bottom: 6px;
}

.section-text {
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 0.78rem;
  line-height: 1.6;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
}
</style>
