import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, CheckCircle2, PackageCheck, Plus, RotateCcw, ScanLine, XCircle } from 'lucide-react';
import { useMemo, useState, type FormEvent, type ReactNode } from 'react';
import { adminApi } from '../api/admin';
import { inventoryApi } from '../api/inventory';
import { salesApi } from '../api/sales';
import type { ProductItem, SalesInvoice } from '../api/types';
import { useAuth } from '../auth/AuthProvider';
import { QrCameraScanner } from '../components/feedback/QrCameraScanner';
import { useToast } from '../components/feedback/ToastProvider';
import { Button } from '../components/ui/Button';
import { Field, Input, Select, Textarea } from '../components/ui/Field';
import { Modal } from '../components/ui/Modal';
import { Card, CardHeader, PageHeader } from '../components/ui/Page';
import { ErrorState, LoadingState } from '../components/ui/States';
import { useAllLocations, useProducts, useVariants } from '../hooks/useReferenceData';
import { dateTimeFa, moneyFa } from '../lib/format';

const statusLabel: Record<string, string> = { draft: 'پیش‌نویس', confirmed: 'تأییدشده', shipped: 'ارسال‌شده', partially_returned: 'مرجوعی جزئی', returned: 'مرجوع کامل', cancelled: 'لغوشده' };
const statusClass: Record<string, string> = { draft: 'bg-slate-100 text-slate-700', confirmed: 'bg-sky-50 text-sky-700', shipped: 'bg-emerald-50 text-emerald-700', partially_returned: 'bg-amber-50 text-amber-800', returned: 'bg-violet-50 text-violet-700', cancelled: 'bg-rose-50 text-rose-700' };

export function SalesPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const { can } = useAuth();
  const canInventory = can('inventory.view');
  const canCatalog = can('catalog.view');
  const canWarehouse = can('warehouse.view');
  const canCreate = can('sales.manage') && canInventory && canCatalog;

  const invoices = useQuery({ queryKey: ['sales', 'invoices'], queryFn: salesApi.invoices });
  const returns = useQuery({ queryKey: ['sales', 'returns'], queryFn: salesApi.returns });
  const channels = useQuery({ queryKey: ['channels'], queryFn: adminApi.channels });
  const items = useQuery({ queryKey: ['inventory', 'items'], queryFn: () => inventoryApi.items(), enabled: canInventory });
  const variants = useVariants(canCatalog);
  const products = useProducts(canCatalog);
  const locations = useAllLocations(canWarehouse);

  const [createOpen, setCreateOpen] = useState(false);
  const [returnTarget, setReturnTarget] = useState<SalesInvoice | null>(null);
  const [form, setForm] = useState({ channel_id: 0, customer_name: '', customer_phone: '', external_reference: '', notes: '', item_ids: [] as number[], scan: '' });
  const [ret, setRet] = useState({ reason: '', line_ids: [] as number[], locations: {} as Record<number, number> });

  const productById = useMemo(() => new Map(products.data?.map((product) => [product.id, product]) || []), [products.data]);
  const variantById = useMemo(() => new Map(variants.data?.map((variant) => [variant.id, variant]) || []), [variants.data]);
  const itemById = useMemo(() => new Map(items.data?.map((item) => [item.id, item]) || []), [items.data]);
  const channelById = useMemo(() => new Map(channels.data?.map((channel) => [channel.id, channel]) || []), [channels.data]);
  const locationById = useMemo(() => new Map(locations.data?.map((location) => [location.id, location]) || []), [locations.data]);
  const available = (items.data || []).filter((item) => item.status === 'in_stock' && item.location_id);

  const variantLabel = (variantId: number) => {
    const variant = variantById.get(variantId);
    if (!variant) return `تنوع #${variantId}`;
    const product = productById.get(variant.product_id);
    const attrs = (variant.resolved_attributes || []).map((attribute) => attribute.value).join(' / ');
    return `${product?.name || `محصول #${variant.product_id}`}${attrs ? ` · ${attrs}` : ''}${variant.sku ? ` · ${variant.sku}` : ''}`;
  };
  const itemLabel = (item: ProductItem) => `${item.warranty_serial || item.serial_number || `واحد #${item.id}`} · ${variantLabel(item.variant_id)}`;
  const locationLabel = (id: number) => {
    const location = locationById.get(id);
    return location ? `${location.warehouse_name} · ${location.path || location.name || location.code}` : `مکان قبلی #${id}`;
  };

  const refresh = async () => {
    await Promise.all([
      qc.invalidateQueries({ queryKey: ['sales'] }),
      qc.invalidateQueries({ queryKey: ['inventory'] }),
      qc.invalidateQueries({ queryKey: ['warranty'] }),
      qc.invalidateQueries({ queryKey: ['dashboard'] }),
    ]);
  };
  const showError = (error: unknown) => toast.error('عملیات انجام نشد', error instanceof Error ? error.message : 'خطای نامشخص');

  const create = useMutation({
    mutationFn: () => salesApi.createInvoice({
      channel_id: form.channel_id,
      customer_name: form.customer_name.trim() || null,
      customer_phone: form.customer_phone.trim() || null,
      external_reference: form.external_reference.trim() || null,
      notes: form.notes.trim() || null,
      lines: form.item_ids.map((item_id) => ({ item_id })),
    }),
    onSuccess: async () => {
      toast.success('فاکتور ثبت شد', 'برای تأیید باید کاربر دیگری اقدام کند.');
      setCreateOpen(false);
      setForm({ channel_id: 0, customer_name: '', customer_phone: '', external_reference: '', notes: '', item_ids: [], scan: '' });
      await refresh();
    },
    onError: showError,
  });

  const action = useMutation({
    mutationFn: async ({ kind, id }: { kind: 'confirm' | 'ship' | 'cancel'; id: number }) => kind === 'confirm' ? salesApi.confirm(id) : kind === 'ship' ? salesApi.ship(id) : salesApi.cancel(id),
    onSuccess: async (_, value) => {
      toast.success(value.kind === 'confirm' ? 'فاکتور تأیید شد' : value.kind === 'ship' ? 'فاکتور از انبار ارسال شد' : 'فاکتور لغو شد');
      await refresh();
    },
    onError: showError,
  });

  const returnMut = useMutation({
    mutationFn: () => {
      if (!returnTarget) throw new Error('فاکتور مرجوعی مشخص نیست.');
      const lines = ret.line_ids.map((invoice_line_id) => {
        const original = returnTarget.lines.find((line) => line.id === invoice_line_id);
        const location_id = ret.locations[invoice_line_id] || original?.location_id || 0;
        if (!location_id) throw new Error('مکان برگشت یکی از اقلام مشخص نشده است.');
        return { invoice_line_id, location_id };
      });
      return salesApi.createReturn(returnTarget.id, { reason: ret.reason.trim() || null, lines });
    },
    onSuccess: async () => {
      toast.success('برگشت از فروش ثبت شد', 'موجودی، درآمد، بهای تمام‌شده و وضعیت گارانتی همگام شدند.');
      setReturnTarget(null);
      setRet({ reason: '', line_ids: [], locations: {} });
      await refresh();
    },
    onError: showError,
  });

  async function addScan(raw: string) {
    if (!canInventory) return;
    try {
      const item = await inventoryApi.scanItem(raw);
      if (item.status !== 'in_stock' || !item.location_id) {
        toast.error('کالا قابل فروش نیست', 'این QR در موجودی قابل فروش قرار ندارد.');
        return;
      }
      setForm((current) => ({ ...current, scan: '', item_ids: current.item_ids.includes(item.id) ? current.item_ids : [...current.item_ids, item.id] }));
      toast.success('کالا اضافه شد', itemLabel(item));
    } catch (error) {
      showError(error);
    }
  }

  function openReturn(invoice: SalesInvoice) {
    setReturnTarget(invoice);
    setRet({
      reason: '',
      line_ids: [],
      locations: Object.fromEntries(invoice.lines.map((line) => [line.id, line.location_id])),
    });
  }

  if (invoices.isLoading || returns.isLoading || channels.isLoading) return <LoadingState label="در حال دریافت اطلاعات فروش…" />;
  if (invoices.isError) return <ErrorState error={invoices.error} onRetry={() => invoices.refetch()} />;
  if (returns.isError) return <ErrorState error={returns.error} onRetry={() => returns.refetch()} />;

  return <div className="space-y-6">
    <PageHeader
      title="فروش و مرجوعی"
      description="فاکتور فروش به واحد فیزیکی، پلتفرم، QR/گارانتی و Snapshot بهای تمام‌شده متصل است. ثبت، تأیید و ارسال از انبار از هم تفکیک شده‌اند."
      action={can('sales.manage') ? <Button disabled={!canCreate} onClick={() => setCreateOpen(true)} title={!canCreate ? 'برای انتخاب واحد کالا، دسترسی catalog.view و inventory.view نیز لازم است.' : undefined}><Plus className="h-4 w-4" />فاکتور جدید</Button> : undefined}
    />

    {can('sales.manage') && !canCreate && <Card className="p-4"><div className="flex gap-3 rounded-xl bg-amber-50 p-3 text-sm leading-7 text-amber-900"><AlertTriangle className="mt-1 h-5 w-5 shrink-0" /><p>برای ساخت فاکتور در رابط کاربری، نقش شما علاوه بر <span dir="ltr" className="font-mono text-xs">sales.manage</span> باید امکان مشاهده کاتالوگ و موجودی را داشته باشد. فاکتورهای موجود همچنان قابل مشاهده‌اند.</p></div></Card>}

    <div className="grid gap-4 sm:grid-cols-3">
      <Metric title="فاکتورهای باز" value={(invoices.data || []).filter((invoice) => ['draft', 'confirmed'].includes(invoice.status)).length} />
      <Metric title="ارسال‌شده" value={(invoices.data || []).filter((invoice) => invoice.status === 'shipped').length} />
      <Metric title="مبلغ مرجوعی" value={moneyFa((returns.data || []).reduce((sum, row) => sum + Number(row.total_refund || 0), 0))} />
    </div>

    <Card><CardHeader title="فاکتورها" description="در پیش‌نویس: تأیید توسط کاربر دوم؛ در تأییدشده: ارسال توسط کاربر مجاز انبار." />
      <div className="overflow-x-auto"><table className="min-w-full text-sm"><thead className="bg-slate-50 text-slate-500"><tr><Th>شماره</Th><Th>پلتفرم</Th><Th>مشتری</Th><Th>اقلام</Th><Th>مبلغ</Th><Th>وضعیت</Th><Th>تاریخ</Th><Th>عملیات</Th></tr></thead><tbody className="divide-y divide-slate-100">{(invoices.data || []).map((invoice) => <tr key={invoice.id}><Td className="font-black">{invoice.number}</Td><Td>{channelById.get(invoice.channel_id)?.name || `#${invoice.channel_id}`}</Td><Td>{invoice.customer_name || '—'}<div className="text-xs text-slate-400">{invoice.customer_phone || invoice.external_reference || ''}</div></Td><Td>{invoice.lines.length}</Td><Td>{moneyFa(invoice.total_amount)}</Td><Td><span className={`rounded-full px-2.5 py-1 text-xs font-bold ${statusClass[invoice.status] || 'bg-slate-100'}`}>{statusLabel[invoice.status] || invoice.status}</span></Td><Td>{dateTimeFa(invoice.created_at)}</Td><Td><div className="flex flex-wrap gap-1.5">{invoice.status === 'draft' && can('sales.manage') && <Button size="sm" variant="secondary" disabled={action.isPending} onClick={() => action.mutate({ kind: 'confirm', id: invoice.id })}><CheckCircle2 className="h-3.5 w-3.5" />تأیید</Button>}{invoice.status === 'confirmed' && can('sales.ship') && <Button size="sm" disabled={action.isPending} onClick={() => action.mutate({ kind: 'ship', id: invoice.id })}><PackageCheck className="h-3.5 w-3.5" />ارسال</Button>}{['draft', 'confirmed'].includes(invoice.status) && can('sales.manage') && <Button size="sm" variant="ghost" disabled={action.isPending} onClick={() => action.mutate({ kind: 'cancel', id: invoice.id })}><XCircle className="h-3.5 w-3.5" />لغو</Button>}{['shipped', 'partially_returned'].includes(invoice.status) && can('sales.return') && <Button size="sm" variant="secondary" onClick={() => openReturn(invoice)}><RotateCcw className="h-3.5 w-3.5" />مرجوعی</Button>}</div></Td></tr>)}{!invoices.data?.length && <tr><td colSpan={8} className="p-8 text-center text-slate-400">هنوز فاکتوری ثبت نشده است.</td></tr>}</tbody></table></div>
    </Card>

    <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="فاکتور فروش جدید" size="xl"><form onSubmit={(event: FormEvent) => { event.preventDefault(); create.mutate(); }} className="space-y-5">
      <div className="grid gap-3 md:grid-cols-2"><Field label="پلتفرم فروش" required><Select required value={form.channel_id || ''} onChange={(event) => setForm({ ...form, channel_id: Number(event.target.value) })}><option value="">انتخاب</option>{channels.data?.filter((channel) => channel.is_active).map((channel) => <option key={channel.id} value={channel.id}>{channel.name}</option>)}</Select></Field><Field label="شماره سفارش پلتفرم"><Input value={form.external_reference} onChange={(event) => setForm({ ...form, external_reference: event.target.value })} /></Field><Field label="نام مشتری"><Input value={form.customer_name} onChange={(event) => setForm({ ...form, customer_name: event.target.value })} /></Field><Field label="تلفن مشتری"><Input value={form.customer_phone} onChange={(event) => setForm({ ...form, customer_phone: event.target.value })} /></Field></div>
      <Card className="shadow-none"><CardHeader title="افزودن کالا با QR" description="QR گارانتی/محصول را با دوربین موبایل اسکن کنید یا شناسه را دستی وارد کنید." /><div className="space-y-3 p-4"><QrCameraScanner onDetected={(value) => void addScan(value)} /><div className="flex gap-2"><Input value={form.scan} onChange={(event) => setForm({ ...form, scan: event.target.value })} placeholder="کد یا لینک QR" /><Button type="button" variant="secondary" disabled={!form.scan.trim()} onClick={() => void addScan(form.scan)}><ScanLine className="h-4 w-4" />افزودن</Button></div><Field label="یا انتخاب از موجودی"><Select value="" onChange={(event) => { const id = Number(event.target.value); if (id && !form.item_ids.includes(id)) setForm({ ...form, item_ids: [...form.item_ids, id] }); }}><option value="">انتخاب یک واحد موجود</option>{available.filter((item) => !form.item_ids.includes(item.id)).map((item) => <option key={item.id} value={item.id}>{itemLabel(item)}</option>)}</Select></Field></div></Card>
      <div className="space-y-2">{form.item_ids.map((id) => { const item = itemById.get(id); return <div key={id} className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 p-3"><div className="min-w-0 text-sm font-bold">{item ? itemLabel(item) : `واحد #${id}`}</div><Button type="button" size="sm" variant="ghost" onClick={() => setForm({ ...form, item_ids: form.item_ids.filter((value) => value !== id) })}>حذف</Button></div>; })}{!form.item_ids.length && <p className="rounded-xl bg-slate-50 p-4 text-sm text-slate-500">حداقل یک واحد فیزیکی اضافه کنید.</p>}</div>
      <Field label="یادداشت"><Textarea value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} /></Field><Button className="w-full" loading={create.isPending} disabled={!form.channel_id || !form.item_ids.length}>ثبت پیش‌نویس فاکتور</Button>
    </form></Modal>

    <Modal open={!!returnTarget} onClose={() => setReturnTarget(null)} title="برگشت از فروش" description={returnTarget?.number} size="lg"><form onSubmit={(event: FormEvent) => { event.preventDefault(); returnMut.mutate(); }} className="space-y-4">
      <div className="rounded-xl bg-slate-50 p-3 text-xs leading-6 text-slate-600">برای هر ردیف، مقصد مرجوعی به‌صورت پیش‌فرض همان مکان اصلی فروش است. اگر دسترسی انبار داشته باشید می‌توانید مقصد را تغییر دهید.</div>
      <div className="space-y-2"><p className="text-sm font-bold text-slate-700">ردیف‌های مرجوعی</p>{returnTarget?.lines.map((line) => {
        const selected = ret.line_ids.includes(line.id);
        return <div key={line.id} className={`rounded-xl border p-3 transition ${selected ? 'border-sky-300 bg-sky-50/40' : 'border-slate-200'}`}>
          <label className="flex cursor-pointer items-start gap-3"><input className="mt-1" type="checkbox" checked={selected} onChange={(event) => setRet((current) => ({ ...current, line_ids: event.target.checked ? [...current.line_ids, line.id] : current.line_ids.filter((id) => id !== line.id) }))} /><span className="min-w-0 flex-1 text-sm"><b>{variantLabel(line.variant_id)}</b><span className="mr-2 text-slate-500">{moneyFa(line.line_total)}</span><span className="mt-1 block text-xs text-slate-400">مقصد فعلی: {locationLabel(ret.locations[line.id] || line.location_id)}</span></span></label>
          {selected && canWarehouse && <div className="mt-3"><Select value={ret.locations[line.id] || line.location_id} onChange={(event) => setRet((current) => ({ ...current, locations: { ...current.locations, [line.id]: Number(event.target.value) } }))}>{locations.data?.filter((location) => location.is_active && location.is_receivable).map((location) => <option key={location.id} value={location.id}>{location.warehouse_name} · {location.path || location.name || location.code}</option>)}</Select></div>}
        </div>;
      })}</div>
      <Field label="علت برگشت"><Textarea value={ret.reason} onChange={(event) => setRet({ ...ret, reason: event.target.value })} /></Field><Button className="w-full" loading={returnMut.isPending} disabled={!ret.line_ids.length}>ثبت مرجوعی و سند معکوس</Button>
    </form></Modal>
  </div>;
}

function Metric({ title, value }: { title: string; value: string | number }) { return <Card className="p-4"><p className="text-xs font-bold text-slate-500">{title}</p><p className="mt-2 text-2xl font-black text-slate-950">{value}</p></Card>; }
function Th({ children }: { children: ReactNode }) { return <th className="whitespace-nowrap px-4 py-3 text-right text-xs font-bold">{children}</th>; }
function Td({ children, className = '' }: { children: ReactNode; className?: string }) { return <td className={`whitespace-nowrap px-4 py-3 align-top text-slate-700 ${className}`}>{children}</td>; }
