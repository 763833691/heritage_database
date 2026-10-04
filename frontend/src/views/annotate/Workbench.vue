<template>
  <div class="page-shell annotate-workbench">
    <section class="section-card wb-top">
      <div class="wb-top__left">
        <el-button text @click="$router.push('/annotate')"><el-icon><ArrowLeft /></el-icon>返回任务列表</el-button>
        <h1>{{ taskName || `标注任务 #${taskId}` }}</h1>
      </div>
      <div class="wb-top__right">
        <button class="coder-chip" type="button" @click="openCoderDialog">
          <el-icon><User /></el-icon>
          编码者：<strong>{{ coder || '未设置' }}</strong>
        </button>
        <span class="wb-progress">进度 <strong>{{ progress.done }}</strong> / {{ progress.total }}</span>
        <el-button @click="$router.push(`/annotate/${taskId}/results`)">结果页</el-button>
      </div>
    </section>

    <section v-if="finished" class="section-card wb-finished">
      <el-icon class="wb-finished__icon"><CircleCheckFilled /></el-icon>
      <h2>已完成全部 {{ progress.total }} 张标注</h2>
      <p class="muted">编码者「{{ coder }}」的盲标任务已全部提交，可查看结果或切换其他编码者继续。</p>
      <div class="wb-finished__actions">
        <el-button type="primary" @click="$router.push(`/annotate/${taskId}/results`)">查看信度结果</el-button>
        <el-button @click="openCoderDialog">切换编码者</el-button>
      </div>
    </section>

    <section v-else class="wb-body" v-loading="loading">
      <div class="wb-photo">
        <div class="wb-photo__frame">
          <img
            v-if="current && !photoError"
            :key="current.item_id"
            :src="current.photo_url"
            :alt="`样本 ${current.sid}`"
            @error="photoError = true"
          />
          <div v-else-if="current && photoError" class="wb-photo__fallback">
            <el-icon><PictureFilled /></el-icon>
            <span>照片加载失败</span>
          </div>
          <div v-else class="wb-photo__fallback">
            <el-icon><PictureFilled /></el-icon>
            <span>暂无照片</span>
          </div>
        </div>
        <div class="wb-photo__meta">
          <span>样本编号</span>
          <strong>{{ current?.sid || '—' }}</strong>
        </div>
      </div>

      <aside class="wb-codes">
        <p class="wb-codes__title">请选择照片所属类目（快捷键 A–G）</p>
        <button
          v-for="code in categoryKeys"
          :key="code"
          type="button"
          :class="['wb-code', { 'wb-code--active': answers[current?.item_id] === code }]"
          :disabled="loading"
          @click="selectCode(code)"
        >
          <span class="wb-code__badge">{{ code }}</span>
          <span class="wb-code__text">
            <strong>{{ CATEGORY_NAMES[code] }}</strong>
            <small>{{ CATEGORY_DEFINITIONS[code] }}</small>
          </span>
        </button>

        <div v-if="gMode" class="wb-note">
          <el-input
            v-model="gNote"
            type="textarea"
            :rows="2"
            maxlength="200"
            placeholder="G 其他：可填写备注（选填）"
            @keydown.enter.prevent="confirmG"
            @keydown.esc.prevent="cancelG"
          />
          <div class="wb-note__actions">
            <el-button size="small" @click="cancelG">取消</el-button>
            <el-button size="small" type="primary" @click="confirmG">确认记录 G</el-button>
          </div>
        </div>

        <div class="wb-nav">
          <el-button :disabled="index <= 0 || loading" @click="goBack"><el-icon><ArrowLeft /></el-icon>上一张</el-button>
          <el-button :disabled="loading || !canAdvance" @click="advance">下一张<el-icon><ArrowRight /></el-icon></el-button>
        </div>
      </aside>
    </section>

    <transition name="wb-flash">
      <div v-if="flash" class="wb-flash">已记录</div>
    </transition>

    <el-dialog
      v-model="coderDialogVisible"
      title="请输入编码者代号"
      width="min(420px, 92vw)"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      :show-close="Boolean(coder)"
    >
      <p class="muted">代号用于区分不同编码者的独立编码（如 coder1、coder2），将保存在本机浏览器。</p>
      <el-input v-model="coderInput" maxlength="50" placeholder="如 coder1" @keyup.enter="saveCoder" />
      <template #footer>
        <el-button v-if="coder" @click="coderDialogVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!coderInput.trim()" @click="saveCoder">确定并开始</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  CATEGORY_DEFINITIONS,
  CATEGORY_NAMES,
  getNextAnnotationItem,
  listAnnotationTasks,
  submitAnnotationCode,
} from '@/utils/annotateApi'

const CODER_KEY = 'annotate_coder'
const route = useRoute()
const taskId = Number(route.params.id)

const categoryKeys = Object.keys(CATEGORY_NAMES)

const taskName = ref('')
const coder = ref(localStorage.getItem(CODER_KEY) || '')
const coderDialogVisible = ref(false)
const coderInput = ref('')

const current = ref(null)
const history = ref([])
const index = ref(-1)
const answers = reactive({})
const notes = reactive({})
const progress = reactive({ done: 0, total: 0 })
const finished = ref(false)
const loading = ref(false)
const photoError = ref(false)
const flash = ref(false)
const gMode = ref(false)
const gNote = ref('')

const canAdvance = computed(() => {
  if (!current.value) return false
  if (index.value < history.value.length - 1) return true
  return Boolean(answers[current.value.item_id])
})

function openCoderDialog() {
  coderInput.value = coder.value
  coderDialogVisible.value = true
}

function saveCoder() {
  const value = coderInput.value.trim()
  if (!value) return
  const changed = value !== coder.value
  coder.value = value
  localStorage.setItem(CODER_KEY, value)
  coderDialogVisible.value = false
  if (changed) resetSession()
}

function resetSession() {
  current.value = null
  history.value = []
  index.value = -1
  finished.value = false
  photoError.value = false
  gMode.value = false
  gNote.value = ''
  Object.keys(answers).forEach((key) => delete answers[key])
  Object.keys(notes).forEach((key) => delete notes[key])
  fetchNext()
}

function applyCurrent() {
  current.value = history.value[index.value] || null
  photoError.value = false
  gMode.value = false
  gNote.value = current.value ? notes[current.value.item_id] || '' : ''
}

async function fetchNext() {
  if (!coder.value) return
  loading.value = true
  try {
    const data = await getNextAnnotationItem(taskId, coder.value)
    if (data.progress) Object.assign(progress, data.progress)
    if (data.finished) {
      finished.value = true
      current.value = null
      return
    }
    const item = { item_id: data.item_id, sid: data.sid, photo_url: data.photo_url }
    history.value = [...history.value, item]
    index.value = history.value.length - 1
    applyCurrent()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '获取下一张失败')
  } finally {
    loading.value = false
  }
}

function advance() {
  if (index.value < history.value.length - 1) {
    index.value += 1
    applyCurrent()
    return
  }
  if (current.value && !answers[current.value.item_id]) return
  fetchNext()
}

function goBack() {
  if (index.value <= 0) return
  index.value -= 1
  applyCurrent()
}

function selectCode(code) {
  if (!current.value || loading.value) return
  if (code === 'G') {
    gMode.value = true
    return
  }
  submit(code, '')
}

function cancelG() {
  gMode.value = false
}

function confirmG() {
  submit('G', gNote.value)
}

async function submit(code, note) {
  if (!current.value || loading.value) return
  const itemId = current.value.item_id
  loading.value = true
  try {
    const data = await submitAnnotationCode(itemId, { coder: coder.value, code, note })
    answers[itemId] = code
    notes[itemId] = note || ''
    if (data.progress) {
      Object.assign(progress, data.progress)
    } else if (progress.done < progress.total) {
      progress.done += 1
    }
    gMode.value = false
    flash.value = true
    setTimeout(() => {
      flash.value = false
    }, 300)
    await advance()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '提交失败')
  } finally {
    loading.value = false
  }
}

function isTypingTarget(target) {
  const tag = target?.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || target?.isContentEditable
}

function onKeydown(event) {
  if (coderDialogVisible.value || finished.value || gMode.value) return
  if (isTypingTarget(event.target)) return
  const key = event.key
  if (key === 'ArrowLeft') {
    event.preventDefault()
    goBack()
    return
  }
  if (key === 'ArrowRight') {
    event.preventDefault()
    advance()
    return
  }
  const code = key.toUpperCase()
  if (categoryKeys.includes(code)) {
    event.preventDefault()
    selectCode(code)
  }
}

onMounted(async () => {
  window.addEventListener('keydown', onKeydown)
  try {
    const data = await listAnnotationTasks()
    const task = (data.items || []).find((item) => item.id === taskId)
    taskName.value = task?.name || ''
  } catch {
    taskName.value = ''
  }
  if (!coder.value) {
    coderDialogVisible.value = true
  } else {
    resetSession()
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
})
</script>

<style scoped>
.annotate-workbench {
  position: relative;
}
.wb-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}
.wb-top__left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.wb-top__left h1 {
  margin: 0;
  font-size: 20px;
  color: var(--text-primary);
}
.wb-top__right {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}
.coder-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: #fff;
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
}
.coder-chip strong {
  color: var(--brand-600);
}
.wb-progress {
  font-size: 14px;
  color: var(--text-secondary);
}
.wb-progress strong {
  color: var(--brand-600);
  font-size: 18px;
}

.wb-body {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 400px;
  gap: 18px;
  margin-top: 18px;
  align-items: start;
}
.wb-photo {
  border: 1px solid var(--border);
  border-radius: 14px;
  background: #0f172a;
  padding: 14px;
}
.wb-photo__frame {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
  max-height: 72vh;
  overflow: hidden;
}
.wb-photo__frame img {
  max-width: 100%;
  max-height: 72vh;
  object-fit: contain;
  border-radius: 8px;
}
.wb-photo__fallback {
  display: grid;
  place-items: center;
  gap: 10px;
  color: #94a3b8;
  min-height: 320px;
  font-size: 40px;
}
.wb-photo__fallback span {
  font-size: 14px;
}
.wb-photo__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 12px;
  padding: 10px 14px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.06);
  color: #cbd5e1;
  font-size: 13px;
}
.wb-photo__meta strong {
  color: #fff;
  font-size: 16px;
  letter-spacing: 0.04em;
}

.wb-codes {
  display: grid;
  gap: 10px;
}
.wb-codes__title {
  margin: 0 0 2px;
  font-size: 13px;
  color: var(--text-secondary);
}
.wb-code {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  width: 100%;
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: #fff;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease, box-shadow 0.15s ease;
}
.wb-code:hover:not(:disabled) {
  border-color: var(--brand-200);
  background: var(--brand-50);
}
.wb-code--active {
  border-color: var(--brand-600);
  background: var(--brand-50);
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.15);
}
.wb-code__badge {
  flex: none;
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  border-radius: 9px;
  background: var(--brand-600);
  color: #fff;
  font-weight: 700;
  font-size: 15px;
}
.wb-code__text {
  display: grid;
  gap: 3px;
}
.wb-code__text strong {
  font-size: 14px;
  color: var(--text-primary);
}
.wb-code__text small {
  font-size: 11px;
  line-height: 1.5;
  color: var(--text-tertiary);
}
.wb-note {
  display: grid;
  gap: 8px;
  padding: 12px;
  border: 1px dashed var(--brand-200);
  border-radius: 12px;
  background: var(--brand-50);
}
.wb-note__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.wb-nav {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  margin-top: 4px;
}

.wb-finished {
  margin-top: 18px;
  display: grid;
  place-items: center;
  gap: 8px;
  text-align: center;
  padding: 56px 24px;
}
.wb-finished__icon {
  font-size: 52px;
  color: #16a34a;
}
.wb-finished h2 {
  margin: 6px 0 0;
  color: var(--text-primary);
}
.wb-finished__actions {
  display: flex;
  gap: 12px;
  margin-top: 14px;
}

.wb-flash {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  padding: 14px 34px;
  border-radius: 12px;
  background: rgba(22, 163, 74, 0.92);
  color: #fff;
  font-size: 18px;
  font-weight: 600;
  z-index: 3000;
  pointer-events: none;
}
.wb-flash-enter-active,
.wb-flash-leave-active {
  transition: opacity 0.15s ease;
}
.wb-flash-enter-from,
.wb-flash-leave-to {
  opacity: 0;
}

@media (max-width: 980px) {
  .wb-body {
    grid-template-columns: 1fr;
  }
  .wb-photo__frame {
    min-height: 40vh;
  }
}
</style>
