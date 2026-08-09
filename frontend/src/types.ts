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
