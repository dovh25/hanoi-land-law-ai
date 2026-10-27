import { useLayoutEffect, useRef } from 'react';
import { Icon } from './Icon';

interface ComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSend: (value: string) => void;
  loading: boolean;
  onStop: () => void;
}

export function Composer({ value, onChange, onSend, loading, onStop }: ComposerProps) {
  const ref = useRef<HTMLTextAreaElement>(null);
  useLayoutEffect(() => {
    const resize = () => {
      const textarea = ref.current;
      if (textarea) { textarea.style.height = 'auto'; textarea.style.height = `${Math.min(160, textarea.scrollHeight)}px`; }
    };
    resize();
    window.addEventListener('resize', resize);
    return () => window.removeEventListener('resize', resize);
  }, [value]);
  return <form className="composer" aria-label="Soạn câu hỏi" onSubmit={event => { event.preventDefault(); if (!loading) onSend(value); }}>
    <textarea ref={ref} aria-label="Câu hỏi" placeholder="Hỏi về pháp luật đất đai..." rows={1} maxLength={1000} value={value} onChange={event => onChange(event.target.value.slice(0, 1000))} onKeyDown={event => {
      if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
        event.preventDefault(); if (!loading) onSend(value);
      }
    }} />
    <div className="composer-tools"><span className="composer-hint"><Icon name="document" />Tra cứu có trích dẫn</span><span className="composer-count">{value.length}/1000</span>
      {loading ? <button type="button" className="send-button" aria-label="Dừng trả lời" title="Dừng trả lời" onClick={onStop}><Icon name="stop" /></button> : <button type="submit" className="send-button" aria-label="Gửi" title="Gửi câu hỏi" disabled={!value.trim()}><Icon name="arrow" /></button>}
    </div>
  </form>;
}
