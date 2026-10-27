export interface DemoSource {
  document_id?: string;
  evidence_id: string;
  chunk_id: string;
  document_number: string;
  document_title: string;
  document_type?: string;
  issuing_authority?: string;
  article_number: string;
  article_heading?: string;
  source_url: string;
  source_start: number;
  source_end: number;
  excerpt: string;
  validity_status: 'unknown' | 'in_force' | 'expired' | 'partially_expired';
  review_status: string;
  corpus_label: string;
}

export interface DemoCorpusInfo {
  label: string;
  validity_status: string;
  review_status: string;
  document_count: number;
  chunk_count: number;
  limitations: Record<string, string>;
  disclaimer: string;
}

export interface DemoChatResponse {
  answer: string;
  status: string;
  sources: DemoSource[];
  warnings: string[];
  rejected_citations: string[];
  llm_used: boolean;
  request_id: string;
  abstention_reason?: string | null;
  corpus: DemoCorpusInfo;
  rate_limit?: { limit: number; remaining: number } | null;
}

export interface DemoInfo {
  corpus: string;
  publication_status: string;
  validity_status: string;
  review_status: string;
  document_count: number;
  chunk_count: number;
  documents: Array<{
    document_number: string;
    title: string;
    document_type: string;
    issuing_authority: string;
    source_url: string;
    validity_status: string;
    review_status: string;
    chunks: number;
  }>;
  limitations: Record<string, string>;
  disclaimer: string;
  llm_enabled: boolean;
  model: string;
  retrieval: string;
  rate_limit_per_minute: number;
  rate_limit_per_day: number;
}

export interface DemoMessage {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  response?: DemoChatResponse;
}
