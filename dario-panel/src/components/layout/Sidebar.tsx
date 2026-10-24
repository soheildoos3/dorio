import { Boxes, ClipboardCheck, Gauge, PackageSearch, Settings2, ShieldCheck, Users, Warehouse, X, Scissors, LogOut, Truck, ShieldPlus, ChevronLeft, Factory, Landmark, ReceiptText } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../../auth/AuthProvider';

const all = [
  { to: '/', label: 'داشبورد', icon: Gauge, p: 'dashboard.view', group: 'اصلی' },
  { to: '/catalog', label: 'کاتالوگ', icon: PackageSearch, p: 'catalog.view', group: 'اصلی' },
  { to: '/warehouses', label: 'انبار و مکان‌ها', icon: Warehouse, p: 'warehouse.view', group: 'انبار' },
  { to: '/inventory', label: 'موجودی', icon: Boxes, p: 'inventory.view', group: 'انبار' },
  { to: '/outbound', label: 'خروج انبار', icon: Truck, p: 'inventory.outbound', all: ['inventory.view', 'inventory.outbound'], group: 'انبار' },
  { to: '/operations', label: 'عملیات انبار', icon: ClipboardCheck, p: 'inventory.view', group: 'انبار' },
  { to: '/quality', label: 'کنترل کیفیت', icon: ShieldCheck, p: 'quality.view', group: 'عملیات' },
  { to: '/warranty', label: 'گارانتی', icon: ShieldPlus, p: 'warranty.view', group: 'عملیات' },
  { to: '/tailors', label: 'خیاط‌ها', icon: Scissors, p: 'tailors.view', group: 'عملیات' },
  { to: '/sales', label: 'فروش و مرجوعی', icon: ReceiptText, p: 'sales.view', group: 'فروش' },
  { to: '/manufacturing', label: 'تولید و مواد', icon: Factory, p: 'manufacturing.view', group: 'تولید و مالی' },
  { to: '/accounting', label: 'حسابداری', icon: Landmark, p: 'accounting.view', group: 'تولید و مالی' },
  { to: '/users', label: 'کاربران', icon: Users, p: 'users.view', group: 'مدیریت' },
  { to: '/management', label: 'تنظیمات سازمانی', icon: Settings2, group: 'مدیریت' },
];

export function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { auth, can, logout } = useAuth();
  const isAdmin = !!auth && (auth.user.is_superuser || auth.user.role?.code === 'admin');
  const items = all.filter((x) => x.to === '/users' ? can('users.view') : x.to === '/management' ? (isAdmin || can('channels.manage') || can('hr.manage')) : 'all' in x && x.all ? x.all.every(can) : !x.p || can(x.p));
  const groups = [...new Set(items.map((x) => x.group))];
  const initials = auth?.user.full_name?.trim().slice(0, 1) || 'D';

  return <>
    {open && <button type="button" aria-label="بستن منو" className="fixed inset-0 z-40 bg-slate-950/50 backdrop-blur-[1px] lg:hidden" onClick={onClose} />}
    <aside className={`fixed inset-y-0 right-0 z-50 flex w-[min(18rem,88vw)] flex-col border-l border-slate-800/80 bg-slate-950 text-white shadow-2xl transition-transform duration-300 lg:w-72 lg:translate-x-0 lg:shadow-none ${open ? 'translate-x-0' : 'translate-x-full'}`}>
      <div className="flex h-[4.5rem] items-center justify-between border-b border-slate-800 px-4">
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-2xl bg-white text-sm font-black text-slate-950">D</span>
          <div><p className="text-base font-black tracking-tight">Dario</p><p className="mt-0.5 text-[11px] text-slate-400">پنل عملیات و انبار</p></div>
        </div>
        <button type="button" onClick={onClose} className="grid h-10 w-10 place-items-center rounded-xl text-slate-400 hover:bg-slate-900 hover:text-white lg:hidden" aria-label="بستن منو"><X className="h-5 w-5" /></button>
      </div>

      <nav className="panel-scrollbar flex-1 overflow-y-auto px-3 py-4">
        {groups.map((group) => <div key={group} className="mb-5 last:mb-0">
          <p className="mb-2 px-3 text-[10px] font-bold tracking-wide text-slate-500">{group}</p>
          <div className="space-y-1">
            {items.filter((x) => x.group === group).map(({ to, label, icon: Icon }) => <NavLink
              key={to}
              to={to}
              end={to === '/'}
              onClick={onClose}
              className={({ isActive }) => `group flex min-h-11 items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-bold outline-none transition focus-visible:ring-2 focus-visible:ring-sky-400 ${isActive ? 'bg-white text-slate-950 shadow-sm' : 'text-slate-300 hover:bg-slate-900 hover:text-white'}`}
            >
              {({ isActive }) => <>
                <span className={`grid h-8 w-8 shrink-0 place-items-center rounded-lg ${isActive ? 'bg-slate-100 text-slate-950' : 'bg-slate-900 text-slate-400 group-hover:text-white'}`}><Icon className="h-4 w-4" /></span>
                <span className="min-w-0 flex-1 truncate">{label}</span>
                <ChevronLeft className={`h-4 w-4 transition ${isActive ? 'opacity-60' : 'opacity-0 group-hover:opacity-40'}`} />
              </>}
            </NavLink>)}
          </div>
        </div>)}
      </nav>

      <div className="border-t border-slate-800 p-3 pb-[max(.75rem,env(safe-area-inset-bottom))]">
        <div className="mb-2 flex items-center gap-3 rounded-xl bg-slate-900/80 p-3">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-slate-800 text-sm font-black">{initials}</span>
          <div className="min-w-0"><p className="truncate text-sm font-bold text-white">{auth?.user.full_name}</p><p className="mt-0.5 truncate text-[11px] text-slate-400">{auth?.user.role?.name || (auth?.user.is_superuser ? 'مدیر کل' : 'کاربر پنل')}</p></div>
        </div>
        <button onClick={() => void logout()} className="flex min-h-10 w-full items-center gap-2 rounded-xl px-3 text-sm font-bold text-rose-300 transition hover:bg-rose-500/10 hover:text-rose-200"><LogOut className="h-4 w-4" />خروج از حساب</button>
      </div>
    </aside>
  </>;
}
