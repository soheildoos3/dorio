import { ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';

export function NotFoundPage() {
  return (
    <div className="grid min-h-[70vh] place-items-center">
      <div className="text-center"><p className="text-7xl font-black text-slate-200">404</p><h1 className="mt-4 text-2xl font-black text-slate-900">این صفحه وجود ندارد</h1><p className="mt-2 text-sm text-slate-500">آدرس واردشده در پنل Dario تعریف نشده است.</p><Link to="/" className="mt-6 inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-bold text-white"><ArrowRight className="h-4 w-4" />بازگشت به داشبورد</Link></div>
    </div>
  );
}
