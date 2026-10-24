import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {useMemo,useState,type FormEvent} from 'react';
import {QrCode,Search,Warehouse} from 'lucide-react';
import {inventoryApi,type OutboundDisposition} from '../api/inventory';
import {adminApi} from '../api/admin';
import {useAuth} from '../auth/AuthProvider';
import {useAllLocations,useProducts,useVariants} from '../hooks/useReferenceData';
import {Button} from '../components/ui/Button';
import {Field,Input,Select,Textarea} from '../components/ui/Field';
import {Card,PageHeader} from '../components/ui/Page';
import {useToast} from '../components/feedback/ToastProvider';
import {QrCameraScanner} from '../components/feedback/QrCameraScanner';
import {normalizeScanIdentifier} from '../lib/scan';
import {dateTimeFa,moneyFa,numberFa} from '../lib/format';

const emptyForm={variant_id:0,location_id:0,quantity:1,item_id:null as number|null,reservation_id:null as number|null,disposition:'sale' as OutboundDisposition,channel_id:null as number|null,external_reference:'',reason:''};

export function OutboundPage(){
  const {can}=useAuth(); const canWarehouse=can('warehouse.view'); const canCatalog=can('catalog.view');
  const toast=useToast(); const qc=useQueryClient(); const variants=useVariants(canCatalog); const products=useProducts(canCatalog); const locations=useAllLocations(canWarehouse);
  const channels=useQuery({queryKey:['channels'],queryFn:adminApi.channels});
  const items=useQuery({queryKey:['inventory','items'],queryFn:()=>inventoryApi.items()});
  const stock=useQuery({queryKey:['inventory','stock'],queryFn:()=>inventoryApi.stock()});
  const reservations=useQuery({queryKey:['inventory','reservations'],queryFn:inventoryApi.reservations});
  const history=useQuery({queryKey:['inventory','outbound'],queryFn:inventoryApi.outbound});
  const[f,setF]=useState(emptyForm);
  const[scan,setScan]=useState('');
  const prices=useQuery({queryKey:['channel-prices',f.variant_id],queryFn:()=>adminApi.prices(f.variant_id),enabled:!!f.variant_id&&can('pricing.view')});
  const selectedPrice=prices.data?.find(x=>x.channel_id===f.channel_id);
  const variantLabel=(id:number)=>{const v=variants.data?.find(x=>x.id===id);if(!v)return `تنوع #${id}`;const product=products.data?.find(p=>p.id===v.product_id)?.name||'محصول';const detail=v.resolved_attributes?.map(a=>a.value).join(' / ')||v.sku||'تنوع پایه';return `${product} · ${detail}`};
  const activeReservations=useMemo(()=>reservations.data?.filter(r=>r.status==='active')||[],[reservations.data]);
  const availableItems=useMemo(()=>items.data?.filter(x=>x.variant_id===f.variant_id&&x.location_id===f.location_id&&['in_stock','reserved'].includes(x.status))||[],[items.data,f.variant_id,f.location_id]);
  const stockRow=useMemo(()=>stock.data?.find(x=>x.variant_id===f.variant_id&&x.location_id===f.location_id),[stock.data,f.variant_id,f.location_id]);
  const variantStocks=useMemo(()=>stock.data?.filter(x=>x.variant_id===f.variant_id)||[],[stock.data,f.variant_id]);
  const knownVariantIds=useMemo(()=>[...new Set([...(stock.data||[]).map(x=>x.variant_id),...(items.data||[]).map(x=>x.variant_id)])],[stock.data,items.data]);
  const knownLocationIds=useMemo(()=>[...new Set([...(stock.data||[]).map(x=>x.location_id),...(items.data||[]).map(x=>x.location_id).filter((id):id is number=>!!id)])],[stock.data,items.data]);
  const locationName=(id:number)=>locations.data?.find(l=>l.id===id)?.path||locations.data?.find(l=>l.id===id)?.name||`مکان #${id}`;
  const availableQty=stockRow?.quantity??0; const reservedQty=stockRow?.reserved??0; const physicalQty=availableQty+reservedQty;

  function selectItem(raw:string){const id=raw?Number(raw):null;const item=items.data?.find(x=>x.id===id);const reservation=item?activeReservations.find(r=>r.item_id===item.id):undefined;setF(v=>({...v,item_id:id,quantity:id?1:v.quantity,reservation_id:reservation?.id??null}));}
  function selectReservation(raw:string){const id=raw?Number(raw):null;const r=activeReservations.find(x=>x.id===id);if(!r){setF(v=>({...v,reservation_id:null}));return;}setF(v=>({...v,reservation_id:r.id,variant_id:r.variant_id,location_id:r.location_id,item_id:r.item_id,quantity:r.quantity,external_reference:r.reference_code||v.external_reference}));}

  const scanMutation=useMutation({
    mutationFn:async(raw:string)=>{const normalized=normalizeScanIdentifier(raw);if(!normalized)throw new Error('QR یا شماره گارانتی را وارد کنید');const item=await inventoryApi.scanItem(normalized);if(!item.location_id)throw new Error('این واحد کالا در حال حاضر داخل قفس انبار نیست');return item},
    onSuccess:(item)=>{setF(v=>({...v,variant_id:item.variant_id,location_id:item.location_id!,item_id:item.id,quantity:1,reservation_id:activeReservations.find(r=>r.item_id===item.id)?.id??null}));toast.success('کالا از روی QR پیدا شد')},
    onError:e=>toast.error('اسکن/جستجو ناموفق',e instanceof Error?e.message:'')
  });

  const m=useMutation({mutationFn:()=>{
    if(!f.variant_id||!f.location_id)throw new Error('تنوع و قفس خروج را انتخاب کنید');
    if(availableItems.length>0&&!f.item_id)throw new Error('این موجودی سریال‌دار است؛ QR یا شماره گارانتی واحد واقعی را انتخاب کنید');
    if(!f.item_id&&!f.reservation_id&&f.quantity>availableQty)throw new Error(`موجودی قابل خروج این قفس فقط ${numberFa(availableQty)} عدد است`);
    if(f.disposition==='sale'&&!f.channel_id)throw new Error('برای فروش، کانال فروش را انتخاب کنید');
    return inventoryApi.createOutbound({...f,external_reference:f.external_reference||null,reason:f.reason||null});
  },onSuccess:async()=>{await Promise.all([qc.invalidateQueries({queryKey:['inventory']}),qc.invalidateQueries({queryKey:['inventory','reservations']}),qc.invalidateQueries({queryKey:['warranty']})]);setF({...emptyForm});setScan('');toast.success('خروج انبار ثبت شد')},onError:e=>toast.error('ثبت خروج ناموفق',e instanceof Error?e.message:'')});

  return <div className="space-y-6">
    <PageHeader title="خروج انبار" description="خروج با QR، شماره گارانتی یا انتخاب دستی؛ موجودی واقعی هر قفس قبل از ثبت نمایش داده می‌شود."/>
    <Card className="p-4 sm:p-5">
      <div className="grid gap-4 lg:grid-cols-[1fr_360px] lg:items-start">
        <form onSubmit={(e)=>{e.preventDefault();scanMutation.mutate(scan)}} className="grid gap-3 md:grid-cols-[1fr_auto] md:items-end">
          <Field label="اسکن QR / شماره گارانتی" hint="QR محصول را با دوربین بخوانید یا شماره روی لیبل را وارد کنید؛ تنوع، قفس و واحد کالا خودکار انتخاب می‌شود."><div className="relative"><QrCode className="absolute right-3 top-3 h-4 w-4 text-slate-400"/><Input autoFocus dir="ltr" className="pr-9" value={scan} onChange={e=>setScan(e.target.value)} placeholder="شماره گارانتی یا لینک QR"/></div></Field>
          <Button type="submit" loading={scanMutation.isPending}><Search className="h-4 w-4"/>پیدا کردن کالا</Button>
        </form>
        <QrCameraScanner disabled={scanMutation.isPending} onDetected={(value)=>{const normalized=normalizeScanIdentifier(value);setScan(normalized);scanMutation.mutate(normalized)}}/>
      </div>
    </Card>
    <div className="grid gap-6 xl:grid-cols-[450px_1fr]">
      <Card className="p-4 sm:p-5"><form onSubmit={(e:FormEvent)=>{e.preventDefault();m.mutate()}} className="space-y-4">
        <Field label="رزرو مرتبط (اختیاری)" hint="اگر خروج مربوط به سفارش رزروشده است، رزرو را انتخاب کنید."><Select value={f.reservation_id??''} onChange={e=>selectReservation(e.target.value)}><option value="">بدون رزرو</option>{activeReservations.map(r=><option key={r.id} value={r.id}>{r.reference_type}{r.reference_code?` · ${r.reference_code}`:''} · {variantLabel(r.variant_id)} · تعداد {r.quantity}</option>)}</Select></Field>
        <Field label="تنوع محصول" required><Select required disabled={!!f.reservation_id} value={f.variant_id||''} onChange={e=>setF({...f,variant_id:Number(e.target.value),location_id:0,item_id:null,reservation_id:null})}><option value="">انتخاب تنوع</option>{(variants.data?.map(v=>v.id)||knownVariantIds).map(id=><option key={id} value={id}>{variantLabel(id)}</option>)}</Select></Field>
        {f.variant_id>0&&<div className="rounded-2xl border border-slate-200 bg-slate-50 p-3"><div className="mb-2 flex items-center gap-2 text-sm font-black"><Warehouse className="h-4 w-4"/>موجودی این تنوع در انبار</div>{variantStocks.length===0?<p className="text-xs text-rose-600">برای این تنوع هیچ موجودی ثبت نشده است.</p>:<div className="space-y-1.5">{variantStocks.map(s=><button type="button" key={s.id} onClick={()=>setF(v=>({...v,location_id:s.location_id,item_id:null,reservation_id:null}))} className={`flex w-full items-center justify-between rounded-xl px-3 py-2 text-xs ${f.location_id===s.location_id?'bg-slate-900 text-white':'bg-white text-slate-700'}`}><span className="truncate pl-2">{locationName(s.location_id)}</span><span className="shrink-0 font-black">قابل خروج {numberFa(s.quantity)} · رزرو {numberFa(s.reserved)}</span></button>)}</div>}</div>}
        <Field label="قفس خروج" required><Select required disabled={!!f.reservation_id} value={f.location_id||''} onChange={e=>setF({...f,location_id:Number(e.target.value),item_id:null,reservation_id:null})}><option value="">انتخاب قفس</option>{(locations.data?.map(l=>l.id)||knownLocationIds).filter(id=>!f.variant_id||variantStocks.some(row=>row.location_id===id)).map(id=><option key={id} value={id}>{locationName(id)}</option>)}</Select></Field>
        {f.variant_id>0&&f.location_id>0&&<div className={`grid grid-cols-3 gap-2 rounded-2xl p-3 text-center text-xs ${physicalQty>0?'bg-emerald-50 text-emerald-900':'bg-rose-50 text-rose-900'}`}><div><span className="block opacity-70">قابل خروج</span><b className="text-lg">{numberFa(availableQty)}</b></div><div><span className="block opacity-70">رزرو</span><b className="text-lg">{numberFa(reservedQty)}</b></div><div><span className="block opacity-70">کل فیزیکی</span><b className="text-lg">{numberFa(physicalQty)}</b></div></div>}
        <Field label={availableItems.length?'واحد کالا / شماره گارانتی':'واحد کالا (اختیاری)'} required={availableItems.length>0} hint={availableItems.length?'برای موجودی سریال‌دار انتخاب واحد واقعی الزامی است.':'در موجودی غیرسریال‌دار می‌توان خروج تعدادی ثبت کرد.'}><Select disabled={!!f.reservation_id&&!!f.item_id} value={f.item_id??''} onChange={e=>selectItem(e.target.value)}><option value="">خروج تعدادی</option>{availableItems.map(i=><option key={i.id} value={i.id}>{i.warranty_serial||i.serial_number||'واحد کالا'}{i.status==='reserved'?' · رزروشده':''}</option>)}</Select></Field>
        <div className="grid grid-cols-2 gap-3"><Field label="تعداد"><Input min={1} max={!f.item_id?Math.max(availableQty,1):1} type="number" disabled={!!f.item_id||!!f.reservation_id} value={f.quantity} onChange={e=>setF({...f,quantity:Math.max(1,Number(e.target.value)||1)})}/></Field><Field label="نوع خروج"><Select value={f.disposition} onChange={e=>setF({...f,disposition:e.target.value as OutboundDisposition})}><option value="sale">فروش</option><option value="damage">خرابی/ضایعات</option><option value="loss">مفقودی</option><option value="return">مرجوعی</option>{!f.item_id&&<option value="other">سایر</option>}</Select></Field></div>
        <Field label="پلتفرم / کانال فروش" required={f.disposition==='sale'}><Select required={f.disposition==='sale'} value={f.channel_id??''} onChange={e=>setF({...f,channel_id:e.target.value?Number(e.target.value):null})}><option value="">انتخاب پلتفرم</option>{channels.data?.filter(c=>c.is_active).map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</Select></Field>
        {f.disposition==='sale'&&f.channel_id&&<div className="rounded-xl bg-emerald-50 p-3 text-sm text-emerald-900">قیمت واحد: <b>{moneyFa(selectedPrice?.effective_price??variants.data?.find(v=>v.id===f.variant_id)?.sale_price??0)}</b><div className="mt-1 text-xs">مبلغ تقریبی خروج: {moneyFa(Number(selectedPrice?.effective_price??variants.data?.find(v=>v.id===f.variant_id)?.sale_price??0)*f.quantity)}</div></div>}
        {availableItems.length>0&&!f.item_id&&<div className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">این قفس واحد سریال‌دار دارد؛ برای جلوگیری از مغایرت، QR همان واحدی که واقعاً خارج می‌شود را اسکن یا انتخاب کنید.</div>}
        <Field label="شماره سفارش یا مرجع خارجی"><Input value={f.external_reference} onChange={e=>setF({...f,external_reference:e.target.value})}/></Field><Field label="توضیحات"><Textarea value={f.reason} onChange={e=>setF({...f,reason:e.target.value})}/></Field><Button className="w-full" type="submit" loading={m.isPending} disabled={!f.variant_id||!f.location_id||(!f.item_id&&!f.reservation_id&&availableQty<=0)}>ثبت خروج قطعی</Button>
      </form></Card>
      <Card><div className="border-b p-5 font-black">آخرین خروج‌ها</div><div className="overflow-x-auto"><table className="w-full min-w-[750px] text-sm"><thead className="bg-slate-50"><tr><th className="p-3 text-right">زمان</th><th className="p-3 text-right">تنوع</th><th className="p-3 text-right">تعداد</th><th className="p-3 text-right">کانال</th><th className="p-3 text-right">مرجع</th><th className="p-3 text-right">مبلغ فروش</th></tr></thead><tbody>{history.data?.map(x=><tr key={x.id} className="border-t"><td className="p-3">{dateTimeFa(x.created_at)}</td><td className="p-3">{variantLabel(x.variant_id)}</td><td className="p-3 font-black">{Math.abs(x.quantity)}</td><td className="p-3">{channels.data?.find(c=>c.id===x.channel_id)?.name||'—'}</td><td className="p-3">{x.external_reference||'—'}</td><td className="p-3 font-black">{x.line_total!=null?moneyFa(x.line_total):'—'}</td></tr>)}</tbody></table></div></Card>
    </div>
  </div>
}
