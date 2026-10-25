/**
 * Anonymous demo API. No auth header, no local storage, no persisted session.
 */
import { API_BASE_URL } from './api';
import type { DemoChatResponse, DemoInfo } from '../types/demo';

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
  const retryAfter = Number(response.headers.get('Retry-After'));
  return new DemoApiError(response.status, detail, Number.isFinite(retryAfter) ? retryAfter : null);
}

export async function fetchDemoInfo(signal?: AbortSignal): Promise<DemoInfo> {
  const response = await fetch(`${API_BASE_URL}/api/v1/demo/info`, { signal });
  if (!response.ok) {
    throw await parseError(response);
  }
  return response.json() as Promise<DemoInfo>;
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
  });
  if (!response.ok) {
    throw await parseError(response);
  }
  return response.json() as Promise<DemoChatResponse>;
}
