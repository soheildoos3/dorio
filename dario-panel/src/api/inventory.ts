import { normalizeScanIdentifier } from '../lib/scan';
import { apiRequest, jsonBody } from '../lib/api';
import type { ProductDefaultLocation, ProductItem, SalesSummary, Stock, StockMovement, StockMovementType, StockReservation } from './types';

export type ProductItemPayload = {
  variant_id: number; serial_number?: string | null; location_id?: number | null;
  warehouse_id?: number | null; received_at?: string | null;
};
export type ProductItemBatchPayload = { variant_id:number; count:number; location_id?:number|null; warehouse_id?:number|null; received_at?:string|null };
export type MovementPayload = {
  item_id?: number | null; variant_id: number; location_id?: number | null; type: StockMovementType; quantity: number;
  reference_type?: string | null; reference_id?: number | null; reason?: string | null; created_by?: number | null;
};
export type ReservationPayload = {
  item_id?: number | null; variant_id: number; location_id: number; reference_type: string; reference_id?: number | null; reference_code?: string | null;
  quantity?: number; expires_at?: string | null; created_by?: number | null;
};
export type DefaultLocationPayload = { variant_id: number; location_id: number; priority?: number; is_primary?: boolean };
export type ProductItemUpdatePayload = { serial_number?: string | null };
export type DefaultLocationUpdatePayload = { location_id?: number; priority?: number; is_primary?: boolean };
export type OutboundDisposition = 'sale' | 'damage' | 'loss' | 'return' | 'other';
export type OutboundPayload = {
  variant_id: number; location_id: number; quantity: number; item_id?: number | null; reservation_id?: number | null;
  disposition: OutboundDisposition; reference_type?: string; reference_id?: number | null; reason?: string | null; channel_id?: number | null; external_reference?: string | null; created_by?: number | null;
};

export const inventoryApi = {
  items: (variantId?: number) => apiRequest<ProductItem[]>(`/inventory/items?offset=0&limit=500${variantId ? `&variant_id=${variantId}` : ''}`),
  scanItem: (identifier:string) => apiRequest<ProductItem>(`/inventory/scan/${encodeURIComponent(normalizeScanIdentifier(identifier))}`),
  decodeQrImage: (file:File) => { const form=new FormData(); form.set('file',file); return apiRequest<{value:string}>('/inventory/decode-qr-image',{method:'POST',body:form}); },
  createItem: (payload: ProductItemPayload) => apiRequest<ProductItem>('/inventory/items', { method: 'POST', body: jsonBody(payload) }),
  createItemsBatch: (payload: ProductItemBatchPayload) => apiRequest<ProductItem[]>('/inventory/items/batch', { method: 'POST', body: jsonBody(payload) }),
  updateItem: (id: number, payload: ProductItemUpdatePayload) => apiRequest<ProductItem>(`/inventory/items/${id}`, { method: 'PATCH', body: jsonBody(payload) }),
  stock: (variantId?: number) => apiRequest<Stock[]>(`/inventory/stock${variantId ? `?variant_id=${variantId}` : ''}`),
  movements: () => apiRequest<StockMovement[]>('/inventory/movements?offset=0&limit=500'),
  createMovement: (payload: MovementPayload) => apiRequest<StockMovement>('/inventory/movements', { method: 'POST', body: jsonBody(payload) }),
  outbound: () => apiRequest<StockMovement[]>('/inventory/outbound?offset=0&limit=500'),
  salesSummary: () => apiRequest<SalesSummary>('/inventory/sales-summary'),
  createOutbound: (payload: OutboundPayload) => apiRequest<StockMovement>('/inventory/outbound', { method: 'POST', body: jsonBody(payload) }),
  reservations: () => apiRequest<StockReservation[]>('/inventory/reservations?offset=0&limit=500'),
  reserve: (payload: ReservationPayload) => apiRequest<StockReservation>('/inventory/reservations', { method: 'POST', body: jsonBody(payload) }),
  releaseReservation: (id: number) => apiRequest<StockReservation>(`/inventory/reservations/${id}/release`, { method: 'POST' }),
  defaultLocations: () => apiRequest<ProductDefaultLocation[]>('/inventory/default-locations?offset=0&limit=1000'),
  createDefaultLocation: (payload: DefaultLocationPayload) => apiRequest<ProductDefaultLocation>('/inventory/default-locations', { method: 'POST', body: jsonBody(payload) }),
  updateDefaultLocation: (id: number, payload: DefaultLocationUpdatePayload) => apiRequest<ProductDefaultLocation>(`/inventory/default-locations/${id}`, { method: 'PATCH', body: jsonBody(payload) }),
};
