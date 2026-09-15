<template>
  <section v-if="!fileId" class="section-card workflow-empty">
    选择文献后，可在此查看文本解析流水线与阶段详情。
  </section>

  <section v-else class="section-card workflow-panel">
    <div class="workflow-panel__header">
      <div>
        <h2>文本解析流水线</h2>
        <p class="muted">管理文献上传后的格式检测、解密提取、段落切分与成果落盘。</p>
      </div>
      <div class="toolbar-row">
        <el-button @click="load()">
          <el-icon :class="{ 'is-spin': loading }"><Refresh /></el-icon>
          刷新
        </el-button>
        <el-button type="primary" :disabled="running || (processing && pipeline?.status === 'running')" @click="runPipelineOnly">
          <el-icon :class="{ 'is-spin': running || (processing && pipeline?.status === 'running') }">
            <component :is="running || (processing && pipeline?.status === 'running') ? 'Loading' : 'VideoPlay'" />
          </el-icon>
          运行文本解析
        </el-button>
        <el-button v-if="textParseReady && !textParseConfirmed" type="success" :disabled="confirming || processing" @click="handleConfirmTextParse">
          <el-icon :class="{ 'is-spin': confirming }">
            <component :is="confirming ? 'Loading' : 'CircleCheck'" />
          </el-icon>
          确认并进入图谱构建
        </el-button>
      </div>
    </div>

    <el-alert v-if="error" class="workflow-panel__alert" type="error" :closable="false" :title="error" />

    <el-alert
      v-if="textParseReady && !textParseConfirmed"
      class="workflow-panel__alert"
      type="success"
      :closable="false"
      :title="`文本解析已完成（${preview?.char_count ?? pipeline?.char_count ?? 0} 字符）。请检查下方预览，确认无误后点击「确认并进入图谱构建」。`"
    />

    <div class="workflow-metrics">
      <div v-for="metric in metrics" :key="metric.label" class="metric-card">
        <div class="metric-card__label">{{ metric.label }}</div>
        <div class="metric-card__value">{{ metric.value }}</div>
      </div>
    </div>

    <div class="workflow-body">
      <div class="stage-list">
        <div class="stage-list__header">
          <span>流水线阶段</span>
          <span>{{ pipeline?.overall_progress ?? 0 }}%</span>
        </div>
        <el-progress :percentage="pipeline?.overall_progress ?? 0" :show-text="false" :stroke-width="6" />
        <div class="stage-list__items">
          <button
            v-for="stage in pipeline?.stages ?? []"
            :key="stage.stage"
            type="button"
            class="stage-item"
            :class="{ 'stage-item--active': selectedStageId === stage.stage }"
            @click="selectedStageId = stage.stage"
          >
            <div class="stage-item__row">
              <span class="stage-item__label">{{ stage.label }}</span>
              <span class="stage-pill" :class="`stage-pill--${stageTone(stage.status)}`">
                {{ STAGE_STATUS_LABELS[stage.status] || stage.status }}
              </span>
            </div>
            <div class="stage-item__message">{{ stage.message || stage.hint }}</div>
          </button>
          <div v-if="!(pipeline?.stages ?? []).length" class="muted stage-list__empty">暂无阶段信息</div>
        </div>
      </div>

      <div class="workflow-detail">
        <div class="detail-card">
          <div class="detail-card__title">
            <el-icon><Document /></el-icon>
            {{ selectedStage?.label || '阶段详情' }}
          </div>
          <div class="detail-rows">
            <div class="detail-row">
              <span class="detail-row__label">阶段说明</span>
              <span class="detail-row__value">{{ selectedStage?.hint || '—' }}</span>
            </div>
            <div class="detail-row">
              <span class="detail-row__label">当前状态</span>
              <span class="detail-row__value">{{ selectedStage ? STAGE_STATUS_LABELS[selectedStage.status] || '—' : '—' }}</span>
            </div>
            <div class="detail-row">
              <span class="detail-row__label">阶段消息</span>
              <span class="detail-row__value">{{ selectedStage?.message || '—' }}</span>
            </div>
            <div class="detail-row">
              <span class="detail-row__label">阻塞原因</span>
              <span class="detail-row__value">{{ selectedStage?.blocked_reason || '无' }}</span>
            </div>
          </div>
        </div>

        <div class="detail-card">
          <div class="detail-card__title">文本预览</div>
          <div class="text-preview">{{ preview?.text_preview || '运行文本解析后，将在此显示提取结果预览。' }}</div>
          <div v-if="preview?.paragraphs?.length" class="paragraphs">
            <div class="paragraphs__title">段落样例（前 5 段）</div>
            <div v-for="(paragraph, index) in preview.paragraphs.slice(0, 5)" :key="index" class="paragraph">
              {{ paragraph }}
            </div>
          </div>
        </div>

        <div class="detail-card">
          <div class="detail-card__title">任务日志</div>
          <div class="log-list">
            <div v-for="(log, index) in (pipeline?.logs ?? []).slice(-8)" :key="index" class="log-item">
              <span class="log-item__dot" />
              <span>{{ log }}</span>
            </div>
            <div v-if="!(pipeline?.logs ?? []).length" class="muted">暂无日志</div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { confirmKgTextParse, getKgTextPipelineStatus, getKgTextPreview, runKgTextPipeline } from '@/utils/kgApi'
import { STAGE_STATUS_LABELS, STAGE_STATUS_TONES } from '@/features/kg/constants'

const props = defineProps({
  fileId: { type: String, default: '' },
  processing: { type: Boolean, default: false },
  textParseConfirmed: { type: Boolean, default: false },
  textParseReady: { type: Boolean, default: false },
})
const emit = defineEmits(['refresh', 'confirmed'])

const pipeline = ref(null)
const preview = ref(null)
const selectedStageId = ref('')
const loading = ref(false)
const running = ref(false)
const confirming = ref(false)
const error = ref('')

let pollTimer = null

const selectedStage = computed(
  () => pipeline.value?.stages?.find((stage) => stage.stage === selectedStageId.value) ?? pipeline.value?.stages?.[0],
)

const metrics = computed(() => [
  { label: '解析模式', value: pipeline.value?.parse_mode_label ?? '—' },
  { label: '字符数', value: String(pipeline.value?.char_count ?? preview.value?.char_count ?? 0) },
  { label: '段落数', value: String(pipeline.value?.paragraph_count ?? preview.value?.paragraph_count ?? 0) },
  { label: '页数', value: String(pipeline.value?.page_count ?? preview.value?.page_count ?? 0) },
])

function stageTone(status) {
  return STAGE_STATUS_TONES[status] || 'neutral'
}

async function load(silent = false) {
  if (!props.fileId) return
  if (!silent) {
    loading.value = true
    error.value = ''
  }
  try {
    const [pipelineData, previewData] = await Promise.all([
      getKgTextPipelineStatus(props.fileId),
      getKgTextPreview(props.fileId),
    ])
    pipeline.value = pipelineData
    preview.value = previewData
    if (!selectedStageId.value) {
      const stages = pipelineData?.stages ?? []
      const active =
        stages.find((stage) => stage.status === 'running') ??
        stages.find((stage) => stage.status === 'failed') ??
        stages.find((stage) => stage.status === 'pending') ??
        stages[0]
      selectedStageId.value = active?.stage ?? ''
    }
  } catch (err) {
    if (!silent) error.value = err?.message || '加载文本解析流水线失败'
  } finally {
    if (!silent) loading.value = false
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
  const period = props.processing || pipeline.value?.status === 'running' ? 5000 : 8000
  pollTimer = setInterval(() => {
    load(true)
    emit('refresh')
  }, period)
}

async function runPipelineOnly() {
  if (!props.fileId) return
  running.value = true
  error.value = ''
  try {
    await runKgTextPipeline(props.fileId)
    await load(true)
    emit('refresh')
  } catch (err) {
    error.value = err?.message || '启动流水线失败'
  } finally {
    running.value = false
  }
}

async function handleConfirmTextParse() {
  if (!props.fileId) return
  confirming.value = true
  error.value = ''
  try {
    await confirmKgTextParse(props.fileId)
    emit('refresh')
    emit('confirmed')
  } catch (err) {
    error.value = err?.message || '确认文本解析失败'
  } finally {
    confirming.value = false
  }
}

watch(
  () => props.fileId,
  () => {
    selectedStageId.value = ''
    load()
    startPolling()
  },
)

watch(
  () => [props.processing, pipeline.value?.status],
  () => startPolling(),
)

onMounted(() => {
  load()
  startPolling()
})

onBeforeUnmount(stopPolling)
</script>

<style scoped lang="scss">
.workflow-empty {
  padding: 22px;
  color: var(--text-secondary);
  font-size: 13px;
}

.workflow-panel {
  padding: 22px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--surface);
  box-shadow: var(--shadow-soft);
}

.workflow-panel__header {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.workflow-panel__header h2 {
  margin: 0;
  font-size: 16px;
}

.workflow-panel__header p {
  margin: 6px 0 0;
  font-size: 13px;
}

.workflow-panel__alert {
  margin-bottom: 14px;
}

.workflow-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 10px;
  margin-bottom: 16px;
}

.metric-card {
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--surface);
}

.metric-card__label {
  color: var(--text-secondary);
  font-size: 11px;
}

.metric-card__value {
  margin-top: 4px;
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 700;
}

.workflow-body {
  display: grid;
  grid-template-columns: minmax(240px, 280px) minmax(0, 1fr);
  gap: 18px;
}

.stage-list {
  padding: 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--surface-soft);
}

.stage-list__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
}

.stage-list__items {
  display: grid;
  gap: 8px;
  margin-top: 12px;
  max-height: 420px;
  overflow: auto;
}

.stage-item {
  display: block;
  width: 100%;
  padding: 10px 12px;
  border: 1px solid transparent;
  border-radius: var(--radius-lg);
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition: background .2s ease, border-color .2s ease;
}

.stage-item:hover {
  background: rgba(255, 255, 255, .8);
}

.stage-item--active {
  border-color: var(--brand-100);
  background: var(--surface);
  box-shadow: var(--shadow-soft);
}

.stage-item__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.stage-item__label {
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 600;
}

.stage-item__message {
  margin-top: 4px;
  color: var(--text-secondary);
  font-size: 11px;
  line-height: 1.6;
}

.stage-list__empty {
  font-size: 12px;
}

.stage-pill {
  padding: 1px 8px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 700;
  white-space: nowrap;
}

.stage-pill--neutral { color: var(--text-secondary); background: #eef1f5; }
.stage-pill--info { color: var(--brand-600); background: #dbeafe; }
.stage-pill--running { color: #fff; background: var(--brand-600); }
.stage-pill--success { color: #fff; background: var(--green-500); }
.stage-pill--failed { color: #fff; background: var(--red-500); }
.stage-pill--muted { color: var(--text-tertiary); background: #e5e7eb; }

.workflow-detail {
  display: grid;
  gap: 14px;
  align-content: start;
}

.detail-card {
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
}

.detail-card__title {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 700;
}

.detail-rows {
  display: grid;
  gap: 8px;
  font-size: 13px;
}

.detail-row {
  display: grid;
  grid-template-columns: 84px minmax(0, 1fr);
  gap: 12px;
}

.detail-row__label {
  color: var(--text-secondary);
}

.detail-row__value {
  color: var(--text-primary);
  font-weight: 550;
  word-break: break-word;
}

.text-preview {
  max-height: 176px;
  overflow: auto;
  padding: 12px;
  border-radius: var(--radius-lg);
  background: var(--surface-soft);
  color: var(--text-primary);
  font-size: 13px;
  line-height: 1.8;
  white-space: pre-wrap;
}

.paragraphs {
  display: grid;
  gap: 8px;
  margin-top: 12px;
}

.paragraphs__title {
  color: var(--text-secondary);
  font-size: 11px;
  font-weight: 600;
}

.paragraph {
  padding: 8px 12px;
  border-radius: var(--radius-lg);
  background: var(--surface-soft);
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.7;
}

.log-list {
  display: grid;
  gap: 8px;
  max-height: 160px;
  overflow: auto;
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

.is-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 900px) {
  .workflow-body {
    grid-template-columns: 1fr;
  }
}
</style>
