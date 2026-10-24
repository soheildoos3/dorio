import { useState, type ReactNode } from 'react';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';

export function AppShell({ children }: { children: ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  return (
    <div className="min-h-screen bg-slate-50">
      <a href="#main-content" className="sr-only z-[100] rounded-xl bg-slate-950 px-4 py-2 text-white focus:not-sr-only focus:fixed focus:right-4 focus:top-4">رفتن به محتوای اصلی</a>
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="min-w-0 lg:mr-72">
        <Topbar onMenu={() => setSidebarOpen(true)} />
        <main id="main-content" className="mx-auto w-full max-w-[1600px] px-3 py-4 pb-[max(1rem,env(safe-area-inset-bottom))] sm:px-5 sm:py-6 lg:px-8 lg:py-8">{children}</main>
      </div>
    </div>
  );
}
