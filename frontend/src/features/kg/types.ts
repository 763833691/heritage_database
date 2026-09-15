export type EntityType = "place" | "person" | "event" | "concept" | "file";
export type FileStatus = "created" | "uploaded" | "processing" | "processed" | "failed";

export interface Entity {
  id: string;
  name: string;
  type: EntityType;
  description?: string;
  source_file?: string | null;
  confidence?: number;
  mention_count?: number;
}

export interface Relation {
  source: string;
  relation: string;
  target: string;
  weight: number;
}

export interface GraphNode {
  data: {
    id: string;
    label: string;
    name: string;
    type: EntityType;
    description?: string;
    source_file?: string | null;
  };
}

export interface GraphEdge {
  data: {
    id: string;
    source: string;
    target: string;
    label: string;
    relation: string;
    weight: number;
    bridge?: boolean;
  };
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export type WorkflowPhase = "text_parse" | "graph_build" | "export" | "completed";
export type GraphBuildMethod = "entity_relation" | "entity_only" | "rule_enhanced";

export interface ProcessStatus {
  progress: number;
  status: FileStatus;
  current_step: string;
  workflow_phase?: WorkflowPhase;
  text_parse_confirmed?: boolean;
  graph_build_method?: GraphBuildMethod;
  export_ready?: boolean;
  logs: string[];
}

export type TextParseStageStatus = "pending" | "queued" | "running" | "success" | "failed" | "skipped";

export interface TextParseStage {
  stage: string;
  label: string;
  hint: string;
  status: TextParseStageStatus;
  progress: number;
  message: string;
  can_run: boolean;
  blocked_reason?: string | null;
  is_rerunnable: boolean;
  action_label: string;
}

export interface TextParseArtifact {
  file_type: string;
  name: string;
  path: string;
}

export interface TextParsePipelineStatus {
  file_id: string;
  current_stage?: string | null;
  overall_progress: number;
  parse_mode: string;
  parse_mode_label: string;
  char_count: number;
  paragraph_count: number;
  page_count: number;
  block_count?: number;
  pipeline_type?: string;
  stages: TextParseStage[];
  logs: string[];
  artifacts: TextParseArtifact[];
  status: string;
}

export interface TextParsePreview {
  text_preview: string;
  char_count: number;
  paragraph_count: number;
  page_count: number;
  paragraphs: string[];
  artifacts: TextParseArtifact[];
  parse_mode: string;
  parse_mode_label: string;
}

export interface ProcessResult {
  entities: Entity[];
  relations: Relation[];
  graph: GraphData;
}

export interface FileItem {
  id: string;
  name: string;
  type: string;
  status: FileStatus;
  size: number;
  source: string;
  upload_time: string;
  folder_id?: string;
  tags: string[];
  summary: string;
  content_path?: string | null;
  doc_code?: string;
  discipline?: string;
  parse_mode?: string;
  page_count?: number;
  block_count?: number;
  pipeline_type?: string;
  process_status: ProcessStatus;
  process_result?: ProcessResult | null;
}

export interface SettingsModelGroup {
  base_url: string;
  model: string;
  api_key_hint: string;
  has_api_key: boolean;
  disable_proxy?: boolean;
}

export interface MineruSelectOption {
  value: string;
  label: string;
  included_languages?: string;
  description?: string;
}

export interface SettingsMineruGroup {
  api_token_hint: string;
  has_api_token: boolean;
  base_url: string;
  language: string;
  model_version: string;
  is_ocr: boolean;
  enable_table: boolean;
  enable_formula: boolean;
  disable_proxy: boolean;
  language_options: MineruSelectOption[];
  model_version_options: MineruSelectOption[];
}

/** 前端兜底：API 未返回选项时使用，应与 backend mineru_settings.py 保持一致 */
export const MINERU_LANGUAGE_OPTIONS: MineruSelectOption[] = [
  { value: "ch", label: "中英文（默认）", included_languages: "Chinese, English, Chinese Traditional" },
  { value: "ch_server", label: "繁体、手写体", included_languages: "Chinese, English, Chinese Traditional, Japanese" },
  { value: "en", label: "纯英文", included_languages: "English" },
  { value: "japan", label: "日文为主", included_languages: "Chinese, English, Chinese Traditional, Japanese" },
  { value: "korean", label: "韩文", included_languages: "Korean, English" },
  { value: "chinese_cht", label: "繁体中文为主", included_languages: "Chinese, English, Chinese Traditional, Japanese" },
  { value: "ta", label: "泰米尔文", included_languages: "Tamil, English" },
  { value: "te", label: "泰卢固文", included_languages: "Telugu, English" },
  { value: "ka", label: "卡纳达文", included_languages: "Kannada" },
  { value: "el", label: "希腊文", included_languages: "Greek, English" },
  { value: "th", label: "泰文", included_languages: "Thai, English" },
];

export const MINERU_MODEL_VERSION_OPTIONS: MineruSelectOption[] = [
  { value: "vlm", label: "VLM（视觉语言模型）" },
  { value: "pipeline", label: "Pipeline" },
];

export interface SettingsUser {
  id: string;
  name: string;
  role: string;
  email: string;
  enabled: boolean;
  created_at?: string;
}

export interface SettingsTranslationGroup extends SettingsModelGroup {
  enabled: boolean;
  source_languages: string[];
  purpose?: string;
}

export interface AppSettings {
  models: {
    vision: SettingsModelGroup;
    translation: SettingsTranslationGroup;
    nlp: SettingsModelGroup;
    mineru: SettingsMineruGroup;
  };
  system: {
    neo4j_enabled: boolean;
    mock_graph_enabled: boolean;
    thai_pipeline_root: string;
    storage_dir: string;
  };
  users: SettingsUser[];
  updated_at?: string;
}
