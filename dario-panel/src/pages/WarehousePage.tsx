import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { MapPin, Pencil, Plus, Trash2, Warehouse as WarehouseIcon } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { warehouseApi, type LocationPayload, type WarehousePayload } from '../api/warehouse';
import type { Location, LocationType, Warehouse } from '../api/types';
import { useUsers } from '../hooks/useReferenceData';
import { useToast } from '../components/feedback/ToastProvider';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Field, Input, Select, Switch, Textarea } from '../components/ui/Field';
import { Modal } from '../components/ui/Modal';
import { Card, CardHeader, PageHeader } from '../components/ui/Page';
import { EmptyState, ErrorState, LoadingState } from '../components/ui/States';
import { labels } from '../lib/labels';
import { nullableNumber, numberFa } from '../lib/format';
import { useAuth } from '../auth/AuthProvider';

const warehouseEmpty: WarehousePayload = { code: '', name: '', address: '', manager_id: null, phone: '', is_active: true };
const locationEmpty: LocationPayload = { warehouse_id: 0, parent_id: null, type: 'bin', code: '', name: '', is_pickable: true, is_receivable: true, max_items: null, max_weight_kg: null, sort_order: 0, is_active: true };

export function WarehousePage() {
  const { can } = useAuth();
  const manage = can('warehouse.manage');
  const canUsers = can('users.view');
  const toast = useToast();
  const client = useQueryClient();
  const users = useUsers(canUsers);
  const warehouses = useQuery({ queryKey: ['warehouses'], queryFn: warehouseApi.list });
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const selected = warehouses.data?.find((w) => w.id === selectedId) || warehouses.data?.[0] || null;
  const locations = useQuery({ queryKey: ['warehouses', selected?.id, 'locations'], queryFn: () => warehouseApi.locations(selected!.id), enabled: !!selected });
  const [warehouseModal, setWarehouseModal] = useState(false);
  const [locationModal, setLocationModal] = useState(false);
  const [editingWarehouse, setEditingWarehouse] = useState<Warehouse | null>(null);
  const [editingLocation, setEditingLocation] = useState<Location | null>(null);
  const [warehouseForm, setWarehouseForm] = useState<WarehousePayload>(warehouseEmpty);
  const [locationForm, setLocationForm] = useState<LocationPayload>(locationEmpty);

  const saveWarehouse = useMutation({
    mutationFn: () => editingWarehouse ? warehouseApi.update(editingWarehouse.id, warehouseForm) : warehouseApi.create(warehouseForm),
    onSuccess: async (row) => { await client.invalidateQueries({ queryKey: ['warehouses'] }); setSelectedId(row.id); toast.success('انبار ذخیره شد'); closeWarehouse(); },
    onError: (e) => toast.error('ذخیره انبار ناموفق بود', e instanceof Error ? e.message : undefined),
  });
  const deleteLocation = useMutation({
    mutationFn: (id:number) => warehouseApi.deleteLocation(id),
    onSuccess: async () => { await client.invalidateQueries({ queryKey: ['warehouses', selected?.id, 'locations'] }); await client.invalidateQueries({ queryKey: ['warehouses', 'all-locations'] }); toast.success('مکان بدون سابقه حذف شد'); },
    onError: (e) => toast.error('حذف مکان انجام نشد', e instanceof Error ? e.message : undefined),
  });
  const deleteWarehouse = useMutation({
    mutationFn: (id:number) => warehouseApi.delete(id),
    onSuccess: async () => { setSelectedId(null); await client.invalidateQueries({ queryKey: ['warehouses'] }); toast.success('انبار خالی حذف شد'); },
    onError: (e) => toast.error('حذف انبار انجام نشد', e instanceof Error ? e.message : undefined),
  });
  const saveLocation = useMutation({
    mutationFn: () => {
      if (!editingLocation) return warehouseApi.createLocation(locationForm);
      const { warehouse_id: _warehouseId, ...payload } = locationForm;
      return warehouseApi.updateLocation(editingLocation.id, payload);
    },
    onSuccess: async () => { await client.invalidateQueries({ queryKey: ['warehouses', selected?.id, 'locations'] }); await client.invalidateQueries({ queryKey: ['warehouses', 'all-locations'] }); toast.success('مکان ذخیره شد'); closeLocation(); },
    onError: (e) => toast.error('ذخیره مکان ناموفق بود', e instanceof Error ? e.message : undefined),
  });

  function closeWarehouse() { setWarehouseModal(false); setEditingWarehouse(null); setWarehouseForm(warehouseEmpty); }
  function closeLocation() { setLocationModal(false); setEditingLocation(null); setLocationForm(locationEmpty); }
  function editWarehouse(row: Warehouse) { setEditingWarehouse(row); setWarehouseForm({ code: row.code, name: row.name, address: row.address || '', manager_id: row.manager_id, phone: row.phone || '', is_active: row.is_active }); setWarehouseModal(true); }
  function createLocation() { if (!selected) return; setLocationForm({ ...locationEmpty, warehouse_id: selected.id }); setLocationModal(true); }
  function editLocation(row: Location) { setEditingLocation(row); setLocationForm({ warehouse_id: row.warehouse_id, parent_id: row.parent_id, type: row.type, code: row.code, name: row.name || '', is_pickable: row.is_pickable, is_receivable: row.is_receivable, max_items: row.max_items, max_weight_kg: row.max_weight_kg === null ? null : Number(row.max_weight_kg), sort_order: row.sort_order, is_active: row.is_active }); setLocationModal(true); }

  return (
    <div className="space-y-6">
      <PageHeader title="انبار و مکان‌ها" description="مدیریت انبار، ساختار درختی zone/aisle/rack/shelf/bin و ظرفیت‌های هر مکان." action={manage?<Button onClick={() => setWarehouseModal(true)}><Plus className="h-4 w-4" />انبار جدید</Button>:undefined} />
      {warehouses.isLoading ? <LoadingState /> : warehouses.isError ? <ErrorState error={warehouses.error} /> : (
        <div className="grid gap-6 xl:grid-cols-[360px_1fr]">
          <Card className="h-fit">
            <CardHeader title="انبارها" description="برای مشاهده مکان‌ها یک انبار را انتخاب کنید." />
            <div className="space-y-2 p-3">
              {warehouses.data?.map((row) => (
                <button key={row.id} type="button" onClick={() => setSelectedId(row.id)} className={`w-full rounded-2xl border p-4 text-right transition ${selected?.id === row.id ? 'border-sky-300 bg-sky-50' : 'border-transparent bg-slate-50 hover:border-slate-200'}`}>
                  <div className="flex items-start justify-between"><div className="flex items-center gap-3"><span className="grid h-9 w-9 place-items-center rounded-xl bg-white text-slate-600 shadow-sm"><WarehouseIcon className="h-4 w-4" /></span><div><p className="font-black text-slate-900">{row.name}</p><p className="text-xs text-slate-500">{row.code}</p></div></div><Badge tone={row.is_active ? 'green' : 'slate'}>{row.is_active ? 'فعال' : 'غیرفعال'}</Badge></div>
                  <div className="mt-3 flex items-center justify-between text-xs text-slate-500"><span>{row.phone || 'بدون تلفن'}</span>{manage&&<span className="flex gap-1"><button type="button" className="rounded-lg p-1.5 hover:bg-white" onClick={(e) => { e.stopPropagation(); editWarehouse(row); }} title="ویرایش"><Pencil className="h-3.5 w-3.5" /></button><button type="button" className="rounded-lg p-1.5 hover:bg-rose-50 hover:text-rose-600" onClick={(e) => { e.stopPropagation(); if(window.confirm(`انبار «${row.name}» حذف شود؟ فقط انبار کاملاً خالی و بدون سابقه قابل حذف است.`)) deleteWarehouse.mutate(row.id); }} title="حذف امن"><Trash2 className="h-3.5 w-3.5" /></button></span>}</div>
                </button>
              ))}
              {warehouses.data?.length === 0 && <EmptyState title="انبار ثبت نشده" />}
            </div>
          </Card>

          <Card>
            <CardHeader title={selected ? `مکان‌های ${selected.name}` : 'مکان‌ها'} description={selected ? `${selected.code} · ${selected.address || 'بدون آدرس'}` : 'ابتدا یک انبار ایجاد کنید.'} action={selected&&manage ? <Button onClick={createLocation}><Plus className="h-4 w-4" />مکان جدید</Button> : undefined} />
            {!selected ? <div className="p-5"><EmptyState /></div> : locations.isLoading ? <LoadingState /> : locations.isError ? <ErrorState error={locations.error} /> : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[900px] text-sm"><thead className="bg-slate-50 text-xs text-slate-500"><tr><th className="px-5 py-3 text-right">مکان</th><th className="px-5 py-3 text-right">نوع</th><th className="px-5 py-3 text-right">مسیر</th><th className="px-5 py-3 text-right">ظرفیت</th><th className="px-5 py-3 text-right">قابلیت</th><th className="px-5 py-3 text-left">ویرایش</th></tr></thead>
                  <tbody className="divide-y divide-slate-100">{locations.data?.map((row) => <tr key={row.id} className="hover:bg-slate-50/60"><td className="px-5 py-4"><div className="flex items-center gap-2"><MapPin className="h-4 w-4 text-slate-400"/><div><p className="font-bold">{row.name || row.code}</p><p className="text-xs text-slate-500">{row.code}</p></div></div></td><td className="px-5 py-4"><Badge tone="blue">{labels.locationType[row.type]}</Badge></td><td className="px-5 py-4 text-xs text-slate-500" dir="ltr"><span className="block text-right">{row.path}</span></td><td className="px-5 py-4 text-xs">{row.max_items !== null ? `${numberFa(row.max_items)} عدد` : '—'}<br/>{row.max_weight_kg !== null ? `${numberFa(row.max_weight_kg)} kg` : '—'}</td><td className="px-5 py-4 text-xs"><span className={row.is_pickable?'text-emerald-600':'text-slate-400'}>برداشت {row.is_pickable?'✓':'—'}</span><span className="mx-2 text-slate-300">|</span><span className={row.is_receivable?'text-sky-600':'text-slate-400'}>رسید {row.is_receivable?'✓':'—'}</span></td><td className="px-5 py-4 text-left">{manage?<div className="flex justify-end gap-1"><Button variant="ghost" className="px-2.5" onClick={() => editLocation(row)} title="ویرایش"><Pencil className="h-4 w-4"/></Button><Button variant="ghost" className="px-2.5 text-rose-600" onClick={()=>{if(window.confirm(`مکان «${row.name||row.code}» حذف شود؟ فقط مکان بدون موجودی و سابقه قابل حذف است.`))deleteLocation.mutate(row.id)}} title="حذف امن"><Trash2 className="h-4 w-4"/></Button></div>:<span className="text-xs text-slate-400">فقط مشاهده</span>}</td></tr>)}{locations.data?.length===0&&<tr><td colSpan={6} className="p-8 text-center text-slate-400">برای این انبار هنوز مکانی ثبت نشده.</td></tr>}</tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      )}

      <Modal open={manage&&warehouseModal} onClose={closeWarehouse} title={editingWarehouse ? 'ویرایش انبار' : 'انبار جدید'}>
        <form onSubmit={(e:FormEvent)=>{e.preventDefault();saveWarehouse.mutate();}} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2"><Field label="کد انبار" required><Input required maxLength={20} dir="ltr" value={warehouseForm.code} onChange={(e)=>setWarehouseForm({...warehouseForm,code:e.target.value})}/></Field><Field label="نام انبار" required><Input required maxLength={100} value={warehouseForm.name} onChange={(e)=>setWarehouseForm({...warehouseForm,name:e.target.value})}/></Field><Field label="مسئول انبار" hint={!canUsers?'برای انتخاب مسئول از فهرست کاربران، دسترسی مشاهده کاربران لازم است.':undefined}><Select value={warehouseForm.manager_id??''} onChange={(e)=>setWarehouseForm({...warehouseForm,manager_id:nullableNumber(e.target.value)})}><option value="">بدون مسئول</option>{!canUsers&&warehouseForm.manager_id&&<option value={warehouseForm.manager_id}>کاربر فعلی #{warehouseForm.manager_id}</option>}{users.data?.map(u=><option key={u.id} value={u.id}>{u.full_name}{u.username?` — @${u.username}`:u.phone?` — ${u.phone}`:''}</option>)}</Select></Field><Field label="تلفن"><Input dir="ltr" maxLength={20} value={warehouseForm.phone||''} onChange={(e)=>setWarehouseForm({...warehouseForm,phone:e.target.value||null})}/></Field></div>
          <Field label="آدرس"><Textarea value={warehouseForm.address||''} onChange={(e)=>setWarehouseForm({...warehouseForm,address:e.target.value||null})}/></Field><Switch checked={warehouseForm.is_active??true} onChange={(v)=>setWarehouseForm({...warehouseForm,is_active:v})} label="انبار فعال"/>
          <div className="flex justify-end gap-2"><Button type="button" variant="secondary" onClick={closeWarehouse}>انصراف</Button><Button type="submit" loading={saveWarehouse.isPending}>ذخیره</Button></div>
        </form>
      </Modal>

      <Modal open={manage&&locationModal} onClose={closeLocation} title={editingLocation ? 'ویرایش مکان' : 'مکان جدید'} size="lg">
        <form onSubmit={(e:FormEvent)=>{e.preventDefault();saveLocation.mutate();}} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2"><Field label="نوع" required><Select value={locationForm.type} onChange={(e)=>setLocationForm({...locationForm,type:e.target.value as LocationType})}>{Object.entries(labels.locationType).map(([v,l])=><option key={v} value={v}>{l}</option>)}</Select></Field><Field label="کد" required><Input required maxLength={50} dir="ltr" value={locationForm.code} onChange={(e)=>setLocationForm({...locationForm,code:e.target.value})}/></Field><Field label="نام توصیفی"><Input maxLength={100} value={locationForm.name||''} onChange={(e)=>setLocationForm({...locationForm,name:e.target.value||null})}/></Field><Field label="والد"><Select value={locationForm.parent_id??''} onChange={(e)=>setLocationForm({...locationForm,parent_id:nullableNumber(e.target.value)})}><option value="">بدون والد</option>{locations.data?.filter(l=>l.id!==editingLocation?.id).map(l=><option key={l.id} value={l.id}>{l.path}</option>)}</Select></Field><Field label="حداکثر تعداد"><Input type="number" min="0" value={locationForm.max_items??''} onChange={(e)=>setLocationForm({...locationForm,max_items:nullableNumber(e.target.value)})}/></Field><Field label="حداکثر وزن kg"><Input type="number" min="0" step="0.01" value={locationForm.max_weight_kg??''} onChange={(e)=>setLocationForm({...locationForm,max_weight_kg:e.target.value===''?null:Number(e.target.value)})}/></Field><Field label="ترتیب"><Input type="number" value={locationForm.sort_order??0} onChange={(e)=>setLocationForm({...locationForm,sort_order:Number(e.target.value)})}/></Field></div>
          <div className="flex flex-wrap gap-5"><Switch checked={locationForm.is_pickable??false} onChange={(v)=>setLocationForm({...locationForm,is_pickable:v})} label="قابل برداشت"/><Switch checked={locationForm.is_receivable??false} onChange={(v)=>setLocationForm({...locationForm,is_receivable:v})} label="قابل رسید"/><Switch checked={locationForm.is_active??true} onChange={(v)=>setLocationForm({...locationForm,is_active:v})} label="فعال"/></div>
          <div className="flex justify-end gap-2"><Button type="button" variant="secondary" onClick={closeLocation}>انصراف</Button><Button type="submit" loading={saveLocation.isPending}>ذخیره</Button></div>
        </form>
      </Modal>
    </div>
  );
}
