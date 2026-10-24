import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react';
import { Link, Navigate, Route, Routes, useNavigate, useParams } from 'react-router-dom';

type Attr = { name: string; value: string };
type WarrantyData = {
  serial: string;
  status: string;
  product_name: string;
  product_description: string | null;
  product_sku: string | null;
  variant_sku: string | null;
  variant_attributes: Attr[];
  images: string[];
  warranty_months: number;
  outbound_at: string | null;
  auto_activate_at: string | null;
  activated_at: string | null;
  expires_at: string | null;
  activation_source: string | null;
  can_activate: boolean;
};
type AuthMe = { user: { id: number; full_name: string; panel_access: boolean; is_superuser: boolean; role?: { name: string } | null }; permissions: string[] };
type Item = { id: number; variant_id: number; serial_number: string | null; warranty_serial: string | null; qc_status: string; status: string; location_id: number | null; warehouse_id: number | null; qc_checked_at: string | null };
type Channel = { id: number; name: string; is_active: boolean };
type Reservation = { id: number; item_id: number | null; status: string };

type BusyAction = '' | 'activate' | 'staff-warranty' | 'qc' | 'outbound';

const apiOrigin = (import.meta.env.VITE_API_ORIGIN || '').trim().replace(/\/$/, '');
const statusText: Record<string, string> = {
  inactive: 'در انبار / غیرفعال',
  grace: 'آماده فعال‌سازی',
  active: 'گارانتی فعال',
  expired: 'گارانتی منقضی',
  returned: 'کالا مرجوع شده',
  void: 'گارانتی باطل',
};
const itemStatus: Record<string, string> = {
  pending_qc: 'در انتظار کنترل کیفیت',
  in_stock: 'موجود در انبار',
  reserved: 'رزرو شده',
  sold: 'فروخته شده',
  damaged: 'خراب / ضایعات',
  lost: 'مفقود',
  returned: 'مرجوعی',
};
const qcText: Record<string, string> = { pending: 'در انتظار QC', passed: 'تأیید QC', failed: 'رد QC' };

class RequestError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'RequestError';
    this.status = status;
  }
}

const faDate = (value: string | null) => value
  ? new Intl.DateTimeFormat('fa-IR-u-ca-persian', { year: 'numeric', month: 'long', day: 'numeric' }).format(new Date(value))
  : '—';
const faNumber = (value: number) => new Intl.NumberFormat('fa-IR').format(value);
const mediaUrl = (value: string) => /^https?:\/\//i.test(value) ? value : `${apiOrigin}${value.startsWith('/') ? '' : '/'}${value}`;

function csrf() {
  return document.cookie.split('; ').find((item) => item.startsWith('dario_csrf='))?.split('=')[1] || '';
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method || 'GET').toUpperCase();
  const headers = new Headers(init.headers);
  headers.set('Accept', 'application/json');
  if (init.body !== undefined && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    const token = csrf();
    if (token) headers.set('X-CSRF-Token', decodeURIComponent(token));
  }

  let response: Response;
  try {
    response = await fetch(`${apiOrigin}${path}`, { ...init, headers, credentials: 'include' });
  } catch {
    throw new RequestError('ارتباط با سامانه برقرار نشد. اتصال اینترنت را بررسی کنید و دوباره تلاش کنید.', 0);
  }

  const contentType = response.headers.get('content-type') || '';
  const body = contentType.includes('application/json')
    ? await response.json().catch(() => null)
    : await response.text().catch(() => '');
  if (!response.ok) {
    const detail = body && typeof body === 'object' && 'detail' in body ? (body as { detail?: unknown }).detail : body;
    const message = typeof detail === 'string' && detail.trim() ? detail : response.status === 404 ? 'اطلاعات این محصول پیدا نشد.' : 'درخواست توسط سامانه پذیرفته نشد.';
    throw new RequestError(message, response.status);
  }
  return body as T;
}

function WarrantyScreen() {
  const { serial = '' } = useParams();
  const [data, setData] = useState<WarrantyData | null>(null);
  const [auth, setAuth] = useState<AuthMe | null>(null);
  const [item, setItem] = useState<Item | null>(null);
  const [reservationId, setReservationId] = useState<number | null>(null);
  const [channels, setChannels] = useState<Channel[]>([]);
  const [loading, setLoading] = useState(true);
  const [fatalError, setFatalError] = useState('');
  const [actionError, setActionError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [busy, setBusy] = useState<BusyAction>('');
  const [slide, setSlide] = useState(0);
  const [qcResult, setQcResult] = useState<'passed' | 'failed'>('passed');
  const [qcNotes, setQcNotes] = useState('');
  const [defect, setDefect] = useState('');
  const [failureAction, setFailureAction] = useState<'rework' | 'scrap'>('rework');
  const [wasteClass, setWasteClass] = useState<'normal' | 'abnormal'>('normal');
  const [channelId, setChannelId] = useState(0);
  const [reference, setReference] = useState('');
  const [disposition, setDisposition] = useState<'sale' | 'damage' | 'loss' | 'return'>('sale');

  const can = (permission: string) => !!auth && (auth.user.is_superuser || auth.permissions.includes('*') || auth.permissions.includes(permission));
  const staff = !!auth && (auth.user.panel_access || auth.user.is_superuser);
  const canOutbound = can('inventory.view') && can('inventory.outbound');

  const load = async () => {
    setLoading(true);
    setFatalError('');
    setActionError('');
    setItem(null);
    setReservationId(null);
    setChannels([]);
    try {
      const publicData = await request<WarrantyData>(`/api/public/warranty/${encodeURIComponent(serial)}`);
      setData(publicData);
      setSlide(0);

      let me: AuthMe | null = null;
      try {
        me = await request<AuthMe>('/api/auth/me');
      } catch {
        // A QR is public; missing panel session is expected for customers.
      }
      setAuth(me);

      if (me && (me.user.panel_access || me.user.is_superuser)) {
        const permissions = new Set(me.permissions);
        const all = me.user.is_superuser || permissions.has('*');
        let foundItem: Item | null = null;
        if (all || permissions.has('inventory.view')) {
          try {
            foundItem = await request<Item>(`/api/inventory/scan/${encodeURIComponent(serial)}`);
            setItem(foundItem);
          } catch {
            // Warranty-only users can still use the warranty actions.
          }
        } else if (permissions.has('quality.view')) {
          try {
            foundItem = await request<Item>(`/api/quality/scan/${encodeURIComponent(serial)}`);
            setItem(foundItem);
          } catch {
            // Keep the page useful even when item details are unavailable.
          }
        }

        const inventoryOutbound = all || (permissions.has('inventory.view') && permissions.has('inventory.outbound'));
        if (inventoryOutbound) {
          try {
            setChannels((await request<Channel[]>('/api/channels')).filter((channel) => channel.is_active));
          } catch {
            // Non-sale dispositions do not require a channel.
          }
          if (foundItem?.status === 'reserved') {
            try {
              const reservations = await request<Reservation[]>('/api/inventory/reservations?offset=0&limit=500');
              setReservationId(reservations.find((reservation) => reservation.item_id === foundItem?.id && reservation.status === 'active')?.id ?? null);
            } catch {
              // Outbound remains blocked for reserved stock when reservation resolution failed.
            }
          }
        }
      }
    } catch (error) {
      setData(null);
      setFatalError(error instanceof Error ? error.message : 'خطا در دریافت اطلاعات محصول');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [serial]);

  const activateCustomer = async (event: FormEvent) => {
    event.preventDefault();
    setBusy('activate');
    setActionError('');
    setSuccessMessage('');
    try {
      const updated = await request<WarrantyData>(`/api/public/warranty/${encodeURIComponent(serial)}/activate`, {
        method: 'POST',
        body: JSON.stringify({ customer_name: name.trim() || null, customer_phone: phone.trim() || null }),
      });
      setData(updated);
      setSuccessMessage('گارانتی با موفقیت فعال شد.');
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'فعال‌سازی انجام نشد.');
    } finally {
      setBusy('');
    }
  };

  const staffActivate = async () => {
    setBusy('staff-warranty');
    setActionError('');
    setSuccessMessage('');
    try {
      await request(`/api/warranty/by-serial/${encodeURIComponent(serial)}/activate`, { method: 'POST' });
      setSuccessMessage('گارانتی توسط کاربر پنل فعال شد.');
      await load();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'فعال‌سازی انجام نشد.');
    } finally {
      setBusy('');
    }
  };

  const submitQC = async (event: FormEvent) => {
    event.preventDefault();
    if (!item) return;
    setBusy('qc');
    setActionError('');
    setSuccessMessage('');
    try {
      await request('/api/quality/qc-records', {
        method: 'POST',
        body: JSON.stringify({
          item_id: item.id,
          result: qcResult,
          defect_type: qcResult === 'failed' ? (defect.trim() || null) : null,
          defect_severity: qcResult === 'failed' ? 'major' : null,
          failure_action: qcResult === 'failed' ? failureAction : null,
          waste_class: qcResult === 'failed' && failureAction === 'scrap' ? wasteClass : null,
          notes: qcNotes.trim() || null,
          photos: null,
        }),
      });
      setSuccessMessage('نتیجه کنترل کیفیت ثبت شد.');
      await load();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'ثبت کنترل کیفیت انجام نشد.');
    } finally {
      setBusy('');
    }
  };

  const submitOutbound = async (event: FormEvent) => {
    event.preventDefault();
    if (!item || !item.location_id) return;
    setBusy('outbound');
    setActionError('');
    setSuccessMessage('');
    try {
      await request('/api/inventory/outbound', {
        method: 'POST',
        body: JSON.stringify({
          variant_id: item.variant_id,
          location_id: item.location_id,
          quantity: 1,
          item_id: item.id,
          reservation_id: reservationId,
          disposition,
          channel_id: disposition === 'sale' ? channelId : null,
          external_reference: reference.trim() || null,
          reason: null,
        }),
      });
      setSuccessMessage('خروج این واحد با موفقیت ثبت شد.');
      await load();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'خروج انبار انجام نشد.');
    } finally {
      setBusy('');
    }
  };

  const attrs = useMemo(() => data?.variant_attributes || [], [data]);
  const remainingDays = useMemo(() => {
    if (!data?.expires_at || data.status !== 'active') return null;
    return Math.max(0, Math.ceil((new Date(data.expires_at).getTime() - Date.now()) / 86_400_000));
  }, [data]);

  if (loading) return <Shell><div className="state"><span className="spinner" />در حال خواندن اطلاعات QR محصول…</div></Shell>;
  if (fatalError || !data) return <Shell><div className="state error"><div className="state-icon">!</div><b>اطلاعات محصول در دسترس نیست</b><span>{fatalError || 'این سریال در سامانه پیدا نشد.'}</span><button type="button" className="secondary-action" onClick={() => void load()}>تلاش دوباره</button></div></Shell>;

  return <Shell>
    {staff && <div className="staffbar"><div><span>ورود کاربر پنل</span><b>{auth?.user.full_name}</b><small>{auth?.user.role?.name || 'کاربر پنل'}</small></div><span className="stafftag">عملیات سازمانی فعال</span></div>}

    {data.images.length > 0 && <div className="gallery"><img src={mediaUrl(data.images[Math.min(slide, data.images.length - 1)])} alt={data.product_name} />{data.images.length > 1 && <div className="dots" role="tablist" aria-label="تصاویر محصول">{data.images.map((image, index) => <button type="button" key={`${image}-${index}`} onClick={() => setSlide(index)} className={index === slide ? 'on' : ''} aria-label={`تصویر ${index + 1}`} aria-current={index === slide ? 'true' : undefined} />)}</div>}</div>}

    <div className="hero">
      <div className="hero-topline"><span className={`status ${data.status}`}>{statusText[data.status] || data.status}</span>{remainingDays !== null && <span className="remaining">{faNumber(remainingDays)} روز تا پایان</span>}</div>
      <h1>{data.product_name}</h1>
      <button type="button" className="serial" dir="ltr" title="کپی سریال" onClick={() => navigator.clipboard?.writeText(data.serial).catch(() => undefined)}>{data.serial}</button>
      {data.product_description && <p className="description">{data.product_description}</p>}
    </div>

    {(data.product_sku || data.variant_sku || attrs.length > 0) && <section className="section"><div className="section-heading"><span>01</span><h2>مشخصات محصول</h2></div><div className="grid">{data.product_sku && <Info label="کد محصول" value={data.product_sku} mono />}{data.variant_sku && <Info label="کد تنوع" value={data.variant_sku} mono />}{attrs.map((attr, index) => <Info key={`${attr.name}-${index}`} label={attr.name} value={attr.value} />)}</div></section>}

    <section className="section">
      <div className="section-heading"><span>02</span><h2>چرخه گارانتی</h2></div>
      <div className="timeline" aria-label="چرخه گارانتی">
        <TimelineStep label="خروج کالا" value={faDate(data.outbound_at)} active={!!data.outbound_at} />
        <TimelineStep label="شروع گارانتی" value={faDate(data.activated_at)} active={!!data.activated_at} />
        <TimelineStep label="پایان گارانتی" value={faDate(data.expires_at)} active={data.status === 'active'} />
      </div>
      <div className="grid warranty-grid"><Info label="مدت گارانتی" value={`${faNumber(data.warranty_months)} ماه`} /><Info label="فعال‌سازی خودکار" value={faDate(data.auto_activate_at)} /><Info label="نوع فعال‌سازی" value={data.activation_source === 'automatic' ? 'خودکار' : data.activation_source === 'customer' ? 'توسط مشتری' : data.activation_source === 'admin' ? 'مدیریت' : '—'} /></div>
    </section>

    {data.status === 'inactive' && <Notice>این محصول هنوز در انبار است. چرخه گارانتی پس از خروج فروش آغاز می‌شود.</Notice>}
    {data.status === 'grace' && <Notice>محصول از انبار خارج شده و اکنون در مهلت فعال‌سازی است. اگر فعال نکنید، در تاریخ تعیین‌شده به‌صورت خودکار فعال می‌شود.</Notice>}
    {data.status === 'returned' && <Notice tone="info">این کالا به انبار مرجوع شده است. وضعیت گارانتی تا خروج فروش بعدی به‌صورت سیستمی نگهداری می‌شود.</Notice>}
    {data.status === 'expired' && <Notice tone="danger">مدت این گارانتی به پایان رسیده است.</Notice>}
    {data.status === 'void' && <Notice tone="danger">این گارانتی توسط مدیریت باطل شده است.</Notice>}

    {!staff && data.can_activate && <form onSubmit={activateCustomer} className="activate action-panel">
      <div className="action-title"><span>فعال‌سازی</span><h2>گارانتی را شروع کنید</h2></div>
      <p>ثبت نام و شماره تماس اختیاری است. با فعال‌سازی، تاریخ شروع و پایان گارانتی قطعی می‌شود.</p>
      <div className="form-grid"><label>نام (اختیاری)<input value={name} onChange={(event) => setName(event.target.value)} maxLength={150} autoComplete="name" /></label><label>شماره تماس (اختیاری)<input value={phone} onChange={(event) => setPhone(event.target.value)} maxLength={20} inputMode="tel" autoComplete="tel" dir="ltr" /></label></div>
      <button disabled={busy === 'activate'}>{busy === 'activate' ? 'در حال فعال‌سازی…' : 'فعال‌کردن گارانتی'}</button>
    </form>}

    {data.status === 'active' && <div className="success"><span>✓</span><div><b>گارانتی معتبر و فعال است</b>{remainingDays !== null && <small>{faNumber(remainingDays)} روز از اعتبار باقی مانده است.</small>}</div></div>}
    {successMessage && <div className="feedback success-feedback">{successMessage}</div>}
    {actionError && <div className="feedback error-feedback">{actionError}</div>}

    {staff && <section className="staffops section">
      <div className="section-heading"><span>03</span><h2>عملیات مجاز پنل</h2></div>
      {item ? <div className="item-summary"><Info label="وضعیت کالا" value={itemStatus[item.status] || item.status} /><Info label="کنترل کیفیت" value={qcText[item.qc_status] || item.qc_status} /></div> : <div className="mini-note">برای نقش فعلی اطلاعات واحد انبار قابل مشاهده نیست؛ عملیات گارانتی همچنان در دسترس است.</div>}
      <div className="ops-grid">
        {can('quality.view') && can('quality.manage') && item && <form onSubmit={submitQC} className="opcard">
          <div className="opcard-head"><span>QC</span><h3>کنترل کیفیت</h3></div>
          <label>نتیجه<select value={qcResult} onChange={(event) => setQcResult(event.target.value as 'passed' | 'failed')}><option value="passed">تأیید</option><option value="failed">رد</option></select></label>
          {qcResult === 'failed' && <><label>نوع عیب<input value={defect} onChange={(event) => setDefect(event.target.value)} /></label><label>تعیین تکلیف<select value={failureAction} onChange={(event) => setFailureAction(event.target.value as 'rework' | 'scrap')}><option value="rework">دوباره‌کاری</option><option value="scrap">ضایعات</option></select></label>{failureAction === 'scrap' && <label>نوع ضایعات<select value={wasteClass} onChange={(event) => setWasteClass(event.target.value as 'normal' | 'abnormal')}><option value="normal">عادی</option><option value="abnormal">غیرعادی</option></select></label>}</>}
          <label>یادداشت<textarea value={qcNotes} onChange={(event) => setQcNotes(event.target.value)} /></label>
          <button disabled={busy === 'qc'}>{busy === 'qc' ? 'در حال ثبت…' : 'ثبت کنترل کیفیت'}</button>
        </form>}

        {canOutbound && item && <form onSubmit={submitOutbound} className="opcard">
          <div className="opcard-head"><span>OUT</span><h3>خروج انبار</h3></div>
          {item.status === 'reserved' && reservationId && <div className="mini-note">رزرو فعال این واحد به خروج متصل می‌شود.</div>}
          {item.status === 'reserved' && !reservationId && <div className="mini-error">رزرو فعال پیدا نشد؛ خروج این واحد برای جلوگیری از مغایرت مسدود است.</div>}
          {!item.location_id ? <div className="mini-error">این واحد داخل مکان انبار نیست.</div> : <>
            <label>نوع خروج<select value={disposition} onChange={(event) => setDisposition(event.target.value as typeof disposition)}><option value="sale">فروش</option><option value="damage">خرابی / ضایعات</option><option value="loss">مفقودی</option><option value="return">مرجوعی عملیاتی</option></select></label>
            {disposition === 'sale' && <label>کانال فروش<select required value={channelId || ''} onChange={(event) => setChannelId(Number(event.target.value))}><option value="">انتخاب</option>{channels.map((channel) => <option key={channel.id} value={channel.id}>{channel.name}</option>)}</select></label>}
            <label>شماره سفارش / مرجع<input value={reference} onChange={(event) => setReference(event.target.value)} /></label>
            <button disabled={busy === 'outbound' || (disposition === 'sale' && !channelId) || (item.status === 'reserved' && !reservationId)}>{busy === 'outbound' ? 'در حال ثبت…' : 'ثبت خروج همین واحد'}</button>
          </>}
        </form>}

        {can('warranty.manage') && <div className="opcard">
          <div className="opcard-head"><span>WR</span><h3>مدیریت گارانتی</h3></div>
          <p>وضعیت فعلی: <b>{statusText[data.status] || data.status}</b></p>
          <button type="button" onClick={staffActivate} disabled={busy === 'staff-warranty' || !data.can_activate}>{busy === 'staff-warranty' ? 'در حال ثبت…' : data.can_activate ? 'فعال‌سازی مدیریتی' : 'فعلاً قابل فعال‌سازی نیست'}</button>
        </div>}
      </div>
    </section>}
  </Shell>;
}

function Info({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return <div className="info"><span>{label}</span><b dir={mono ? 'ltr' : undefined}>{value}</b></div>;
}

function TimelineStep({ label, value, active }: { label: string; value: string; active: boolean }) {
  return <div className={`timeline-step ${active ? 'active' : ''}`}><span className="timeline-dot" /><div><b>{label}</b><small>{value}</small></div></div>;
}

function Notice({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'info' | 'danger' }) {
  return <div className={`notice ${tone}`}>{children}</div>;
}

function Shell({ children }: { children: ReactNode }) {
  return <main><div className="brand"><Link to="/" aria-label="Dario"><b>Dario</b><span>سفر به زندگی راحت</span></Link><span className="brand-chip">PRODUCT ID</span></div><section className="card">{children}</section><p className="foot">Dario · شناسه واحد محصول، مشخصات و گارانتی</p></main>;
}

function LookupPage() {
  const navigate = useNavigate();
  const [serial, setSerial] = useState('');
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const value = serial.trim();
    if (value) navigate(`/warranty/${encodeURIComponent(value)}`);
  };
  return <Shell><div className="lookup"><div className="lookup-mark">D</div><p className="eyebrow">DARIO PRODUCT</p><h1>استعلام محصول و گارانتی</h1><p>سریال درج‌شده روی QR محصول را وارد کنید.</p><form onSubmit={submit}><label>سریال محصول<input dir="ltr" value={serial} onChange={(event) => setSerial(event.target.value)} placeholder="مثال: DARIO-..." autoFocus /></label><button disabled={!serial.trim()}>مشاهده اطلاعات</button></form></div></Shell>;
}

export default function App() {
  return <Routes>
    <Route path="/" element={<LookupPage />} />
    <Route path="/warranty/:serial" element={<WarrantyScreen />} />
    <Route path="/product/:serial" element={<WarrantyScreen />} />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes>;
}
