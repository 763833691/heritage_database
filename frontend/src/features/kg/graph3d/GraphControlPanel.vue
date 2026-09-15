<template>
  <aside class="kg-panel">
    <header class="kg-panel__header">
      <div>
        <strong>图谱控制台</strong>
        <p class="kg-panel__summary" data-testid="graph-summary">{{ savedSummary }}</p>
      </div>
      <el-button text size="small" title="收起面板" @click="$emit('collapse')">
        <el-icon><DArrowLeft /></el-icon>
      </el-button>
    </header>

    <section class="kg-panel__block">
      <el-input
        :model-value="search"
        clearable
        placeholder="搜索实体，例如：大明宫"
        @update:model-value="$emit('update:search', $event)"
        @keyup.enter="$emit('focus-search')"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
        <template #append>
          <el-button @click="$emit('focus-search')">定位</el-button>
        </template>
      </el-input>
      <div class="kg-panel__actions">
        <el-button size="small" @click="$emit('refresh')">
          <el-icon><Refresh /></el-icon> 刷新数据
        </el-button>
        <span class="kg-panel__saved" :class="`is-${saveStatus}`">{{ saveStatusLabel }}</span>
      </div>
      <p class="kg-panel__meta" data-testid="node-count">节点 {{ nodeCount }} · 关系 {{ edgeCount }}</p>
      <p v-if="loading" class="kg-panel__meta">正在计算 3D 布局…</p>
    </section>

    <section class="kg-panel__block">
      <h3>展示方案</h3>
      <div class="kg-panel__presets">
        <button
          v-for="preset in presets"
          :key="preset.id"
          type="button"
          class="kg-preset"
          :class="{ 'is-active': preset.id === activePresetId, 'is-builtin': preset.builtIn }"
          :title="preset.description"
          @click="$emit('apply-preset', preset.id)"
        >
          <span>{{ preset.name }}</span>
          <el-icon v-if="!preset.builtIn" class="kg-preset__remove" title="删除方案" @click.stop="$emit('remove-preset', preset.id)">
            <Close />
          </el-icon>
        </button>
      </div>
      <div class="kg-panel__row">
        <el-button size="small" :disabled="!hasUnsavedChanges" @click="savePreset">保存当前为方案</el-button>
        <span class="kg-panel__meta">上次保存 {{ savedTimeLabel }}</span>
      </div>
    </section>

    <section class="kg-panel__block">
      <h3>视觉主题</h3>
      <el-radio-group :model-value="visualTheme" size="small" @update:model-value="$emit('update:visualTheme', $event)">
        <el-radio-button value="jspace">J-space 点云</el-radio-button>
        <el-radio-button value="jarvis">Jarvis 3D</el-radio-button>
      </el-radio-group>

      <h3>布局算法</h3>
      <el-select :model-value="layoutType" size="small" @update:model-value="$emit('update:layoutType', $event)">
        <el-option v-for="option in layoutOptions" :key="option.value" :label="option.label" :value="option.value" />
      </el-select>

      <h3>节点大小 <span class="kg-panel__meta">{{ nodeSizeMultiplier.toFixed(2) }}×</span></h3>
      <el-slider
        :model-value="nodeSizeMultiplier"
        :min="0.25"
        :max="2"
        :step="0.05"
        @update:model-value="$emit('update:nodeSizeMultiplier', $event)"
      />
    </section>

    <section class="kg-panel__block">
      <h3>实体类型</h3>
      <div class="kg-panel__types">
        <button
          v-for="type in filterableTypes"
          :key="type"
          type="button"
          class="kg-type"
          :class="{ 'is-active': activeTypes.has(type) }"
          @click="$emit('toggle-type', type)"
        >
          <span class="kg-type__dot" :style="{ background: typeStyle(type).color }" />
          <span>{{ typeStyle(type).label }}</span>
          <em>{{ typeCounts[type] || 0 }}</em>
        </button>
      </div>
    </section>

    <section v-if="sourceClusters.length" class="kg-panel__block">
      <h3>文献分球</h3>
      <el-radio-group :model-value="sourceClusterMode" size="small" @update:model-value="$emit('update:sourceClusterMode', $event)">
        <el-radio-button value="by_source">按文献</el-radio-button>
        <el-radio-button value="unified">统一云图</el-radio-button>
      </el-radio-group>
      <div class="kg-panel__clusters">
        <button
          v-for="cluster in sourceClusters"
          :key="cluster.id"
          type="button"
          class="kg-cluster"
          :class="{ 'is-active': cluster.id === focusedSourceId }"
          :title="cluster.label"
          @click="$emit('update:focusedSourceId', cluster.id === focusedSourceId ? null : cluster.id)"
        >
          <span class="kg-cluster__dot" :style="{ background: cluster.color }" />
          <span class="kg-cluster__label">{{ cluster.label }}</span>
          <em>{{ cluster.nodeCount }}</em>
        </button>
      </div>
    </section>
  </aside>
</template>

<script setup>
import { computed } from 'vue'
import { filterableTypes, getNodeTypeStyle } from './graphStyleConfig'

const props = defineProps({
  search: { type: String, default: '' },
  activeTypes: { type: Object, default: () => new Set() },
  typeCounts: { type: Object, default: () => ({}) },
  layoutType: { type: String, default: 'jspace_cloud' },
  visualTheme: { type: String, default: 'jspace' },
  nodeSizeMultiplier: { type: Number, default: 0.65 },
  nodeCount: { type: Number, default: 0 },
  edgeCount: { type: Number, default: 0 },
  loading: { type: Boolean, default: false },
  styles: { type: Object, default: () => ({}) },
  sourceClusterMode: { type: String, default: 'unified' },
  sourceClusters: { type: Array, default: () => [] },
  focusedSourceId: { type: String, default: null },
  presets: { type: Array, default: () => [] },
  activePresetId: { type: String, default: '' },
  saveStatus: { type: String, default: 'idle' },
  savedSummary: { type: String, default: '' },
  savedTimeLabel: { type: String, default: '' },
  hasUnsavedChanges: { type: Boolean, default: false },
})

const emit = defineEmits([
  'update:search',
  'update:layoutType',
  'update:visualTheme',
  'update:nodeSizeMultiplier',
  'update:sourceClusterMode',
  'update:focusedSourceId',
  'focus-search',
  'toggle-type',
  'apply-preset',
  'remove-preset',
  'refresh',
  'collapse',
])

const LAYOUTS = {
  jspace: [
    { value: 'jspace_cloud', label: '语义云图' },
    { value: 'cluster_3d', label: '类型聚类' },
  ],
  jarvis: [
    { value: 'semantic_orbit', label: '语义轨道' },
    { value: 'force_3d', label: '力导布局' },
    { value: 'cluster_3d', label: '类型聚类' },
  ],
}

const layoutOptions = computed(() => LAYOUTS[props.visualTheme] || LAYOUTS.jspace)

const saveStatusLabel = computed(
  () => ({ idle: '自动保存已开启', saving: '正在保存…', saved: '已自动保存', error: '保存失败' }[props.saveStatus] || '')
)

function typeStyle(type) {
  return getNodeTypeStyle(type, props.styles)
}

function savePreset() {
  const name = window.prompt('为当前展示效果命名', '我的展示方案')
  if (name === null) return
  emit('save-preset', name)
}
</script>

<style scoped lang="scss">
.kg-panel {
  height: 100%;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  border-right: 1px solid var(--border);
  background: var(--surface);
}

.kg-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.kg-panel__summary {
  margin: 4px 0 0;
  color: var(--text-tertiary);
  font-size: 11px;
}

.kg-panel__block {
  display: grid;
  gap: 8px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border);

  &:last-child {
    border-bottom: 0;
  }

  h3 {
    margin: 0;
    font-size: 12px;
    font-weight: 600;
    color: var(--text-secondary);
  }
}

.kg-panel__actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.kg-panel__saved {
  font-size: 11px;
  color: var(--text-tertiary);

  &.is-saved {
    color: var(--green-500);
  }

  &.is-error {
    color: var(--red-500);
  }
}

.kg-panel__meta {
  margin: 0;
  font-size: 11px;
  color: var(--text-tertiary);
}

.kg-panel__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.kg-panel__presets {
  display: grid;
  gap: 6px;
}

.kg-preset {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  padding: 7px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface-soft);
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.16s ease;

  &:hover {
    border-color: var(--brand-500);
    color: var(--brand-600);
  }

  &.is-active {
    border-color: var(--brand-600);
    background: var(--brand-50);
    color: var(--brand-700);
    font-weight: 600;
  }
}

.kg-preset__remove {
  opacity: 0.55;

  &:hover {
    opacity: 1;
    color: var(--red-500);
  }
}

.kg-panel__types {
  display: grid;
  gap: 6px;
}

.kg-type {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface);
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;

  &.is-active {
    border-color: var(--brand-500);
    background: var(--brand-50);
    color: var(--brand-700);
  }

  em {
    margin-left: auto;
    font-style: normal;
    color: var(--text-tertiary);
  }
}

.kg-type__dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
}

.kg-panel__clusters {
  display: grid;
  gap: 6px;
  max-height: 200px;
  overflow-y: auto;
}

.kg-cluster {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface);
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;

  &.is-active {
    border-color: var(--brand-500);
    background: var(--brand-50);
    color: var(--brand-700);
  }

  em {
    margin-left: auto;
    font-style: normal;
    color: var(--text-tertiary);
  }
}

.kg-cluster__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.kg-cluster__label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
