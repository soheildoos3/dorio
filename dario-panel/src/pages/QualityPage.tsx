import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {useState,type FormEvent} from 'react';
import {ClipboardCheck,Printer,ShieldCheck} from 'lucide-react';
import {qualityApi,type QCPayload} from '../api/quality';
import {inventoryApi} from '../api/inventory';
import type {DefectSeverity,LabelType,Product,ProductItem,ProductVariant,QCRecordResult} from '../api/types';
import {useProducts,useVariants} from '../hooks/useReferenceData';
import {useToast} from '../components/feedback/ToastProvider';
import {Badge} from '../components/ui/Badge';
import {Button} from '../components/ui/Button';
import {Field,Input,Select,Textarea} from '../components/ui/Field';
import {Modal} from '../components/ui/Modal';
import {Card,CardHeader,PageHeader} from '../components/ui/Page';
import {QrPrintSettingsFields} from '../components/printing/QrPrintSettingsFields';
import {dateTimeFa} from '../lib/format';
import {labels} from '../lib/labels';
import {loadQrPrintSettings,saveQrPrintSettings,type QrPrintSettings} from '../lib/qrPrint';
import {useAuth} from '../auth/AuthProvider';

export function QualityPage(){
  const {can}=useAuth();
  const manage=can('quality.manage');
  const canPrint=can('quality.print');
  const canInventory=can('inventory.view');
  const canCatalog=can('catalog.view');
  const items=useQuery({queryKey:['inventory','items'],queryFn:()=>inventoryApi.items(),enabled:canInventory});
  const qc=useQuery({queryKey:['quality','qc'],queryFn:()=>qualityApi.qcRecords()});
  const logs=useQuery({queryKey:['quality','labels'],queryFn:()=>qualityApi.labels()});
  const variants=useVariants(canCatalog);
  const products=useProducts(canCatalog);
  const client=useQueryClient();
  const toast=useToast();
  const quickLog=useMutation({mutationFn:(p:{item_id:number;label_type:LabelType})=>qualityApi.logLabel(p),onSuccess:()=>client.invalidateQueries({queryKey:['quality','labels']}),onError:e=>toast.error('چاپ باز شد، اما ثبت لاگ چاپ ناموفق بود',e instanceof Error?e.message:'')});
  const[open,setOpen]=useState(false);
  const[labelOpen,setLabelOpen]=useState(false);
  const[batchOpen,setBatchOpen]=useState(false);
  const variantName=(id:number)=>{const v=variants.data?.find(x=>x.id===id);if(!v)return '—';const product=products.data?.find(p=>p.id===v.product_id)?.name||'محصول';const detail=v.resolved_attributes?.map(a=>a.value).join(' / ')||v.sku||'تنوع پایه';return `${product} · ${detail}`};
  const quickPrint=(itemId:number,type:LabelType)=>{qualityApi.print(itemId,type,loadQrPrintSettings());quickLog.mutate({item_id:itemId,label_type:type})};

  return <div className="space-y-6">
    <PageHeader title="کنترل کیفیت و چاپ" description="QR هر واحد بر پایه سریال یکتای همان کالا ساخته می‌شود و آدرس چاپ‌شده ثابت می‌ماند؛ مقصد QR را بعداً از تنظیمات گارانتی می‌توان تغییر داد."/>
    <div className="grid gap-6 xl:grid-cols-2">
      <Card><CardHeader title="واحدهای آماده کنترل" action={manage&&canInventory?<Button onClick={()=>setOpen(true)}><ClipboardCheck className="h-4 w-4"/>ثبت QC</Button>:undefined}/><div className="max-h-[500px] overflow-auto divide-y">{items.data?.map(i=><div key={i.id} className="flex flex-col items-stretch justify-between gap-3 p-4 sm:flex-row sm:items-center"><div><p className="font-bold" dir="ltr">{i.warranty_serial||i.serial_number||'واحد کالا'}</p><p className="text-xs text-slate-500">{variantName(i.variant_id)}</p></div><div className="flex flex-wrap items-center gap-2 max-sm:[&>button]:flex-1"><Badge tone={i.qc_status==='passed'?'green':i.qc_status==='failed'?'red':'amber'}>{labels.qcStatus[i.qc_status]}</Badge>{canPrint&&<Button size="sm" variant="secondary" onClick={()=>quickPrint(i.id,'warranty')}><Printer className="h-4 w-4"/>QR محصول</Button>}</div></div>)}</div></Card>
      <Card><CardHeader title="تاریخچه QC"/><div className="max-h-[500px] overflow-auto divide-y">{qc.data?.map(r=><div key={r.id} className="p-4"><div className="flex justify-between"><b>{items.data?.find(i=>i.id===r.item_id)?.warranty_serial||items.data?.find(i=>i.id===r.item_id)?.serial_number||'واحد کالا'}</b><Badge tone={r.result==='passed'?'green':'red'}>{labels.qcResult[r.result]}</Badge></div><p className="mt-2 text-xs text-slate-500">{r.defect_type||'بدون عیب'}{r.failure_action?` · ${r.failure_action==='rework'?'دوباره‌کاری':'ضایعات'}${r.waste_class?` (${r.waste_class==='normal'?'عادی':'غیرعادی'})`:''}`:''} · {r.notes||'بدون توضیح'}</p><p className="mt-2 text-[11px] text-slate-400">{dateTimeFa(r.checked_at)}</p></div>)}</div></Card>
    </div>
    <Card><CardHeader title="لاگ چاپ" description="تنظیمات اندازه آخرین چاپ در همین مرورگر ذخیره می‌شود و برای چاپ سریع بعدی استفاده خواهد شد." action={canPrint&&canInventory?<div className="flex flex-wrap gap-2">{canCatalog&&<Button variant="secondary" onClick={()=>setBatchOpen(true)}><Printer className="h-4 w-4"/>چاپ گروهی QR</Button>}<Button onClick={()=>setLabelOpen(true)}><Printer className="h-4 w-4"/>چاپ تکی</Button></div>:undefined}/><div className="overflow-x-auto"><table className="w-full min-w-[560px] text-sm"><thead><tr><th className="p-3 text-right">واحد</th><th>نوع</th><th>زمان</th></tr></thead><tbody>{logs.data?.map(l=><tr key={l.id} className="border-t"><td className="p-3">{items.data?.find(i=>i.id===l.item_id)?.warranty_serial||items.data?.find(i=>i.id===l.item_id)?.serial_number||'واحد کالا'}</td><td className="text-center">{labels.labelType[l.label_type]}</td><td className="text-center">{dateTimeFa(l.printed_at)}</td></tr>)}</tbody></table></div></Card>
    {manage&&canInventory&&<QCModal open={open} close={()=>setOpen(false)} items={items.data||[]} variantName={variantName}/>} 
    {canPrint&&canInventory&&<PrintModal open={labelOpen} close={()=>setLabelOpen(false)} items={items.data||[]} variantName={variantName}/>} 
    {canPrint&&canCatalog&&<BatchPrintModal open={batchOpen} close={()=>setBatchOpen(false)} variants={variants.data||[]} products={products.data||[]}/>} 
  </div>;
}

function QCModal({open,close,items,variantName}:{open:boolean;close:()=>void;items:ProductItem[];variantName:(id:number)=>string}){
  const toast=useToast();
  const client=useQueryClient();
  const[files,setFiles]=useState<File[]>([]);
  const[f,setF]=useState<QCPayload>({item_id:0,result:'passed',defect_type:null,defect_severity:null,failure_action:null,waste_class:null,notes:null,photos:null});
  const m=useMutation({mutationFn:async()=>{const photos=f.result==='failed'&&files.length?await Promise.all(files.map(async x=>(await qualityApi.uploadPhoto(f.item_id,x)).url)):null;return qualityApi.recordQC({...f,photos})},onSuccess:async()=>{await client.invalidateQueries({queryKey:['quality']});await client.invalidateQueries({queryKey:['inventory']});await client.invalidateQueries({queryKey:['manufacturing','orders']});await client.invalidateQueries({queryKey:['tailor-works']});close();toast.success('QC ثبت شد')},onError:e=>toast.error('ثبت QC ناموفق',e instanceof Error?e.message:'')});
  return <Modal open={open} onClose={close} title="ثبت کنترل کیفیت"><form onSubmit={(e:FormEvent)=>{e.preventDefault();m.mutate()}} className="space-y-4"><Field label="واحد فیزیکی"><Select required value={f.item_id||''} onChange={e=>setF({...f,item_id:Number(e.target.value)})}><option value="">انتخاب سریال</option>{items.map(i=><option key={i.id} value={i.id}>{i.warranty_serial||i.serial_number||'واحد کالا'} · {variantName(i.variant_id)}</option>)}</Select></Field><Field label="نتیجه"><Select value={f.result} onChange={e=>{const result=e.target.value as QCRecordResult;setF({...f,result,failure_action:result==='failed'?(f.failure_action||'rework'):null,waste_class:result==='failed'&&f.failure_action==='scrap'?(f.waste_class||'normal'):null})}}><option value="passed">تأیید</option><option value="failed">رد</option></Select></Field>{f.result==='failed'&&<><Field label="نوع عیب"><Input value={f.defect_type||''} onChange={e=>setF({...f,defect_type:e.target.value||null})}/></Field><Field label="شدت"><Select value={f.defect_severity||''} onChange={e=>setF({...f,defect_severity:(e.target.value||null) as DefectSeverity|null})}><option value="">انتخاب</option><option value="minor">جزئی</option><option value="major">مهم</option><option value="critical">بحرانی</option></Select></Field><Field label="تعیین تکلیف"><Select value={f.failure_action||'rework'} onChange={e=>setF({...f,failure_action:e.target.value as 'rework'|'scrap',waste_class:e.target.value==='rework'?null:(f.waste_class||'normal')})}><option value="rework">قابل اصلاح / دوباره‌کاری</option><option value="scrap">ضایعات / غیرقابل اصلاح</option></Select></Field>{f.failure_action==='scrap'&&<Field label="نوع ضایعات"><Select value={f.waste_class||'normal'} onChange={e=>setF({...f,waste_class:e.target.value as 'normal'|'abnormal'})}><option value="normal">عادی؛ جذب بهای محصول سالم</option><option value="abnormal">غیرعادی؛ هزینه دوره</option></Select></Field>}<Field label="عکس عیب"><Input type="file" multiple accept="image/jpeg,image/png,image/webp" onChange={e=>setFiles(Array.from(e.target.files||[]))}/></Field></>}<Field label="توضیحات"><Textarea value={f.notes||''} onChange={e=>setF({...f,notes:e.target.value||null})}/></Field><Button className="w-full" loading={m.isPending}><ShieldCheck className="h-4 w-4"/>ثبت</Button></form></Modal>;
}

function PrintModal({open,close,items,variantName}:{open:boolean;close:()=>void;items:ProductItem[];variantName:(id:number)=>string}){
  const toast=useToast();
  const client=useQueryClient();
  const[item,setItem]=useState(0);
  const[settings,setSettings]=useState<QrPrintSettings>(()=>loadQrPrintSettings());
  const type:LabelType='warranty';
  const m=useMutation({mutationFn:()=>qualityApi.logLabel({item_id:item,label_type:type}),onSuccess:async()=>{await client.invalidateQueries({queryKey:['quality','labels']});close();toast.success('پنجره چاپ QR محصول باز شد')},onError:e=>toast.error('پنجره چاپ باز شد، اما ثبت لاگ چاپ ناموفق بود',e instanceof Error?e.message:'')});
  return <Modal open={open} onClose={close} title="چاپ QR محصول" description="QR شامل مسیر ثابت سریال است؛ مقصد آن بدون نیاز به چاپ مجدد قابل تغییر خواهد بود."><form onSubmit={(e:FormEvent)=>{e.preventDefault();saveQrPrintSettings(settings);qualityApi.print(item,type,settings);m.mutate()}} className="space-y-4"><Field label="واحد"><Select required value={item||''} onChange={e=>setItem(Number(e.target.value))}><option value="">انتخاب سریال</option>{items.map(i=><option key={i.id} value={i.id}>{i.warranty_serial||i.serial_number||'واحد کالا'} · {variantName(i.variant_id)}</option>)}</Select></Field><QrPrintSettingsFields value={settings} onChange={setSettings}/><Button className="w-full" loading={m.isPending}><Printer className="h-4 w-4"/>چاپ QR محصول</Button></form></Modal>;
}

function BatchPrintModal({open,close,variants,products}:{open:boolean;close:()=>void;variants:ProductVariant[];products:Product[]}){
  const toast=useToast();
  const client=useQueryClient();
  const[variantId,setVariantId]=useState(0);
  const variantName=(v:ProductVariant)=>{const product=products.find(p=>p.id===v.product_id)?.name||'محصول';const detail=v.resolved_attributes?.map(a=>a.value).join(' / ')||v.sku||'تنوع پایه';return `${product} · ${detail}`};
  const type:LabelType='warranty';
  const[limit,setLimit]=useState(100);
  const[settings,setSettings]=useState<QrPrintSettings>(()=>loadQrPrintSettings());
  const m=useMutation({
    mutationFn:async(popup:Window|null)=>({result:await qualityApi.batchLabels({variant_id:variantId,label_type:type,limit}),popup}),
    onSuccess:async({result:r,popup})=>{
      await Promise.all([client.invalidateQueries({queryKey:['quality','labels']}),client.invalidateQueries({queryKey:['inventory','items']})]);
      saveQrPrintSettings(settings);
      const url=qualityApi.printBatchUrl(r.item_ids,type,settings);
      if(popup&&!popup.closed)popup.location.href=url;else qualityApi.printBatch(r.item_ids,type,settings);
      close();toast.success(`${r.count} QR یکتا در چیدمان ${settings.columns} ستونه برای چاپ آماده شد`);
    },
    onError:(e,popup)=>{if(popup&&!popup.closed)popup.close();toast.error('چاپ گروهی ناموفق',e instanceof Error?e.message:'')},
  });
  return <Modal open={open} onClose={close} title="چاپ گروهی QR محصول" description="QRها در یک شبکه کنار هم قرار می‌گیرند؛ تعداد ستون و اندازه‌ها را مطابق برچسب و چاپگر خودت تنظیم کن."><form onSubmit={(e:FormEvent)=>{e.preventDefault();const popup=window.open('about:blank','_blank');m.mutate(popup)}} className="space-y-4"><Field label="تنوع محصول"><Select required value={variantId||''} onChange={e=>setVariantId(Number(e.target.value))}><option value="">انتخاب تنوع</option>{variants.map(v=><option key={v.id} value={v.id}>{variantName(v)}</option>)}</Select></Field><Field label="تعداد QR"><Input type="number" min={1} max={200} value={limit} onChange={e=>setLimit(Math.max(1,Math.min(200,Number(e.target.value)||1)))}/></Field><QrPrintSettingsFields value={settings} onChange={setSettings} group/><p className="rounded-xl bg-sky-50 p-3 text-xs leading-6 text-sky-900">اگر ابعاد و تعداد ستون از عرض کاغذ بیشتر شود، سرور قبل از چاپ خطای واضح می‌دهد تا خروجی نصفه یا روی‌هم‌افتاده تولید نشود.</p><Button className="w-full" loading={m.isPending}><Printer className="h-4 w-4"/>آماده‌سازی و چاپ گروهی</Button></form></Modal>;
}
