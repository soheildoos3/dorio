import { apiRequest, jsonBody } from '../lib/api';
import type { User } from './types';
export type AuthMe={user:User;permissions:string[]};
export const authApi={
 status:()=>apiRequest<{required:boolean}>('/auth/bootstrap-status'),
 bootstrap:(p:{username:string;full_name:string;password:string;email?:string|null;phone?:string|null})=>apiRequest<{ok:boolean}>('/auth/bootstrap',{method:'POST',body:jsonBody(p)}),
 login:(p:{identifier:string;password:string})=>apiRequest<{ok:boolean;panel_access:boolean}>('/auth/login',{method:'POST',body:jsonBody(p)}),
 logout:()=>apiRequest<{ok:boolean}>('/auth/logout',{method:'POST'}),
 me:()=>apiRequest<AuthMe>('/auth/me'),
};
