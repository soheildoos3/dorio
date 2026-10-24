import { apiRequest, jsonBody } from '../lib/api';
import type { Location, LocationType, Warehouse } from './types';

export type WarehousePayload = {
  code: string; name: string; address?: string | null; manager_id?: number | null; phone?: string | null; is_active?: boolean;
};
export type LocationPayload = {
  warehouse_id: number; parent_id?: number | null; type: LocationType; code: string; name?: string | null;
  is_pickable?: boolean; is_receivable?: boolean; max_items?: number | null; max_weight_kg?: number | null;
  sort_order?: number; is_active?: boolean;
};

export const warehouseApi = {
  list: () => apiRequest<Warehouse[]>('/warehouses'),
  create: (payload: WarehousePayload) => apiRequest<Warehouse>('/warehouses', { method: 'POST', body: jsonBody(payload) }),
  update: (id: number, payload: Partial<WarehousePayload>) => apiRequest<Warehouse>(`/warehouses/${id}`, { method: 'PATCH', body: jsonBody(payload) }),
  delete: (id: number) => apiRequest<void>(`/warehouses/${id}`, { method: 'DELETE' }),
  locations: (warehouseId: number) => apiRequest<Location[]>(`/warehouses/${warehouseId}/locations`),
  createLocation: (payload: LocationPayload) => apiRequest<Location>('/warehouses/locations', { method: 'POST', body: jsonBody(payload) }),
  updateLocation: (id: number, payload: Partial<Omit<LocationPayload, 'warehouse_id'>>) => apiRequest<Location>(`/warehouses/locations/${id}`, { method: 'PATCH', body: jsonBody(payload) }),
  deleteLocation: (id: number) => apiRequest<void>(`/warehouses/locations/${id}`, { method: 'DELETE' }),
};
