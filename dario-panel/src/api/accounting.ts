import {apiRequest,jsonBody} from '../lib/api';
import type {Account,AuditEvent,CostCenter,FinancialStatements,JournalEntry,TrialBalanceRow} from './types';

export type AccountPayload={code:string;name:string;account_type:'asset'|'liability'|'equity'|'revenue'|'expense';parent_id?:number|null;allow_posting?:boolean;is_active?:boolean};
export type JournalPayload={entry_date?:string;description:string;source_type?:string|null;source_id?:number|null;source_ref?:string|null;lines:Array<{account_id:number;cost_center_id?:number|null;debit:number;credit:number;memo?:string|null}>};

export const accountingApi={
  accounts:()=>apiRequest<Account[]>('/accounting/accounts'),
  createAccount:(p:AccountPayload)=>apiRequest<Account>('/accounting/accounts',{method:'POST',body:jsonBody(p)}),
  updateAccount:(id:number,p:Partial<Pick<AccountPayload,'name'|'parent_id'|'allow_posting'|'is_active'>>)=>apiRequest<Account>(`/accounting/accounts/${id}`,{method:'PATCH',body:jsonBody(p)}),
  deleteAccount:(id:number)=>apiRequest<void>(`/accounting/accounts/${id}`,{method:'DELETE'}),
  costCenters:()=>apiRequest<CostCenter[]>('/accounting/cost-centers'),
  createCostCenter:(p:{code:string;name:string;center_type:string;is_active?:boolean})=>apiRequest<CostCenter>('/accounting/cost-centers',{method:'POST',body:jsonBody(p)}),
  updateCostCenter:(id:number,p:{name?:string;center_type?:string;is_active?:boolean})=>apiRequest<CostCenter>(`/accounting/cost-centers/${id}`,{method:'PATCH',body:jsonBody(p)}),
  deleteCostCenter:(id:number)=>apiRequest<void>(`/accounting/cost-centers/${id}`,{method:'DELETE'}),
  journals:()=>apiRequest<JournalEntry[]>('/accounting/journals?offset=0&limit=500'),
  createJournalDraft:(p:JournalPayload)=>apiRequest<JournalEntry>('/accounting/journals',{method:'POST',body:jsonBody(p)}),
  finalizeJournal:(id:number)=>apiRequest<JournalEntry>(`/accounting/journals/${id}/post`,{method:'POST'}),
  reverseJournal:(id:number)=>apiRequest<JournalEntry>(`/accounting/journals/${id}/reverse`,{method:'POST'}),
  inventoryImpairment:(p:{inventory_account_code:'1300'|'1310'|'1320'|'1330'|'1340';amount:number;reference:string;description?:string|null})=>apiRequest<JournalEntry>('/accounting/period-adjustments/inventory-impairment',{method:'POST',body:jsonBody(p)}),
  overheadVariance:(p:{actual_overhead:number;absorbed_overhead:number;cogs_share_percent:number;reference:string;description?:string|null})=>apiRequest<JournalEntry>('/accounting/period-adjustments/overhead-variance',{method:'POST',body:jsonBody(p)}),
  audit:()=>apiRequest<AuditEvent[]>('/accounting/audit?offset=0&limit=500'),
  trialBalance:(from?:string,to?:string)=>apiRequest<TrialBalanceRow[]>(`/accounting/reports/trial-balance?${new URLSearchParams(Object.fromEntries(Object.entries({date_from:from,date_to:to}).filter(([,v])=>v)))}`),
  statements:(from?:string,to?:string)=>apiRequest<FinancialStatements>(`/accounting/reports/financial-statements?${new URLSearchParams(Object.fromEntries(Object.entries({date_from:from,date_to:to}).filter(([,v])=>v)))}`),
};
