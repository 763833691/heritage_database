import api from '@/utils/api'

// ===== 调研任务 / 事件 =====
export const listSurveyTasks = () => api.get('/survey/tasks').then((res) => res.data)
export const getSurveyTask = (taskId) => api.get(`/survey/tasks/${taskId}`).then((res) => res.data)
export const createSurveyTask = (payload) => api.post('/survey/tasks', payload).then((res) => res.data)
export const deleteSurveyTask = (taskId) => api.delete(`/survey/tasks/${taskId}`).then((res) => res.data)

export const listSurveyEvents = (taskId) =>
  api.get(`/survey/tasks/${taskId}/events`).then((res) => res.data)
export const updateSurveyEvent = (eventId, payload) =>
  api.patch(`/survey/events/${eventId}`, payload).then((res) => res.data)
export const getSurveyTimeline = (taskId) =>
  api.get(`/survey/tasks/${taskId}/timeline`).then((res) => res.data)
export const autoTitleSurveyEvents = (taskId, overwrite = false) =>
  api
    .post(`/survey/tasks/${taskId}/events/auto-title`, { overwrite }, { timeout: 180000 })
    .then((res) => res.data)

// ===== 轨迹（KML）=====
export const uploadTrackKml = (file, surveyTaskId) => {
  const form = new FormData()
  form.append('file', file)
  if (surveyTaskId) form.append('survey_task_id', String(surveyTaskId))
  return api.post('/track/upload', form, { timeout: 300000 }).then((res) => res.data)
}
export const getTrackStatus = (trackId) =>
  api.get(`/track/${trackId}/status`).then((res) => res.data)
export const getTrackDetail = (trackId) => api.get(`/track/${trackId}`).then((res) => res.data)
export const retryTrack = (trackId, forceDescribe = false) =>
  api
    .post(`/track/${trackId}/retry`, null, { params: { force_describe: forceDescribe } })
    .then((res) => res.data)
export const getTrackList = () => api.get('/track/list').then((res) => res.data)
export const trackExportUrl = (trackId, kind) => `/api/track/${trackId}/export.${kind}`

// ===== 全域田野照片聚合（照片地图 / 照片墙 / 筛选一次拉取）=====
export const getPhotosOverview = (params = {}) =>
  api.get('/track/photos/overview', { params, timeout: 120000 }).then((res) => res.data)

// ===== 轨迹语义分析（A–F 编码 / 构成 / 密度 / 点位簇）=====
export const analyzeTrack = (trackId) =>
  api.post(`/track/${trackId}/analyze`).then((res) => res.data)
export const getTrackAnalysis = (trackId) =>
  api.get(`/track/${trackId}/analysis`).then((res) => res.data)
export const downloadTrackAnalysisCsv = async (trackId) => {
  const response = await api.get(`/track/${trackId}/analysis.csv`, { responseType: 'blob', timeout: 120000 })
  return response.data
}
export const compareTracks = (ids) =>
  api.get('/track/analysis/compare', { params: { ids: ids.join(',') } }).then((res) => res.data)

// ===== 报告 =====
export const generateChapter2 = (taskId) =>
  api.post(`/survey/tasks/${taskId}/report/chapter2`, null, { timeout: 120000 }).then((res) => res.data)
export const getSurveyReport = (taskId) =>
  api.get(`/survey/tasks/${taskId}/report`).then((res) => res.data)
export const downloadReportDocx = async (taskId) => {
  const response = await api.get(`/survey/tasks/${taskId}/report.docx`, { responseType: 'blob', timeout: 120000 })
  return response.data
}

export const TRACK_STAGE_LABELS = {
  pending: '等待处理',
  parsing: '解析 KML 轨迹',
  downloading: '下载照片',
  geocoding: '逆地理编码',
  describing: '语义提取',
  done: '处理完成',
  failed: '处理失败',
}

export function saveBlob(blob, filename) {
  const url = window.URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
  window.URL.revokeObjectURL(url)
}
