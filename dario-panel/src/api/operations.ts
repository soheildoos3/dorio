import { apiRequest, jsonBody } from '../lib/api';
import type { CycleCount, CycleCountLine, StockAdjustment, StockAdjustmentReason, StockAdjustmentType, StockOpening, StockTransfer } from './types';

export type TransferPayload = {
  transfer_number?: string | null; item_id?: number | null; variant_id: number; from_location_id: number; to_location_id: number;
  quantity?: number; requested_by?: number | null; notes?: string | null;
};
export type AdjustmentPayload = {
  adjustment_number?: string | null; item_id?: number | null; variant_id: number; location_id: number; type: StockAdjustmentType;
  quantity: number; reason: StockAdjustmentReason; reference_type?: string | null; reference_id?: number | null;
  approved_by?: number | null; created_by?: number | null;
};
export type CycleCountPayload = { count_number?: string | null; warehouse_id: number; location_id?: number | null; created_by?: number | null; notes?: string | null };
export type CycleCountLinePayload = {
  cycle_count_id: number; item_id: number; variant_id: number; location_id: number; system_qty: number; counted_qty: number; notes?: string | null;
};
export type OpeningPayload = { variant_id: number; location_id: number; quantity: number; recorded_by?: number | null };

export const operationsApi = {
  transfers: () => apiRequest<StockTransfer[]>('/inventory-operations/transfers'),
  createTransfer: (payload: TransferPayload) => apiRequest<StockTransfer>('/inventory-operations/transfers', { method: 'POST', body: jsonBody(payload) }),
  completeTransfer: (id: number) => apiRequest<StockTransfer>(`/inventory-operations/transfers/${id}/complete`, { method: 'POST' }),
  adjustments: () => apiRequest<StockAdjustment[]>('/inventory-operations/adjustments?offset=0&limit=500'),
  createAdjustment: (payload: AdjustmentPayload) => apiRequest<StockAdjustment>('/inventory-operations/adjustments', { method: 'POST', body: jsonBody(payload) }),
  cycleCounts: () => apiRequest<CycleCount[]>('/inventory-operations/cycle-counts?offset=0&limit=500'),
  createCycleCount: (payload: CycleCountPayload) => apiRequest<CycleCount>('/inventory-operations/cycle-counts', { method: 'POST', body: jsonBody(payload) }),
  cycleLines: (countId: number) => apiRequest<CycleCountLine[]>(`/inventory-operations/cycle-counts/${countId}/lines`),
  createCycleLine: (payload: CycleCountLinePayload) => apiRequest<CycleCountLine>('/inventory-operations/cycle-count-lines', { method: 'POST', body: jsonBody(payload) }),
  openings: () => apiRequest<StockOpening[]>('/inventory-operations/openings?offset=0&limit=500'),
  createOpening: (payload: OpeningPayload) => apiRequest<StockOpening>('/inventory-operations/openings', { method: 'POST', body: jsonBody(payload) }),
};
