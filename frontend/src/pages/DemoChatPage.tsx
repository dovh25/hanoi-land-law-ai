import { useCallback, useEffect, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { Link } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import { fetchDemoInfo, sendDemoMessage, DemoApiError } from '../services/demoApi';
import type { DemoInfo, DemoMessage, DemoSource } from '../types/demo';

const SUGGESTIONS = [
  'Khi Nhà nước thu hồi đất ở, hộ gia đình được bồi thường những gì?',
  'Điều kiện được bồi thường về đất khi Nhà nước thu hồi đất?',
  'Hỗ trợ tái định cư khi thu hồi đất nông nghiệp được quy định thế nào?',
  'Nghị định 88/2024/NĐ-CP có hiệu lực khi nào?',
  'Luật 43/2024/QH15 sửa đổi những nội dung gì?',
];

const STATUS_LABELS: Record<string, { label: string; tone: string }> = {
  answered: { label: 'Trả lời có trích dẫn', tone: 'bg-okbg text-ok border-[#CBE2D6]' },
  greeting: { label: 'Trợ lý', tone: 'bg-line-soft text-muted border-line' },
  abstained: { label: 'Chưa đủ căn cứ', tone: 'bg-warnbg text-warn border-[#E7D6A8]' },
  llm_disabled: { label: 'Chỉ truy xuất — Gemini đang tắt', tone: 'bg-infobg text-info border-[#CFE0EA]' },
  llm_unavailable: { label: 'Gemini tạm thời không khả dụng', tone: 'bg-warnbg text-warn border-[#E7D6A8]' },
  citation_rejected: { label: 'Câu trả lời AI bị loại', tone: 'bg-[#F7E7E7] text-[#9B2C2C] border-[#E8C9C9]' },
};

function newId(): string {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function SourceCard({ source, anchorId }: { source: DemoSource; anchorId: string }) {
  return (
    <article id={anchorId} className="scroll-mt-24 rounded-xl border border-line bg-paper-2 p-3 sm:p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-md bg-gold-500 px-2 py-0.5 text-[11px] font-extrabold text-[#20180A]">
          {source.evidence_id}
        </span>
        <span className="font-display text-sm font-bold text-ink-900">{source.document_number}</span>
        <span className="text-xs text-muted">{source.article_number}</span>
        <span className="ml-auto rounded-full border border-[#E7D6A8] bg-warnbg px-2 py-0.5 text-[11px] font-medium text-warn">
          Hiệu lực: chưa xác minh
        </span>
      </div>
      {source.article_heading && (
        <p className="mt-2 text-sm font-medium text-[#242019]">{source.article_heading}</p>
      )}
      <p className="excerpt-scroll mt-2 max-h-44 overflow-y-auto whitespace-pre-wrap break-words rounded-lg border border-line-soft bg-[#F5F1E6] p-2.5 text-xs leading-relaxed text-[#4A4437] sm:text-sm">
        {source.excerpt}
      </p>
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-2">
        <span>Đoạn {source.source_start}–{source.source_end}</span>
        <span>Đánh giá: kỹ thuật, chưa duyệt pháp lý</span>
        <a
          href={source.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="font-semibold text-info underline decoration-[#B9D0DD] underline-offset-2 hover:text-navy-700"
        >
          Nguồn chính thức ↗
        </a>
      </div>
    </article>
  );
}

function AssistantMessage({ message }: { message: DemoMessage }) {
  const response = message.response;
  const status = response ? STATUS_LABELS[response.status] : undefined;
  const answer = response?.answer ?? message.text;
  const rendered = answer.replace(
    /\[E(\d+)\]/g,
    `[E$1](#${message.id}-E$1)`,
  );
  return (
    <div className="flex gap-2 sm:gap-3">
      <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-gold-500 bg-ink-900 font-display text-[11px] font-bold text-gold-300 sm:h-9 sm:w-9">
        AI
      </div>
      <div className="min-w-0 flex-1">
        <div className="rounded-2xl rounded-tl-sm border border-line bg-paper-2 px-3 py-3 shadow-[0_12px_30px_-24px_rgba(11,20,32,0.5)] sm:px-4">
          {status && (
            <span className={`mb-2 inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${status.tone}`}>
              <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden="true" />
              {status.label}
            </span>
          )}
          <div className="prose prose-sm max-w-none text-[#242019]">
            <ReactMarkdown>{rendered}</ReactMarkdown>
          </div>
          {response && response.warnings.length > 0 && (
            <p className="mt-3 rounded-lg border border-[#EBDCB8] bg-[#FBF4E2] px-2.5 py-2 text-[11px] leading-relaxed text-[#7A5A16]">
              Ghi chú an toàn: câu trả lời đã qua kiểm tra trích dẫn, ngày và số điều.
            </p>
          )}
        </div>
        {response && response.sources.length > 0 && (
          <div className="mt-3 space-y-2">
            <p className="px-1 text-[11px] font-bold uppercase tracking-[0.12em] text-muted-2">
              Trích đoạn nguồn ({response.sources.length})
            </p>
            {response.sources.map((source) => (
              <SourceCard key={source.evidence_id} source={source} anchorId={`${message.id}-${source.evidence_id}`} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function InfoPanel({ info }: { info: DemoInfo | null }) {
  if (!info) {
    return null;
  }
  return (
    <section className="rounded-2xl border border-line bg-paper-2 px-4 py-3.5 shadow-[0_12px_30px_-30px_rgba(11,20,32,0.45)] sm:px-5">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-full bg-ink-900 px-2.5 py-1 font-display text-[11px] font-semibold tracking-[0.06em] text-gold-300">
          MVP_DEMO_CORPUS
        </span>
        <span className="rounded-full border border-[#E7D6A8] bg-warnbg px-2.5 py-1 text-[11px] font-medium text-warn">
          Hiệu lực: chưa xác minh
        </span>
        <span className="rounded-full border border-[#CFE0EA] bg-infobg px-2.5 py-1 text-[11px] text-info">
          {info.llm_enabled ? `Gemini: ${info.model}` : 'Gemini: đang tắt (chế độ truy xuất)'}
        </span>
      </div>
      <p className="mt-3 text-sm leading-relaxed text-[#3A352B]">
        Kho demo gồm <strong className="text-ink-900">{info.document_count} văn bản</strong> và{' '}
        <strong className="text-ink-900">{info.chunk_count} trích đoạn</strong>, truy xuất bằng {info.retrieval}. Đây là bản
        nghiên cứu, không phải tư vấn pháp lý và không xác nhận văn bản đang có hiệu lực hiện hành.
      </p>
      <details className="mt-3 border-t border-dashed border-line pt-3 text-xs text-muted">
        <summary className="cursor-pointer select-none font-medium text-muted">
          Văn bản và giới hạn dữ liệu
        </summary>
        <ul className="mt-2.5 space-y-1.5">
          {info.documents.map((document) => (
            <li key={document.document_number} className="rounded-lg border border-line-soft bg-[#F5F1E6] p-2.5">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-display font-bold text-ink-900">{document.document_number}</span>
                <span className="text-muted">{document.issuing_authority}</span>
                <span className="rounded border border-line bg-paper-2 px-1.5 py-0.5 text-[10px] text-muted-2">
                  {document.chunks} trích đoạn
                </span>
              </div>
              <p className="mt-1 line-clamp-2 text-[#3A352B]">{document.title}</p>
              <a
                href={document.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[11px] font-semibold text-info underline decoration-[#B9D0DD] underline-offset-2"
              >
                Trang nguồn chính thức ↗
              </a>
            </li>
          ))}
        </ul>
        {Object.keys(info.limitations).length > 0 && (
          <div className="mt-3">
            <p className="font-medium text-muted">Chưa đưa vào kho demo:</p>
            <ul className="mt-1 list-disc space-y-1 pl-4">
              {Object.entries(info.limitations).map(([number, reason]) => (
                <li key={number}>
                  <span className="font-medium">{number}:</span> {reason}
                </li>
              ))}
            </ul>
          </div>
        )}
        <p className="mt-3 text-[11px] text-muted-2">
          Giới hạn tần suất: {info.rate_limit_per_minute} câu/phút và {info.rate_limit_per_day} câu/ngày
          cho mỗi địa chỉ IP. Không lưu hội thoại trên máy chủ.
        </p>
      </details>
    </section>
  );
}

export function DemoChatPage() {
  const [messages, setMessages] = useState<DemoMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<DemoInfo | null>(null);
  const [infoError, setInfoError] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetchDemoInfo(controller.signal)
      .then(setInfo)
      .catch((reason) => {
        if ((reason as Error).name !== 'AbortError') {
          setInfoError(true);
        }
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, loading]);

  const submit = useCallback(
    async (text: string) => {
      const question = text.trim();
      if (!question || loading) {
        return;
      }
      setError(null);
      setInput('');
      setMessages((current) => [...current, { id: newId(), role: 'user', text: question }]);
      setLoading(true);
      const controller = new AbortController();
      try {
        const history = messages.slice(-6).map((message) => ({
          role: message.role === 'user' ? ('user' as const) : ('assistant' as const),
          content: message.text,
        }));
        const response = await sendDemoMessage(question, history, controller.signal);
        setMessages((current) => [
          ...current,
          { id: newId(), role: 'assistant', text: response.answer, response },
        ]);
      } catch (reason) {
        if ((reason as Error).name === 'AbortError') {
          return;
        }
        if (reason instanceof DemoApiError) {
          setError(
            reason.status === 429
              ? `Bạn đã gửi quá nhiều câu hỏi. Vui lòng thử lại sau ${reason.retryAfter ?? 60} giây.`
              : reason.message,
          );
        } else {
          setError('Không thể kết nối tới máy chủ demo. Vui lòng kiểm tra mạng và thử lại.');
        }
      } finally {
        setLoading(false);
      }
    },
    [loading, messages],
  );

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void submit(input);
    }
  };

  return (
    <div className="flex min-h-dvh flex-col bg-paper text-[#1B1915]">
      <header className="sticky top-0 z-20 border-b-2 border-gold-500 bg-ink-900 text-paper-2">
        <div className="mx-auto flex w-full max-w-4xl items-center justify-between gap-2 px-3 py-2.5 sm:px-4 sm:py-3.5">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[4px] border border-gold-500 bg-gradient-to-br from-navy-700 to-ink-900 font-display text-base font-semibold tracking-wide text-gold-300">
              HL
            </div>
            <div className="min-w-0">
              <h1 className="truncate font-display text-base font-semibold sm:text-xl">Hanoi Land Law AI</h1>
              <p className="truncate text-[10px] tracking-[0.02em] text-[#9FB0C0] sm:text-xs">
                Trợ lý nghiên cứu pháp luật đất đai · bản demo
              </p>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <span className="hidden rounded-full border border-gold-500/65 px-3 py-1.5 text-[11px] tracking-[0.02em] text-gold-300 sm:inline">
              Không phải tư vấn pháp lý
            </span>
            <Link
              to="/chat"
              className="rounded-lg border border-[#2C4055] px-3 py-1.5 text-[11px] font-medium text-[#D6DEE6] transition hover:bg-[#132435]"
            >
              Đăng nhập
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-4xl flex-1 space-y-3 px-3 pb-44 pt-4 sm:px-4 sm:pb-40">
        <InfoPanel info={info} />
        {infoError && (
          <p className="rounded-xl border border-[#E7D6A8] bg-warnbg px-3 py-2 text-xs text-warn">
            Không tải được thông tin kho dữ liệu. Bạn vẫn có thể đặt câu hỏi.
          </p>
        )}
        {messages.length === 0 && (
          <section className="rounded-2xl border border-line bg-paper-2 px-5 py-6 shadow-[0_12px_30px_-30px_rgba(11,20,32,0.45)] sm:px-6">
            <h2 className="font-display text-xl font-semibold text-ink-900 sm:text-2xl">
              Hỏi về bồi thường, hỗ trợ, tái định cư
            </h2>
            <p className="mt-2.5 max-w-2xl text-sm leading-relaxed text-[#4A4437]">
              Câu trả lời được tổng hợp từ trích đoạn văn bản thật và kèm liên kết nguồn chính thức.
              Hệ thống sẽ từ chối trả lời khi kho demo không đủ căn cứ.
            </p>
            <div className="mt-4 flex flex-wrap gap-2.5">
              {SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => void submit(suggestion)}
                  className="rounded-full border border-line bg-[#FBF8F0] px-3.5 py-2 text-left text-xs leading-snug text-[#3E382C] transition hover:border-gold-500 hover:bg-gold-100 sm:text-[13px]"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </section>
        )}

        <div className="space-y-5" aria-live="polite">
          {messages.map((message) =>
            message.role === 'user' ? (
              <div key={message.id} className="flex justify-end">
                <div className="max-w-[88%] rounded-2xl rounded-tr-sm bg-navy-700 px-3.5 py-2.5 text-sm leading-relaxed text-[#F3EEE2] sm:max-w-[80%] sm:px-4 sm:py-3">
                  {message.text}
                </div>
              </div>
            ) : (
              <AssistantMessage key={message.id} message={message} />
            ),
          )}
          {loading && (
            <div className="flex items-center gap-2 text-xs text-muted">
              <span className="h-3 w-3 animate-spin rounded-full border-2 border-line border-t-gold-500" />
              Đang truy xuất trích đoạn và soạn câu trả lời…
            </div>
          )}
          {error && (
            <div className="rounded-xl border border-[#E8C9C9] bg-[#F7E7E7] px-3 py-2 text-sm text-[#9B2C2C]">
              {error}
            </div>
          )}
        </div>
        <div ref={bottomRef} />
      </main>

      <div className="fixed inset-x-0 bottom-0 z-20 border-t border-line bg-paper-2/95 backdrop-blur">
        <div className="mx-auto w-full max-w-4xl px-3 py-2.5 sm:px-4 sm:py-3.5">
          <div className="flex items-end gap-2">
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value.slice(0, 1000))}
              onKeyDown={onKeyDown}
              rows={1}
              maxLength={1000}
              placeholder="Nhập câu hỏi về pháp luật đất đai…"
              aria-label="Câu hỏi"
              className="max-h-32 min-h-[46px] flex-1 resize-y rounded-xl border border-[#CFC6AE] bg-white px-3.5 py-3 text-sm outline-none focus:border-gold-500 focus:ring-2 focus:ring-gold-100"
            />
            <button
              type="button"
              onClick={() => void submit(input)}
              disabled={loading || input.trim().length === 0}
              className="h-[46px] shrink-0 rounded-xl bg-gold-500 px-5 text-sm font-bold text-[#20180A] transition hover:bg-gold-600 disabled:cursor-not-allowed disabled:bg-line disabled:text-muted-2"
            >
              Gửi
            </button>
          </div>
          <div className="mt-1.5 flex flex-wrap items-center justify-between gap-1 text-[10px] text-muted-2">
            <span>Enter để gửi · Shift+Enter để xuống dòng</span>
            <span>{input.length}/1000 · Không lưu hội thoại</span>
          </div>
        </div>
      </div>
    </div>
  );
}
