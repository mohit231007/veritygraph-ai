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
export type AssertionPolarity = "unknown" | "affirmed" | "negated";
export type AssertionModality = "unknown" | "asserted" | "modal";

export type AnalysisRun = {
  run_id: string;
  workspace_id: string;
  status: AnalysisStatus;
  pipeline_version: string;
  model_name: string;
  model_version: string;
  extractor_version: string;
  resolver_version: string;
  started_at: string;
  completed_at: string | null;
  duration_ms: number | null;
  source_count: number;
  source_ids: string[];
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
  polarity: AssertionPolarity;
  polarity_method: string;
  modality: AssertionModality;
  modality_method: string;
  temporal_years: number[];
  temporal_method: string;
  extraction_score: number;
  extraction_method: string;
  evidence: RelationEvidence[];
};

export type WorkspaceAnalysis = {
  run: AnalysisRun;
  entities: AnalysisEntity[];
  relations: AnalysisRelation[];
};

export type GraphNode = {
  entity_id: string;
  label: string;
  entity_type: string;
  mention_count: number;
  source_count: number;
  in_degree: number;
  out_degree: number;
  degree_centrality: number;
  pagerank: number;
  betweenness: number;
  community: number;
};

export type GraphEdge = {
  relation_id: string;
  source_entity_id: string;
  target_entity_id: string;
  predicate: string;
  polarity: AssertionPolarity;
  polarity_method: string;
  modality: AssertionModality;
  modality_method: string;
  temporal_years: number[];
  temporal_method: string;
  extraction_score: number;
  extraction_method: string;
  evidence_count: number;
  source_count: number;
  evidence: RelationEvidence[];
};

export type GraphSummary = {
  node_count: number;
  edge_count: number;
  density: number;
  weak_component_count: number;
  community_count: number;
};

export type EvidenceGraph = {
  run_id: string;
  workspace_id: string;
  graph_version: string;
  summary: GraphSummary;
  nodes: GraphNode[];
  edges: GraphEdge[];
};

export type GraphPathStep = {
  source_entity_id: string;
  target_entity_id: string;
  relation_ids: string[];
};

export type GraphPath = {
  run_id: string;
  source_entity_id: string;
  target_entity_id: string;
  directed: boolean;
  hop_count: number;
  entity_ids: string[];
  steps: GraphPathStep[];
};

export type ClaimSupportLevel = "single_source" | "cross_source";

export type ComparisonClaim = {
  relation_id: string;
  subject_entity_id: string;
  subject_label: string;
  predicate: string;
  object_entity_id: string;
  object_label: string;
  polarity: AssertionPolarity;
  polarity_method: string;
  modality: AssertionModality;
  modality_method: string;
  temporal_years: number[];
  temporal_method: string;
  extraction_score: number;
  support_level: ClaimSupportLevel;
  source_count: number;
  source_ids: string[];
  evidence_count: number;
  evidence: RelationEvidence[];
  distinct_content_count: number;
  distinct_evidence_text_count: number;
  content_duplicate_signal: boolean;
  repeated_evidence_text_signal: boolean;
};

export type ContradictionCandidate = {
  assertion_key: string;
  subject_entity_id: string;
  subject_label: string;
  predicate: string;
  object_entity_id: string;
  object_label: string;
  temporal_years: number[];
  affirmed_relation_ids: string[];
  negated_relation_ids: string[];
  affirmed_source_ids: string[];
  negated_source_ids: string[];
  source_count: number;
  evidence_count: number;
  affirmed_evidence: RelationEvidence[];
  negated_evidence: RelationEvidence[];
};

export type SourceClaimProfile = {
  source_id: string;
  label: string;
  source_type: SourceDocument["source_type"] | null;
  claim_count: number;
  cross_source_claim_count: number;
  single_source_claim_count: number;
  contradiction_candidate_count: number;
};

export type SourcePairOverlap = {
  left_source_id: string;
  right_source_id: string;
  shared_claim_count: number;
  union_claim_count: number;
  jaccard_similarity: number;
  shared_relation_ids: string[];
  same_content_hash: boolean;
  same_origin_host: boolean;
  shared_origin_host: string | null;
  exact_shared_evidence_text_count: number;
  exact_shared_evidence_texts: string[];
  possible_derivation_signal: boolean;
};

export type SourceComparisonSummary = {
  source_count: number;
  claim_count: number;
  cross_source_claim_count: number;
  single_source_claim_count: number;
  contradiction_candidate_count: number;
  pair_count: number;
  possible_derivation_pair_count: number;
};

export type SourceComparison = {
  run_id: string;
  workspace_id: string;
  comparison_version: string;
  summary: SourceComparisonSummary;
  sources: SourceClaimProfile[];
  claims: ComparisonClaim[];
  contradictions: ContradictionCandidate[];
  overlaps: SourcePairOverlap[];
  interpretation_note: string;
};
