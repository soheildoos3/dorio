import { useEffect, useState, type FormEvent } from 'react';
import { ArrowLeft, Boxes, ShieldCheck } from 'lucide-react';
import { authApi } from '../api/auth';
import { Button } from '../components/ui/Button';
import { Field, Input } from '../components/ui/Field';
import { useToast } from '../components/feedback/ToastProvider';
import { useAuth } from '../auth/AuthProvider';

export function LoginPage() {
  const [bootstrap, setBootstrap] = useState(false);
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('مدیر سیستم');
  const [submitting, setSubmitting] = useState(false);
  const toast = useToast();
  const auth = useAuth();

  useEffect(() => { authApi.status().then((x) => setBootstrap(x.required)).catch(() => {}); }, []);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      if (bootstrap) await authApi.bootstrap({ username: identifier, password, full_name: fullName });
      else {
        const r = await authApi.login({ identifier, password });
        if (!r.panel_access) {
          toast.error('این حساب برای خرید/سایت معتبر است اما دسترسی پنل ندارد');
          await authApi.logout();
          return;
        }
      }
      await auth.refresh();
    } catch (e) {
      toast.error('ورود ناموفق', e instanceof Error ? e.message : 'خطا');
    } finally {
      setSubmitting(false);
    }
  }

  return <div className="min-h-screen min-h-[100dvh] bg-slate-950 p-3 sm:p-6">
    <div className="mx-auto grid min-h-[calc(100dvh-1.5rem)] max-w-6xl overflow-hidden rounded-[2rem] border border-white/10 bg-slate-900 shadow-2xl sm:min-h-[calc(100dvh-3rem)] lg:grid-cols-[1.05fr_.95fr]">
      <div className="relative hidden overflow-hidden p-10 text-white lg:flex lg:flex-col lg:justify-between">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_80%_10%,rgba(14,165,233,.22),transparent_30%),radial-gradient(circle_at_10%_90%,rgba(99,102,241,.18),transparent_30%)]" />
        <div className="relative">
          <div className="flex items-center gap-3"><span className="grid h-12 w-12 place-items-center rounded-2xl bg-white text-lg font-black text-slate-950">D</span><div><p className="text-xl font-black">Dario</p><p className="text-xs text-slate-400">Operations Panel</p></div></div>
          <h1 className="mt-16 max-w-lg text-4xl font-black leading-[1.5]">مدیریت یکپارچه تولید، انبار، کیفیت و گارانتی</h1>
          <p className="mt-5 max-w-xl text-sm leading-8 text-slate-400">پنل عملیاتی برای کنترل دقیق جریان کالا از تولید تا خروج و خدمات پس از فروش.</p>
        </div>
        <div className="relative grid gap-3 sm:grid-cols-2">
          <div className="rounded-2xl border border-white/10 bg-white/5 p-4"><Boxes className="h-5 w-5 text-sky-300" /><p className="mt-3 text-sm font-bold">موجودی و خروج</p><p className="mt-1 text-xs leading-6 text-slate-400">رهگیری سریال، مکان و عملیات انبار</p></div>
          <div className="rounded-2xl border border-white/10 bg-white/5 p-4"><ShieldCheck className="h-5 w-5 text-emerald-300" /><p className="mt-3 text-sm font-bold">کیفیت و گارانتی</p><p className="mt-1 text-xs leading-6 text-slate-400">فعال‌سازی و رهگیری چرخه خدمات</p></div>
        </div>
      </div>

      <div className="flex items-center justify-center bg-white p-5 sm:p-10">
        <div className="w-full max-w-md">
          <div className="mb-8 lg:hidden"><div className="flex items-center gap-3"><span className="grid h-11 w-11 place-items-center rounded-2xl bg-slate-950 text-base font-black text-white">D</span><div><p className="text-xl font-black text-slate-950">Dario</p><p className="text-xs text-slate-400">پنل عملیات</p></div></div></div>
          <div className="mb-7">
            <p className="text-2xl font-black text-slate-950 sm:text-3xl">{bootstrap ? 'راه‌اندازی مدیر سیستم' : 'ورود به پنل'}</p>
            <p className="mt-2 text-sm leading-7 text-slate-500">{bootstrap ? 'حساب اولین مدیر را بسازید تا سیستم آماده استفاده شود.' : 'با حساب دارای دسترسی پنل وارد شوید.'}</p>
          </div>
          <form onSubmit={submit} className="space-y-4">
            {bootstrap && <Field label="نام مدیر" required><Input autoComplete="name" required value={fullName} onChange={(e) => setFullName(e.target.value)} /></Field>}
            <Field label={bootstrap ? 'نام کاربری مدیر' : 'نام کاربری، ایمیل یا تلفن'} hint={!bootstrap ? 'هر کدام که برای حساب ثبت شده باشد قابل استفاده است.' : undefined} required>
              <Input dir="ltr" autoComplete="username" required value={identifier} onChange={(e) => setIdentifier(e.target.value)} />
            </Field>
            <Field label="رمز عبور" required>
              <Input dir="ltr" type="password" autoComplete={bootstrap ? 'new-password' : 'current-password'} minLength={8} required value={password} onChange={(e) => setPassword(e.target.value)} />
            </Field>
            <Button size="lg" className="mt-2 w-full" type="submit" loading={submitting}>
              {bootstrap ? 'ایجاد مدیر و ورود' : 'ورود'}<ArrowLeft className="h-4 w-4" />
            </Button>
          </form>
        </div>
      </div>
    </div>
  </div>;
}
