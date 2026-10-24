import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { authApi, type AuthMe } from '../api/auth';

type Ctx = {
  auth: AuthMe | null;
  loading: boolean;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
  can: (permission: string) => boolean;
};

const C = createContext<Ctx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [auth, setAuth] = useState<AuthMe | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const data = await authApi.me();
      setAuth(data.user.panel_access || data.user.is_superuser ? data : null);
    } catch {
      setAuth(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      setAuth(null);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const onUnauthorized = () => setAuth(null);
    window.addEventListener('dario:unauthorized', onUnauthorized);
    return () => window.removeEventListener('dario:unauthorized', onUnauthorized);
  }, []);

  const can = useCallback((permission: string) => (
    !!auth && (auth.user.is_superuser || auth.permissions.includes('*') || auth.permissions.includes(permission))
  ), [auth]);

  const value = useMemo(() => ({ auth, loading, refresh, logout, can }), [auth, loading, refresh, logout, can]);
  return <C.Provider value={value}>{children}</C.Provider>;
}

export function useAuth() {
  const value = useContext(C);
  if (!value) throw new Error('AuthProvider missing');
  return value;
}
