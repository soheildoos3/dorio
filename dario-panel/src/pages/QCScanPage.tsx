import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CheckCircle2, LockKeyhole, XCircle } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { useParams } from 'react-router-dom';
import { qualityApi, type QCPayload } from '../api/quality';
import type { DefectSeverity, QCRecordResult } from '../api/types';
import { useAuth } from '../auth/AuthProvider';
import { useToast } from '../components/feedback/ToastProvider';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Field, Input, Select, Textarea } from '../components/ui/Field';
import { Card, PageHeader } from '../components/ui/Page';
import { ErrorState, LoadingState } from '../components/ui/States';
import { labels } from '../lib/labels';

export function QCScanPage() {
  const { serial = '' } = useParams();
  const { can } = useAuth();
  const manage = can('quality.manage');
  const toast = useToast();
  const client = useQueryClient();
  const item = useQuery({ queryKey: ['quality', 'scan', serial], queryFn: () => qualityApi.scanItem(serial), enabled: !!serial });
  const [result, setResult] = useState<QCRecordResult>('passed');
  const [defect, setDefect] = useState('');
  const [severity, setSeverity] = useState<DefectSeverity | null>(null);
  const [failureAction, setFailureAction] = useState<'rework' | 'scrap'>('rework');
  const [wasteClass, setWasteClass] = useState<'normal' | 'abnormal'>('normal');
  const [notes, setNotes] = useState('');
  const [files, setFiles] = useState<File[]>([]);

  const mutation = useMutation({
    mutationFn: async () => {
      if (!manage) throw new Error('برای ثبت کنترل کیفیت دسترسی quality.manage لازم است.');
      if (!item.data) throw new Error('واحد کالا پیدا نشد');
      const photos = result === 'failed' && files.length
        ? await Promise.all(files.map(async (file) => (await qualityApi.uploadPhoto(item.data!.id, file)).url))
        : null;
      const payload: QCPayload = {
        item_id: item.data.id,
        result,
        defect_type: result === 'failed' ? (defect || null) : null,
        defect_severity: result === 'failed' ? severity : null,
        failure_action: result === 'failed' ? failureAction : null,
        waste_class: result === 'failed' && failureAction === 'scrap' ? wasteClass : null,
        notes: notes || null,
        photos,
      };
      return qualityApi.recordQC(payload);
    },
    onSuccess: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: ['quality'] }),
        client.invalidateQueries({ queryKey: ['inventory'] }),
        client.invalidateQueries({ queryKey: ['quality', 'scan', serial] }),
      ]);
      toast.success('کنترل کیفیت ثبت شد');
    },
    onError: (error) => toast.error('ثبت QC ناموفق', error instanceof Error ? error.message : ''),
  });

  if (item.isLoading) return <LoadingState />;
  if (item.isError || !item.data) return <ErrorState error={item.error} />;
  const current = item.data;

  return <div className="space-y-6">
    <PageHeader title="اسکن کنترل کیفیت" description="شناسه این واحد مستقیماً از QR خوانده شده است. اطلاعات کالا برای همه کاربران دارای quality.view قابل مشاهده است؛ ثبت نتیجه فقط برای quality.manage فعال می‌شود." />
    <Card className="p-5"><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-xs text-slate-500">شماره واحد</p><p className="mt-1 font-black" dir="ltr">{current.warranty_serial || current.serial_number}</p></div><div className="flex gap-2"><Badge tone={current.qc_status === 'passed' ? 'green' : current.qc_status === 'failed' ? 'red' : 'amber'}>{labels.qcStatus[current.qc_status]}</Badge><Badge tone={current.status === 'in_stock' ? 'green' : 'slate'}>{labels.itemStatus[current.status]}</Badge></div></div></Card>

    {!manage ? <Card className="p-5"><div className="flex items-start gap-3 rounded-2xl bg-slate-50 p-4"><span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-white text-slate-600 shadow-sm"><LockKeyhole className="h-5 w-5" /></span><div><p className="font-black text-slate-900">حالت فقط مشاهده</p><p className="mt-1 text-sm leading-7 text-slate-500">نقش شما اجازه مشاهده نتیجه QC را دارد، اما ثبت یا تغییر نتیجه نیازمند دسترسی <span dir="ltr" className="font-mono text-xs">quality.manage</span> است.</p></div></div></Card> :
      <Card className="p-5"><form onSubmit={(event: FormEvent) => { event.preventDefault(); mutation.mutate(); }} className="space-y-4">
        <Field label="نتیجه کنترل"><Select value={result} onChange={(event) => setResult(event.target.value as QCRecordResult)}><option value="passed">تأیید QC</option><option value="failed">رد QC</option></Select></Field>
        {result === 'failed' && <div className="grid gap-4 sm:grid-cols-2">
          <Field label="نوع عیب"><Input value={defect} onChange={(event) => setDefect(event.target.value)} /></Field>
          <Field label="شدت"><Select value={severity || ''} onChange={(event) => setSeverity((event.target.value || null) as DefectSeverity | null)}><option value="">انتخاب</option><option value="minor">جزئی</option><option value="major">مهم</option><option value="critical">بحرانی</option></Select></Field>
          <Field label="تعیین تکلیف"><Select value={failureAction} onChange={(event) => setFailureAction(event.target.value as 'rework' | 'scrap')}><option value="rework">قابل اصلاح / دوباره‌کاری</option><option value="scrap">ضایعات / غیرقابل اصلاح</option></Select></Field>
          {failureAction === 'scrap' && <Field label="نوع ضایعات"><Select value={wasteClass} onChange={(event) => setWasteClass(event.target.value as 'normal' | 'abnormal')}><option value="normal">عادی؛ جذب محصول سالم</option><option value="abnormal">غیرعادی؛ هزینه دوره</option></Select></Field>}
          <Field label="عکس عیب"><Input type="file" multiple accept="image/jpeg,image/png,image/webp" onChange={(event) => setFiles(Array.from(event.target.files || []))} /></Field>
        </div>}
        <Field label="توضیحات"><Textarea value={notes} onChange={(event) => setNotes(event.target.value)} /></Field>
        <Button className="w-full" loading={mutation.isPending}>{result === 'passed' ? <CheckCircle2 className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}{result === 'passed' ? 'تأیید کنترل کیفیت' : 'ثبت رد کنترل کیفیت'}</Button>
      </form></Card>}
  </div>;
}
