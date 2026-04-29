<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import * as echarts from 'echarts/core'
import { SankeyChart } from 'echarts/charts'
import { TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([SankeyChart, TooltipComponent, CanvasRenderer])

const { t } = useI18n()

const props = defineProps({
  foci: { type: Array, default: () => [] },
  activatedMemories: { type: Array, default: () => [] },
})

const container = ref(null)
let chart = null
let observer = null

const SRC_COLOR = { episodic: '#818cf8', semantic: '#22d3ee', skill: '#fbbf24' }

function buildData() {
  const foci = props.foci || []
  const mems = props.activatedMemories || []
  if (!foci.length || !mems.length) return null

  const nodes = []
  const links = []

  // 左列：焦点节点
  foci.forEach((f, i) => {
    const raw = (f.dimension || '')
      .replace(/从「.+?」出发：/, '')
      .replace(/从「.+?」视角审视：/, '')
    nodes.push({ name: `F${i}`, itemStyle: { color: '#94a3b8' }, _label: raw.slice(0, 15) || `维度${i + 1}` })
  })

  // 右列：记忆节点（按内容前20字去重）
  const dedup = new Map()
  mems.forEach((m, i) => {
    const key = (m.content || '').slice(0, 20)
    if (!dedup.has(key)) {
      dedup.set(key, { id: `M${i}`, content: m.content, source: m.source, score: m.activation_score || 0 })
    } else {
      const prev = dedup.get(key)
      prev.score = Math.max(prev.score, m.activation_score || 0)
    }
  })
  for (const [key, v] of dedup) {
    const lbl = key.length > 18 ? key.slice(0, 18) + '…' : key
    nodes.push({ name: v.id, itemStyle: { color: SRC_COLOR[v.source] || '#64748b' }, _label: lbl, _source: v.source })
  }

  // 连线：焦点 × 记忆全连接，宽度 = 归一化score
  const maxScore = Math.max(...mems.map(m => m.activation_score || 0), 0.001)
  foci.forEach((_, fi) => {
    dedup.forEach((v) => {
      links.push({
        source: `F${fi}`,
        target: v.id,
        value: Math.max((v.score / maxScore) * 8, 0.5),
      })
    })
  })

  return { nodes, links }
}

function render() {
  const el = container.value
  if (!el) return
  const data = buildData()
  if (!data) return
  if (chart) chart.dispose()

  chart = echarts.init(el, null)
  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      triggerOn: 'mousemove',
      backgroundColor: 'rgba(15,15,25,0.95)',
      borderColor: '#333',
      textStyle: { color: '#ccc', fontSize: 12 },
      formatter(p) {
        if (p.dataType === 'edge') return `${p.data.source} → ${p.data.target}<br/>流量: ${(p.data.value / 8).toFixed(3)}`
        return p.data._label || p.name
      },
    },
    series: [{
      type: 'sankey',
      layoutIterations: 32,
      emphasis: { focus: 'adjacency' },
      nodeWidth: 16,
      nodeGap: 12,
      left: 8, right: 8, top: 16, bottom: 16,
      data: data.nodes,
      links: data.links,
      label: {
        show: true,
        fontSize: 10,
        color: '#94a3b8',
        formatter(p) { return p.data._label || p.name },
      },
      lineStyle: { color: 'source', curveness: 0.5, opacity: 0.25 },
    }],
  })
}

onMounted(() => {
  nextTick(render)
  observer = new ResizeObserver(() => { if (chart) chart.resize() })
  if (container.value) observer.observe(container.value)
})

onUnmounted(() => {
  observer?.disconnect()
  chart?.dispose()
})

watch(() => [props.foci, props.activatedMemories], () => nextTick(render), { deep: true })
</script>

<template>
  <div ref="container" style="width:100%;height:400px;" />
</template>
