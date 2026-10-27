import { useEffect, useId, useRef, type ButtonHTMLAttributes, type InputHTMLAttributes, type PropsWithChildren } from 'react';
import { Icon, type IconName } from './Icon';

export function Button({ className = '', variant = 'secondary', type = 'button', ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'ghost' }) {
  return <button type={type} className={`button button--${variant} ${className}`} {...props} />;
}

export function IconButton({ label, icon, className = '', ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { label: string; icon: IconName }) {
  return <button type="button" aria-label={label} title={label} className={`icon-button ${className}`} {...props}><Icon name={icon} /></button>;
}

export function Input({ className = '', ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={`input ${className}`} {...props} />;
}

export function Badge({ className = '', children }: PropsWithChildren<{ className?: string }>) {
  return <span className={`badge ${className}`}>{children}</span>;
}

export function Loading({ children = 'Đang tải dữ liệu…' }: PropsWithChildren) {
  return <div role="status" className="loading"><span className="spinner" aria-hidden="true" />{children}</div>;
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return <div role="alert" className="error-state"><Icon name="info" /><div><p>{message}</p>{onRetry && <Button onClick={onRetry}>Thử lại</Button>}</div></div>;
}

export function Dialog({ open, onClose, title, children, drawer = false }: PropsWithChildren<{ open: boolean; onClose: () => void; title: string; drawer?: boolean }>) {
  const ref = useRef<HTMLDialogElement>(null);
  const heading = useId();
  useEffect(() => {
    const dialog = ref.current;
    if (open && dialog && !dialog.open) dialog.showModal();
    return () => { if (dialog?.open) dialog.close(); };
  }, [open]);
  return <dialog ref={ref} aria-labelledby={heading} className={drawer ? 'drawer-dialog' : 'modal-dialog'} onCancel={event => { event.preventDefault(); onClose(); }} onClick={event => {
    const rect = event.currentTarget.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) onClose();
  }}>
    <div className="dialog-heading"><h2 id={heading}>{title}</h2><IconButton label={drawer ? 'Đóng thanh bên' : 'Đóng hộp thoại'} icon="close" onClick={onClose} /></div>
    {children}
  </dialog>;
}
