import {apiRequest,jsonBody} from '../lib/api';
import type {User,UserType} from './types';
export type PermissionOverridePayload={permission_id:number;is_allowed:boolean};
export type UserPayload={username?:string|null;full_name:string;phone?:string|null;email?:string|null;user_type:UserType;panel_access:boolean;role_id?:number|null;status?:string;is_superuser?:boolean;password:string;permission_overrides?:PermissionOverridePayload[]};
export type UserUpdatePayload=Partial<Omit<UserPayload,'password'>> & {password?:string};
export const usersApi={
 list:(type?:UserType)=>{const safeType=typeof type==='string'?type:undefined;return apiRequest<User[]>(`/users?offset=0&limit=500${safeType?`&user_type=${safeType}`:''}`)},
 get:(id:number)=>apiRequest<User>(`/users/${id}`),
 create:(p:UserPayload)=>apiRequest<User>('/users',{method:'POST',body:jsonBody(p)}),
 update:(id:number,p:UserUpdatePayload)=>apiRequest<User>(`/users/${id}`,{method:'PATCH',body:jsonBody(p)}),
 remove:(id:number)=>apiRequest<void>(`/users/${id}`,{method:'DELETE'}),
};
