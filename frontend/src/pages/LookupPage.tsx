import { useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Button, ErrorState, Input, Loading } from '../components/ui';
import { Icon } from '../components/Icon';
import { publicJson } from '../services/publicApi';
import { containsArticle, escapeHtml, safeSourceUrl } from '../utils/documentSafety';
import type { LawDocument, DocumentListResponse, TypesResponse } from '../types';
import type { DemoInfo } from '../types/demo';

function validDocument(doc: LawDocument): boolean {
  return Boolean(doc && [doc.id, doc.title, doc.ref, doc.type, doc.date, doc.snippet].every(value => typeof value === 'string') && (doc.content == null || typeof doc.content === 'string'));
}

export function LookupPage({ info }: { info: DemoInfo | null }) {
  const [params, setParams] = useSearchParams();
  const id = params.get('id');
  const article = params.get('article');
  const [query, setQuery] = useState('');
  const [search, setSearch] = useState('');
  const [type, setType] = useState('');
  const [page, setPage] = useState(1);
  const [types, setTypes] = useState<string[]>([]);
  const [list, setList] = useState<DocumentListResponse | null>(null);
  const [doc, setDoc] = useState<LawDocument | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [tocOpen, setTocOpen] = useState(false);
  const [printError, setPrintError] = useState('');
  const reader = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const controller = new AbortController();
    publicJson<TypesResponse>('/api/v1/documents/types', controller.signal).then(data => { if (!controller.signal.aborted && Array.isArray(data.types) && data.types.every(t => typeof t === 'string')) setTypes(data.types); }).catch(() => {});
    return () => controller.abort();
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError(null); setDoc(null);
    const request = async () => {
      try {
        if (id) {
          const result = await publicJson<LawDocument>(`/api/v1/documents/${encodeURIComponent(id)}`, controller.signal);
          if (!validDocument(result)) throw Error('Invalid document');
          if (!controller.signal.aborted) setDoc(result);
        } else {
          const queryParams = new URLSearchParams({ page: String(page), page_size: '20' });
          if (type) queryParams.set('type', type);
          if (search) queryParams.set('q', search);
          const result = await publicJson<DocumentListResponse>(`/api/v1/documents${search ? '/search' : ''}?${queryParams}`, controller.signal);
          if (!result || !Array.isArray(result.items) || !result.items.every(validDocument) || ![result.page, result.page_size, result.total, result.total_pages].every(Number.isInteger)) throw Error('Invalid list');
          if (!controller.signal.aborted) setList(result);
        }
      } catch { if (!controller.signal.aborted) setError(id ? 'Không thể tải văn bản. Văn bản có thể không tồn tại hoặc máy chủ chưa sẵn sàng.' : 'Không thể tải danh sách văn bản. Vui lòng thử lại.'); }
      finally { if (!controller.signal.aborted) setLoading(false); }
    };
    void request();
    return () => controller.abort();
  }, [id, page, search, type, attempt]);
  const lines = useMemo(() => (doc?.content || doc?.snippet || '').split('\n'), [doc]);
  const toc = useMemo(() => lines.flatMap((line, index) => /^(?:PHẦN\s+[IVXLCDM\d]+|CHƯƠNG\s+[IVXLCDM\d]+|MỤC\s+\d+|Điều\s+\d+[a-zđ]?[.\s])/iu.test(line.trim()) ? [{ title: line.trim(), index }] : []), [lines]);
  useEffect(() => {
    if (!doc) return;
    const target = article && /^Điều\s+\d+[a-zđ]?$/iu.test(article) ? reader.current?.querySelector('.cited-provision') : null;
    target?.scrollIntoView({ block: 'center' });
  }, [doc, article]);
  const official = safeSourceUrl(info?.documents.find(item => item.document_number === doc?.ref)?.source_url || '');
  const print = () => {
    if (!doc) return;
    const popup = window.open('', '_blank');
    if (!popup) { setPrintError('Vui lòng cho phép cửa sổ bật lên để xuất PDF.'); return; }
    popup.opener = null;
    popup.document.write(`<!doctype html><html lang="vi"><meta charset="utf-8"><title>${escapeHtml(doc.ref)}</title><style>body{font:16px/1.7 sans-serif;margin:24mm}pre{white-space:pre-wrap;font:inherit}</style><h1>${escapeHtml(doc.title)}</h1><p>${escapeHtml(doc.ref)} · ${escapeHtml(doc.type)} · ${escapeHtml(doc.date)}</p><p>Hiệu lực chưa xác minh. Trích đoạn demo, không phải toàn văn.</p><pre>${escapeHtml(doc.content || doc.snippet)}</pre><footer>Hanoi Land Law AI</footer></html>`);
    popup.document.close(); popup.focus(); popup.print();
  };
  return <main className="lookup-page">
    {id ? <div className="reader-layout">
      <div className="reader-scroll" ref={reader}>
        <div className="reader-document"><Button variant="ghost" onClick={() => { setParams({}); setTocOpen(false); }}><Icon name="back" />Thư viện văn bản</Button>
          {loading ? <Loading /> : error ? <ErrorState message={error} onRetry={() => setAttempt(v => v + 1)} /> : doc && <>
            <header className="document-header"><h1>{doc.title}</h1><p className="metadata">{doc.ref} · {doc.type} · {doc.date}</p><p className="caption">Hiệu lực chưa xác minh · Trích đoạn demo, không phải toàn văn</p><div className="document-actions">{official && <a className="text-link" href={official} target="_blank" rel="noopener noreferrer">Nguồn chính thức<Icon name="external" /></a>}<Button variant="ghost" onClick={print}><Icon name="download" />Xuất PDF</Button><Button className="toc-toggle" variant="ghost" aria-expanded={tocOpen} onClick={() => setTocOpen(v => !v)}><Icon name="list" />Mục lục</Button></div></header>
            {printError && <p role="alert">{printError}</p>}
            {tocOpen && <nav aria-label="Mục lục di động" className="mobile-toc">{toc.map(item => <a key={item.index} href={`#provision-${item.index}`} onClick={() => setTocOpen(false)}>{item.title}</a>)}</nav>}
            <article className="legal-content">{lines.map((line, index) => {
              const heading = toc.some(item => item.index === index);
              const highlighted = !!article && /^Điều\s+\d+[a-zđ]?$/iu.test(article) && containsArticle(line, article);
              return heading ? <h2 id={`provision-${index}`} className={highlighted ? 'cited-provision' : ''} key={index}>{line}</h2> : <p key={index}>{line || '\u00a0'}</p>;
            })}</article><p className="notice">Nội dung trích đoạn cần được đối chiếu với văn bản gốc. Đây không phải tư vấn pháp lý.</p>
          </>}
        </div>
      </div>
      {doc && <aside className="document-toc"><h2>Mục lục</h2><nav aria-label="Mục lục">{toc.map(item => <a key={item.index} href={`#provision-${item.index}`}>{item.title}</a>)}</nav></aside>}
    </div> : <div className="library-scroll"><div className="document-library"><h1>Thư viện văn bản</h1><p className="supporting">Tra cứu theo tên, số hiệu hoặc nội dung văn bản.</p>
      <form className="document-search" onSubmit={event => { event.preventDefault(); setPage(1); setSearch(query.trim()); }}><Icon name="search" /><Input aria-label="Tìm kiếm văn bản" placeholder="Tìm tên, số hiệu hoặc nội dung văn bản..." value={query} onChange={event => setQuery(event.target.value)} /><Button type="submit">Tìm kiếm</Button></form>
      <div className="library-filters" aria-label="Loại văn bản">{['', ...types].map(value => <button key={value} aria-pressed={type === value} onClick={() => { setType(value); setPage(1); }}>{value || 'Tất cả'}</button>)}<span className="metadata">{list?.total ?? 0} văn bản</span></div>
      {loading ? <Loading /> : error ? <ErrorState message={error} onRetry={() => setAttempt(v => v + 1)} /> : list?.items.length ? <div className="document-results">{list.items.map(item => <button key={item.id} className="document-result" onClick={() => setParams({ id: item.id })}><Icon name="document" /><span><strong>{item.title}</strong><span className="metadata">{item.ref} · {item.type} · {item.date}</span><span className="caption">Hiệu lực chưa xác minh · Kho trích đoạn demo</span></span><Icon name="chevron" /></button>)}</div> : <div className="empty-results"><Icon name="search" /><h2>Không tìm thấy văn bản phù hợp</h2><p>Thử tìm theo số hiệu hoặc từ khóa ngắn hơn.</p></div>}
      {!!list && list.total_pages > 1 && <nav className="pagination" aria-label="Phân trang"><Button disabled={page <= 1} onClick={() => setPage(v => v - 1)}>Trang trước</Button><span>{page}/{list.total_pages}</span><Button disabled={page >= list.total_pages} onClick={() => setPage(v => v + 1)}>Trang sau</Button></nav>}
      <p className="library-disclaimer caption">Kho trích đoạn demo · Hiệu lực chưa xác minh</p>
    </div></div>}
  </main>;
}
