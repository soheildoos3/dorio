export type ProductStatus = 'draft' | 'active' | 'archived';
export type LocationType = 'zone' | 'aisle' | 'rack' | 'shelf' | 'bin';
export type QCStatus = 'pending' | 'passed' | 'failed';
export type ProductItemStatus = 'pending_qc' | 'in_stock' | 'reserved' | 'sold' | 'returned' | 'damaged' | 'lost';
export type StockMovementType = 'in' | 'out' | 'transfer' | 'adjust' | 'qc_pass' | 'qc_fail' | 'reserve' | 'release';
export type StockReservationStatus = 'active' | 'released' | 'fulfilled';
export type StockTransferStatus = 'pending' | 'in_transit' | 'completed' | 'cancelled';
export type StockAdjustmentType = 'increase' | 'decrease';
export type StockAdjustmentReason = 'cycle_count' | 'damage' | 'loss' | 'return' | 'correction' | 'other';
export type CycleCountStatus = 'draft' | 'in_progress' | 'completed' | 'cancelled';
export type CycleCountLineStatus = 'pending' | 'counted' | 'adjusted';
export type QCRecordResult = 'passed' | 'failed';
export type DefectSeverity = 'minor' | 'major' | 'critical';
export type LabelType = 'qc' | 'warranty';
export type UserStatus = 'active' | 'inactive' | 'suspended';
export type UserType = 'customer' | 'employee' | 'tailor';

export interface Category { id:number; parent_id:number|null; name:string; path:string; level:number; sort_order:number; is_active:boolean; created_at:string }
export interface Product { id:number; sku:string|null; name:string; description:string|null; category_id:number|null; is_sellable:boolean; is_manufacturable:boolean; warranty_months:number; status:ProductStatus; created_at:string; updated_at:string; deleted_at:string|null }
export interface VariantAttribute { attribute_id:number; attribute_code:string; attribute_name:string; value_id:number; value:string }
export interface ProductVariant { id:number; product_id:number; sku:string|null; attributes:Record<string,unknown>; resolved_attributes:VariantAttribute[]; sale_price:string|number; is_active:boolean; created_at:string }
export interface Media { id:number; product_id:number; variant_id:number|null; url:string; is_primary:boolean; sort_order:number; created_at:string }
export interface AttributeValue { id:number; attribute_id:number; value:string; sort_order:number }
export interface AttributeDefinition { id:number; code:string; name:string; is_variant_axis:boolean; sort_order:number; values:AttributeValue[] }
export interface ProductAttributeSelection { id:number; attribute:AttributeDefinition; values:AttributeValue[]; sort_order:number }
export interface ProductDetail extends Product { category:Category|null; variants:ProductVariant[]; media:Media[]; attribute_config:ProductAttributeSelection[] }

export interface Warehouse { id:number; code:string; name:string; address:string|null; manager_id:number|null; phone:string|null; is_active:boolean; created_at:string; updated_at:string }
export interface Location { id:number; warehouse_id:number; parent_id:number|null; type:LocationType; code:string; name:string|null; path:string; level:number; is_pickable:boolean; is_receivable:boolean; max_items:number|null; max_weight_kg:string|number|null; sort_order:number; is_active:boolean; created_at:string }
export interface ProductItem { id:number; variant_id:number; serial_number:string|null; warranty_serial:string|null; production_order_id:number|null; unit_cost_snapshot:string|number|null; qc_status:QCStatus; qc_checked_by:number|null; qc_checked_at:string|null; qc_notes:string|null; qc_label_printed:boolean; warranty_label_printed:boolean; status:ProductItemStatus; location_id:number|null; warehouse_id:number|null; received_at:string|null; moved_out_at:string|null; sold_at:string|null; created_at:string }
export interface Stock { id:number; variant_id:number; location_id:number; quantity:number; reserved:number; updated_at:string }
export interface StockMovement { id:number; item_id:number|null; variant_id:number; location_id:number|null; type:StockMovementType; quantity:number; qty_before:number; qty_after:number; reference_type:string|null; reference_id:number|null; reason:string|null; channel_id:number|null; external_reference:string|null; unit_list_price:string|number|null; unit_sale_price:string|number|null; discount_total:string|number|null; line_total:string|number|null; unit_cost_snapshot:string|number|null; created_by:number|null; created_at:string }
export interface StockReservation { id:number; item_id:number|null; variant_id:number; location_id:number; reference_type:string; reference_id:number|null; reference_code:string|null; quantity:number; status:StockReservationStatus; expires_at:string|null; created_by:number|null; created_at:string }
export interface ProductDefaultLocation { id:number; variant_id:number; location_id:number; priority:number; is_primary:boolean }
export interface StockTransfer { id:number; transfer_number:string; item_id:number|null; variant_id:number; from_location_id:number; to_location_id:number; quantity:number; status:StockTransferStatus; requested_by:number; approved_by:number|null; completed_at:string|null; notes:string|null; created_at:string }
export interface StockAdjustment { id:number; adjustment_number:string; item_id:number|null; variant_id:number; location_id:number; type:StockAdjustmentType; quantity:number; reason:StockAdjustmentReason; reference_type:string|null; reference_id:number|null; approved_by:number|null; created_by:number; created_at:string }
export interface CycleCount { id:number; count_number:string; warehouse_id:number; location_id:number|null; status:CycleCountStatus; started_at:string|null; completed_at:string|null; created_by:number; notes:string|null }
export interface CycleCountLine { id:number; cycle_count_id:number; item_id:number; variant_id:number; location_id:number; system_qty:number; counted_qty:number; difference:number; status:CycleCountLineStatus; notes:string|null }
export interface StockOpening { id:number; variant_id:number; location_id:number; quantity:number; recorded_at:string; recorded_by:number }
export interface QCRecord { id:number; item_id:number; result:QCRecordResult; checked_by:number; checked_at:string; defect_type:string|null; defect_severity:DefectSeverity|null; failure_action:'rework'|'scrap'|null; waste_class:'normal'|'abnormal'|null; notes:string|null; photos:Array<Record<string,unknown>|string>|null; created_at:string }
export interface LabelLog { id:number; item_id:number; label_type:LabelType; printed_by:number; printed_at:string }

export interface Permission { id:number; code:string; name:string; description:string|null }
export interface Role { id:number; code:string; name:string; is_system:boolean; created_at:string; permissions:Permission[] }
export interface PermissionOverride { id:number; permission_id:number; is_allowed:boolean; permission:Permission }
export interface User { id:number; username:string|null; full_name:string; phone:string|null; email:string|null; user_type:UserType; panel_access:boolean; role_id:number|null; status:string; is_superuser:boolean; last_login_at:string|null; created_at:string; updated_at:string; role:Role|null; permission_overrides:PermissionOverride[]; effective_permissions:string[] }
export interface SalesChannel { id:number; code:string; name:string; is_active:boolean; notes:string|null; created_at:string }
export interface ChannelPrice { id:number; variant_id:number; channel_id:number; list_price:string|number; discount_type:'percent'|'fixed'|null; discount_value:string|number; starts_at:string|null; ends_at:string|null; is_active:boolean; created_at:string; updated_at:string; effective_price:string|number }
export interface SalesChannelSummary { channel_id:number|null; channel_name:string; quantity:number; outbound_count:number; gross_amount:string|number; discount_amount:string|number; net_amount:string|number }
export interface SalesSummary { quantity:number; outbound_count:number; gross_amount:string|number; discount_amount:string|number; net_amount:string|number; channels:SalesChannelSummary[] }
export interface Tailor { id:number; full_name:string; phone:string|null; status:string; panel_access:boolean; role_id:number|null }
export interface TailorWork { id:number; tailor_user_id:number; work_no:string; product_id:number|null; production_order_id:number|null; quantity:number; delivered_good:number; returned_for_fix:number; damaged:number; assigned_at:string; due_at:string|null; completed_at:string|null; status:string; notes:string|null; created_at:string }
export interface TailorStats { tailor_user_id:number; assigned:number; delivered_good:number; returned_for_fix:number; damaged:number; defect_rate:number; open_work:number; overdue_work:number }
export interface MonthlyTailorStats { month:string; delivered_good:number; returned_for_fix:number; damaged:number; defect_rate:number }
export interface Warranty { id:number; item_id:number; serial:string; status:string; warranty_months:number; customer_name:string|null; customer_phone:string|null; outbound_at:string|null; auto_activate_at:string|null; activated_at:string|null; expires_at:string|null; activation_source:string|null; qr_redirect_url:string|null; notes:string|null; created_at:string }
export interface WarrantySetting { id:number; name:string; base_url:string; qr_base_url:string|null; qr_destination_template:string|null; grace_period_months:number; is_default:boolean; created_at:string }
export interface EmployeeProfile { id:number; user_id:number; personnel_code:string; department:string|null; job_title:string|null; hire_date:string|null; national_id:string|null; address:string|null; emergency_phone:string|null; created_at:string }

export interface Account { id:number; code:string; name:string; account_type:'asset'|'liability'|'equity'|'revenue'|'expense'; parent_id:number|null; allow_posting:boolean; is_system:boolean; is_active:boolean; created_at:string }
export interface CostCenter { id:number; code:string; name:string; center_type:string; is_active:boolean; created_at:string }
export interface JournalLine { id:number; line_no:number; account_id:number; cost_center_id:number|null; debit:string|number; credit:string|number; memo:string|null; account:Account; cost_center:CostCenter|null }
export interface JournalEntry { id:number; number:string; entry_date:string; description:string; source_type:string|null; source_id:number|null; source_ref:string|null; status:string; created_by:number; posted_by:number|null; reversed_by_entry_id:number|null; created_at:string; posted_at:string|null; lines:JournalLine[] }
export interface AuditEvent { id:number; user_id:number|null; action:string; entity_type:string; entity_id:string|null; source_ref:string|null; before_data:Record<string,unknown>|null; after_data:Record<string,unknown>|null; created_at:string }
export interface TrialBalanceRow { account_id:number; code:string; name:string; account_type:string; debit:string|number; credit:string|number; balance:string|number }
export interface FinancialStatements { date_from:string|null; date_to:string|null; profit_and_loss:{revenue:string|number;expense:string|number;net_profit:string|number}; balance_sheet:{assets:string|number;liabilities:string|number;equity:string|number;check:string|number} }

export interface Material { id:number; code:string; name:string; unit:string; category:string|null; reorder_point:string|number; weighted_average_cost:string|number; is_active:boolean; created_at:string }
export interface MaterialStock { id:number; material_id:number; location_id:number; quantity:string|number; updated_at:string; material:Material }
export interface MaterialMovement { id:number; number:string; material_id:number; location_id:number; movement_type:string; quantity:string|number; unit_cost:string|number; total_cost:string|number; production_order_id:number|null; reference_type:string|null; reference_ref:string|null; notes:string|null; created_by:number; created_at:string; material:Material }
export interface BOMItem { id:number; material_id:number; quantity_per_unit:string|number; normal_waste_percent:string|number; material:Material }
export interface BOM { id:number; product_id:number; version:number; status:string; effective_from:string|null; effective_to:string|null; notes:string|null; created_by:number; created_at:string; items:BOMItem[] }
export interface ProductionOrder { id:number; order_no:string; product_id:number; variant_id:number|null; quantity:number; tailor_user_id:number|null; bom_id:number; fg_location_id:number|null; status:string; due_at:string|null; material_cost:string|number; labor_cost:string|number; overhead_cost:string|number; abnormal_scrap_cost:string|number; total_cost_snapshot:string|number|null; unit_cost_snapshot:string|number|null; prepared_units:number; qc_passed:number; qc_failed:number; notes:string|null; created_by:number; created_at:string; started_at:string|null; completed_at:string|null }
export interface LaborEntry { id:number; production_order_id:number; tailor_user_id:number; work_date:string; hours:string|number; pieces:number; rate:string|number; rate_basis:string; amount:string|number; status:string; notes:string|null; created_by:number; approved_by:number|null; approved_at:string|null; created_at:string }
export interface OverheadRate { id:number; name:string; basis:string; rate:string|number; effective_from:string; effective_to:string|null; is_active:boolean; created_by:number; created_at:string }

export interface SalesInvoiceLine { id:number; invoice_id:number; variant_id:number; item_id:number; location_id:number; warranty_id:number|null; reservation_id:number|null; quantity:number; unit_list_price:string|number; unit_sale_price:string|number; line_total:string|number; unit_cost_snapshot:string|number|null }
export interface SalesInvoice { id:number; number:string; channel_id:number; customer_name:string|null; customer_phone:string|null; external_reference:string|null; status:'draft'|'confirmed'|'shipped'|'partially_returned'|'returned'|'cancelled'|string; total_amount:string|number; created_by:number; confirmed_by:number|null; shipped_by:number|null; created_at:string; confirmed_at:string|null; shipped_at:string|null; notes:string|null; lines:SalesInvoiceLine[] }
export interface SalesReturnLine { id:number; return_id:number; invoice_line_id:number; item_id:number; location_id:number; refund_amount:string|number; unit_cost_snapshot:string|number }
export interface SalesReturn { id:number; number:string; invoice_id:number; reason:string|null; total_refund:string|number; created_by:number; created_at:string; lines:SalesReturnLine[] }
export interface CatalogFeedRow { variant_id:number; sku:string|null; available_quantity:number; list_price:string|number; sale_price:string|number }
