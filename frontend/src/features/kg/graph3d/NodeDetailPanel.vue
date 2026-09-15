<template>
  <aside class="kg-detail">
    <header class="kg-detail__header">
      <div>
        <span class="kg-detail__eyebrow">{{ visualTheme === 'jspace' ? 'J-space 语义云图' : 'Jarvis 3D 语义图谱' }}</span>
        <h2>节点详情</h2>
      </div>
      <div class="kg-detail__header-actions">
        <el-button text size="small" title="收起面板" @click="$emit('collapse')">
          <el-icon><DArrowRight /></el-icon>
        </el-button>
        <el-button text size="small" title="关闭" @click="$emit('close')">
          <el-icon><Close /></el-icon>
        </el-button>
      </div>
    </header>

    <template v-if="displayNode">
      <section class="kg-detail__block">
        <span class="kg-detail__tag" :style="{ color: displayNode.color, borderColor: displayNode.color }">
          {{ typeLabel }}
        </span>
        <h3>{{ displayNode.label }}</h3>
        <p class="kg-detail__summary">{{ displayNode.summary || '该实体暂无描述信息。' }}</p>
      </section>

      <section class="kg-detail__block">
        <h4>关联强度</h4>
        <div class="kg-detail__metrics">
          <div><small>连接数</small><strong>{{ displayNode.metadata?.connection_count ?? 0 }}</strong></div>
          <div><small>语义价值</small><strong>{{ displayNode.metadata?.semantic_value ?? '-' }}</strong></div>
          <div><small>公众感知</small><strong>{{ displayNode.metadata?.public_perception ?? '-' }}</strong></div>
          <div><small>重要度</small><strong>{{ displayNode.score }}</strong></div>
        </div>
      </section>

      <section class="kg-detail__block">
        <h4>来源文献</h4>
        <p class="kg-detail__meta">{{ sourceLabel }}</p>
      </section>

      <section class="kg-detail__block">
        <h4>直接关联（{{ relatedLinks.length }}）</h4>
        <ul v-if="relatedLinks.length" class="kg-detail__links">
          <li v-for="link in relatedLinks.slice(0, 12)" :key="link.id">
            <button type="button" @click="goToNeighbor(link)">
              <span class="kg-detail__relation">{{ link.label }}</span>
              <span class="kg-detail__neighbor">{{ neighborLabel(link) }}</span>
            </button>
          </li>
        </ul>
        <p v-else class="kg-detail__meta">暂无直接关联。</p>
      </section>

      <section v-if="relatedEvidence.length" class="kg-detail__block">
        <h4>关系证据</h4>
        <ul class="kg-detail__evidence">
          <li v-for="item in relatedEvidence.slice(0, 4)" :key="item.id">
            <strong>{{ item.title }}</strong>
            <p>{{ item.text }}</p>
          </li>
        </ul>
      </section>
    </template>

    <p v-else class="kg-detail__empty">点击图谱节点查看实体详情。</p>
  </aside>
</template>

<script setup>
import { computed } from 'vue'
import { getNodeTypeStyle } from './graphStyleConfig'

const props = defineProps({
  graph: { type: Object, default: null },
  node: { type: Object, default: null },
  relatedLinks: { type: Array, default: () => [] },
  relatedEvidence: { type: Array, default: () => [] },
  visualTheme: { type: String, default: 'jspace' },
  fileNameMap: { type: Object, default: () => new Map() },
})

const emit = defineEmits(['close', 'collapse', 'select-node'])

const displayNode = computed(() => {
  if (props.node) return props.node
  const nodes = props.graph?.nodes || []
  return nodes.find((item) => item.label === '大明宫') || nodes[0] || null
})

const typeLabel = computed(() => {
  if (!displayNode.value) return ''
  return getNodeTypeStyle(displayNode.value.type, props.graph?.styles || {}).label
})

const sourceLabel = computed(() => {
  const source = displayNode.value?.metadata?.source_file
  if (!source) return '未标注来源文件。'
  return props.fileNameMap?.get?.(source) || String(source)
})

function neighborLabel(link) {
  const nodes = props.graph?.nodes || []
  const neighborId = link.source === displayNode.value?.id ? link.target : link.source
  return nodes.find((item) => item.id === neighborId)?.label || neighborId
}

function goToNeighbor(link) {
  const nodes = props.graph?.nodes || []
  const neighborId = link.source === displayNode.value?.id ? link.target : link.source
  const neighbor = nodes.find((item) => item.id === neighborId)
  if (neighbor) emit('select-node', neighbor)
}
</script>

<style scoped lang="scss">
.kg-detail {
  height: 100%;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  border-left: 1px solid var(--border);
  background: var(--surface);
}

.kg-detail__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;

  h2 {
    margin: 2px 0 0;
    font-size: 15px;
  }
}

.kg-detail__eyebrow {
  font-size: 10px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-tertiary);
}

.kg-detail__header-actions {
  display: flex;
  gap: 2px;
}

.kg-detail__block {
  display: grid;
  gap: 6px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border);

  &:last-of-type {
    border-bottom: 0;
  }

  h3 {
    margin: 0;
    font-size: 16px;
  }

  h4 {
    margin: 0;
    font-size: 12px;
    font-weight: 600;
    color: var(--text-secondary);
  }
}

.kg-detail__tag {
  justify-self: start;
  padding: 2px 8px;
  border: 1px solid currentColor;
  border-radius: 999px;
  font-size: 11px;
}

.kg-detail__summary {
  margin: 0;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.7;
}

.kg-detail__metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;

  > div {
    display: grid;
    padding: 8px 10px;
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    background: var(--surface-soft);
  }

  small {
    color: var(--text-tertiary);
    font-size: 10px;
  }

  strong {
    font-size: 15px;
  }
}

.kg-detail__meta {
  margin: 0;
  font-size: 12px;
  color: var(--text-tertiary);
}

.kg-detail__links,
.kg-detail__evidence {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 6px;
}

.kg-detail__links button {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface);
  font-size: 12px;
  text-align: left;
  cursor: pointer;

  &:hover {
    border-color: var(--brand-500);
    background: var(--brand-50);
  }
}

.kg-detail__relation {
  color: var(--brand-600);
  flex-shrink: 0;
}

.kg-detail__neighbor {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kg-detail__evidence li {
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface-soft);

  strong {
    font-size: 12px;
  }

  p {
    margin: 4px 0 0;
    font-size: 11px;
    color: var(--text-secondary);
    line-height: 1.6;
  }
}

.kg-detail__empty {
  font-size: 12px;
  color: var(--text-tertiary);
}
</style>
