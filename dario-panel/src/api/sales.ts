import {apiRequest,jsonBody} from '../lib/api';
import type {SalesInvoice,SalesReturn,CatalogFeedRow} from './types';

export const salesApi={
  invoices:()=>apiRequest<SalesInvoice[]>('/sales/invoices?offset=0&limit=500'),
  createInvoice:(p:{channel_id:number;customer_name?:string|null;customer_phone?:string|null;external_reference?:string|null;notes?:string|null;lines:Array<{item_id:number}>})=>apiRequest<SalesInvoice>('/sales/invoices',{method:'POST',body:jsonBody(p)}),
  confirm:(id:number)=>apiRequest<SalesInvoice>(`/sales/invoices/${id}/confirm`,{method:'POST'}),
  ship:(id:number)=>apiRequest<SalesInvoice>(`/sales/invoices/${id}/ship`,{method:'POST'}),
  cancel:(id:number)=>apiRequest<SalesInvoice>(`/sales/invoices/${id}/cancel`,{method:'POST'}),
  returns:()=>apiRequest<SalesReturn[]>('/sales/returns?offset=0&limit=500'),
  createReturn:(invoiceId:number,p:{reason?:string|null;lines:Array<{invoice_line_id:number;location_id:number}>})=>apiRequest<SalesReturn>(`/sales/invoices/${invoiceId}/returns`,{method:'POST',body:jsonBody(p)}),
  catalogFeed:(channelId:number)=>apiRequest<CatalogFeedRow[]>(`/sales/catalog-feed/${channelId}`),
};
