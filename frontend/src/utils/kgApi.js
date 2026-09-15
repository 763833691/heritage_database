import api from '@/utils/api'

/**
 * 知识图谱子系统接口客户端。
 *
 * 后端契约：知识图谱子系统使用 { code, message, data } 信封（code=0 成功、
 * code=1 业务失败、code=2 处理中），与平台原有的 { detail } 错误结构共存。
 */

const SENTINEL_MESSAGES = {
  FILE_TOO_LARGE: (_, raw) => {
    const limit = raw.split(':')[1]
    return `文件超过上传大小限制（最大 ${limit} MB）`
  },
  FOLDER_NAME_EXISTS: () => '同名分类已存在',
  FOLDER_NAME_REQUIRED: () => '分类名称不能为空',
  FOLDER_NOT_FOUND: () => '分类不存在',
  FILE_NOT_FOUND: () => '文件不存在',
}

function normalizeError(error) {
  const detail = error?.response?.data?.detail
  const message = error?.response?.data?.message || detail || error?.message || '请求失败'
  const sentinelKey = Object.keys(SENTINEL_MESSAGES).find((key) => String(message).startsWith(key))
  if (sentinelKey) {
    return new Error(SENTINEL_MESSAGES[sentinelKey](message, String(message)))
  }
  return new Error(message)
}

async function request(promise) {
  try {
    const response = await promise
    const body = response?.data
    if (body && typeof body === 'object' && 'code' in body) {
      if (body.code === 1) {
        // 契约说明：业务失败时真实原因在 data.message，信封 message 固定为 "success"
        const reason = body.data?.message || (body.message !== 'success' ? body.message : '')
        throw new Error(reason || '操作未完成，请按提示先完成前置步骤')
      }
      return body.data
    }
    return body
  } catch (error) {
    if (error instanceof Error && !error.response) throw error
    throw normalizeError(error)
  }
}

const POLL_TIMEOUT = 120000

// ===== 文件库 =====
export const getKgFiles = () => request(api.get('/file/list', { timeout: POLL_TIMEOUT }))
export const getKgFile = (fileId) => request(api.get(`/file/${fileId}`))
export const uploadKgFile = (file, folderId = '') => {
  const form = new FormData()
  form.append('file', file)
  return request(
    api.post('/file/upload', form, { params: { folder_id: folderId }, timeout: 300000 })
  )
}
export const createKgFileTask = (payload) => request(api.post('/file/tasks', payload))
export const uploadToKgTask = (fileId, file) => {
  const form = new FormData()
  form.append('file', file)
  return request(api.post(`/file/${fileId}/upload`, form, { timeout: 300000 }))
}
export const importFromKgLibrary = (fileId, sourceFileId) =>
  request(api.post(`/file/${fileId}/import/${sourceFileId}`))
export const updateKgFile = (fileId, payload) => request(api.patch(`/file/${fileId}`, payload))
export const deleteKgFile = (fileId) => request(api.delete(`/file/${fileId}`))

// ===== 分类（文件库目录）=====
export const getKgFolders = () => request(api.get('/file/folders/list'))
export const createKgFolder = (name) => request(api.post('/file/folders', { name }))
export const updateKgFolder = (folderId, name) =>
  request(api.patch(`/file/folders/${folderId}`, { name }))
export const deleteKgFolder = (folderId) => request(api.delete(`/file/folders/${folderId}`))

// ===== 处理流程 =====
export const startKgProcess = (fileId) => request(api.post(`/process/${fileId}`))
export const rerunKgProcess = (fileId) => request(api.post(`/process/${fileId}/rerun`))
export const batchRunKgProcess = (fileIds, mode = 'start') =>
  request(api.post('/process/batch-run', { file_ids: fileIds, mode }))
export const confirmKgTextParse = (fileId) =>
  request(api.post(`/process/${fileId}/confirm-text-parse`))
export const runKgGraphBuild = (fileId, method) =>
  request(api.post(`/process/${fileId}/graph-build/run`, { method }))
export const runKgExport = (fileId) => request(api.post(`/process/${fileId}/export/run`))
export const getKgProcessStatus = (fileId) =>
  request(api.get(`/process/${fileId}/status`, { timeout: POLL_TIMEOUT }))
export const getKgProcessResult = (fileId) =>
  request(api.get(`/process/${fileId}/result`, { timeout: POLL_TIMEOUT }))
export const getKgTextPipelineStatus = (fileId) =>
  request(api.get(`/process/${fileId}/text-pipeline`, { timeout: POLL_TIMEOUT }))
export const getKgTextPreview = (fileId) =>
  request(api.get(`/process/${fileId}/text-preview`, { timeout: POLL_TIMEOUT }))
export const runKgTextPipeline = (fileId) =>
  request(api.post(`/process/${fileId}/text-pipeline/run`))

// ===== 图谱数据 =====
export const getKgFullGraph = () => request(api.get('/graph/full'))
export const getKgNodeGraph = (nodeId) => request(api.get(`/graph/node/${nodeId}`))
export const searchKgGraph = (q) => request(api.get('/graph/search', { params: { q } }))

// ===== 系统状态 =====
export const getKgSystemStatus = () => request(api.get('/system/status'))
export const recoverKgInterrupted = () => request(api.post('/system/recover-interrupted'))

// ===== 语音转写 =====
export const transcribeKgAudio = (file) => {
  const form = new FormData()
  form.append('file', file)
  return request(api.post('/asr/transcribe', form, { timeout: 180000 }))
}
