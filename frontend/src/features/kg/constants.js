/**
 * 知识图谱前端共享常量与展示辅助函数。
 *
 * 由 React 版本以下模块移植而来（去掉 React/TS 类型，改为纯 JS 命名导出）：
 * - constants/fileVault.ts      -> 文件库虚拟目录与文件归类判断
 * - constants/workflowSteps.ts  -> 处理流程步骤、图谱构建方法与步骤状态
 * - utils/workflowDisplay.ts    -> 处理状态展示文案
 * - TextParseBooksPanel.tsx     -> 解析模式 / 阶段名称映射
 * - FileVaultPage.tsx           -> 文件状态、文件图标等展示辅助
 */

// ===== 文件库虚拟目录 =====

/** 虚拟目录：全部资料 */
export const VAULT_ALL_KEY = 'all'
/** 虚拟目录：未分类 */
export const VAULT_UNCATEGORIZED_KEY = 'uncategorized'

export function isVaultFolderId(key) {
  return key !== VAULT_ALL_KEY && key !== VAULT_UNCATEGORIZED_KEY
}

export function folderNameById(folders, folderId) {
  if (!folderId) return '未分类'
  return folders.find((folder) => folder.id === folderId)?.name ?? '未分类'
}

export function countFilesInFolder(files, key) {
  if (key === VAULT_ALL_KEY) return files.length
  if (key === VAULT_UNCATEGORIZED_KEY) return files.filter((file) => !file.folder_id).length
  return files.filter((file) => file.folder_id === key).length
}

export function matchesVaultFolder(file, key) {
  if (key === VAULT_ALL_KEY) return true
  if (key === VAULT_UNCATEGORIZED_KEY) return !file.folder_id
  return file.folder_id === key
}

export function uploadFolderIdFromKey(key) {
  return isVaultFolderId(key) ? key : ''
}

export function vaultBreadcrumb(key, folders) {
  if (key === VAULT_ALL_KEY) return '我的文献 / 全部'
  if (key === VAULT_UNCATEGORIZED_KEY) return '我的文献 / 未分类'
  return `我的文献 / ${folderNameById(folders, key)}`
}

/** 文件库目录的装饰性图标（无对应名称时使用默认文件夹图标）。 */
export const FOLDER_ICONS = {
  历史典籍: '📜',
  考古资料: '🏺',
  学术研究: '📚',
  图像资料: '🖼️',
  空间数据: '🗺️',
  保护资料: '🛡️',
}

export function folderIcon(name) {
  return FOLDER_ICONS[name] || '📁'
}

// ===== 处理流程步骤 =====

export const WORKFLOW_STEPS = [
  { id: 'text_parse', label: '文本解析', hint: '流水线：格式检测 → 解密提取 → 段落切分' },
  { id: 'graph_build', label: '图谱构建', hint: '实体识别、关系抽取与图数据库写入，可自定义构建方法' },
  { id: 'export', label: '结果导出', hint: '导出 JSON 成果包并发布到图谱展示' },
]

export const GRAPH_BUILD_METHODS = [
  { id: 'entity_relation', label: '实体 + 关系抽取', description: '默认 NLP 管线，识别实体并抽取关系后写入图谱' },
  { id: 'entity_only', label: '仅实体识别', description: '只识别实体节点，不抽取实体间关系' },
  { id: 'rule_enhanced', label: '规则增强', description: '在 NLP 结果上补充大明宫领域词典实体' },
]

export function resolveWorkflowPhase(input = {}) {
  if (input.workflow_phase) return input.workflow_phase
  if (input.status === 'processed') return 'completed'
  if (input.export_ready) return 'export'
  if (input.text_parse_confirmed) return 'graph_build'
  if ((input.progress ?? 0) >= 33) return 'text_parse'
  return 'text_parse'
}

export function getStepVisualState(stepId, phase, processing, progress) {
  const order = ['text_parse', 'graph_build', 'export', 'completed']
  const stepIndex = order.indexOf(stepId)
  const phaseIndex = order.indexOf(phase === 'completed' ? 'completed' : phase)

  if (phase === 'completed' || phaseIndex > stepIndex) return 'done'
  if (phaseIndex < stepIndex) return 'waiting'
  if (processing) return 'active'
  if (stepId === 'text_parse' && progress >= 33) return 'active'
  if (stepId === 'graph_build' && progress >= 34 && progress < 67) return 'active'
  if (stepId === 'export' && progress >= 67 && progress < 100) return 'active'
  return progress > 0 ? 'done' : 'waiting'
}

export function stepProgressLabel(state, progress, stepId) {
  if (state === 'done') return '已完成'
  if (state === 'waiting') return '等待中'
  const bands = {
    text_parse: [0, 33],
    graph_build: [34, 66],
    export: [67, 100],
    completed: [100, 100],
  }
  const [low, high] = bands[stepId] ?? bands.text_parse
  const local = Math.max(0, Math.min(100, Math.round(((progress - low) / Math.max(high - low, 1)) * 100)))
  return `进行中 ${local}%`
}

// ===== 处理状态展示 =====

const TEXT_PARSE_DONE_MARKERS = ['文本解析完成', '原文已就绪']

export function isTextParseReady(processStatus) {
  if (!processStatus) return false
  if (processStatus.text_parse_confirmed) return true
  if ((processStatus.progress ?? 0) >= 33) return true
  const currentStep = processStatus.current_step || ''
  return TEXT_PARSE_DONE_MARKERS.some((marker) => currentStep.includes(marker))
}

/**
 * 前端展示状态。返回 `tone` 语义键，由 StatusBadge.vue 映射为具体样式，
 * 以替代 React 版本中的 Tailwind 类名字符串。
 */
export function getWorkflowDisplayStatus(status, processStatus) {
  if (status === 'processing') return { label: '处理中', tone: 'processing' }
  if (status === 'failed') return { label: '处理失败', tone: 'failed' }
  if (status === 'processed') return { label: '已完成', tone: 'success' }
  if (status === 'created') return { label: '待上传', tone: 'neutral' }

  const ps = processStatus
  if (ps?.text_parse_confirmed) {
    if (ps.export_ready || ps.workflow_phase === 'export') return { label: '待导出', tone: 'violet' }
    if ((ps.progress ?? 0) >= 67) return { label: '图谱已构建', tone: 'success' }
    return { label: '待图谱构建', tone: 'cyan' }
  }
  if (isTextParseReady(ps)) return { label: '解析完成，待确认', tone: 'success' }
  if ((ps?.progress ?? 0) > 0) return { label: '解析未完成', tone: 'warning' }
  return { label: '待处理', tone: 'warning' }
}

export function getFileWorkflowDisplay(file) {
  return getWorkflowDisplayStatus(file?.status, file?.process_status)
}

// ===== 标签映射 =====

export const PARSE_MODE_LABELS = {
  auto_detect: '自动检测',
  scanned_pdf: '扫描 PDF',
  digital_pdf: '数字 PDF',
  text: '纯文本',
  caj: 'CAJ/KDH',
}

/** 解析模式下拉顺序（与 React 版本保持一致）。 */
export const PARSE_MODE_OPTIONS = [
  { value: 'auto_detect', label: '自动检测' },
  { value: 'digital_pdf', label: '数字 PDF' },
  { value: 'scanned_pdf', label: '扫描 PDF' },
  { value: 'caj', label: 'CAJ/KDH' },
  { value: 'text', label: '纯文本' },
]

export const STAGE_LABELS = {
  import_file: '文件导入',
  format_detect: '格式检测',
  content_read: '内容读取',
  caj_decrypt: 'CAJ 解密',
  pdf_extract: 'PDF 提取',
  text_decode: '文本解码',
  text_clean: '文本清洗',
  paragraph_split: '段落切分',
  persist_result: '成果落盘',
}

export const STAGE_STATUS_LABELS = {
  pending: '等待中',
  queued: '排队中',
  running: '进行中',
  success: '已完成',
  failed: '失败',
  skipped: '已跳过',
}

/** 流水线阶段状态 -> 语义色调键（由组件的 scoped 样式映射）。 */
export const STAGE_STATUS_TONES = {
  pending: 'neutral',
  queued: 'info',
  running: 'running',
  success: 'success',
  failed: 'failed',
  skipped: 'muted',
}

export const FILE_STATUS_LABELS = {
  created: '待创建',
  uploaded: '待处理',
  processing: '处理中',
  processed: '已处理',
  failed: '处理失败',
}

export const ENTITY_TYPE_LABELS = {
  place: '地点',
  person: '人物',
  event: '事件',
  concept: '概念',
  file: '文件',
}

// ===== 文件库展示辅助 =====

export function formatSize(size) {
  const value = Number(size) || 0
  if (value >= 1024 * 1024) return `${(value / 1024 / 1024).toFixed(1)} MB`
  if (value >= 1024) return `${Math.round(value / 1024)} KB`
  return `${value} B`
}

export function statusLabel(status) {
  return FILE_STATUS_LABELS[status] || status
}

/** 文件状态 -> el-tag 的 type 值。 */
export function statusTagType(status) {
  switch (status) {
    case 'processed':
      return 'success'
    case 'processing':
      return 'primary'
    case 'uploaded':
      return 'warning'
    case 'failed':
      return 'danger'
    default:
      return 'info'
  }
}

/** 文件状态 -> 全局注册的 Element Plus 图标组件名。 */
export function statusIconName(status) {
  switch (status) {
    case 'processed':
      return 'CircleCheck'
    case 'processing':
      return 'Loading'
    case 'uploaded':
      return 'Clock'
    case 'failed':
      return 'Warning'
    default:
      return 'Clock'
  }
}

/** 文件类型 -> 图标色板变体键（由组件的 scoped 样式映射）。 */
export function fileTypeVariant(type) {
  const value = String(type || '').toLowerCase()
  if (value === 'pdf') return 'pdf'
  if (value === 'docx' || value === 'doc') return 'doc'
  if (value === 'md') return 'md'
  if (value === 'txt') return 'txt'
  if (value === 'jpg' || value === 'jpeg' || value === 'png') return 'image'
  if (value === 'zip' || value === 'rar' || value === '7z') return 'zip'
  return 'other'
}

export function fileIconLabel(type) {
  const map = { pdf: 'PDF', docx: 'W', doc: 'W', md: 'MD', txt: 'TXT', jpg: 'JPG', jpeg: 'JPG', png: 'PNG', zip: 'ZIP' }
  const value = String(type || '').toLowerCase()
  return map[value] || value.toUpperCase().slice(0, 3)
}

/** 实体类型 -> 全局注册的 Element Plus 图标组件名。 */
export function entityIconName(type) {
  const map = { place: 'Location', person: 'User', event: 'Calendar', concept: 'Collection', file: 'Document' }
  return map[type] || 'Location'
}

/** 实体类型 -> 语义色调键。 */
export function entityTone(type) {
  const map = { place: 'green', person: 'blue', event: 'violet', concept: 'orange', file: 'slate' }
  return map[type] || 'orange'
}

/** 音频转写等长任务使用的简单等待函数。 */
export function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}
