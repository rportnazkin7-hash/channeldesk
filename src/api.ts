const headers=()=>{const h=new Headers({'Content-Type':'application/json'});const data=window.Telegram?.WebApp?.initData;if(data)h.set('X-Telegram-Init-Data',data);return h}
async function req<T>(path:string,options:RequestInit={}):Promise<T>{const r=await fetch(path,{...options,headers:headers()});if(!r.ok){let m=`Ошибка ${r.status}`;try{const j=await r.json();m=j.detail||m}catch{}throw new Error(m)}return r.json()}
export type Workspace={id:number;name:string;role:string}
export type Pending={id:number;telegram_chat_id:number;title:string;username:string|null;bot_permissions:Record<string,boolean>}
export type Channel={id:number;title:string;username:string|null;is_connected:boolean}
export const api={
 workspaces:()=>req<Workspace[]>('/api/workspaces'),
 createWorkspace:(name:string)=>req<Workspace>('/api/workspaces',{method:'POST',body:JSON.stringify({name})}),
 pending:()=>req<Pending[]>('/api/channel-connections/pending'),
 channels:(wid:number)=>req<Channel[]>(`/api/workspaces/${wid}/channels`),
 connect:(wid:number,id:number)=>req<Channel>(`/api/workspaces/${wid}/channels/connect`,{method:'POST',body:JSON.stringify({connection_id:id})}),
}
