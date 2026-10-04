import api from '@/utils/api'

// ===== 标注任务 =====
export const importAnnotationTask = (payload) =>
  api.post('/annotate/tasks/import', payload).then((res) => res.data)
export const listAnnotationTasks = () => api.get('/annotate/tasks').then((res) => res.data)

// ===== 盲标：取题 / 照片元信息 / 提交编码 =====
export const getNextAnnotationItem = (taskId, coder) =>
  api.get(`/annotate/tasks/${taskId}/next`, { params: { coder } }).then((res) => res.data)
export const getAnnotationPhotoMeta = (itemId) =>
  api.get(`/annotate/items/${itemId}/photo-meta`).then((res) => res.data)
export const submitAnnotationCode = (itemId, payload) =>
  api.post(`/annotate/items/${itemId}/code`, payload).then((res) => res.data)

// ===== 信度结果 / 导出 =====
export const getAnnotationResults = (taskId) =>
  api.get(`/annotate/tasks/${taskId}/results`).then((res) => res.data)
export const annotationExportUrl = (taskId) => `/api/annotate/tasks/${taskId}/export`

export const CATEGORY_NAMES = {
  A: '遗址本体展示',
  B: '复原建筑与覆罩',
  C: '阐释解说设施',
  D: '数字互动展示',
  E: '运营与消费场景',
  F: '景观环境与城市关系',
  G: '其他',
}

export const CATEGORY_DEFINITIONS = {
  A: '遗址原生遗存本体及直接保护设施（夯土、基址、封土、柱础、遗址剖面、出土遗物、保护栈道围栏）',
  B: '覆罩保护建筑与形象复原建筑（保护棚/罩、城楼、阙楼、仿古复原建筑）',
  C: '非数字阐释媒介（展板、说明牌、沙盘模型、壁画浮雕、展厅展陈、导览标识）',
  D: '数字互动沉浸设施（互动屏、电子屏、VR/AR、全息、数字展厅）',
  E: '运营商业服务设施（售票、文创店、售卖机、演艺、游客中心）',
  F: '景观空间与环境（广场、绿地、步道、湿地、水面、远眺天际线）',
  G: '无法归入以上六类',
}
