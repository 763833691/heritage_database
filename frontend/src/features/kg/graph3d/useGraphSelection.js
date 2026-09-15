import { computed, ref } from 'vue'
import { getFirstDegreeHighlight } from './graphDataAdapter'

/** 选中/悬停节点以及一度关联高亮集合。 */
export function useGraphSelection(positionedGraph) {
  const selectedNodeId = ref(null)
  const hoveredNodeId = ref(null)

  const selectedNode = computed(() => {
    const graph = positionedGraph.value
    if (!graph || !selectedNodeId.value) return null
    return graph.nodes.find((node) => node.id === selectedNodeId.value) || null
  })

  const highlight = computed(() =>
    getFirstDegreeHighlight(positionedGraph.value || { nodes: [], links: [] }, selectedNodeId.value)
  )
  const highlightedNodeIds = computed(() => highlight.value.nodeIds)
  const highlightedLinkIds = computed(() => highlight.value.linkIds)

  function selectNode(node) {
    selectedNodeId.value = typeof node === 'string' ? node : node?.id ?? null
  }

  function clearSelection() {
    selectedNodeId.value = null
  }

  function setHoveredNodeId(nodeId) {
    hoveredNodeId.value = nodeId ?? null
  }

  return {
    selectedNodeId,
    selectedNode,
    hoveredNodeId,
    highlightedNodeIds,
    highlightedLinkIds,
    selectNode,
    clearSelection,
    setHoveredNodeId,
  }
}
