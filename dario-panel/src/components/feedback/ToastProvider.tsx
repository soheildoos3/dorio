import { CheckCircle2, CircleAlert, Info, X, XCircle } from 'lucide-react';
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';

type ToastKind = 'success' | 'error' | 'info' | 'warning';
type Toast = { id: number; kind: ToastKind; title: string; message?: string };

type ToastContextValue = {
  push: (toast: Omit<Toast, 'id'>) => void;
  success: (title: string, message?: string) => void;
  error: (title: string, message?: string) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);

const styleMap: Record<ToastKind, { icon: typeof CheckCircle2; classes: string }> = {
  success: { icon: CheckCircle2, classes: 'border-emerald-200 bg-emerald-50 text-emerald-950' },
  error: { icon: XCircle, classes: 'border-rose-200 bg-rose-50 text-rose-950' },
  warning: { icon: CircleAlert, classes: 'border-amber-200 bg-amber-50 text-amber-950' },
  info: { icon: Info, classes: 'border-sky-200 bg-sky-50 text-sky-950' },
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const remove = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const push = useCallback((toast: Omit<Toast, 'id'>) => {
    const id = Date.now() + Math.floor(Math.random() * 1000);
    setToasts((current) => [...current, { ...toast, id }]);
    window.setTimeout(() => remove(id), 4500);
  }, [remove]);

  const value = useMemo<ToastContextValue>(() => ({
    push,
    success: (title, message) => push({ kind: 'success', title, message }),
    error: (title, message) => push({ kind: 'error', title, message }),
  }), [push]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="fixed left-4 top-4 z-[100] flex w-[min(92vw,380px)] flex-col gap-2" aria-live="polite">
        {toasts.map((toast) => {
          const preset = styleMap[toast.kind];
          const Icon = preset.icon;
          return (
            <div key={toast.id} className={`rounded-2xl border p-4 shadow-lg shadow-slate-900/5 ${preset.classes}`}>
              <div className="flex items-start gap-3">
                <Icon className="mt-0.5 h-5 w-5 shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="font-bold">{toast.title}</p>
                  {toast.message && <p className="mt-1 text-sm opacity-80">{toast.message}</p>}
                </div>
                <button type="button" onClick={() => remove(toast.id)} className="rounded-lg p-1 opacity-60 hover:bg-black/5 hover:opacity-100" aria-label="بستن پیام">
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) throw new Error('useToast must be used inside ToastProvider');
  return context;
}
