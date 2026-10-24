export type TabItem<T extends string> = { id: T; label: string; count?: number };

export function Tabs<T extends string>({ value, onChange, items }: { value: T; onChange: (value: T) => void; items: TabItem<T>[] }) {
  return (
    <div role="tablist" aria-label="بخش‌ها" className="panel-scrollbar flex snap-x gap-1 overflow-x-auto rounded-2xl border border-slate-200 bg-white p-1.5 shadow-sm">
      {items.map((item) => (
        <button
          type="button"
          role="tab"
          aria-selected={value === item.id}
          key={item.id}
          onClick={() => onChange(item.id)}
          className={`min-h-10 shrink-0 snap-start rounded-xl px-3.5 py-2 text-sm font-bold outline-none transition focus-visible:ring-4 focus-visible:ring-sky-100 ${value === item.id ? 'bg-slate-950 text-white shadow-sm' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-950'}`}
        >
          {item.label}
          {item.count !== undefined && <span className={`mr-2 text-xs ${value === item.id ? 'text-slate-300' : 'text-slate-400'}`}>{item.count.toLocaleString('fa-IR')}</span>}
        </button>
      ))}
    </div>
  );
}
