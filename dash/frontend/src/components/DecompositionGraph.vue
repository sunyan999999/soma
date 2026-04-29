<script setup>
import { ref, watch, onMounted, onUnmounted, inject } from 'vue'
import { useI18n } from 'vue-i18n'
import * as echarts from 'echarts/core'
import { GraphChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([GraphChart, TooltipComponent, LegendComponent, CanvasRenderer])

const { t } = useI18n()

const props = defineProps({
  foci: { type: Array, default: () => [] },
  problem: { type: String, default: '' },
  lawNames: { type: Object, default: () => ({}) },
})

const chartRef = ref(null)
let chart = null
let resizeObserver = null

function buildGraphData() {
  if (!props.foci.length) return null

  const nodes = []
  const links = []

  // 中心问题节点
  const problemLabel = props.problem.length > 20 ? props.problem.slice(0, 20) + '...' : props.problem
  nodes.push({
    id: 'problem',
    name: problemLabel || '?',
    symbolSize: 50,
    category: 0,
    itemStyle: { color: '#6366f1' },
    label: { show: true, fontSize: 13, fontWeight: 'bold' },
  })

  // 统计用到的规律（去重）
  const lawSet = new Set()
  props.foci.forEach(f => lawSet.add(f.law_id))

  // 规律节点
  const lawColorMap = {}
  const colors = ['#f59e0b', '#06b6d4', '#10b981', '#ef4444', '#8b5cf6', '#ec4899', '#f97316']
  let ci = 0
  for (const lawId of lawSet) {
    const name = props.lawNames[lawId] || lawId
    const color = colors[ci % colors.length]
    lawColorMap[lawId] = color
    nodes.push({
      id: lawId,
      name: name,
      symbolSize: 35,
      category: 1,
      itemStyle: { color, borderColor: color, borderWidth: 2, opacity: 0.9 },
      label: { show: true, fontSize: 12 },
    })
    ci++
  }

  // 焦点节点 + 连线
  props.foci.forEach((f, i) => {
    const focusId = `focus_${i}`
    const color = lawColorMap[f.law_id] || '#94a3b8'
    const label = (f.dimension || '').replace(/从「.+?」出发：/, '').replace(/从「.+?」视角审视：/, '').slice(0, 25)
    nodes.push({
      id: focusId,
      name: label || `维度${i + 1}`,
      symbolSize: 22,
      category: 2,
      itemStyle: { color, opacity: 0.75 },
      label: { show: true, fontSize: 10, position: 'right' },
      tooltip_data: {
        dimension: f.dimension,
        rationale: f.rationale,
        keywords: (f.keywords || []).join(', '),
        weight: f.weight,
      },
    })
    // 问题 → 焦点
    links.push({ source: 'problem', target: focusId, lineStyle: { color: '#94a3b8', width: 1, type: 'dashed' } })
    // 焦点 → 规律
    links.push({ source: focusId, target: f.law_id, lineStyle: { color, width: 1.5, opacity: 0.6 } })
  })

  return { nodes, links, categories: [
    { name: t('chat.currentProblem') || '问题' },
    { name: t('framework.lawWeights') || '规律' },
    { name: t('chat.dimensions') || '维度' },
  ]}
}

function initChart() {
  if (!chartRef.value) return
  const data = buildGraphData()
  if (!data) return

  if (chart) chart.dispose()

  chart = echarts.init(chartRef.value)
  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      backgroundColor: 'rgba(15,15,25,0.95)',
      borderColor: '#333',
      textStyle: { color: '#ccc', fontSize: 12 },
      formatter(params) {
        if (params.dataType === 'node' && params.data.tooltip_data) {
          const d = params.data.tooltip_data
          return `<div style="max-width:300px;"><b>${d.dimension || ''}</b><br/>
            <span style="color:#94a3b8;">${t('chat.rationale') || '触发'}: ${d.rationale || ''}</span><br/>
            <span style="color:#94a3b8;">${t('memory.domain') || '关键词'}: ${d.keywords || ''}</span><br/>
            <span style="color:#f59e0b;">${t('chat.weight') || '权重'}: ${(d.weight || 0).toFixed(2)}</span></div>`
        }
        return params.name
      },
    },
    legend: {
      data: data.categories.map(c => c.name),
      bottom: 0,
      textStyle: { color: '#94a3b8', fontSize: 11 },
    },
    series: [{
      type: 'graph',
      layout: 'force',
      categories: data.categories,
      nodes: data.nodes,
      links: data.links,
      roam: true,
      draggable: true,
      force: { repulsion: 300, gravity: 0.08, edgeLength: [100, 200] },
      emphasis: { focus: 'adjacency', itemStyle: { shadowBlur: 12, shadowColor: 'rgba(99,102,241,0.5)' } },
      lineStyle: { curveness: 0.2 },
    }],
  }, true)

  chart.on('click', (params) => {
    if (params.dataType === 'node' && params.data.tooltip_data) {
      // click handled by tooltip
    }
  })
}

onMounted(() => {
  initChart()
  resizeObserver = new ResizeObserver(() => chart?.resize())
  if (chartRef.value) resizeObserver.observe(chartRef.value)
})

onUnmounted(() => {
  resizeObserver?.disconnect()
  chart?.dispose()
})

watch(() => [props.foci, props.problem], () => {
  initChart()
}, { deep: true })
</script>

<template>
  <div ref="chartRef" class="decomp-chart"></div>
</template>

<style scoped>
.decomp-chart {
  width: 100%;
  height: 420px;
}
</style>
