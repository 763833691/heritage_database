<template>
  <section class="section-card export-panel">
    <div class="export-panel__header">
      <div>
        <h2>结果导出</h2>
        <p class="muted">导出知识图谱 JSON 成果包，并发布到「图谱展示」供浏览与检索。</p>
      </div>
      <div class="toolbar-row">
        <el-button type="primary" :disabled="!ready || running || exporting" @click="handleExport">
          <el-icon :class="{ 'is-spin': running || exporting }">
            <component :is="running || exporting ? 'Loading' : 'Download'" />
          </el-icon>
          {{ exporting ? '导出中' : '导出并发布' }}
        </el-button>
        <el-button :disabled="!completed && !ready" @click="openGraph">
          <el-icon><Share /></el-icon>
          打开图谱展示
        </el-button>
      </div>
    </div>

    <el-alert
      v-if="!ready"
      class="export-panel__alert"
      type="warning"
      :closable="false"
      title="请先完成图谱构建，再导出成果文件。"
    />

    <el-alert v-if="error" class="export-panel__alert" type="error" :closable="false" :title="error" />

    <div class="export-panel__grid">
      <div class="export-card">
        <div class="export-card__title">文件导出</div>
        <p class="export-card__text">
          将生成 <strong>knowledge_graph.json</strong>，包含实体、关系与图结构数据，便于归档与二次处理。
        </p>
        <div class="export-card__meta">来源文献：{{ fileName || '—' }}</div>
      </div>
      <div class="export-card">
        <div class="export-card__title">
          <el-icon><Link /></el-icon>
          图谱展示
        </div>
        <p class="export-card__text">
          导出完成后，数据会写入图数据库并出现在「图谱展示」页面，可进行 3D 浏览与检索。
        </p>
        <div v-if="completed" class="export-card__meta export-card__meta--done">已发布到图谱展示</div>
        <div v-else class="export-card__meta">等待导出发布</div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { runKgExport } from '@/utils/kgApi'

const props = defineProps({
  fileId: { type: String, required: true },
  fileName: { type: String, default: '' },
  processStatus: { type: Object, default: null },
  processResult: { type: Object, default: null },
  processing: { type: Boolean, default: false },
})
const emit = defineEmits(['refresh'])

const router = useRouter()
const running = ref(false)
const error = ref('')

const ready = computed(() => Boolean(props.processResult?.entities?.length))
const exporting = computed(() => props.processing && props.processStatus?.workflow_phase === 'export')
const completed = computed(
  () => props.processStatus?.workflow_phase === 'completed' || props.processStatus?.status === 'processed',
)

async function handleExport() {
  running.value = true
  error.value = ''
  try {
    await runKgExport(props.fileId)
    emit('refresh')
  } catch (err) {
    error.value = err?.message || '导出失败'
  } finally {
    running.value = false
  }
}

function openGraph() {
  router.push('/knowledge-graph')
}
</script>

<style scoped lang="scss">
.export-panel {
  padding: 22px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--surface);
  box-shadow: var(--shadow-soft);
}

.export-panel__header {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.export-panel__header h2 {
  margin: 0;
  font-size: 16px;
}

.export-panel__header p {
  margin: 6px 0 0;
  font-size: 13px;
}

.export-panel__alert {
  margin-bottom: 14px;
}

.export-panel__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 12px;
}

.export-card {
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--surface-soft);
}

.export-card__title {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 650;
}

.export-card__text {
  margin: 8px 0 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.7;
}

.export-card__meta {
  margin-top: 10px;
  color: var(--text-tertiary);
  font-size: 11px;
}

.export-card__meta--done {
  color: #15803d;
  font-weight: 600;
}

.is-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
