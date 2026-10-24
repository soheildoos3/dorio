import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {useMemo,useState,type FormEvent} from 'react';
import {DatabaseBackup,FileSpreadsheet,FileText,Plus,Pencil} from 'lucide-react';
import {adminApi} from '../api/admin';
import {usersApi} from '../api/users';
import type {EmployeeProfile,Role,SalesChannel} from '../api/types';
import {useAuth} from '../auth/AuthProvider';
import {useToast} from '../components/feedback/ToastProvider';
import {Button} from '../components/ui/Button';
import {Card,PageHeader} from '../components/ui/Page';
import {Field,Input,Select,Switch,Textarea} from '../components/ui/Field';
import {Modal} from '../components/ui/Modal';
import {Tabs} from '../components/ui/Tabs';

type Tab='roles'|'channels'|'hr'|'system';
export function ManagementPage(){
  const {can,auth}=useAuth();
  const isAdmin=!!auth&&(auth.user.is_superuser||auth.user.role?.code==='admin');
  const tabs=useMemo(()=>[
    ...(isAdmin?[{id:'roles' as Tab,label:'نقش‌ها و دسترسی'}]:[]),
    ...(can('channels.manage')?[{id:'channels' as Tab,label:'پلتفرم‌های فروش'}]:[]),
    ...(can('hr.manage')?[{id:'hr' as Tab,label:'منابع انسانی'}]:[]),
    ...(isAdmin?[{id:'system' as Tab,label:'گزارش و پشتیبان'}]:[]),
  ],[can,isAdmin]);
  const [tab,setTab]=useState<Tab>((tabs[0]?.id||'roles') as Tab);
  const current=tabs.some(x=>x.id===tab)?tab:(tabs[0]?.id||'roles');
  return <div className="space-y-6"><PageHeader title="تنظیمات سازمانی" description="Master data سازمان؛ این بخش‌ها قابل ویرایش‌اند و تاریخچه عملیاتی دست‌نخورده می‌ماند."/>{tabs.length>0&&<Tabs value={current} onChange={setTab} items={tabs}/>} {current==='roles'?<Roles/>:current==='channels'?<Channels/>:current==='hr'?<HR/>:current==='system'?<SystemTools/>:null}</div>
}

function Roles(){
  const q=useQuery({queryKey:['roles'],queryFn:adminApi.roles}); const perms=useQuery({queryKey:['permissions'],queryFn:adminApi.permissions}); const qc=useQueryClient(); const toast=useToast();
  const [editing,setEditing]=useState<Role|null>(null); const [open,setOpen]=useState(false); const [f,setF]=useState({code:'',name:'',permission_ids:[] as number[]});
  function start(r?:Role){setEditing(r||null);setF(r?{code:r.code,name:r.name,permission_ids:r.permissions.map(p=>p.id)}:{code:'',name:'',permission_ids:[]});setOpen(true)}
  const m=useMutation({mutationFn:()=>editing?adminApi.updateRole(editing.id,{name:f.name,permission_ids:f.permission_ids}):adminApi.createRole(f),onSuccess:async()=>{await qc.invalidateQueries({queryKey:['roles']});setOpen(false);toast.success('نقش ذخیره شد')},onError:e=>toast.error('ذخیره نقش ناموفق',e instanceof Error?e.message:'')});
  return <><Card><div className="flex items-center justify-between border-b p-5"><div><b>نقش‌ها</b><p className="text-xs text-slate-500">دسترسی منو و API از permission همین نقش محاسبه می‌شود.</p></div><Button onClick={()=>start()}><Plus className="h-4 w-4"/>نقش جدید</Button></div><div className="grid gap-3 p-5 md:grid-cols-2 xl:grid-cols-3">{q.data?.map(r=><div key={r.id} className="rounded-2xl border p-4"><div className="flex justify-between"><div><p className="font-black">{r.name}</p><p className="text-xs text-slate-500">{r.code}</p></div><Button variant="ghost" onClick={()=>start(r)}><Pencil className="h-4 w-4"/></Button></div><div className="mt-3 flex flex-wrap gap-1">{r.permissions.map(p=><span key={p.id} className="rounded-lg bg-slate-100 px-2 py-1 text-[11px]">{p.name}</span>)}</div></div>)}</div></Card><Modal open={open} onClose={()=>setOpen(false)} title={editing?'ویرایش نقش':'نقش جدید'}><form onSubmit={(e:FormEvent)=>{e.preventDefault();m.mutate()}} className="space-y-4"><Field label="کد نقش" hint="شناسه فنی ثابت؛ انگلیسی و بدون فاصله، مثل warehouse_manager. بعداً تغییرش ندهید."><Input disabled={!!editing} required dir="ltr" value={f.code} onChange={e=>setF({...f,code:e.target.value})}/></Field><Field label="نام نقش"><Input required value={f.name} onChange={e=>setF({...f,name:e.target.value})}/></Field><div className="grid max-h-80 gap-2 overflow-auto">{perms.data?.map(p=><label key={p.id} className="flex items-center gap-2 rounded-xl border p-2 text-sm"><input type="checkbox" checked={f.permission_ids.includes(p.id)} onChange={e=>setF({...f,permission_ids:e.target.checked?[...f.permission_ids,p.id]:f.permission_ids.filter(x=>x!==p.id)})}/>{p.name}</label>)}</div><Button className="w-full" loading={m.isPending}>ذخیره نقش</Button></form></Modal></>
}

function Channels(){
  const q=useQuery({queryKey:['channels'],queryFn:adminApi.channels}); const qc=useQueryClient(); const toast=useToast();
  const [editing,setEditing]=useState<SalesChannel|null>(null); const [open,setOpen]=useState(false); const [f,setF]=useState({code:'',name:'',is_active:true,notes:''});
  function start(c?:SalesChannel){setEditing(c||null);setF(c?{code:c.code,name:c.name,is_active:c.is_active,notes:c.notes||''}:{code:'',name:'',is_active:true,notes:''});setOpen(true)}
  const m=useMutation({mutationFn:()=>editing?adminApi.updateChannel(editing.id,{name:f.name,is_active:f.is_active,notes:f.notes||null}):adminApi.createChannel(f),onSuccess:async()=>{await qc.invalidateQueries({queryKey:['channels']});setOpen(false);toast.success('کانال ذخیره شد')}});
  return <><Card><div className="flex justify-between border-b p-5"><div><b>کانال‌های خروج و فروش</b><p className="text-xs text-slate-500">مثل فروش مستقیم، باسلام، دیجی‌کالا و هر کانال جدید.</p></div><Button onClick={()=>start()}><Plus className="h-4 w-4"/>کانال جدید</Button></div><div className="divide-y">{q.data?.map(c=><div className="flex items-center justify-between p-4" key={c.id}><div><b>{c.name}</b><p className="text-xs text-slate-500">{c.code} · {c.notes||'بدون توضیح'}</p></div><div className="flex items-center gap-2"><span className={c.is_active?'text-emerald-600':'text-slate-400'}>{c.is_active?'فعال':'غیرفعال'}</span><Button variant="ghost" onClick={()=>start(c)}><Pencil className="h-4 w-4"/></Button></div></div>)}</div></Card><Modal open={open} onClose={()=>setOpen(false)} title={editing?'ویرایش کانال':'کانال جدید'}><form onSubmit={(e:FormEvent)=>{e.preventDefault();m.mutate()}} className="space-y-4"><Field label="کد کانال" hint="شناسه فنی ثابت مثل digikala یا basalam؛ نام نمایشی می‌تواند فارسی باشد."><Input disabled={!!editing} required dir="ltr" value={f.code} onChange={e=>setF({...f,code:e.target.value})}/></Field><Field label="نام"><Input required value={f.name} onChange={e=>setF({...f,name:e.target.value})}/></Field><Field label="توضیح"><Textarea value={f.notes} onChange={e=>setF({...f,notes:e.target.value})}/></Field><Switch checked={f.is_active} onChange={v=>setF({...f,is_active:v})} label="فعال"/><Button className="w-full" loading={m.isPending}>ذخیره</Button></form></Modal></>
}


type ReportKind='inventory'|'items'|'movements'|'sales';
function SystemTools(){
  const toast=useToast();
  const [report,setReport]=useState<ReportKind>('inventory');
  const [busy,setBusy]=useState<string|null>(null);
  const reportLabels:Record<ReportKind,string>={inventory:'موجودی انبار',items:'واحدهای فیزیکی',movements:'کاردکس موجودی',sales:'فروش'};
  async function exportFile(format:'xlsx'|'pdf'){
    const key=`${report}-${format}`;setBusy(key);
    try{const name=await adminApi.exportReport(report,format);toast.success(`فایل ${name} آماده شد`)}
    catch(e){toast.error('خروجی گزارش ناموفق بود',e instanceof Error?e.message:'')}
    finally{setBusy(null)}
  }
  async function backup(){
    setBusy('backup');
    try{const name=await adminApi.backupDatabase();toast.success(`پشتیبان دیتابیس دانلود شد: ${name}`)}
    catch(e){toast.error('تهیه پشتیبان ناموفق بود',e instanceof Error?e.message:'')}
    finally{setBusy(null)}
  }
  return <div className="grid gap-5 xl:grid-cols-2">
    <Card className="p-5"><div className="mb-5"><b className="text-base">خروجی گزارش‌ها</b><p className="mt-1 text-xs leading-6 text-slate-500">گزارش انتخابی را با اطلاعات کامل محصول و تنوع به Excel یا PDF دریافت کنید.</p></div><div className="space-y-4"><Field label="نوع گزارش"><Select value={report} onChange={e=>setReport(e.target.value as ReportKind)}>{(Object.keys(reportLabels) as ReportKind[]).map(key=><option key={key} value={key}>{reportLabels[key]}</option>)}</Select></Field><div className="grid gap-3 sm:grid-cols-2"><Button variant="secondary" loading={busy===`${report}-xlsx`} disabled={!!busy&&busy!==`${report}-xlsx`} onClick={()=>void exportFile('xlsx')}><FileSpreadsheet className="h-4 w-4"/>خروجی Excel</Button><Button variant="secondary" loading={busy===`${report}-pdf`} disabled={!!busy&&busy!==`${report}-pdf`} onClick={()=>void exportFile('pdf')}><FileText className="h-4 w-4"/>خروجی PDF</Button></div></div></Card>
    <Card className="p-5"><div className="mb-5"><b className="text-base">پشتیبان دیتابیس</b><p className="mt-1 text-xs leading-6 text-slate-500">یک Snapshot منطقی فشرده از تمام جدول‌های دیتابیس تهیه می‌شود. فایل را خارج از سرور و در محل امن نگه دارید.</p></div><div className="rounded-2xl bg-amber-50 p-4 text-xs leading-6 text-amber-900">این بخش فقط برای مدیر کل فعال است. قبل از migration، تغییرات بزرگ یا پاک‌سازی داده‌ها یک نسخه پشتیبان جدید بگیرید.</div><Button className="mt-4 w-full" loading={busy==='backup'} disabled={!!busy&&busy!=='backup'} onClick={()=>void backup()}><DatabaseBackup className="h-4 w-4"/>دانلود بکاپ دیتابیس</Button></Card>
  </div>;
}

function HR(){
  const {can}=useAuth(); const canUsers=can('users.view');
  const employees=useQuery({queryKey:['hr'],queryFn:adminApi.employees}); const users=useQuery({queryKey:['users'],queryFn:()=>usersApi.list(),enabled:canUsers}); const qc=useQueryClient(); const toast=useToast();
  const [editing,setEditing]=useState<EmployeeProfile|null>(null); const [open,setOpen]=useState(false); const [f,setF]=useState({user_id:0,personnel_code:'',department:'',job_title:'',hire_date:'',national_id:'',address:'',emergency_phone:''});
  function start(e?:EmployeeProfile){setEditing(e||null);setF(e?{user_id:e.user_id,personnel_code:e.personnel_code,department:e.department||'',job_title:e.job_title||'',hire_date:e.hire_date||'',national_id:e.national_id||'',address:e.address||'',emergency_phone:e.emergency_phone||''}:{user_id:0,personnel_code:'',department:'',job_title:'',hire_date:'',national_id:'',address:'',emergency_phone:''});setOpen(true)}
  const m=useMutation({mutationFn:()=>editing?adminApi.updateEmployee(editing.id,{department:f.department||null,job_title:f.job_title||null,hire_date:f.hire_date||null,national_id:f.national_id||null,address:f.address||null,emergency_phone:f.emergency_phone||null}):adminApi.createEmployee({...f,hire_date:f.hire_date||null}),onSuccess:async()=>{await qc.invalidateQueries({queryKey:['hr']});setOpen(false);toast.success('پرونده پرسنلی ذخیره شد')}});
  return <>{!canUsers&&<div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">برای ساخت پرونده جدید، دسترسی مشاهده کاربران لازم است. پرونده‌های موجود همچنان قابل ویرایش‌اند.</div>}<Card><div className="flex justify-between border-b p-5"><div><b>پرونده منابع انسانی</b><p className="text-xs text-slate-500">حساب ورود فقط توسط مدیر ساخته می‌شود؛ HR پرونده پرسنلی را مدیریت می‌کند.</p></div>{canUsers?<Button onClick={()=>start()}><Plus className="h-4 w-4"/>پرونده جدید</Button>:undefined}</div><div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr><th className="p-3 text-right">کارمند</th><th>کد پرسنلی</th><th>واحد</th><th>سمت</th><th></th></tr></thead><tbody>{employees.data?.map(e=><tr key={e.id} className="border-t"><td className="p-3">{users.data?.find(u=>u.id===e.user_id)?.full_name||`کاربر #${e.user_id}`}</td><td className="text-center">{e.personnel_code}</td><td className="text-center">{e.department||'—'}</td><td className="text-center">{e.job_title||'—'}</td><td><Button variant="ghost" onClick={()=>start(e)}><Pencil className="h-4 w-4"/></Button></td></tr>)}</tbody></table></div></Card><Modal open={open} onClose={()=>setOpen(false)} title={editing?'ویرایش پرونده':'پرونده پرسنلی'}><form onSubmit={(e:FormEvent)=>{e.preventDefault();m.mutate()}} className="space-y-4"><Field label="کاربر"><Select disabled={!!editing} required value={f.user_id||''} onChange={e=>setF({...f,user_id:Number(e.target.value)})}><option value="">انتخاب کاربر</option>{users.data?.filter(u=>u.user_type==='employee').map(u=><option key={u.id} value={u.id}>{u.full_name}{u.username?` · @${u.username}`:u.phone?` · ${u.phone}`:''}</option>)}</Select></Field><Field label="کد پرسنلی"><Input disabled={!!editing} required value={f.personnel_code} onChange={e=>setF({...f,personnel_code:e.target.value})}/></Field><Field label="واحد"><Input value={f.department} onChange={e=>setF({...f,department:e.target.value})}/></Field><Field label="سمت"><Input value={f.job_title} onChange={e=>setF({...f,job_title:e.target.value})}/></Field><Field label="تاریخ استخدام"><Input type="date" value={f.hire_date} onChange={e=>setF({...f,hire_date:e.target.value})}/></Field><Field label="شماره تماس اضطراری"><Input value={f.emergency_phone} onChange={e=>setF({...f,emergency_phone:e.target.value})}/></Field><Field label="آدرس"><Textarea value={f.address} onChange={e=>setF({...f,address:e.target.value})}/></Field><Button className="w-full" loading={m.isPending}>ذخیره</Button></form></Modal></>
}
