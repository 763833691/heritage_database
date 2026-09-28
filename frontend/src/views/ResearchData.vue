<template>
  <div class="page-shell research-data-page">
    <PageHero title="研究数据" accent="数据总览" description="全面汇聚遗址公园真实数据，洞察类型、区域与评价维度，为保护研究和管理决策提供清晰证据。" :image="portalHero" compact />

    <div class="portal-stat-grid">
      <div v-for="item in statItems" :key="item.label" class="portal-stat-card">
        <span :class="['portal-stat-card__icon', item.tone]"><el-icon><component :is="item.icon" /></el-icon></span>
        <div class="portal-stat-card__copy"><div class="portal-stat-card__label">{{ item.label }}</div><div class="portal-stat-card__value">{{ item.value }}</div><div class="portal-stat-card__meta">{{ item.meta }}</div></div>
      </div>
    </div>

    <StatusState v-if="loading" type="loading" title="正在加载研究数据" />
    <StatusState v-else-if="error" type="error" title="研究数据加载失败" :description="error" action-label="重新加载" @action="loadData" />
    <template v-else>
      <div class="coverage-block">
        <div class="section-card__header"><div><h2>田野调研覆盖</h2><p>来自 KML 轨迹、语义化照片与调研事件的真实统计，数字与数据库一致。</p></div></div>
        <div class="coverage-grid">
          <div v-for="item in coverageItems" :key="item.label" class="portal-stat-card">
            <span :class="['portal-stat-card__icon', item.tone]"><el-icon><component :is="item.icon" /></el-icon></span>
            <div class="portal-stat-card__copy"><div class="portal-stat-card__label">{{ item.label }}</div><div class="portal-stat-card__value">{{ item.value }}</div><div class="portal-stat-card__meta">{{ item.meta }}</div></div>
          </div>
        </div>
      </div>

      <div class="research-chart-grid">
        <div class="chart-card chart-card--wide"><div class="section-card__header"><div><h2>评价维度概览</h2><p>不同遗址公园类型的真实平均得分。</p></div></div><div ref="dimensionRef" class="chart-canvas"></div></div>
        <div class="chart-card"><div class="section-card__header"><div><h2>公园类型分布</h2><p>当前数据库中的类型构成。</p></div></div><div ref="typeRef" class="chart-canvas"></div></div>
        <div class="chart-card"><div class="section-card__header"><div><h2>省级区域分布</h2><p>按收录公园数量排序。</p></div></div><div ref="provinceRef" class="chart-canvas"></div></div>
      </div>

      <section v-if="scoreMatrix" class="chart-card">
        <div class="section-card__header">
          <div><h2>公园 × 指标评分热力图</h2><p>{{ scoreMatrix.parks.length }} 个公园在 {{ scoreMatrix.indicators.length }} 项指标上的标准化得分，悬停查看原始得分与评分依据。</p></div>
          <el-radio-group v-model="heatDimension" size="small">
            <el-radio-button label="">全部</el-radio-button>
            <el-radio-button v-for="dim in heatDimensions" :key="dim.dimension" :label="dim.dimension">{{ dim.dimension }}</el-radio-button>
          </el-radio-group>
        </div>
        <div ref="heatmapRef" class="chart-canvas tall"></div>
      </section>

      <div class="research-lower-grid">
        <div class="section-card insight-card">
          <div class="section-card__header"><div><h2>数据洞察</h2><p>基于当前真实数据的直接观察。</p></div></div>
          <ul>
            <li>当前共收录 <strong>{{ stats.total_parks || 0 }}</strong> 个遗址公园，覆盖 <strong>{{ provinceCount }}</strong> 个省级区域。</li>
            <li>公园数量最多的类型为 <strong>{{ topType.name }}</strong>，共 {{ topType.value }} 个。</li>
            <li>评价体系包含 <strong>{{ stats.total_indicators || 0 }}</strong> 项指标，已形成 {{ dimensions.length }} 个可统计维度。</li>
            <li v-if="!stats.total_sites">当前数据库暂无遗址点记录，相关模块会显示明确空状态。</li>
          </ul>
          <el-button type="primary" plain @click="$router.push('/parks')">浏览公园档案</el-button>
        </div>
        <div class="section-card quick-card">
          <div class="section-card__header"><div><h2>快速入口</h2><p>从数据概览继续深入研究。</p></div></div>
          <div class="quick-grid">
            <router-link v-for="item in quickLinks" :key="item.path" :to="item.path"><el-icon><component :is="item.icon" /></el-icon><span><strong>{{ item.title }}</strong><small>{{ item.description }}</small></span><el-icon><ArrowRight /></el-icon></router-link>
          </div>
        </div>
      </div>

      <div class="section-card update-card">
        <div class="section-card__header"><div><h2>数据更新说明</h2><p>当前接口未提供独立的数据版本和更新时间字段。</p></div></div>
        <StatusState type="empty" title="暂无可展示的更新日志" description="为保持数据可信，本页面不会编造更新时间或增长趋势；后端提供真实元数据后可在此展示。" />
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { OfficeBuilding, Location, DataAnalysis, PieChart, MapLocation, TrendCharts, Collection, Picture, Notebook, Odometer } from '@element-plus/icons-vue'
import api from '@/utils/api'
import PageHero from '@/components/portal/PageHero.vue'
import StatusState from '@/components/common/StatusState.vue'
import portalHero from '@/assets/images/portal-hero.webp'

const stats = ref({})
const dimensions = ref([])
const scoreMatrix = ref(null)
const heatDimension = ref('')
const loading = ref(true)
const error = ref('')
const dimensionRef = ref()
const typeRef = ref()
const provinceRef = ref()
const heatmapRef = ref()
const charts = []
let observer
let heatmapChart

const heatDimensions = computed(() => scoreMatrix.value?.dimensions || [])

const provinceCount = computed(() => Object.keys(stats.value.by_province || {}).length)
const topType = computed(() => Object.entries(stats.value.by_type || {}).map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value)[0] || { name: '暂无', value: 0 })
const statItems = computed(() => [
  { label: '遗址公园总数', value: Number(stats.value.total_parks || 0).toLocaleString('zh-CN'), meta: `覆盖 ${provinceCount.value} 个省级区域`, icon: OfficeBuilding, tone: '' },
  { label: '遗址地点', value: Number(stats.value.total_sites || 0).toLocaleString('zh-CN'), meta: stats.value.total_sites ? '已录入地点信息' : '当前暂无记录', icon: Location, tone: 'green' },
  { label: '评价指标', value: Number(stats.value.total_indicators || 0).toLocaleString('zh-CN'), meta: '真实评价体系指标', icon: DataAnalysis, tone: 'violet' },
  { label: '评定批次', value: Object.keys(stats.value.by_batch || {}).length, meta: '当前数据中的批次', icon: PieChart, tone: 'orange' },
])
const coverageItems = computed(() => {
  const field = stats.value.field_research || {}
  return [
    { label: '轨迹条数', value: Number(field.track_count || 0).toLocaleString('zh-CN'), meta: '已处理的 KML 轨迹', icon: MapLocation, tone: '' },
    { label: '田野照片', value: Number(field.photo_count || 0).toLocaleString('zh-CN'), meta: '含语义描述的照片点', icon: Picture, tone: 'green' },
    { label: '调研事件', value: Number(field.event_count || 0).toLocaleString('zh-CN'), meta: 'survey_events 记录', icon: Notebook, tone: 'violet' },
    { label: '覆盖公园', value: Number(field.park_count || 0).toLocaleString('zh-CN'), meta: '已开展调研的公园', icon: OfficeBuilding, tone: 'orange' },
    { label: '轨迹总里程', value: `${field.track_distance_km ?? 0} km`, meta: '按 KML 轨迹累计', icon: Odometer, tone: 'cyan' },
  ]
})
const quickLinks = [
  { title: '遗址公园', description: '浏览真实公园档案', path: '/parks', icon: OfficeBuilding },
  { title: '地图浏览', description: '查看空间分布', path: '/map', icon: MapLocation },
  { title: '对比分析', description: '比较评价指标', path: '/compare', icon: TrendCharts },
  { title: '知识库', description: '检索研究文献', path: '/library', icon: Collection },
]

onMounted(loadData)
onBeforeUnmount(() => { observer?.disconnect(); charts.forEach((chart) => chart.dispose()) })

async function loadData() {
  loading.value = true
  error.value = ''
  try {
    const [overview, dimension, matrix] = await Promise.all([
      api.get('/statistics/overview', { silent: true }),
      api.get('/statistics/dimension', { silent: true }),
      api.get('/statistics/score-matrix', { silent: true }),
    ])
    stats.value = overview.data || {}
    dimensions.value = dimension.data || []
    scoreMatrix.value = matrix.data || null
    loading.value = false
    await nextTick()
    renderCharts()
  } catch (e) {
    error.value = e.response?.data?.detail || '请检查后端服务后重试。'
    loading.value = false
  }
}

function createChart(el) {
  const chart = echarts.init(el)
  charts.push(chart)
  observer ||= new ResizeObserver(() => charts.forEach((item) => item.resize()))
  observer.observe(el)
  return chart
}
function renderCharts() {
  charts.splice(0).forEach((chart) => chart.dispose())
  heatmapChart = null
  const palette = ['#2563eb', '#22c55e', '#7c3aed', '#f59e0b', '#06b6d4']
  const dimNames = [...new Set(dimensions.value.map((item) => item.dimension))]
  const typeNames = [...new Set(dimensions.value.map((item) => item.park_type))]
  createChart(dimensionRef.value).setOption({ color: palette, tooltip: { trigger: 'axis' }, legend: { top: 0 }, grid: { top: 52, right: 20, bottom: 34, left: 46 }, xAxis: { type: 'category', data: dimNames, axisLabel: { color: '#667085' }, axisLine: { lineStyle: { color: '#e7eaf0' } } }, yAxis: { type: 'value', max: 100, splitLine: { lineStyle: { color: '#eef1f5' } } }, series: typeNames.map((type) => ({ name: type, type: 'bar', barMaxWidth: 24, data: dimNames.map((dim) => dimensions.value.find((item) => item.park_type === type && item.dimension === dim)?.avg_score || 0) })) })
  const typeData = Object.entries(stats.value.by_type || {}).map(([name, value]) => ({ name, value }))
  createChart(typeRef.value).setOption({ color: palette, tooltip: { trigger: 'item' }, legend: { bottom: 0 }, series: [{ type: 'pie', radius: ['48%', '70%'], center: ['50%', '44%'], label: { formatter: '{b}\n{d}%' }, data: typeData }] })
  const provinceData = Object.entries(stats.value.by_province || {}).map(([name, value]) => ({ name, value })).sort((a, b) => a.value - b.value)
  createChart(provinceRef.value).setOption({ color: ['#3b82f6'], tooltip: { trigger: 'axis' }, grid: { top: 12, right: 24, bottom: 24, left: 72 }, xAxis: { type: 'value', splitLine: { lineStyle: { color: '#eef1f5' } } }, yAxis: { type: 'category', data: provinceData.map((item) => item.name), axisLine: { show: false }, axisTick: { show: false } }, series: [{ type: 'bar', data: provinceData.map((item) => item.value), barMaxWidth: 18, itemStyle: { borderRadius: [0, 7, 7, 0] } }] })
  renderHeatmap()
}
function renderHeatmap() {
  const matrix = scoreMatrix.value
  if (!heatmapRef.value || !matrix) return
  if (!heatmapChart) heatmapChart = createChart(heatmapRef.value)
  const indicators = heatDimension.value
    ? matrix.indicators.filter((item) => item.dimension === heatDimension.value)
    : matrix.indicators
  const codeIndex = new Map(indicators.map((item, index) => [item.code, index]))
  const cellMap = new Map(matrix.cells.map((cell) => [`${cell.park_id}:${cell.indicator_id}`, cell]))
  const data = []
  const infoMap = {}
  matrix.parks.forEach((park, parkIndex) => {
    indicators.forEach((indicator) => {
      const cell = cellMap.get(`${park.park_id}:${indicator.id}`)
      if (!cell || cell.score == null) return
      const x = codeIndex.get(indicator.code)
      data.push([x, parkIndex, cell.score])
      infoMap[`${x}:${parkIndex}`] = { cell, indicator, park }
    })
  })
  heatmapChart.setOption({
    tooltip: {
      formatter: (params) => {
        const info = infoMap[`${params.data[0]}:${params.data[1]}`]
        if (!info) return ''
        const evidence = info.cell.evidence ? `<br/>依据：${info.cell.evidence}` : ''
        return `${info.park.park_name}<br/>${info.indicator.code} ${info.indicator.name}<br/>得分：${info.cell.score}（${info.cell.grade || '—'}）${evidence}`
      },
    },
    grid: { top: 16, left: 92, right: 24, bottom: 92 },
    xAxis: { type: 'category', data: indicators.map((item) => item.code), splitArea: { show: true }, axisLabel: { fontSize: 10 } },
    yAxis: { type: 'category', data: matrix.parks.map((park) => park.park_name), splitArea: { show: true }, axisLabel: { fontSize: 10 } },
    visualMap: { min: 20, max: 100, calculable: true, orient: 'horizontal', left: 'center', bottom: 34, inRange: { color: ['#e0ecff', '#60a5fa', '#1d4ed8'] } },
    dataZoom: [{ type: 'inside' }, { type: 'slider', bottom: 8, height: 14 }],
    series: [{ type: 'heatmap', data, label: { show: indicators.length <= 12, fontSize: 10 }, emphasis: { itemStyle: { shadowBlur: 6, shadowColor: 'rgba(0,0,0,.3)' } } }],
  }, true)
}
watch(heatDimension, () => nextTick(renderHeatmap))
</script>

<style scoped lang="scss">
.coverage-block { display: grid; gap: 12px; }.coverage-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); }.coverage-grid .portal-stat-card { border-right: 1px solid var(--border); }.coverage-grid .portal-stat-card:last-child { border-right: 0; }
.research-chart-grid { display: grid; grid-template-columns: 1.35fr .8fr; gap: 16px; }.chart-card--wide{grid-row:span 2}.research-lower-grid{display:grid;grid-template-columns:1fr 1.2fr;gap:16px}.insight-card,.quick-card,.update-card{padding:24px}.insight-card ul{display:grid;gap:13px;margin:0 0 20px;padding-left:20px;color:var(--text-secondary);font-size:13px;line-height:1.7}.insight-card strong{color:var(--brand-600)}.quick-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.quick-grid a{min-height:76px;padding:14px;display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:10px;color:inherit;text-decoration:none;border:1px solid var(--border);border-radius:12px}.quick-grid>a>.el-icon:first-child{width:36px;height:36px;display:grid;place-items:center;color:var(--brand-600);background:var(--brand-50);border-radius:11px}.quick-grid span{display:grid}.quick-grid strong{font-size:13px}.quick-grid small{margin-top:4px;color:var(--text-tertiary)}.quick-grid>a>.el-icon:last-child{color:var(--text-tertiary)}
@media(max-width:980px){.research-chart-grid,.research-lower-grid{grid-template-columns:1fr}.chart-card--wide{grid-row:auto}.coverage-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.coverage-grid .portal-stat-card:nth-child(2n){border-right:0}}@media(max-width:640px){.quick-grid{grid-template-columns:1fr}.coverage-grid{grid-template-columns:1fr}.coverage-grid .portal-stat-card{border-right:0}}
</style>
