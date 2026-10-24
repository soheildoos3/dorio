import { apiRequest, jsonBody } from '../lib/api';
import type { AttributeDefinition, AttributeValue, Category, Media, Product, ProductAttributeSelection, ProductDetail, ProductStatus, ProductVariant } from './types';

export type CategoryPayload={parent_id?:number|null;name:string;sort_order?:number;is_active?:boolean};
export type ProductPayload={sku?:string|null;name:string;description?:string|null;category_id?:number|null;is_sellable?:boolean;is_manufacturable?:boolean;warranty_months?:number;status?:ProductStatus};
export type ProductVariantPayload={product_id:number;sku?:string|null;attribute_value_ids?:number[];sale_price?:number;is_active?:boolean};
export type MediaUploadPayload={product_id:number;variant_id?:number|null;file:File;is_primary?:boolean;sort_order?:number};
export type AttributePayload={code:string;name:string;is_variant_axis?:boolean;sort_order?:number};
export type AttributeValuePayload={attribute_id:number;value:string;sort_order?:number};
export type ProductAttributeConfigPayload={selections:{attribute_id:number;value_ids:number[];sort_order?:number}[]};

export const catalogApi={
 categories:(activeOnly=false)=>{const value=typeof activeOnly==='boolean'?activeOnly:false;return apiRequest<Category[]>(`/catalog/categories?active_only=${value}`)},
 createCategory:(p:CategoryPayload)=>apiRequest<Category>('/catalog/categories',{method:'POST',body:jsonBody(p)}),
 updateCategory:(id:number,p:Partial<CategoryPayload>)=>apiRequest<Category>(`/catalog/categories/${id}`,{method:'PATCH',body:jsonBody(p)}),
 deleteCategory:(id:number)=>apiRequest<void>(`/catalog/categories/${id}`,{method:'DELETE'}),
 products:()=>apiRequest<Product[]>('/catalog/products?offset=0&limit=500'),
 product:(id:number)=>apiRequest<ProductDetail>(`/catalog/products/${id}`),
 createProduct:(p:ProductPayload)=>apiRequest<Product>('/catalog/products',{method:'POST',body:jsonBody(p)}),
 updateProduct:(id:number,p:Partial<ProductPayload>)=>apiRequest<Product>(`/catalog/products/${id}`,{method:'PATCH',body:jsonBody(p)}),
 deleteProduct:(id:number)=>apiRequest<void>(`/catalog/products/${id}`,{method:'DELETE'}),
 variants:(productId?:number)=>{const id=typeof productId==='number'&&Number.isFinite(productId)?productId:undefined;return apiRequest<ProductVariant[]>(`/catalog/variants${id!=null?`?product_id=${id}`:''}`)},
 createVariant:(p:ProductVariantPayload)=>apiRequest<ProductVariant>('/catalog/variants',{method:'POST',body:jsonBody(p)}),
 updateVariant:(id:number,p:Partial<Omit<ProductVariantPayload,'product_id'>>)=>apiRequest<ProductVariant>(`/catalog/variants/${id}`,{method:'PATCH',body:jsonBody(p)}),
 deleteVariant:(id:number)=>apiRequest<void>(`/catalog/variants/${id}`,{method:'DELETE'}),
 productAttributes:(productId:number)=>apiRequest<ProductAttributeSelection[]>(`/catalog/products/${productId}/attributes`),
 setProductAttributes:(productId:number,p:ProductAttributeConfigPayload)=>apiRequest<ProductAttributeSelection[]>(`/catalog/products/${productId}/attributes`,{method:'PUT',body:jsonBody(p)}),
 generateVariants:(productId:number,defaultPrice:number)=>apiRequest<ProductVariant[]>(`/catalog/products/${productId}/generate-variants`,{method:'POST',body:jsonBody({default_price:defaultPrice,keep_existing:true})}),
 media:(productId:number)=>apiRequest<Media[]>(`/catalog/products/${productId}/media`),
 uploadMedia:async(p:MediaUploadPayload)=>{const f=new FormData();f.append('product_id',String(p.product_id));if(p.variant_id!=null)f.append('variant_id',String(p.variant_id));f.append('is_primary',String(!!p.is_primary));f.append('sort_order',String(p.sort_order||0));f.append('file',p.file);return apiRequest<Media>('/catalog/media/upload',{method:'POST',body:f})},
 updateMedia:(id:number,p:{variant_id?:number|null;is_primary?:boolean;sort_order?:number})=>apiRequest<Media>(`/catalog/media/${id}`,{method:'PATCH',body:jsonBody(p)}),
 deleteMedia:(id:number)=>apiRequest<void>(`/catalog/media/${id}`,{method:'DELETE'}),
 attributes:()=>apiRequest<AttributeDefinition[]>('/catalog/attributes'),
 createAttribute:(p:AttributePayload)=>apiRequest<AttributeDefinition>('/catalog/attributes',{method:'POST',body:jsonBody(p)}),
 updateAttribute:(id:number,p:Partial<AttributePayload>)=>apiRequest<AttributeDefinition>(`/catalog/attributes/${id}`,{method:'PATCH',body:jsonBody(p)}),
 deleteAttribute:(id:number)=>apiRequest<void>(`/catalog/attributes/${id}`,{method:'DELETE'}),
 attributeValues:(attributeId?:number)=>{const id=typeof attributeId==='number'&&Number.isFinite(attributeId)?attributeId:undefined;return apiRequest<AttributeValue[]>(`/catalog/attribute-values${id!=null?`?attribute_id=${id}`:''}`)},
 createAttributeValue:(p:AttributeValuePayload)=>apiRequest<AttributeValue>('/catalog/attribute-values',{method:'POST',body:jsonBody(p)}),
 updateAttributeValue:(id:number,p:Partial<Omit<AttributeValuePayload,'attribute_id'>>)=>apiRequest<AttributeValue>(`/catalog/attribute-values/${id}`,{method:'PATCH',body:jsonBody(p)}),
 deleteAttributeValue:(id:number)=>apiRequest<void>(`/catalog/attribute-values/${id}`,{method:'DELETE'}),
};
