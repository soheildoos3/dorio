import { Inbox, LoaderCircle, TriangleAlert } from 'lucide-react';
import type { ReactNode } from 'react';
import { Button } from './Button';

export function LoadingState({ label = 'در حال دریافت اطلاعات…' }: { label?: string }) {
  return <div className="flex min-h-40 items-center justify-center gap-2 text-sm text-slate-500"><LoaderCircle className="h-5 w-5 animate-spin" />{label}</div>;
}

export function EmptyState({ title = 'اطلاعاتی ثبت نشده', description, action }: { title?: string; description?: string; action?: ReactNode }) {
  return (
    <div className="flex min-h-48 flex-col items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-slate-50/60 p-8 text-center">
      <span className="mb-3 rounded-2xl bg-white p-3 text-slate-400 shadow-sm"><Inbox className="h-6 w-6" /></span>
      <p className="font-bold text-slate-800">{title}</p>
      {description && <p className="mt-1 max-w-md text-sm leading-6 text-slate-500">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof Error ? error.message : 'خطایی در دریافت اطلاعات رخ داد';
  return (
    <div className="flex min-h-48 flex-col items-center justify-center rounded-2xl border border-rose-100 bg-rose-50 p-8 text-center">
      <TriangleAlert className="mb-3 h-7 w-7 text-rose-500" />
      <p className="font-bold text-rose-900">دریافت اطلاعات ناموفق بود</p>
      <p className="mt-1 text-sm text-rose-700">{message}</p>
      {onRetry && <Button type="button" variant="secondary" className="mt-4" onClick={onRetry}>تلاش دوباره</Button>}
    </div>
  );
}
