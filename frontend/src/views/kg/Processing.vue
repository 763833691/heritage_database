<template>
  <div class="page-shell processing-page">
    <header class="processing-header">
      <div>
        <h1>处理流程</h1>
        <p class="muted">选择文献后依次完成文本解析、图谱构建与结果导出。</p>
      </div>
      <div class="toolbar-row">
        <AudioTranscribeDialog @saved="handleTranscribeSaved" />
        <el-button :disabled="!selectedFile" @click="handleRefresh">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </header>

    <StatusState v-if="loading" type="loading" title="正在加载文献列表" />
    <StatusState
      v-else-if="loadError"
      type="error"
      title="处理流程加载失败"
      :description="loadError"
      action-label="重新加载"
      @action="bootstrap"
    />

    <div v-else class="processing-layout">
      <!-- 左侧：步骤与当前文献 -->
      <aside class="processing-side">
        <div class="processing-side__steps">
          <template v-for="(step, index) in WORKFLOW_STEPS" :key="step.id">
            <button
              type="button"
              class="step-card"
              :class="{ 'step-card--active': activeStep === step.id }"
              @click="activeStep = step.id"
            >
              <span class="step-card__index" :class="`step-card__index--${stepVisual(step.id)}`">{{ index + 1 }}</span>
              <span class="step-card__body">
                <span class="step-card__head">
                  <span class="step-card__label">{{ step.label }}</span>
                  <span class="step-card__state" :class="`step-card__state--${stepVisual(step.id)}`">
                    {{ stepProgressLabel(stepVisual(step.id), progress, step.id) }}
                  </span>
                </span>
                <span class="step-card__hint">{{ step.hint }}</span>
              </span>
            </button>
            <span v-if="index < WORKFLOW_STEPS.length - 1" class="step-connector" />
          </template>
        </div>

        <div v-if="selectedFile" class="processing-side__current">
          <div class="processing-side__label">当前文献</div>
          <div class="processing-side__name">{{ selectedFile.name }}</div>
          <StatusBadge :status="status" :process-status="activeProcessStatus" />
          <el-select :model-value="selectedFile.id" class="processing-side__select" @change="handleSelectFile">
            <el-option v-for="file in files" :key="file.id" :label="file.name" :value="file.id">
              <span class="option-row">{{ file.name }}</span>
            </el-option>
          </el-select>

          <template v-if="activeStep === 'text_parse'">
            <el-button
              v-if="textParseReady && !textParseConfirmed"
              type="success"
              class="processing-side__action"
              :disabled="isProcessing"
              @click="confirmSelectedTextParse"
            >
              <el-icon><CircleCheck /></el-icon>
              确认并进入图谱构建
            </el-button>
            <el-button
              v-else
              type="primary"
              class="processing-side__action"
              :disabled="status === 'processing' && !isStaleProcessing"
              @click="runSelected"
            >
              <el-icon :class="{ 'is-spin': status === 'processing' && !isStaleProcessing }">
                <component :is="status === 'processing' && !isStaleProcessing ? 'Loading' : 'VideoPlay'" />
              </el-icon>
              {{ startButtonLabel }}
            </el-button>

            <el-button class="processing-side__action" :disabled="!selectedFile" @click="rerunSelected">
              <el-icon><RefreshLeft /></el-icon>
              重新运行
            </el-button>

            <p v-if="actionHint" class="processing-side__hint">{{ actionHint }}</p>
          </template>
        </div>

        <div v-else class="processing-side__empty">
          {{ files.length === 0 ? '请先在文件库上传文献' : '请选择文献' }}
        </div>
      </aside>

      <!-- 右侧：当前步骤内容 -->
      <main class="processing-main">
        <template v-if="activeStep === 'text_parse'">
          <TextParseBooksPanel :selected-file-id="selectedFile?.id || ''" @open-detail="handleSelectFile" />
          <TextParsingWorkflow
            v-if="selectedFile"
            :key="selectedFile.id"
            :file-id="selectedFile.id"
            :processing="isProcessing"
            :text-parse-confirmed="textParseConfirmed"
            :text-parse-ready="textParseReady"
            @refresh="handleRefresh"
            @confirmed="activeStep = 'graph_build'"
          />
        </template>

        <template v-else-if="activeStep === 'graph_build'">
          <GraphConstructionPanel
            v-if="selectedFile"
            :file-id="selectedFile.id"
            :process-status="activeProcessStatus"
            :process-result="activeProcessResult"
            :processing="isProcessing"
            @refresh="handleRefresh"
          />
          <StatusState v-else type="empty" title="请先选择文献" description="请先在「文本解析」步骤选择文献并完成确认。" />

          <div class="stat-grid">
            <StatCard
              v-for="card in statCards"
              :key="card.label"
              :label="card.label"
              :value="card.value"
              :delta="card.delta"
              :tone="card.tone"
              :icon="card.icon"
            />
          </div>

          <div class="result-grid">
            <section class="result-card">
              <el-tabs v-model="resultTab">
                <el-tab-pane :label="`实体（${entities.length}）`" name="entities">
                  <el-table :data="entityRows" size="small">
                    <el-table-column prop="name" label="实体名称" min-width="140" />
                    <el-table-column label="类型" width="90">
                      <template #default="{ row }">{{ ENTITY_TYPE_LABELS[row.type] || row.type }}</template>
                    </el-table-column>
                    <el-table-column label="出现次数" width="100">
                      <template #default="{ row }">{{ row.mention_count ?? 0 }}</template>
                    </el-table-column>
                    <el-table-column label="置信度" width="100">
                      <template #default="{ row }">{{ (row.confidence ?? 0).toFixed(2) }}</template>
                    </el-table-column>
                  </el-table>
                </el-tab-pane>
                <el-tab-pane :label="`关系（${relations.length}）`" name="relations">
                  <el-table :data="relationRows" size="small">
                    <el-table-column prop="source" label="源实体" min-width="130" />
                    <el-table-column prop="relation" label="关系" min-width="110" />
                    <el-table-column prop="target" label="目标实体" min-width="130" />
                    <el-table-column label="权重" width="90">
                      <template #default="{ row }">{{ (row.weight ?? 0).toFixed(2) }}</template>
                    </el-table-column>
                  </el-table>
                </el-tab-pane>
              </el-tabs>
              <el-empty v-if="!entities.length && !relations.length" description="暂无识别结果，请先完成图谱构建" />
            </section>

            <section class="result-card">
              <h2 class="result-card__title">处理日志</h2>
              <div class="log-list">
                <div v-for="(log, index) in processLogs.slice(-6)" :key="index" class="log-item">
                  <span class="log-item__dot" />
                  <span>{{ log }}</span>
                </div>
                <div v-if="!processLogs.length" class="muted">暂无日志</div>
              </div>
            </section>
          </div>
        </template>

        <template v-else-if="activeStep === 'export'">
          <ExportResultPanel
            v-if="selectedFile"
            :file-id="selectedFile.id"
            :file-name="selectedFile.name"
            :process-status="activeProcessStatus"
            :process-result="activeProcessResult"
            :processing="isProcessing"
            @refresh="handleRefresh"
          />
          <StatusState v-else type="empty" title="请先选择文献" description="请先在「文本解析」步骤选择文献。" />
        </template>
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { confirmKgTextParse, recoverKgInterrupted, rerunKgProcess } from '@/utils/kgApi'
import { useKgStore } from '@/stores/kg'
import StatusState from '@/components/common/StatusState.vue'
import AudioTranscribeDialog from '@/features/kg/components/AudioTranscribeDialog.vue'
import ExportResultPanel from '@/features/kg/components/ExportResultPanel.vue'
import GraphConstructionPanel from '@/features/kg/components/GraphConstructionPanel.vue'
import StatCard from '@/features/kg/components/StatCard.vue'
import StatusBadge from '@/features/kg/components/StatusBadge.vue'
import TextParseBooksPanel from '@/features/kg/components/TextParseBooksPanel.vue'
import TextParsingWorkflow from '@/features/kg/components/TextParsingWorkflow.vue'
import {
  ENTITY_TYPE_LABELS,
  WORKFLOW_STEPS,
  getStepVisualState,
  isTextParseReady,
  resolveWorkflowPhase,
  stepProgressLabel,
} from '@/features/kg/constants'

const route = useRoute()
const router = useRouter()
const store = useKgStore()

const loading = ref(true)
const loadError = ref('')
const selectedFile = ref(null)
const activeStep = ref('text_parse')
const resultTab = ref('entities')
const actionHint = ref('')

let pollTimer = null

const files = computed(() => store.files)
const currentFile = computed(() => store.currentFile)
const activeProcessStatus = computed(() => selectedFile.value?.process_status ?? store.processStatus ?? null)
const activeProcessResult = computed(
  () => store.processResult ?? selectedFile.value?.process_result ?? null,
)
const progress = computed(() => activeProcessStatus.value?.progress ?? 0)
const status = computed(() => selectedFile.value?.status ?? activeProcessStatus.value?.status ?? 'uploaded')

const workflowPhase = computed(() =>
  resolveWorkflowPhase({
    workflow_phase: activeProcessStatus.value?.workflow_phase,
    text_parse_confirmed: activeProcessStatus.value?.text_parse_confirmed,
    export_ready: activeProcessStatus.value?.export_ready,
    progress: progress.value,
    status: status.value,
  }),
)

const textParseConfirmed = computed(() => Boolean(activeProcessStatus.value?.text_parse_confirmed))
const textParseReady = computed(
  () => isTextParseReady(activeProcessStatus.value) || workflowPhase.value !== 'text_parse' || textParseConfirmed.value,
)
const isProcessing = computed(() => status.value === 'processing')

const processLogs = computed(() => store.processStatus?.logs ?? activeProcessStatus.value?.logs ?? [])
const isStaleProcessing = computed(
  () =>
    status.value === 'processing' &&
    processLogs.value.some((log) => log.includes('处理已中断') || log.includes('服务重启') || log.includes('任务已中断')),
)

const entities = computed(() => activeProcessResult.value?.entities ?? [])
const relations = computed(() => activeProcessResult.value?.relations ?? [])

const entityRows = computed(() =>
  [...entities.value].sort((a, b) => (b.confidence ?? 0) - (a.confidence ?? 0)).slice(0, 12),
)
const relationRows = computed(() => relations.value.slice(0, 12))

const typeStats = computed(() => {
  const counts = { place: 0, person: 0, event: 0, concept: 0 }
  entities.value.forEach((entity) => {
    counts[entity.type] = (counts[entity.type] ?? 0) + 1
  })
  return counts
})

const statCards = computed(() => [
  { label: '实体总数', value: entities.value.length, delta: `+${Math.max(0, entities.value.length - 1)}`, tone: 'blue', icon: 'User' },
  { label: '关系总数', value: relations.value.length, delta: `+${Math.max(0, relations.value.length - 1)}`, tone: 'green', icon: 'Link' },
  { label: '实体类型', value: Object.values(typeStats.value).filter(Boolean).length, delta: '+1', tone: 'violet', icon: 'Collection' },
  {
    label: '文本覆盖率',
    value: entities.value.length ? `${Math.min(99, 70 + Math.round(entities.value.length / 2))}%` : '0%',
    delta: '+5%',
    tone: 'orange',
    icon: 'TrendCharts',
  },
  {
    label: '平均置信度',
    value: entities.value.length
      ? (entities.value.reduce((sum, entity) => sum + (entity.confidence ?? 0), 0) / entities.value.length).toFixed(2)
      : '0.00',
    delta: '+0.06',
    tone: 'blue',
    icon: 'TrendCharts',
  },
])

const startButtonLabel = computed(() => {
  if (status.value === 'processing' && !isStaleProcessing.value) return '解析中'
  if (isStaleProcessing.value) return '恢复解析'
  return '开始文本解析'
})

function stepVisual(stepId) {
  return getStepVisualState(stepId, workflowPhase.value, isProcessing.value, progress.value)
}

function stepFromPhase(phase) {
  if (phase === 'graph_build' || phase === 'export') return phase
  return 'text_parse'
}

function syncSelection() {
  const paramId = route.params.fileId
  const list = files.value || []
  const file = paramId
    ? list.find((item) => item.id === paramId)
    : currentFile.value ?? list.find((item) => item.status !== 'failed') ?? list[0]
  if (!file) {
    selectedFile.value = null
    return
  }
  selectedFile.value = file
  store.selectFile(file.id)
  store.refreshProcess(file.id, { silent: true }).catch(() => undefined)
}

async function bootstrap() {
  loading.value = true
  loadError.value = ''
  try {
    try {
      await recoverKgInterrupted()
    } catch {
      // 旧版后端无此接口时忽略
    }
    await store.loadFiles()
    syncSelection()
  } catch (error) {
    loadError.value = error?.message || '加载文献列表失败'
  } finally {
    loading.value = false
  }
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function startPolling() {
  stopPolling()
  const period = store.processStatus?.status === 'processing' ? 5000 : 8000
  pollTimer = setInterval(async () => {
    const file = selectedFile.value
    if (file) {
      await store.refreshProcess(file.id, { silent: true }).catch(() => undefined)
      await store.loadFiles({ silent: true }).catch(() => undefined)
    }
  }, period)
}

async function runSelected() {
  if (!selectedFile.value) return
  actionHint.value = ''
  if (textParseReady.value && !textParseConfirmed.value) {
    actionHint.value = '文本解析已完成。请检查预览后，点击「确认并进入图谱构建」。'
    return
  }
  try {
    await store.process(selectedFile.value.id)
    router.push(`/kg/processing/${selectedFile.value.id}`)
    activeStep.value = 'text_parse'
  } catch (error) {
    actionHint.value = error?.message || '启动处理失败'
  }
}

async function rerunSelected() {
  const file = selectedFile.value
  if (!file) return
  try {
    await ElMessageBox.confirm(
      `确定要重跑「${file.doc_code || file.name}」吗？将清除文本解析中间产物并按最新流程从头处理。`,
      '重跑确认',
      { type: 'warning', confirmButtonText: '重跑', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  actionHint.value = ''
  try {
    await rerunKgProcess(file.id)
    await store.refreshProcess(file.id, { silent: true })
    await store.loadFiles({ silent: true })
    ElMessage.success('已开始重跑')
  } catch (error) {
    actionHint.value = error?.message || '重跑失败'
  }
}

async function confirmSelectedTextParse() {
  const file = selectedFile.value
  if (!file) return
  actionHint.value = ''
  try {
    await confirmKgTextParse(file.id)
    await store.refreshProcess(file.id)
    await store.loadFiles()
    activeStep.value = 'graph_build'
  } catch (error) {
    actionHint.value = error?.message || '确认文本解析失败'
  }
}

async function handleRefresh() {
  const file = selectedFile.value
  if (!file) return
  await store.refreshProcess(file.id).catch(() => undefined)
  await store.loadFiles().catch(() => undefined)
}

function handleSelectFile(fileId) {
  const file = files.value.find((item) => item.id === fileId)
  if (!file) return
  selectedFile.value = file
  store.selectFile(fileId)
  router.push(`/kg/processing/${fileId}`)
  store.refreshProcess(fileId, { silent: true }).catch(() => undefined)
}

function handleTranscribeSaved() {
  store.loadFiles({ silent: true }).catch(() => undefined)
}

watch(
  [() => route.params.fileId, files],
  () => {
    if (!loading.value) syncSelection()
  },
)

watch(files, () => {
  if (!selectedFile.value) return
  const latest = files.value.find((item) => item.id === selectedFile.value.id)
  if (latest) selectedFile.value = latest
})

watch(
  [() => selectedFile.value?.id, workflowPhase],
  () => {
    activeStep.value = stepFromPhase(workflowPhase.value)
  },
)

watch(
  () => store.processStatus?.status === 'processing',
  () => startPolling(),
)

onMounted(async () => {
  await bootstrap()
  startPolling()
})

onBeforeUnmount(stopPolling)
</script>

<style scoped lang="scss">
.processing-page {
  width: 100%;
}

.processing-header {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.processing-header h1 {
  margin: 0;
  font-size: 20px;
}

.processing-header p {
  margin: 4px 0 0;
  font-size: 13px;
}

.processing-layout {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  gap: 18px;
  align-items: start;
}

.processing-side {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--surface);
  box-shadow: var(--shadow-soft);
}

.processing-side__steps {
  display: grid;
  gap: 6px;
}

.step-card {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  width: 100%;
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--surface);
  text-align: left;
  cursor: pointer;
  transition: border-color .2s ease, background .2s ease;
}

.step-card:hover {
  border-color: var(--brand-100);
  background: var(--surface-soft);
}

.step-card--active {
  border-color: var(--brand-100);
  background: var(--brand-50);
}

.step-card__index {
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: #e5e7eb;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
}

.step-card__index--active {
  background: var(--brand-600);
  color: #fff;
}

.step-card__index--done {
  background: var(--green-500);
  color: #fff;
}

.step-card__body {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.step-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.step-card__label {
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 700;
}

.step-card__state {
  color: var(--text-tertiary);
  font-size: 10px;
  font-weight: 700;
}

.step-card__state--active {
  color: var(--brand-600);
}

.step-card__state--done {
  color: var(--green-500);
}

.step-card__hint {
  color: var(--text-secondary);
  font-size: 11px;
  line-height: 1.6;
}

.step-connector {
  width: 1px;
  height: 8px;
  margin-left: 22px;
  background: var(--border);
}

.processing-side__current {
  display: grid;
  gap: 10px;
  padding-top: 14px;
  border-top: 1px solid var(--border);
}

.processing-side__label {
  color: var(--text-tertiary);
  font-size: 11px;
}

.processing-side__name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 650;
}

.processing-side__select {
  width: 100%;
}

.processing-side__action {
  width: 100%;
}

.processing-side__hint {
  margin: 0;
  color: #b45309;
  font-size: 11px;
  line-height: 1.7;
}

.processing-side__empty {
  padding-top: 14px;
  border-top: 1px solid var(--border);
  color: var(--text-tertiary);
  font-size: 12px;
}

.processing-main {
  display: grid;
  gap: 16px;
  min-width: 0;
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.result-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(260px, .75fr);
  gap: 16px;
  align-items: start;
}

.result-card {
  padding: 18px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--surface);
  box-shadow: var(--shadow-soft);
}

.result-card__title {
  margin: 0 0 12px;
  font-size: 15px;
}

.log-list {
  display: grid;
  gap: 8px;
  color: var(--text-secondary);
  font-size: 13px;
}

.log-item {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}

.log-item__dot {
  margin-top: 6px;
  width: 6px;
  height: 6px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: var(--brand-500);
}

.option-row {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.is-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 1024px) {
  .processing-layout {
    grid-template-columns: 1fr;
  }

  .result-grid {
    grid-template-columns: 1fr;
  }
}
</style>
