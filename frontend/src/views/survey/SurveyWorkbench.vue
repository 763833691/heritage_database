<template>
  <div class="page-shell survey-workbench">
    <section class="section-card wb-header">
      <div class="wb-header__titles">
        <el-button text @click="$router.push('/survey')"><el-icon><ArrowLeft /></el-icon>返回任务列表</el-button>
        <h1>{{ task?.title || '调研工作台' }}</h1>
        <p class="muted">
          调研日期：{{ task?.survey_date || '未设置' }}
          <template v-if="task?.track"> · 轨迹点 {{ task.track.track_point_count }} · 照片 {{ task.track.photo_count }}</template>
        </p>
      </div>
      <el-steps :active="step" finish-status="success" class="wb-steps">
        <el-step title="材料接入" description="上传 KML / 解析 / 下载 / 语义提取" />
        <el-step title="时间线校对" description="校对标题、标签与可用性" />
        <el-step title="语义分析" description="A–F 编码 / 构成 / 密度 / 点位簇" />
        <el-step title="报告生成" description="生成并导出调研过程章节" />
      </el-steps>
    </section>

    <!-- 步骤一：材料接入 -->
    <section v-show="step === 0" class="section-card">
      <div class="section-card__header">
        <div>
          <h2>材料接入</h2>
          <p>上传两步路导出的 KML 轨迹文件（上限 50MB），系统将自动下载轨迹照片并完成语义化。</p>
        </div>
      </div>

      <el-upload
        v-if="!task?.track"
        drag
        accept=".kml"
        :auto-upload="false"
        :show-file-list="false"
        :on-change="handleKmlSelected"
        :disabled="uploading"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">将 KML 文件拖到此处，或<em>点击选择文件</em></div>
      </el-upload>

      <div v-else class="wb-track">
        <div class="wb-track__bar">
          <div>
            <strong>{{ TRACK_STAGE_LABELS[trackStatus.stage] || trackStatus.stage }}</strong>
            <span class="muted">
              <template v-if="trackStatus.total"> （{{ trackStatus.done }}/{{ trackStatus.total }}）</template>
            </span>
          </div>
          <el-tag :type="trackTagType(trackStatus.status)" size="small">{{ TRACK_STAGE_LABELS[trackStatus.status] || trackStatus.status }}</el-tag>
        </div>
        <el-progress :percentage="progressPercent" :status="progressStatus" :stroke-width="12" />
        <p class="muted wb-track__file">文件：{{ task.track.original_name }}</p>
        <el-alert
          v-if="trackStatus.status === 'failed'"
          type="error"
          :closable="false"
          :title="trackStatus.error_message || task.track.error_message || '处理失败'"
        />

        <div v-if="failedPhotos.length" class="wb-failed">
          <h3>失败项（{{ failedPhotos.length }}）</h3>
          <div v-for="photo in failedPhotos" :key="photo.id" class="wb-failed__item">
            <el-tag type="danger" size="small">{{ photo.file_name || `照片 ${photo.seq + 1}` }}</el-tag>
            <span class="muted">{{ photo.error_message || '下载/描述失败' }}</span>
          </div>
          <el-button type="warning" size="small" :loading="retrying" @click="retryFailed">重新触发处理</el-button>
        </div>

        <div class="wb-actions">
          <el-button :disabled="trackStatus.status !== 'done'" type="primary" @click="goStep(1)">
            进入时间线校对<el-icon><ArrowRight /></el-icon>
          </el-button>
          <el-button @click="refreshAll">刷新状态</el-button>
          <el-button v-if="trackStatus.status === 'done'" @click="redescribeAll">按主题重新生成图注</el-button>
          <el-button v-if="trackStatus.status === 'failed'" type="warning" @click="retryFailed">重试</el-button>
        </div>
      </div>
    </section>

    <!-- 步骤二：时间线校对 -->
    <section v-show="step === 1" class="section-card">
      <div class="section-card__header">
        <div>
          <h2>时间线校对</h2>
          <p>这是全链路唯一强制人工环节：逐条确认标题、主题标签与「可用于报告」，全部确认后才能生成报告。</p>
        </div>
        <div class="wb-review-actions">
          <el-button size="small" :loading="autoTitling" @click="autoTitle">AI 生成标题</el-button>
          <el-button size="small" @click="confirmAll">全部确认</el-button>
        </div>
      </div>

      <StatusState v-if="eventsLoading" type="loading" title="正在加载调研事件" />
      <StatusState v-else-if="!events.length" type="empty" title="暂无调研事件" description="请先在上一步完成 KML 处理。" />
      <template v-else>
        <div class="wb-timeline">
          <span v-for="bucket in timeline" :key="bucket.hour" class="wb-timeline__chip">
            {{ bucket.hour === 'unknown' ? '时间未知' : bucket.hour.slice(11, 16) }}
            <strong>{{ bucket.count }}</strong>
          </span>
        </div>

        <el-table :data="events" row-key="id" class="wb-table">
          <el-table-column label="照片" width="92">
            <template #default="{ row }">
              <el-image
                v-if="row.photo?.thumb_url"
                :src="row.photo.thumb_url"
                :preview-src-list="[row.photo.url]"
                preview-teleported
                fit="cover"
                class="wb-thumb"
              />
              <span v-else class="muted">无图</span>
            </template>
          </el-table-column>
          <el-table-column label="时间" width="150">
            <template #default="{ row }">{{ formatTime(row.timestamp) }}</template>
          </el-table-column>
          <el-table-column label="语义地址" min-width="200">
            <template #default="{ row }">{{ row.address || '—' }}</template>
          </el-table-column>
          <el-table-column label="标题（可编辑）" min-width="200">
            <template #default="{ row }">
              <el-input v-model="row.title" size="small" @change="saveEvent(row)" />
            </template>
          </el-table-column>
          <el-table-column label="主题标签" min-width="200">
            <template #default="{ row }">
              <el-select
                v-model="row.tags"
                multiple
                filterable
                allow-create
                default-first-option
                size="small"
                placeholder="添加标签"
                style="width: 100%"
                @change="saveEvent(row)"
              >
                <el-option v-for="tag in tagOptions" :key="tag" :label="tag" :value="tag" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="可用于报告" width="110" align="center">
            <template #default="{ row }">
              <el-switch v-model="row.usable_for_report" @change="saveEvent(row)" />
            </template>
          </el-table-column>
          <el-table-column label="已确认" width="90" align="center">
            <template #default="{ row }">
              <el-checkbox v-model="confirmed[row.id]" />
            </template>
          </el-table-column>
        </el-table>

        <div class="wb-actions">
          <el-button @click="goStep(0)"><el-icon><ArrowLeft /></el-icon>上一步</el-button>
          <el-button type="primary" @click="goStep(2)">
            进入语义分析<el-icon><ArrowRight /></el-icon>
          </el-button>
          <span v-if="!allConfirmed" class="muted">还有 {{ unconfirmedCount }} 条事件未确认（生成报告前需全部确认）</span>
        </div>
      </template>
    </section>

    <!-- 步骤三：语义分析 -->
    <section v-show="step === 2" class="section-card">
      <div class="section-card__header">
        <div>
          <h2>语义分析</h2>
          <p>按课题组保护展示编码表（A–F）对照片归类，计算类型构成、拍摄密度、点位簇与停留时长，并支持跨公园比较。</p>
        </div>
        <div class="wb-report-actions">
          <el-select
            v-if="trackChoices.length > 1"
            v-model="selectedTrackId"
            size="small"
            style="width: 220px"
            placeholder="选择轨迹"
            @change="onTrackChanged"
          >
            <el-option v-for="item in trackChoices" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
          <el-button type="primary" :loading="analysisLoading" :disabled="!activeTrackId" @click="runAnalysis">
            {{ analysis ? '重新生成语义分析' : '生成语义分析' }}
          </el-button>
          <el-button :disabled="!analysis" @click="exportAnalysisCsv">导出编码 CSV</el-button>
        </div>
      </div>

      <StatusState v-if="analysisLoading" type="loading" title="正在生成语义分析" />
      <el-alert v-else-if="analysisError" type="warning" :closable="false" :title="analysisError" />
      <StatusState
        v-else-if="!analysis"
        type="empty"
        title="尚未生成语义分析"
        description="点击右上角「生成语义分析」，按 A–F 编码表统计照片类型构成、拍摄密度与点位簇。"
      />
      <template v-else>
        <div class="wb-metrics">
          <el-card shadow="never" class="wb-metric">
            <span>照片总数</span><strong>{{ analysis.photo_count }}</strong>
          </el-card>
          <el-card shadow="never" class="wb-metric">
            <span>轨迹里程</span><strong>{{ analysis.distance_km }}<em>km</em></strong>
          </el-card>
          <el-card shadow="never" class="wb-metric">
            <span>拍摄密度</span><strong>{{ analysis.photo_density_per_km ?? '—' }}<em>张/km</em></strong>
          </el-card>
          <el-card shadow="never" class="wb-metric">
            <span>考察时长</span><strong>{{ analysis.duration_minutes ?? '—' }}<em>min</em></strong>
          </el-card>
          <el-card shadow="never" class="wb-metric">
            <span>点位簇</span><strong>{{ analysis.clusters.length }}</strong>
          </el-card>
        </div>

        <div class="wb-chart-grid">
          <div class="chart-card">
            <div class="section-card__header"><div><h2>图 1 语义类型构成</h2><p>每张照片归唯一类型，D＞E＞A＞C＞B＞F 优先级。</p></div></div>
            <div ref="compositionRef" class="chart-canvas"></div>
          </div>
          <div class="chart-card">
            <div class="section-card__header"><div><h2>图 2 动线时空分布</h2><p>横轴为考察进行分钟，纵轴为纬度，颜色为语义类型。</p></div></div>
            <div ref="spacetimeRef" class="chart-canvas"></div>
            <p v-if="skippedTimeCount" class="muted wb-chart-note">有 {{ skippedTimeCount }} 张照片缺少拍摄时间，未绘制在图中。</p>
          </div>
        </div>

        <h3 class="wb-subtitle">点位簇（相邻照片时间差 &gt; 5 分钟或间距 &gt; 150 m 切分）</h3>
        <el-table :data="analysis.clusters" size="small" border class="wb-table">
          <el-table-column prop="cluster" label="簇号" width="80" />
          <el-table-column prop="count" label="照片数" width="90" />
          <el-table-column label="首末时间" min-width="230">
            <template #default="{ row }">{{ formatClusterTime(row.time_start) }} ~ {{ formatClusterTime(row.time_end) }}</template>
          </el-table-column>
          <el-table-column label="停留(分钟)" width="110">
            <template #default="{ row }">{{ row.stay_minutes }}</template>
          </el-table-column>
          <el-table-column label="构成" min-width="160">
            <template #default="{ row }">{{ compositionText(row.composition) || '—' }}</template>
          </el-table-column>
        </el-table>

        <div class="wb-compare">
          <div class="section-card__header">
            <div>
              <h2>跨公园轨迹比较</h2>
              <p>多选轨迹（建议按公园名命名 KML），生成 100% 堆叠构成图与指标对照表。</p>
            </div>
            <div class="wb-report-actions">
              <el-select
                v-model="compareIds"
                multiple
                filterable
                collapse-tags
                :multiple-limit="8"
                size="small"
                style="width: 320px"
                placeholder="选择 2 条以上轨迹"
              >
                <el-option v-for="item in comparableTracks" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
              <el-button size="small" :loading="compareLoading" :disabled="compareIds.length < 2" @click="runCompare">开始比较</el-button>
            </div>
          </div>
          <div v-show="compareResult" ref="compareRef" class="chart-canvas"></div>
          <el-table v-if="compareResult" :data="compareResult.items" size="small" border class="wb-table">
            <el-table-column prop="name" label="轨迹 / 公园" min-width="180" />
            <el-table-column prop="photo_count" label="照片数" width="90" />
            <el-table-column label="里程(km)" width="100">
              <template #default="{ row }">{{ row.distance_km }}</template>
            </el-table-column>
            <el-table-column label="密度(张/km)" width="120">
              <template #default="{ row }">{{ row.photo_density_per_km ?? '—' }}</template>
            </el-table-column>
            <el-table-column prop="cluster_count" label="簇数" width="80" />
          </el-table>
        </div>
      </template>

      <div class="wb-actions">
        <el-button @click="goStep(1)"><el-icon><ArrowLeft /></el-icon>返回校对</el-button>
        <el-button type="primary" :disabled="!allConfirmed" @click="goStep(3)">
          进入报告生成<el-icon><ArrowRight /></el-icon>
        </el-button>
        <span v-if="!allConfirmed" class="muted">还有 {{ unconfirmedCount }} 条事件未确认</span>
      </div>
    </section>

    <!-- 步骤四：报告生成 -->
    <section v-show="step === 3" class="section-card">
      <div class="section-card__header">
        <div>
          <h2>报告生成</h2>
          <p>生成报告「二、调研过程」章节：调研时间、调研方式、实地踏勘、踏勘照片与材料溯源表。</p>
        </div>
        <div class="wb-report-actions">
          <el-button type="primary" :loading="report?.status === 'generating'" @click="generateReport">
            {{ report?.status === 'done' ? '重新生成' : '生成调研过程章节' }}
          </el-button>
          <el-button :disabled="report?.status !== 'done'" @click="exportDocx">导出 docx</el-button>
        </div>
      </div>

      <el-alert v-if="report?.status === 'generating'" type="info" :closable="false" title="正在生成章节，请稍候…" />
      <el-alert v-else-if="report?.status === 'failed'" type="error" :closable="false" :title="report.error_message || '生成失败'" />

      <div v-if="report?.content" class="wb-report">
        <h2 class="wb-report__title">{{ report.content.title }}</h2>
        <div v-for="section in report.content.sections" :key="section.heading" class="wb-report__section">
          <h3>{{ section.heading }}</h3>
          <template v-for="(block, index) in section.blocks" :key="index">
            <p v-if="block.type === 'text'" class="wb-report__text" v-html="renderText(block.text)" />
            <figure v-else class="wb-report__figure">
              <img :src="photoUrl(block.photo_id)" :alt="block.no" />
              <figcaption>{{ figureCaption(block.photo_id) }}</figcaption>
            </figure>
          </template>
        </div>

        <h3 class="wb-report__source-title">材料溯源表</h3>
        <el-table :data="report.citations" size="small" border>
          <el-table-column prop="section" label="章节" width="150" />
          <el-table-column label="引用事件" min-width="200">
            <template #default="{ row }">EV:{{ row.event_id }} {{ row.title }}</template>
          </el-table-column>
          <el-table-column prop="role" label="引用方式" width="100" />
          <el-table-column prop="time" label="时间" width="150" />
          <el-table-column prop="address" label="地点" min-width="200" />
        </el-table>
      </div>

      <div class="wb-actions">
        <el-button @click="goStep(2)"><el-icon><ArrowLeft /></el-icon>返回语义分析</el-button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as echarts from 'echarts'
import StatusState from '@/components/common/StatusState.vue'
import {
  TRACK_STAGE_LABELS,
  analyzeTrack,
  autoTitleSurveyEvents,
  compareTracks,
  downloadReportDocx,
  downloadTrackAnalysisCsv,
  generateChapter2,
  getSurveyReport,
  getSurveyTask,
  getSurveyTimeline,
  getTrackAnalysis,
  getTrackDetail,
  getTrackList,
  getTrackStatus,
  listSurveyEvents,
  retryTrack,
  saveBlob,
  updateSurveyEvent,
  uploadTrackKml,
} from '@/utils/surveyApi'

const route = useRoute()
const taskId = Number(route.params.id)

const task = ref(null)
const step = ref(0)
const uploading = ref(false)
const retrying = ref(false)
const autoTitling = ref(false)
const trackStatus = reactive({ status: 'pending', stage: 'pending', done: 0, total: 0, failed_count: 0, error_message: '', track_point_count: 0, photo_count: 0 })
const photos = ref([])
const events = ref([])
const eventsLoading = ref(false)
const timeline = ref([])
const confirmed = reactive({})
const report = ref(null)
const tagOptions = ref(['刘贺主墓', '保护展示', '参观步道', '标识牌', '环境风貌', '遗址本体'])

// ===== 语义分析 =====
const TYPE_COLORS = { A: '#085399', B: '#4a7fb5', C: '#7fa8cc', D: '#c9a227', E: '#b5543a', F: '#6b8f71', G: '#999999' }
const analysis = ref(null)
const analysisLoading = ref(false)
const analysisError = ref('')
const allTracks = ref([])
const selectedTrackId = ref(null)
const compositionRef = ref()
const spacetimeRef = ref()
const compareRef = ref()
const compareIds = ref([])
const compareLoading = ref(false)
const compareResult = ref(null)
let compositionChart = null
let spacetimeChart = null
let compareChart = null

const trackChoices = computed(() => {
  const scoped = allTracks.value.filter((item) => item.survey_task_id === taskId && item.photo_count > 0)
  const list = scoped.length ? scoped : allTracks.value.filter((item) => item.photo_count > 0)
  return list.map((item) => ({ id: item.id, name: item.original_name?.replace(/\.kml$/i, '') || `轨迹 ${item.id}` }))
})
const comparableTracks = computed(() =>
  allTracks.value
    .filter((item) => item.photo_count > 0)
    .map((item) => ({ id: item.id, name: item.original_name?.replace(/\.kml$/i, '') || `轨迹 ${item.id}` }))
)
const activeTrackId = computed(() => selectedTrackId.value || task.value?.track_id || null)
const skippedTimeCount = computed(() =>
  analysis.value ? analysis.value.spacetime.filter((point) => point.t_min == null).length : 0
)

let trackTimer = null
let reportTimer = null

const failedPhotos = computed(() =>
  photos.value.filter((photo) => photo.download_status === 'failed' || photo.describe_status === 'failed')
)
const progressPercent = computed(() => {
  if (trackStatus.status === 'done') return 100
  if (trackStatus.total > 0) return Math.min(99, Math.round((trackStatus.done / trackStatus.total) * 100))
  return trackStatus.stage === 'parsing' ? 8 : 2
})
const progressStatus = computed(() => {
  if (trackStatus.status === 'done') return 'success'
  if (trackStatus.status === 'failed') return 'exception'
  return undefined
})
const allConfirmed = computed(() => events.value.length > 0 && events.value.every((event) => confirmed[event.id]))
const unconfirmedCount = computed(() => events.value.filter((event) => !confirmed[event.id]).length)

onMounted(async () => {
  window.addEventListener('resize', resizeCharts)
  await loadAll()
})
onBeforeUnmount(() => {
  stopTrackPolling()
  stopReportPolling()
  window.removeEventListener('resize', resizeCharts)
  disposeCharts()
})

async function loadAll() {
  try {
    task.value = await getSurveyTask(taskId)
  } catch {
    ElMessage.error('调研任务加载失败')
    return
  }
  if (task.value.track_id) {
    await refreshTrack({ silent: true })
    if (trackStatus.status === 'done') step.value = 1
    else startTrackPolling()
  }
  await loadEvents()
  await loadReport()
  await loadTracks()
  await loadAnalysis()
}

async function loadEvents() {
  eventsLoading.value = true
  try {
    const data = await listSurveyEvents(taskId)
    events.value = (data.items || []).map((item) => ({ ...item, tags: item.tags || [] }))
    events.value.forEach((item) => {
      if (confirmed[item.id] === undefined) confirmed[item.id] = false
      ;(item.tags || []).forEach((tag) => {
        if (!tagOptions.value.includes(tag)) tagOptions.value.push(tag)
      })
    })
    const tl = await getSurveyTimeline(taskId)
    timeline.value = tl.items || []
  } catch {
    events.value = []
  } finally {
    eventsLoading.value = false
  }
}

async function refreshTrack({ silent = false } = {}) {
  if (!task.value?.track_id) return
  try {
    const status = await getTrackStatus(task.value.track_id)
    Object.assign(trackStatus, status)
    if (!silent) {
      task.value = await getSurveyTask(taskId)
      if (!['pending', 'parsing', 'downloading', 'geocoding', 'describing'].includes(trackStatus.status)) {
        photos.value = (await getTrackDetail(task.value.track_id)).photos || []
      }
    }
    if (!['pending', 'parsing', 'downloading', 'geocoding', 'describing'].includes(trackStatus.status)) {
      stopTrackPolling()
      if (trackStatus.status === 'done' && step.value === 0) {
        await loadEvents()
        ElMessage.success('轨迹处理完成，可进入时间线校对')
      }
    }
  } catch {
    stopTrackPolling()
  }
}

async function refreshAll() {
  await refreshTrack()
  if (task.value?.track_id) photos.value = (await getTrackDetail(task.value.track_id)).photos || []
}

function startTrackPolling() {
  stopTrackPolling()
  trackTimer = setInterval(() => refreshTrack(), 1500)
}

function stopTrackPolling() {
  if (trackTimer) clearInterval(trackTimer)
  trackTimer = null
}

async function handleKmlSelected(uploadFile) {
  const file = uploadFile?.raw
  if (!file) return
  if (!file.name.toLowerCase().endsWith('.kml')) {
    ElMessage.warning('请选择 .kml 文件')
    return
  }
  uploading.value = true
  try {
    const data = await uploadTrackKml(file, taskId)
    task.value = await getSurveyTask(taskId)
    Object.assign(trackStatus, { status: data.status || 'pending', stage: 'pending', done: 0, total: 0, failed_count: 0 })
    ElMessage.success('KML 已上传，开始处理')
    startTrackPolling()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '上传失败')
  } finally {
    uploading.value = false
  }
}

async function retryFailed() {
  if (!task.value?.track_id) return
  retrying.value = true
  try {
    await retryTrack(task.value.track_id)
    Object.assign(trackStatus, { status: 'pending', stage: 'pending', done: 0, total: 0 })
    ElMessage.success('已重新触发处理')
    startTrackPolling()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '重试失败')
  } finally {
    retrying.value = false
  }
}

async function redescribeAll() {
  if (!task.value?.track_id) return
  try {
    await ElMessageBox.confirm(
      '将重置全部照片的语义描述，并按「调研主题」重新调用视觉模型生成图注与标签（耗时较长且会产生模型费用）。是否继续？',
      '重新生成图注',
      { type: 'warning', confirmButtonText: '开始', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  retrying.value = true
  try {
    await retryTrack(task.value.track_id, true)
    Object.assign(trackStatus, { status: 'pending', stage: 'pending', done: 0, total: 0 })
    ElMessage.success('已重新触发语义生成')
    startTrackPolling()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '重新生成失败')
  } finally {
    retrying.value = false
  }
}

async function autoTitle() {
  if (!eventsLoading.value && !events.value.length) return
  let overwrite
  try {
    await ElMessageBox.confirm(
      '将结合调研主题，用大语言模型为全部照片事件重新生成标题。是否同时覆盖已在时间线校对中人工修改过的标题？',
      'AI 生成标题',
      { type: 'warning', confirmButtonText: '覆盖人工标题', cancelButtonText: '保留人工标题', distinguishCancelAndClose: true },
    )
    overwrite = true
  } catch (action) {
    overwrite = action === 'cancel' ? false : null
  }
  if (overwrite === null) return

  autoTitling.value = true
  try {
    const data = await autoTitleSurveyEvents(taskId, overwrite)
    events.value = data.items || []
    const skipped = data.skipped ? `，跳过 ${data.skipped} 条` : ''
    ElMessage.success(`已生成 ${data.updated} 条标题${skipped}`)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '标题生成失败')
  } finally {
    autoTitling.value = false
  }
}

async function saveEvent(row) {
  try {
    const updated = await updateSurveyEvent(row.id, {
      title: row.title,
      tags: row.tags,
      usable_for_report: row.usable_for_report,
    })
    Object.assign(row, updated)
    ;(updated.tags || []).forEach((tag) => {
      if (!tagOptions.value.includes(tag)) tagOptions.value.push(tag)
    })
  } catch {
    ElMessage.error('保存失败')
  }
}

function confirmAll() {
  events.value.forEach((event) => {
    confirmed[event.id] = true
  })
}

function goStep(target) {
  if (target === 3 && !allConfirmed.value) {
    ElMessage.warning('请先确认全部调研事件')
    return
  }
  step.value = target
  if (target === 2) nextTick(renderAnalysisCharts)
}

async function loadReport() {
  try {
    report.value = await getSurveyReport(taskId)
  } catch {
    report.value = { status: 'empty', content: null, citations: [] }
  }
  if (report.value.status === 'generating') startReportPolling()
}

function startReportPolling() {
  stopReportPolling()
  reportTimer = setInterval(async () => {
    try {
      report.value = await getSurveyReport(taskId)
    } catch {
      stopReportPolling()
      return
    }
    if (report.value.status !== 'generating') {
      stopReportPolling()
      if (report.value.status === 'done') ElMessage.success('章节生成完成')
    }
  }, 2000)
}

function stopReportPolling() {
  if (reportTimer) clearInterval(reportTimer)
  reportTimer = null
}

async function generateReport() {
  try {
    report.value = await generateChapter2(taskId)
    ElMessage.info('已开始生成章节')
    startReportPolling()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '生成失败')
  }
}

async function exportDocx() {
  try {
    const blob = await downloadReportDocx(taskId)
    saveBlob(blob, `调研报告_第二章_${taskId}.docx`)
  } catch {
    ElMessage.error('导出失败，请先生成章节')
  }
}

async function loadTracks() {
  try {
    const data = await getTrackList()
    allTracks.value = data.items || []
  } catch {
    allTracks.value = []
  }
  if (!selectedTrackId.value && trackChoices.value.length) {
    selectedTrackId.value = trackChoices.value.some((item) => item.id === task.value?.track_id)
      ? task.value.track_id
      : trackChoices.value[0].id
  }
}

async function loadAnalysis() {
  const trackId = activeTrackId.value
  if (!trackId) return
  try {
    const data = await getTrackAnalysis(trackId)
    analysis.value = data
    analysisError.value = ''
    await nextTick()
    if (step.value === 2) renderAnalysisCharts()
  } catch {
    analysis.value = null
  }
}

function onTrackChanged() {
  analysis.value = null
  analysisError.value = ''
  loadAnalysis()
}

async function runAnalysis() {
  const trackId = activeTrackId.value
  if (!trackId) return
  analysisLoading.value = true
  analysisError.value = ''
  try {
    analysis.value = await analyzeTrack(trackId)
    await nextTick()
    renderAnalysisCharts()
    ElMessage.success('语义分析已生成')
  } catch (error) {
    analysis.value = null
    analysisError.value = error.response?.data?.detail || '该轨迹暂无照片，无法分析'
    ElMessage.warning(analysisError.value)
  } finally {
    analysisLoading.value = false
  }
}

async function exportAnalysisCsv() {
  const trackId = activeTrackId.value
  if (!trackId) return
  try {
    const blob = await downloadTrackAnalysisCsv(trackId)
    const name = (task.value?.track?.original_name || `track_${trackId}`).replace(/\.kml$/i, '')
    saveBlob(blob, `${name}_语义编码.csv`)
  } catch {
    ElMessage.error('导出失败，请先生成语义分析')
  }
}

function disposeCharts() {
  ;[compositionChart, spacetimeChart, compareChart].forEach((chart) => chart?.dispose())
  compositionChart = null
  spacetimeChart = null
  compareChart = null
}

function resizeCharts() {
  compositionChart?.resize()
  spacetimeChart?.resize()
  compareChart?.resize()
}

function renderAnalysisCharts() {
  renderCompositionChart()
  renderSpacetimeChart()
}

function renderCompositionChart() {
  if (!compositionRef.value || !analysis.value) return
  compositionChart?.dispose()
  compositionChart = echarts.init(compositionRef.value)
  const rows = [...analysis.value.composition].reverse()
  compositionChart.setOption({
    backgroundColor: '#ffffff',
    grid: { top: 16, right: 96, bottom: 28, left: 120 },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    xAxis: { type: 'value', name: '照片数', splitLine: { lineStyle: { color: '#eef1f5' } } },
    yAxis: {
      type: 'category',
      data: rows.map((item) => `${item.code} ${item.name}`),
      axisLine: { lineStyle: { color: '#cbd5e1' } },
      axisTick: { show: false },
    },
    series: [
      {
        type: 'bar',
        barMaxWidth: 22,
        itemStyle: { color: '#085399' },
        data: rows.map((item) => item.count),
        label: {
          show: true,
          position: 'right',
          color: '#085399',
          formatter: (_params) => `${rows[_params.dataIndex].count}（${rows[_params.dataIndex].percent}%）`,
        },
      },
    ],
  })
}

function renderSpacetimeChart() {
  if (!spacetimeRef.value || !analysis.value) return
  spacetimeChart?.dispose()
  spacetimeChart = echarts.init(spacetimeRef.value)
  const points = analysis.value.spacetime.filter((point) => point.t_min != null && point.lat != null)
  const codes = ['A', 'B', 'C', 'D', 'E', 'F', 'G']
  const nameMap = {}
  ;(analysis.value.composition || []).forEach((item) => { nameMap[item.code] = item.name })
  const series = codes
    .map((code) => ({
      name: nameMap[code] ? `${code} ${nameMap[code]}` : code,
      type: 'scatter',
      symbolSize: 10,
      itemStyle: { color: TYPE_COLORS[code] },
      data: points
        .filter((point) => point.type === code)
        .map((point) => ({
          value: [point.t_min, point.lat],
          caption: point.caption,
          thumb_url: point.thumb_url,
          type_name: point.type_name,
          t_min: point.t_min,
        })),
    }))
    .filter((item) => item.data.length)
  spacetimeChart.setOption({
    backgroundColor: '#ffffff',
    color: codes.map((code) => TYPE_COLORS[code]),
    grid: { top: 44, right: 24, bottom: 40, left: 60 },
    legend: { top: 6 },
    tooltip: {
      trigger: 'item',
      formatter: (params) => {
        const data = params.data
        return `<div style="max-width:200px">
          <img src="${data.thumb_url}" style="width:100%;border-radius:4px;margin-bottom:4px" />
          <div>${escapeHtml(data.caption || '')}</div>
          <div style="color:#888">${escapeHtml(data.type_name || '')} · ${data.t_min} min</div>
        </div>`
      },
    },
    xAxis: { type: 'value', name: '考察进行(min)', splitLine: { lineStyle: { color: '#eef1f5' } } },
    yAxis: { type: 'value', name: '纬度', scale: true, splitLine: { lineStyle: { color: '#eef1f5' } } },
    series,
  })
}

async function runCompare() {
  if (compareIds.value.length < 2) return
  compareLoading.value = true
  try {
    compareResult.value = await compareTracks(compareIds.value)
    await nextTick()
    renderCompareChart()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '跨轨迹比较失败')
  } finally {
    compareLoading.value = false
  }
}

function renderCompareChart() {
  if (!compareRef.value || !compareResult.value) return
  compareChart?.dispose()
  compareChart = echarts.init(compareRef.value)
  const items = compareResult.value.items
  const codes = ['A', 'B', 'C', 'D', 'E', 'F', 'G']
  compareChart.setOption({
    backgroundColor: '#ffffff',
    color: codes.map((code) => TYPE_COLORS[code]),
    grid: { top: 44, right: 24, bottom: 40, left: 48 },
    legend: { top: 6 },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    xAxis: { type: 'category', data: items.map((item) => item.name), axisLabel: { interval: 0, rotate: items.length > 3 ? 20 : 0 } },
    yAxis: { type: 'value', max: 100, name: '构成比(%)', splitLine: { lineStyle: { color: '#eef1f5' } } },
    series: codes.map((code) => ({
      name: code,
      type: 'bar',
      stack: 'total',
      barMaxWidth: 48,
      data: items.map((item) => {
        const row = (item.composition || []).find((entry) => entry.code === code)
        return row ? row.percent : 0
      }),
    })),
  })
}

function compositionText(composition) {
  if (!composition) return ''
  return ['A', 'B', 'C', 'D', 'E', 'F', 'G']
    .filter((code) => composition[code])
    .map((code) => `${code}${composition[code]}`)
    .join('·')
}

function formatClusterTime(value) {
  if (!value) return '—'
  return value.replace('T', ' ').slice(0, 16)
}

function trackTagType(status) {
  if (status === 'done') return 'success'
  if (status === 'failed') return 'danger'
  return 'warning'
}

function formatTime(value) {
  if (!value) return '时间未知'
  return value.replace('T', ' ').slice(0, 16)
}

function photoUrl(photoId) {
  const trackId = task.value?.track_id
  return `/api/track/${trackId}/photos/${photoId}?thumb=true`
}

function figureCaption(photoId) {
  const figure = (report.value?.content?.figures || []).find((item) => item.photo_id === photoId)
  if (!figure) return ''
  return `${figure.no}：${figure.caption}（拍摄时间：${figure.shot_time || '未知'}，${figure.address || '位置未知'}）（来源：本次调研拍摄）`
}

function escapeHtml(text) {
  return String(text || '').replace(/[&<>"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[char]))
}

function renderText(text) {
  return escapeHtml(text).replace(/\[EV:(\d+)\]/g, '<sup class="ev-ref">[$1]</sup>')
}
</script>

<style scoped>
.wb-header {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.wb-review-actions {
  display: flex;
  align-items: center;
}

.wb-header__titles h1 {
  margin: 6px 0 4px;
  font-size: 22px;
  color: var(--text-primary);
}
.wb-steps {
  max-width: 900px;
}
.wb-track {
  display: grid;
  gap: 12px;
  margin-top: 8px;
}
.wb-track__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.wb-track__file {
  font-size: 13px;
}
.wb-failed {
  display: grid;
  gap: 8px;
  padding: 12px;
  border: 1px solid #fecaca;
  border-radius: 12px;
  background: #fef2f2;
}
.wb-failed__item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  flex-wrap: wrap;
}
.wb-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 16px;
  flex-wrap: wrap;
}
.wb-timeline {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.wb-timeline__chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--brand-50);
  color: var(--brand-700);
  font-size: 12px;
}
.wb-thumb {
  width: 64px;
  height: 48px;
  border-radius: 6px;
}
.wb-report {
  display: grid;
  gap: 14px;
  margin-top: 16px;
}
.wb-report__title {
  text-align: center;
  margin: 0;
  font-size: 20px;
}
.wb-report__section h3 {
  margin: 8px 0;
  font-size: 16px;
  color: var(--brand-700);
}
.wb-report__text {
  line-height: 1.9;
  text-indent: 2em;
  margin: 6px 0;
  color: var(--text-primary);
}
.wb-report__figure {
  margin: 12px auto;
  text-align: center;
}
.wb-report__figure img {
  width: min(100%, 560px);
  border-radius: 10px;
  border: 1px solid var(--border);
}
.wb-report__figure figcaption {
  margin-top: 6px;
  font-size: 13px;
  color: var(--text-secondary);
}
.wb-report__source-title {
  margin: 16px 0 8px;
  font-size: 16px;
}
.wb-report :deep(.ev-ref) {
  color: var(--brand-600);
}
.wb-chart-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-top: 8px;
}
.wb-chart-grid .chart-card {
  padding: 18px;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: #ffffff;
}
.wb-chart-grid .chart-canvas {
  height: 340px;
  background: #ffffff;
}
.wb-chart-note {
  margin: 6px 0 0;
  font-size: 12px;
}
.wb-metrics {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
  margin: 12px 0 18px;
}
.wb-metric {
  background: #ffffff;
}
.wb-metric :deep(.el-card__body) {
  display: grid;
  gap: 6px;
  padding: 14px 16px;
}
.wb-metric span {
  color: var(--text-secondary);
  font-size: 12px;
}
.wb-metric strong {
  color: #085399;
  font-size: 22px;
  font-weight: 600;
}
.wb-metric strong em {
  margin-left: 4px;
  font-size: 12px;
  font-style: normal;
  color: var(--text-tertiary);
}
.wb-subtitle {
  margin: 18px 0 10px;
  font-size: 15px;
  color: var(--brand-700);
}
.wb-compare {
  margin-top: 26px;
  padding-top: 18px;
  border-top: 1px solid var(--border);
}
.wb-compare .chart-canvas {
  height: 340px;
  margin-bottom: 14px;
  background: #ffffff;
}
.wb-report-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
@media (max-width: 1080px) {
  .wb-chart-grid {
    grid-template-columns: 1fr;
  }
  .wb-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
