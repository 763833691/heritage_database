<template>
  <div class="page-shell field-gallery-page">
    <PageHero
      title="田野影像总览"
      accent="全域照片"
      description="把全部 KML 轨迹照片与语义分析结果放到同一视图：地图点聚合、照片墙与跨轨迹对比。"
      :image="portalHero"
      compact
    >
      <template #actions>
        <el-button plain :loading="loading" @click="load"><el-icon><Refresh /></el-icon> 刷新数据</el-button>
      </template>
    </PageHero>

    <div class="portal-stat-grid">
      <div class="portal-stat-card">
        <span class="portal-stat-card__icon"><el-icon><Picture /></el-icon></span>
        <div class="portal-stat-card__copy">
          <div class="portal-stat-card__label">田野照片</div>
          <div class="portal-stat-card__value">{{ formatNumber(stats?.photo_total) }}</div>
          <div class="portal-stat-card__meta">数据库 track_photo 全量记录</div>
        </div>
      </div>
      <div class="portal-stat-card">
        <span class="portal-stat-card__icon green"><el-icon><OfficeBuilding /></el-icon></span>
        <div class="portal-stat-card__copy">
          <div class="portal-stat-card__label">覆盖公园</div>
          <div class="portal-stat-card__value">{{ formatNumber(stats?.park_count) }}</div>
          <div class="portal-stat-card__meta">经调研任务关联的真实公园</div>
        </div>
      </div>
      <div class="portal-stat-card">
        <span class="portal-stat-card__icon violet"><el-icon><MapLocation /></el-icon></span>
        <div class="portal-stat-card__copy">
          <div class="portal-stat-card__label">轨迹条数</div>
          <div class="portal-stat-card__value">{{ formatNumber(stats?.track_count) }}</div>
          <div class="portal-stat-card__meta">总里程 {{ stats?.distance_km ?? 0 }} km</div>
        </div>
      </div>
      <div class="portal-stat-card">
        <span class="portal-stat-card__icon orange"><el-icon><Notebook /></el-icon></span>
        <div class="portal-stat-card__copy">
          <div class="portal-stat-card__label">调研事件</div>
          <div class="portal-stat-card__value">{{ formatNumber(stats?.event_count) }}</div>
          <div class="portal-stat-card__meta">survey_events 语义化单元</div>
        </div>
      </div>
    </div>

    <section class="section-card filter-surface">
      <div class="section-card__header">
        <div><h2>筛选条件</h2><p>按公园、轨迹、语义编码与拍摄时间收窄范围，地图与照片墙同步生效。</p></div>
      </div>
      <div class="fg-filters">
        <label class="fg-filter"><span>遗址公园</span><el-select v-model="filters.parkId" clearable filterable placeholder="全部公园"><el-option v-for="park in parkOptions" :key="park.park_id" :label="`${park.park_name}（${park.photo_count}）`" :value="park.park_id" /></el-select></label>
        <label class="fg-filter"><span>轨迹任务</span><el-select v-model="filters.trackId" clearable filterable placeholder="全部轨迹"><el-option v-for="track in trackOptions" :key="track.track_id" :label="`${track.track_name}（${track.photo_count}）`" :value="track.track_id" /></el-select></label>
        <label class="fg-filter"><span>语义编码</span><el-select v-model="filters.code" clearable placeholder="A–F 全部"><el-option v-for="option in codeOptions" :key="option.code" :label="`${option.code} ${option.name}（${option.count}）`" :value="option.code" /></el-select></label>
        <label class="fg-filter fg-filter--wide"><span>拍摄时间</span><el-date-picker v-model="filters.dateRange" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="起始日期" end-placeholder="截止日期" /></label>
        <div class="fg-filter-actions">
          <el-button type="primary" :loading="loading" @click="load">应用筛选</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </div>
      </div>
      <div v-if="stats?.by_code" class="fg-code-chips">
        <span v-for="option in codeOptions" :key="option.code" class="fg-code-chip"><i :style="{ background: CODE_COLORS[option.code] }"></i>{{ option.code }} {{ option.name }} · {{ option.count }}</span>
      </div>
    </section>

    <StatusState v-if="error" type="error" title="田野影像数据加载失败" :description="error" action-label="重新加载" @action="load" />

    <template v-else>
      <section class="chart-card fg-map-card">
        <div class="section-card__header">
          <div><h2>照片地图</h2><p>全部 {{ formatNumber(total) }} 个筛选结果按点位聚合；点击点位查看照片与语义描述。</p></div>
        </div>
        <div class="fg-map-shell">
          <div ref="mapRef" class="fg-map" aria-label="田野照片分布地图"></div>
          <StatusState v-if="mapStatus === 'loading'" class="fg-map-state" type="loading" title="正在加载地图服务" />
          <StatusState v-else-if="mapStatus === 'missing-key'" class="fg-map-state" type="error" title="地图服务暂不可用" description="请在前端环境变量中配置 VITE_AMAP_JS_KEY；照片墙不受影响。" />
          <StatusState v-else-if="mapStatus === 'error'" class="fg-map-state" type="error" title="地图服务加载失败" :description="mapError" action-label="重新加载" @action="initMap" />
          <div v-if="mapStatus === 'ready'" class="fg-map-legend"><strong>语义编码</strong><span v-for="option in codeOptions" :key="option.code"><i :style="{ background: CODE_COLORS[option.code] }"></i>{{ option.code }} {{ option.name }}</span></div>
        </div>
      </section>

      <section class="section-card fg-wall-card">
        <div class="section-card__header">
          <div><h2>照片墙</h2><p>共 {{ formatNumber(total) }} 张，缩略图按需懒加载，点击查看完整语义描述。</p></div>
        </div>
        <StatusState v-if="!loading && !items.length" type="empty" title="暂无匹配照片" description="调整筛选条件后重试。" />
        <template v-else>
          <div class="fg-wall">
            <button v-for="photo in wallItems" :key="photo.photo_id" type="button" class="fg-wall-item" @click="openDetail(photo)">
              <img :src="photo.thumb_url" :alt="photo.caption || `照片 ${photo.photo_id}`" loading="lazy" decoding="async" />
              <span class="fg-wall-item__code" :style="{ background: CODE_COLORS[photo.code] }">{{ photo.code }}</span>
              <span class="fg-wall-item__caption">{{ photo.caption || photo.address || '未命名照片' }}</span>
            </button>
          </div>
          <div class="fg-pagination">
            <el-pagination
              v-model:current-page="wallPage"
              :page-size="WALL_PAGE_SIZE"
              :total="items.length"
              layout="prev, pager, next, total"
              background
              hide-on-single-page
            />
          </div>
        </template>
      </section>

      <section class="chart-card">
        <div class="section-card__header">
          <div><h2>跨轨迹语义构成对比</h2><p>按 A–F 编码统计各轨迹照片构成占比，数据来自 <code>/track/analysis/compare</code>。</p></div>
        </div>
        <StatusState v-if="compareError" type="error" title="语义对比加载失败" :description="compareError" />
        <StatusState v-else-if="compareLoading" type="loading" title="正在计算语义构成" />
        <div v-else ref="compareRef" class="chart-canvas tall"></div>
      </section>
    </template>

    <el-dialog v-model="detailVisible" :title="activePhoto?.caption || '照片详情'" width="min(900px, 94vw)" append-to-body>
      <div v-if="activePhoto" class="fg-detail">
        <img class="fg-detail__image" :src="activePhoto.photo_url" :alt="activePhoto.caption || '田野照片'" loading="lazy" />
        <div class="fg-detail__body">
          <div class="fg-detail__tags">
            <span class="fg-detail__tag" :style="{ background: CODE_COLORS[activePhoto.code] }">{{ activePhoto.code }} {{ activePhoto.code_name }}</span>
            <span v-if="activePhoto.park_name" class="fg-detail__tag fg-detail__tag--soft">{{ activePhoto.park_name }}</span>
          </div>
          <dl class="fg-detail__meta">
            <div><dt>拍摄时间</dt><dd>{{ formatTime(activePhoto.shot_time) }}</dd></div>
            <div><dt>所属轨迹</dt><dd>{{ activePhoto.track_name || '—' }}</dd></div>
            <div><dt>语义地址</dt><dd>{{ activePhoto.address || '—' }}</dd></div>
            <div><dt>经纬度</dt><dd>{{ coordinateText(activePhoto) }}</dd></div>
          </dl>
          <p class="fg-detail__desc">{{ activePhoto.description || '暂无视觉描述。' }}</p>
          <div v-if="activePhoto.tags?.length" class="fg-detail__taglist">
            <span v-for="tag in activePhoto.tags" :key="tag"># {{ tag }}</span>
          </div>
          <div class="fg-detail__actions">
            <el-button v-if="activePhoto.survey_task_id" type="primary" @click="goToTask(activePhoto)">前往所属调研任务</el-button>
            <el-button plain @click="detailVisible = false">关闭</el-button>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { Picture, OfficeBuilding, MapLocation, Notebook, Refresh } from '@element-plus/icons-vue'
import PageHero from '@/components/portal/PageHero.vue'
import StatusState from '@/components/common/StatusState.vue'
import { getPhotosOverview, compareTracks } from '@/utils/surveyApi'
import { AMapProvider } from '@/features/map/provider/AMapProvider'
import { toGcj02 } from '@/features/map/coordinates'
import portalHero from '@/assets/images/portal-hero.webp'

const WALL_PAGE_SIZE = 24
const CODE_COLORS = { A: '#2563eb', B: '#7c3aed', C: '#22c55e', D: '#f59e0b', E: '#ef4444', F: '#06b6d4', G: '#94a3b8' }

const router = useRouter()
const mapRef = ref()
const compareRef = ref()
const mapStatus = ref('loading')
const mapError = ref('')
const loading = ref(true)
const error = ref('')
const compareLoading = ref(false)
const compareError = ref('')
const items = ref([])
const total = ref(0)
const stats = ref(null)
const wallPage = ref(1)
const detailVisible = ref(false)
const activePhoto = ref(null)
const filters = reactive({ parkId: '', trackId: '', code: '', dateRange: [] })

let provider
let observer
let compareChart

const parkOptions = computed(() => stats.value?.parks || [])
const trackOptions = computed(() => {
  const tracks = stats.value?.tracks || []
  if (!filters.parkId) return tracks
  return tracks.filter((track) => track.park_id === filters.parkId)
})
const codeOptions = computed(() => Object.entries(stats.value?.by_code || {}).map(([code, row]) => ({ code, name: row.name, count: row.count })))
const wallItems = computed(() => {
  const start = (wallPage.value - 1) * WALL_PAGE_SIZE
  return items.value.slice(start, start + WALL_PAGE_SIZE)
})

onMounted(async () => {
  await load()
  initMap()
})
onBeforeUnmount(() => {
  observer?.disconnect()
  compareChart?.dispose()
  provider?.destroy()
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const params = { page: 1, page_size: 2000 }
    if (filters.parkId) params.park_id = filters.parkId
    if (filters.trackId) params.track_id = filters.trackId
    if (filters.code) params.code = filters.code
    if (filters.dateRange?.length === 2) {
      params.date_from = filters.dateRange[0]
      params.date_to = filters.dateRange[1]
    }
    const data = await getPhotosOverview(params)
    items.value = data.items || []
    total.value = data.total || 0
    stats.value = data.stats || null
    wallPage.value = 1
    if (filters.parkId && filters.trackId && !trackOptions.value.some((track) => track.track_id === filters.trackId)) {
      filters.trackId = ''
    }
    await nextTick()
    updateMapPoints()
    loadCompare()
  } catch (e) {
    error.value = e.response?.data?.detail || '请检查后端服务后重试。'
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  Object.assign(filters, { parkId: '', trackId: '', code: '', dateRange: [] })
  load()
}

async function initMap() {
  provider?.destroy()
  mapError.value = ''
  const key = import.meta.env.VITE_AMAP_JS_KEY
  if (!key) {
    mapStatus.value = 'missing-key'
    return
  }
  mapStatus.value = 'loading'
  try {
    provider = new AMapProvider({
      key,
      securityCode: import.meta.env.VITE_AMAP_SECURITY_CODE,
      mapStyle: import.meta.env.VITE_AMAP_MAP_STYLE,
    })
    await provider.mount(mapRef.value)
    provider.onPointClick(handleMarkerClick)
    updateMapPoints()
    observer?.disconnect()
    observer = new ResizeObserver(() => provider.resize())
    observer.observe(mapRef.value)
    mapStatus.value = 'ready'
  } catch (e) {
    mapStatus.value = e.message === 'MISSING_AMAP_KEY' ? 'missing-key' : 'error'
    mapError.value = e.message || '请检查地图服务配置。'
  }
}

function photoPoint(photo) {
  return {
    id: photo.photo_id,
    name: photo.caption || photo.address || `照片 ${photo.photo_id}`,
    longitude: photo.longitude,
    latitude: photo.latitude,
    coordinateSystem: 'WGS84',
    ...photo,
  }
}

function updateMapPoints() {
  if (mapStatus.value !== 'ready' || !provider) return
  const points = items.value
    .filter((photo) => Number.isFinite(photo.longitude) && Number.isFinite(photo.latitude))
    .map(photoPoint)
  provider.setPoints(points)
  if (points.length) {
    try {
      provider.fitBounds(points.map((point) => toGcj02(point)))
    } catch {
      provider.setView({ center: [104.2, 35.8], zoom: 4.6 })
    }
  }
}

function handleMarkerClick(point) {
  if (!point?.photo_id) return
  openDetail(point)
}

function openDetail(photo) {
  activePhoto.value = photo
  detailVisible.value = true
  if (mapStatus.value === 'ready') provider?.setSelectedPoint(photo.photo_id)
}

function goToTask(photo) {
  detailVisible.value = false
  router.push(`/survey/${photo.survey_task_id}`)
}

async function loadCompare() {
  const trackIds = (stats.value?.tracks || []).map((track) => track.track_id)
  if (!trackIds.length) return
  compareLoading.value = true
  compareError.value = ''
  try {
    const data = await compareTracks(trackIds)
    await nextTick()
    renderCompareChart(data)
  } catch (e) {
    compareError.value = e.response?.data?.detail || '无法读取语义分析结果。'
  } finally {
    compareLoading.value = false
  }
}

function renderCompareChart(data) {
  if (!compareRef.value || !data?.items?.length) return
  compareChart?.dispose()
  compareChart = echarts.init(compareRef.value)
  observer ||= new ResizeObserver(() => compareChart?.resize())
  observer.observe(compareRef.value)
  const codes = ['A', 'B', 'C', 'D', 'E', 'F', 'G'].filter((code) => data.items.some((item) => (item.composition || []).some((row) => row.code === code && row.count)))
  const series = codes.map((code) => ({
    name: `${code} ${data.type_names?.[code] || ''}`.trim(),
    type: 'bar',
    stack: 'total',
    barMaxWidth: 34,
    itemStyle: { color: CODE_COLORS[code] },
    data: data.items.map((item) => {
      const composition = item.composition || []
      const sum = composition.reduce((acc, row) => acc + (row.count || 0), 0) || 1
      const row = composition.find((entry) => entry.code === code)
      return row ? Number(((row.count / sum) * 100).toFixed(1)) : 0
    }),
  }))
  compareChart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: (value) => `${value}%` },
    legend: { top: 0, type: 'scroll' },
    grid: { top: 48, right: 20, bottom: 70, left: 48 },
    xAxis: { type: 'category', data: data.items.map((item) => item.name), axisLabel: { interval: 0, rotate: 30, fontSize: 10 } },
    yAxis: { type: 'value', max: 100, axisLabel: { formatter: '{value}%' }, splitLine: { lineStyle: { color: '#eef1f5' } } },
    series,
  })
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString('zh-CN')
}

function formatTime(value) {
  return value ? String(value).replace('T', ' ').slice(0, 19) : '—'
}

function coordinateText(photo) {
  if (!Number.isFinite(photo.longitude) || !Number.isFinite(photo.latitude)) return '暂无坐标'
  return `${photo.longitude.toFixed(5)}, ${photo.latitude.toFixed(5)}（WGS84）`
}
</script>

<style scoped lang="scss">
.field-gallery-page :deep(.page-context__actions) { justify-content: flex-end; }
.fg-filters { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)) 1.4fr auto; gap: 14px; align-items: end; }
.fg-filter { display: grid; gap: 6px; min-width: 0; }
.fg-filter > span { color: var(--text-secondary); font-size: 12px; }
.fg-filter :deep(.el-select), .fg-filter :deep(.el-date-editor) { width: 100%; }
.fg-filter-actions { display: flex; gap: 8px; }
.fg-code-chips { margin-top: 16px; display: flex; flex-wrap: wrap; gap: 8px; }
.fg-code-chip { display: inline-flex; align-items: center; gap: 6px; padding: 5px 10px; border: 1px solid var(--border); border-radius: 999px; color: var(--text-secondary); font-size: 11px; }
.fg-code-chip i { width: 8px; height: 8px; border-radius: 50%; }
.fg-map-shell { position: relative; height: 540px; border: 1px solid var(--border); border-radius: 14px; overflow: hidden; background: #edf3fb; }
.fg-map { width: 100%; height: 100%; }
.fg-map-state { position: absolute; inset: 50% auto auto 50%; width: min(440px, calc(100% - 32px)); min-height: 220px; transform: translate(-50%, -50%); }
.fg-map-legend { position: absolute; left: 14px; bottom: 14px; z-index: 2; padding: 12px 14px; display: grid; gap: 6px; border: 1px solid var(--border); border-radius: 11px; background: rgba(255, 255, 255, .94); box-shadow: var(--shadow-soft); font-size: 11px; }
.fg-map-legend span { display: flex; align-items: center; gap: 6px; color: var(--text-secondary); }
.fg-map-legend i { width: 9px; height: 9px; border-radius: 50%; }
.fg-wall { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 14px; }
.fg-wall-item { position: relative; padding: 0; border: 1px solid var(--border); border-radius: 12px; overflow: hidden; background: #edf2f8; cursor: pointer; aspect-ratio: 4 / 3; }
.fg-wall-item img { width: 100%; height: 100%; object-fit: cover; display: block; transition: transform .25s ease; }
.fg-wall-item:hover img { transform: scale(1.04); }
.fg-wall-item__code { position: absolute; top: 8px; left: 8px; min-width: 22px; padding: 2px 7px; border-radius: 6px; color: #fff; font-size: 11px; font-weight: 700; text-align: center; }
.fg-wall-item__caption { position: absolute; left: 0; right: 0; bottom: 0; padding: 16px 10px 8px; color: #fff; font-size: 11px; line-height: 1.4; text-align: left; background: linear-gradient(180deg, rgba(15, 23, 42, 0) 0%, rgba(15, 23, 42, .82) 100%); display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.fg-pagination { margin-top: 20px; display: flex; justify-content: center; }
.fg-detail { display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr); gap: 20px; }
.fg-detail__image { width: 100%; max-height: 560px; object-fit: contain; border-radius: 12px; background: #0f172a; }
.fg-detail__body { min-width: 0; display: flex; flex-direction: column; gap: 14px; }
.fg-detail__tags { display: flex; flex-wrap: wrap; gap: 8px; }
.fg-detail__tag { padding: 4px 10px; border-radius: 999px; color: #fff; font-size: 11px; font-weight: 600; }
.fg-detail__tag--soft { color: var(--brand-700); background: var(--brand-50); font-weight: 500; }
.fg-detail__meta { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 0; }
.fg-detail__meta > div { padding: 10px 12px; border-radius: 10px; background: var(--surface-soft); }
.fg-detail__meta dt { color: var(--text-tertiary); font-size: 10px; }
.fg-detail__meta dd { margin: 4px 0 0; font-size: 12px; line-height: 1.5; word-break: break-all; }
.fg-detail__desc { margin: 0; color: var(--text-secondary); font-size: 13px; line-height: 1.85; }
.fg-detail__taglist { display: flex; flex-wrap: wrap; gap: 6px; }
.fg-detail__taglist span { padding: 3px 8px; border-radius: 6px; color: var(--text-secondary); background: var(--surface-soft); font-size: 11px; }
.fg-detail__actions { margin-top: auto; display: flex; gap: 8px; }
@media (max-width: 1080px) {
  .fg-filters { grid-template-columns: 1fr 1fr; }
  .fg-filter--wide { grid-column: 1 / -1; }
}
@media (max-width: 760px) {
  .fg-filters { grid-template-columns: 1fr; }
  .fg-map-shell { height: 380px; }
  .fg-detail { grid-template-columns: 1fr; }
  .fg-detail__meta { grid-template-columns: 1fr; }
}
</style>
