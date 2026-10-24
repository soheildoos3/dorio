import { LoaderCircle } from 'lucide-react';
import type { ButtonHTMLAttributes, ReactNode } from 'react';

type Variant = 'primary' | 'secondary' | 'danger' | 'ghost';
type Size = 'sm' | 'md' | 'lg';

const variants: Record<Variant, string> = {
  primary: 'bg-slate-950 text-white shadow-sm shadow-slate-950/10 hover:bg-slate-800 focus-visible:ring-slate-300',
  secondary: 'border border-slate-200 bg-white text-slate-700 shadow-sm hover:border-slate-300 hover:bg-slate-50 focus-visible:ring-slate-200',
  danger: 'bg-rose-600 text-white shadow-sm shadow-rose-600/15 hover:bg-rose-700 focus-visible:ring-rose-200',
  ghost: 'text-slate-600 hover:bg-slate-100 hover:text-slate-950 focus-visible:ring-slate-200',
};

const sizes: Record<Size, string> = {
  sm: 'min-h-9 rounded-lg px-3 py-1.5 text-xs',
  md: 'min-h-10 rounded-xl px-4 py-2 text-sm',
  lg: 'min-h-12 rounded-xl px-5 py-2.5 text-sm',
};

export function Button({
  children,
  variant = 'primary',
  size = 'md',
  loading = false,
  className = '',
  disabled,
  type,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size; loading?: boolean; children: ReactNode }) {
  return (
    <button
      {...props}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={`inline-flex shrink-0 items-center justify-center gap-2 font-bold transition duration-200 focus:outline-none focus-visible:ring-4 disabled:cursor-not-allowed disabled:opacity-50 active:scale-[.98] ${variants[variant]} ${sizes[size]} ${className}`}
    >
      {loading && <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden="true" />}
      {children}
    </button>
  );
}
