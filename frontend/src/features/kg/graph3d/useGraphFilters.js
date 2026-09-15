import { computed, ref, watch } from 'vue'
import { filterableTypes, NODE_SIZE_MULTIPLIER_DEFAULT, NODE_SIZE_MULTIPLIER_MAX, NODE_SIZE_MULTIPLIER_MIN } from './graphStyleConfig'
import {
  applyPresetToStore,
  deleteCustomPreset,
  formatPresetSummary,
  formatSavedTime,
  getActivePreset,
  isSameSnapshot,
  loadDisplayPrefsStore,
  loadSessionPrefs,
  saveDisplayPrefsStore,
  saveSessionPrefs,
  snapshotFromPreset,
  snapshotFromState,
  touchDisplayStore,
  upsertCustomPreset,
} from './graphDisplayPrefs'

const GRAPH_SEARCH_KEY = 'kg-graph-search'

export function loadGraphSearch() {
  try {
    return localStorage.getItem(GRAPH_SEARCH_KEY) || '大明宫'
  } catch {
    return '大明宫'
  }
}

export function saveGraphSearch(value) {
  try {
    localStorage.setItem(GRAPH_SEARCH_KEY, value ?? '')
  } catch {
    // 忽略隐私模式下的写入失败
  }
}

const THEME_ALLOWED_LAYOUTS = {
  jspace: ['jspace_cloud', 'cluster_3d'],
  jarvis: ['semantic_orbit', 'force_3d', 'cluster_3d'],
}

function coerceLayout(theme, layoutType) {
  const allowed = THEME_ALLOWED_LAYOUTS[theme] || []
  return allowed.includes(layoutType) ? layoutType : allowed[0]
}

/** 图谱展示的集中状态：筛选、主题、布局、面板、文献分球与展示方案。 */
export function useGraphFilters() {
  const store = ref(loadDisplayPrefsStore())
  const session = loadSessionPrefs()
  const active = getActivePreset(store.value)

  const activeTypes = ref(new Set(active.activeTypes?.length ? active.activeTypes : filterableTypes))
  const layoutType = ref(active.layoutType)
  const visualTheme = ref(active.visualTheme)
  const nodeSizeMultiplier = ref(active.nodeSizeMultiplier ?? NODE_SIZE_MULTIPLIER_DEFAULT)
  const sourceClusterMode = ref(active.sourceClusterMode || 'by_source')
  const focusedSourceId = ref(session.focusedSourceId ?? null)
  const graphViewMode = ref(session.focusedSourceId ? 'planet' : 'overview')
  const leftPanelOpen = ref(session.leftPanelOpen !== false)
  const rightPanelOpen = ref(session.rightPanelOpen !== false)

  const saveStatus = ref('idle')
  const lastSavedAt = ref(store.value.lastSavedAt)
  let saveTimer = null

  const currentSnapshot = computed(() =>
    snapshotFromState({
      visualTheme: visualTheme.value,
      layoutType: layoutType.value,
      nodeSizeMultiplier: nodeSizeMultiplier.value,
      sourceClusterMode: sourceClusterMode.value,
      activeTypes: [...activeTypes.value],
    })
  )

  const activePreset = computed(() => getActivePreset(store.value))
  const activePresetId = computed(() => store.value.activePresetId)
  const displayPresets = computed(() => store.value.presets)
  const hasUnsavedChanges = computed(() => !isSameSnapshot(currentSnapshot.value, store.value.liveSnapshot))
  const savedSummary = computed(() => formatPresetSummary(activePreset.value))
  const savedTimeLabel = computed(() => formatSavedTime(lastSavedAt.value))

  watch(
    currentSnapshot,
    (snapshot) => {
      const next = touchDisplayStore(store.value, snapshot)
      store.value = next
      lastSavedAt.value = next.lastSavedAt
      saveDisplayPrefsStore(next)
      saveStatus.value = 'saved'
      if (saveTimer) clearTimeout(saveTimer)
      saveTimer = setTimeout(() => {
        saveStatus.value = 'idle'
      }, 2400)
    },
    { deep: true }
  )

  watch([leftPanelOpen, rightPanelOpen, focusedSourceId, graphViewMode], () => {
    saveSessionPrefs({
      leftPanelOpen: leftPanelOpen.value,
      rightPanelOpen: rightPanelOpen.value,
      focusedSourceId: focusedSourceId.value,
      graphViewMode: graphViewMode.value,
    })
  })

  function toggleType(type) {
    const next = new Set(activeTypes.value)
    if (next.has(type)) next.delete(type)
    else next.add(type)
    if (!next.size) next.add(type)
    activeTypes.value = next
  }

  function setLayoutType(value) {
    layoutType.value = value
  }

  function setVisualTheme(value) {
    visualTheme.value = value
    layoutType.value = coerceLayout(value, layoutType.value)
  }

  function setNodeSizeMultiplier(value) {
    nodeSizeMultiplier.value = Math.min(NODE_SIZE_MULTIPLIER_MAX, Math.max(NODE_SIZE_MULTIPLIER_MIN, value))
  }

  function setSourceClusterMode(value) {
    sourceClusterMode.value = value
    if (value === 'unified') exitToOverview()
  }

  function enterPlanet(sourceId) {
    focusedSourceId.value = sourceId
    graphViewMode.value = 'planet'
  }

  function exitToOverview() {
    focusedSourceId.value = null
    graphViewMode.value = 'overview'
  }

  function applyDisplayPreset(presetId) {
    const nextStore = applyPresetToStore(store.value, presetId)
    if (nextStore === store.value) return
    store.value = nextStore
    const preset = getActivePreset(nextStore)
    visualTheme.value = preset.visualTheme
    layoutType.value = preset.layoutType
    nodeSizeMultiplier.value = preset.nodeSizeMultiplier
    sourceClusterMode.value = preset.sourceClusterMode
    activeTypes.value = new Set(preset.activeTypes)
    saveDisplayPrefsStore(touchDisplayStore(nextStore, snapshotFromPreset(preset)))
  }

  function saveCurrentAsPreset(name) {
    store.value = upsertCustomPreset(store.value, currentSnapshot.value, name)
    lastSavedAt.value = store.value.lastSavedAt
    saveDisplayPrefsStore(store.value)
  }

  function removeCustomPreset(presetId) {
    store.value = deleteCustomPreset(store.value, presetId)
    saveDisplayPrefsStore(store.value)
  }

  return {
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
    currentSnapshot,
    activePreset,
    activePresetId,
    displayPresets,
    toggleType,
    setLayoutType,
    setVisualTheme,
    setNodeSizeMultiplier,
    setSourceClusterMode,
    setLeftPanelOpen: (value) => {
      leftPanelOpen.value = value
    },
    setRightPanelOpen: (value) => {
      rightPanelOpen.value = value
    },
    enterPlanet,
    exitToOverview,
    applyDisplayPreset,
    saveCurrentAsPreset,
    removeCustomPreset,
  }
}
