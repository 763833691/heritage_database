<template>
  <div class="map-page">
    <div :class="['map-workspace', { 'filter-collapsed': filterCollapsed, 'detail-open': !!selectedPoint }]">
      <aside v-show="!filterCollapsed" class="map-side-panel">
        <div class="map-panel-tabs">
          <button class="active" type="button">公园筛选</button>
          <button type="button" @click="layerInfoVisible = true">图层管理</button>
        </div>
        <div class="map-filter-body">
          <div class="map-filter-group">
            <div><strong>公园类型</strong><button type="button" @click="filters.parkType = ''">清空</button></div>
            <div class="chip-list">
              <button v-for="type in ['', '城市型', '城郊型', '乡村型']" :key="type || 'all'" :class="{ active: filters.parkType === type }" type="button" @click="filters.parkType = type">{{ type || '全部' }}</button>
            </div>
          </div>
          <div class="map-filter-group">
            <div><strong>所属区域</strong><button type="button" @click="filters.province = ''">清空</button></div>
            <el-select v-model="filters.province" clearable filterable placeholder="全部区域">
              <el-option v-for="province in provinces" :key="province" :label="province" :value="province" />
            </el-select>
          </div>
          <div class="map-filter-group">
            <div><strong>批次</strong><button type="button" @click="filters.batch = ''">清空</button></div>
            <div class="chip-list">
              <button :class="{ active: !filters.batch }" type="button" @click="filters.batch = ''">全部</button>
              <button v-for="batch in batches" :key="batch" :class="{ active: Number(filters.batch) === Number(batch) }" type="button" @click="filters.batch = batch">第{{ batch }}批</button>
            </div>
          </div>
          <div class="map-filter-group map-filter-group--compact">
            <div><strong>最低综合分</strong><button type="button" @click="filters.minScore = 0">清空</button></div>
            <el-slider v-model="filters.minScore" :min="0" :max="100" :show-input="false" />
          </div>
          <el-button type="primary" class="map-filter-submit" @click="applyFilters">筛选公园</el-button>
          <el-button class="map-filter-reset" @click="resetFilters">重置筛选</el-button>
        </div>
        <div class="map-park-list__section">
          <div class="map-park-list__label">公园列表 <span>{{ filteredPoints.length }} 个</span></div>
          <div class="map-park-list__body">
            <StatusState v-if="!filteredPoints.length" type="empty" title="暂无公园" description="调整筛选条件后重试。" />
            <button
              v-for="point in filteredPoints"
              :key="point.id"
              type="button"
              :class="['map-park-card', { 'map-park-card--active': selectedPoint?.id === point.id }]"
              @click="selectPoint(point)"
            >
              <img :src="parkCover" :alt="`${point.name}封面`" loading="lazy" />
              <div class="map-park-card__overlay">
                <strong>{{ point.name }}</strong>
              </div>
              <span v-if="point.score != null" class="map-park-card__score">{{ point.score }}</span>
            </button>
          </div>
        </div>
      </aside>

      <section class="map-canvas-shell">
        <button class="panel-collapse" type="button" :aria-label="filterCollapsed ? '展开筛选面板' : '收起筛选面板'" @click="toggleFilterPanel"><el-icon><DArrowLeft /></el-icon></button>
        <div ref="mapRef" class="map-canvas" aria-label="遗址公园专题地图"></div>
        <div class="map-utility-actions">
          <el-button v-if="auth.isAdmin" type="primary" size="small" :disabled="mapStatus !== 'ready'" @click="beginCreatePark">
            <el-icon><Plus /></el-icon> 创建公园
          </el-button>
          <el-button size="small" plain @click="guideVisible=true"><el-icon><QuestionFilled /></el-icon> 使用指南</el-button>
          <el-button size="small" plain @click="copyShareLink"><el-icon><Share /></el-icon> 分享</el-button>
        </div>
        <div v-if="isPickingLocation" class="map-picking-notice" role="status">
          <div><el-icon><LocationFilled /></el-icon><span><strong>请在地图上点击公园位置</strong><small>选定后填写公园基本信息</small></span></div>
          <el-button size="small" @click="cancelCreatePark">取消</el-button>
        </div>
        <StatusState v-if="mapStatus==='loading'" class="map-state" type="loading" title="正在加载地图服务" />
        <StatusState v-else-if="mapStatus==='missing-key'" class="map-state" type="error" title="地图服务暂不可用" description="请在前端环境变量中配置 VITE_AMAP_JS_KEY；页面不会回退为假地图。" />
        <StatusState v-else-if="mapStatus==='error'" class="map-state" type="error" title="地图服务加载失败" :description="mapError" action-label="重新加载" @action="initMap" />
        <div v-if="mapStatus==='ready'" class="map-controls"><button type="button" title="回到全国" @click="resetView"><el-icon><Aim /></el-icon></button><button type="button" title="放大" @click="changeZoom(1)"><el-icon><Plus /></el-icon></button><button type="button" title="缩小" @click="changeZoom(-1)"><el-icon><Minus /></el-icon></button></div>
        <div class="map-legend"><strong>公园数量</strong><span><i></i> 当前筛选 {{ filteredPoints.length }} 个</span><small>点位经 WGS84 → GCJ-02 单一适配层转换</small></div>
        <button class="mobile-filter-button" type="button" @click="mobileFilterOpen=true"><el-icon><Filter /></el-icon>筛选</button>
        <div v-if="filteredPoints.length" class="map-mobile-park-strip">
          <button
            v-for="point in filteredPoints"
            :key="`mobile-${point.id}`"
            type="button"
            :class="['map-park-card', { 'map-park-card--active': selectedPoint?.id === point.id }]"
            @click="selectPoint(point)"
          >
            <img :src="parkCover" :alt="`${point.name}封面`" loading="lazy" />
            <div class="map-park-card__overlay">
              <strong>{{ point.name }}</strong>
              <small>{{ point.province }}</small>
            </div>
          </button>
        </div>
        <button v-if="!selectedPoint && filteredPoints.length" class="map-result-hint" type="button" @click="selectPoint(filteredPoints[0])">{{ filteredPoints.length }} 个结果 · 查看首个公园</button>
      </section>

      <aside v-if="selectedPoint" class="map-detail-panel">
        <img :src="parkCover" :alt="`${selectedPoint.name}主题封面`" />
        <div class="map-detail-panel__body"><div class="map-detail-panel__heading"><div><span>{{ selectedPoint.parkType||'类型未录入' }}</span><h2>{{ selectedPoint.name }}</h2></div><button type="button" aria-label="关闭详情" @click="selectPoint(null)"><el-icon><Close /></el-icon></button></div><p class="map-detail-panel__location"><el-icon><Location /></el-icon>{{ selectedPoint.province }} {{ selectedPoint.city }}</p><span class="map-detail-panel__batch">{{ selectedPoint.batch||'批次未录入' }}</span><h3>关键指标</h3><div class="map-detail-metrics"><div><span>综合评分</span><strong>{{ selectedPoint.score??'—' }}</strong></div><div v-for="([name,value],index) in Object.entries(selectedPoint.metrics||{}).slice(0,3)" :key="name"><span>{{ index===0?'研究指标':shortText(name) }}</span><strong>{{ value??'—' }}</strong></div></div><h3>公园简介</h3><p class="map-detail-panel__summary">{{ selectedPoint.summary||'当前公园尚未录入简介。' }}</p><div class="map-detail-panel__actions"><el-button type="primary" @click="$router.push(`/parks/${selectedPoint.id}`)">进入详情页</el-button><el-button plain @click="$router.push({path:'/compare',query:{park_ids:selectedPoint.id}})">对比分析</el-button><el-button v-if="auth.isAdmin" class="map-detail-panel__delete" type="danger" plain :loading="deletingPark" @click="deleteSelectedPark"><el-icon><Delete /></el-icon>删除公园</el-button></div></div>
      </aside>
    </div>

    <el-drawer v-model="mobileFilterOpen" direction="btt" size="78%" title="筛选遗址公园" append-to-body>
      <div class="mobile-filter-content">
        <div class="map-filter-group"><strong>公园类型</strong><el-select v-model="filters.parkType" clearable placeholder="全部类型"><el-option v-for="type in ['城市型','城郊型','乡村型']" :key="type" :label="type" :value="type" /></el-select></div>
        <div class="map-filter-group"><strong>所属区域</strong><el-select v-model="filters.province" clearable filterable placeholder="全部区域"><el-option v-for="province in provinces" :key="province" :label="province" :value="province" /></el-select></div>
        <div class="map-filter-group"><strong>批次</strong><el-select v-model="filters.batch" clearable placeholder="全部批次"><el-option v-for="batch in batches" :key="batch" :label="`第${batch}批`" :value="batch" /></el-select></div>
        <div class="map-filter-group"><strong>最低综合分</strong><el-slider v-model="filters.minScore" :min="0" :max="100" show-input /></div>
        <el-button type="primary" @click="applyMobileFilters">应用筛选</el-button>
        <el-button @click="resetFilters(); mobileFilterOpen = false">重置筛选</el-button>
      </div>
    </el-drawer>
    <el-dialog v-model="guideVisible" title="地图使用指南" width="min(560px,92vw)"><p class="guide-copy">使用筛选面板缩小研究范围，点击地图点位查看详情。筛选条件会同步到地址栏，刷新或分享后仍可恢复。高德地图版权与审图信息保留在地图画布中。</p></el-dialog>
    <el-dialog v-model="layerInfoVisible" title="地图图层" width="min(520px,92vw)"><div class="layer-list"><div><strong>浅色基础底图</strong><span>高德地图 JavaScript API 2.0</span></div><div><strong>遗址公园点图层</strong><span>Loca 2.0 + MarkerCluster</span></div><div><strong>筛选交互层</strong><span>当前真实公园接口数据</span></div></div></el-dialog>
    <ParkFormDialog
      v-model="createDialogVisible"
      :initial-values="createFormSeed"
      location-picked
      @saved="handleParkCreated"
    />
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/utils/api'
import { useAuthStore } from '@/stores/auth'
import StatusState from '@/components/common/StatusState.vue'
import ParkFormDialog from '@/components/park/ParkFormDialog.vue'
import { gcj02ToWgs84 } from '@/features/map/coordinates'
import { parkToMapPoint } from '@/features/map/parkPointAdapter'
import { AMapProvider } from '@/features/map/provider/AMapProvider'
import parkCover from '@/assets/images/park-cover-fallback.webp'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const mapRef = ref()
const mapStatus = ref('loading')
const mapError = ref('')
const points = ref([])
const selectedPoint = ref(null)
const filterCollapsed = ref(false)
const mobileFilterOpen = ref(false)
const guideVisible = ref(false)
const layerInfoVisible = ref(false)
const isPickingLocation = ref(false)
const createDialogVisible = ref(false)
const createFormSeed = ref(null)
const deletingPark = ref(false)
let provider
let observer

const filters = reactive({
  parkType: String(route.query.type || ''),
  province: String(route.query.province || ''),
  batch: route.query.batch ? Number(route.query.batch) : '',
  minScore: Number(route.query.minScore || 0),
})
const provinces = computed(() => [...new Set(points.value.map((point) => point.province).filter(Boolean))])
const batches = computed(() => [...new Set(
  points.value
    .map((point) => Number(String(point.batch || '').replace(/\D/g, '')))
    .filter(Boolean)
)].sort((a, b) => a - b))
const filteredPoints = computed(() => points.value.filter((point) => (
  (!filters.parkType || point.parkType === filters.parkType)
  && (!filters.province || point.province === filters.province)
  && (!filters.batch || Number(String(point.batch || '').replace(/\D/g, '')) === Number(filters.batch))
  && (!filters.minScore || Number(point.score || 0) >= filters.minScore)
)))

onMounted(loadPoints)
onBeforeUnmount(() => {
  observer?.disconnect()
  provider?.destroy()
})

watch(filterCollapsed, () => resizeMapAfterLayout())
watch(createDialogVisible, (open) => {
  if (!open) cancelCreatePark()
})

async function fetchPoints() {
  const response = await api.get('/parks', { params: { page_size: 100 }, silent: true })
  points.value = (response.data.items || [])
    .map(parkToMapPoint)
    .filter((point) => Number.isFinite(point.longitude) && Number.isFinite(point.latitude))
}

async function loadPoints() {
  try {
    await fetchPoints()
    await nextTick()
    await initMap()
    const selected = route.query.selected
      && points.value.find((point) => String(point.id) === String(route.query.selected))
    if (selected) selectPoint(selected)
    else if (points.value.length) selectPoint(points.value[0])
  } catch (error) {
    mapStatus.value = 'error'
    mapError.value = error.response?.data?.detail || '无法读取公园点位数据。'
  }
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
    provider.onPointClick(handlePointClick)
    provider.onMapClick(handleMapClick)
    provider.setPoints(filteredPoints.value)
    observer?.disconnect()
    observer = new ResizeObserver(() => provider.resize())
    observer.observe(mapRef.value)
    mapStatus.value = 'ready'
  } catch (error) {
    mapStatus.value = error.message === 'MISSING_AMAP_KEY' ? 'missing-key' : 'error'
    mapError.value = error.message || '请检查地图服务配置。'
  }
}

function beginCreatePark() {
  if (mapStatus.value !== 'ready') {
    ElMessage.warning('地图加载完成后才可以选择公园位置')
    return
  }
  selectPoint(null)
  createFormSeed.value = null
  provider?.clearDraftPoint()
  provider?.setPickingMode(true)
  isPickingLocation.value = true
}

function handleMapClick(position) {
  if (!isPickingLocation.value) return
  const [longitude, latitude] = gcj02ToWgs84(position.longitude, position.latitude)
  createFormSeed.value = {
    longitude: Number(longitude.toFixed(6)),
    latitude: Number(latitude.toFixed(6)),
  }
  provider?.setDraftPoint(position)
  provider?.setPickingMode(false)
  isPickingLocation.value = false
  createDialogVisible.value = true
}

function handlePointClick(point) {
  if (isPickingLocation.value) return
  selectPoint(point)
}

function cancelCreatePark() {
  isPickingLocation.value = false
  provider?.setPickingMode(false)
  provider?.clearDraftPoint()
  if (!createDialogVisible.value) createFormSeed.value = null
}

async function handleParkCreated(result) {
  const createdId = result?.id
  Object.assign(filters, { parkType: '', province: '', batch: '', minScore: 0 })
  await fetchPoints()
  provider?.setPoints(filteredPoints.value)
  const createdPoint = points.value.find((point) => String(point.id) === String(createdId))
  if (createdPoint) selectPoint(createdPoint)
  else syncQuery()
}

async function deleteSelectedPark() {
  const point = selectedPoint.value
  if (!point || deletingPark.value) return

  try {
    await ElMessageBox.confirm(
      `确定删除“${point.name}”吗？该公园的关联数据也将一并删除，此操作无法恢复。`,
      '删除公园',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger',
      }
    )
  } catch (action) {
    if (action !== 'cancel' && action !== 'close') {
      ElMessage.error('无法打开删除确认框，请稍后重试')
    }
    return
  }

  deletingPark.value = true
  try {
    await api.delete(`/admin/parks/${point.id}`)
    selectPoint(null)
    await fetchPoints()
    provider?.setPoints(filteredPoints.value)
    ElMessage.success(`“${point.name}”已删除`)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '删除失败，请稍后重试')
  } finally {
    deletingPark.value = false
  }
}

function applyFilters() {
  provider?.setPoints(filteredPoints.value)
  syncQuery()
  if (selectedPoint.value && !filteredPoints.value.some((point) => point.id === selectedPoint.value.id)) {
    selectedPoint.value = null
  }
}

function resetFilters() {
  Object.assign(filters, { parkType: '', province: '', batch: '', minScore: 0 })
  applyFilters()
}

function syncQuery() {
  router.replace({
    query: {
      ...(filters.province && { province: filters.province }),
      ...(filters.parkType && { type: filters.parkType }),
      ...(filters.batch && { batch: filters.batch }),
      ...(filters.minScore && { minScore: filters.minScore }),
      ...(selectedPoint.value && { selected: selectedPoint.value.id }),
    },
  })
}

function toggleFilterPanel() {
  filterCollapsed.value = !filterCollapsed.value
}

function resizeMapAfterLayout() {
  nextTick(() => {
    provider?.resize()
    setTimeout(() => provider?.resize(), 220)
  })
}

function selectPoint(point) {
  selectedPoint.value = point
  provider?.setSelectedPoint(point?.id || null)
  syncQuery()
  nextTick(() => provider?.resize())
}

function resetView() {
  provider?.setView({ center: [104.2, 35.8], zoom: 4.6 })
}

function changeZoom(delta) {
  const current = provider?.map?.getZoom?.() || 5
  provider?.map?.setZoom?.(current + delta)
}

function applyMobileFilters() {
  mobileFilterOpen.value = false
  applyFilters()
}

async function copyShareLink() {
  try {
    await navigator.clipboard.writeText(window.location.href)
    ElMessage.success('分享链接已复制')
  } catch {
    ElMessage.warning('请从地址栏复制当前链接')
  }
}

function shortText(text) {
  return String(text || '指标').replace(/[（(].*$/, '').slice(0, 7)
}
</script>

<style scoped lang="scss">
.map-page{display:flex!important;flex-direction:column;height:100%;overflow:hidden;overscroll-behavior:none;touch-action:pan-x pan-y}
.map-workspace{flex:1;min-height:0;height:auto;position:relative;display:grid;grid-template-columns:278px minmax(0,1fr) 320px;grid-template-rows:minmax(0,1fr);overflow:hidden;overscroll-behavior:none;border:0;border-radius:0;background:#edf3fb;box-shadow:none;transition:grid-template-columns .2s ease}
.map-workspace.filter-collapsed{grid-template-columns:minmax(0,1fr) 320px}
.map-workspace.filter-collapsed:not(.detail-open){grid-template-columns:minmax(0,1fr)}
.map-side-panel{grid-column:1;grid-row:1;z-index:3;background:rgba(255,255,255,.97);min-width:0;min-height:0;overflow:hidden;display:flex;flex-direction:column;border-right:1px solid var(--border)}
.map-canvas-shell{grid-column:2;grid-row:1;min-width:0;min-height:0;position:relative;height:100%;overflow:hidden}
.map-workspace.filter-collapsed .map-canvas-shell{grid-column:1}
.map-workspace.filter-collapsed.detail-open .map-canvas-shell{grid-column:1}
.map-detail-panel{grid-column:3;grid-row:1;z-index:3;background:rgba(255,255,255,.97);min-width:0;min-height:0;overflow:hidden auto;border-left:1px solid var(--border)}
.map-workspace.filter-collapsed .map-detail-panel{grid-column:2}
.map-panel-tabs{height:44px;display:flex;flex-shrink:0;border-bottom:1px solid var(--border)}
.map-panel-tabs button{flex:1;border:0;background:none;color:var(--text-secondary);cursor:pointer;font-size:12px}
.map-panel-tabs button.active{color:var(--brand-600);font-weight:650;box-shadow:0 -2px 0 var(--brand-600) inset}
.map-filter-body{flex:0 0 auto;max-height:min(320px,42vh);padding:12px 14px 10px;overflow-y:auto;border-bottom:1px solid var(--border)}
.map-filter-group{display:grid;gap:8px;padding:0 0 12px;margin-bottom:12px;border-bottom:1px solid var(--border)}
.map-filter-group:last-of-type{border-bottom:0;margin-bottom:10px;padding-bottom:0}
.map-filter-group>div:first-child{display:flex;align-items:center;justify-content:space-between}
.map-filter-group strong{font-size:12px}
.map-filter-group>div:first-child button{border:0;background:none;color:var(--text-tertiary);font-size:10px;cursor:pointer}
.map-filter-group--compact{padding-bottom:8px;margin-bottom:8px}
.chip-list{display:flex;gap:5px;flex-wrap:wrap}
.chip-list button{padding:5px 8px;border:1px solid var(--border);border-radius:7px;color:var(--text-secondary);background:#fff;cursor:pointer;font-size:10px}
.chip-list button.active{border-color:var(--brand-600);color:#fff;background:var(--brand-600)}
.map-filter-submit,.map-filter-reset{width:100%;margin:0 0 6px}
.map-filter-reset{margin-left:0}
.map-park-list__section{flex:1 1 auto;min-height:0;display:flex;flex-direction:column;overflow:hidden}
.map-park-list__label{padding:10px 14px 8px;font-size:12px;font-weight:650;flex-shrink:0}
.map-park-list__label span{margin-left:6px;color:var(--text-tertiary);font-size:11px;font-weight:400}
.map-park-list__body{flex:1 1 auto;min-height:0;padding:0 10px 16px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;overflow-y:auto;align-content:start;overscroll-behavior:contain}
.map-park-card{position:relative;width:100%;height:72px;padding:0;border:2px solid transparent;border-radius:10px;overflow:hidden;background:#edf2f8;cursor:pointer;text-align:left;transition:border-color .2s ease}
.map-park-card:hover{border-color:var(--brand-200)}
.map-park-card--active{border-color:var(--brand-600);box-shadow:0 0 0 1px var(--brand-100)}
.map-park-card img{width:100%;height:100%;object-fit:cover;display:block}
.map-park-card__overlay{position:absolute;inset:0;display:flex;align-items:flex-end;padding:8px;background:linear-gradient(180deg,rgba(15,23,42,0) 10%,rgba(15,23,42,.82) 100%);color:#fff}
.map-park-card__overlay strong{font-size:11px;line-height:1.3;text-shadow:0 1px 3px rgba(0,0,0,.4);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.map-park-card__score{position:absolute;top:5px;right:5px;min-width:26px;padding:2px 5px;border-radius:6px;color:var(--brand-700);background:rgba(255,255,255,.92);font-size:10px;font-weight:700;text-align:center}
.panel-collapse{width:28px;height:40px;position:absolute;left:0;top:58px;z-index:6;border:1px solid var(--border);border-left:0;border-radius:0 8px 8px 0;color:var(--text-secondary);background:#fff;cursor:pointer;transition:transform .2s ease}
.map-workspace:not(.filter-collapsed) .panel-collapse{left:-1px}
.map-workspace.filter-collapsed .panel-collapse{top:16px}
.map-workspace.filter-collapsed .panel-collapse .el-icon{transform:rotate(180deg)}
.map-workspace.filter-collapsed .map-controls{left:40px}
.map-canvas{width:100%;height:100%;background:#edf3fb}
.map-state{position:absolute;inset:50% auto auto 50%;width:min(440px,calc(100% - 36px));min-height:240px;transform:translate(-50%,-50%);z-index:4;box-shadow:var(--shadow-soft)}
.map-controls{position:absolute;left:16px;top:16px;display:grid;z-index:2;border:1px solid var(--border);border-radius:11px;overflow:hidden;box-shadow:var(--shadow-soft)}
.map-controls button{width:38px;height:38px;border:0;border-bottom:1px solid var(--border);color:var(--text-secondary);background:#fff;cursor:pointer}
.map-controls button:last-child{border-bottom:0}
.map-legend{position:absolute;left:16px;bottom:16px;z-index:2;padding:13px 15px;display:grid;gap:6px;border:1px solid var(--border);border-radius:11px;background:rgba(255,255,255,.94);box-shadow:var(--shadow-soft);font-size:11px}
.map-legend span{display:flex;align-items:center;gap:6px;color:var(--text-secondary)}
.map-legend i{width:9px;height:9px;border-radius:50%;background:var(--brand-600)}
.map-legend small{max-width:190px;color:var(--text-tertiary);line-height:1.5}
.map-detail-panel>img{width:100%;height:190px;object-fit:cover}
.map-detail-panel__body{padding:20px}
.map-detail-panel__heading{display:flex;justify-content:space-between;gap:10px}
.map-detail-panel__heading span{color:var(--brand-600);font-size:10px}
.map-detail-panel__heading h2{margin:6px 0 0;font-size:21px;line-height:1.4}
.map-detail-panel__heading button{width:32px;height:32px;border:1px solid var(--border);border-radius:9px;background:#fff;cursor:pointer}
.map-detail-panel__location{margin:9px 0;display:flex;align-items:center;gap:5px;color:var(--text-secondary);font-size:12px}
.map-detail-panel__batch{display:inline-block;padding:6px 9px;border-radius:999px;color:#6d28d9;background:#f5f3ff;font-size:10px}
.map-detail-panel h3{margin:20px 0 10px;font-size:13px}
.map-detail-metrics{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.map-detail-metrics>div{padding:11px;border-radius:10px;background:var(--surface-soft)}
.map-detail-metrics span{display:block;color:var(--text-tertiary);font-size:9px}
.map-detail-metrics strong{display:block;margin-top:4px;font-size:16px}
.map-detail-panel__summary{color:var(--text-secondary);font-size:12px;line-height:1.75}
.map-detail-panel__actions{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:18px}
.map-result-hint{position:absolute;right:18px;top:18px;z-index:2;padding:10px 14px;border:1px solid var(--brand-100);border-radius:10px;color:var(--brand-600);background:#fff;cursor:pointer;box-shadow:var(--shadow-soft)}
.map-summary-bar{min-height:96px;padding:16px 24px;display:grid;grid-template-columns:repeat(3,1fr) 1.6fr;align-items:center;border:1px solid var(--border);border-radius:16px;background:#fff;box-shadow:var(--shadow-soft)}
.map-summary-bar>div{min-width:0;display:flex;align-items:center;gap:12px;padding:0 22px;border-right:1px solid var(--border)}
.map-summary-bar>div:first-child{padding-left:0}
.map-summary-bar>div:last-child{border:0}
.map-summary-bar p{display:grid}
.map-summary-bar small{color:var(--text-tertiary);font-size:10px}
.map-summary-bar strong{font-size:21px}
.map-summary-distribution{display:flex!important;flex-wrap:wrap!important}
.map-summary-distribution span{padding:5px 8px;border-radius:999px;background:var(--surface-soft);font-size:10px}
.mobile-filter-button{display:none}
.map-mobile-park-strip{display:none}
.guide-copy{color:var(--text-secondary);line-height:1.9}
.layer-list{display:grid;gap:10px}
.layer-list>div{padding:14px;display:flex;justify-content:space-between;gap:10px;border:1px solid var(--border);border-radius:11px}
.layer-list span{color:var(--text-secondary);font-size:12px}
.mobile-filter-content{display:grid;gap:18px}
.mobile-filter-content .map-filter-group{margin:0}
.mobile-filter-content>.el-button{width:100%}
@media(max-width:1200px){.map-workspace{grid-template-columns:260px minmax(0,1fr)}.map-workspace.filter-collapsed{grid-template-columns:minmax(0,1fr)}.map-workspace.filter-collapsed.detail-open{grid-template-columns:minmax(0,1fr) 320px}.map-detail-panel{position:absolute;right:0;top:0;bottom:0;width:320px;box-shadow:-12px 0 30px rgba(31,45,61,.1)}.map-workspace.filter-collapsed .map-detail-panel{grid-column:auto}.map-summary-bar{grid-template-columns:repeat(3,1fr)}.map-summary-distribution{display:none!important}}@media(max-width:760px){.map-workspace{display:block;border-radius:0}.map-side-panel{display:none}.map-canvas-shell{width:100%;height:100%}.mobile-filter-button{display:flex;align-items:center;gap:6px;position:absolute;left:14px;top:14px;z-index:3;padding:10px 14px;border:1px solid var(--border);border-radius:10px;color:var(--brand-600);background:#fff;box-shadow:var(--shadow-soft)}.map-controls{top:62px}.map-legend{bottom:14px}.map-detail-panel{top:auto;left:0;width:100%;max-height:70%;border-radius:18px 18px 0 0}.map-detail-panel>img{height:140px}.map-result-hint{right:12px;top:14px;max-width:54%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.map-state{min-height:210px}.map-detail-panel__body{padding:16px}.map-mobile-park-strip{position:absolute;left:0;right:0;bottom:0;z-index:3;display:flex;gap:8px;padding:10px 12px;overflow-x:auto;background:linear-gradient(180deg,rgba(255,255,255,0) 0%,rgba(255,255,255,.96) 28%);scrollbar-width:none}.map-mobile-park-strip::-webkit-scrollbar{display:none}.map-mobile-park-strip .map-park-card{flex:0 0 148px;height:92px}}
.map-utility-actions{position:absolute;right:16px;top:16px;z-index:3;display:flex;gap:8px}.map-utility-actions .el-button{margin:0;background:rgba(255,255,255,.94)}.map-utility-actions .el-button--primary{color:#fff;background:var(--brand-600)}.map-picking-notice{position:absolute;left:50%;top:72px;z-index:5;transform:translateX(-50%);width:min(410px,calc(100% - 32px));padding:12px 14px;display:flex;align-items:center;justify-content:space-between;gap:14px;border:1px solid var(--brand-200);border-radius:12px;background:rgba(255,255,255,.97);box-shadow:0 14px 36px rgba(37,99,235,.18)}.map-picking-notice>div{display:flex;align-items:center;gap:10px}.map-picking-notice>div>.el-icon{flex:none;color:var(--brand-600);font-size:24px}.map-picking-notice span{display:grid;gap:2px}.map-picking-notice strong{font-size:13px}.map-picking-notice small{color:var(--text-secondary);font-size:11px}.map-detail-panel__actions .el-button{margin:0}.map-detail-panel__delete{grid-column:1/-1}.map-detail-panel__batch{border-radius:4px;color:var(--brand-700);background:var(--brand-50)}.map-result-hint{top:58px;border-radius:6px}
@media(max-width:760px){.map-utility-actions{right:10px;top:10px}.map-utility-actions .el-button:not(.el-button--primary){display:none}.map-picking-notice{top:62px}.map-detail-panel{border-radius:12px 12px 0 0}.map-result-hint{top:58px}}
</style>
