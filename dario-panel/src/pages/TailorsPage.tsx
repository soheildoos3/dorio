import {useEffect,useMemo,useState,type FormEvent} from 'react';
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {AlertTriangle,ClipboardList,Factory,Pencil,Scissors,Trash2} from 'lucide-react';
import {adminApi} from '../api/admin';
import {useAuth} from '../auth/AuthProvider';
import {catalogApi} from '../api/catalog';
import type {TailorWork} from '../api/types';
import {useToast} from '../components/feedback/ToastProvider';
import {Button} from '../components/ui/Button';
import {Field,Input,Select,Textarea} from '../components/ui/Field';
import {Modal} from '../components/ui/Modal';
import {Badge} from '../components/ui/Badge';
import {Card,CardHeader,PageHeader} from '../components/ui/Page';
import {dateFa,numberFa} from '../lib/format';

const emptyWork={tailor_user_id:0,product_id:null as number|null,quantity:1,due_at:'',notes:''};

export function TailorsPage(){
  const {auth,can}=useAuth();
  const manage=can('tailors.manage');
  const canReport=manage||can('tailors.report');
  const canCatalog=can('catalog.view');
  const tailors=useQuery({queryKey:['tailors'],queryFn:adminApi.tailors});
  const works=useQuery({queryKey:['tailor-works'],queryFn:()=>adminApi.works()});
  const stats=useQuery({queryKey:['tailor-stats'],queryFn:adminApi.stats});
  const products=useQuery({queryKey:['catalog','products'],queryFn:catalogApi.products,enabled:canCatalog});
  const client=useQueryClient();
  const toast=useToast();
  const [selected,setSelected]=useState<number|null>(null);
  const [modal,setModal]=useState<'work'|'report'|'edit'|null>(null);
  const [target,setTarget]=useState<TailorWork|null>(null);
  const [work,setWork]=useState(emptyWork);
  const [report,setReport]=useState({delivered_good:0,returned_for_fix:0,damaged:0,notes:''});
  const [edit,setEdit]=useState({tailor_user_id:0,product_id:null as number|null,quantity:1,due_at:'',status:'open',notes:''});

  const rows=useMemo(()=> (tailors.data||[]).map(t=>({...t,stats:stats.data?.find(s=>s.tailor_user_id===t.id)})),[tailors.data,stats.data]);
  useEffect(()=>{
    if(auth?.user.user_type==='tailor'&&selected===null)setSelected(auth.user.id);
    else if(auth?.user.user_type!=='tailor'&&selected===null&&rows.length)setSelected(rows[0].id);
  },[auth?.user.id,auth?.user.user_type,selected,rows]);
  const selectedTailor=rows.find(x=>x.id===selected);
  const selectedWorks=(works.data||[]).filter(w=>w.tailor_user_id===selected);
  const monthly=useQuery({queryKey:['tailor-monthly',selected],queryFn:()=>adminApi.monthly(selected!),enabled:!!selected});
  const targetRemaining=target?Math.max(target.quantity-target.delivered_good,0):0;
  const linkedTarget=!!target?.production_order_id;
  const reportTotal=linkedTarget?report.delivered_good:report.delivered_good+report.returned_for_fix+report.damaged;
  const reportValid=reportTotal>0&&report.delivered_good<=targetRemaining;

  const invalidate=async()=>Promise.all([
    client.invalidateQueries({queryKey:['tailor-works']}),
    client.invalidateQueries({queryKey:['tailor-stats']}),
    client.invalidateQueries({queryKey:['tailor-monthly']}),
  ]);
  const create=useMutation({mutationFn:()=>adminApi.createWork({...work,due_at:work.due_at||null}),onSuccess:async()=>{await invalidate();toast.success('کار مستقل برای خیاط ثبت شد');setWork(emptyWork);setModal(null)},onError:e=>toast.error('ثبت کار ناموفق بود',e instanceof Error?e.message:undefined)});
  const rep=useMutation({mutationFn:()=>{if(!target)throw new Error('کار انتخاب نشده است');if(!reportValid)throw new Error(`جمع تحویل باید بین ۱ تا ${numberFa(targetRemaining)} باشد`);return adminApi.reportWork(target.id,report)},onSuccess:async()=>{await invalidate();toast.success('تحویل ثبت شد');setModal(null)},onError:e=>toast.error('ثبت تحویل ناموفق بود',e instanceof Error?e.message:undefined)});
  const upd=useMutation({mutationFn:()=>adminApi.updateWork(target!.id,{...edit,due_at:edit.due_at||null}),onSuccess:async()=>{await invalidate();toast.success('کار ویرایش شد');setModal(null)},onError:e=>toast.error('ویرایش ناموفق بود',e instanceof Error?e.message:undefined)});
  const remove=useMutation({mutationFn:(id:number)=>adminApi.deleteWork(id),onSuccess:async()=>{await invalidate();toast.success('کار اشتباهی حذف شد')},onError:e=>toast.error('حذف کار ناموفق بود',e instanceof Error?e.message:undefined)});

  const productName=(id:number|null)=>products.data?.find(p=>p.id===id)?.name||(id?`محصول #${id}`:'بدون محصول');
  const startManualEdit=(x:TailorWork)=>{setTarget(x);setEdit({tailor_user_id:x.tailor_user_id,product_id:x.product_id,quantity:x.quantity,due_at:x.due_at||'',status:x.status,notes:x.notes||''});setModal('edit')};

  return <div className="space-y-6">
    <PageHeader title="داشبورد خیاط‌ها" description="دستور تولیدی که خیاط دارد خودکار اینجا تبدیل به کار می‌شود؛ کار مستقل فقط برای کارهای خارج از دستور تولید است." action={manage?<Button onClick={()=>{setWork(emptyWork);setModal('work')}}><ClipboardList className="h-4 w-4"/>کار مستقل</Button>:undefined}/>
    <Card className="border-sky-100 bg-sky-50/60 p-4 text-sm leading-7 text-sky-950">برای کارهای تولیدی دوباره از این صفحه «تخصیص کار» نسازید. خیاط را در <b>دستور تولید</b> انتخاب کنید؛ شماره دستور، محصول، تعداد و موعد خودکار در کار خیاط همگام می‌شود.</Card>

    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">{rows.map(x=><button type="button" key={x.id} onClick={()=>setSelected(x.id)} className={`rounded-2xl border bg-white p-5 text-right shadow-sm transition hover:-translate-y-0.5 hover:shadow-md ${selected===x.id?'border-sky-300 ring-2 ring-sky-100':'border-slate-200'}`}><div className="flex items-center justify-between"><div><p className="font-black">{x.full_name}</p><p className="text-xs text-slate-500">{x.phone||'بدون تلفن'}</p></div><Scissors className="h-5 w-5 text-sky-600"/></div><div className="mt-5 grid grid-cols-2 gap-3 text-xs"><K label="کار در دست" v={x.stats?.open_work||0}/><K label="سالم" v={x.stats?.delivered_good||0}/><K label="برگشتی" v={x.stats?.returned_for_fix||0}/><K label="خرابی %" v={x.stats?.defect_rate||0}/></div>{(x.stats?.overdue_work||0)>0&&<p className="mt-3 flex items-center gap-1 text-xs font-bold text-rose-600"><AlertTriangle className="h-3.5 w-3.5"/>{numberFa(x.stats?.overdue_work||0)} واحد عقب‌افتاده</p>}</button>)}</div>

    {selectedTailor&&<Card><CardHeader title={`کارهای ${selectedTailor.full_name}`} description="کارهای متصل به تولید از خود دستور تولید مدیریت می‌شوند تا دو منبع داده جدا ایجاد نشود."/><div className="overflow-x-auto"><table className="w-full min-w-[1100px] text-sm"><thead className="bg-slate-50"><tr><th className="p-3 text-right">کار</th><th>منبع</th><th className="text-right">محصول</th><th>تعداد</th><th>تحویل سالم</th><th>باقی‌مانده</th><th>موعد</th><th>وضعیت</th><th>عملیات</th></tr></thead><tbody>{selectedWorks.map(x=>{const remaining=Math.max(x.quantity-x.delivered_good,0);const linked=!!x.production_order_id;return <tr key={x.id} className="border-t"><td className="p-3 font-bold" dir="ltr">{x.work_no}</td><td className="text-center">{linked?<Badge tone="blue"><Factory className="ml-1 inline h-3 w-3"/>دستور تولید</Badge>:<Badge tone="slate">مستقل</Badge>}</td><td className="p-3">{productName(x.product_id)}</td><td className="text-center">{numberFa(x.quantity)}</td><td className="text-center">{numberFa(x.delivered_good)}</td><td className="text-center font-black">{numberFa(remaining)}</td><td className="text-center">{dateFa(x.due_at)}</td><td className="text-center"><Badge tone={x.status==='completed'?'green':x.status==='cancelled'?'red':'amber'}>{x.status==='completed'?'تکمیل':x.status==='cancelled'?'لغو':'باز'}</Badge></td><td className="p-2"><div className="flex flex-wrap justify-center gap-1">{manage&&!linked&&<Button size="sm" variant="secondary" onClick={()=>startManualEdit(x)}><Pencil className="h-3.5 w-3.5"/>ویرایش</Button>}{manage&&!linked&&<Button size="sm" variant="ghost" onClick={()=>confirm('اگر این کار سابقه تحویل نداشته باشد حذف می‌شود. ادامه؟')&&remove.mutate(x.id)}><Trash2 className="h-3.5 w-3.5 text-rose-600"/></Button>}{linked&&manage&&<span className="rounded-lg bg-slate-50 px-2 py-1 text-[11px] text-slate-500">ویرایش از تولید</span>}{canReport&&x.status==='open'&&remaining>0&&<Button size="sm" onClick={()=>{setTarget(x);setReport({delivered_good:0,returned_for_fix:0,damaged:0,notes:''});setModal('report')}}>ثبت تحویل</Button>}</div></td></tr>})}</tbody></table></div></Card>}

    {selected&&<Card className="p-5"><h2 className="font-black">آمار ماه‌به‌ماه {selectedTailor?.full_name}</h2><div className="mt-4 overflow-x-auto"><table className="w-full text-sm"><thead><tr><th className="p-2 text-right">ماه</th><th>سالم</th><th>برگشتی</th><th>خراب</th><th>نرخ ایراد</th></tr></thead><tbody>{monthly.data?.map(m=><tr key={m.month} className="border-t text-center"><td className="p-2 text-right">{dateFa(`${m.month}-01`)}</td><td>{numberFa(m.delivered_good)}</td><td>{numberFa(m.returned_for_fix)}</td><td>{numberFa(m.damaged)}</td><td>{numberFa(m.defect_rate)}%</td></tr>)}</tbody></table></div></Card>}

    <Modal open={modal==='work'} onClose={()=>setModal(null)} title="کار مستقل خیاط" description="فقط برای کاری که دستور تولید ندارد؛ دستورهای تولید به‌صورت خودکار وارد داشبورد خیاط می‌شوند."><form onSubmit={(e:FormEvent)=>{e.preventDefault();create.mutate()}} className="space-y-4"><Field label="خیاط" required><Select required value={work.tailor_user_id||''} onChange={e=>setWork({...work,tailor_user_id:Number(e.target.value)})}><option value="">انتخاب خیاط</option>{tailors.data?.map(x=><option value={x.id} key={x.id}>{x.full_name}{x.phone?` · ${x.phone}`:''}</option>)}</Select></Field><Field label="محصول"><Select value={work.product_id??''} onChange={e=>setWork({...work,product_id:e.target.value?Number(e.target.value):null})}><option value="">بدون محصول مشخص</option>{products.data?.map(x=><option value={x.id} key={x.id}>{x.name}{x.sku?` · ${x.sku}`:''}</option>)}</Select></Field><Field label="تعداد"><Input type="number" min={1} value={work.quantity} onChange={e=>setWork({...work,quantity:Number(e.target.value)})}/></Field><Field label="موعد"><Input type="date" value={work.due_at} onChange={e=>setWork({...work,due_at:e.target.value})}/></Field><Field label="یادداشت"><Textarea value={work.notes} onChange={e=>setWork({...work,notes:e.target.value})}/></Field><Button className="w-full" loading={create.isPending}>ثبت کار مستقل</Button></form></Modal>

    <Modal open={modal==='report'} onClose={()=>setModal(null)} title="گزارش تحویل" description={target?`از ${numberFa(targetRemaining)} واحد باقی‌مانده این کار تحویل ثبت می‌شود.`:undefined}><form onSubmit={(e:FormEvent)=>{e.preventDefault();rep.mutate()}} className="space-y-4"><div className={`rounded-xl p-3 text-sm ${reportTotal>targetRemaining?'bg-rose-50 text-rose-700':'bg-sky-50 text-sky-800'}`}>باقی‌مانده کار: <b>{numberFa(targetRemaining)}</b> · جمع این تحویل: <b>{numberFa(reportTotal)}</b>{reportTotal>targetRemaining?' · جمع واردشده بیشتر از باقیمانده است.':''}</div><div className={`grid gap-3 ${linkedTarget?'sm:grid-cols-1':'sm:grid-cols-3'}`}><Field label="تحویل سالم"><Input type="number" min={0} max={targetRemaining} value={report.delivered_good} onChange={e=>setReport({...report,delivered_good:Math.max(0,Number(e.target.value)||0)})}/></Field>{!linkedTarget&&<><Field label="برگشتی"><Input type="number" min={0} value={report.returned_for_fix} onChange={e=>setReport({...report,returned_for_fix:Math.max(0,Number(e.target.value)||0)})}/></Field><Field label="خراب"><Input type="number" min={0} value={report.damaged} onChange={e=>setReport({...report,damaged:Math.max(0,Number(e.target.value)||0)})}/></Field></>}</div>{linkedTarget&&<p className="rounded-xl bg-amber-50 p-3 text-xs leading-6 text-amber-800">برای دستور تولید فقط تحویل سالم را ثبت کن؛ برگشتی و ضایعات با نتیجه QC خودکار در آمار خیاط ثبت می‌شوند و کار برای اصلاح/جایگزینی دوباره باز می‌شود.</p>}<Field label="یادداشت"><Textarea value={report.notes} onChange={e=>setReport({...report,notes:e.target.value})}/></Field><Button className="w-full" loading={rep.isPending} disabled={!reportValid}>ثبت گزارش</Button></form></Modal>

    <Modal open={modal==='edit'} onClose={()=>setModal(null)} title="ویرایش کار مستقل">{target&&<form onSubmit={(e:FormEvent)=>{e.preventDefault();upd.mutate()}} className="space-y-4"><Field label="خیاط"><Select value={edit.tailor_user_id||''} onChange={e=>setEdit({...edit,tailor_user_id:Number(e.target.value)})}>{tailors.data?.map(x=><option value={x.id} key={x.id}>{x.full_name}</option>)}</Select></Field><Field label="محصول"><Select value={edit.product_id??''} onChange={e=>setEdit({...edit,product_id:e.target.value?Number(e.target.value):null})}><option value="">بدون محصول</option>{products.data?.map(x=><option value={x.id} key={x.id}>{x.name}</option>)}</Select></Field><Field label="تعداد"><Input type="number" min={Math.max(target.delivered_good,1)} value={edit.quantity} onChange={e=>setEdit({...edit,quantity:Number(e.target.value)})}/></Field><Field label="موعد"><Input type="date" value={edit.due_at} onChange={e=>setEdit({...edit,due_at:e.target.value})}/></Field><Field label="وضعیت"><Select value={edit.status} onChange={e=>setEdit({...edit,status:e.target.value})}><option value="open">باز</option><option value="completed">تکمیل</option><option value="cancelled">لغوشده</option></Select></Field><Field label="یادداشت"><Textarea value={edit.notes} onChange={e=>setEdit({...edit,notes:e.target.value})}/></Field><Button className="w-full" loading={upd.isPending}>ذخیره</Button></form>}</Modal>
  </div>;
}

function K({label,v}:{label:string;v:number}){return <div className="rounded-xl bg-slate-50 p-2"><p className="text-slate-500">{label}</p><p className="mt-1 text-lg font-black">{numberFa(v)}</p></div>}
