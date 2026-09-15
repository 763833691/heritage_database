<template>
  <div class="books-panel">
    <div v-if="queueProgress" class="books-queue">
      <el-alert
        type="info"
        :closable="false"
        :title="`批量${queueProgress.mode === 'rerun' ? '重跑' : '处理'}：${queueProgress.current}/${queueProgress.total} · ${queueProgress.label}`"
      />
      <el-button text type="danger" size="small" @click="queueAbort = true">取消队列</el-button>
    </div>

    <el-alert v-if="error" class="books-alert" type="error" :closable="false" :title="error" />

    <input ref="fileInputRef" type="file" accept=".pdf,.caj,.kdh,.txt,.md" hidden @change="onFileChange" />

    <section class="section-card books-create">
      <div class="books-create__toolbar">
        <AutoSaveIndicator :status="createSaveStatus" :saving="creating" />
        <el-button size="small" @click="loadFiles()">
          <el-icon :class="{ 'is-spin': loading }"><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
      <div class="books-create__fields">
        <el-input v-model="docCode" placeholder="文献编号" @blur="handleCreateBlurSave" />
        <el-input v-model="title" placeholder="文献标题" @blur="handleCreateBlurSave" />
        <el-input v-model="discipline" placeholder="专业（可选）" @blur="handleCreateBlurSave" />
        <el-select v-model="parseMode" placeholder="解析模式" @blur="handleCreateBlurSave">
          <el-option v-for="option in PARSE_MODE_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
        </el-select>
      </div>
      <p class="muted books-create__hint">文献编号与标题填写完成后，任意字段失焦将自动创建文献任务。</p>
    </section>

    <StatusState v-if="loading && !files.length" type="loading" title="正在加载文献列表" />
    <StatusState
      v-else-if="!files.length"
      type="empty"
      title="还没有文献任务"
      description="请先在上方创建文献并上传文件，或前往「文件库」上传后回到此处处理。"
    />

    <template v-else>
      <section class="section-card books-batch">
        <div class="toolbar-row">
          <el-checkbox :model-value="allSelectableSelected" @change="toggleSelectAll">全选</el-checkbox>
          <span class="muted">已选 {{ selectedIds.length }} 项</span>
          <div class="books-batch__actions">
            <el-button
              type="success"
              size="small"
              :disabled="batchRunning || !selectedStartCount"
              @click="runSequentialQueue('start', startQueueFiles)"
            >
              批量开始 ({{ selectedStartCount }})
            </el-button>
            <el-button
              size="small"
              :disabled="batchRunning || !selectedRerunCount"
              @click="runSequentialQueue('rerun', rerunQueueFiles)"
            >
              批量重跑 ({{ selectedRerunCount }})
            </el-button>
          </div>
        </div>
      </section>

      <div class="books-list">
        <article
          v-for="file in files"
          :key="file.id"
          class="book-card"
          :class="{
            'book-card--active': selectedFileId === file.id,
            'book-card--running': isRunning(file.id),
          }"
          tabindex="0"
          @click="focusFile(file)"
          @keydown.enter.prevent="focusFile(file)"
          @keydown.space.prevent="focusFile(file)"
        >
          <el-checkbox
            class="book-card__check"
            :model-value="selectedIds.includes(file.id)"
            :disabled="file.status === 'created' || batchRunning"
            @click.stop
            @change="toggleSelect(file.id)"
          />
          <div class="book-card__body">
            <div class="book-card__meta">
              <span v-if="selectedFileId === file.id" class="book-card__current">当前处理</span>
              <span class="book-card__code">{{ file.doc_code || file.id }}</span>
              <StatusBadge :status="file.status" :process-status="file.process_status" />
              <span class="book-card__tag">{{ PARSE_MODE_LABELS[file.parse_mode || 'auto_detect'] || file.parse_mode || '—' }}</span>
              <span v-if="file.page_count" class="muted">{{ file.page_count }} 页</span>
            </div>
            <p class="book-card__name">{{ file.name }}</p>
            <div v-if="pipelines[file.id]?.status" class="book-card__progress">
              <el-progress
                :percentage="pipelines[file.id].overallProgress"
                :show-text="false"
                :stroke-width="6"
                class="book-card__bar"
              />
              <span class="muted">
                {{ stageSuccessCount(file.id) }}/{{ pipelines[file.id].status.stages?.length ?? 0 }} 阶段 ·
                {{ pipelines[file.id].overallProgress }}%
              </span>
              <span v-if="isRunning(file.id) && pipelines[file.id].activeStage" class="book-card__stage">
                {{ STAGE_LABELS[pipelines[file.id].activeStage] || pipelines[file.id].activeStage }} 运行中...
              </span>
            </div>
          </div>
          <div class="book-card__actions" @click.stop @keydown.stop>
            <el-button size="small" :disabled="uploading[file.id] || isRunning(file.id)" @click="openLibraryModal(file.id)">
              <el-icon><FolderOpened /></el-icon>
              文件库载入
            </el-button>
            <el-button size="small" :disabled="uploading[file.id] || isRunning(file.id)" @click="handleUploadClick(file.id)">
              <el-icon :class="{ 'is-spin': uploading[file.id] }">
                <component :is="uploading[file.id] ? 'Loading' : 'Upload'" />
              </el-icon>
              上传文件
            </el-button>
            <el-button
              size="small"
              :type="startButtonTone(file)"
              :disabled="isRunning(file.id) || !isEligible(file) || uploading[file.id] || rerunning[file.id] || batchRunning"
              @click="handleAutoRun(file)"
            >
              <el-icon><VideoPlay /></el-icon>
              {{ startButtonLabel(file) }}
            </el-button>
            <el-button size="small" :disabled="!canRerun(file) || batchRunning" @click="handleRerun(file)">
              <el-icon :class="{ 'is-spin': rerunning[file.id] }">
                <component :is="rerunning[file.id] ? 'Loading' : 'RefreshLeft'" />
              </el-icon>
              重跑
            </el-button>
            <el-button size="small" @click="focusFile(file)">
              <el-icon><View /></el-icon>
              处理详情
            </el-button>
            <el-button size="small" text type="danger" @click="handleDelete(file)">
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
        </article>
      </div>
    </template>

    <el-dialog v-model="showLibraryModal" title="从文件库载入" width="min(620px, 94vw)">
      <div class="library-list">
        <button
          v-for="file in libraryCandidates"
          :key="file.id"
          type="button"
          class="library-item"
          @click="handleLibrarySelect(file.id)"
        >
          <span class="library-item__name">{{ file.name }}</span>
          <span class="muted">{{ String(file.type || '').toUpperCase() }}</span>
        </button>
        <p v-if="!libraryCandidates.length" class="muted">文件库暂无可载入的文献，请先在文件库上传。</p>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createKgFileTask,
  deleteKgFile,
  getKgFiles,
  getKgTextPipelineStatus,
  importFromKgLibrary,
  recoverKgInterrupted,
  rerunKgProcess,
  startKgProcess,
  uploadToKgTask,
} from '@/utils/kgApi'
import AutoSaveIndicator from '@/features/kg/components/AutoSaveIndicator.vue'
import StatusBadge from '@/features/kg/components/StatusBadge.vue'
import StatusState from '@/components/common/StatusState.vue'
import { useBlurSave } from '@/features/kg/useBlurSave'
import { PARSE_MODE_LABELS, PARSE_MODE_OPTIONS, STAGE_LABELS, isTextParseReady, sleep } from '@/features/kg/constants'

defineProps({
  selectedFileId: { type: String, default: '' },
})
const emit = defineEmits(['open-detail'])

const files = ref([])
const pipelines = ref({})
const docCode = ref('')
const title = ref('')
const discipline = ref('')
const parseMode = ref('auto_detect')
const loading = ref(true)
const error = ref('')
const selectedIds = ref([])
const batchRunning = ref(false)
const queueProgress = ref(null)
const queueAbort = ref(false)
const uploading = ref({})
const rerunning = ref({})
const showLibraryModal = ref(false)
const targetFileId = ref('')
const fileInputRef = ref(null)
const lastCreatedKey = ref('')

let pollTimer = null

function computeOverall(stages) {
  if (!stages?.length) return 0
  const sum = stages.reduce(
    (acc, stage) => acc + (stage.status === 'success' || stage.status === 'skipped' ? 100 : stage.progress),
    0,
  )
  return Math.round(sum / stages.length)
}

function findActiveStage(stages) {
  const active = (stages || []).find((stage) => ['running', 'queued', 'cancel_requested'].includes(stage.status))
  return active?.stage ?? null
}

async function loadFiles({ silent = false } = {}) {
  if (!silent) {
    loading.value = true
    error.value = ''
  }
  try {
    const data = await getKgFiles()
    files.value = data?.files || []
  } catch (err) {
    if (!silent) error.value = err?.message || '加载文献列表失败'
  } finally {
    if (!silent) loading.value = false
  }
}

async function loadPipelines(items) {
  const readyItems = (items || []).filter((item) => item.status !== 'created' && item.content_path)
  const results = await Promise.allSettled(readyItems.map((item) => getKgTextPipelineStatus(item.id)))
  const next = { ...pipelines.value }
  readyItems.forEach((item, index) => {
    const result = results[index]
    if (result.status !== 'fulfilled') return
    const status = result.value
    next[item.id] = {
      status,
      activeStage: status?.status === 'running' ? findActiveStage(status.stages) : null,
      overallProgress: status?.overall_progress || computeOverall(status?.stages),
    }
  })
  pipelines.value = next
}

function hasCreateChanges() {
  return Boolean(docCode.value.trim() && title.value.trim())
}

async function createLiterature() {
  const code = docCode.value.trim()
  const name = title.value.trim()
  if (!code || !name) return

  const createKey = `${code}|${name}|${discipline.value.trim()}|${parseMode.value}`
  if (lastCreatedKey.value === createKey) return

  error.value = ''
  await createKgFileTask({
    doc_code: code,
    title: name,
    discipline: discipline.value.trim(),
    parse_mode: parseMode.value,
  })
  lastCreatedKey.value = createKey
  docCode.value = ''
  title.value = ''
  discipline.value = ''
  parseMode.value = 'auto_detect'
  lastCreatedKey.value = ''
  await loadFiles()
}

const {
  status: createSaveStatus,
  saving: creating,
  onBlurSave: handleCreateBlurSave,
} = useBlurSave({
  hasChanges: hasCreateChanges,
  save: createLiterature,
  onError: (err) => {
    error.value = err?.message || '创建文献任务失败'
  },
})

const hasActiveJobs = computed(
  () => files.value.some((file) => file.status === 'processing') || Object.values(pipelines.value).some((item) => item.activeStage),
)

const selectableFiles = computed(() => files.value.filter((file) => file.status !== 'created'))
const allSelectableSelected = computed(
  () => selectableFiles.value.length > 0 && selectableFiles.value.every((file) => selectedIds.value.includes(file.id)),
)

function isRunning(fileId) {
  return Boolean(pipelines.value[fileId]?.activeStage)
}

function isStaleProcessing(file) {
  return file.status === 'processing' && !isRunning(file.id)
}

function isEligible(file) {
  if (file.status === 'created' || !file.content_path) return false
  return !isRunning(file.id)
}

function canRerun(file) {
  if (file.status === 'created' || !file.content_path) return false
  if (uploading.value[file.id] || rerunning.value[file.id] || isRunning(file.id)) return false
  return true
}

function startButtonTone(file) {
  return isTextParseReady(file.process_status) && !file.process_status?.text_parse_confirmed ? 'default' : 'success'
}

function startButtonLabel(file) {
  if (isStaleProcessing(file)) return '恢复文本解析'
  if (isTextParseReady(file.process_status) && !file.process_status?.text_parse_confirmed) return '已完成，待确认'
  return '开始文本解析'
}

const selectedStartCount = computed(
  () => files.value.filter((file) => selectedIds.value.includes(file.id) && isEligible(file)).length,
)
const selectedRerunCount = computed(
  () => files.value.filter((file) => selectedIds.value.includes(file.id) && canRerun(file)).length,
)
const startQueueFiles = computed(() => files.value.filter((file) => selectedIds.value.includes(file.id) && isEligible(file)))
const rerunQueueFiles = computed(() => files.value.filter((file) => selectedIds.value.includes(file.id) && canRerun(file)))
const libraryCandidates = computed(() => files.value.filter((file) => file.content_path && file.status !== 'created'))

function stageSuccessCount(fileId) {
  const stages = pipelines.value[fileId]?.status?.stages ?? []
  return stages.filter((stage) => stage.status === 'success' || stage.status === 'skipped').length
}

function setFlag(mapRef, id, value) {
  mapRef.value = { ...mapRef.value, [id]: value }
}

function focusFile(file) {
  emit('open-detail', file.id)
}

function toggleSelect(fileId) {
  if (selectedIds.value.includes(fileId)) {
    selectedIds.value = selectedIds.value.filter((id) => id !== fileId)
  } else {
    selectedIds.value = [...selectedIds.value, fileId]
  }
}

function toggleSelectAll(checked) {
  if (checked) {
    selectedIds.value = Array.from(new Set([...selectedIds.value, ...selectableFiles.value.map((file) => file.id)]))
    return
  }
  selectedIds.value = selectedIds.value.filter((id) => !selectableFiles.value.some((file) => file.id === id))
}

async function handleAutoRun(file) {
  error.value = ''
  focusFile(file)
  if (isTextParseReady(file.process_status) && !file.process_status?.text_parse_confirmed) {
    error.value = '该文献文本解析已完成，请在下方点击「确认并进入图谱构建」，不要重复点「开始文本解析」。'
    return
  }
  try {
    await startKgProcess(file.id)
    await loadFiles()
    await loadPipelines([file])
  } catch (err) {
    error.value = err?.message || `启动 ${file.doc_code || file.name} 失败`
  }
}

async function handleRerun(file) {
  try {
    await ElMessageBox.confirm(
      `确定要重跑「${file.doc_code || file.name}」吗？将清除文本解析中间产物并按最新流程从头处理。`,
      '重跑确认',
      { type: 'warning', confirmButtonText: '重跑', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  focusFile(file)
  setFlag(rerunning, file.id, true)
  error.value = ''
  try {
    await rerunKgProcess(file.id)
    await loadFiles()
    await loadPipelines([file])
  } catch (err) {
    error.value = err?.message || '重跑失败'
  } finally {
    setFlag(rerunning, file.id, false)
  }
}

function handleUploadClick(fileId) {
  targetFileId.value = fileId
  fileInputRef.value?.click()
}

async function onFileChange(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file || !targetFileId.value) return
  const fileId = targetFileId.value
  setFlag(uploading, fileId, true)
  error.value = ''
  try {
    const data = await uploadToKgTask(fileId, file)
    await loadFiles()
    const targetId = data?.file_id ?? fileId
    const created = files.value.find((entry) => entry.id === targetId)
    await handleAutoRun(created || { id: targetId, name: file.name, status: 'uploaded', process_status: null })
  } catch (err) {
    error.value = err?.message || '上传失败'
  } finally {
    setFlag(uploading, fileId, false)
    targetFileId.value = ''
  }
}

function openLibraryModal(fileId) {
  targetFileId.value = fileId
  showLibraryModal.value = true
}

async function handleLibrarySelect(sourceFileId) {
  if (!targetFileId.value) return
  const fileId = targetFileId.value
  showLibraryModal.value = false
  setFlag(uploading, fileId, true)
  error.value = ''
  try {
    const data = await importFromKgLibrary(fileId, sourceFileId)
    await loadFiles()
    const targetId = data?.file_id ?? fileId
    const created = files.value.find((entry) => entry.id === targetId)
    await handleAutoRun(created || { id: targetId, name: sourceFileId, status: 'uploaded', process_status: null })
  } catch (err) {
    error.value = err?.message || '文件库载入失败'
  } finally {
    setFlag(uploading, fileId, false)
    targetFileId.value = ''
  }
}

async function handleDelete(file) {
  try {
    await ElMessageBox.confirm(`确定删除「${file.doc_code || file.name}」吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await deleteKgFile(file.id)
    await loadFiles()
    ElMessage.success('已删除')
  } catch (err) {
    error.value = err?.message || '删除失败'
  }
}

async function runSequentialQueue(mode, ordered) {
  if (!ordered.length) {
    error.value = '请先勾选要处理的文献'
    return
  }
  queueAbort.value = false
  batchRunning.value = true
  error.value = ''
  const failures = []
  try {
    for (let index = 0; index < ordered.length; index += 1) {
      if (queueAbort.value) break
      const file = ordered[index]
      queueProgress.value = { current: index + 1, total: ordered.length, label: file.doc_code || file.name, mode }
      try {
        if (mode === 'rerun') {
          setFlag(rerunning, file.id, true)
          await rerunKgProcess(file.id)
        } else {
          await startKgProcess(file.id)
        }
        while (!queueAbort.value) {
          await sleep(2000)
          await loadFiles({ silent: true })
          const latest = (files.value || []).find((item) => item.id === file.id)
          if (!latest || latest.status !== 'processing') break
        }
      } catch (err) {
        failures.push(`${file.doc_code || file.name}: ${err?.message || '失败'}`)
      } finally {
        if (mode === 'rerun') setFlag(rerunning, file.id, false)
      }
    }
    if (failures.length) error.value = `批量完成，${failures.length} 项失败：\n${failures.join('\n')}`
    await loadFiles()
    await loadPipelines(files.value)
  } finally {
    batchRunning.value = false
    queueProgress.value = null
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
  pollTimer = setInterval(() => {
    loadPipelines(files.value)
    loadFiles({ silent: true })
  }, hasActiveJobs.value ? 5000 : 8000)
}

watch(
  () => files.value,
  (value) => {
    if (value?.length) loadPipelines(value)
  },
)

watch(hasActiveJobs, () => {
  if (files.value.length) startPolling()
})

onMounted(async () => {
  try {
    await recoverKgInterrupted()
  } catch {
    // 旧版后端无此接口时忽略
  }
  await loadFiles()
  if (files.value.length) startPolling()
})

onBeforeUnmount(stopPolling)
</script>

<style scoped lang="scss">
.books-panel {
  display: grid;
  gap: 14px;
}

.books-alert {
  margin: 0;
}

.books-queue {
  display: flex;
  align-items: center;
  gap: 10px;
}

.books-queue :deep(.el-alert) {
  flex: 1;
}

.books-create {
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--surface);
  box-shadow: var(--shadow-soft);
}

.books-create__toolbar {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  margin-bottom: 12px;
}

.books-create__fields {
  display: grid;
  grid-template-columns: 160px minmax(0, 1fr) 180px 150px;
  gap: 12px;
}

.books-create__hint {
  margin: 10px 0 0;
  font-size: 11px;
}

.books-batch {
  padding: 12px 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--surface);
  box-shadow: var(--shadow-soft);
}

.books-batch__actions {
  display: flex;
  gap: 8px;
  margin-left: auto;
}

.books-list {
  display: grid;
  gap: 12px;
}

.book-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--surface);
  box-shadow: var(--shadow-soft);
  cursor: pointer;
  transition: border-color .2s ease, background .2s ease;
}

.book-card:hover {
  border-color: var(--brand-100);
  background: #fbfdff;
}

.book-card--active {
  border-color: var(--brand-500);
  background: var(--brand-50);
}

.book-card--running {
  border-color: #a5f3fc;
}

.book-card__check {
  flex: 0 0 auto;
}

.book-card__body {
  min-width: 0;
  flex: 1;
}

.book-card__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.book-card__current {
  padding: 1px 7px;
  border-radius: var(--radius-md);
  color: #fff;
  background: var(--brand-600);
  font-size: 10px;
  font-weight: 700;
}

.book-card__code {
  color: var(--text-primary);
  font-weight: 650;
}

.book-card__tag {
  padding: 1px 9px;
  border-radius: 999px;
  color: var(--text-secondary);
  background: var(--surface-soft);
  font-size: 11px;
}

.book-card__name {
  margin: 0;
  color: var(--text-secondary);
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.book-card__progress {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-top: 8px;
  font-size: 11px;
}

.book-card__bar {
  width: 160px;
}

.book-card__stage {
  color: #0e7490;
  font-weight: 600;
}

.book-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  flex: 0 0 auto;
}

.library-list {
  display: grid;
  gap: 8px;
  max-height: 320px;
  overflow: auto;
}

.library-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--surface);
  font-size: 13px;
  text-align: left;
  cursor: pointer;
}

.library-item:hover {
  background: var(--surface-soft);
}

.library-item__name {
  font-weight: 600;
}

.is-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 1100px) {
  .books-create__fields {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
