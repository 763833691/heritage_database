<template>
  <div class="kg-page">
    <header class="kg-page__bar">
      <div class="kg-page__title">
        <span class="kg-page__badge">
          <el-icon><Share /></el-icon>
        </span>
        <div>
          <h1>知识图谱</h1>
          <p>文件驱动的实体关系抽取与 3D 语义图谱探索</p>
        </div>
      </div>
      <div class="kg-page__stats">
        <div><small>实体总数</small><strong>{{ sourceGraph.nodes.length }}</strong></div>
        <div><small>关系总数</small><strong>{{ sourceGraph.links.length }}</strong></div>
        <div><small>文献簇</small><strong>{{ sourceClusters.length }}</strong></div>
        <div><small>存储模式</small><strong>{{ systemStatus.storage_mode === 'neo4j' ? 'Neo4j' : '本地' }}</strong></div>
      </div>
      <div class="kg-page__actions">
        <el-button size="small" @click="goVault">
          <el-icon><FolderOpened /></el-icon> 文件库
        </el-button>
        <el-button size="small" @click="goProcessing">
          <el-icon><Operation /></el-icon> 处理流程
        </el-button>
      </div>
    </header>

    <StatusState
      v-if="loading"
      class="kg-page__state"
      type="loading"
      title="正在加载知识图谱"
      description="正在读取图谱数据并计算 3D 布局。"
    />
    <StatusState
      v-else-if="error"
      class="kg-page__state"
      type="error"
      title="知识图谱加载失败"
      :description="error"
      action-label="重新加载"
      @action="load"
    />
    <StatusState
      v-else-if="!kgStore.graph.nodes.length"
      class="kg-page__state"
      type="empty"
      title="暂无图谱数据"
      description="请先在「文件库」上传资料，完成文本解析与图谱构建后即可在此探索 3D 语义图谱。"
      action-label="前往文件库"
      @action="goVault"
    />

    <div v-else class="kg-page__body">
      <div v-if="leftPanelOpen" class="kg-page__panel kg-page__panel--left">
        <GraphControlPanel
          :search="search"
          :active-types="activeTypes"
          :type-counts="typeCounts"
          :layout-type="layoutType"
          :visual-theme="visualTheme"
          :node-size-multiplier="nodeSizeMultiplier"
          :node-count="displayGraph?.nodes.length || 0"
          :edge-count="displayGraph?.links.length || 0"
          :loading="layoutLoading"
          :styles="sourceGraph.styles"
          :source-cluster-mode="sourceClusterMode"
          :source-clusters="sourceClusters"
          :focused-source-id="focusedSourceId"
          :presets="displayPresets"
          :active-preset-id="activePresetId"
          :save-status="saveStatus"
          :saved-summary="savedSummary"
          :saved-time-label="savedTimeLabel"
          :has-unsaved-changes="hasUnsavedChanges"
          @update:search="onSearchChange"
          @update:layout-type="setLayoutType"
          @update:visual-theme="setVisualTheme"
          @update:node-size-multiplier="setNodeSizeMultiplier"
          @update:source-cluster-mode="setSourceClusterMode"
          @update:focused-source-id="onFocusSourceChange"
          @toggle-type="toggleType"
          @apply-preset="applyDisplayPreset"
          @remove-preset="removeCustomPreset"
          @save-preset="saveCurrentAsPreset"
          @focus-search="focusSearch"
          @refresh="load"
          @collapse="setLeftPanelOpen(false)"
        />
      </div>

      <main class="kg-page__canvas">
        <div class="kg-page__canvas-bar">
          <div class="kg-page__canvas-left">
            <el-button v-if="!leftPanelOpen" size="small" title="显示控制面板" @click="setLeftPanelOpen(true)">
              <el-icon><DArrowRight /></el-icon>
            </el-button>
            <el-button v-if="graphViewMode === 'planet' && sourceClusters.length > 1" size="small" @click="handleExitOverview">
              <el-icon><Back /></el-icon> 返回文献星空
            </el-button>
          </div>
          <span class="kg-page__breadcrumb">
            {{ visualTheme === 'jspace' ? 'J-space 语义云图' : 'Jarvis 3D 语义图谱' }} /
            {{ graphViewMode === 'planet' && activePlanet ? `近景 · ${activePlanet.label}` : selectedNode?.label || '全局总览' }}
          </span>
          <div class="kg-page__canvas-right">
            <el-button v-if="!rightPanelOpen" size="small" title="显示详情面板" @click="setRightPanelOpen(true)">
              <el-icon><DArrowLeft /></el-icon>
            </el-button>
          </div>
        </div>

        <GraphScene
          class="kg-page__scene"
          data-testid="graph-canvas"
          :graph="displayGraph"
          :selected-node-id="selectedNodeId"
          :hovered-node-id="hoveredNodeId"
          :highlighted-node-ids="highlightedNodeIds"
          :highlighted-link-ids="highlightedLinkIds"
          :graph-view-mode="graphViewMode"
          :source-cluster-mode="sourceClusterMode"
          :cluster-bounds="clusterBounds"
          :camera-controller="cameraController"
          :camera-min-distance="showOverviewPlanets ? 8 : 6"
          :camera-max-distance="showOverviewPlanets ? 200 : 110"
          @select="handleSelectNode"
          @hover="setHoveredNodeId"
          @background-click="clearSelection"
          @enter-planet="handleEnterPlanet"
        />

        <footer class="kg-page__legend">
          <template v-if="sourceClusterMode === 'by_source' && sourceClusters.length > 1">
            <button
              v-for="cluster in sourceClusters.slice(0, 8)"
              :key="cluster.id"
              type="button"
              class="kg-page__legend-chip"
              :class="{ 'is-active': cluster.id === focusedSourceId && graphViewMode === 'planet' }"
              @click="handleEnterPlanet(cluster.id)"
            >
              <span :style="{ background: cluster.color }" />
              {{ cluster.label }}
            </button>
          </template>
          <template v-else>
            <span v-for="type in filterableTypes" :key="type" class="kg-page__legend-chip">
              <span :style="{ background: typeStyle(type).color }" />
              {{ typeStyle(type).label }}
            </span>
          </template>
        </footer>
      </main>

      <div v-if="rightPanelOpen" class="kg-page__panel kg-page__panel--right">
        <NodeDetailPanel
          :graph="displayGraph || sourceGraph"
          :node="detailNode"
          :related-links="relatedLinks"
          :related-evidence="relatedEvidence"
          :visual-theme="visualTheme"
          :file-name-map="fileNameMap"
          @close="clearSelection"
          @collapse="setRightPanelOpen(false)"
          @select-node="handleSelectNode"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import StatusState from '@/components/common/StatusState.vue'
import { useKgStore } from '@/stores/kg'
import { getKgSystemStatus } from '@/utils/kgApi'
import GraphScene from '@/features/kg/graph3d/GraphScene.vue'
import GraphControlPanel from '@/features/kg/graph3d/GraphControlPanel.vue'
import NodeDetailPanel from '@/features/kg/graph3d/NodeDetailPanel.vue'
import { adaptGraphData, filterRenderGraph } from '@/features/kg/graph3d/graphDataAdapter'
import { filterableTypes, getNodeTypeStyle } from '@/features/kg/graph3d/graphStyleConfig'
import {
  annotateSourceClusters,
  buildEntitySourceMap,
  computeClusterBounds,
  filterLinksForClusterMode,
  filterNodesBySource,
} from '@/features/kg/graph3d/sourceCluster'
import { useGraphFilters, loadGraphSearch, saveGraphSearch } from '@/features/kg/graph3d/useGraphFilters'
import { useGraphLayout } from '@/features/kg/graph3d/useGraphLayout'
import { useGraphSelection } from '@/features/kg/graph3d/useGraphSelection'
import { createGraphCameraController } from '@/features/kg/graph3d/useGraphCamera'

const router = useRouter()
const kgStore = useKgStore()

const loading = ref(true)
const error = ref('')
const search = ref(loadGraphSearch())
const systemStatus = ref({ storage_mode: 'local' })

const {
  activeTypes,
  layoutType,
  visualTheme,
  nodeSizeMultiplier,
  sourceClusterMode,
  focusedSourceId,
  graphViewMode,
  leftPanelOpen,
  rightPanelOpen,
  saveStatus,
  savedSummary,
  savedTimeLabel,
  hasUnsavedChanges,
  activePresetId,
  displayPresets,
  toggleType,
  setLayoutType,
  setVisualTheme,
  setNodeSizeMultiplier,
  setSourceClusterMode,
  setLeftPanelOpen,
  setRightPanelOpen,
  enterPlanet,
  exitToOverview,
  applyDisplayPreset,
  saveCurrentAsPreset,
  removeCustomPreset,
} = useGraphFilters()

const cameraController = createGraphCameraController()
let lastCameraKey = ''

const fileNameMap = computed(() => {
  const map = new Map()
  kgStore.files.forEach((file) => map.set(file.id, file.name))
  return map
})

const sourceGraph = computed(() => adaptGraphData(kgStore.graph, 'dmg_semantic_graph', visualTheme.value, fileNameMap.value))

const sourceClusters = computed(() => {
  const entitySourceMap = buildEntitySourceMap(kgStore.graph)
  return annotateSourceClusters(sourceGraph.value, entitySourceMap, fileNameMap.value).clusters
})

const typeCounts = computed(() => {
  const counts = { place: 0, person: 0, event: 0, concept: 0, file: 0 }
  sourceGraph.value.nodes.forEach((node) => {
    counts[node.type] = (counts[node.type] || 0) + 1
  })
  return counts
})

const showOverviewPlanets = computed(
  () => graphViewMode.value === 'overview' && sourceClusterMode.value === 'by_source' && sourceClusters.value.length > 1
)

const overviewGraphInput = computed(() => {
  const typeFiltered = filterRenderGraph(sourceGraph.value, activeTypes.value)
  const links = filterLinksForClusterMode(typeFiltered.links, typeFiltered.nodes, sourceClusterMode.value)
  return { ...typeFiltered, links }
})

const layoutInput = computed(() => {
  if (showOverviewPlanets.value) return { graph: overviewGraphInput.value, clusterMode: 'by_source' }
  if (graphViewMode.value === 'planet' && focusedSourceId.value) {
    const typeFiltered = filterRenderGraph(sourceGraph.value, activeTypes.value)
    const nodes = filterNodesBySource(typeFiltered.nodes, focusedSourceId.value)
    if (!nodes.length) return null
    const ids = new Set(nodes.map((node) => node.id))
    const links = typeFiltered.links.filter((link) => ids.has(link.source) && ids.has(link.target))
    return { graph: { ...typeFiltered, nodes, links }, clusterMode: 'unified' }
  }
  return { graph: overviewGraphInput.value, clusterMode: sourceClusterMode.value }
})

const activeGraph = computed(() => layoutInput.value?.graph || null)
const activeClusterMode = computed(() => layoutInput.value?.clusterMode || 'unified')

const { positionedGraph, loading: layoutLoading, ready: layoutReady } = useGraphLayout(
  activeGraph,
  layoutType,
  activeClusterMode
)

const { selectedNodeId, selectedNode, hoveredNodeId, highlightedNodeIds, highlightedLinkIds, selectNode, clearSelection, setHoveredNodeId } =
  useGraphSelection(positionedGraph)

const displayGraph = computed(() => {
  const base = positionedGraph.value
  if (!base) return null
  return { ...base, styles: { ...base.styles, nodeSizeMultiplier: nodeSizeMultiplier.value } }
})

const activePlanet = computed(() => sourceClusters.value.find((cluster) => cluster.id === focusedSourceId.value) || null)

const clusterBounds = computed(() => {
  if (!positionedGraph.value || !showOverviewPlanets.value) return []
  return computeClusterBounds(positionedGraph.value.nodes, sourceClusters.value)
})

/** 详情面板展示的节点：优先当前选中，否则回落到最相关的节点。 */
const detailNode = computed(() => {
  if (selectedNode.value) return selectedNode.value
  const nodes = positionedGraph.value?.nodes || []
  return nodes.find((node) => node.label === '大明宫') || nodes[0] || null
})

/** 当前可见节点的外接球，用于把镜头收到合适距离。 */
const graphBounds = computed(() => {
  const nodes = positionedGraph.value?.nodes || []
  if (!nodes.length) return null
  let cx = 0
  let cy = 0
  let cz = 0
  nodes.forEach((node) => {
    cx += node.x
    cy += node.y
    cz += node.z
  })
  cx /= nodes.length
  cy /= nodes.length
  cz /= nodes.length
  let maxRadius = 0
  nodes.forEach((node) => {
    maxRadius = Math.max(maxRadius, Math.hypot(node.x - cx, node.y - cy, node.z - cz))
  })
  return { x: cx, y: cy, z: cz, radius: Math.max(maxRadius, 2) }
})

const relatedLinks = computed(() => {
  if (!detailNode.value || !positionedGraph.value) return []
  return positionedGraph.value.links.filter(
    (link) => link.source === detailNode.value.id || link.target === detailNode.value.id
  )
})

const relatedEvidence = computed(() => {
  if (!detailNode.value || !positionedGraph.value) return []
  const ids = new Set(detailNode.value.evidenceIds || [])
  relatedLinks.value.forEach((link) => {
    if (link.evidenceId) ids.add(link.evidenceId)
  })
  return positionedGraph.value.evidence.filter((item) => ids.has(item.id))
})

function typeStyle(type) {
  return getNodeTypeStyle(type, sourceGraph.value.styles)
}

function onSearchChange(value) {
  search.value = value
  saveGraphSearch(value)
}

function goVault() {
  router.push('/kg/vault')
}

function goProcessing() {
  router.push('/kg/processing')
}

function focusSearch() {
  const query = search.value.trim()
  if (!query) return
  const nodes = positionedGraph.value?.nodes || []
  const target =
    nodes.find((node) => node.label.includes(query)) ||
    nodes.find((node) => node.label.toLowerCase().includes(query.toLowerCase()))
  if (!target) {
    ElMessage({ message: `未在当前图谱中找到「${query}」`, type: 'warning' })
    return
  }
  handleSelectNode(target)
}

function handleSelectNode(node) {
  if (!node) return
  selectNode(node)
  setRightPanelOpen(true)
  cameraController.focusOnNode(node)
}

function handleEnterPlanet(clusterId) {
  clearSelection()
  lastCameraKey = ''
  enterPlanet(clusterId)
}

function handleExitOverview() {
  clearSelection()
  lastCameraKey = ''
  exitToOverview()
}

function onFocusSourceChange(clusterId) {
  if (clusterId) handleEnterPlanet(clusterId)
  else handleExitOverview()
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    await Promise.all([kgStore.loadGraph(), kgStore.loadFiles({ silent: true })])
    systemStatus.value = (await getKgSystemStatus().catch(() => systemStatus.value)) || systemStatus.value
  } catch (err) {
    error.value = err?.message || '请检查知识图谱服务后重试。'
  } finally {
    loading.value = false
  }
}

/** 相机自动聚焦：布局就绪或视图模式变化时，把镜头移动到目标位置。 */
const cameraKey = computed(
  () => `${graphViewMode.value}:${focusedSourceId.value || 'all'}:${positionedGraph.value?.nodes.length || 0}`
)

watch([layoutReady, cameraKey], () => {
  if (!layoutReady.value) return
  const key = cameraKey.value
  if (key === lastCameraKey) return
  lastCameraKey = key
  if (showOverviewPlanets.value) {
    cameraController.focusOnOverview(clusterBounds.value)
    return
  }
  if (graphViewMode.value === 'planet' && positionedGraph.value?.nodes.length) {
    const bounds = clusterBounds.value.find((item) => item.id === focusedSourceId.value)
    if (bounds) {
      cameraController.focusOnCluster(bounds, bounds.radius, 'planet')
      return
    }
  }
  const bounds = clusterBounds.value.length
    ? clusterBounds.value
    : graphBounds.value
      ? [{ ...graphBounds.value, id: 'all', label: '全部', color: '#94a3b8', nodeCount: positionedGraph.value?.nodes.length || 0 }]
      : []
  cameraController.focusOnOverview(bounds)
})

onMounted(load)
</script>

<style scoped lang="scss">
.kg-page {
  display: grid;
  gap: 14px;
}

.kg-page__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.kg-page__title {
  display: flex;
  align-items: center;
  gap: 12px;

  h1 {
    margin: 0;
    font-size: 20px;
  }

  p {
    margin: 2px 0 0;
    font-size: 12px;
    color: var(--text-secondary);
  }
}

.kg-page__badge {
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  border-radius: 12px;
  color: #fff;
  font-size: 19px;
  background: var(--brand-600);
  box-shadow: 0 8px 18px rgba(37, 99, 235, 0.22);
}

.kg-page__stats {
  display: flex;
  align-items: center;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);

  > div {
    min-width: 92px;
    padding: 8px 14px;
    display: grid;
    border-right: 1px solid var(--border);

    &:last-child {
      border-right: 0;
    }
  }

  small {
    color: var(--text-tertiary);
    font-size: 10px;
  }

  strong {
    margin-top: 2px;
    font-size: 16px;
  }
}

.kg-page__actions {
  display: flex;
  gap: 8px;
}

.kg-page__state {
  min-height: 320px;
}

.kg-page__body {
  display: flex;
  height: calc(100vh - 260px);
  min-height: 520px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
  background: var(--surface);
}

.kg-page__panel {
  flex-shrink: 0;
  width: 280px;
  min-width: 0;

  &--right {
    width: 320px;
  }
}

.kg-page__canvas {
  position: relative;
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.kg-page__canvas-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
}

.kg-page__canvas-left,
.kg-page__canvas-right {
  display: flex;
  gap: 6px;
  min-width: 34px;
}

.kg-page__breadcrumb {
  font-size: 12px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kg-page__scene {
  flex: 1;
  min-height: 0;
}

.kg-page__legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 8px 14px;
  border-top: 1px solid var(--border);
  background: var(--surface);
}

.kg-page__legend-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 220px;
  padding: 2px 8px;
  border: 1px solid transparent;
  border-radius: 999px;
  background: transparent;
  font-size: 11px;
  color: var(--text-secondary);

  span {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  &.is-active {
    border-color: var(--brand-500);
    background: var(--brand-50);
    color: var(--brand-700);
  }
}

@media (max-width: 1080px) {
  .kg-page__panel {
    display: none;
  }
}
</style>
