import { Navigate, Route, Routes } from 'react-router-dom';
import { useAuth } from './auth/AuthProvider';
import { AppShell } from './components/layout/AppShell';
import { LoadingState } from './components/ui/States';
import { AccountingPage } from './pages/AccountingPage';
import { CatalogPage } from './pages/CatalogPage';
import { DashboardPage } from './pages/DashboardPage';
import { InventoryPage } from './pages/InventoryPage';
import { LoginPage } from './pages/LoginPage';
import { ManagementPage } from './pages/ManagementPage';
import { ManufacturingPage } from './pages/ManufacturingPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { OperationsPage } from './pages/OperationsPage';
import { OutboundPage } from './pages/OutboundPage';
import { ProductDetailPage } from './pages/ProductDetailPage';
import { QCScanPage } from './pages/QCScanPage';
import { QualityPage } from './pages/QualityPage';
import { SalesPage } from './pages/SalesPage';
import { TailorsPage } from './pages/TailorsPage';
import { UsersPage } from './pages/UsersPage';
import { WarehousePage } from './pages/WarehousePage';
import { WarrantyPage } from './pages/WarrantyPage';

export default function App() {
  const { auth, loading, can } = useAuth();
  if (loading) return <div className="p-10"><LoadingState /></div>;
  if (!auth) return <LoginPage />;

  const isAdmin = auth.user.is_superuser || auth.user.role?.code === 'admin';
  const canManageOrganization = isAdmin || can('channels.manage') || can('hr.manage');
  const canOutbound = can('inventory.view') && can('inventory.outbound');

  const firstAccessible = [
    can('dashboard.view') && '/',
    can('sales.view') && '/sales',
    can('manufacturing.view') && '/manufacturing',
    can('accounting.view') && '/accounting',
    can('catalog.view') && '/catalog',
    can('warehouse.view') && '/warehouses',
    can('inventory.view') && '/inventory',
    canOutbound && '/outbound',
    can('quality.view') && '/quality',
    can('warranty.view') && '/warranty',
    can('tailors.view') && '/tailors',
    can('users.view') && '/users',
    canManageOrganization && '/management',
  ].find(Boolean) as string | undefined;

  const fallback = firstAccessible ? <Navigate to={firstAccessible} replace /> : <NotFoundPage />;

  return (
    <AppShell>
      <Routes>
        <Route path="/" element={can('dashboard.view') ? <DashboardPage /> : fallback} />
        <Route path="/catalog" element={can('catalog.view') ? <CatalogPage /> : fallback} />
        <Route path="/catalog/products/:id" element={can('catalog.view') ? <ProductDetailPage /> : fallback} />
        <Route path="/warehouses" element={can('warehouse.view') ? <WarehousePage /> : fallback} />
        <Route path="/inventory" element={can('inventory.view') ? <InventoryPage /> : fallback} />
        <Route path="/outbound" element={canOutbound ? <OutboundPage /> : fallback} />
        <Route path="/operations" element={can('inventory.view') ? <OperationsPage /> : fallback} />
        <Route path="/quality" element={can('quality.view') ? <QualityPage /> : fallback} />
        <Route path="/quality/scan/:serial" element={can('quality.view') ? <QCScanPage /> : fallback} />
        <Route path="/warranty" element={can('warranty.view') ? <WarrantyPage /> : fallback} />
        <Route path="/tailors" element={can('tailors.view') ? <TailorsPage /> : fallback} />
        <Route path="/sales" element={can('sales.view') ? <SalesPage /> : fallback} />
        <Route path="/manufacturing" element={can('manufacturing.view') ? <ManufacturingPage /> : fallback} />
        <Route path="/accounting" element={can('accounting.view') ? <AccountingPage /> : fallback} />
        <Route path="/users" element={can('users.view') ? <UsersPage /> : fallback} />
        <Route path="/management" element={canManageOrganization ? <ManagementPage /> : fallback} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </AppShell>
  );
}
