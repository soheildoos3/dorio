import { X } from 'lucide-react';
import { useEffect, useRef, type ReactNode } from 'react';

export function Modal({ open, onClose, title, description, children, size = 'lg' }: {
  open: boolean; onClose: () => void; title: string; description?: string; children: ReactNode; size?: 'md' | 'lg' | 'xl';
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);

  // Keep the latest close handler without making the focus-management effect
  // restart on every parent render. Most callers pass inline callbacks, so using
  // `onClose` directly as an effect dependency would steal focus on every
  // keystroke in controlled form fields.
  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!open) return;

    const previous = document.activeElement as HTMLElement | null;
    const listener = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onCloseRef.current();
    };

    document.addEventListener('keydown', listener);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const focusTimer = window.setTimeout(() => {
      // Do not override focus if the user/browser already focused something
      // inside the modal (for example via autoFocus or fast pointer input).
      if (panelRef.current?.contains(document.activeElement)) return;
      const focusable = panelRef.current?.querySelector<HTMLElement>(
        'input:not([disabled]), select:not([disabled]), textarea:not([disabled]), button:not([disabled])',
      );
      focusable?.focus();
    }, 0);

    return () => {
      window.clearTimeout(focusTimer);
      document.removeEventListener('keydown', listener);
      document.body.style.overflow = previousOverflow;
      if (previous?.isConnected) previous.focus?.();
    };
  }, [open]);

  if (!open) return null;
  const width = { md: 'max-w-xl', lg: 'max-w-2xl', xl: 'max-w-4xl' }[size];

  return (
    <div className="fixed inset-0 z-[70] flex items-end justify-center bg-slate-950/55 p-0 backdrop-blur-[2px] sm:items-center sm:p-6" role="dialog" aria-modal="true" aria-label={title}>
      <button type="button" className="absolute inset-0 cursor-default" aria-label="بستن پنجره" onClick={onClose} />
      <div ref={panelRef} className={`relative z-10 max-h-[94dvh] w-full ${width} overflow-hidden rounded-t-[1.75rem] bg-white shadow-2xl sm:max-h-[90vh] sm:rounded-3xl`}>
        <div className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-slate-100 bg-white/95 px-4 py-4 backdrop-blur sm:px-6">
          <div className="min-w-0">
            <h2 className="text-lg font-black text-slate-950">{title}</h2>
            {description && <p className="mt-1 text-sm leading-6 text-slate-500">{description}</p>}
          </div>
          <button type="button" onClick={onClose} className="grid h-10 w-10 shrink-0 place-items-center rounded-xl text-slate-500 outline-none transition hover:bg-slate-100 hover:text-slate-950 focus-visible:ring-4 focus-visible:ring-sky-100" aria-label="بستن">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="panel-scrollbar max-h-[calc(94dvh-73px)] overflow-y-auto overscroll-contain p-4 pb-[max(1rem,env(safe-area-inset-bottom))] sm:max-h-[calc(90vh-73px)] sm:p-6">{children}</div>
      </div>
    </div>
  );
}
