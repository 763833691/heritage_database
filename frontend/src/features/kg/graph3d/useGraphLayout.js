import { onScopeDispose, ref, shallowRef, watch } from 'vue'

/** 简易布局指纹，用于避免重复计算同一份图。 */
export function graphLayoutKey(graph, layoutType, clusterMode) {
  if (!graph) return ''
  const ids = graph.nodes.map((node) => node.id)
  return `${layoutType}:${clusterMode}:${ids.length}:${ids.slice(0, 8).join(',')}:${ids.slice(-4).join(',')}`
}

function fallbackPositions(graph) {
  const nodes = graph?.nodes || []
  const total = Math.max(nodes.length, 1)
  const radius = Math.max(10, Math.sqrt(total) * 4)
  return nodes.map((node, index) => {
    const angle = (index / total) * Math.PI * 2
    const lift = ((index % 5) - 2) * (radius / 12)
    return {
      id: node.id,
      x: Math.cos(angle) * radius,
      y: lift,
      z: Math.sin(angle) * radius,
    }
  })
}

function applyPositions(graph, positions) {
  const positionMap = new Map(positions.map((item) => [item.id, item]))
  if (graph.nodes.some((node) => !positionMap.has(node.id))) return null
  return {
    ...graph,
    nodes: graph.nodes.map((node) => {
      const position = positionMap.get(node.id)
      return { ...node, x: position.x, y: position.y, z: position.z }
    }),
  }
}

/**
 * 3D 布局：在 Web Worker 中执行（d3-force-3d），并按节点数/主题选择布局算法。
 * 传入的是 ref/computed(ref) 形式的入参。
 */
export function useGraphLayout(graphSource, layoutTypeSource, clusterModeSource) {
  const positionedGraph = shallowRef(null)
  const loading = ref(false)
  const ready = ref(false)

  let worker = null
  let currentKey = ''
  let currentPositions = []
  let requestSeq = 0

  function ensureWorker() {
    if (worker) return worker
    try {
      worker = new Worker(new URL('./layoutWorker.ts', import.meta.url), { type: 'module' })
    } catch (error) {
      console.warn('[kg] 3D 布局 Worker 创建失败，使用降级布局', error)
      worker = null
    }
    return worker
  }

  function finish(graph, positions) {
    currentPositions = positions
    const next = applyPositions(graph, positions)
    positionedGraph.value = next
    ready.value = Boolean(next)
    loading.value = false
  }

  function runLayout(graph, layoutType, clusterMode) {
    const key = graphLayoutKey(graph, layoutType, clusterMode)
    // 布局未变时复用缓存的坐标，但要把新的节点元信息（配色、尺寸、描述）合并进来
    if (key === currentKey && currentPositions.length) {
      const next = applyPositions(graph, currentPositions)
      if (next) {
        positionedGraph.value = next
        ready.value = true
        loading.value = false
        return
      }
    }
    currentKey = key
    currentPositions = []
    loading.value = true

    const instance = ensureWorker()
    if (!instance) {
      finish(graph, fallbackPositions(graph))
      return
    }

    const seq = (requestSeq += 1)
    instance.onmessage = (event) => {
      if (seq !== requestSeq) return
      const positions = event.data?.positions
      if (!Array.isArray(positions) || !positions.length) {
        finish(graph, fallbackPositions(graph))
        return
      }
      finish(graph, positions)
    }
    instance.onerror = () => {
      if (seq !== requestSeq) return
      finish(graph, fallbackPositions(graph))
    }

    instance.postMessage({
      nodes: graph.nodes.map((node) => ({
        id: node.id,
        type: node.type,
        label: node.label,
        sourceKey: node.metadata?.source_cluster_key ?? node.metadata?.source_file ?? undefined,
      })),
      links: graph.links.map((link) => ({
        source: link.source,
        target: link.target,
        bridge: Boolean(link.metadata?.bridge),
      })),
      layoutType,
      nodeCount: graph.nodes.length,
      visualTheme: graph.styles?.theme ?? 'jspace',
      clusterBySource: clusterMode === 'by_source',
    })
  }

  watch(
    [graphSource, layoutTypeSource, clusterModeSource],
    ([graph, layoutType, clusterMode]) => {
      if (!graph || !graph.nodes.length) {
        positionedGraph.value = graph ? { ...graph, nodes: [] } : null
        ready.value = false
        loading.value = false
        currentKey = ''
        currentPositions = []
        return
      }
      runLayout(graph, layoutType, clusterMode)
    },
    { immediate: true }
  )

  onScopeDispose(() => {
    worker?.terminate()
    worker = null
  })

  function invalidate() {
    currentKey = ''
    currentPositions = []
  }

  return { positionedGraph, loading, ready, invalidate }
}
