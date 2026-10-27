/**
 * Anonymous demo API. No auth header, no local storage, no persisted session.
 */
import { API_BASE_URL } from './publicApi';
import type { DemoChatResponse, DemoInfo } from '../types/demo';
import { parseRetryAfter } from '../utils/retryAfter';

export class DemoApiError extends Error {
  status: number;
  retryAfter: number | null;

  constructor(status: number, message: string, retryAfter: number | null = null) {
    super(message);
    this.name = 'DemoApiError';
    this.status = status;
    this.retryAfter = retryAfter;
  }
}

async function parseError(response: Response): Promise<DemoApiError> {
  let detail = 'Không thể xử lý yêu cầu.';
  try {
    const body = await response.json();
    if (typeof body?.detail === 'string') {
      detail = body.detail;
    } else if (Array.isArray(body?.detail)) {
      detail = 'Nội dung câu hỏi chưa hợp lệ.';
    }
  } catch {
    // Keep the generic Vietnamese message.
  }
  return new DemoApiError(response.status, detail, parseRetryAfter(response.headers.get('Retry-After')));
}

export async function fetchDemoInfo(signal?: AbortSignal): Promise<DemoInfo> {
  const response = await fetch(`${API_BASE_URL}/api/v1/demo/info`, { signal, credentials: 'omit' });
  if (!response.ok) {
    throw await parseError(response);
  }
  const data = await response.json();
  if (!data || !Array.isArray(data.documents) || !data.limitations || typeof data.limitations !== 'object'
    || !Object.values(data.limitations).every(value => typeof value === 'string')
    || typeof data.document_count !== 'number' || typeof data.chunk_count !== 'number'
    || typeof data.retrieval !== 'string' || typeof data.model !== 'string'
    || !data.documents.every((doc: Record<string, unknown>) => doc
      && ['document_number', 'title', 'issuing_authority', 'source_url'].every(key => typeof doc[key] === 'string'))) {
    throw new DemoApiError(502, 'Thông tin kho dữ liệu chưa hợp lệ.');
  }
  return data as DemoInfo;
}

export async function sendDemoMessage(
  message: string,
  history: Array<{ role: 'user' | 'assistant'; content: string }>,
  signal?: AbortSignal,
): Promise<DemoChatResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/demo/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, history: history.slice(-6) }),
    signal,
    credentials: 'omit',
  });
  if (!response.ok) {
    throw await parseError(response);
  }
  const data = await response.json();
  if (!data || typeof data.answer !== 'string' || typeof data.status !== 'string'
    || !Array.isArray(data.sources) || !Array.isArray(data.warnings) || !data.warnings.every((value: unknown) => typeof value === 'string')
    || !data.sources.every((source: Record<string, unknown>) => source
      && ['evidence_id', 'document_number', 'document_title', 'article_number', 'excerpt', 'source_url'].every(key => typeof source[key] === 'string')
      && (source.document_id === undefined || typeof source.document_id === 'string')
      && (source.article_heading === undefined || typeof source.article_heading === 'string')
      && typeof source.source_start === 'number' && typeof source.source_end === 'number')) {
    throw new DemoApiError(502, 'Máy chủ trả về dữ liệu chưa hợp lệ. Vui lòng thử lại.');
  }
  return data as DemoChatResponse;
}
