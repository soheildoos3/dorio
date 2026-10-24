import { apiRequest, apiUrl, jsonBody } from '../lib/api';
import { normalizeScanIdentifier } from '../lib/scan';
import type { DefectSeverity, LabelLog, LabelType, ProductItem, QCRecord, QCRecordResult } from './types';
import { qrPrintQuery, type QrPrintSettings } from '../lib/qrPrint';

export type QCPayload = {
  item_id: number;
  result: QCRecordResult;
  defect_type?: string | null;
  defect_severity?: DefectSeverity | null;
  failure_action?: 'rework' | 'scrap' | null;
  waste_class?: 'normal' | 'abnormal' | null;
  notes?: string | null;
  photos?: Array<Record<string, unknown> | string> | null;
};

export type LabelPayload = { item_id: number; label_type: LabelType };

function openPrint(path: string) {
  return window.open(apiUrl(path), '_blank', 'noopener,noreferrer');
}

export const qualityApi = {
  scanItem: (identifier: string) => apiRequest<ProductItem>(`/quality/scan/${encodeURIComponent(normalizeScanIdentifier(identifier))}`),
  qcRecords: (itemId?: number) => apiRequest<QCRecord[]>(`/quality/qc-records?offset=0&limit=500${itemId ? `&item_id=${itemId}` : ''}`),
  uploadPhoto: (itemId: number, file: File) => {
    const form = new FormData();
    form.set('file', file);
    return apiRequest<{ url: string }>(`/quality/items/${itemId}/photos`, { method: 'POST', body: form });
  },
  recordQC: (payload: QCPayload) => apiRequest<QCRecord>('/quality/qc-records', { method: 'POST', body: jsonBody(payload) }),
  labels: (itemId?: number) => apiRequest<LabelLog[]>(`/quality/labels?offset=0&limit=500${itemId ? `&item_id=${itemId}` : ''}`),
  logLabel: (payload: LabelPayload) => apiRequest<LabelLog>('/quality/labels', { method: 'POST', body: jsonBody(payload) }),
  batchLabels: (payload: { variant_id: number; label_type: LabelType; limit: number }) => apiRequest<{ item_ids: number[]; count: number }>('/quality/labels/batch', { method: 'POST', body: jsonBody(payload) }),
  printBatchUrl: (itemIds: number[], type: LabelType, settings: QrPrintSettings) => apiUrl(`/quality/print-batch?item_ids=${itemIds.join(',')}&label_type=${type}&${qrPrintQuery(settings,true)}`),
  printBatch: (itemIds: number[], type: LabelType, settings: QrPrintSettings) => openPrint(`/quality/print-batch?item_ids=${itemIds.join(',')}&label_type=${type}&${qrPrintQuery(settings,true)}`),
  print: (itemId: number, type: LabelType, settings: QrPrintSettings) => openPrint(`/quality/items/${itemId}/print?label_type=${type}&${qrPrintQuery(settings,false)}`),
};
