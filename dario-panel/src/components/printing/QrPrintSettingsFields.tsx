import {Field,Input,Select,Switch} from '../ui/Field';
import type {QrPrintSettings} from '../../lib/qrPrint';

export function QrPrintSettingsFields({value,onChange,group=false}:{value:QrPrintSettings;onChange:(next:QrPrintSettings)=>void;group?:boolean}){
  const set=<K extends keyof QrPrintSettings>(key:K,next:QrPrintSettings[K])=>onChange({...value,[key]:next});
  return <div className="space-y-4 rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
    <div><p className="text-sm font-black text-slate-900">تنظیمات چاپ</p><p className="mt-1 text-xs leading-5 text-slate-500">ابعاد بر حسب میلی‌متر است و برای چاپگر لیبل یا برگه معمولی قابل تنظیم می‌ماند.</p></div>
    <div className="grid gap-3 sm:grid-cols-3">
      <Field label="عرض لیبل"><Input type="number" min={20} max={120} step="0.5" value={value.label_width_mm} onChange={e=>set('label_width_mm',Number(e.target.value))}/></Field>
      <Field label="ارتفاع لیبل"><Input type="number" min={20} max={150} step="0.5" value={value.label_height_mm} onChange={e=>set('label_height_mm',Number(e.target.value))}/></Field>
      <Field label="اندازه QR"><Input type="number" min={12} max={100} step="0.5" value={value.qr_size_mm} onChange={e=>set('qr_size_mm',Number(e.target.value))}/></Field>
    </div>
    {group&&<>
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label="تعداد در هر ردیف"><Input type="number" min={1} max={10} value={value.columns} onChange={e=>set('columns',Math.max(1,Number(e.target.value)||1))}/></Field>
        <Field label="فاصله افقی"><Input type="number" min={0} max={30} step="0.5" value={value.gap_x_mm} onChange={e=>set('gap_x_mm',Number(e.target.value))}/></Field>
        <Field label="فاصله عمودی"><Input type="number" min={0} max={30} step="0.5" value={value.gap_y_mm} onChange={e=>set('gap_y_mm',Number(e.target.value))}/></Field>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="کاغذ"><Select value={value.page_size} onChange={e=>set('page_size',e.target.value as 'A4'|'A5')}><option value="A4">A4</option><option value="A5">A5</option></Select></Field>
        <Field label="حاشیه صفحه"><Input type="number" min={0} max={30} step="0.5" value={value.margin_mm} onChange={e=>set('margin_mm',Number(e.target.value))}/></Field>
      </div>
      <Switch checked={value.landscape} onChange={v=>set('landscape',v)} label="چاپ صفحه به‌صورت افقی"/>
    </>}
    <div className="flex flex-wrap gap-x-6 gap-y-2"><Switch checked={value.show_title} onChange={v=>set('show_title',v)} label="نمایش عنوان"/><Switch checked={value.show_serial} onChange={v=>set('show_serial',v)} label="نمایش سریال"/></div>
  </div>;
}
