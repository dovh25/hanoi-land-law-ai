import { Link } from 'react-router-dom';
import { Icon } from './Icon';
import { safeSourceUrl } from '../utils/documentSafety';
import type { DemoSource } from '../types/demo';

export function CitationCard({ source, anchorId }: { source: DemoSource; anchorId: string }) {
  const url = safeSourceUrl(source.source_url);
  return <article id={anchorId} className="source-card" aria-label={`Nguồn ${source.evidence_id}`}>
    <div className="source-heading"><span className="evidence-label">{source.evidence_id}</span><strong>{source.document_number}</strong><span className="metadata">{source.article_number}</span></div>
    <p className="source-title">{source.document_title || source.article_heading}</p>
    <div className="source-footer"><span className="caption">Hiệu lực: chưa xác minh</span><div className="source-actions">
      {source.document_id && <Link className="text-link" to={`/lookup?${new URLSearchParams({ id: source.document_id, article: source.article_number })}`}>Đọc {source.article_number}<Icon name="chevron" /></Link>}
      {url && <a className="text-link" href={url} target="_blank" rel="noopener noreferrer">Nguồn chính thức<Icon name="external" /></a>}
    </div></div>
    <details className="source-excerpt"><summary>Xem trích đoạn</summary><p>{source.excerpt}</p><p className="caption">Vị trí {source.source_start}–{source.source_end} · Kiểm tra kỹ thuật, chưa duyệt pháp lý.</p></details>
  </article>;
}
