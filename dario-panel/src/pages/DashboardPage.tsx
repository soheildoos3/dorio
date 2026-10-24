import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, Boxes, PackageSearch, ShoppingCart, Users, Warehouse, Scissors, ShieldCheck, Truck, Factory, AlertTriangle } from 'lucide-react';
import { Link } from 'react-router-dom';
import { catalogApi } from '../api/catalog';
import { inventoryApi } from '../api/inventory';
import { usersApi } from '../api/users';
import { warehouseApi } from '../api/warehouse';
import { adminApi } from '../api/admin';
import { manufacturingApi } from '../api/manufacturing';
import { accountingApi } from '../api/accounting';
import { useAuth } from '../auth/AuthProvider';
import { Card, CardHeader, PageHeader } from '../components/ui/Page';
import { LoadingState, ErrorState, EmptyState } from '../components/ui/States';
import { moneyFa, numberFa } from '../lib/format';

export function DashboardPage() {
  const { can, auth } = useAuth();
  const overview = useQuery({
    queryKey: ['dashboard', 'overview', auth?.user.id], queryFn: async () => {
      const [products, warehouses, users, stock, items, sales, tailorStats, productionOrders, materials, materialStock, trial, warranties] = await Promise.all([
        can('catalog.view') ? catalogApi.products() : Promise.resolve([]),
        can('warehouse.view') ? warehouseApi.list() : Promise.resolve([]),
        can('users.view') ? usersApi.list() : Promise.resolve([]),
        can('inventory.view') ? inventoryApi.stock() : Promise.resolve([]),
        can('inventory.view') ? inventoryApi.items() : Promise.resolve([]),
        can('sales.view') && can('inventory.view') ? inventoryApi.salesSummary() : Promise.resolve(null),
        can('tailors.view') ? adminApi.stats() : Promise.resolve([]),
        can('manufacturing.view') ? manufacturingApi.orders() : Promise.resolve([]),
        can('manufacturing.view') ? manufacturingApi.materials() : Promise.resolve([]),
        can('manufacturing.view') ? manufacturingApi.materialStock() : Promise.resolve([]),
        can('accounting.view') ? accountingApi.trialBalance() : Promise.resolve([]),
        can('warranty.view') ? adminApi.warranties() : Promise.resolve([]),
      ]);
      return { products, warehouses, users, stock, items, sales, tailorStats, productionOrders, materials, materialStock, trial, warranties };
    }
  });
  if (overview.isLoading) return <LoadingState label="در حال آماده‌سازی داشبورد…" />;
  if (overview.isError || !overview.data) return <ErrorState error={overview.error} onRetry={() => overview.refetch()} />;

  const d = overview.data;
  const available = d.stock.reduce((s, x) => s + x.quantity, 0);
  const pendingQc = d.items.filter((x) => x.qc_status === 'pending').length;
  const materialValue = d.materialStock.reduce((sum, row) => sum + Number(row.quantity) * Number(d.materials.find((m) => m.id === row.material_id)?.weighted_average_cost || 0), 0);
  const finishedValue = d.items.filter((x) => x.status === 'in_stock').reduce((sum, x) => sum + Number(x.unit_cost_snapshot || 0), 0);
  const activeProduction = d.productionOrders.filter((o) => !['completed','cancelled'].includes(o.status)).length;
  const qcPassed = d.productionOrders.reduce((sum, o) => sum + o.qc_passed, 0);
  const qcFailed = d.productionOrders.reduce((sum, o) => sum + o.qc_failed, 0);
  const qcRejectRate = qcPassed + qcFailed ? (qcFailed * 100) / (qcPassed + qcFailed) : 0;
  const balanceByCode = (code:string, prefix=false) => d.trial.filter((x) => prefix ? x.code.startsWith(code) : x.code === code).reduce((sum, x) => sum + Number(x.balance || 0), 0);
  const grossProfit = -balanceByCode('4100') - balanceByCode('5100');
  const receivable = balanceByCode('1200');
  const payable = -balanceByCode('2100') - balanceByCode('2120', true);
  const lowMaterials = d.materials.filter((m) => d.materialStock.filter((s) => s.material_id === m.id).reduce((sum, s) => sum + Number(s.quantity), 0) <= Number(m.reorder_point)).length;
  const now = Date.now(); const month = 30 * 86400000;
  const expiringWarranties = d.warranties.filter((w) => w.status === 'active' && w.expires_at && new Date(w.expires_at).getTime() >= now && new Date(w.expires_at).getTime() <= now + month).length;
  const overdueProduction = d.productionOrders.filter((o) => !['completed','cancelled'].includes(o.status) && o.due_at && new Date(o.due_at).getTime() < now).length;
  const cards = [
    can('catalog.view') && { label: 'محصولات', value: numberFa(d.products.length), icon: PackageSearch, to: '/catalog', hint: 'مدیریت کاتالوگ' },
    can('inventory.view') && { label: 'موجودی', value: numberFa(available), icon: Boxes, to: '/inventory', hint: 'واحد قابل دسترس' },
    can('warehouse.view') && { label: 'انبارها', value: numberFa(d.warehouses.length), icon: Warehouse, to: '/warehouses', hint: 'انبار فعال' },
    can('quality.view') && can('inventory.view') && { label: 'در انتظار QC', value: numberFa(pendingQc), icon: ShieldCheck, to: '/quality', hint: pendingQc ? 'نیازمند بررسی' : 'همه بررسی شده' },
    can('users.view') && { label: 'کاربران', value: numberFa(d.users.length), icon: Users, to: '/users', hint: 'حساب ثبت‌شده' },
    can('sales.view') && d.sales && { label: 'فروش خالص', value: moneyFa(d.sales.net_amount), icon: ShoppingCart, to: '/sales', hint: 'جمع فروش ثبت‌شده' },
    can('inventory.view') && can('inventory.outbound') && { label: 'خروج انبار', value: 'ثبت خروج', icon: Truck, to: '/outbound', hint: 'فروش یا خروج عملیاتی' },
    can('tailors.view') && { label: 'خیاط‌ها', value: numberFa(d.tailorStats.length), icon: Scissors, to: '/tailors', hint: 'همکار تولید' },
    can('manufacturing.view') && { label: 'ارزش موجودی تولیدی', value: moneyFa(materialValue + finishedValue), icon: Factory, to: '/manufacturing', hint: `${numberFa(activeProduction)} دستور در جریان` },
    can('manufacturing.view') && { label: 'نرخ رد QC تولید', value: `${numberFa(qcRejectRate)}٪`, icon: ShieldCheck, to: '/manufacturing', hint: 'بر اساس دستورهای تولید' },
    can('accounting.view') && { label: 'سود ناخالص', value: moneyFa(grossProfit), icon: ShoppingCart, to: '/accounting', hint: 'فروش منهای بهای فروش' },
    can('accounting.view') && { label: 'دریافتنی / پرداختنی', value: `${moneyFa(receivable)} / ${moneyFa(payable)}`, icon: Boxes, to: '/accounting', hint: 'مانده دفتر' },
  ].filter(Boolean) as { label: string; value: string; icon: any; to: string; hint: string }[];

  return <div className="space-y-6">
    <PageHeader title={`سلام ${auth?.user.full_name?.split(' ')[0] || ''}`} description="نمای سریع از وضعیت عملیات؛ فقط بخش‌هایی را می‌بینید که دسترسی آن‌ها برای نقش شما فعال است." />

    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {cards.map(({ label, value, icon: Icon, to, hint }) => <Link key={label} to={to} className="group rounded-2xl border border-slate-200 bg-white p-4 shadow-sm outline-none transition duration-200 hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-lg hover:shadow-slate-950/5 focus-visible:ring-4 focus-visible:ring-sky-100 sm:p-5">
        <div className="flex items-start justify-between gap-3"><span className="grid h-11 w-11 place-items-center rounded-2xl bg-slate-100 text-slate-700 transition group-hover:bg-slate-950 group-hover:text-white"><Icon className="h-5 w-5" /></span><ArrowLeft className="h-4 w-4 text-slate-300 transition group-hover:-translate-x-1 group-hover:text-slate-600" /></div>
        <p className="mt-5 truncate text-2xl font-black text-slate-950">{value}</p>
        <div className="mt-1 flex items-end justify-between gap-3"><p className="text-sm font-bold text-slate-700">{label}</p><p className="truncate text-[11px] text-slate-400">{hint}</p></div>
      </Link>)}
    </div>

    {(lowMaterials > 0 || expiringWarranties > 0 || overdueProduction > 0) && <Card>
      <CardHeader title="هشدارهای مدیریتی" description="مواردی که نیاز به اقدام دارند." />
      <div className="grid gap-3 p-5 md:grid-cols-3">
        {lowMaterials > 0 && <Link to="/manufacturing" className="rounded-xl bg-amber-50 p-4 text-amber-800"><AlertTriangle className="mb-2 h-5 w-5"/><b>{numberFa(lowMaterials)} ماده زیر نقطه سفارش</b></Link>}
        {overdueProduction > 0 && <Link to="/manufacturing" className="rounded-xl bg-rose-50 p-4 text-rose-800"><AlertTriangle className="mb-2 h-5 w-5"/><b>{numberFa(overdueProduction)} دستور تولید معطل</b></Link>}
        {expiringWarranties > 0 && <Link to="/warranty" className="rounded-xl bg-sky-50 p-4 text-sky-800"><AlertTriangle className="mb-2 h-5 w-5"/><b>{numberFa(expiringWarranties)} گارانتی نزدیک انقضا</b></Link>}
      </div>
    </Card>}

    {d.sales && can('sales.view') && <Card>
      <CardHeader title="فروش به تفکیک پلتفرم" description={`تعداد فروش: ${numberFa(d.sales.quantity)} · تخفیف کل: ${moneyFa(d.sales.discount_amount)}`} />
      {d.sales.channels.length === 0 ? <div className="p-5"><EmptyState title="هنوز فروشی ثبت نشده" description="پس از ثبت خروج فروش، آمار این بخش نمایش داده می‌شود." /></div> : <div className="overflow-x-auto">
        <table className="w-full min-w-[650px] text-sm"><thead className="bg-slate-50"><tr><th className="p-3 text-right">پلتفرم</th><th>تعداد</th><th>دفعات خروج</th><th>فروش ناخالص</th><th>تخفیف</th><th>فروش خالص</th></tr></thead><tbody>{d.sales.channels.map((x) => <tr key={x.channel_id ?? 'none'} className="border-t border-slate-100 text-center"><td className="p-3 text-right font-bold">{x.channel_name}</td><td>{numberFa(x.quantity)}</td><td>{numberFa(x.outbound_count)}</td><td>{moneyFa(x.gross_amount)}</td><td>{moneyFa(x.discount_amount)}</td><td className="font-black text-slate-950">{moneyFa(x.net_amount)}</td></tr>)}</tbody></table>
      </div>}
    </Card>}
  </div>;
}
