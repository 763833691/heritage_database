<template>
  <section class="section-card graph-panel">
    <div class="graph-panel__header">
      <div>
        <h2>图谱构建</h2>
        <p class="muted">在文本解析确认后，选择实体识别与关系抽取策略，生成知识图谱数据。</p>
      </div>
      <el-button type="primary" :disabled="!confirmed || running || graphBuilding" @click="handleRun">
        <el-icon :class="{ 'is-spin': running || graphBuilding }">
          <component :is="running || graphBuilding ? 'Loading' : 'VideoPlay'" />
        </el-icon>
        {{ graphBuilding ? '构建中' : '开始图谱构建' }}
      </el-button>
    </div>

    <el-alert
      v-if="!confirmed"
      class="graph-panel__alert"
      type="warning"
      :closable="false"
      title="请先在「文本解析」步骤检查预览结果，确认无误后再进入图谱构建。"
    />

    <el-alert v-if="error" class="graph-panel__alert" type="error" :closable="false" :title="error" />

    <div class="graph-panel__label">
      <el-icon><Setting /></el-icon>
      构建方法
    </div>

    <el-radio-group v-model="method" class="graph-panel__methods">
      <label
        v-for="item in GRAPH_BUILD_METHODS"
        :key="item.id"
        class="method-card"
        :class="{ 'method-card--active': method === item.id }"
      >
        <el-radio :value="item.id">
          <span class="method-card__title">{{ item.label }}</span>
        </el-radio>
        <span class="method-card__description">{{ item.description }}</span>
      </label>
    </el-radio-group>

    <el-alert
      v-if="hasResult"
      class="graph-panel__alert"
      type="success"
      :closable="false"
      :title="`已生成 ${processResult?.entities?.length ?? 0} 个实体、${processResult?.relations?.length ?? 0} 条关系，可进入结果导出。`"
    />
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { runKgGraphBuild } from '@/utils/kgApi'
import { GRAPH_BUILD_METHODS } from '@/features/kg/constants'

const props = defineProps({
  fileId: { type: String, required: true },
  processStatus: { type: Object, default: null },
  processResult: { type: Object, default: null },
  processing: { type: Boolean, default: false },
})
const emit = defineEmits(['refresh'])

const method = ref(props.processStatus?.graph_build_method || 'entity_relation')
const running = ref(false)
const error = ref('')

const confirmed = computed(() => Boolean(props.processStatus?.text_parse_confirmed))
const hasResult = computed(() => Boolean(props.processResult?.entities?.length))
const graphBuilding = computed(() => props.processing && props.processStatus?.workflow_phase === 'graph_build')

async function handleRun() {
  running.value = true
  error.value = ''
  try {
    await runKgGraphBuild(props.fileId, method.value)
    emit('refresh')
  } catch (err) {
    error.value = err?.message || '启动图谱构建失败'
  } finally {
    running.value = false
  }
}
</script>

<style scoped lang="scss">
.graph-panel {
  padding: 22px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--surface);
  box-shadow: var(--shadow-soft);
}

.graph-panel__header {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.graph-panel__header h2 {
  margin: 0;
  font-size: 16px;
}

.graph-panel__header p {
  margin: 6px 0 0;
  font-size: 13px;
}

.graph-panel__alert {
  margin-bottom: 14px;
}

.graph-panel__label {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 12px;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 600;
}

.graph-panel__methods {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
  width: 100%;
  align-items: stretch;
}

.method-card {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--surface);
  cursor: pointer;
  transition: border-color .2s ease, background .2s ease;
}

.method-card--active {
  border-color: var(--brand-100);
  background: var(--brand-50);
}

.method-card__title {
  font-size: 13px;
  font-weight: 650;
  color: var(--text-primary);
}

.method-card__description {
  padding-left: 22px;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.65;
}

.is-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
