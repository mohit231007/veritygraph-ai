export type HealthResponse = {
  status: string;
  service: string;
  version: string;
};

export type SourceDocument = {
  source_id: string;
  source_type: "document" | "wikipedia" | "public_url";
  title: string;
  filename: string | null;
  url: string | null;
  source_format: string;
  mime_type: string;
  content_hash: string;
  size_bytes: number;
  metadata: Record<string, string | number | boolean | null>;
};

export type SourceSpan = {
  span_id: string;
  source_id: string;
  text: string;
  page_number: number | null;
  section: string | null;
  paragraph_number: number | null;
  char_start: number;
  char_end: number;
};

export type SourceBundle = {
  document: SourceDocument;
  spans: SourceSpan[];
};

export type WorkspaceSummary = {
  workspace_id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
  source_count: number;
};

export type WorkspaceDetail = WorkspaceSummary & {
  sources: SourceDocument[];
};

export type WikipediaSearchResult = {
  page_id: number;
  title: string;
  snippet: string;
  word_count: number;
  size_bytes: number;
  updated_at: string | null;
};

export type WikipediaSection = {
  index: string;
  title: string;
  number: string;
  level: number;
  anchor: string;
};

export type WikipediaOutline = {
  page_id: number;
  title: string;
  revision_id: number | null;
  url: string;
  sections: WikipediaSection[];
};

export type AnalysisStatus = "running" | "completed" | "failed";

export type AnalysisRun = {
  run_id: string;
  workspace_id: string;
  status: AnalysisStatus;
  pipeline_version: string;
  model_name: string;
  model_version: string;
  extractor_version: string;
  started_at: string;
  completed_at: string | null;
  duration_ms: number | null;
  source_count: number;
  span_count: number;
  entity_count: number;
  relation_count: number;
  error: string | null;
};

export type EntityMention = {
  mention_id: string;
  entity_id: string;
  source_id: string;
  span_id: string;
  text: string;
  start_char: number;
  end_char: number;
};

export type AnalysisEntity = {
  entity_id: string;
  run_id: string;
  canonical_name: string;
  entity_type: string;
  normalized_key: string;
  mention_count: number;
  mentions: EntityMention[];
};

export type RelationEvidence = {
  evidence_id: string;
  relation_id: string;
  source_id: string;
  span_id: string;
  text: string;
  sentence_start: number;
  sentence_end: number;
};

export type AnalysisRelation = {
  relation_id: string;
  run_id: string;
  subject_entity_id: string;
  predicate: string;
  object_entity_id: string;
  extraction_score: number;
  extraction_method: string;
  evidence: RelationEvidence[];
};

export type WorkspaceAnalysis = {
  run: AnalysisRun;
  entities: AnalysisEntity[];
  relations: AnalysisRelation[];
};
