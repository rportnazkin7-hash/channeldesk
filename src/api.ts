const headers=()=>{const h=new Headers({'Content-Type':'application/json'});const data=window.Telegram?.WebApp?.initData;if(data)h.set('X-Telegram-Init-Data',data);return h}
async function req<T>(path:string,options:RequestInit={}):Promise<T>{const r=await fetch(path,{...options,headers:headers()});if(!r.ok){let m=`Ошибка ${r.status}`;try{const j=await r.json();m=j.detail||m}catch{}throw new Error(m)}return r.json()}
export type Workspace={id:number;name:string;role:string}
export type Pending={id:number;telegram_chat_id:number;title:string;username:string|null;bot_permissions:Record<string,boolean>}
export type Channel={id:number;title:string;username:string|null;is_connected:boolean}
export type Member={id:number;role:string;status:string;channel_scope:number[]|null;telegram_id:number;username:string|null;first_name:string|null;last_name:string|null}
export type Invite={id:number;role:string;max_uses:number|null;expires_at:string|null;token:string}
export type AuditEntry={id:number;action:string;entity_type:string;entity_id:number|null;created_at:string}
export const api={
 workspaces:()=>req<Workspace[]>('/api/workspaces'),
 createWorkspace:(name:string)=>req<Workspace>('/api/workspaces',{method:'POST',body:JSON.stringify({name})}),
 pending:()=>req<Pending[]>('/api/channel-connections/pending'),
 channels:(wid:number)=>req<Channel[]>(`/api/workspaces/${wid}/channels`),
 connect:(wid:number,id:number)=>req<Channel>(`/api/workspaces/${wid}/channels/connect`,{method:'POST',body:JSON.stringify({connection_id:id})}),
 members:(wid:number)=>req<Member[]>(`/api/workspaces/${wid}/members`),
 createInvite:(wid:number,role='viewer')=>req<Invite>(`/api/workspaces/${wid}/invites`,{method:'POST',body:JSON.stringify({role})}),
 acceptInvite:(token:string)=>req<{workspace_id:number;workspace_name:string;role:string}>(`/api/invites/accept`,{method:'POST',body:JSON.stringify({token})}),
 audit:(wid:number)=>req<AuditEntry[]>(`/api/workspaces/${wid}/audit`),
}
