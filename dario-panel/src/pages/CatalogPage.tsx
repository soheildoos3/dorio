import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ImagePlus, PackagePlus, Pencil, Plus, Shapes, Trash2 } from 'lucide-react';
import { useMemo, useState, type FormEvent } from 'react';
import { catalogApi, type AttributePayload, type AttributeValuePayload, type CategoryPayload, type ProductPayload, type ProductVariantPayload } from '../api/catalog';
import type { AttributeDefinition, Category, Media, Product, ProductStatus, ProductVariant } from '../api/types';
import { useToast } from '../components/feedback/ToastProvider';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Field, Input, Select, Switch, Textarea } from '../components/ui/Field';
import { Modal } from '../components/ui/Modal';
import { Card, CardHeader, PageHeader } from '../components/ui/Page';
import { EmptyState, ErrorState, LoadingState } from '../components/ui/States';
import { Tabs } from '../components/ui/Tabs';
import { dateTimeFa, moneyFa, nullableNumber } from '../lib/format';
import { labels } from '../lib/labels';
import { useAuth } from '../auth/AuthProvider';
import { useNavigate } from 'react-router-dom';

type Tab = 'products' | 'categories' | 'variants' | 'attributes' | 'media';

const productEmpty: ProductPayload = { sku: '', name: '', description: '', category_id: null, is_sellable: true, is_manufacturable: false, warranty_months: 12, status: 'draft' };
const categoryEmpty: CategoryPayload = { name: '', parent_id: null, sort_order: 0, is_active: true };
const variantEmpty: ProductVariantPayload = { product_id: 0, sku: '', attribute_value_ids: [], sale_price: 0, is_active: true };
const attributeEmpty: AttributePayload = { code: '', name: '', is_variant_axis: false, sort_order: 0 };

export function CatalogPage() {
  const {can}=useAuth();
  const manage=can('catalog.manage');
  const [tab, setTab] = useState<Tab>('products');
  const products = useQuery({ queryKey: ['catalog', 'products'], queryFn: catalogApi.products });
  const categories = useQuery({ queryKey: ['catalog', 'categories'], queryFn: () => catalogApi.categories(false) });
  const variants = useQuery({ queryKey: ['catalog', 'variants'], queryFn: () => catalogApi.variants() });
  const attributes = useQuery({ queryKey: ['catalog', 'attributes'], queryFn: catalogApi.attributes });

  return (
    <div className="space-y-6">
      <PageHeader title="کاتالوگ محصولات" description="محصول، تنوع، دسته‌بندی، ویژگی و رسانه؛ مطابق قرارداد فعلی ماژول catalog در FastAPI." />
      <Tabs value={tab} onChange={setTab} items={manage ? [
        { id: 'products', label: 'محصولات', count: products.data?.length },
        { id: 'categories', label: 'دسته‌بندی‌ها', count: categories.data?.length },
        { id: 'variants', label: 'تنوع‌ها', count: variants.data?.length },
        { id: 'attributes', label: 'ویژگی‌ها', count: attributes.data?.length },
        { id: 'media', label: 'تصاویر' },
      ] : [{ id: 'products', label: 'محصولات', count: products.data?.length }]} />
      {tab === 'products' && <ProductsSection manage={manage} products={products.data || []} categories={categories.data || []} variants={variants.data||[]} loading={products.isLoading || categories.isLoading || variants.isLoading} error={products.error || categories.error || variants.error} />}
      {manage && tab === 'categories' && <CategoriesSection categories={categories.data || []} loading={categories.isLoading} error={categories.error} />}
      {manage && tab === 'variants' && <VariantsSection />}
      {manage && tab === 'attributes' && <AttributesSection />}
      {manage && tab === 'media' && <MediaSection />}
    </div>
  );
}

function ProductsSection({ manage, products, categories, variants, loading, error }: { manage:boolean; products: Product[]; categories: Category[]; variants:ProductVariant[]; loading: boolean; error: unknown }) {
  const navigate = useNavigate();
  const toast = useToast();
  const client = useQueryClient();
  const [modal, setModal] = useState(false);
  const [editing, setEditing] = useState<Product | null>(null);
  const [form, setForm] = useState<ProductPayload>(productEmpty);
  const [search, setSearch] = useState('');

  const save = useMutation({ mutationFn: () => editing ? catalogApi.updateProduct(editing.id, form) : catalogApi.createProduct(form), onSuccess: async () => { await client.invalidateQueries({ queryKey: ['catalog', 'products'] }); toast.success(editing ? 'محصول ویرایش شد' : 'محصول ایجاد شد'); close(); }, onError: (e) => toast.error('ذخیره محصول ناموفق بود', e instanceof Error ? e.message : undefined) });
  const remove = useMutation({ mutationFn: catalogApi.deleteProduct, onSuccess: async () => { await client.invalidateQueries({ queryKey: ['catalog', 'products'] }); toast.success('محصول حذف نرم شد'); }, onError: (e) => toast.error('حذف محصول ناموفق بود', e instanceof Error ? e.message : undefined) });
  const filtered = useMemo(() => products.filter((p) => !search.trim() || `${p.name} ${p.sku}`.toLowerCase().includes(search.trim().toLowerCase())), [products, search]);
  const categoryName = (id: number | null) => categories.find((c) => c.id === id)?.path || 'بدون دسته';

  function close() { setModal(false); setEditing(null); setForm(productEmpty); }
  function startEdit(p: Product) { setEditing(p); setForm({ sku: p.sku, name: p.name, description: p.description || '', category_id: p.category_id, is_sellable: p.is_sellable, is_manufacturable: p.is_manufacturable, warranty_months: p.warranty_months, status: p.status }); setModal(true); }

  if (loading) return <LoadingState />;
  if (error) return <ErrorState error={error} />;
  return <>
    <Card>
      <div className="flex flex-col gap-3 border-b border-slate-100 p-4 sm:flex-row sm:items-center sm:justify-between"><Input className="sm:max-w-sm" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="جستجو نام یا SKU…" />{manage&&<Button onClick={() => setModal(true)}><Plus className="h-4 w-4" />محصول جدید</Button>}</div>
      {filtered.length === 0 ? <div className="p-5"><EmptyState title="محصولی ثبت نشده" /></div> : <div className="overflow-x-auto"><table className="w-full min-w-[950px] text-sm"><thead className="bg-slate-50 text-xs text-slate-500"><tr><th className="px-5 py-3 text-right">محصول</th><th className="px-5 py-3 text-right">دسته</th><th className="px-5 py-3 text-right">وضعیت</th><th className="px-5 py-3 text-right">فروش/تولید</th><th className="px-5 py-3 text-right">به‌روزرسانی</th>{manage&&<th className="px-5 py-3 text-left">عملیات</th>}</tr></thead><tbody className="divide-y divide-slate-100">{filtered.map((p) => <tr key={p.id} role="link" tabIndex={0} onClick={()=>navigate(`/catalog/products/${p.id}`)} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();navigate(`/catalog/products/${p.id}`)}}} className="cursor-pointer hover:bg-slate-50/60 focus-within:bg-sky-50/60 focus:outline-none"><td className="px-5 py-4"><button type="button" onClick={e=>{e.stopPropagation();navigate(`/catalog/products/${p.id}`)}} className="font-bold text-slate-900 hover:text-sky-700 hover:underline">{p.name}</button><p dir="ltr" className="mt-1 text-right text-xs text-slate-500">{p.sku||'بدون SKU'}</p><div className="mt-2 flex max-w-[520px] flex-wrap gap-1">{variants.filter(v=>v.product_id===p.id).slice(0,6).map(v=><span key={v.id} className="rounded-lg bg-sky-50 px-2 py-1 text-[10px] font-bold text-sky-700">{v.resolved_attributes.map(a=>a.value).join(' / ')||v.sku||'تنوع پایه'}</span>)}{variants.filter(v=>v.product_id===p.id).length>6&&<span className="rounded-lg bg-slate-100 px-2 py-1 text-[10px] text-slate-500">+{variants.filter(v=>v.product_id===p.id).length-6}</span>}</div></td><td className="px-5 py-4 text-slate-600">{categoryName(p.category_id)}</td><td className="px-5 py-4"><Badge tone={p.status === 'active' ? 'green' : p.status === 'archived' ? 'slate' : 'amber'}>{labels.productStatus[p.status]}</Badge></td><td className="px-5 py-4 text-xs"><span className={p.is_sellable ? 'text-emerald-600' : 'text-slate-400'}>فروش {p.is_sellable ? '✓' : '—'}</span><span className="mx-2 text-slate-300">|</span><span className={p.is_manufacturable ? 'text-sky-600' : 'text-slate-400'}>تولید {p.is_manufacturable ? '✓' : '—'}</span></td><td className="px-5 py-4 text-xs text-slate-500">{dateTimeFa(p.updated_at)}</td>{manage&&<td className="px-5 py-4"><div className="flex justify-end gap-1"><Button variant="ghost" className="px-2.5" onClick={(e) => {e.stopPropagation();startEdit(p)}}><Pencil className="h-4 w-4" /></Button><Button variant="ghost" className="px-2.5 text-rose-600" onClick={(e) => {e.stopPropagation();if(confirm(`محصول «${p.name}» حذف شود؟`)) remove.mutate(p.id)}}><Trash2 className="h-4 w-4" /></Button></div></td>}</tr>)}</tbody></table></div>}
    </Card>
    {manage&&<Modal open={modal} onClose={close} title={editing ? 'ویرایش محصول' : 'محصول جدید'}>
      <form onSubmit={(e) => { e.preventDefault(); save.mutate(); }} className="space-y-5">
        <div className="grid gap-4 sm:grid-cols-2"><Field label="SKU" hint="اختیاری است؛ فقط اگر کد داخلی مشخصی دارید وارد کنید."><Input maxLength={50} dir="ltr" value={form.sku||''} onChange={(e) => setForm({ ...form, sku: e.target.value })} /></Field><Field label="نام محصول" required><Input required maxLength={255} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field><Field label="دسته‌بندی"><Select value={form.category_id ?? ''} onChange={(e) => setForm({ ...form, category_id: nullableNumber(e.target.value) })}><option value="">بدون دسته</option>{categories.map((c) => <option value={c.id} key={c.id}>{c.path}</option>)}</Select></Field><Field label="وضعیت"><Select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value as ProductStatus })}>{Object.entries(labels.productStatus).map(([v,l]) => <option key={v} value={v}>{l}</option>)}</Select></Field></div>
        <Field label="توضیحات"><Textarea value={form.description || ''} onChange={(e) => setForm({ ...form, description: e.target.value || null })} /></Field>
        <Field label="مدت گارانتی (ماه)" hint="از زمان فعال‌شدن گارانتی محاسبه می‌شود."><Input type="number" min={1} max={120} value={form.warranty_months ?? 12} onChange={(e) => setForm({ ...form, warranty_months: Math.max(1, Number(e.target.value)||1) })} /></Field>
        <div className="flex flex-wrap gap-5"><Switch checked={!!form.is_sellable} onChange={(v) => setForm({ ...form, is_sellable: v })} label="قابل فروش" /><Switch checked={!!form.is_manufacturable} onChange={(v) => setForm({ ...form, is_manufacturable: v })} label="قابل تولید" /></div>
        <div className="flex justify-end gap-2 border-t border-slate-100 pt-4"><Button type="button" variant="secondary" onClick={close}>انصراف</Button><Button type="submit" loading={save.isPending}>ذخیره</Button></div>
      </form>
    </Modal>}
  </>;
}

function CategoriesSection({ categories, loading, error }: { categories: Category[]; loading: boolean; error: unknown }) {
  const toast = useToast(); const client = useQueryClient();
  const [modal, setModal] = useState(false); const [editing, setEditing] = useState<Category | null>(null); const [form, setForm] = useState<CategoryPayload>(categoryEmpty);
  const save = useMutation({ mutationFn: () => editing ? catalogApi.updateCategory(editing.id, form) : catalogApi.createCategory(form), onSuccess: async () => { await client.invalidateQueries({ queryKey: ['catalog','categories'] }); toast.success('دسته‌بندی ذخیره شد'); setModal(false); setEditing(null); setForm(categoryEmpty); }, onError: (e) => toast.error('ذخیره دسته‌بندی ناموفق بود', e instanceof Error ? e.message : undefined) });
  const remove = useMutation({ mutationFn: catalogApi.deleteCategory, onSuccess: async () => { await client.invalidateQueries({ queryKey: ['catalog','categories'] }); toast.success('دسته‌بندی استفاده‌نشده حذف شد'); }, onError: (e) => toast.error('حذف دسته‌بندی ممکن نیست', e instanceof Error ? e.message : undefined) });
  if (loading) return <LoadingState />; if (error) return <ErrorState error={error} />;
  return <><Card><div className="flex justify-end border-b border-slate-100 p-4"><Button onClick={() => setModal(true)}><Plus className="h-4 w-4" />دسته جدید</Button></div><div className="grid gap-3 p-4 md:grid-cols-2 xl:grid-cols-3">{categories.map((c) => <div key={c.id} className="rounded-2xl border border-slate-200 p-4 text-right transition hover:border-sky-300 hover:bg-sky-50/30"><div className="flex items-start justify-between"><span className="rounded-xl bg-slate-100 p-2 text-slate-600"><Shapes className="h-4 w-4" /></span><Badge tone={c.is_active ? 'green' : 'slate'}>{c.is_active ? 'فعال' : 'غیرفعال'}</Badge></div><p className="mt-4 font-black text-slate-900">{c.name}</p><p className="mt-1 text-xs text-slate-500">{c.path} · سطح {c.level.toLocaleString('fa-IR')}</p><div className="mt-3 flex justify-end gap-1"><Button variant="ghost" className="px-2.5" onClick={() => { setEditing(c); setForm({ name:c.name,parent_id:c.parent_id,sort_order:c.sort_order,is_active:c.is_active }); setModal(true); }}><Pencil className="h-4 w-4" /></Button><Button variant="ghost" className="px-2.5 text-rose-600" loading={remove.isPending} onClick={()=>confirm('این دسته‌بندی فقط در صورت استفاده‌نشدن حذف می‌شود. ادامه می‌دهید؟')&&remove.mutate(c.id)}><Trash2 className="h-4 w-4" /></Button></div></div>)}{categories.length===0 && <div className="md:col-span-2 xl:col-span-3"><EmptyState /></div>}</div></Card>
    <Modal open={modal} onClose={() => { setModal(false); setEditing(null); setForm(categoryEmpty); }} title={editing ? 'ویرایش دسته‌بندی' : 'دسته‌بندی جدید'}><form onSubmit={(e)=>{e.preventDefault();save.mutate();}} className="space-y-4"><Field label="نام" required><Input required maxLength={100} value={form.name} onChange={(e)=>setForm({...form,name:e.target.value})}/></Field><Field label="والد"><Select value={form.parent_id ?? ''} onChange={(e)=>setForm({...form,parent_id:nullableNumber(e.target.value)})}><option value="">بدون والد</option>{categories.filter(c=>c.id!==editing?.id).map(c=><option key={c.id} value={c.id}>{c.path}</option>)}</Select></Field><Field label="ترتیب"><Input type="number" value={form.sort_order ?? 0} onChange={(e)=>setForm({...form,sort_order:Number(e.target.value)})}/></Field><Switch checked={form.is_active ?? true} onChange={(v)=>setForm({...form,is_active:v})} label="فعال"/><div className="flex justify-end gap-2 pt-3"><Button type="button" variant="secondary" onClick={()=>setModal(false)}>انصراف</Button><Button type="submit" loading={save.isPending}>ذخیره</Button></div></form></Modal></>;
}

function VariantsSection() {
  const variants=useQuery({queryKey:['catalog','variants'],queryFn:()=>catalogApi.variants()});
  const products=useQuery({queryKey:['catalog','products'],queryFn:catalogApi.products});
  return <Card><CardHeader title="تنوع‌های محصول" description="ویژگی‌های تنوع دیگر JSON دستی نیستند. برای ساخت یا تغییر ترکیب‌ها وارد صفحه همان محصول شوید." />{variants.isLoading?<LoadingState/>:variants.isError?<ErrorState error={variants.error}/>:<div className="overflow-x-auto"><table className="w-full min-w-[820px] text-sm"><thead className="bg-slate-50"><tr><th className="p-3 text-right">محصول</th><th className="p-3 text-right">ترکیب ویژگی</th><th className="p-3 text-right">SKU</th><th className="p-3 text-right">قیمت</th><th className="p-3">وضعیت</th></tr></thead><tbody>{variants.data?.map(v=><tr key={v.id} className="border-t"><td className="p-3"><a className="font-bold text-sky-700 hover:underline" href={`/catalog/products/${v.product_id}`}>{products.data?.find(p=>p.id===v.product_id)?.name||'—'}</a></td><td className="p-3">{v.resolved_attributes.map(x=>`${x.attribute_name}: ${x.value}`).join(' · ')||'تنوع پایه'}</td><td className="p-3" dir="ltr">{v.sku||'—'}</td><td className="p-3 font-black">{moneyFa(v.sale_price)}</td><td className="p-3 text-center"><Badge tone={v.is_active?'green':'slate'}>{v.is_active?'فعال':'غیرفعال'}</Badge></td></tr>)}</tbody></table></div>}</Card>;
}
function AttributesSection() {
  const toast=useToast(); const client=useQueryClient(); const attrs=useQuery({queryKey:['catalog','attributes'],queryFn:catalogApi.attributes}); const values=useQuery({queryKey:['catalog','attribute-values'],queryFn:()=>catalogApi.attributeValues()});
  const [open,setOpen]=useState<'attribute'|'value'|null>(null); const [editingAttr,setEditingAttr]=useState<any|null>(null); const [editingValue,setEditingValue]=useState<any|null>(null); const [form,setForm]=useState<AttributePayload>(attributeEmpty); const [valueForm,setValueForm]=useState<AttributeValuePayload>({attribute_id:0,value:'',sort_order:0});
  const saveAttr=useMutation({mutationFn:()=>editingAttr?catalogApi.updateAttribute(editingAttr.id,form):catalogApi.createAttribute(form),onSuccess:async()=>{await client.invalidateQueries({queryKey:['catalog','attributes']});toast.success('ویژگی ذخیره شد');setOpen(null);setEditingAttr(null);setForm(attributeEmpty)},onError:(e)=>toast.error('ذخیره ویژگی ناموفق بود',e instanceof Error?e.message:undefined)});
  const saveValue=useMutation({mutationFn:()=>editingValue?catalogApi.updateAttributeValue(editingValue.id,{value:valueForm.value,sort_order:valueForm.sort_order}):catalogApi.createAttributeValue(valueForm),onSuccess:async()=>{await client.invalidateQueries({queryKey:['catalog','attribute-values']});toast.success('مقدار ذخیره شد');setOpen(null);setEditingValue(null);setValueForm({attribute_id:0,value:'',sort_order:0})},onError:(e)=>toast.error('ذخیره مقدار ناموفق بود',e instanceof Error?e.message:undefined)});
  const removeAttr=useMutation({mutationFn:catalogApi.deleteAttribute,onSuccess:async()=>{await Promise.all([client.invalidateQueries({queryKey:['catalog','attributes']}),client.invalidateQueries({queryKey:['catalog','attribute-values']})]);toast.success('ویژگی استفاده‌نشده حذف شد')},onError:(e)=>toast.error('حذف ویژگی ممکن نیست',e instanceof Error?e.message:undefined)});
  const removeValue=useMutation({mutationFn:catalogApi.deleteAttributeValue,onSuccess:async()=>{await client.invalidateQueries({queryKey:['catalog','attribute-values']});toast.success('مقدار استفاده‌نشده حذف شد')},onError:(e)=>toast.error('حذف مقدار ممکن نیست',e instanceof Error?e.message:undefined)});
  if(attrs.isLoading)return <LoadingState/>; if(attrs.isError)return <ErrorState error={attrs.error}/>;
  return <><div className="grid gap-6 xl:grid-cols-2"><Card><CardHeader title="تعریف ویژگی‌ها" action={<Button onClick={()=>{setEditingAttr(null);setForm(attributeEmpty);setOpen('attribute')}}><Plus className="h-4 w-4"/>ویژگی</Button>}/><div className="divide-y">{attrs.data?.map(a=><div key={a.id} className="flex items-center justify-between p-4"><div><p className="font-bold">{a.name}</p><p className="text-xs text-slate-500">{a.code}</p></div><div className="flex items-center gap-2"><Badge tone={a.is_variant_axis?'violet':'slate'}>{a.is_variant_axis?'تنوع‌ساز':'اطلاعاتی'}</Badge><Button variant="ghost" className="px-2.5" onClick={()=>{setEditingAttr(a);setForm({code:a.code,name:a.name,is_variant_axis:a.is_variant_axis,sort_order:a.sort_order});setOpen('attribute')}}><Pencil className="h-4 w-4"/></Button><Button variant="ghost" className="px-2.5 text-rose-600" onClick={()=>confirm('ویژگی فقط اگر در هیچ محصول/تنوعی استفاده نشده باشد حذف می‌شود. ادامه؟')&&removeAttr.mutate(a.id)}><Trash2 className="h-4 w-4"/></Button></div></div>)}</div></Card><Card><CardHeader title="مقادیر ویژگی‌ها" action={<Button variant="secondary" onClick={()=>{setEditingValue(null);setValueForm({attribute_id:0,value:'',sort_order:0});setOpen('value')}}><Plus className="h-4 w-4"/>مقدار</Button>}/><div className="divide-y">{values.data?.map(v=><div key={v.id} className="flex items-center justify-between p-4"><div><b>{v.value}</b><p className="text-xs text-slate-500">{attrs.data?.find(a=>a.id===v.attribute_id)?.name}</p></div><div className="flex gap-1"><Button variant="ghost" className="px-2.5" onClick={()=>{setEditingValue(v);setValueForm({attribute_id:v.attribute_id,value:v.value,sort_order:v.sort_order});setOpen('value')}}><Pencil className="h-4 w-4"/></Button><Button variant="ghost" className="px-2.5 text-rose-600" onClick={()=>confirm('این مقدار فقط اگر استفاده نشده باشد حذف می‌شود. ادامه؟')&&removeValue.mutate(v.id)}><Trash2 className="h-4 w-4"/></Button></div></div>)}</div></Card></div><Modal open={open==='attribute'} onClose={()=>setOpen(null)} title={editingAttr?'ویرایش ویژگی':'ویژگی جدید'}><form onSubmit={e=>{e.preventDefault();saveAttr.mutate()}} className="space-y-4"><Field label="کد"><Input disabled={!!editingAttr} required value={form.code} onChange={e=>setForm({...form,code:e.target.value})}/></Field><Field label="نام"><Input required value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/></Field><Field label="ترتیب"><Input type="number" value={form.sort_order??0} onChange={e=>setForm({...form,sort_order:Number(e.target.value)})}/></Field><Switch checked={form.is_variant_axis??false} onChange={v=>setForm({...form,is_variant_axis:v})} label="تنوع‌ساز"/><Button className="w-full">ذخیره</Button></form></Modal><Modal open={open==='value'} onClose={()=>setOpen(null)} title={editingValue?'ویرایش مقدار':'مقدار جدید'}><form onSubmit={e=>{e.preventDefault();saveValue.mutate()}} className="space-y-4"><Field label="ویژگی"><Select disabled={!!editingValue} required value={valueForm.attribute_id||''} onChange={e=>setValueForm({...valueForm,attribute_id:Number(e.target.value)})}><option value="">انتخاب</option>{attrs.data?.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</Select></Field><Field label="مقدار"><Input required value={valueForm.value} onChange={e=>setValueForm({...valueForm,value:e.target.value})}/></Field><Field label="ترتیب"><Input type="number" value={valueForm.sort_order??0} onChange={e=>setValueForm({...valueForm,sort_order:Number(e.target.value)})}/></Field><Button className="w-full">ذخیره</Button></form></Modal></>;
}

function MediaSection() {
  const toast = useToast();
  const client = useQueryClient();
  const [productId, setProductId] = useState<number>(0);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Media | null>(null);
  const [variantId, setVariantId] = useState<number | null>(null);
  const [isPrimary, setIsPrimary] = useState(false);
  const [sortOrder, setSortOrder] = useState(0);
  const [file, setFile] = useState<File | null>(null);

  const products = useQuery({ queryKey: ['catalog','products'], queryFn: catalogApi.products });
  const variants = useQuery({ queryKey: ['catalog','variants'], queryFn: () => catalogApi.variants() });
  const media = useQuery({ queryKey: ['catalog','media',productId], queryFn: () => catalogApi.media(productId), enabled: productId > 0 });
  const variantLabel=(id:number|null)=>id?variants.data?.find(v=>v.id===id)?.sku||'تنوع نامشخص':'عمومی محصول';
  const reset=()=>{setEditing(null);setFile(null);setVariantId(null);setIsPrimary(false);setSortOrder(0);};
  const startCreate=()=>{reset();setOpen(true)};
  const startEdit=(m:Media)=>{setEditing(m);setVariantId(m.variant_id);setIsPrimary(m.is_primary);setSortOrder(m.sort_order);setOpen(true)};

  const save = useMutation({
    mutationFn: () => {
      if(editing) return catalogApi.updateMedia(editing.id,{variant_id:variantId,is_primary:isPrimary,sort_order:sortOrder});
      if (!file) throw new Error('یک تصویر انتخاب کنید');
      return catalogApi.uploadMedia({ product_id: productId, variant_id: variantId, file, is_primary: isPrimary, sort_order: sortOrder });
    },
    onSuccess: async () => {
      await Promise.all([client.invalidateQueries({ queryKey: ['catalog','media',productId] }),client.invalidateQueries({queryKey:['catalog','product',String(productId)]})]);
      toast.success(editing?'مشخصات تصویر ویرایش شد':'تصویر با موفقیت آپلود شد');
      setOpen(false); reset();
    },
    onError: (e) => toast.error(editing?'ویرایش تصویر ناموفق بود':'آپلود تصویر ناموفق بود', e instanceof Error ? e.message : undefined),
  });
  const remove = useMutation({
    mutationFn: catalogApi.deleteMedia,
    onSuccess: async () => { await client.invalidateQueries({ queryKey: ['catalog','media',productId] }); toast.success('تصویر حذف شد'); },
    onError: (e) => toast.error('حذف تصویر ناموفق بود', e instanceof Error ? e.message : undefined),
  });

  return <Card>
    <CardHeader title="تصاویر محصول" description="فایل تصویر مستقیماً در بک‌اند Dario ذخیره می‌شود؛ URL خارجی لازم نیست. تصویر اصلی، تنوع و ترتیب نیز قابل ویرایش‌اند." action={<Button onClick={startCreate} disabled={!productId}><ImagePlus className="h-4 w-4"/>آپلود تصویر</Button>}/>
    <div className="p-4"><Field label="محصول"><Select value={productId||''} onChange={(e)=>setProductId(Number(e.target.value))}><option value="">انتخاب محصول</option>{products.data?.map(p=><option key={p.id} value={p.id}>{p.name} — {p.sku}</option>)}</Select></Field></div>
    {!productId ? <div className="p-5 pt-0"><EmptyState title="یک محصول انتخاب کنید" description="بعد از انتخاب محصول، تصاویر ذخیره‌شده در خود بک‌اند نمایش داده می‌شوند."/></div>
      : media.isLoading ? <LoadingState/> : media.isError ? <ErrorState error={media.error}/>
      : <div className="grid gap-4 p-4 pt-0 sm:grid-cols-2 xl:grid-cols-3">{media.data?.map(m=><div key={m.id} className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
          <div className="aspect-video bg-slate-100"><img src={m.url} alt="تصویر محصول" className="h-full w-full object-cover"/></div>
          <div className="p-3"><div className="flex items-center justify-between"><Badge tone={m.is_primary?'blue':'slate'}>{m.is_primary?'تصویر اصلی':'تصویر'}</Badge><div className="flex gap-1"><Button variant="ghost" className="px-2.5" onClick={()=>startEdit(m)}><Pencil className="h-4 w-4"/></Button><Button variant="ghost" className="px-2.5 text-rose-600" onClick={()=>confirm('این تصویر حذف شود؟')&&remove.mutate(m.id)}><Trash2 className="h-4 w-4"/></Button></div></div><p className="mt-2 text-xs text-slate-500" dir="ltr">{variantLabel(m.variant_id)} · ترتیب {m.sort_order}</p></div>
        </div>)}{media.data?.length===0&&<div className="sm:col-span-2 xl:col-span-3"><EmptyState title="تصویری ثبت نشده" description="با دکمه آپلود تصویر، فایل را از سیستم خود انتخاب کنید."/></div>}</div>}

    <Modal open={open} onClose={()=>{setOpen(false);reset()}} title={editing?'ویرایش تصویر':'آپلود تصویر محصول'}>
      <form onSubmit={(e)=>{e.preventDefault();save.mutate();}} className="space-y-4">
        <Field label="محصول"><Select value={productId} disabled><option value={productId}>{products.data?.find(p=>p.id===productId)?.name || ''}</option></Select></Field>
        <Field label="تنوع (اختیاری)"><Select value={variantId??''} onChange={(e)=>setVariantId(nullableNumber(e.target.value))}><option value="">بدون تنوع</option>{variants.data?.filter(v=>v.product_id===productId).map(v=><option key={v.id} value={v.id}>{v.sku}</option>)}</Select></Field>
        {!editing&&<><Field label="فایل تصویر" required hint="JPG / PNG / WEBP"><Input required type="file" accept="image/jpeg,image/png,image/webp" onChange={(e)=>setFile(e.target.files?.[0] || null)}/></Field>{file && <div className="rounded-xl bg-slate-50 px-3 py-2 text-xs text-slate-600">{file.name} · {(file.size/1024/1024).toFixed(2)} MB</div>}</>}
        <Field label="ترتیب"><Input type="number" value={sortOrder} onChange={(e)=>setSortOrder(Number(e.target.value))}/></Field>
        <Switch checked={isPrimary} onChange={setIsPrimary} label="تصویر اصلی"/>
        <Button type="submit" loading={save.isPending} className="w-full">{editing?'ذخیره تغییرات':'آپلود و ذخیره'}</Button>
      </form>
    </Modal>
  </Card>;
}

