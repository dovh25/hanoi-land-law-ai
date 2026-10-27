import { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { CitationCard } from './CitationCard';
import { IconButton } from './ui';
import type { DemoMessage } from '../types/demo';

const STATUS: Record<string, string> = {
  answered: 'Trả lời có trích dẫn', greeting: 'Trợ lý', abstained: 'Chưa đủ căn cứ',
  llm_disabled: 'Trích đoạn liên quan', llm_unavailable: 'Trích đoạn liên quan · AI tạm gián đoạn',
  citation_rejected: 'Chưa thể xác nhận câu trả lời AI',
};
const WARNINGS: Record<string, string> = {
  live_llm_disabled: 'Gemini đang tắt. Đây là trích đoạn truy xuất, không phải câu trả lời do AI tổng hợp.',
  llm_unavailable: 'AI tạm thời không khả dụng. Vui lòng đối chiếu các trích đoạn nguồn.',
  out_of_domain: 'Câu hỏi nằm ngoài lĩnh vực pháp luật đất đai.',
  outside_corpus_scope: 'Kho demo chưa bao phủ nội dung này.',
  explicit_citation_not_in_corpus: 'Văn bản hoặc điều khoản được hỏi chưa có trong kho demo.',
  no_evidence: 'Không tìm thấy trích đoạn phù hợp.',
  insufficient_evidence: 'Chưa đủ trích đoạn để trả lời đáng tin cậy.',
  weak_query_match: 'Trích đoạn tìm thấy chưa khớp đủ với câu hỏi.',
};

export function AssistantMessage({ message }: { message: DemoMessage }) {
  const [copied, setCopied] = useState<string | null>(null);
  const response = message.response;
  const rendered = (response?.answer ?? message.text).replace(/\[E(\d+)\]/g, `[E$1](#${message.id}-E$1)`);
  useEffect(() => { if (!copied) return; const timeout = window.setTimeout(() => setCopied(null), 3000); return () => window.clearTimeout(timeout); }, [copied]);
  return <section className="assistant-message" aria-label="Câu trả lời của trợ lý">
    <div className={`answer-label ${response?.status === 'abstained' || response?.status === 'citation_rejected' ? 'answer-label--warning' : ''}`}><span className="status-dot" />{STATUS[response?.status ?? 'greeting'] ?? 'Trợ lý'}</div>
    <div className="prose"><ReactMarkdown components={{ a: ({ href, children }) => <a href={href} target={href?.startsWith('https://') ? '_blank' : undefined} rel={href?.startsWith('https://') ? 'noopener noreferrer' : undefined}>{children}</a> }}>{rendered}</ReactMarkdown></div>
    {!!response?.warnings.length && <p className="answer-note">{response.warnings.map(warning => WARNINGS[warning] ?? 'Vui lòng kiểm tra phạm vi dữ liệu và đối chiếu nguồn chính thức.').join(' ')}</p>}
    {!!response?.sources.length && <section className="sources" aria-label="Trích đoạn nguồn"><h2>Nguồn tham khảo <span>{response.sources.length}</span></h2>{response.sources.map(source => <CitationCard key={source.evidence_id} source={source} anchorId={`${message.id}-${source.evidence_id}`} />)}</section>}
    <div className="answer-actions"><IconButton label="Sao chép câu trả lời" icon={copied?.startsWith('Đã') ? 'check' : 'copy'} onClick={async () => {
      try { await navigator.clipboard.writeText(message.text); setCopied('Đã sao chép câu trả lời'); }
      catch { setCopied('Không thể sao chép. Vui lòng chọn văn bản.'); }
    }} />{copied && <span role="status" className="caption">{copied}</span>}</div>
  </section>;
}
