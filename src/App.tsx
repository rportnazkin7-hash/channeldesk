import { useEffect,useState } from 'react'
import { BarChart3,CalendarDays,CirclePlus,Link2,Megaphone,MoreHorizontal,Radio,RefreshCw,Users } from 'lucide-react'
import { api,type Workspace,type Pending,type Channel,type Member,type Invite } from './api'

const APP_VERSION = 'v0.5.0'
const ROLE_LABEL:Record<string,string>={owner:'Владелец',admin:'Администратор',editor:'Редактор',author:'Автор',designer:'Дизайнер',ad_manager:'Рекламный менеджер',analyst:'Аналитик',viewer:'Наблюдатель'}

function errorHint(msg:string):string{
 if(msg.includes('401')) return 'Telegram-авторизация не получена. Откройте приложение через Telegram (кнопка WebApp у @channel_desk_bot), а не через браузер.'
 if(msg.includes('503')) return 'Серверная служба недоступна: проверьте DATABASE_URL на Vercel и состояние БД Supabase.'
 if(msg.includes('500')) return 'Внутренняя ошибка сервера. Проверьте журналы Vercel и состояние миграций БД.'
 if(msg.includes('429')) return 'Слишком много запросов. Подождите минуту и обновите экран.'
 if(msg.includes('Нет соединения')||msg.includes('не ответил')) return 'Проверьте интернет-соединение и обновите экран (кнопка со стрелками вверху).'
 return ''
}

export default function App(){
 const [spaces,setSpaces]=useState<Workspace[]>([]),[active,setActive]=useState<Workspace|null>(null),[pending,setPending]=useState<Pending[]>([]),[channels,setChannels]=useState<Channel[]>([]),[members,setMembers]=useState<Member[]>([]),[invite,setInvite]=useState<Invite|null>(null),[copied,setCopied]=useState(false),[joined,setJoined]=useState<{workspace_name:string;role:string}|null>(null),[name,setName]=useState('Моё агентство'),[error,setError]=useState(''),[loading,setLoading]=useState(true)
 const hasInitData=!!(window.Telegram?.WebApp?.initData)
 async function load(){setLoading(true);setError('');try{const s=await api.workspaces();setSpaces(s);const a=active&&s.some(x=>x.id===active.id)?active:s[0]||null;setActive(a);const [p,c,m]=await Promise.all([api.pending(),a?api.channels(a.id):Promise.resolve([]),a?api.members(a.id):Promise.resolve([])]);setPending(p);setChannels(c);setMembers(m);setInvite(null)}catch(e){setError(e instanceof Error?e.message:'Ошибка загрузки')}finally{setLoading(false)}}
 useEffect(()=>{const sp=window.Telegram?.WebApp?.initDataUnsafe?.start_param||'';if(sp.startsWith('invite_')){api.acceptInvite(sp.slice('invite_'.length)).then(res=>{setJoined({workspace_name:res.workspace_name,role:res.role});return load()}).catch(e=>{setError(e instanceof Error?e.message:'Ошибка принятия приглашения');return load()})}else{load()}},[])
 async function create(){try{await api.createWorkspace(name);await load()}catch(e){setError(e instanceof Error?e.message:'Ошибка')}}
 async function connect(id:number){if(!active)return;try{await api.connect(active.id,id);await load()}catch(e){setError(e instanceof Error?e.message:'Ошибка подключения')}}
 async function makeInvite(){if(!active)return;setError('');try{const iv=await api.createInvite(active.id,'editor');setInvite(iv);setCopied(false)}catch(e){setError(e instanceof Error?e.message:'Ошибка создания приглашения')}}
 async function copyInvite(){if(!invite)return;try{await navigator.clipboard.writeText(invite.token);setCopied(true)}catch{setCopied(false)}}
 const canManage=active?.role==='owner'||active?.role==='admin'
 const hint=error?errorHint(error):''
 return <div className="app"><header><div><span className="eyebrow">РАБОЧЕЕ ПРОСТРАНСТВО</span><h1>ChannelDesk</h1></div><button className="workspace" onClick={load} title="Обновить"><RefreshCw size={15}/></button></header><main>
  {!hasInitData&&<section className="panel warn"><strong>⚠ Приложение работает только внутри Telegram</strong><p>Откройте его через бота <code>@channel_desk_bot</code> (кнопка «Открыть ChannelDesk») — так Telegram передаст авторизацию.</p></section>}
  {error&&<section className="panel err"><strong>{error}</strong>{hint&&<p className="hint">{hint}</p>}</section>}
  {joined&&<section className="panel ok">✓ Вы присоединились к «{joined.workspace_name}» (роль: {ROLE_LABEL[joined.role]||joined.role})</section>}
  {!active&&!loading?<section className="hero"><p>Создайте рабочее пространство агентства.</p><input value={name} onChange={e=>setName(e.target.value)} style={{width:'100%',padding:13,borderRadius:12,border:'1px solid #445',background:'#111722',color:'white',marginBottom:12}}/><button onClick={create}><CirclePlus size={19}/> Создать</button></section>:<>
   <section className="hero"><span className="eyebrow">{active?.role}</span><p style={{marginTop:8}}>{active?.name}</p><div>{spaces.length>1&&<select value={active?.id} onChange={e=>setActive(spaces.find(x=>x.id===Number(e.target.value))||null)}>{spaces.map(w=><option key={w.id} value={w.id}>{w.name}</option>)}</select>}</div></section>
   {pending.length>0&&<section className="panel" style={{marginTop:16}}><div className="panel-title"><h2>Обнаруженные каналы</h2><Radio size={20}/></div>{pending.map(p=><article key={p.id} style={{padding:'14px 0',borderBottom:'1px solid #252b36'}}><strong>{p.title}</strong><p style={{color:'#8d96a8',fontSize:12}}>{p.bot_permissions.can_post_messages?'Публикация разрешена':'Нет права публикации'}</p><button onClick={()=>connect(p.id)} disabled={!p.bot_permissions.can_post_messages}>Подключить</button></article>)}</section>}
   <section className="stats"><article><span>Каналы</span><strong>{channels.length}</strong></article><article><span>Запланировано</span><strong>0</strong></article><article><span>На согласовании</span><strong>0</strong></article><article><span>Доход</span><strong>0 ₽</strong></article></section>
   <section className="panel"><div className="panel-title"><h2>Каналы</h2><CalendarDays size={20}/></div>{channels.length?channels.map(c=><div key={c.id} style={{padding:'15px 0',borderBottom:'1px solid #252b36'}}><strong>{c.title}</strong><div style={{color:'#72d99f',fontSize:12}}>● подключён</div></div>):<div className="empty"><div className="empty-icon"><Megaphone/></div><h3>Каналов пока нет</h3><p>Добавьте бота администратором канала и обновите экран.</p></div>}</section>
   {active&&<section className="panel" style={{marginTop:16}}><div className="panel-title"><h2>Команда</h2><Users size={20}/></div>
    {canManage&&<button className="invite-btn" onClick={makeInvite}><Link2 size={15}/> Создать приглашение (редактор)</button>}
    {invite&&<div className="invite-box"><p>Токен приглашения: <code>{invite.token}</code></p><p className="hint">Ссылка для сотрудника: <code>https://t.me/channel_desk_bot?start=invite_{invite.token}</code></p><button onClick={copyInvite}>{copied?'Скопировано':'Скопировать токен'}</button></div>}
    {members.length?members.map(m=><div key={m.id} style={{padding:'13px 0',borderBottom:'1px solid #252b36',display:'flex',justifyContent:'space-between',alignItems:'center'}}><strong>{m.first_name||m.username||`ID ${m.telegram_id}`}</strong><span style={{color:'#8d96a8',fontSize:12}}>{ROLE_LABEL[m.role]||m.role}</span></div>):<div className="empty"><p>Участников пока нет.</p></div>}
   </section>}
  </>}
  <div className="ver">ChannelDesk {APP_VERSION}</div>
 </main><nav>{[[BarChart3,'Обзор'],[CalendarDays,'Календарь'],[CirclePlus,'Создать'],[Megaphone,'Реклама'],[MoreHorizontal,'Ещё']].map(([Icon,label],i)=>{const C=Icon as typeof BarChart3;return <button className={i===0?'active':''} key={label as string}><C size={21}/><span>{label as string}</span></button>})}</nav></div>
}
