<template>
  <el-button type="primary" plain @click="open">
    <el-icon><Microphone /></el-icon>
    语音转写
  </el-button>

  <el-dialog v-model="visible" title="语音转写" width="min(760px, 94vw)" @closed="reset">
    <div class="asr-toolbar">
      <el-button :loading="transcribing" @click="pickFile">
        <el-icon><Upload /></el-icon>
        选择音频文件
      </el-button>
      <span class="muted asr-toolbar__name">{{ fileName || '支持 m4a / mp3' }}</span>
    </div>
    <input ref="inputRef" type="file" accept=".m4a,.mp3" hidden @change="onFileChange" />

    <el-alert v-if="hint" class="asr-alert" type="info" :closable="false" show-icon :title="hint" />
    <el-alert v-if="error" class="asr-alert" type="error" :closable="false" show-icon :title="error" />

    <template v-if="result">
      <el-descriptions :column="3" border size="small" class="asr-meta">
        <el-descriptions-item label="时长">{{ result.duration || '—' }}</el-descriptions-item>
        <el-descriptions-item label="转写引擎">{{ result.engine || '—' }}</el-descriptions-item>
        <el-descriptions-item label="请求 ID">{{ result.requestId || '—' }}</el-descriptions-item>
      </el-descriptions>
      <el-input v-model="transcript" type="textarea" :rows="10" placeholder="转写结果可在此编辑后保存" />
    </template>

    <template #footer>
      <el-button @click="visible = false">关闭</el-button>
      <el-button :disabled="!transcript" @click="copyTranscript">
        <el-icon><DocumentCopy /></el-icon>
        复制文本
      </el-button>
      <el-button type="primary" :loading="saving" :disabled="!transcript" @click="saveAsText">
        保存为文本资料
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { createKgFileTask, transcribeKgAudio, uploadToKgTask } from '@/utils/kgApi'

const emit = defineEmits(['saved'])

const visible = ref(false)
const inputRef = ref(null)
const transcribing = ref(false)
const saving = ref(false)
const transcript = ref('')
const fileName = ref('')
const hint = ref('')
const error = ref('')
const result = ref(null)

function open() {
  visible.value = true
}

function reset() {
  transcript.value = ''
  fileName.value = ''
  hint.value = ''
  error.value = ''
  result.value = null
  transcribing.value = false
  saving.value = false
}

function pickFile() {
  inputRef.value?.click()
}

function normalizeDuration(value) {
  if (value === undefined || value === null || value === '') return ''
  const seconds = Number(value)
  if (Number.isNaN(seconds)) return String(value)
  const minutes = Math.floor(seconds / 60)
  const rest = Math.round(seconds % 60)
  return `${minutes}:${String(rest).padStart(2, '0')}`
}

function isCredentialMissing(message) {
  return /腾讯云|凭证|未配置|credential|secretid|secretkey/i.test(String(message || ''))
}

async function onFileChange(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return

  fileName.value = file.name
  transcript.value = ''
  result.value = null
  hint.value = ''
  error.value = ''
  transcribing.value = true
  try {
    const data = await transcribeKgAudio(file)
    transcript.value = data?.text ?? data?.transcript ?? ''
    result.value = {
      duration: normalizeDuration(data?.duration ?? data?.duration_seconds),
      engine: data?.engine ?? data?.engine_name ?? '',
      requestId: data?.request_id ?? data?.requestId ?? '',
    }
    if (!transcript.value) error.value = '转写完成，但未返回文本内容。'
  } catch (err) {
    const message = err?.message || '语音转写失败'
    if (isCredentialMissing(message)) {
      hint.value = '腾讯云语音服务凭证未配置，暂时无法转写。请联系管理员补全凭证后重试。'
    } else {
      error.value = message
    }
  } finally {
    transcribing.value = false
  }
}

async function copyTranscript() {
  try {
    await navigator.clipboard.writeText(transcript.value)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败，请手动选择文本复制')
  }
}

async function saveAsText() {
  if (!transcript.value) return
  saving.value = true
  error.value = ''
  try {
    const title = `${fileName.value || 'audio'}.txt`
    const task = await createKgFileTask({
      doc_code: `ASR-${Date.now()}`,
      title,
      parse_mode: 'text',
    })
    const fileId = task?.file_id ?? task?.id
    if (!fileId) throw new Error('创建文本资料任务失败')
    await uploadToKgTask(fileId, new File([transcript.value], title, { type: 'text/plain' }))
    emit('saved')
    ElMessage.success('已保存为文本资料')
    visible.value = false
  } catch (err) {
    error.value = err?.message || '保存为文本资料失败'
  } finally {
    saving.value = false
  }
}
</script>

<style scoped lang="scss">
.asr-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.asr-toolbar__name {
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.asr-alert {
  margin-bottom: 14px;
}

.asr-meta {
  margin-bottom: 14px;
}
</style>
