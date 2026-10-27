import { useCallback, useEffect, useReducer, useState } from 'react';
import { Navigate, Route, Routes, useNavigate } from 'react-router-dom';
import { AppShell } from './components/AppShell';
import { DemoChatPage } from './pages/DemoChatPage';
import { LookupPage } from './pages/LookupPage';
import { fetchDemoInfo } from './services/demoApi';
import { conversationReducer, initialConversations, newId } from './utils/conversations';
import type { DemoInfo, DemoMessage } from './types/demo';

export default function App() {
  const navigate = useNavigate();
  const [state, dispatch] = useReducer(conversationReducer, undefined, () => initialConversations(newId()));
  const active = state.items.find(item => item.id === state.activeId)!;
  const [info, setInfo] = useState<DemoInfo | null>(null);
  const [infoError, setInfoError] = useState(false);
  const [infoAttempt, setInfoAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    fetchDemoInfo(controller.signal).then(value => { if (!controller.signal.aborted) { setInfo(value); setInfoError(false); } }).catch(() => { if (!controller.signal.aborted) setInfoError(true); });
    return () => controller.abort();
  }, [infoAttempt]);
  const setMessages = useCallback((update: DemoMessage[] | ((messages: DemoMessage[]) => DemoMessage[])) => {
    dispatch({ type: 'messages', id: state.activeId, update: messages => typeof update === 'function' ? update(messages) : update });
  }, [state.activeId]);
  const setInput = useCallback((value: string) => dispatch({ type: 'draft', id: state.activeId, value }), [state.activeId]);
  return <AppShell conversations={state.items} activeId={state.activeId} info={info} infoError={infoError} onRetryInfo={() => setInfoAttempt(value => value + 1)}
    onNew={() => { dispatch({ type: 'new', id: newId() }); navigate('/'); }}
    onSelect={id => { dispatch({ type: 'select', id }); navigate('/'); }}
    onDelete={id => dispatch({ type: 'delete', id, replacementId: newId() })}>
    <Routes>
      <Route path="/" element={<DemoChatPage key={active.id} messages={active.messages} setMessages={setMessages} input={active.draft} setInput={setInput} />} />
      <Route path="/lookup" element={<LookupPage info={info} />} />
      {['/demo', '/login', '/register', '/chat', '/chat/:sessionId', '*'].map(path => <Route key={path} path={path} element={<Navigate to="/" replace />} />)}
    </Routes>
  </AppShell>;
}
