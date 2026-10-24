import type { ReactNode } from 'react';

export function PageHeader({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0">
        <h1 className="text-[1.55rem] font-black tracking-tight text-slate-950 sm:text-3xl">{title}</h1>
        {description && <p className="mt-2 max-w-3xl text-sm leading-7 text-slate-500 sm:text-[15px]">{description}</p>}
      </div>
      {action && <div className="flex w-full flex-wrap gap-2 sm:w-auto sm:shrink-0 sm:justify-end max-sm:[&>button]:flex-1">{action}</div>}
    </div>
  );
}

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-[0_1px_2px_rgba(15,23,42,.03),0_8px_30px_rgba(15,23,42,.025)] ${className}`}>{children}</section>;
}

export function CardHeader({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col gap-3 border-b border-slate-100 px-4 py-4 sm:flex-row sm:items-start sm:justify-between sm:px-5">
      <div className="min-w-0">
        <h2 className="font-black text-slate-900">{title}</h2>
        {description && <p className="mt-1.5 text-xs leading-6 text-slate-500 sm:text-sm">{description}</p>}
      </div>
      {action && <div className="flex w-full flex-wrap gap-2 sm:w-auto sm:shrink-0 sm:justify-end max-sm:[&>button]:flex-1">{action}</div>}
    </div>
  );
}
