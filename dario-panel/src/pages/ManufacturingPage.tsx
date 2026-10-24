import {useMemo,useState,type FormEvent} from 'react';
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {Factory,PackagePlus,Pencil,Play,Plus,RotateCcw,Send,ShieldCheck,Trash2,Wrench,Scale,UserRound} from 'lucide-react';
import {adminApi} from '../api/admin';
import {manufacturingApi} from '../api/manufacturing';
import type {BOM,LaborEntry,Material,OverheadRate,ProductionOrder} from '../api/types';
import {useAuth} from '../auth/AuthProvider';
import {useToast} from '../components/feedback/ToastProvider';
import {Badge} from '../components/ui/Badge';
import {Button} from '../components/ui/Button';
import {Field,Input,Select,Switch,Textarea} from '../components/ui/Field';
import {Modal} from '../components/ui/Modal';
import {Card,CardHeader,PageHeader} from '../components/ui/Page';
import {Tabs} from '../components/ui/Tabs';
import {useAllLocations,useProducts,useVariants} from '../hooks/useReferenceData';
import {dateFa,numberFa} from '../lib/format';

type Tab='orders'|'materials'|'bom'|'labor'|'overhead';
type ModalName='material'|'purchase'|'adjustment'|'bom'|'order'|'issueBom'|'returnMaterial'|'labor'|'overhead'|'absorb'|null;
const money=(v:string|number|null|undefined)=>`${numberFa(Number(v||0))} ریال`;
const statusFa:Record<string,string>={draft:'پیش‌نویس',materials_issued:'مواد صادرشده',in_production:'در حال تولید',waiting_qc:'در انتظار QC',completed:'تکمیل',rejected:'ردشده',cancelled:'لغوشده'};
const workStatusFa:Record<string,string>={open:'باز',completed:'تکمیل',cancelled:'لغو'};

export function ManufacturingPage(){
  const {can}=useAuth();
  const manage=can('manufacturing.manage');
  const laborManage=can('labor.manage');
  const laborApprove=can('labor.approve');
  const canWarehouse=can('warehouse.view');
  const canCatalog=can('catalog.view');
  const canTailors=can('tailors.view');
  const qc=useQueryClient();
  const toast=useToast();
  const [tab,setTab]=useState<Tab>('orders');
  const [modal,setModal]=useState<ModalName>(null);
  const [target,setTarget]=useState<ProductionOrder|null>(null);

  const materials=useQuery({queryKey:['manufacturing','materials'],queryFn:manufacturingApi.materials});
  const stock=useQuery({queryKey:['manufacturing','material-stock'],queryFn:manufacturingApi.materialStock});
  const movements=useQuery({queryKey:['manufacturing','material-movements'],queryFn:manufacturingApi.materialMovements});
  const boms=useQuery({queryKey:['manufacturing','boms'],queryFn:manufacturingApi.boms});
  const orders=useQuery({queryKey:['manufacturing','orders'],queryFn:manufacturingApi.orders});
  const labor=useQuery({queryKey:['manufacturing','labor'],queryFn:manufacturingApi.labor});
  const overhead=useQuery({queryKey:['manufacturing','overhead'],queryFn:manufacturingApi.overheadRates});
  const products=useProducts(canCatalog);
  const variants=useVariants(canCatalog);
  const locations=useAllLocations(canWarehouse);
  const tailors=useQuery({queryKey:['tailors'],queryFn:adminApi.tailors,enabled:canTailors});
  const tailorWorks=useQuery({queryKey:['tailor-works'],queryFn:()=>adminApi.works(),enabled:canTailors});

  const [materialForm,setMaterialForm]=useState({code:'',name:'',unit:'عدد',category:'',reorder_point:0,is_active:true});
  const [editingMaterial,setEditingMaterial]=useState<Material|null>(null);
  const [purchaseForm,setPurchaseForm]=useState({material_id:0,location_id:0,quantity:1,unit_cost:0,freight_cost:0,reference_ref:'',notes:''});
  const [adjustForm,setAdjustForm]=useState({material_id:0,location_id:0,quantity:1,direction:'increase' as 'increase'|'decrease',notes:''});
  const [bomForm,setBomForm]=useState({product_id:0,version:1,status:'active' as 'draft'|'active'|'retired',notes:'',items:[{material_id:0,quantity_per_unit:1,normal_waste_percent:0}]});
  const [editingBom,setEditingBom]=useState<BOM|null>(null);
  const [orderForm,setOrderForm]=useState({product_id:0,variant_id:0,quantity:1,tailor_user_id:0,bom_id:0,fg_location_id:0,due_at:'',notes:''});
  const [editingOrder,setEditingOrder]=useState<ProductionOrder|null>(null);
  const [rawLocation,setRawLocation]=useState(0);
  const [returnForm,setReturnForm]=useState({material_id:0,location_id:0,quantity:1,production_order_id:0,notes:''});
  const [laborForm,setLaborForm]=useState({production_order_id:0,tailor_user_id:0,work_date:new Date().toISOString().slice(0,10),hours:0,pieces:1,rate:0,rate_basis:'piece' as 'hour'|'piece',notes:''});
  const [editingLabor,setEditingLabor]=useState<LaborEntry|null>(null);
  const [overheadForm,setOverheadForm]=useState({name:'',basis:'piece' as 'piece'|'direct_labor_hour',rate:0,effective_from:new Date().toISOString().slice(0,10),effective_to:'',is_active:true});
  const [editingOverhead,setEditingOverhead]=useState<OverheadRate|null>(null);
  const [rateId,setRateId]=useState(0);

  const invalidate=async()=>{
    await Promise.all([
      ...['materials','material-stock','material-movements','boms','orders','labor','overhead'].map(k=>qc.invalidateQueries({queryKey:['manufacturing',k]})),
      qc.invalidateQueries({queryKey:['tailor-works']}),
      qc.invalidateQueries({queryKey:['tailor-stats']}),
    ]);
  };
  const close=()=>setModal(null);
  const err=(title:string,e:unknown)=>toast.error(title,e instanceof Error?e.message:'خطای ناشناخته');

  const materialMut=useMutation({
    mutationFn:()=>editingMaterial
      ? manufacturingApi.updateMaterial(editingMaterial.id,{name:materialForm.name,unit:materialForm.unit,category:materialForm.category||null,reorder_point:materialForm.reorder_point,is_active:materialForm.is_active})
      : manufacturingApi.createMaterial({...materialForm,category:materialForm.category||null}),
    onSuccess:async()=>{await invalidate();close();setEditingMaterial(null);toast.success(editingMaterial?'ماده اولیه ویرایش شد':'ماده اولیه تعریف شد')},
    onError:e=>err('ذخیره ماده ناموفق بود',e),
  });
  const materialDelete=useMutation({mutationFn:(id:number)=>manufacturingApi.deleteMaterial(id),onSuccess:async()=>{await invalidate();toast.success('ماده بدون سابقه حذف شد')},onError:e=>err('حذف ماده ممکن نیست',e)});
  const purchaseMut=useMutation({mutationFn:()=>manufacturingApi.purchase({...purchaseForm,reference_ref:purchaseForm.reference_ref||null,notes:purchaseForm.notes||null}),onSuccess:async()=>{await invalidate();close();toast.success('خرید مواد و میانگین موزون ثبت شد')},onError:e=>err('ثبت خرید ناموفق بود',e)});
  const adjustMut=useMutation({mutationFn:()=>manufacturingApi.adjust({...adjustForm,notes:adjustForm.notes||null}),onSuccess:async()=>{await invalidate();close();toast.success('اصلاح موجودی با سابقه ثبت شد')},onError:e=>err('اصلاح موجودی ناموفق بود',e)});
  const bomMut=useMutation({
    mutationFn:()=>editingBom
      ? manufacturingApi.updateBom(editingBom.id,{status:bomForm.status,notes:bomForm.notes||null,items:bomForm.items})
      : manufacturingApi.createBom({...bomForm,notes:bomForm.notes||null}),
    onSuccess:async()=>{await invalidate();close();setEditingBom(null);toast.success(editingBom?'BOM ویرایش شد':'نسخه BOM ذخیره شد')},
    onError:e=>err('ذخیره BOM ناموفق بود',e),
  });
  const bomDelete=useMutation({mutationFn:(id:number)=>manufacturingApi.deleteBom(id),onSuccess:async()=>{await invalidate();toast.success('BOM استفاده‌نشده حذف شد')},onError:e=>err('حذف BOM ممکن نیست',e)});
  const orderMut=useMutation({
    mutationFn:()=>{
      const common={tailor_user_id:orderForm.tailor_user_id||null,fg_location_id:orderForm.fg_location_id||null,due_at:orderForm.due_at||null,notes:orderForm.notes||null};
      if(editingOrder){
        return manufacturingApi.updateOrder(editingOrder.id,editingOrder.status==='draft'?{...common,product_id:orderForm.product_id,variant_id:orderForm.variant_id||null,quantity:orderForm.quantity,bom_id:orderForm.bom_id}:common);
      }
      return manufacturingApi.createOrder({...common,product_id:orderForm.product_id,variant_id:orderForm.variant_id||null,quantity:orderForm.quantity,bom_id:orderForm.bom_id});
    },
    onSuccess:async()=>{await invalidate();close();setEditingOrder(null);toast.success(editingOrder?'دستور تولید و کار خیاط همگام شد':'دستور تولید ساخته شد و برای خیاط نیز ایجاد شد')},
    onError:e=>err('ذخیره دستور ناموفق بود',e),
  });
  const orderDelete=useMutation({mutationFn:(id:number)=>manufacturingApi.deleteOrder(id),onSuccess:async()=>{await invalidate();toast.success('دستور پیش‌نویس حذف شد')},onError:e=>err('حذف دستور ممکن نیست',e)});
  const issueBom=useMutation({mutationFn:()=>manufacturingApi.issueBom(target!.id,rawLocation),onSuccess:async()=>{await invalidate();close();toast.success('مواد BOM به تولید حواله شد')},onError:e=>err('حواله مواد ناموفق بود',e)});
  const statusMut=useMutation({mutationFn:({id,status}:{id:number;status:string})=>manufacturingApi.setStatus(id,status),onSuccess:async()=>{await invalidate();toast.success('وضعیت دستور و کار خیاط همگام شد')},onError:e=>err('تغییر وضعیت ناموفق بود',e)});
  const prepareQc=useMutation({mutationFn:(o:ProductionOrder)=>manufacturingApi.prepareQc(o.id,o.fg_location_id),onSuccess:async()=>{await invalidate();toast.success('واحدهای فیزیکی و QR برای QC ساخته شدند')},onError:e=>err('آماده‌سازی QC ناموفق بود',e)});
  const returnMut=useMutation({mutationFn:()=>manufacturingApi.returnMaterial({...returnForm,notes:returnForm.notes||null}),onSuccess:async()=>{await invalidate();close();toast.success('برگشت مواد ثبت شد')},onError:e=>err('برگشت مواد ناموفق بود',e)});
  const laborMut=useMutation({
    mutationFn:()=>editingLabor
      ? manufacturingApi.updateLabor(editingLabor.id,{tailor_user_id:laborForm.tailor_user_id,work_date:laborForm.work_date,hours:laborForm.hours,pieces:laborForm.pieces,rate:laborForm.rate,rate_basis:laborForm.rate_basis,notes:laborForm.notes||null})
      : manufacturingApi.createLabor({...laborForm,notes:laborForm.notes||null}),
    onSuccess:async()=>{await invalidate();close();setEditingLabor(null);toast.success(editingLabor?'کارکرد ویرایش شد':'کارکرد ثبت شد و منتظر تأیید است')},
    onError:e=>err('ذخیره کارکرد ناموفق بود',e),
  });
  const laborDelete=useMutation({mutationFn:(id:number)=>manufacturingApi.deleteLabor(id),onSuccess:async()=>{await invalidate();toast.success('کارکرد در انتظار حذف شد')},onError:e=>err('حذف کارکرد ممکن نیست',e)});
  const approveLabor=useMutation({mutationFn:(id:number)=>manufacturingApi.approveLabor(id),onSuccess:async()=>{await invalidate();toast.success('دستمزد مستقیم تأیید و به WIP منتقل شد')},onError:e=>err('تأیید کارکرد ناموفق بود',e)});
  const overheadMut=useMutation({
    mutationFn:()=>editingOverhead
      ? manufacturingApi.updateOverheadRate(editingOverhead.id,{...overheadForm,effective_to:overheadForm.effective_to||null})
      : manufacturingApi.createOverheadRate({...overheadForm,effective_to:overheadForm.effective_to||null}),
    onSuccess:async()=>{await invalidate();close();setEditingOverhead(null);toast.success(editingOverhead?'نرخ سربار ویرایش شد':'نرخ جذب سربار ذخیره شد')},
    onError:e=>err('ذخیره نرخ ناموفق بود',e),
  });
  const overheadDelete=useMutation({mutationFn:(id:number)=>manufacturingApi.deleteOverheadRate(id),onSuccess:async()=>{await invalidate();toast.success('نرخ استفاده‌نشده حذف شد')},onError:e=>err('حذف نرخ ممکن نیست',e)});
  const absorb=useMutation({mutationFn:()=>manufacturingApi.absorbOverhead(target!.id,rateId),onSuccess:async()=>{await invalidate();close();toast.success('سربار جذب شد')},onError:e=>err('جذب سربار ناموفق بود',e)});

  const knownLocationIds=useMemo(()=>[...new Set([...(stock.data||[]).map(x=>x.location_id),...(orders.data||[]).map(x=>x.fg_location_id).filter((id):id is number=>!!id)])],[stock.data,orders.data]);
  const locationOptions=useMemo(()=>locations.data?.length?locations.data:knownLocationIds.map(id=>({id,path:`مکان ثبت‌شده #${id}`,name:null,warehouse_name:undefined})),[locations.data,knownLocationIds]);
  const productName=(id:number)=>products.data?.find(x=>x.id===id)?.name||`محصول ${id}`;
  const matName=(id:number)=>materials.data?.find(x=>x.id===id)?.name||`ماده ${id}`;
  const locName=(id:number|null)=>locationOptions.find(x=>x.id===id)?.path||locationOptions.find(x=>x.id===id)?.name||'—';
  const tailorName=(id:number|null)=>id?tailors.data?.find(t=>t.id===id)?.full_name||`خیاط #${id}`:'—';
  const variantLabel=(id:number|null)=>{const v=variants.data?.find(x=>x.id===id);if(!v)return id?`تنوع #${id}`:'—';return v.resolved_attributes?.map(a=>`${a.attribute_name}: ${a.value}`).join(' / ')||v.sku||`#${v.id}`};
  const bomCandidates=useMemo(()=>boms.data?.filter(b=>(b.status==='active'||b.id===editingOrder?.bom_id)&&(!orderForm.product_id||b.product_id===orderForm.product_id))||[],[boms.data,orderForm.product_id,editingOrder?.bom_id]);

  const startMaterial=(m?:Material)=>{
    setEditingMaterial(m||null);
    setMaterialForm(m?{code:m.code,name:m.name,unit:m.unit,category:m.category||'',reorder_point:Number(m.reorder_point),is_active:m.is_active}:{code:'',name:'',unit:'عدد',category:'',reorder_point:0,is_active:true});
    setModal('material');
  };
  const startBom=(b?:BOM)=>{
    setEditingBom(b||null);
    setBomForm(b?{product_id:b.product_id,version:b.version,status:b.status as 'draft'|'active'|'retired',notes:b.notes||'',items:b.items.map(i=>({material_id:i.material_id,quantity_per_unit:Number(i.quantity_per_unit),normal_waste_percent:Number(i.normal_waste_percent)}))}:{product_id:0,version:1,status:'active',notes:'',items:[{material_id:0,quantity_per_unit:1,normal_waste_percent:0}]});
    setModal('bom');
  };
  const startOrder=(o?:ProductionOrder)=>{
    setEditingOrder(o||null);
    setOrderForm(o?{product_id:o.product_id,variant_id:o.variant_id||0,quantity:o.quantity,tailor_user_id:o.tailor_user_id||0,bom_id:o.bom_id,fg_location_id:o.fg_location_id||0,due_at:o.due_at||'',notes:o.notes||''}:{product_id:0,variant_id:0,quantity:1,tailor_user_id:0,bom_id:0,fg_location_id:0,due_at:'',notes:''});
    setModal('order');
  };
  const startLabor=(l?:LaborEntry)=>{
    setEditingLabor(l||null);
    setLaborForm(l?{production_order_id:l.production_order_id,tailor_user_id:l.tailor_user_id,work_date:l.work_date,hours:Number(l.hours),pieces:l.pieces,rate:Number(l.rate),rate_basis:l.rate_basis as 'hour'|'piece',notes:l.notes||''}:{production_order_id:0,tailor_user_id:0,work_date:new Date().toISOString().slice(0,10),hours:0,pieces:1,rate:0,rate_basis:'piece',notes:''});
    setModal('labor');
  };
  const startOverhead=(r?:OverheadRate)=>{
    setEditingOverhead(r||null);
    setOverheadForm(r?{name:r.name,basis:r.basis as 'piece'|'direct_labor_hour',rate:Number(r.rate),effective_from:r.effective_from,effective_to:r.effective_to||'',is_active:r.is_active}:{name:'',basis:'piece',rate:0,effective_from:new Date().toISOString().slice(0,10),effective_to:'',is_active:true});
    setModal('overhead');
  };

  return <div className="space-y-6">
    <PageHeader
      title="تولید و مواد اولیه"
      description="مواد، BOM، دستور تولید و کار خیاط یک زنجیره واحدند. انتخاب یا تغییر خیاط در دستور تولید، کار همان خیاط را خودکار ایجاد و همگام می‌کند."
      action={manage&&canCatalog?<Button onClick={()=>startOrder()}><Factory className="h-4 w-4"/>دستور تولید</Button>:undefined}
    />
    {manage&&!canCatalog&&<Card className="border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">برای تعریف BOM و دستور تولید جدید، دسترسی مشاهده کاتالوگ لازم است. سوابق همچنان قابل مشاهده‌اند.</Card>}
    {manage&&!canWarehouse&&locationOptions.length===0&&<Card className="border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">هیچ مکان انباری شناخته‌شده‌ای نیست. برای انتخاب قفسه جدید، دسترسی مشاهده انبار لازم است.</Card>}
    <Tabs value={tab} onChange={setTab} items={[{id:'orders',label:'دستورهای تولید',count:orders.data?.length},{id:'materials',label:'مواد و کاردکس',count:materials.data?.length},{id:'bom',label:'BOM',count:boms.data?.length},{id:'labor',label:'کارکرد خیاط',count:labor.data?.length},{id:'overhead',label:'سربار',count:overhead.data?.length}]}/>

    {tab==='orders'&&<Card>
      <CardHeader title="دستورهای تولید" description="خیاط این جدول منبع اصلی تخصیص است؛ تا قبل از اولین تحویل قابل تغییر است و بعد از آن برای حفظ آمار قفل می‌شود." action={manage&&canCatalog?<Button size="sm" onClick={()=>startOrder()}><Plus className="h-4 w-4"/>دستور</Button>:undefined}/>
      <div className="overflow-x-auto"><table className="w-full min-w-[1460px] text-sm"><thead className="bg-slate-50"><tr><th className="p-3 text-right">شماره</th><th className="text-right">محصول / تنوع</th><th>تعداد</th><th>خیاط</th><th>پیشرفت خیاط</th><th>وضعیت</th><th>مواد</th><th>دستمزد</th><th>سربار</th><th>QC</th><th>موعد</th><th>عملیات</th></tr></thead><tbody>
        {orders.data?.map(o=>{const w=tailorWorks.data?.find(x=>x.production_order_id===o.id);const done=w?w.delivered_good:0;const remaining=Math.max(0,(w?.quantity||o.quantity)-done);return <tr key={o.id} className="border-t align-top"><td className="p-3 font-mono" dir="ltr">{o.order_no}</td><td className="py-3"><b>{productName(o.product_id)}</b><p className="mt-1 text-xs text-slate-500">{variantLabel(o.variant_id)}</p></td><td className="text-center">{numberFa(o.quantity)}</td><td className="text-center"><div className="inline-flex items-center gap-1.5"><UserRound className="h-3.5 w-3.5 text-slate-400"/>{tailorName(o.tailor_user_id)}</div></td><td className="text-center">{o.tailor_user_id?(w?<div><b>{numberFa(done)} / {numberFa(w.quantity)}</b><p className="mt-1 text-[11px] text-slate-500">مانده {numberFa(remaining)} · {workStatusFa[w.status]||w.status}</p></div>:<span className="text-amber-600">در حال همگام‌سازی</span>):'—'}</td><td className="text-center font-bold">{statusFa[o.status]||o.status}</td><td className="text-center">{money(o.material_cost)}</td><td className="text-center">{money(o.labor_cost)}</td><td className="text-center">{money(o.overhead_cost)}</td><td className="text-center">{numberFa(o.qc_passed)}✓ / {numberFa(o.qc_failed)}✕</td><td className="text-center">{dateFa(o.due_at)}</td><td className="p-2"><div className="flex flex-wrap justify-center gap-1">
          {manage&&!['completed','cancelled'].includes(o.status)&&<Button size="sm" variant="ghost" title="ویرایش" onClick={()=>startOrder(o)}><Pencil className="h-3.5 w-3.5"/></Button>}
          {manage&&o.status==='draft'&&<Button size="sm" variant="ghost" className="text-rose-600" title="حذف پیش‌نویس" onClick={()=>confirm(`دستور ${o.order_no} حذف شود؟ فقط دستور بدون سابقه حذف می‌شود.`)&&orderDelete.mutate(o.id)}><Trash2 className="h-3.5 w-3.5"/></Button>}
          {manage&&o.status==='draft'&&<Button size="sm" onClick={()=>{setTarget(o);setRawLocation(0);setModal('issueBom')}}><Send className="h-3.5 w-3.5"/>حواله BOM</Button>}
          {manage&&o.status==='materials_issued'&&<Button size="sm" onClick={()=>statusMut.mutate({id:o.id,status:'in_production'})}><Play className="h-3.5 w-3.5"/>شروع</Button>}
          {manage&&o.status==='in_production'&&<><Button size="sm" variant="secondary" onClick={()=>{setTarget(o);setRateId(0);setModal('absorb')}}>جذب سربار</Button><Button size="sm" onClick={()=>prepareQc.mutate(o)}><ShieldCheck className="h-3.5 w-3.5"/>ارسال QC</Button></>}
          {manage&&o.status==='rejected'&&<Button size="sm" onClick={()=>statusMut.mutate({id:o.id,status:'in_production'})}><Wrench className="h-3.5 w-3.5"/>دوباره‌کاری</Button>}
          {manage&&['materials_issued','in_production'].includes(o.status)&&<Button size="sm" variant="ghost" onClick={()=>{setReturnForm({material_id:0,location_id:0,quantity:1,production_order_id:o.id,notes:''});setModal('returnMaterial')}}><RotateCcw className="h-3.5 w-3.5"/>برگشت مواد</Button>}
          {manage&&!['completed','cancelled'].includes(o.status)&&<Button size="sm" variant="ghost" className="text-rose-600" onClick={()=>confirm(`دستور ${o.order_no} لغو شود؟ سابقه آن حفظ خواهد شد.`)&&statusMut.mutate({id:o.id,status:'cancelled'})}>لغو</Button>}
        </div></td></tr>})}
      </tbody></table></div>
    </Card>}

    {tab==='materials'&&<div className="space-y-4">
      <Card><CardHeader title="مواد اولیه" description="رکورد بدون سابقه قابل حذف است؛ برای موجودی دارای سابقه از اصلاح موجودی استفاده کن تا کاردکس و حسابداری خراب نشوند." action={manage?<div className="flex flex-wrap gap-2"><Button size="sm" variant="secondary" onClick={()=>startMaterial()}><Plus className="h-4 w-4"/>ماده</Button><Button size="sm" variant="secondary" onClick={()=>{setAdjustForm({material_id:0,location_id:0,quantity:1,direction:'increase',notes:''});setModal('adjustment')}}><Scale className="h-4 w-4"/>اصلاح موجودی</Button><Button size="sm" onClick={()=>setModal('purchase')}><PackagePlus className="h-4 w-4"/>خرید</Button></div>:undefined}/>
        <div className="overflow-x-auto"><table className="w-full min-w-[980px] text-sm"><thead className="bg-slate-50"><tr><th className="p-3 text-right">کد</th><th className="text-right">ماده</th><th>وضعیت</th><th>واحد</th><th>نقطه سفارش</th><th>میانگین موزون</th><th>موجودی کل</th>{manage&&<th>عملیات</th>}</tr></thead><tbody>{materials.data?.map(m=>{const qty=(stock.data||[]).filter(s=>s.material_id===m.id).reduce((a,s)=>a+Number(s.quantity),0);return <tr key={m.id} className="border-t"><td className="p-3 font-mono">{m.code}</td><td>{m.name}<p className="text-xs text-slate-500">{m.category||'بدون دسته'}</p></td><td className="text-center"><Badge tone={m.is_active?'green':'slate'}>{m.is_active?'فعال':'غیرفعال'}</Badge></td><td className="text-center">{m.unit}</td><td className="text-center">{numberFa(Number(m.reorder_point))}</td><td className="text-center">{money(m.weighted_average_cost)}</td><td className={`text-center font-black ${qty<=Number(m.reorder_point)?'text-rose-600':'text-emerald-700'}`}>{numberFa(qty)}</td>{manage&&<td><div className="flex justify-center gap-1"><Button size="sm" variant="ghost" onClick={()=>startMaterial(m)}><Pencil className="h-4 w-4"/></Button><Button size="sm" variant="ghost" className="text-rose-600" onClick={()=>confirm(`ماده «${m.name}» حذف شود؟ اگر سابقه داشته باشد سیستم اجازه حذف نمی‌دهد.`)&&materialDelete.mutate(m.id)}><Trash2 className="h-4 w-4"/></Button></div></td>}</tr>})}</tbody></table></div>
      </Card>
      <Card><CardHeader title="کاردکس مواد" description="حرکت‌های انبار سند تاریخی‌اند و حذف نمی‌شوند؛ اشتباه را با اصلاح افزایشی/کاهشی جبران کن."/><div className="overflow-x-auto"><table className="w-full min-w-[900px] text-sm"><thead className="bg-slate-50"><tr><th className="p-3 text-right">شماره</th><th>ماده</th><th>نوع</th><th>مقدار</th><th>قفسه</th><th>بهای واحد</th><th>کل</th><th>زمان</th></tr></thead><tbody>{movements.data?.map(m=><tr key={m.id} className="border-t"><td className="p-3 font-mono">{m.number}</td><td className="text-center">{matName(m.material_id)}</td><td className="text-center">{m.movement_type}</td><td className="text-center">{numberFa(Number(m.quantity))}</td><td className="text-center">{locName(m.location_id)}</td><td className="text-center">{money(m.unit_cost)}</td><td className="text-center">{money(m.total_cost)}</td><td className="text-center">{dateFa(m.created_at)}</td></tr>)}</tbody></table></div></Card>
    </div>}

    {tab==='bom'&&<Card><CardHeader title="فرمول ساخت نسخه‌دار" description="BOM استفاده‌نشده قابل ویرایش/حذف است؛ مواد نسخه‌ای که وارد دستور شده‌اند برای حفظ تاریخچه تغییر نمی‌کنند." action={manage&&canCatalog?<Button size="sm" onClick={()=>startBom()}><Plus className="h-4 w-4"/>BOM</Button>:undefined}/><div className="divide-y">{boms.data?.map(b=><div key={b.id} className="p-5"><div className="flex flex-wrap items-start justify-between gap-3"><div><b>{productName(b.product_id)} · نسخه {numberFa(b.version)}</b><div className="mt-1 flex items-center gap-2"><Badge tone={b.status==='active'?'green':b.status==='draft'?'amber':'slate'}>{b.status==='active'?'فعال':b.status==='draft'?'پیش‌نویس':'بازنشسته'}</Badge><span className="text-xs text-slate-500">{b.notes||'بدون توضیح'}</span></div></div><div className="flex items-center gap-1"><span className="ml-2 text-xs font-bold">{numberFa(b.items.length)} ماده</span>{manage&&<><Button size="sm" variant="ghost" onClick={()=>startBom(b)}><Pencil className="h-4 w-4"/></Button><Button size="sm" variant="ghost" className="text-rose-600" onClick={()=>confirm('این BOM حذف شود؟ فقط نسخه استفاده‌نشده حذف می‌شود.')&&bomDelete.mutate(b.id)}><Trash2 className="h-4 w-4"/></Button></>}</div></div><div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{b.items.map(i=><div key={i.id} className="rounded-xl bg-slate-50 p-3 text-sm"><b>{i.material.name}</b><p className="mt-1 text-xs text-slate-500">{numberFa(Number(i.quantity_per_unit))} {i.material.unit} / واحد · ضایعات عادی {numberFa(Number(i.normal_waste_percent))}%</p></div>)}</div></div>)}</div></Card>}

    {tab==='labor'&&<Card><CardHeader title="کارکرد و دستمزد مستقیم" description="کارکرد در انتظار قابل ویرایش و حذف است؛ پس از تأیید به حسابداری می‌رود و برای حفظ سند مالی دیگر قابل حذف نیست." action={laborManage?<Button size="sm" onClick={()=>startLabor()}><Plus className="h-4 w-4"/>کارکرد</Button>:undefined}/><div className="overflow-x-auto"><table className="w-full min-w-[1050px] text-sm"><thead className="bg-slate-50"><tr><th className="p-3 text-right">دستور</th><th>خیاط</th><th>تاریخ</th><th>مبنا</th><th>نرخ</th><th>مبلغ</th><th>وضعیت</th><th>عملیات</th></tr></thead><tbody>{labor.data?.map(l=><tr key={l.id} className="border-t"><td className="p-3 text-right">{orders.data?.find(o=>o.id===l.production_order_id)?.order_no||l.production_order_id}</td><td className="text-center">{tailorName(l.tailor_user_id)}</td><td className="text-center">{dateFa(l.work_date)}</td><td className="text-center">{l.rate_basis==='piece'?`${numberFa(l.pieces)} قطعه`:`${numberFa(Number(l.hours))} ساعت`}</td><td className="text-center">{money(l.rate)}</td><td className="text-center font-black">{money(l.amount)}</td><td className="text-center"><Badge tone={l.status==='approved'?'green':'amber'}>{l.status==='approved'?'تأیید':'در انتظار'}</Badge></td><td><div className="flex justify-center gap-1">{laborManage&&l.status==='pending'&&<><Button size="sm" variant="ghost" onClick={()=>startLabor(l)}><Pencil className="h-4 w-4"/></Button><Button size="sm" variant="ghost" className="text-rose-600" onClick={()=>confirm('کارکرد در انتظار حذف شود؟')&&laborDelete.mutate(l.id)}><Trash2 className="h-4 w-4"/></Button></>}{laborApprove&&l.status==='pending'&&<Button size="sm" onClick={()=>approveLabor.mutate(l.id)}>تأیید</Button>}</div></td></tr>)}</tbody></table></div></Card>}

    {tab==='overhead'&&<Card><CardHeader title="نرخ جذب سربار" description="نرخ استفاده‌نشده قابل حذف است؛ نرخ استفاده‌شده را غیرفعال کن و نرخ جدید بساز تا تاریخچه بهای تمام‌شده ثابت بماند." action={manage?<Button size="sm" onClick={()=>startOverhead()}><Plus className="h-4 w-4"/>نرخ</Button>:undefined}/><div className="divide-y">{overhead.data?.map(r=><div key={r.id} className="flex flex-wrap items-center justify-between gap-3 p-4"><div><div className="flex items-center gap-2"><b>{r.name}</b><Badge tone={r.is_active?'green':'slate'}>{r.is_active?'فعال':'غیرفعال'}</Badge></div><p className="mt-1 text-xs text-slate-500">{r.basis==='piece'?'هر قطعه':'هر ساعت کار مستقیم'} · از {dateFa(r.effective_from)}{r.effective_to?` تا ${dateFa(r.effective_to)}`:''}</p></div><div className="flex items-center gap-2"><b>{money(r.rate)}</b>{manage&&<><Button size="sm" variant="ghost" onClick={()=>startOverhead(r)}><Pencil className="h-4 w-4"/></Button><Button size="sm" variant="ghost" className="text-rose-600" onClick={()=>confirm('این نرخ حذف شود؟ اگر قبلاً جذب شده باشد سیستم اجازه حذف نمی‌دهد.')&&overheadDelete.mutate(r.id)}><Trash2 className="h-4 w-4"/></Button></>}</div></div>)}</div></Card>}

    <Modal open={modal==='material'} onClose={close} title={editingMaterial?'ویرایش ماده اولیه':'ماده اولیه جدید'}>
      <form onSubmit={(e:FormEvent)=>{e.preventDefault();materialMut.mutate()}} className="space-y-4">
        <Field label="کد" hint={editingMaterial?'کد ماده بعد از ایجاد ثابت می‌ماند.':undefined}><Input required dir="ltr" disabled={!!editingMaterial} value={materialForm.code} onChange={e=>setMaterialForm({...materialForm,code:e.target.value})}/></Field>
        <Field label="نام"><Input required value={materialForm.name} onChange={e=>setMaterialForm({...materialForm,name:e.target.value})}/></Field>
        <div className="grid gap-3 sm:grid-cols-2"><Field label="واحد"><Input required value={materialForm.unit} onChange={e=>setMaterialForm({...materialForm,unit:e.target.value})}/></Field><Field label="نقطه سفارش"><Input type="number" min={0} step="0.0001" value={materialForm.reorder_point} onChange={e=>setMaterialForm({...materialForm,reorder_point:Number(e.target.value)})}/></Field></div>
        <Field label="دسته"><Input value={materialForm.category} onChange={e=>setMaterialForm({...materialForm,category:e.target.value})}/></Field>
        <Switch checked={materialForm.is_active} onChange={is_active=>setMaterialForm({...materialForm,is_active})} label="ماده فعال باشد"/>
        <Button className="w-full" loading={materialMut.isPending}>{editingMaterial?'ذخیره تغییرات':'ذخیره'}</Button>
      </form>
    </Modal>

    <Modal open={modal==='purchase'} onClose={close} title="خرید مواد" description="خرید ثبت‌شده سند موجودی و حسابداری دارد و حذف نمی‌شود؛ اشتباه بعدی با اصلاح موجودی/سند اصلاحی جبران می‌شود.">
      <form onSubmit={(e:FormEvent)=>{e.preventDefault();purchaseMut.mutate()}} className="space-y-4"><Field label="ماده"><Select required value={purchaseForm.material_id||''} onChange={e=>setPurchaseForm({...purchaseForm,material_id:Number(e.target.value)})}><option value="">انتخاب</option>{materials.data?.filter(m=>m.is_active).map(m=><option key={m.id} value={m.id}>{m.code} · {m.name}</option>)}</Select></Field><Field label="قفسه مقصد"><LocationSelect value={purchaseForm.location_id} onChange={v=>setPurchaseForm({...purchaseForm,location_id:v})} locations={locationOptions}/></Field><div className="grid gap-3 sm:grid-cols-3"><Field label="مقدار"><Input type="number" min={0.0001} step="0.0001" value={purchaseForm.quantity} onChange={e=>setPurchaseForm({...purchaseForm,quantity:Number(e.target.value)})}/></Field><Field label="بهای واحد"><Input type="number" min={0} value={purchaseForm.unit_cost} onChange={e=>setPurchaseForm({...purchaseForm,unit_cost:Number(e.target.value)})}/></Field><Field label="کرایه قابل انتساب"><Input type="number" min={0} value={purchaseForm.freight_cost} onChange={e=>setPurchaseForm({...purchaseForm,freight_cost:Number(e.target.value)})}/></Field></div><Field label="مرجع خرید"><Input value={purchaseForm.reference_ref} onChange={e=>setPurchaseForm({...purchaseForm,reference_ref:e.target.value})}/></Field><Field label="یادداشت"><Textarea value={purchaseForm.notes} onChange={e=>setPurchaseForm({...purchaseForm,notes:e.target.value})}/></Field><Button className="w-full" loading={purchaseMut.isPending}>ثبت خرید و سند</Button></form>
    </Modal>

    <Modal open={modal==='adjustment'} onClose={close} title="اصلاح موجودی مواد" description="برای اصلاح اشتباهات شمارش یا ثبت قبلی؛ این عملیات در کاردکس باقی می‌ماند.">
      <form onSubmit={(e:FormEvent)=>{e.preventDefault();adjustMut.mutate()}} className="space-y-4"><Field label="ماده"><Select required value={adjustForm.material_id||''} onChange={e=>setAdjustForm({...adjustForm,material_id:Number(e.target.value)})}><option value="">انتخاب</option>{materials.data?.map(m=><option key={m.id} value={m.id}>{m.code} · {m.name}</option>)}</Select></Field><Field label="قفسه"><LocationSelect value={adjustForm.location_id} onChange={v=>setAdjustForm({...adjustForm,location_id:v})} locations={locationOptions}/></Field><div className="grid gap-3 sm:grid-cols-2"><Field label="نوع اصلاح"><Select value={adjustForm.direction} onChange={e=>setAdjustForm({...adjustForm,direction:e.target.value as 'increase'|'decrease'})}><option value="increase">افزایش موجودی</option><option value="decrease">کاهش موجودی</option></Select></Field><Field label="مقدار"><Input type="number" min={0.0001} step="0.0001" value={adjustForm.quantity} onChange={e=>setAdjustForm({...adjustForm,quantity:Number(e.target.value)})}/></Field></div><Field label="علت اصلاح"><Textarea required value={adjustForm.notes} onChange={e=>setAdjustForm({...adjustForm,notes:e.target.value})}/></Field><Button className="w-full" loading={adjustMut.isPending}>ثبت اصلاح با سابقه</Button></form>
    </Modal>

    <Modal open={modal==='bom'} onClose={close} title={editingBom?'ویرایش BOM':'BOM جدید'}>
      <form onSubmit={(e:FormEvent)=>{e.preventDefault();bomMut.mutate()}} className="space-y-4"><div className="grid gap-3 sm:grid-cols-2"><Field label="محصول"><Select required disabled={!!editingBom} value={bomForm.product_id||''} onChange={e=>setBomForm({...bomForm,product_id:Number(e.target.value)})}><option value="">انتخاب</option>{products.data?.filter(p=>p.is_manufacturable).map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</Select></Field><Field label="نسخه"><Input type="number" min={1} disabled={!!editingBom} value={bomForm.version} onChange={e=>setBomForm({...bomForm,version:Number(e.target.value)})}/></Field></div><Field label="وضعیت"><Select value={bomForm.status} onChange={e=>setBomForm({...bomForm,status:e.target.value as typeof bomForm.status})}><option value="draft">پیش‌نویس</option><option value="active">فعال</option><option value="retired">بازنشسته</option></Select></Field><div className="space-y-2">{bomForm.items.map((r,i)=><div key={i} className="grid gap-2 rounded-xl border p-3 sm:grid-cols-[2fr_1fr_1fr_auto]"><Select value={r.material_id||''} onChange={e=>setBomForm({...bomForm,items:bomForm.items.map((x,k)=>k===i?{...x,material_id:Number(e.target.value)}:x)})}><option value="">ماده</option>{materials.data?.filter(m=>m.is_active||m.id===r.material_id).map(m=><option key={m.id} value={m.id}>{m.name} ({m.unit})</option>)}</Select><Input type="number" min={0.0001} step="0.0001" value={r.quantity_per_unit} onChange={e=>setBomForm({...bomForm,items:bomForm.items.map((x,k)=>k===i?{...x,quantity_per_unit:Number(e.target.value)}:x)})}/><Input type="number" min={0} max={100} step="0.01" value={r.normal_waste_percent} onChange={e=>setBomForm({...bomForm,items:bomForm.items.map((x,k)=>k===i?{...x,normal_waste_percent:Number(e.target.value)}:x)})}/>{bomForm.items.length>1?<Button type="button" variant="ghost" size="sm" onClick={()=>setBomForm({...bomForm,items:bomForm.items.filter((_,k)=>k!==i)})}>×</Button>:<span/>}</div>)}</div><Button type="button" variant="secondary" onClick={()=>setBomForm({...bomForm,items:[...bomForm.items,{material_id:0,quantity_per_unit:1,normal_waste_percent:0}]})}><Plus className="h-4 w-4"/>ماده دیگر</Button><Field label="یادداشت"><Textarea value={bomForm.notes} onChange={e=>setBomForm({...bomForm,notes:e.target.value})}/></Field><Button className="w-full" loading={bomMut.isPending}>{editingBom?'ذخیره تغییرات':'ذخیره BOM'}</Button></form>
    </Modal>

    <Modal open={modal==='order'} onClose={close} title={editingOrder?`ویرایش ${editingOrder.order_no}`:'دستور تولید'} description={editingOrder&&editingOrder.status!=='draft'?'بعد از حواله مواد، محصول/تنوع/تعداد/BOM ثابت‌اند؛ خیاط، موعد و یادداشت همچنان قابل اصلاح‌اند.':'با انتخاب خیاط، کار او خودکار ساخته و به همین دستور لینک می‌شود.'}>
      <form onSubmit={(e:FormEvent)=>{e.preventDefault();orderMut.mutate()}} className="space-y-4"><Field label="محصول"><Select required disabled={!!editingOrder&&editingOrder.status!=='draft'} value={orderForm.product_id||''} onChange={e=>setOrderForm({...orderForm,product_id:Number(e.target.value),variant_id:0,bom_id:0})}><option value="">انتخاب</option>{products.data?.filter(p=>p.is_manufacturable||p.id===orderForm.product_id).map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</Select></Field><Field label="تنوع محصول"><Select disabled={!!editingOrder&&editingOrder.status!=='draft'} value={orderForm.variant_id||''} onChange={e=>setOrderForm({...orderForm,variant_id:Number(e.target.value)||0})}><option value="">انتخاب تنوع</option>{variants.data?.filter(v=>v.product_id===orderForm.product_id&&(v.is_active||v.id===orderForm.variant_id)).map(v=><option key={v.id} value={v.id}>{variantLabel(v.id)}</option>)}</Select></Field><Field label="نسخه BOM"><Select required disabled={!!editingOrder&&editingOrder.status!=='draft'} value={orderForm.bom_id||''} onChange={e=>setOrderForm({...orderForm,bom_id:Number(e.target.value)})}><option value="">انتخاب</option>{bomCandidates.map(b=><option key={b.id} value={b.id}>نسخه {b.version} · {b.status}</option>)}</Select></Field><div className="grid gap-3 sm:grid-cols-2"><Field label="تعداد"><Input type="number" min={1} disabled={!!editingOrder&&editingOrder.status!=='draft'} value={orderForm.quantity} onChange={e=>setOrderForm({...orderForm,quantity:Number(e.target.value)})}/></Field><Field label="موعد"><Input type="date" value={orderForm.due_at} onChange={e=>setOrderForm({...orderForm,due_at:e.target.value})}/></Field></div><Field label="خیاط" hint="تا قبل از اولین تحویل می‌توان خیاط را تغییر داد؛ بعد از ثبت تحویل/QC برای حفظ آمار، تغییر خیاط مسدود می‌شود."><Select value={orderForm.tailor_user_id||''} onChange={e=>setOrderForm({...orderForm,tailor_user_id:Number(e.target.value)||0})}><option value="">بدون خیاط مشخص</option>{tailors.data?.map(t=><option key={t.id} value={t.id}>{t.full_name}</option>)}</Select></Field><Field label="قفسه محصول نهایی"><LocationSelect value={orderForm.fg_location_id} onChange={v=>setOrderForm({...orderForm,fg_location_id:v})} locations={locationOptions}/></Field><Field label="یادداشت"><Textarea value={orderForm.notes} onChange={e=>setOrderForm({...orderForm,notes:e.target.value})}/></Field><Button className="w-full" loading={orderMut.isPending}>{editingOrder?'ذخیره تغییرات':'ساخت دستور و کار خیاط'}</Button></form>
    </Modal>

    <Modal open={modal==='issueBom'} onClose={close} title="حواله مواد BOM" description={target?.order_no}><form onSubmit={(e:FormEvent)=>{e.preventDefault();issueBom.mutate()}} className="space-y-4"><Field label="قفسه مواد"><LocationSelect value={rawLocation} onChange={setRawLocation} locations={locationOptions}/></Field><Button className="w-full" loading={issueBom.isPending} disabled={!rawLocation}>حواله و انتقال هزینه به WIP</Button></form></Modal>
    <Modal open={modal==='returnMaterial'} onClose={close} title="برگشت مواد از تولید"><form onSubmit={(e:FormEvent)=>{e.preventDefault();returnMut.mutate()}} className="space-y-4"><Field label="ماده"><Select value={returnForm.material_id||''} onChange={e=>setReturnForm({...returnForm,material_id:Number(e.target.value)})}><option value="">انتخاب</option>{materials.data?.map(m=><option key={m.id} value={m.id}>{m.name}</option>)}</Select></Field><Field label="قفسه مقصد"><LocationSelect value={returnForm.location_id} onChange={v=>setReturnForm({...returnForm,location_id:v})} locations={locationOptions}/></Field><Field label="مقدار"><Input type="number" min={0.0001} step="0.0001" value={returnForm.quantity} onChange={e=>setReturnForm({...returnForm,quantity:Number(e.target.value)})}/></Field><Field label="یادداشت"><Textarea value={returnForm.notes} onChange={e=>setReturnForm({...returnForm,notes:e.target.value})}/></Field><Button className="w-full" loading={returnMut.isPending}>ثبت برگشت</Button></form></Modal>

    <Modal open={modal==='labor'} onClose={close} title={editingLabor?'ویرایش کارکرد':'ثبت کارکرد'} description={editingLabor?'دستور تولید کارکرد ثابت است؛ تا قبل از تأیید بقیه اطلاعات قابل اصلاح‌اند.':undefined}><form onSubmit={(e:FormEvent)=>{e.preventDefault();laborMut.mutate()}} className="space-y-4"><Field label="دستور تولید"><Select required disabled={!!editingLabor} value={laborForm.production_order_id||''} onChange={e=>{const id=Number(e.target.value);const order=orders.data?.find(o=>o.id===id);setLaborForm({...laborForm,production_order_id:id,tailor_user_id:order?.tailor_user_id||laborForm.tailor_user_id})}}><option value="">انتخاب</option>{orders.data?.filter(o=>['in_production','waiting_qc','rejected'].includes(o.status)||o.id===editingLabor?.production_order_id).map(o=><option key={o.id} value={o.id}>{o.order_no} · {productName(o.product_id)}</option>)}</Select></Field><Field label="خیاط" hint={orders.data?.find(o=>o.id===laborForm.production_order_id)?.tailor_user_id?'برای این دستور، خیاط از خود دستور تولید تعیین می‌شود.':undefined}><Select required disabled={!!orders.data?.find(o=>o.id===laborForm.production_order_id)?.tailor_user_id} value={laborForm.tailor_user_id||''} onChange={e=>setLaborForm({...laborForm,tailor_user_id:Number(e.target.value)})}><option value="">انتخاب</option>{tailors.data?.map(t=><option key={t.id} value={t.id}>{t.full_name}</option>)}</Select></Field><div className="grid gap-3 sm:grid-cols-2"><Field label="مبنای نرخ"><Select value={laborForm.rate_basis} onChange={e=>setLaborForm({...laborForm,rate_basis:e.target.value as 'hour'|'piece'})}><option value="piece">قطعه</option><option value="hour">ساعت</option></Select></Field><Field label="نرخ"><Input type="number" min={0} value={laborForm.rate} onChange={e=>setLaborForm({...laborForm,rate:Number(e.target.value)})}/></Field></div>{laborForm.rate_basis==='piece'?<Field label="تعداد قطعه"><Input type="number" min={1} value={laborForm.pieces} onChange={e=>setLaborForm({...laborForm,pieces:Number(e.target.value),hours:0})}/></Field>:<Field label="ساعت"><Input type="number" min={0.01} step="0.25" value={laborForm.hours} onChange={e=>setLaborForm({...laborForm,hours:Number(e.target.value),pieces:0})}/></Field>}<Field label="تاریخ"><Input type="date" value={laborForm.work_date} onChange={e=>setLaborForm({...laborForm,work_date:e.target.value})}/></Field><Field label="یادداشت"><Textarea value={laborForm.notes} onChange={e=>setLaborForm({...laborForm,notes:e.target.value})}/></Field><Button className="w-full" loading={laborMut.isPending}>{editingLabor?'ذخیره تغییرات':'ثبت برای تأیید'}</Button></form></Modal>

    <Modal open={modal==='overhead'} onClose={close} title={editingOverhead?'ویرایش نرخ سربار':'نرخ جذب سربار'}><form onSubmit={(e:FormEvent)=>{e.preventDefault();overheadMut.mutate()}} className="space-y-4"><Field label="نام"><Input required value={overheadForm.name} onChange={e=>setOverheadForm({...overheadForm,name:e.target.value})}/></Field><Field label="مبنا"><Select value={overheadForm.basis} onChange={e=>setOverheadForm({...overheadForm,basis:e.target.value as typeof overheadForm.basis})}><option value="piece">هر قطعه</option><option value="direct_labor_hour">هر ساعت کار مستقیم</option></Select></Field><Field label="نرخ"><Input type="number" min={0} value={overheadForm.rate} onChange={e=>setOverheadForm({...overheadForm,rate:Number(e.target.value)})}/></Field><div className="grid gap-3 sm:grid-cols-2"><Field label="از تاریخ"><Input type="date" value={overheadForm.effective_from} onChange={e=>setOverheadForm({...overheadForm,effective_from:e.target.value})}/></Field><Field label="تا تاریخ"><Input type="date" value={overheadForm.effective_to} onChange={e=>setOverheadForm({...overheadForm,effective_to:e.target.value})}/></Field></div><Switch checked={overheadForm.is_active} onChange={is_active=>setOverheadForm({...overheadForm,is_active})} label="نرخ فعال باشد"/><Button className="w-full" loading={overheadMut.isPending}>{editingOverhead?'ذخیره تغییرات':'ذخیره'}</Button></form></Modal>
    <Modal open={modal==='absorb'} onClose={close} title="جذب سربار" description={target?.order_no}><form onSubmit={(e:FormEvent)=>{e.preventDefault();absorb.mutate()}} className="space-y-4"><Field label="نرخ"><Select value={rateId||''} onChange={e=>setRateId(Number(e.target.value))}><option value="">انتخاب نرخ</option>{overhead.data?.filter(r=>r.is_active).map(r=><option key={r.id} value={r.id}>{r.name} · {money(r.rate)}</option>)}</Select></Field><Button className="w-full" loading={absorb.isPending} disabled={!rateId}>جذب به دستور</Button></form></Modal>
  </div>;
}

function LocationSelect({value,onChange,locations}:{value:number;onChange:(v:number)=>void;locations:Array<{id:number;path:string;name:string|null;warehouse_name?:string}>}){
  return <Select required value={value||''} onChange={e=>onChange(Number(e.target.value))}><option value="">انتخاب قفسه</option>{locations.filter(l=>l.id).map(l=><option key={l.id} value={l.id}>{l.warehouse_name?`${l.warehouse_name} · `:''}{l.path||l.name||l.id}</option>)}</Select>;
}
