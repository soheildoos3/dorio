import type { ReactNode } from 'react';

type Tone = 'slate' | 'gray' | 'green' | 'red' | 'amber' | 'blue' | 'violet';
const tones: Record<Tone, string> = {
  slate: 'border-slate-200 bg-slate-100 text-slate-700',
  gray: 'border-slate-200 bg-slate-100 text-slate-700',
  green: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  red: 'border-rose-200 bg-rose-50 text-rose-700',
  amber: 'border-amber-200 bg-amber-50 text-amber-700',
  blue: 'border-sky-200 bg-sky-50 text-sky-700',
  violet: 'border-violet-200 bg-violet-50 text-violet-700',
};

export function Badge({ children, tone = 'slate' }: { children: ReactNode; tone?: Tone }) {
  return <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-bold leading-none ${tones[tone]}`}>{children}</span>;
}
