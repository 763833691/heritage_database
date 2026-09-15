import type { EntityType } from "../types";
import { filterableTypes, NODE_SIZE_MULTIPLIER_DEFAULT } from "./graphStyleConfig";
import type { LayoutType, VisualTheme } from "./graphTypes";
import type { SourceClusterMode } from "./sourceCluster";

export const GRAPH_DISPLAY_PREFS_KEY = "kg-graph-display-prefs";
export const GRAPH_SESSION_PREFS_KEY = "kg-graph-session-prefs";
/** @deprecated 旧版合并存储键，读取后自动迁移 */
const LEGACY_GRAPH_PREFS_KEY = "kg-graph-prefs";

export interface GraphDisplayPreset {
  id: string;
  name: string;
  description: string;
  builtIn: boolean;
  visualTheme: VisualTheme;
  layoutType: LayoutType;
  nodeSizeMultiplier: number;
  sourceClusterMode: SourceClusterMode;
  activeTypes: EntityType[];
  savedAt: string;
}

export interface GraphDisplayPrefsStore {
  version: 1;
  activePresetId: string;
  lastSavedAt: string | null;
  liveSnapshot: GraphDisplaySnapshot;
  presets: GraphDisplayPreset[];
}

export interface GraphSessionPrefs {
  leftPanelOpen: boolean;
  rightPanelOpen: boolean;
  focusedSourceId: string | null;
  graphViewMode: "overview" | "planet";
}

export interface GraphDisplaySnapshot {
  visualTheme: VisualTheme;
  layoutType: LayoutType;
  nodeSizeMultiplier: number;
  sourceClusterMode: SourceClusterMode;
  activeTypes: EntityType[];
}

const nowIso = () => new Date().toISOString();

export const BUILTIN_PRESET_IDS = {
  jspaceOverview: "builtin-jspace-overview",
  jarvisOrbit: "builtin-jarvis-orbit",
} as const;

function createBuiltinPresets(): GraphDisplayPreset[] {
  const savedAt = "2026-07-10T00:00:00.000Z";
  return [
    {
      id: BUILTIN_PRESET_IDS.jspaceOverview,
      name: "文献点云总览",
      description: "J-space 白底点云 · 按文献分簇 · 适合多本书宏观浏览",
      builtIn: true,
      visualTheme: "jspace",
      layoutType: "jspace_cloud",
      nodeSizeMultiplier: NODE_SIZE_MULTIPLIER_DEFAULT,
      sourceClusterMode: "by_source",
      activeTypes: [...filterableTypes],
      savedAt,
    },
    {
      id: BUILTIN_PRESET_IDS.jarvisOrbit,
      name: "Jarvis 3D 轨道",
      description: "暗色 3D 语义轨道 · 按文献分球 · 适合近景探索",
      builtIn: true,
      visualTheme: "jarvis",
      layoutType: "semantic_orbit",
      nodeSizeMultiplier: NODE_SIZE_MULTIPLIER_DEFAULT,
      sourceClusterMode: "by_source",
      activeTypes: [...filterableTypes],
      savedAt,
    },
  ];
}

export function createDefaultDisplayStore(): GraphDisplayPrefsStore {
  const defaultPreset = createBuiltinPresets()[0];
  return {
    version: 1,
    activePresetId: BUILTIN_PRESET_IDS.jspaceOverview,
    lastSavedAt: null,
    liveSnapshot: snapshotFromPreset(defaultPreset),
    presets: createBuiltinPresets(),
  };
}

function normalizePreset(preset: GraphDisplayPreset): GraphDisplayPreset {
  return {
    ...preset,
    activeTypes: preset.activeTypes?.length ? preset.activeTypes : [...filterableTypes],
  };
}

function mergeBuiltinPresets(presets: GraphDisplayPreset[]): GraphDisplayPreset[] {
  const builtins = createBuiltinPresets();
  const custom = presets.filter((preset) => !preset.builtIn);
  const mergedBuiltins = builtins.map((builtin) => {
    const existing = presets.find((preset) => preset.id === builtin.id);
    return existing?.builtIn ? normalizePreset({ ...builtin, ...existing, builtIn: true }) : builtin;
  });
  return [...mergedBuiltins, ...custom.map(normalizePreset)];
}

function migrateLegacyPrefs(): Partial<GraphDisplayPrefsStore> | null {
  try {
    const raw = localStorage.getItem(LEGACY_GRAPH_PREFS_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    return {
      activePresetId: BUILTIN_PRESET_IDS.jspaceOverview,
      lastSavedAt: typeof parsed.lastSavedAt === "string" ? parsed.lastSavedAt : nowIso(),
      presets: mergeBuiltinPresets([
        ...createBuiltinPresets(),
        {
          id: "legacy-user-prefs",
          name: "上次浏览配置",
          description: "从旧版本偏好自动迁移",
          builtIn: false,
          visualTheme: (parsed.visualTheme as VisualTheme) ?? "jspace",
          layoutType: (parsed.layoutType as LayoutType) ?? "jspace_cloud",
          nodeSizeMultiplier: Number(parsed.nodeSizeMultiplier ?? NODE_SIZE_MULTIPLIER_DEFAULT),
          sourceClusterMode: (parsed.sourceClusterMode as SourceClusterMode) ?? "by_source",
          activeTypes: Array.isArray(parsed.activeTypes) ? (parsed.activeTypes as EntityType[]) : [...filterableTypes],
          savedAt: nowIso(),
        },
      ]),
    };
  } catch {
    return null;
  }
}

export function loadDisplayPrefsStore(): GraphDisplayPrefsStore {
  try {
    const raw = localStorage.getItem(GRAPH_DISPLAY_PREFS_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as GraphDisplayPrefsStore;
      const presets = mergeBuiltinPresets(parsed.presets ?? []);
      const activePresetId = presets.some((preset) => preset.id === parsed.activePresetId)
        ? parsed.activePresetId
        : BUILTIN_PRESET_IDS.jspaceOverview;
      return {
        version: 1,
        activePresetId,
        lastSavedAt: parsed.lastSavedAt ?? null,
        liveSnapshot: parsed.liveSnapshot ?? snapshotFromPreset(getActivePreset({ ...parsed, presets, activePresetId } as GraphDisplayPrefsStore)),
        presets,
      };
    }
  } catch {
    // fall through
  }

  const migrated = migrateLegacyPrefs();
  if (migrated) {
    const store: GraphDisplayPrefsStore = {
      version: 1,
      activePresetId: migrated.activePresetId ?? BUILTIN_PRESET_IDS.jspaceOverview,
      lastSavedAt: migrated.lastSavedAt ?? null,
      liveSnapshot: snapshotFromPreset(
        migrated.presets?.find((preset) => preset.id === (migrated.activePresetId ?? BUILTIN_PRESET_IDS.jspaceOverview)) ??
          createBuiltinPresets()[0],
      ),
      presets: migrated.presets ?? createBuiltinPresets(),
    };
    saveDisplayPrefsStore(store);
    return store;
  }

  return createDefaultDisplayStore();
}

export function saveDisplayPrefsStore(store: GraphDisplayPrefsStore): void {
  localStorage.setItem(GRAPH_DISPLAY_PREFS_KEY, JSON.stringify(store));
}

export function loadSessionPrefs(): Partial<GraphSessionPrefs> {
  try {
    const raw = localStorage.getItem(GRAPH_SESSION_PREFS_KEY);
    if (!raw) {
      const legacy = localStorage.getItem(LEGACY_GRAPH_PREFS_KEY);
      if (!legacy) return {};
      const parsed = JSON.parse(legacy) as Partial<GraphSessionPrefs>;
      return {
        leftPanelOpen: parsed.leftPanelOpen,
        rightPanelOpen: parsed.rightPanelOpen,
        focusedSourceId: parsed.focusedSourceId ?? null,
        graphViewMode: parsed.graphViewMode ?? (parsed.focusedSourceId ? "planet" : "overview"),
      };
    }
    return JSON.parse(raw) as Partial<GraphSessionPrefs>;
  } catch {
    return {};
  }
}

export function saveSessionPrefs(prefs: GraphSessionPrefs): void {
  localStorage.setItem(GRAPH_SESSION_PREFS_KEY, JSON.stringify(prefs));
}

export function getActivePreset(store: GraphDisplayPrefsStore): GraphDisplayPreset {
  return (
    store.presets.find((preset) => preset.id === store.activePresetId) ??
    store.presets.find((preset) => preset.id === BUILTIN_PRESET_IDS.jspaceOverview) ??
    createBuiltinPresets()[0]
  );
}

export function snapshotFromPreset(preset: GraphDisplayPreset): GraphDisplaySnapshot {
  return {
    visualTheme: preset.visualTheme,
    layoutType: preset.layoutType,
    nodeSizeMultiplier: preset.nodeSizeMultiplier,
    sourceClusterMode: preset.sourceClusterMode,
    activeTypes: [...preset.activeTypes],
  };
}

export function snapshotFromState(state: GraphDisplaySnapshot): GraphDisplaySnapshot {
  return {
    visualTheme: state.visualTheme,
    layoutType: state.layoutType,
    nodeSizeMultiplier: state.nodeSizeMultiplier,
    sourceClusterMode: state.sourceClusterMode,
    activeTypes: [...state.activeTypes],
  };
}

export function isSameSnapshot(a: GraphDisplaySnapshot, b: GraphDisplaySnapshot): boolean {
  return (
    a.visualTheme === b.visualTheme &&
    a.layoutType === b.layoutType &&
    a.nodeSizeMultiplier === b.nodeSizeMultiplier &&
    a.sourceClusterMode === b.sourceClusterMode &&
    a.activeTypes.length === b.activeTypes.length &&
    a.activeTypes.every((type) => b.activeTypes.includes(type))
  );
}

export function formatPresetSummary(preset: GraphDisplayPreset): string {
  const theme = preset.visualTheme === "jspace" ? "J-space" : "Jarvis 3D";
  const layoutLabels: Record<LayoutType, string> = {
    jspace_cloud: "语义云图",
    semantic_orbit: "语义轨道",
    cluster_3d: "类型聚类",
    force_3d: "力导布局",
  };
  const cluster = preset.sourceClusterMode === "by_source" ? "按文献分球" : "统一云图";
  return `${theme} · ${layoutLabels[preset.layoutType]} · ${cluster}`;
}

export function formatSavedTime(iso: string | null): string {
  if (!iso) return "尚未保存";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "尚未保存";
  return date.toLocaleString("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function upsertCustomPreset(
  store: GraphDisplayPrefsStore,
  snapshot: GraphDisplaySnapshot,
  name: string,
): GraphDisplayPrefsStore {
  const savedAt = nowIso();
  const customPresets = store.presets.filter((preset) => !preset.builtIn);
  const existing = customPresets.find((preset) => preset.name === name.trim());
  const nextPreset: GraphDisplayPreset = {
    id: existing?.id ?? `custom-${Date.now()}`,
    name: name.trim() || "我的展示方案",
    description: "用户自定义展示效果",
    builtIn: false,
    ...snapshot,
    savedAt,
  };

  const presets = mergeBuiltinPresets([
    ...store.presets.filter((preset) => preset.builtIn),
    ...customPresets.filter((preset) => preset.id !== nextPreset.id),
    nextPreset,
  ]).slice(0, 8);

  return {
    ...store,
    activePresetId: nextPreset.id,
    lastSavedAt: savedAt,
    presets,
  };
}

export function applyPresetToStore(store: GraphDisplayPrefsStore, presetId: string): GraphDisplayPrefsStore {
  if (!store.presets.some((preset) => preset.id === presetId)) return store;
  return { ...store, activePresetId: presetId };
}

export function deleteCustomPreset(store: GraphDisplayPrefsStore, presetId: string): GraphDisplayPrefsStore {
  const target = store.presets.find((preset) => preset.id === presetId);
  if (!target || target.builtIn) return store;
  const presets = store.presets.filter((preset) => preset.id !== presetId);
  const activePresetId =
    store.activePresetId === presetId ? BUILTIN_PRESET_IDS.jspaceOverview : store.activePresetId;
  return { ...store, presets, activePresetId };
}

export function touchDisplayStore(
  store: GraphDisplayPrefsStore,
  snapshot: GraphDisplaySnapshot,
): GraphDisplayPrefsStore {
  const savedAt = nowIso();
  return {
    ...store,
    liveSnapshot: snapshotFromState(snapshot),
    lastSavedAt: savedAt,
  };
}
