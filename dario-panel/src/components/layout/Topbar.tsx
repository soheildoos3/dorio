import { useQuery } from '@tanstack/react-query';
import { Command, Menu, Search, Wifi, WifiOff, X } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthProvider';
import { apiRequest } from '../../lib/api';

type RouteItem = {
  path: string;
  label: string;
  permission?: string;
  allPermissions?: string[];
  management?: boolean;
};

const routes: RouteItem[] = [
  { path: '/', label: 'داشبورد', permission: 'dashboard.view' },
  { path: '/catalog', label: 'کاتالوگ محصولات', permission: 'catalog.view' },
  { path: '/warehouses', label: 'انبار و مکان‌ها', permission: 'warehouse.view' },
  { path: '/inventory', label: 'موجودی و رزرو', permission: 'inventory.view' },
  { path: '/outbound', label: 'خروج انبار', allPermissions: ['inventory.view', 'inventory.outbound'] },
  { path: '/operations', label: 'عملیات انبار', permission: 'inventory.view' },
  { path: '/quality', label: 'کنترل کیفیت', permission: 'quality.view' },
  { path: '/warranty', label: 'گارانتی', permission: 'warranty.view' },
  { path: '/tailors', label: 'خیاط‌ها', permission: 'tailors.view' },
  { path: '/sales', label: 'فروش و مرجوعی', permission: 'sales.view' },
  { path: '/manufacturing', label: 'تولید و مواد', permission: 'manufacturing.view' },
  { path: '/accounting', label: 'حسابداری', permission: 'accounting.view' },
  { path: '/users', label: 'کاربران', permission: 'users.view' },
  { path: '/management', label: 'تنظیمات سازمانی', management: true },
];

export function Topbar({ onMenu }: { onMenu: () => void }) {
  const location = useLocation();
  const navigate = useNavigate();
  const { auth, can } = useAuth();
  const [query, setQuery] = useState('');
  const boxRef = useRef<HTMLDivElement>(null);
  const isAdmin = !!auth && (auth.user.is_superuser || auth.user.role?.code === 'admin');
  const canManage = isAdmin || can('channels.manage') || can('hr.manage');
  const health = useQuery({
    queryKey: ['system', 'health'],
    queryFn: () => apiRequest<{ status: string; version?: string }>('/health'),
    retry: false,
    refetchInterval: 60_000,
    refetchOnWindowFocus: true,
  });

  const visibleRoutes = useMemo(() => routes.filter((route) => {
    if (route.management) return canManage;
    if (route.allPermissions) return route.allPermissions.every(can);
    return !route.permission || can(route.permission);
  }), [can, canManage]);

  const currentRoute = [...routes]
    .sort((a, b) => b.path.length - a.path.length)
    .find((route) => route.path === '/' ? location.pathname === '/' : location.pathname.startsWith(route.path));
  const title = currentRoute?.label || 'Dario';
  const matches = useMemo(
    () => query.trim() ? visibleRoutes.filter((route) => route.label.includes(query.trim())) : [],
    [query, visibleRoutes],
  );

  useEffect(() => {
    const onPointer = (event: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(event.target as Node)) setQuery('');
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setQuery('');
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        boxRef.current?.querySelector('input')?.focus();
      }
    };
    document.addEventListener('mousedown', onPointer);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onPointer);
      document.removeEventListener('keydown', onKey);
    };
  }, []);

  const online = health.isSuccess && health.data.status === 'ok';

  return (
    <header className="sticky top-0 z-30 border-b border-slate-200/80 bg-white/90 backdrop-blur-xl supports-[backdrop-filter]:bg-white/80">
      <div className="mx-auto flex h-[4.5rem] max-w-[1600px] items-center gap-2.5 px-3 sm:px-5 lg:px-8">
        <button type="button" className="grid h-10 w-10 shrink-0 place-items-center rounded-xl text-slate-600 outline-none transition hover:bg-slate-100 hover:text-slate-950 focus-visible:ring-4 focus-visible:ring-sky-100 lg:hidden" onClick={onMenu} aria-label="باز کردن منو"><Menu className="h-5 w-5" /></button>
        <div className="hidden min-w-36 lg:block"><p className="text-sm font-black text-slate-900">{title}</p><p className="mt-0.5 text-[11px] text-slate-400">Dario Operations</p></div>

        <div ref={boxRef} className="relative mx-auto min-w-0 w-full max-w-2xl">
          <Search className="pointer-events-none absolute right-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="جستجو در بخش‌های پنل…"
            aria-label="جستجو در بخش‌های پنل"
            className="h-11 w-full rounded-xl border border-slate-200 bg-slate-50 pr-10 pl-10 text-sm outline-none transition placeholder:text-slate-400 hover:border-slate-300 focus:border-sky-300 focus:bg-white focus:ring-4 focus:ring-sky-100"
          />
          {query && <button type="button" onClick={() => setQuery('')} className="absolute left-2.5 top-1/2 grid h-7 w-7 -translate-y-1/2 place-items-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-700" aria-label="پاک کردن جستجو"><X className="h-4 w-4" /></button>}
          {!query && <span className="pointer-events-none absolute left-3 top-1/2 hidden -translate-y-1/2 items-center gap-1 rounded-md border border-slate-200 bg-white px-1.5 py-0.5 text-[10px] text-slate-400 md:flex"><Command className="h-3 w-3" />K</span>}

          {query.trim() && (
            <div className="absolute top-[calc(100%+8px)] z-40 w-full overflow-hidden rounded-2xl border border-slate-200 bg-white p-2 shadow-2xl shadow-slate-950/10">
              {matches.length > 0 ? matches.map((item) => (
                <button key={item.path} type="button" onClick={() => { navigate(item.path); setQuery(''); }} className="flex min-h-11 w-full items-center justify-between rounded-xl px-3 text-right text-sm font-bold text-slate-700 transition hover:bg-slate-100 hover:text-slate-950">
                  <span>{item.label}</span><span className="text-[10px] font-normal text-slate-400">باز کردن</span>
                </button>
              )) : <div className="px-3 py-5 text-center text-sm text-slate-500">بخشی با این عنوان پیدا نشد.</div>}
            </div>
          )}
        </div>

        <div title={online ? `اتصال برقرار${health.data.version ? ` · API ${health.data.version}` : ''}` : 'اتصال سرویس در دسترس نیست'} className={`hidden shrink-0 items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-bold sm:flex ${online ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : health.isLoading ? 'border-slate-200 bg-slate-50 text-slate-500' : 'border-rose-200 bg-rose-50 text-rose-700'}`}>
          {online ? <Wifi className="h-3.5 w-3.5" /> : <WifiOff className="h-3.5 w-3.5" />}
          {online ? 'متصل' : health.isLoading ? 'بررسی اتصال' : 'قطع ارتباط'}
        </div>
      </div>
    </header>
  );
}
