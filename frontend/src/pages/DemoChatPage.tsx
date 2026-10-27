import { useCallback, useEffect, useRef, useState, type Dispatch, type SetStateAction } from 'react';
import { Composer } from '../components/Composer';
import { AssistantMessage } from '../components/AssistantMessage';
import { Icon } from '../components/Icon';
import { ErrorState, Loading } from '../components/ui';
import { sendDemoMessage, DemoApiError } from '../services/demoApi';
import { newId } from '../utils/conversations';
import type { DemoMessage } from '../types/demo';

const SUGGESTIONS = [
  'Khi Nhà nước thu hồi đất ở, hộ gia đình được bồi thường những gì?',
  'Điều 11 Nghị định 88/2024/NĐ-CP quy định gì?',
  'Luật 43/2024/QH15 sửa đổi những nội dung gì?',
];

interface DemoChatPageProps {
  messages: DemoMessage[];
  setMessages: Dispatch<SetStateAction<DemoMessage[]>>;
  input: string;
  setInput: (value: string) => void;
}

export function DemoChatPage({ messages, setMessages, input, setInput }: DemoChatPageProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const request = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLElement>(null);
  const lastRef = useRef<HTMLDivElement>(null);
  const pinned = useRef(true);
  useEffect(() => () => { request.current?.abort('navigation'); request.current = null; }, []);
  useEffect(() => {
    if (pinned.current && messages.length) lastRef.current?.scrollIntoView({ block: messages.at(-1)?.role === 'assistant' ? 'start' : 'end', behavior: 'instant' });
  }, [messages]);

  const submit = useCallback(async (value: string) => {
    const question = value.trim();
    if (!question || question.length > 1000 || request.current) return;
    const controller = new AbortController();
    request.current = controller;
    pinned.current = true;
    setLoading(true); setError(null); setNotice(null); setInput('');
    setMessages(current => [...current, { id: `m-${newId()}`, role: 'user', text: question }]);
    const timeout = window.setTimeout(() => controller.abort('timeout'), 60000);
    try {
      const history = messages.slice(-6).map(message => ({ role: message.role, content: message.text.slice(0, 4000) }));
      const response = await sendDemoMessage(question, history, controller.signal);
      if (!controller.signal.aborted && request.current === controller) setMessages(current => [...current, { id: `m-${newId()}`, role: 'assistant', text: response.answer, response }]);
    } catch (reason) {
      if (request.current !== controller) return;
      if (controller.signal.aborted && controller.signal.reason !== 'timeout') return;
      setInput(question);
      setError(controller.signal.reason === 'timeout' ? 'Máy chủ phản hồi chậm. Vui lòng thử lại.' : reason instanceof DemoApiError
        ? reason.status === 429 ? `Bạn đã gửi quá nhiều câu hỏi. Vui lòng thử lại sau ${reason.retryAfter ?? 60} giây.` : reason.message
        : 'Không thể kết nối tới máy chủ. Vui lòng kiểm tra mạng và thử lại.');
    } finally {
      window.clearTimeout(timeout);
      if (request.current === controller) { request.current = null; setLoading(false); }
    }
  }, [messages, setInput, setMessages]);

  const stop = () => { request.current?.abort('user'); request.current = null; setLoading(false); setNotice('Đã dừng yêu cầu. Bạn có thể tiếp tục đặt câu hỏi.'); };
  const empty = messages.length === 0;
  return <div className={`chat-page ${empty ? 'is-empty' : ''}`}>
    <main ref={scrollRef} className="chat-scroll" aria-label="Hội thoại" onScroll={() => { const node = scrollRef.current; if (node) pinned.current = node.scrollHeight - node.clientHeight - node.scrollTop < 180; }}>
      {empty ? <div className="welcome"><span className="welcome-mark"><Icon name="document" /></span><h1>Bạn muốn tìm hiểu vấn đề đất đai nào?</h1><p>Đặt câu hỏi để tra cứu thông tin từ các văn bản pháp luật.</p><div className="mobile-suggestions">{SUGGESTIONS.slice(0, 2).map(question => <button key={question} className="suggestion" onClick={() => void submit(question)}><Icon name="external" /><span>{question}</span></button>)}</div></div> : <div className="chat-transcript" role="log" aria-label="Tin nhắn" aria-live="polite" aria-relevant="additions">
        {messages.map((message, index) => <div key={message.id} ref={index === messages.length - 1 ? lastRef : undefined} className="message-row">{message.role === 'user' ? <div className="user-message">{message.text}</div> : <AssistantMessage message={message} />}</div>)}
        {loading && <Loading>Đang tìm trích đoạn liên quan…</Loading>}
        {error && <ErrorState message={error} />}
        {notice && <p role="status" className="notice">{notice}</p>}
      </div>}
    </main>
    <section className="composer-region" aria-label="Vùng soạn thảo"><Composer value={input} onChange={setInput} onSend={value => void submit(value)} loading={loading} onStop={stop} />
      {empty && <div className="desktop-suggestions">{SUGGESTIONS.map(question => <button key={question} className="suggestion" onClick={() => void submit(question)}><Icon name="external" /><span>{question}</span></button>)}</div>}
      <p className="composer-disclaimer">Thông tin tham khảo, không thay thế tư vấn pháp lý.</p>
    </section>
  </div>;
}
