import api from '@/utils/api'

// ===== 状态 =====
export const getAiRouterStatus = () => api.get('/ai/status').then((res) => res.data)

// ===== 模型注册表 =====
export const listAiModels = () => api.get('/ai/models').then((res) => res.data)
export const createAiModel = (payload) => api.post('/ai/models', payload).then((res) => res.data)
export const updateAiModel = (modelId, payload) =>
  api.patch(`/ai/models/${modelId}`, payload).then((res) => res.data)
export const deleteAiModel = (modelId) => api.delete(`/ai/models/${modelId}`).then((res) => res.data)
export const testAiModel = (modelId) => api.post(`/ai/models/${modelId}/test`).then((res) => res.data)
export const seedAiModels = () => api.post('/ai/models/seed').then((res) => res.data)

// ===== 任务路由 =====
export const listAiRoutes = () => api.get('/ai/routes').then((res) => res.data)
export const setAiRoute = (task, modelId) =>
  api.put(`/ai/routes/${encodeURIComponent(task)}`, { model_id: modelId }).then((res) => res.data)

export const PROVIDER_TYPES = [
  { value: 'openai_compatible', label: 'OpenAI 兼容' },
  { value: 'volcengine', label: '火山方舟' },
  { value: 'mobile_cloud', label: '移动云' },
  { value: 'koala', label: '梧桐聚合' },
  { value: 'dashscope', label: '阿里云 DashScope' },
  { value: 'custom', label: '自定义' },
]

export const CAPABILITIES = [
  { value: 'text', label: '文本 (text)' },
  { value: 'vision', label: '视觉 (vision)' },
  { value: 'multimodal', label: '多模态 (text+vision)' },
  { value: 'image', label: '图像生成' },
  { value: 'video', label: '视频生成' },
]

export const MODALITIES = ['text', 'image', 'video', 'audio', 'structured_json', 'embedding']

export function capabilityMatches(taskCapability, modelCapability) {
  if (!taskCapability || taskCapability === 'any') return true
  if (!modelCapability || modelCapability === 'any' || modelCapability === 'multimodal') return true
  return modelCapability === taskCapability
}
