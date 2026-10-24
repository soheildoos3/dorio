import {apiRequest,jsonBody} from '../lib/api';
import type {BOM,LaborEntry,Material,MaterialMovement,MaterialStock,OverheadRate,ProductionOrder} from './types';

export type MaterialPayload={code?:string;name?:string;unit?:string;category?:string|null;reorder_point?:number;is_active?:boolean};
export type BomPayload={product_id:number;version:number;status:'draft'|'active'|'retired';effective_from?:string|null;effective_to?:string|null;notes?:string|null;items:Array<{material_id:number;quantity_per_unit:number;normal_waste_percent:number}>};
export type OrderPayload={product_id:number;variant_id?:number|null;quantity:number;tailor_user_id?:number|null;bom_id:number;fg_location_id?:number|null;due_at?:string|null;notes?:string|null};
export type LaborPayload={production_order_id:number;tailor_user_id:number;work_date:string;hours:number;pieces:number;rate:number;rate_basis:'hour'|'piece';notes?:string|null};
export type OverheadPayload={name:string;basis:'piece'|'direct_labor_hour';rate:number;effective_from:string;effective_to?:string|null;is_active?:boolean};

export const manufacturingApi={
  materials:()=>apiRequest<Material[]>('/manufacturing/materials'),
  createMaterial:(p:{code:string;name:string;unit:string;category?:string|null;reorder_point?:number;is_active?:boolean})=>apiRequest<Material>('/manufacturing/materials',{method:'POST',body:jsonBody(p)}),
  updateMaterial:(id:number,p:MaterialPayload)=>apiRequest<Material>(`/manufacturing/materials/${id}`,{method:'PATCH',body:jsonBody(p)}),
  deleteMaterial:(id:number)=>apiRequest<void>(`/manufacturing/materials/${id}`,{method:'DELETE'}),
  materialStock:()=>apiRequest<MaterialStock[]>('/manufacturing/material-stock'),
  materialMovements:()=>apiRequest<MaterialMovement[]>('/manufacturing/material-movements?offset=0&limit=500'),
  purchase:(p:{material_id:number;location_id:number;quantity:number;unit_cost:number;freight_cost?:number;offset_account_code?:string;reference_ref?:string|null;notes?:string|null})=>apiRequest<MaterialMovement>('/manufacturing/materials/purchase',{method:'POST',body:jsonBody(p)}),
  adjust:(p:{material_id:number;location_id:number;quantity:number;direction:'increase'|'decrease';offset_account_code?:string;notes?:string|null})=>apiRequest<MaterialMovement>('/manufacturing/materials/adjust',{method:'POST',body:jsonBody(p)}),
  issue:(p:{material_id:number;location_id:number;quantity:number;production_order_id:number;notes?:string|null})=>apiRequest<MaterialMovement>('/manufacturing/materials/issue',{method:'POST',body:jsonBody(p)}),
  returnMaterial:(p:{material_id:number;location_id:number;quantity:number;production_order_id:number;notes?:string|null})=>apiRequest<MaterialMovement>('/manufacturing/materials/return',{method:'POST',body:jsonBody(p)}),
  boms:()=>apiRequest<BOM[]>('/manufacturing/boms'),
  createBom:(p:BomPayload)=>apiRequest<BOM>('/manufacturing/boms',{method:'POST',body:jsonBody(p)}),
  updateBom:(id:number,p:Partial<Pick<BomPayload,'status'|'effective_from'|'effective_to'|'notes'|'items'>>)=>apiRequest<BOM>(`/manufacturing/boms/${id}`,{method:'PATCH',body:jsonBody(p)}),
  deleteBom:(id:number)=>apiRequest<void>(`/manufacturing/boms/${id}`,{method:'DELETE'}),
  orders:()=>apiRequest<ProductionOrder[]>('/manufacturing/orders'),
  createOrder:(p:OrderPayload)=>apiRequest<ProductionOrder>('/manufacturing/orders',{method:'POST',body:jsonBody(p)}),
  updateOrder:(id:number,p:Partial<OrderPayload>)=>apiRequest<ProductionOrder>(`/manufacturing/orders/${id}`,{method:'PATCH',body:jsonBody(p)}),
  deleteOrder:(id:number)=>apiRequest<void>(`/manufacturing/orders/${id}`,{method:'DELETE'}),
  issueBom:(id:number,location_id:number)=>apiRequest<ProductionOrder>(`/manufacturing/orders/${id}/issue-bom`,{method:'POST',body:jsonBody({location_id})}),
  setStatus:(id:number,status:string)=>apiRequest<ProductionOrder>(`/manufacturing/orders/${id}/status`,{method:'PATCH',body:jsonBody({status})}),
  prepareQc:(id:number,location_id?:number|null)=>apiRequest<ProductionOrder>(`/manufacturing/orders/${id}/prepare-qc`,{method:'POST',body:jsonBody({location_id:location_id||null})}),
  labor:()=>apiRequest<LaborEntry[]>('/manufacturing/labor'),
  createLabor:(p:LaborPayload)=>apiRequest<LaborEntry>('/manufacturing/labor',{method:'POST',body:jsonBody(p)}),
  updateLabor:(id:number,p:Partial<Omit<LaborPayload,'production_order_id'>>)=>apiRequest<LaborEntry>(`/manufacturing/labor/${id}`,{method:'PATCH',body:jsonBody(p)}),
  deleteLabor:(id:number)=>apiRequest<void>(`/manufacturing/labor/${id}`,{method:'DELETE'}),
  approveLabor:(id:number)=>apiRequest<LaborEntry>(`/manufacturing/labor/${id}/approve`,{method:'POST'}),
  overheadRates:()=>apiRequest<OverheadRate[]>('/manufacturing/overhead-rates'),
  createOverheadRate:(p:OverheadPayload)=>apiRequest<OverheadRate>('/manufacturing/overhead-rates',{method:'POST',body:jsonBody(p)}),
  updateOverheadRate:(id:number,p:Partial<OverheadPayload>)=>apiRequest<OverheadRate>(`/manufacturing/overhead-rates/${id}`,{method:'PATCH',body:jsonBody(p)}),
  deleteOverheadRate:(id:number)=>apiRequest<void>(`/manufacturing/overhead-rates/${id}`,{method:'DELETE'}),
  absorbOverhead:(orderId:number,rateId:number)=>apiRequest<ProductionOrder>(`/manufacturing/orders/${orderId}/absorb-overhead/${rateId}`,{method:'POST'}),
};
