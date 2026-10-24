import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useMemo, useState, type FormEvent } from 'react';
import { CheckCircle2, Clock3, Pencil, Printer, RefreshCw, Search, Settings2, ShieldCheck, ShieldPlus } from 'lucide-react';
import { adminApi } from '../api/admin';
import type { Warranty, WarrantySetting } from '../api/types';
import { useAuth } from '../auth/AuthProvider';
import { useToast } from '../components/feedback/ToastProvider';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Field, Input, Select, Switch, Textarea } from '../components/ui/Field';
import { Modal } from '../components/ui/Modal';
import { Card, CardHeader, PageHeader } from '../components/ui/Page';
import { EmptyState, ErrorState, LoadingState } from '../components/ui/States';
import { dateTimeFa, numberFa } from '../lib/format';
import { loadQrPrintSettings } from '../lib/qrPrint';

const statusLabel: Record<string, string> = { inactive: 'در انبار / غیرفعال', grace: 'مهلت فعال‌سازی', active: 'فعال', expired: 'منقضی', returned: 'مرجوع‌شده', void: 'باطل' };
const statusTone = (s: string): 'slate' | 'amber' | 'green' | 'red' | 'blue' => s === 'active' ? 'green' : s === 'grace' ? 'amber' : s === 'void' || s === 'expired' ? 'red' : s === 'returned' ? 'blue' : s === 'inactive' ? 'slate' : 'blue';

export function WarrantyPage() {
  const { can } = useAuth();
  const manage = can('warranty.manage');
  const toast = useToast();
  const client = useQueryClient();
  const q = useQuery({ queryKey: ['warranty'], queryFn: adminApi.warranties });
  const settings = useQuery({ queryKey: ['warranty', 'settings'], queryFn: adminApi.settings });
  const [editing, setEditing] = useState<Warranty | null>(null);
  const [open, setOpen] = useState(false);
  const [urlOpen, setUrlOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const defaultBase = (import.meta.env.VITE_WARRANTY_BASE_URL || (import.meta.env.DEV ? `${window.location.protocol}//${window.location.hostname}:5174/warranty` : `${window.location.origin}/warranty`)).replace(/\/$/, '');
  const currentSetting = settings.data?.find((x) => x.is_default) || settings.data?.[0] || null;
  const [settingEditing, setSettingEditing] = useState<WarrantySetting | null>(null);
  const [f, setF] = useState({ status: 'inactive', warranty_months: 12, customer_name: '', customer_phone: '', qr_redirect_url: '', notes: '' });
  const [u, setU] = useState({ name: 'صفحه گارانتی', base_url: defaultBase, qr_base_url: '', qr_destination_template: '', grace_period_months: 6, is_default: true });

  const counts = useMemo(() => Object.fromEntries(['inactive', 'grace', 'active', 'expired', 'returned', 'void'].map((s) => [s, q.data?.filter((x) => x.status === s).length || 0])), [q.data]);
  const rows = useMemo(() => {
    const term = query.trim().toLowerCase();
    return (q.data || []).filter((w) => {
      if (statusFilter !== 'all' && w.status !== statusFilter) return false;
      if (!term) return true;
      return [w.serial, w.customer_name, w.customer_phone].some((v) => String(v || '').toLowerCase().includes(term));
    });
  }, [q.data, query, statusFilter]);

  const save = useMutation({ mutationFn: () => { if (!editing) return Promise.reject(new Error('گارانتی برای ویرایش انتخاب نشده است')); const allowed = ['inactive', 'grace', 'active', 'expired', 'void']; return adminApi.updateWarranty(editing.id, { ...(allowed.includes(f.status) ? { status: f.status } : {}), warranty_months: f.warranty_months, customer_name: f.customer_name || null, customer_phone: f.customer_phone || null, qr_redirect_url: f.qr_redirect_url || null, notes: f.notes || null }); }, onSuccess: async () => { await client.invalidateQueries({ queryKey: ['warranty'] }); setOpen(false); toast.success('گارانتی ذخیره شد'); }, onError: (e) => toast.error('ذخیره گارانتی ناموفق', e instanceof Error ? e.message : '') });
  const activate = useMutation({ mutationFn: (w: Warranty) => adminApi.activateWarranty(w.id), onSuccess: async () => { await client.invalidateQueries({ queryKey: ['warranty'] }); toast.success('گارانتی فعال شد'); }, onError: (e) => toast.error('فعال‌سازی ناموفق', e instanceof Error ? e.message : '') });
  const refresh = useMutation({ mutationFn: adminApi.refreshWarranties, onSuccess: async (r) => { await client.invalidateQueries({ queryKey: ['warranty'] }); toast.success(`${numberFa(r.activated)} گارانتی خودکار فعال شد`); }, onError: (e) => toast.error('به‌روزرسانی خودکار ناموفق بود', e instanceof Error ? e.message : '') });
  const printMutation = useMutation({ mutationFn: (w: Warranty) => adminApi.printWarrantyLog(w.id), onSuccess: () => toast.success('لاگ چاپ QR محصول ثبت شد'), onError: (e) => toast.error('صفحه چاپ باز شد، اما ثبت لاگ ناموفق بود', e instanceof Error ? e.message : '') });
  const printWarranty = (w: Warranty) => { adminApi.printWarranty(w.id, loadQrPrintSettings()); if (manage) printMutation.mutate(w); };
  const saveSetting = useMutation({ mutationFn: () => settingEditing ? adminApi.updateSetting(settingEditing.id, u) : adminApi.createSetting(u), onSuccess: async () => { await client.invalidateQueries({ queryKey: ['warranty', 'settings'] }); setUrlOpen(false); toast.success('تنظیمات گارانتی ذخیره شد'); }, onError: (e) => toast.error('ذخیره تنظیمات ناموفق', e instanceof Error ? e.message : '') });

  function edit(w: Warranty) {
    setEditing(w);
    setF({ status: w.status, warranty_months: w.warranty_months, customer_name: w.customer_name || '', customer_phone: w.customer_phone || '', qr_redirect_url: w.qr_redirect_url || '', notes: w.notes || '' });
    setOpen(true);
  }

  function openSettings() {
    setSettingEditing(currentSetting);
    setU(currentSetting ? { name: currentSetting.name, base_url: currentSetting.base_url, qr_base_url: currentSetting.qr_base_url || '', qr_destination_template: currentSetting.qr_destination_template || '', grace_period_months: currentSetting.grace_period_months, is_default: currentSetting.is_default } : { name: 'صفحه گارانتی', base_url: defaultBase, qr_base_url: '', qr_destination_template: '', grace_period_months: 6, is_default: true });
    setUrlOpen(true);
  }

  const stats = [
    { status: 'inactive', label: 'در انبار', icon: ShieldPlus, tone: 'bg-slate-100 text-slate-600' },
    { status: 'grace', label: 'در مهلت خواب', icon: Clock3, tone: 'bg-amber-50 text-amber-600' },
    { status: 'active', label: 'فعال', icon: ShieldCheck, tone: 'bg-emerald-50 text-emerald-600' },
    { status: 'expired', label: 'منقضی', icon: Clock3, tone: 'bg-rose-50 text-rose-600' },
    { status: 'returned', label: 'مرجوع‌شده', icon: RefreshCw, tone: 'bg-sky-50 text-sky-700' },
    { status: 'void', label: 'باطل', icon: ShieldPlus, tone: 'bg-slate-100 text-slate-500' },
  ];

  return <div className="space-y-6">
    <PageHeader title="گارانتی" description="چرخه گارانتی از زمان حضور کالا در انبار تا خروج، مهلت فعال‌سازی مشتری و فعال‌سازی خودکار مدیریت می‌شود." />

    <div className="grid gap-3 grid-cols-2 md:grid-cols-3 xl:grid-cols-6">
      {stats.map(({ status, label, icon: Icon, tone }) => <button key={status} type="button" onClick={() => setStatusFilter(statusFilter === status ? 'all' : status)} className={`rounded-2xl border bg-white p-4 text-right shadow-sm outline-none transition hover:-translate-y-0.5 hover:shadow-md focus-visible:ring-4 focus-visible:ring-sky-100 ${statusFilter === status ? 'border-slate-950 ring-1 ring-slate-950' : 'border-slate-200'}`}>
        <div className="flex items-center justify-between gap-3"><span className={`grid h-9 w-9 place-items-center rounded-xl ${tone}`}><Icon className="h-4 w-4" /></span><span className="text-2xl font-black text-slate-950">{numberFa(counts[status] || 0)}</span></div>
        <p className="mt-3 text-xs font-bold text-slate-600">{label}</p>
      </button>)}
    </div>

    <Card>
      <CardHeader title="تنظیمات چرخه گارانتی" description={`QR پویا: ${currentSetting?.qr_base_url || 'دامنه فعلی API'} → ${currentSetting?.qr_destination_template || currentSetting?.base_url || defaultBase} · مهلت خواب: ${currentSetting?.grace_period_months ?? 6} ماه`} action={manage ? <div className="flex flex-wrap gap-2"><Button variant="secondary" onClick={() => refresh.mutate()} loading={refresh.isPending}><RefreshCw className="h-4 w-4" />به‌روزرسانی خودکار</Button><Button onClick={openSettings}><Settings2 className="h-4 w-4" />تنظیمات</Button></div> : undefined} />
    </Card>

    <Card>
      <div className="grid gap-3 border-b border-slate-100 p-4 sm:grid-cols-[minmax(0,1fr)_220px]">
        <div className="relative"><Search className="pointer-events-none absolute right-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" /><Input className="pr-10" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="جستجو سریال، نام یا تلفن مشتری…" /></div>
        <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}><option value="all">همه وضعیت‌ها</option>{Object.entries(statusLabel).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</Select>
      </div>
      {q.isLoading ? <LoadingState label="در حال دریافت گارانتی‌ها…" /> : q.isError ? <div className="p-4"><ErrorState error={q.error} onRetry={() => q.refetch()} /></div> : rows.length === 0 ? <div className="p-4"><EmptyState title="گارانتی مطابق فیلتر پیدا نشد" description="عبارت جستجو یا وضعیت انتخابی را تغییر دهید." /></div> : <div className="overflow-x-auto">
        <table className="w-full min-w-[1150px] text-sm">
          <thead className="bg-slate-50"><tr><th className="p-3 text-right">سریال</th><th>وضعیت</th><th>خروج</th><th>فعال‌سازی خودکار</th><th>شروع</th><th>پایان</th><th>مدت</th><th>عملیات</th></tr></thead>
          <tbody>{rows.map((w) => <tr key={w.id} className="border-t border-slate-100"><td className="p-3"><p className="font-bold text-slate-900" dir="ltr">{w.serial}</p>{w.customer_name && <p className="mt-1 text-xs text-slate-500">{w.customer_name}</p>}</td><td className="text-center"><Badge tone={statusTone(w.status)}>{statusLabel[w.status] || w.status}</Badge></td><td className="text-center text-xs text-slate-600">{dateTimeFa(w.outbound_at)}</td><td className="text-center text-xs text-slate-600">{dateTimeFa(w.auto_activate_at)}</td><td className="text-center text-xs text-slate-600">{dateTimeFa(w.activated_at)}</td><td className="text-center text-xs text-slate-600">{dateTimeFa(w.expires_at)}</td><td className="text-center font-bold">{numberFa(w.warranty_months)} ماه</td><td className="p-2"><div className="flex justify-center gap-1">{manage && w.status === 'grace' && <Button size="sm" onClick={() => activate.mutate(w)}><CheckCircle2 className="h-4 w-4" />فعال</Button>}{manage && <Button size="sm" variant="ghost" onClick={() => edit(w)} aria-label="ویرایش گارانتی"><Pencil className="h-4 w-4" /></Button>}<Button size="sm" variant="secondary" onClick={() => printWarranty(w)}><Printer className="h-4 w-4" />QR محصول</Button></div></td></tr>)}</tbody>
        </table>
      </div>}
    </Card>

    <Modal open={open} onClose={() => setOpen(false)} title="ویرایش گارانتی">
      <form onSubmit={(e: FormEvent) => { e.preventDefault(); save.mutate(); }} className="space-y-4">
        <Field label="سریال"><Input disabled dir="ltr" value={editing?.serial || ''} /></Field>
        <div className="grid gap-4 sm:grid-cols-2"><Field label="وضعیت"><Select value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })}><option value="inactive">در انبار</option><option value="grace">مهلت فعال‌سازی</option><option value="active">فعال</option><option value="expired">منقضی</option><option value="void">باطل</option>{f.status === 'returned' && <option value="returned" disabled>مرجوع‌شده (وضعیت سیستمی)</option>}</Select></Field><Field label="مدت گارانتی (ماه)"><Input type="number" min={1} max={120} value={f.warranty_months} onChange={(e) => setF({ ...f, warranty_months: Number(e.target.value) })} /></Field></div>
        <div className="grid gap-4 sm:grid-cols-2"><Field label="نام مشتری"><Input value={f.customer_name} onChange={(e) => setF({ ...f, customer_name: e.target.value })} /></Field><Field label="تلفن"><Input dir="ltr" value={f.customer_phone} onChange={(e) => setF({ ...f, customer_phone: e.target.value })} /></Field></div>
        <Field label="مقصد اختصاصی QR این سریال" hint="اختیاری. اگر وارد شود فقط همین سریال به این صفحه هدایت می‌شود؛ با پاک‌کردن آن دوباره از مقصد عمومی استفاده می‌کند."><Input dir="ltr" value={f.qr_redirect_url} onChange={(e) => setF({ ...f, qr_redirect_url: e.target.value })} placeholder="https://example.com/custom-page" /></Field>
        <Field label="یادداشت"><Textarea value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} /></Field>
        <Button className="w-full" type="submit" loading={save.isPending}>ذخیره تغییرات</Button>
      </form>
    </Modal>

    <Modal open={urlOpen} onClose={() => setUrlOpen(false)} title="تنظیمات QR پویا و گارانتی" description="QR چاپ‌شده فقط به resolver ثابت سریال اشاره می‌کند؛ مقصد واقعی را هر زمان بخواهید بدون چاپ دوباره تغییر دهید.">
      <form onSubmit={(e: FormEvent) => { e.preventDefault(); saveSetting.mutate(); }} className="space-y-4">
        <Field label="عنوان"><Input value={u.name} onChange={(e) => setU({ ...u, name: e.target.value })} /></Field>
        <Field label="آدرس پیش‌فرض صفحه گارانتی" hint="اگر مقصد اختصاصی QR خالی باشد، سریال به انتهای این آدرس اضافه می‌شود."><Input dir="ltr" value={u.base_url} onChange={(e) => setU({ ...u, base_url: e.target.value })} placeholder="https://warranty.example.com/warranty" /></Field>
        <Field label="دامنه ثابت QR (Resolver)" hint="این آدرس داخل QR چاپ می‌شود و باید در طول عمر لیبل ثابت بماند. اگر خالی باشد، دامنه عمومی همین API استفاده می‌شود."><Input dir="ltr" value={u.qr_base_url} onChange={(e) => setU({ ...u, qr_base_url: e.target.value })} placeholder="https://qr.example.com" /></Field>
        <Field label="مقصد پویای QR" hint="اختیاری. {serial} با سریال یکتا جایگزین می‌شود. با تغییر این فیلد، QRهای قبلاً چاپ‌شده هم به مقصد جدید می‌روند."><Input dir="ltr" value={u.qr_destination_template} onChange={(e) => setU({ ...u, qr_destination_template: e.target.value })} placeholder="https://site.example.com/product/{serial}" /></Field>
        <div className="rounded-xl border border-sky-200 bg-sky-50 p-3 text-xs leading-6 text-sky-900">نمونه مسیر چاپ‌شده: <span dir="ltr" className="font-mono">{(u.qr_base_url || 'https://your-api.example.com').replace(/\/$/,'')}/q/SERIAL</span><br/>این مسیر ثابت می‌ماند؛ فقط مقصد پشت آن تغییر می‌کند.</div>
        <Field label="مهلت خواب بعد از خروج (ماه)" hint="اگر مشتری در این بازه فعال نکند، گارانتی در پایان مهلت به‌صورت خودکار فعال می‌شود."><Input type="number" min={0} max={36} value={u.grace_period_months} onChange={(e) => setU({ ...u, grace_period_months: Number(e.target.value) })} /></Field>
        <Switch checked={u.is_default} onChange={(v) => setU({ ...u, is_default: v })} label="تنظیم پیش‌فرض" />
        <Button className="w-full" type="submit" loading={saveSetting.isPending}><ShieldCheck className="h-4 w-4" />ذخیره تنظیمات</Button>
      </form>
    </Modal>
  </div>;
}
