import { useState, type PropsWithChildren } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import { Icon } from './Icon';
import { Button, Dialog, IconButton } from './ui';
import { useTheme } from '../hooks/useTheme';
import { useViewportHeight } from '../hooks/useViewportHeight';
import { conversationTitle, type Conversation } from '../utils/conversations';
import { safeSourceUrl } from '../utils/documentSafety';
import type { DemoInfo } from '../types/demo';

interface AppShellProps {
  conversations: Conversation[];
  activeId: string;
  onNew: () => void;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  info: DemoInfo | null;
  infoError: boolean;
  onRetryInfo: () => void;
}

export function AppShell({ conversations, activeId, onNew, onSelect, onDelete, info, infoError, onRetryInfo, children }: PropsWithChildren<AppShellProps>) {
  const [collapsed, setCollapsed] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [infoOpen, setInfoOpen] = useState(false);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const { preference, changeTheme } = useTheme();
  const location = useLocation();
  useViewportHeight();
  const recent = conversations.filter(item => item.messages.length || item.draft.trim());
  const themeIcon = preference === 'system' ? 'monitor' : preference === 'dark' ? 'moon' : 'sun';
  const closeDrawer = () => setDrawerOpen(false);
  const newChat = () => { closeDrawer(); onNew(); };

  const sidebar = (compact: boolean) => <div className={`sidebar-content ${compact ? 'is-compact' : ''}`}>
    <Link to="/" className="brand" onClick={closeDrawer} aria-label="Hanoi Land Law AI — Trò chuyện"><Icon name="document" /><span>Hanoi Land Law AI</span></Link>
    <button className="navigation-item new-chat" onClick={newChat} title="Hội thoại mới"><Icon name="plus" /><span>Hội thoại mới</span></button>
    <nav aria-label="Điều hướng chính" className="primary-nav">
      <NavLink end to="/" className="navigation-item" title="Trò chuyện" onClick={closeDrawer}><Icon name="chat" /><span>Trò chuyện</span></NavLink>
      <NavLink to="/lookup" className="navigation-item" title="Thư viện văn bản" onClick={closeDrawer}><Icon name="document" /><span>Thư viện văn bản</span></NavLink>
    </nav>
    {!compact && <div className="recent-conversations">
      <h2>Gần đây</h2>
      {recent.length ? <ul>{recent.map(item => <li key={item.id} className={item.id === activeId && location.pathname === '/' ? 'selected' : ''}>
        <button className="conversation-item" aria-current={item.id === activeId && location.pathname === '/' ? 'true' : undefined} onClick={() => { closeDrawer(); onSelect(item.id); }} title={conversationTitle(item)}>{conversationTitle(item)}</button>
        <IconButton className="delete-conversation" label={`Xóa hội thoại: ${conversationTitle(item)}`} icon="trash" onClick={() => { closeDrawer(); setDeleteId(item.id); }} />
      </li>)}</ul> : <p className="metadata">Chưa có hội thoại</p>}
    </div>}
    <div className="sidebar-footer">
      {compact ? <IconButton label="Đổi giao diện" icon={themeIcon} onClick={() => changeTheme(preference === 'dark' ? 'light' : 'dark')} /> : <label className="theme-control"><Icon name={themeIcon} /><span className="sr-only">Giao diện</span><select aria-label="Giao diện" value={preference} onChange={event => changeTheme(event.target.value as typeof preference)}>
        <option value="system">Theo hệ thống</option><option value="light">Giao diện sáng</option><option value="dark">Giao diện tối</option>
      </select></label>}
      {!compact && <p className="caption">Chỉ lưu trong tab này.<br />Tải lại trang sẽ xóa hội thoại.</p>}
    </div>
  </div>;

  return <div className={`app-shell ${collapsed ? 'sidebar-collapsed' : ''}`}>
    <a href="#main-content" className="skip-link">Bỏ qua điều hướng</a>
    <aside className="desktop-sidebar" aria-label="Thanh bên">{sidebar(collapsed)}</aside>
    <div className="app-main">
      <header className="app-header">
        <div className="header-title"><IconButton className="desktop-only" icon="sidebar" label={collapsed ? 'Mở rộng thanh bên' : 'Thu gọn thanh bên'} aria-expanded={!collapsed} onClick={() => setCollapsed(value => !value)} /><IconButton className="mobile-only" icon="menu" label="Mở thanh bên" aria-expanded={drawerOpen} onClick={() => setDrawerOpen(true)} /><Link to={location.pathname === '/lookup' ? '/lookup' : '/'}>{location.pathname === '/lookup' ? 'Thư viện văn bản' : 'Hanoi Land Law AI'}</Link></div>
        <div className="header-actions"><button className="service-status" onClick={() => setInfoOpen(true)} aria-label="Thông tin kho dữ liệu"><span className="status-dot" /><span className="status-label">{info ? (info.llm_enabled ? 'Trả lời có nguồn' : 'Chế độ truy xuất') : infoError ? 'Kết nối gián đoạn' : 'Đang tải dữ liệu'}</span><Icon name="info" /></button><IconButton className="mobile-only" label="Hội thoại mới" icon="plus" onClick={newChat} /></div>
      </header>
      <div id="main-content" tabIndex={-1} className="route-content">{children}</div>
    </div>
    <Dialog open={drawerOpen} onClose={closeDrawer} title="Điều hướng" drawer>{sidebar(false)}</Dialog>
    <Dialog open={infoOpen} onClose={() => setInfoOpen(false)} title="Thông tin kho dữ liệu">
      <div className="corpus-info">
        <p className="notice">Đây là bản nghiên cứu, không phải tư vấn pháp lý. Hiệu lực và khả năng áp dụng của văn bản chưa được xác minh.</p>
        {info ? <><p><strong>{info.document_count} văn bản · {info.chunk_count} trích đoạn</strong></p><p className="metadata">{info.llm_enabled ? `Mô hình: ${info.model}` : 'Truy xuất từ khóa BM25 · Gemini đang tắt'}</p><ul className="corpus-documents">{info.documents.map(doc => <li key={doc.document_number}><strong>{doc.document_number}</strong><p>{doc.title}</p><a className="text-link" href={safeSourceUrl(doc.source_url)} target="_blank" rel="noopener noreferrer">Nguồn chính thức <Icon name="external" /></a></li>)}</ul><details><summary>Văn bản chưa có trong kho demo</summary><ul className="scope-limitations">{Object.keys(info.limitations).map(number => <li key={number}>{number} — chưa có bản trích đoạn hoàn chỉnh trong kho demo.</li>)}</ul></details><p className="caption">Giới hạn: {info.rate_limit_per_minute} câu/phút và {info.rate_limit_per_day} câu/ngày cho mỗi địa chỉ IP. Không lưu hội thoại trên máy chủ.</p></> : <><p>{infoError ? 'Không tải được thông tin kho dữ liệu.' : 'Đang tải thông tin…'}</p>{infoError && <Button onClick={onRetryInfo}>Thử lại</Button>}</>}
      </div>
    </Dialog>
    <Dialog open={deleteId !== null} onClose={() => setDeleteId(null)} title="Xóa hội thoại?">
      <p>Hội thoại này sẽ bị xóa khỏi tab đang mở. Bạn không thể khôi phục thao tác này.</p>
      <div className="dialog-actions"><Button onClick={() => setDeleteId(null)}>Hủy</Button><Button variant="primary" onClick={() => { if (deleteId) onDelete(deleteId); setDeleteId(null); }}>Xóa hội thoại</Button></div>
    </Dialog>
  </div>;
}
